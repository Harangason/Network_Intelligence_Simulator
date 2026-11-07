"""Two actual small-model selection reads; no Original or model acceptance."""
import asyncio
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import httpx
from jsonschema import Draft202012Validator

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration.project_intake import document_response_json
from backend.tests.test_reference_inventory_context_capacity import authored_context, read_selection

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--raw-selection-control', action='store_true')
parser.add_argument('--explicit-task', action='store_true')
parser.add_argument('--report-target', action='store_true')
parser.add_argument('--keyed-selection-control', action='store_true')
parser.add_argument('--grouped-selection-control', action='store_true')
parser.add_argument('--plain-context-control', action='store_true')
parser.add_argument('--literal-copy-control', action='store_true')
args = parser.parse_args()
OUT = args.output.resolve()
assert OUT.parent == Path(__file__).resolve().parent
OUT.mkdir(exist_ok=False)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


async def main():
    config = json.loads((ROOT / '.local-implementation-agent.json').read_text(encoding='utf-8'))['local_implementation_agent']
    model = config['preferred_models']['reasoning']
    assert config['enabled_models'] == [model] == ['llama3.1:8b']
    assert config['preferred_models']['fallback'] is None
    admission = json.loads(subprocess.check_output([
        sys.executable, str(OUT.parents[1] / 'read_provider.py')], text=True, encoding='utf-8'))
    save('admission.json', admission)
    current = authored_context(12, 2)
    for index, device in enumerate(current['current_candidate']['devices']):
        device['kind'] = 'SENSOR' if index >= 8 else 'CONTROLLER'
        device['source_fact_ids'] = ['F-selection']
        device['source_member_bindings'] = {'F-selection': 'rear' if index in (10, 11) else 'front'}
    current['existing_inventory_for_this_stage'] = [
        {key: deepcopy(row[key]) for key in ('id', 'name', 'kind')}
        for row in current['current_candidate']['devices']]
    current['inventory_target_for_this_stage'].update(
        fact_id='F-selection', member='rear', names=[], minimum_rows=2, max_rows=2)
    current['instruction'] = (
        'Independent synthetic reading counter, not a hardware proposal. Return selected_device_ids '
        'with exactly those existing SENSOR IDs whose source_member_bindings[F-selection] equals '
        'the current inventory_target.member. Use the latest nis_current_selection, preserve source order. '
        'Do not choose controllers. Old selection and old answer are superseded by the latest update.')
    system = 'Read the complete synthetic context. Return only the required JSON. No model writes or qualification.'
    if args.explicit_task:
        system += ' ' + current['instruction']
    if args.grouped_selection_control:
        system += ' existing_inventory.groups is an ordered list of tables. Apply each table constants to every row and concatenate tables in order.'
    identities = [row['id'] for row in current['current_candidate']['devices']]
    schema = {'type': 'object', 'additionalProperties': False,
              'properties': {'selected_device_ids': {'type': 'array', 'minItems': 2, 'maxItems': 2,
                  'items': {'type': 'string', 'enum': identities}}}, 'required': ['selected_device_ids']}
    if args.report_target:
        system += ' First report target_member from the latest selection, then select matching SENSOR IDs.'
        schema['properties'] = {'target_member': {'type': 'string', 'enum': ['front', 'rear']}, **schema['properties']}
        schema['required'] = ['target_member', *schema['required']]
    history, previous, anchor = [], None, None
    observations = []
    async with httpx.AsyncClient(timeout=1200, trust_env=False) as client:
        for index, expected in enumerate((identities[10:12], identities[8:10]), 1):
            if index == 2:
                current = deepcopy(current)
                current['inventory_target_for_this_stage']['member'] = 'front'
            messages, _, rebased = r._reference_context_messages(
                [] if args.plain_context_control or args.literal_copy_control else history,
                None if args.plain_context_control or args.literal_copy_control else previous,
                current, system, 131072,
                anchor=None if args.plain_context_control or args.literal_copy_control else anchor)
            selection = json.loads(messages[-1]['content'])['nis_current_selection']
            assert isinstance(selection['existing_inventory'], dict)
            assert len(read_selection(selection)) == 12
            assert current['existing_inventory_for_this_stage'] == [
                {key: row[key] for key in ('id', 'name', 'kind')}
                for row in current['current_candidate']['devices']]
            assert [row['id'] for row in read_selection(selection)
                    if row['kind'] == 'SENSOR' and row['source_member_bindings']['F-selection']
                    == selection['inventory_target']['member']] == expected
            if args.raw_selection_control:
                wire = json.loads(messages[-1]['content'])
                wire['nis_current_selection']['existing_inventory'] = read_selection(selection)
                messages[-1]['content'] = json.dumps(wire, ensure_ascii=False, separators=(',', ':'))
            if args.keyed_selection_control:
                wire = json.loads(messages[-1]['content'])
                rows = read_selection(selection)
                wire['nis_current_selection']['existing_inventory'] = {
                    'columns': ['name', 'kind', 'source_fact_ids', 'source_member_bindings'],
                    'constants': {}, 'keys': [row['id'] for row in rows],
                    'rows': [[row[key] for key in ('name', 'kind', 'source_fact_ids', 'source_member_bindings')]
                             for row in rows]}
                messages[-1]['content'] = json.dumps(wire, ensure_ascii=False, separators=(',', ':'))
            if args.grouped_selection_control:
                wire = json.loads(messages[-1]['content'])
                groups = []
                for row in read_selection(selection):
                    constants = {key: row[key] for key in ('kind', 'source_fact_ids', 'source_member_bindings')}
                    if not groups or groups[-1]['constants'] != constants:
                        groups.append({'columns': ['id', 'name'], 'constants': constants, 'rows': []})
                    groups[-1]['rows'].append([row['id'], row['name']])
                wire['nis_current_selection']['existing_inventory'] = {'groups': groups}
                messages[-1]['content'] = json.dumps(wire, ensure_ascii=False, separators=(',', ':'))
            if args.plain_context_control:
                messages = [{'role': 'system', 'content': system},
                            {'role': 'user', 'content': json.dumps({'nis_current_selection': {
                                **selection, 'existing_inventory': read_selection(selection)}}, ensure_ascii=False)}]
            if args.literal_copy_control:
                messages = [{'role': 'system', 'content': 'Copy the supplied literal object exactly. No selection or reasoning.'},
                            {'role': 'user', 'content': json.dumps({'target_member': current['inventory_target_for_this_stage']['member'],
                                                                  'selected_device_ids': expected})}]
            payload = {'model': model, 'messages': messages, 'format': schema, 'think': False,
                       'stream': True, 'keep_alive': '10m', 'options': {
                           'temperature': 0, 'num_predict': 8192,
                           'num_ctx': r._reference_context_window(messages, 131072)}}
            save(f'request-{index}.json', payload)
            save(f'context-{index}.json', current)
            with (OUT / f'events-{index}.ndjson').open('w', encoding='utf-8') as log:
                def report(value):
                    log.write(json.dumps({'at_utc': datetime.now(timezone.utc).isoformat(), **value}) + '\n')
                    log.flush()
                body = await r._reference_stream_response(client, 'http://127.0.0.1:11434/api/chat', payload, report)
            save(f'response-{index}.json', body)
            assert body['done'] is True and body.get('done_reason') != 'length' and body['model'] == model
            answer = document_response_json(body['message']['content'])
            Draft202012Validator(schema).validate(answer)
            if args.report_target:
                assert answer['target_member'] == current['inventory_target_for_this_stage']['member'], answer
            observations.append({'round': index, 'expected': expected, 'actual': answer,
                'matched': answer['selected_device_ids'] == expected,
                'context_rebased': rebased, 'eval_count': body.get('eval_count'),
                'prompt_eval_count': body.get('prompt_eval_count'), 'total_duration': body.get('total_duration')})
            history = [*deepcopy(messages), {'role': 'assistant', 'content': body['message']['content']}]
            previous = deepcopy(current)
            if anchor is None:
                anchor = (deepcopy(history), deepcopy(current))
    result = {'status': 'PASS' if all(row['matched'] for row in observations) else 'FAIL',
              'raw_selection_control': args.raw_selection_control,
              'explicit_task': args.explicit_task,
              'report_target': args.report_target,
              'keyed_selection_control': args.keyed_selection_control,
              'grouped_selection_control': args.grouped_selection_control,
              'plain_context_control': args.plain_context_control,
              'literal_copy_control': args.literal_copy_control,
              'actual_inference_requests': 2, 'model': model,
              'scope': __doc__, 'observations': observations,
              'source_code_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
              'original_acceptance': False, 'simulation_pass': False}
    save('result.json', result)
    print(json.dumps(result), flush=True)
    assert result['status'] == 'PASS', observations


asyncio.run(main())
