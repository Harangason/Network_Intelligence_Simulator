"""Bounded JSONL windows; the browser never downloads the entire trace."""
from __future__ import annotations

import json
import math
from bisect import bisect_left
from pathlib import Path


def read_trace_window(path: Path, *, cursor=0, limit=500, start_s=0.0, end_s=1e15, query='') -> dict:
    if not 0 <= cursor or not 1 <= limit <= 2000:
        raise ValueError('Cursor muss positiv und das Limit zwischen 1 und 2000 liegen.')
    if not math.isfinite(start_s) or not math.isfinite(end_s) or start_s < 0 or end_s < start_s:
        raise ValueError('Ungültiges Trace-Zeitfenster.')
    selected, scanned, selected_bytes = [], 0, 0
    needle = str(query).casefold()
    ordered = False
    index_path = path.with_suffix('.index.json')
    try:
        if index_path.stat().st_size <= 2_097_152:
            index = json.loads(index_path.read_text(encoding='utf-8'))
            metadata = path.stat()
            entries = index.get('entries') or []
            ordered = (index.get('schema') == 'trace-time-index-v1' and index.get('ordered') is True
                and index.get('size_bytes') == metadata.st_size and index.get('mtime_ns') == metadata.st_mtime_ns
                and all(isinstance(row, list) and len(row) == 2 and math.isfinite(row[0]) and isinstance(row[1], int) and 0 <= row[1] < metadata.st_size for row in entries)
                and all(a[0] <= b[0] and a[1] < b[1] for a, b in zip(entries, entries[1:])))
            if ordered and cursor == 0 and entries:
                # Start BEFORE equal timestamps: a timestamp may span index blocks.
                position = max(0, bisect_left([row[0] for row in entries], start_s) - 1)
                cursor = entries[position][1]
    except (OSError, ValueError, TypeError, KeyError):
        # Missing/stale/invalid auxiliary index never changes trace contents.
        ordered = False
    reached_end = False
    with path.open('rb') as handle:
        if cursor > path.stat().st_size:
            raise ValueError('Cursor liegt außerhalb des Traces.')
        handle.seek(cursor)
        # A scan budget also bounds requests whose filters match no events.
        while (len(selected) < limit and scanned < 10_000
               and handle.tell() - cursor < 8_388_608 and selected_bytes < 2_097_152):
            line = handle.readline(1_048_577)
            if not line:
                break
            if len(line) > 1_048_576:
                raise ValueError('Ein Trace-Ereignis überschreitet 1 MiB.')
            scanned += 1
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError('Trace-Ereignisse müssen JSON-Objekte sein.')
            timestamp = float(event.get('time_s', event.get('timestamp_s', 0)))
            if ordered and timestamp > end_s:
                reached_end = True
                break
            if start_s <= timestamp <= end_s and (not needle or needle in line.decode('utf-8').casefold()):
                selected.append(event)
                selected_bytes += len(line)
        next_cursor = handle.tell()
        has_more = not reached_end and bool(handle.read(1))
    return {'events': selected, 'count': len(selected), 'scanned': scanned,
            'next_cursor': next_cursor if has_more else None, 'has_more': has_more,
            'start_s': start_s, 'end_s': end_s}
