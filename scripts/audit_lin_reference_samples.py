"""Read-only MF4/DBC and saved project audit; no source files or SQL are changed.

Use --reader-path for an isolated installation of mdf_iter, asammdf, cantools and numpy.
The report contains traffic metadata, not raw diagnostic payloads or VINs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from collections import Counter
from pathlib import Path
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace-root', type=Path, required=True)
    parser.add_argument('--dbc-root', type=Path, required=True)
    parser.add_argument('--capacity', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reader-path', type=Path)
    args = parser.parse_args()
    if args.reader_path:
        sys.path.insert(0, str(args.reader_path.resolve()))
    import asammdf
    import cantools
    import numpy as np
    from mdf_iter import MdfFile

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def intervals(times):
        values = np.diff(times) * 1000
        if not len(values):
            return None
        return dict(zip(('min', 'median', 'p95', 'max'),
                        (round(float(v), 6) for v in np.quantile(values, [0, .5, .95, 1]))))

    databases = []
    regular = None
    for path in sorted(args.dbc_root.rglob('*.dbc')):
        entry = {'file': str(path), 'sha256': digest(path)}
        try:
            database = cantools.database.load_file(path, strict=True)
            entry.update(messages=len(database.messages),
                         signals=sum(len(m.signals) for m in database.messages),
                         cycle_times_ms=sorted({m.cycle_time for m in database.messages
                                               if m.cycle_time is not None}),
                         payload_lengths=sorted({m.length for m in database.messages}))
            if path.name == 'OBD-v4.3.dbc':
                regular = database
        except Exception as exc:
            entry['error'] = f'{type(exc).__name__}: {exc}'
        databases.append(entry)

    traces = []
    files = sorted(set(args.trace_root.rglob('*.MF4')) | set(args.dbc_root.rglob('*.MF4')))
    for path in files:
        entry = {'file': str(path), 'sha256': digest(path), 'groups': []}
        # The CANedge reader handles packed fields in these unsorted/unfinalized
        # samples. Generic composite MDF records can expose unmasked bit fields.
        with path.open('rb') as stream:
            mdf = MdfFile(stream)
            for kind, getter in (('CAN_DataFrame', mdf.get_data_frame_can),
                                 ('LIN_Frame', mdf.get_data_frame_lin)):
                frame = getter()
                count = len(frame)
                info = {'kind': kind, 'records': count}
                entry['groups'].append(info)
                if not count:
                    continue
                times = (frame.index - frame.index[0]).total_seconds().to_numpy()
                identifiers = frame['ID'].to_numpy()
                channels = frame['BusChannel'].to_numpy()
                info.update(duration_s=round(float(times[-1]-times[0]), 6),
                            payload_lengths=sorted(int(v) for v in np.unique(frame['DataLength'])),
                            channels=sorted(int(v) for v in np.unique(channels)),
                            distinct_channel_identifiers=len(set(zip(channels.tolist(), identifiers.tolist()))))
                if 'OBD2 (Audi A4)' not in str(path) or kind != 'CAN_DataFrame':
                    continue
                # Keep each channel and ID separate: an ID is not an ECU count.
                info['streams'] = []
                data = np.array([list(payload) for payload in frame['DataBytes']], dtype=np.uint8)
                for channel, identifier in sorted(set(zip(channels.tolist(), identifiers.tolist()))):
                    mask = (channels == channel) & (identifiers == identifier)
                    info['streams'].append({'channel': channel, 'identifier': hex(identifier),
                                            'records': int(mask.sum()),
                                            'interval_ms': intervals(times[mask])})
                info['response_pids'] = []
                for pid in sorted(np.unique(data[identifiers == 0x7E8, 2])):
                    mask = (identifiers == 0x7E8) & (data[:, 1] == 0x41) & (data[:, 2] == pid)
                    info['response_pids'].append({'pid': hex(int(pid)), 'records': int(mask.sum()),
                                                  'interval_ms': intervals(times[mask])})
                decoded, errors = 0, Counter()
                if regular is not None:
                    for identifier, payload in zip(identifiers, data):
                        try:
                            regular.decode_message(int(identifier), bytes(payload))
                            decoded += 1
                        except Exception as exc:
                            errors[type(exc).__name__] += 1
                info['regular_dbc_decoded_records'] = decoded
                info['regular_dbc_decode_errors'] = dict(errors)
                with asammdf.MDF(path, process_bus_logging=False) as other_reader:
                    other = other_reader.get('CAN_DataFrame', raw=True)
                    info['independent_reader_record_count_matches'] = len(other.samples) == count
                    info['independent_reader_identifier_counts_match'] = (
                        Counter(other.samples['CAN_DataFrame.ID'].tolist()) == Counter(identifiers.tolist()))
        traces.append(entry)

    capacity = json.loads(args.capacity.read_text(encoding='utf-8'))
    source = json.loads(args.bundle.read_text(encoding='utf-8'))['source_data']
    network_id = 'Fahrwerk_Fahrdynamik_03-IO-bremsregelung-can-fd-S01'
    transmissions = [t for t in capacity['results']['transmissions'] if t['network_id'] == network_id]
    nodes = {n['id']: n['name'] for n in source['engineering_hardware_nodes']}
    ports = [p for p in source['engineering_hardware_interfaces'] if p['network_ref'] == network_id]
    signals = source['engineering_signals']
    rows = []
    for t in sorted(transmissions, key=lambda r: r['message_name']):
        packed = [s for s in signals if s['message_id'] == t['message_id']]
        rows.append({'sender': nodes[t['producer']], 'message': t['message_name'],
                     'period_ms': t['cycle_ms'], 'payload_bytes': t['payload_bytes'],
                     'signals': [{k: s.get(k) for k in ('name', 'start_bit', 'length_bits',
                                 'data_type', 'factor', 'offset_value', 'min_value', 'max_value', 'unit')}
                                 for s in packed],
                     'fits_little_endian_payload': all(s['byte_order'] == 'little_endian' and
                         0 <= s['start_bit'] and s['start_bit'] + s['length_bits'] <= t['payload_bytes'] * 8
                         for s in packed)})
    nominal_ms = (34 + 10 * (2 + 1)) / 19200 * 1000
    report = {
        'reader_versions': {'mdf_iter': importlib.metadata.version('mdf_iter'),
                            'asammdf': asammdf.__version__, 'cantools': cantools.__version__},
        'snapshot': {k: capacity.get(k) for k in ('id', 'created_at', 'is_outdated', 'source_versions')},
        'bus': {'network_id': network_id, 'data_publishers': len({t['producer'] for t in transmissions}),
                'physical_nodes': sorted({nodes[p['hardware_node_id']] for p in ports}), 'messages': rows,
                'stored_result': next(n for n in capacity['results']['networks'] if n['network_id'] == network_id)},
        'independent_calculation': {'two_byte_frame_ms': nominal_ms,
            'old_buggy_frame_ms': 54 / 19200 * 1000,
            'old_checksum_corrected_load_percent': nominal_ms * (4/5 + 1/10 + 3/50) * 100,
            'eight_frames_50ms_load_percent': 8 * nominal_ms / 50 * 100,
            'eight_frames_50ms_slot_percent': 8 * 5 / 50 * 100,
            'eight_byte_frame_ms': 124 / 19200 * 1000},
        'percent_signals_with_enum_domain': [{k: s.get(k) for k in ('id', 'name', 'unit', 'factor', 'data', 'semantic')}
            for s in signals if s.get('unit') == '%' and s.get('data', {}).get('enum_values')],
        'traces': traces, 'databases': databases,
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'report': str(args.output), 'trace_files': len(traces), 'dbc_files': len(databases),
                      'data_publishers': report['bus']['data_publishers'],
                      'physical_nodes': len(report['bus']['physical_nodes']),
                      'all_eight_payloads_fit': all(r['fits_little_endian_payload'] for r in rows),
                      'dbc_errors': [d['file'] for d in databases if 'error' in d]}, ensure_ascii=True))


if __name__ == '__main__':
    main()
