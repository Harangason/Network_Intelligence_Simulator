"""Existing SOME/IP header encoder and native trace example payloads."""
from __future__ import annotations
import struct
from backend.nis.traces.trace_support import route_label

SOMEIP_REQUEST = 0x00
SOMEIP_REQUEST_NO_RETURN = 0x01
SOMEIP_NOTIFICATION = 0x02
SOMEIP_RESPONSE = 0x80

def build_someip_payload(service_id: int, method_id: int, client_id: int, session_id: int, message_type: int, payload: bytes) -> bytes:
    length = 8 + len(payload)
    return struct.pack("!HHIHHBBBB", service_id, method_id, length, client_id, session_id, 1, 1, message_type, 0) + payload


def someip_payload_text(kind: str, src_node: str, dst_node: str, service_id: int, sequence: int) -> bytes:
    if kind == "sd_offer":
        return f"SD OFFER service=0x{service_id:04X} provider={src_node}".encode("ascii")
    if kind == "sd_find":
        return f"SD FIND service=0x{service_id:04X} consumer={src_node}".encode("ascii")
    if kind == "subscribe":
        return f"SUBSCRIBE eventgroup=0x0001 service=0x{service_id:04X}".encode("ascii")
    if kind == "subscribe_ack":
        return f"SUBSCRIBE_ACK eventgroup=0x0001 service=0x{service_id:04X}".encode("ascii")
    if src_node == "LIDAR_FRONT":
        objects = []
        for obj_id in range(1, 5):
            x_cm = 1200 + sequence * 7 + obj_id * 135
            y_cm = -180 + obj_id * 95
            vx_cms = -60 + obj_id * 12
            confidence = 82 + (sequence + obj_id) % 15
            objects.append(f"id={obj_id},x_cm={x_cm},y_cm={y_cm},vx_cms={vx_cms},class=vehicle,conf={confidence}")
        return ("LIDAR_OBJECT_LIST ts_ms=%d " % sequence + ";".join(objects)).encode("ascii")
    if src_node == "CAMERA_FRONT_WIDE":
        return f"CAMERA_LANE_MODEL ts_ms={sequence} left_q=91 right_q=88 curvature=0.0012 objects=3".encode("ascii")
    if src_node == "RADAR_FRONT_LONG_RANGE":
        return f"RADAR_TARGET_LIST ts_ms={sequence} tracks=6 range_m=42.3 range_rate_mps=-2.1 azimuth_deg=1.8".encode("ascii")
    return f"{route_label(src_node, dst_node)} seq={sequence} service=0x{service_id:04X}".encode("ascii")
