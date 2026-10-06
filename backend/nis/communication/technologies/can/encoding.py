"""Preserved CAN example checksum and bit packing contracts."""
from __future__ import annotations

def crc8_autosar(data: bytes, start_value: int = 0xFF, final_xor: int = 0xFF) -> int:
    crc = start_value
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x1D) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc ^ final_xor


def set_unsigned_le(payload: bytearray, start_bit: int, length: int, value: int) -> None:
    value &= (1 << length) - 1
    for bit in range(length):
        absolute_bit = start_bit + bit
        byte_index = absolute_bit // 8
        if byte_index >= len(payload):
            return
        bit_index = absolute_bit % 8
        if value & (1 << bit):
            payload[byte_index] |= 1 << bit_index
        else:
            payload[byte_index] &= ~(1 << bit_index)


def get_unsigned_le(payload: bytes, start_bit: int, length: int) -> int:
    value = 0
    for bit in range(length):
        absolute_bit = start_bit + bit
        byte_index = absolute_bit // 8
        if byte_index >= len(payload):
            return value
        bit_index = absolute_bit % 8
        if payload[byte_index] & (1 << bit_index):
            value |= 1 << bit
    return value


def set_unsigned_le_strict(payload: bytearray, start_bit: int, length: int, value: int) -> None:
    """Setzt ein unsigned little-endian / Intel Signal bitweise."""
    max_value = (1 << length) - 1
    value = int(value) & max_value
    for bit in range(length):
        absolute_bit = start_bit + bit
        byte_index = absolute_bit // 8
        bit_index = absolute_bit % 8
        if value & (1 << bit):
            payload[byte_index] |= 1 << bit_index
        else:
            payload[byte_index] &= ~(1 << bit_index)


def verify_payload_crc(payload: bytes) -> bool:
    if len(payload) < 2:
        return False
    return payload[0] == crc8_autosar(payload[1:])
