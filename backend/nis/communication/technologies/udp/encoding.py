"""Existing UDP header and checksum encoding; no new transport capability."""
import struct
from backend.nis.communication.technologies.ip.encoding import internet_checksum, pseudo_header

def header(source_port, destination_port, payload_size):
    return struct.pack('!HHHH', source_port, destination_port, 8 + payload_size, 0)

def checksum_header(raw, payload, src, dst, version, *, encode_zero=True):
    check = internet_checksum(pseudo_header(src, dst, version, 17, len(raw) + len(payload)) + raw + payload)
    if encode_zero and check == 0:
        check = 0xffff
    return raw[:6] + struct.pack('!H', check) + raw[8:]
