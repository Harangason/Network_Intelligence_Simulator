"""Preserved Ethernet/IPv4/UDP/SOME-IP native example trace adapter.

The protocol stack is explicit. This example writer supplies no project defaults
and makes no additional capacity or native transport support claim.
"""
from __future__ import annotations
import random
import struct
from dataclasses import dataclass
from backend.nis.traces.trace_support import utc_now
from backend.nis.industries.automotive.templates.trace_example import trace_example
from backend.nis.communication.technologies.ip.encoding import ip_bytes, internet_checksum
from backend.nis.communication.technologies.someip.encoding import build_someip_payload, someip_payload_text, SOMEIP_REQUEST, SOMEIP_REQUEST_NO_RETURN, SOMEIP_NOTIFICATION, SOMEIP_RESPONSE
from backend.nis.communication.technologies.someip_sd.constants import SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID

ETHERNET_NODES = {key:tuple(value) for key,value in trace_example()['ETHERNET_NODES'].items()}

@dataclass(frozen=True)
class EthernetFrame:
    timestamp: float
    rel_time: float
    src_node: str
    dst_node: str
    src_mac: str
    dst_mac: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    service_id: int
    method_id: int
    message_type: int
    payload: bytes


def mac_bytes(mac: str) -> bytes:
    return bytes(int(part, 16) for part in mac.split(":"))


def build_udp_ipv4_ethernet_packet(frame: EthernetFrame) -> bytes:
    udp_payload = build_someip_payload(frame.service_id, frame.method_id, 0x1001, int(frame.rel_time * 1000) & 0xFFFF, frame.message_type, frame.payload)
    from backend.nis.communication.technologies.ip.encoding import packet_header
    from backend.nis.communication.technologies.udp.encoding import header, checksum_header
    src, dst = ip_bytes(frame.src_ip), ip_bytes(frame.dst_ip)
    udp_header = header(frame.src_port, frame.dst_port, len(udp_payload))
    udp_header = checksum_header(udp_header, udp_payload, src, dst, 4, encode_zero=False)
    ip_header = packet_header(src, dst, 4, 17, len(udp_header) + len(udp_payload), int(frame.rel_time * 1000))
    return mac_bytes(frame.dst_mac) + mac_bytes(frame.src_mac) + struct.pack("!H", 0x0800) + ip_header + udp_header + udp_payload


def make_ethernet_frame(
    start_utc: float,
    rel_time: float,
    src_node: str,
    dst_node: str,
    src_port: int,
    dst_port: int,
    service_id: int,
    method_id: int,
    message_type: int,
    payload: bytes,
) -> EthernetFrame:
    src_mac, src_ip = ETHERNET_NODES[src_node]
    dst_mac, dst_ip = ETHERNET_NODES[dst_node]
    return EthernetFrame(
        timestamp=start_utc + rel_time,
        rel_time=rel_time,
        src_node=src_node,
        dst_node=dst_node,
        src_mac=src_mac,
        dst_mac=dst_mac,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        service_id=service_id,
        method_id=method_id,
        message_type=message_type,
        payload=payload,
    )


def build_ethernet_trace(duration: float = 1.0, messages: int = 10, seed: int = 42, start_utc: float | None = None) -> list[EthernetFrame]:
    rng = random.Random(seed)
    start_utc = utc_now() if start_utc is None else start_utc
    endpoints = [
        ("LIDAR_FRONT", "CENTRAL_GATEWAY", "ADAS_DOMAIN", 20, 0x1234, 0x0421),
        ("CAMERA_FRONT_WIDE", "CENTRAL_GATEWAY", "ADAS_DOMAIN", 33, 0x1235, 0x0422),
        ("RADAR_FRONT_LONG_RANGE", "CENTRAL_GATEWAY", "ADAS_DOMAIN", 20, 0x1236, 0x0423),
        ("ADAS_DOMAIN", "CENTRAL_GATEWAY", "VEHICLE_MOTION_CONTROLLER", 20, 0x2234, 0x0101),
    ]
    frames: list[EthernetFrame] = []
    for index in range(messages):
        src_node, gateway_node, dst_node, cycle_ms, service_id, method_id = endpoints[index % len(endpoints)]
        base = 0.001 + index * 0.015
        src_port = 30500 + index
        dst_port = 30490
        frames.extend(
            [
                make_ethernet_frame(start_utc, base, src_node, gateway_node, src_port, dst_port, SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID, SOMEIP_NOTIFICATION, someip_payload_text("sd_offer", src_node, gateway_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.001, dst_node, gateway_node, src_port + 100, dst_port, SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID, SOMEIP_REQUEST, someip_payload_text("sd_find", dst_node, gateway_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.002, gateway_node, dst_node, dst_port, src_port + 100, SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID, SOMEIP_NOTIFICATION, someip_payload_text("sd_offer", gateway_node, dst_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.003, dst_node, gateway_node, src_port + 100, dst_port, service_id, method_id, SOMEIP_REQUEST, someip_payload_text("subscribe", dst_node, gateway_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.004, gateway_node, dst_node, dst_port, src_port + 100, service_id, method_id, SOMEIP_RESPONSE, someip_payload_text("subscribe_ack", gateway_node, dst_node, service_id, 0)),
                make_ethernet_frame(start_utc, base + 0.005, src_node, gateway_node, src_port, dst_port, service_id, method_id, SOMEIP_REQUEST, f"CONNECT_REQ {src_node}->{dst_node}".encode("ascii")),
                make_ethernet_frame(start_utc, base + 0.006, gateway_node, src_node, dst_port, src_port, service_id, method_id, SOMEIP_RESPONSE, f"CONNECT_ACK route={src_node}->{dst_node}".encode("ascii")),
            ]
        )
        rel_time = base + 0.010
        while rel_time <= duration:
            jittered = max(0.0, rel_time + rng.uniform(-0.0002, 0.0005))
            sequence = int(jittered * 1000)
            sensor_payload = someip_payload_text("notification", src_node, dst_node, service_id, sequence)
            frames.append(make_ethernet_frame(start_utc, jittered, src_node, gateway_node, src_port, dst_port, service_id, method_id, SOMEIP_NOTIFICATION, sensor_payload))
            frames.append(make_ethernet_frame(start_utc, jittered + rng.uniform(0.0008, 0.0018), gateway_node, dst_node, dst_port, src_port + 100, service_id, method_id, SOMEIP_NOTIFICATION, sensor_payload + b";gw=forwarded"))
            if int(sequence / max(1, cycle_ms)) % 10 == 0:
                frames.append(make_ethernet_frame(start_utc, jittered + rng.uniform(0.0020, 0.0035), dst_node, gateway_node, src_port + 100, dst_port, service_id, method_id, SOMEIP_RESPONSE, f"APP_ACK service=0x{service_id:04X} seq={sequence}".encode("ascii")))
            rel_time += cycle_ms / 1000.0
    return sorted(frames, key=lambda frame: frame.timestamp)
