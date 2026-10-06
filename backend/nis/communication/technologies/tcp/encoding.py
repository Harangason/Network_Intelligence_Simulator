"""Existing fixed TCP header encoding for the project data-plane emulator."""
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
