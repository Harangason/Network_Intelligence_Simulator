"""Existing IPv4 address and Internet checksum encoding used by native exports."""
import struct

def ip_bytes(ip: str) -> bytes:
    return bytes(int(part) for part in ip.split("."))


def internet_checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total > 0xFFFF:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def pseudo_header(src, dst, version, protocol, length):
    return src + dst + (struct.pack('!BBH', 0, protocol, length) if version == 4 else struct.pack('!I3xB', length, protocol))

def packet_header(src, dst, version, protocol, length, identification):
    if version == 4:
        header = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20 + length, identification & 0xffff, 0x4000, 64, protocol, 0, src, dst)
        return header[:10] + struct.pack('!H', internet_checksum(header)) + header[12:]
    return struct.pack('!IHBB16s16s', 6 << 28, length, protocol, 64, src, dst)
