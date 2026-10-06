"""CAN native-example routing compatibility contract."""
from backend.nis.communication.technologies.can.formats.trace_model import normalize_routing_row

def normalized_routing_row(row, index, channel_count):
    normalized = normalize_routing_row(row, index, channel_count)
    keys = ('sender', 'receiver', 'cycle_ms', 'channel', 'gateway_to_channel', 'frame_id', 'name')
    return {**{key: normalized[key] for key in keys}, **{key: value for key, value in normalized.items() if key not in keys}}

import csv
from pathlib import Path
from typing import Dict, List
from backend.nis.communication.technologies.can.formats.trace_model import DEFAULT_ROUTING_ROWS

def load_routing_table(path: Path, channel_count: int) -> List[Dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Routing table is empty: {path}")
    return [normalized_routing_row(row, index, channel_count) for index, row in enumerate(rows)]


def write_routing_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["name", "sender", "receiver", "cycle_ms", "channel", "gateway_to_channel", "frame_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in DEFAULT_ROUTING_ROWS:
            output_row = dict(row)
            output_row["frame_id"] = f"0x{int(output_row['frame_id']):X}"
            writer.writerow(output_row)

