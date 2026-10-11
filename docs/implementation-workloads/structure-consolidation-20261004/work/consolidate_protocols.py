from edit_utils import read, write, extract, apply

ip = 'backend/nis/communication/technologies/ip/encoding.py'
write(ip, read(ip) + '''

def pseudo_header(src, dst, version, protocol, length):
    return src + dst + (struct.pack('!BBH', 0, protocol, length) if version == 4 else struct.pack('!I3xB', length, protocol))

def packet_header(src, dst, version, protocol, length, identification):
    if version == 4:
        header = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20 + length, identification & 0xffff, 0x4000, 64, protocol, 0, src, dst)
        return header[:10] + struct.pack('!H', internet_checksum(header)) + header[12:]
    return struct.pack('!IHBB16s16s', 6 << 28, length, protocol, 64, src, dst)
''')
write('backend/nis/communication/technologies/udp/encoding.py', '''"""Existing UDP header and checksum encoding; no new transport capability."""
import struct
from backend.nis.communication.technologies.ip.encoding import internet_checksum, pseudo_header

def header(source_port, destination_port, payload_size):
    return struct.pack('!HHHH', source_port, destination_port, 8 + payload_size, 0)

def checksum_header(raw, payload, src, dst, version, *, encode_zero=True):
    check = internet_checksum(pseudo_header(src, dst, version, 17, len(raw) + len(payload)) + raw + payload)
    if encode_zero and check == 0:
        check = 0xffff
    return raw[:6] + struct.pack('!H', check) + raw[8:]
''')
write('backend/nis/communication/technologies/tcp/encoding.py', '''"""Existing fixed TCP header encoding for the project data-plane emulator."""
import struct
from backend.nis.communication.technologies.ip.encoding import internet_checksum, pseudo_header

def header(event, source_port, destination_port, payload):
    sequence = int(event.get('transport_sequence_bytes', int(event['sequence']) * len(payload))) & 0xffffffff
    acknowledgement = int(event.get('transport_ack_number') or 0) & 0xffffffff
    flags = int(event.get('tcp_flags', 0x18 if payload else 0x10)) & 0xff
    return struct.pack('!HHIIBBHHH', source_port, destination_port, sequence, acknowledgement, 5 << 4, flags, 65535, 0, 0)

def checksum_header(raw, payload, src, dst, version):
    check = internet_checksum(pseudo_header(src, dst, version, 6, len(raw) + len(payload)) + raw + payload)
    return raw[:16] + struct.pack('!H', check) + raw[18:]
''')
path = 'backend/nis/communication/technologies/ethernet/transport.py'
_, source = extract(read(path), {'checksum'})
source = source.replace('ETHERNET_TECHNOLOGIES =', '''from backend.nis.communication.technologies.ip.encoding import internet_checksum as checksum, packet_header
from backend.nis.communication.technologies.udp import encoding as udp_encoding
from backend.nis.communication.technologies.tcp import encoding as tcp_encoding

ETHERNET_TECHNOLOGIES =''', 1)
start = source.index('    if protocol == 17:\n', source.index('def packet_bytes'))
end = source.index('    length = ', start)
source = source[:start] + '''    encoder = udp_encoding if protocol == 17 else tcp_encoding
    transport = udp_encoding.header(sport, dport, len(payload)) if protocol == 17 else tcp_encoding.header(event, sport, dport, payload)
''' + source[end:]
start = source.index('    pseudo = ', source.index('def packet_bytes'))
end = source.index('    ethertype = ', start)
source = source[:start] + '''    transport = encoder.checksum_header(transport, payload, src, dst, version)
    header = packet_header(src, dst, version, protocol, length, int(event['sequence']))
''' + source[end:]
write(path, source)
path = 'backend/nis/communication/technologies/ethernet/formats/trace_model.py'
source = read(path)
start = source.index('    udp_len = ', source.index('def build_udp_ipv4_ethernet_packet'))
end = source.index('    return mac_bytes', start)
source = source[:start] + '''    from backend.nis.communication.technologies.ip.encoding import packet_header
    from backend.nis.communication.technologies.udp.encoding import header, checksum_header
    src, dst = ip_bytes(frame.src_ip), ip_bytes(frame.dst_ip)
    udp_header = header(frame.src_port, frame.dst_port, len(udp_payload))
    udp_header = checksum_header(udp_header, udp_payload, src, dst, 4, encode_zero=False)
    ip_header = packet_header(src, dst, 4, 17, len(udp_header) + len(udp_payload), int(frame.rel_time * 1000))
''' + source[end:]
write(path, source)
# Retain the public simulator exports; the native CAN adapter owns its settings.
path = 'backend/nis/simulation/communication_simulator.py'
source = read(path)
chunk, source = extract(source, {'_native_participants', '_native_configuration'})
chunk = chunk.replace('    ethernet_enabled = bool(technologies & ETHERNET_TECHNOLOGIES)\n', '')
constants = source[source.index('NATIVE_CAN_FORMATS ='):source.index('DEFAULT_GOLDEN_TRACE_EVENT_LIMIT')]
source = source.replace(constants, '''from backend.nis.communication.technologies.can.formats.native_configuration import (
    NATIVE_CAN_FORMATS, NATIVE_ETHERNET_FORMATS, CAN_TECHNOLOGIES, ETHERNET_TECHNOLOGIES,
    _native_participants, _native_configuration,
)
''')
write('backend/nis/communication/technologies/can/formats/native_configuration.py', '''"""Existing standalone native-export configuration, not project rate defaults."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from backend.nis.simulation.bus_technologies import normalize_technology_id
from backend.nis.simulation.hardware_profile import iter_network_interfaces as _all_interfaces
CONFIG_SCHEMA = 'communication-simulator.simulation-config.v1'
''' + constants + '\n' + chunk)
write(path, source)
apply('protocol-encoding-owners')
