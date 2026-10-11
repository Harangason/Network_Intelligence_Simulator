"""CAN native-example routing compatibility contract."""
from backend.nis.communication.technologies.can.formats.trace_model import normalize_routing_row

def normalized_routing_row(row, index, channel_count):
    normalized = normalize_routing_row(row, index, channel_count)
    keys = ('sender', 'receiver', 'cycle_ms', 'channel', 'gateway_to_channel', 'frame_id', 'name')
    return {**{key: normalized[key] for key in keys}, **{key: value for key, value in normalized.items() if key not in keys}}
