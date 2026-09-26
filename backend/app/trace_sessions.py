"""Project-scoped, immutable imported trace sessions with bounded JSONL windows."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from uuid import uuid4
from flask import jsonify, request
from .saved_storage import project_folder
from .trace_service import read_trace_window
from .trace_import import (trace_import_api, detect_format, text_records, can_records,
                           capture_records, mdf_records, normalize_record)


def session_root():
    root = project_folder(request.headers.get('X-Project-ID') or 'default') / 'trace-imports'
    if root.is_symlink():
        raise ValueError('Ungültiger Trace-Speicherort.')
    return root


def _publish_session(stage, destination):
    """Publish atomically, allowing short-lived Windows directory handle locks."""
    delays = (0.05, 0.1, 0.2, 0.4)
    for attempt in range(len(delays) + 1):
        if destination.exists():
            raise FileExistsError('Die Trace-Session existiert bereits.')
        try:
            os.replace(stage, destination)
            return
        except PermissionError:
            if attempt == len(delays) or destination.exists() or not stage.is_dir():
                raise
            time.sleep(delays[attempt])


def persist_import(data, filename, source_path):
    fmt = detect_format(data, filename)
    warnings = []
    if fmt in ('json','jsonl','csv'):
        records = text_records(data, fmt, source_path)
    elif fmt in ('asc','blf','log','trc'):
        records = can_records(data, fmt, source_path)
        warnings.append('CAN-Rohdaten; Signaldecodierung benötigt eine passende Datenbank.')
    elif fmt in ('pcap','pcapng'):
        records = capture_records(data, fmt)
        warnings.append('Paket-Rohdaten; keine anwendungsspezifische Signaldecodierung.')
    else:
        records = mdf_records(data, warnings, source_path)
    root = session_root()
    root.mkdir(parents=True, exist_ok=True)
    session_id = uuid4().hex
    destination = root / session_id
    with tempfile.TemporaryDirectory(prefix='.import-', dir=root) as directory:
        stage = Path(directory)
        count = 0
        entries = []
        technologies, networks, time_bases = set(), set(), set()
        first_time, last_time, missing_times = None, None, 0
        ordered, previous_time = True, -1.0
        with (stage / 'events.jsonl').open('wb') as target:
            try:
                for index, raw in enumerate(records):
                    event = normalize_record(raw, index)
                    event['event_id'] = f'{session_id}:{index}'
                    line = (json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n').encode('utf8')
                    if len(line) > 1_048_576:
                        raise ValueError('Ein Trace-Ereignis überschreitet 1 MiB.')
                    timestamp = event.get('timestamp')
                    for field, values in (('technology', technologies), ('network_id', networks), ('network', networks), ('time_basis', time_bases)):
                        value = event.get(field)
                        if value is not None:
                            if not isinstance(value, str) or not value.strip():
                                raise ValueError(f'Ungültige Trace-Metadaten: {field}.')
                            values.add(value)
                    if not event.get('time_basis'):
                        time_bases.add('unknown')
                    if timestamp is None:
                        missing_times += 1
                    else:
                        first_time = timestamp if first_time is None else min(first_time, timestamp)
                        last_time = timestamp if last_time is None else max(last_time, timestamp)
                    if timestamp is None or timestamp < previous_time:
                        ordered = False
                    if timestamp is not None:
                        previous_time = timestamp
                        if index % 1000 == 0 and len(entries) < 50000:
                            entries.append([timestamp, target.tell()])
                    target.write(line)
                    count += 1
            finally:
                records.close()
        if not count:
            raise ValueError('Keine unterstützten Ereignisse in der Datei gefunden.')
        stat = (stage / 'events.jsonl').stat()
        # An index must not treat unrelated clocks as one ordered timeline.
        ordered = ordered and len(time_bases) == 1
        (stage / 'events.index.json').write_text(json.dumps(dict(schema='trace-time-index-v1',
            ordered=ordered, entries=entries, size_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)), encoding='utf8')
        metadata = dict(session_id=session_id, filename=Path(filename).name, format=fmt,
                        source_sha256=hashlib.sha256(data).hexdigest(), total_events=count,
                        warnings=warnings, analysis_only=True, partial=any('nicht' in warning for warning in warnings))
        metadata.update(source_type='ImportTrace', source=Path(filename).name,
                        simulation_run_ref=None, technologies=sorted(technologies), networks=sorted(networks),
                        metadata={'filename': Path(filename).name, 'format': fmt, 'analysis_only': True},
                        time_range={'start_s': first_time if len(time_bases) == 1 else None,
                                    'end_s': last_time if len(time_bases) == 1 else None},
                        timebase={'unit': 's', 'bases': sorted(time_bases), 'missing_timestamps': missing_times},
                        sync_status=('unavailable' if missing_times else 'unknown' if 'unknown' in time_bases
                                     else 'unsynchronized' if len(time_bases) > 1 else 'single_timebase'))
        shutil.copyfile(source_path, stage / 'source.trace')
        (stage / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf8')
        # Both paths are newly allocated direct children of the scoped root.
        assert stage.resolve().parent == root.resolve() == destination.resolve().parent
        _publish_session(stage, destination)
    return session_window(session_id, limit=2000)


def session_window(session_id, **options):
    if not re.fullmatch('[a-f0-9]{32}', session_id):
        raise ValueError('Ungültige Trace-Session.')
    root = session_root()
    folder = root / session_id
    if folder.is_symlink() or folder.resolve().parent != root.resolve():
        raise ValueError('Ungültiger Trace-Speicherort.')
    metadata = json.loads((folder / 'metadata.json').read_text(encoding='utf8'))
    page = read_trace_window(folder / 'events.jsonl', **options)
    from .e2e_assurance import build_sequence_model
    sequence_events = [{**event, 'time_s': event.get('timestamp'), 'source_name': event.get('source'),
                        'destination_names': [event.get('destination')] if event.get('destination') else []}
                       for event in page['events']]
    return {**metadata, **page,
            'sequence_model': build_sequence_model(sequence_events, source='OBSERVED'),
            'imported_events': len(page['events']), 'truncated': metadata['partial']}


