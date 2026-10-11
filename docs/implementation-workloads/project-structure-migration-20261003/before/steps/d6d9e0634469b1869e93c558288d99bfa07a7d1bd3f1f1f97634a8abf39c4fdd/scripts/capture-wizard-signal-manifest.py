"""Normalize a saved canonical baseline; never reads or mutates a live project."""
import argparse
import hashlib
import json
from pathlib import Path


def contract_manifest(canonical):
    hardware = {item['id']: item for item in canonical['hardware-nodes']}
    functions = {item['id']: item for item in canonical['functions']}
    messages = {item['id']: item for item in canonical['messages']}

    def producer_name(reference):
        owner = hardware.get(reference)
        if reference in functions:
            owner = hardware.get(functions[reference].get('hardware_node_id'))
        if owner and owner['device_type'] == 'Gateway':
            return '$gateway'
        return (hardware.get(reference) or functions.get(reference) or {})['name']

    signals = {}
    fields = ('start_bit', 'length_bits', 'data_type', 'factor', 'offset_value',
              'unit', 'min_value', 'max_value', 'byte_order')
    for signal in canonical['signals']:
        message = messages[signal['message_id']]
        producer = producer_name(message['configuration']['communication_contract']['producer_ref'])
        key = ' :: '.join((producer, message['name'], signal['name']))
        if key in signals:
            raise ValueError('Non-unique semantic signal identity: ' + key)
        signals[key] = {**{field: signal.get(field) for field in fields},
                        'enum_values': signal.get('data', {}).get('enum_values'),
                        'semantic_type': signal.get('semantic', {}).get('semantic_type'),
                        'generation_role': signal.get('configuration', {}).get('generation_role')}
    return signals


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('saved_baseline', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    raw = args.saved_baseline.read_bytes()
    canonical = json.loads(raw)
    signals = contract_manifest(canonical)
    manifest = {'source_project': canonical['hardware-nodes'][0]['project_id'],
                'source_sha256': hashlib.sha256(raw).hexdigest(), 'signal_count': len(signals),
                'normalization': 'UUIDs replaced by producer/message/signal names; gateway is a role identity.',
                'signals': signals}
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps({'signals': len(signals), 'output': str(args.output)}))
