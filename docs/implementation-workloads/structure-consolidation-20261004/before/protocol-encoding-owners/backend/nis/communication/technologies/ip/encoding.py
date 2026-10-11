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
