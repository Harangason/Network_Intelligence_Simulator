"""Compatibility exports for native trace adapters.

Algorithms live with CAN, Ethernet, IP and SOME/IP. Only timestamps, identifiers
and technology-neutral text output belong to the shared trace layer.
"""
from backend.nis.traces.trace_support import utc_now, iso_utc, route_label, safe_identifier, parse_optional_int, triangle_wave, write_text
from backend.nis.communication.technologies.can.formats.trace_model import SignalDef, MessageDef, CanFrame, normalize_routing_row, load_routing_table, write_routing_template, data_signals, response_signals, build_messages, encode_data_payload, encode_response_payload, iter_schedule, build_can_trace, ROUTE_INFO_START_BYTE, ROUTE_INFO_LENGTH, DEFAULT_ROUTING_ROWS
from backend.nis.communication.technologies.can.encoding import crc8_autosar, set_unsigned_le, get_unsigned_le
from backend.nis.communication.technologies.ethernet.formats.trace_model import EthernetFrame, mac_bytes, build_udp_ipv4_ethernet_packet, make_ethernet_frame, build_ethernet_trace, ETHERNET_NODES
from backend.nis.communication.technologies.ip.encoding import ip_bytes, internet_checksum
from backend.nis.communication.technologies.someip.encoding import build_someip_payload, someip_payload_text, SOMEIP_REQUEST, SOMEIP_REQUEST_NO_RETURN, SOMEIP_NOTIFICATION, SOMEIP_RESPONSE
from backend.nis.communication.technologies.someip_sd.constants import SOMEIP_SD_SERVICE_ID, SOMEIP_SD_METHOD_ID
from backend.nis.industries.automotive.templates.trace_example import trace_example
COMMUNICATION_PAIRS = [tuple(pair) for pair in trace_example()['COMMUNICATION_PAIRS']]
