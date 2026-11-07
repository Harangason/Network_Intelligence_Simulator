"""One real configured-model grammar probe, no original/model/simulation acceptance."""
import asyncio
import argparse
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
from backend.tests.test_reference_inventory_batch import batch_case
from backend.nis.agent.orchestration import local_reasoner as r
from backend.nis.agent.orchestration.project_intake import ReferenceDesignProposal, document_response_json

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path)
parser.add_argument('--packed-context', action='store_true')
parser.add_argument('--cohort-context', action='store_true')
parser.add_argument('--many-cohort-context', action='store_true')
parser.add_argument('--column-dictionaries', action='store_true')
parser.add_argument('--shared-owner-clarification', action='store_true')
parser.add_argument('--model', choices=['llama3.1:8b', 'qwen3.5:9b'])
args = parser.parse_args()
args.many_cohort_context = args.many_cohort_context or args.column_dictionaries
args.cohort_context = args.cohort_context or args.many_cohort_context
args.packed_context = args.packed_context or args.cohort_context
OUT = (args.output or Path(__file__).resolve().parent / 'native-grammar').resolve()
GOAL = Path(__file__).resolve().parents[1]
assert OUT.is_relative_to(GOAL)
OUT.mkdir(exist_ok=False)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


async def main():
    settings = json.loads((ROOT / '.local-implementation-agent.json').read_text(encoding='utf8'))['local_implementation_agent']
    model = args.model or settings['preferred_models']['reasoning']
    if model == 'qwen3.5:9b':
        authorization = GOAL / 'human-small-model-decision-20261107.json'
        decision = json.loads(authorization.read_text(encoding='utf8'))
        assert decision['verified_directly'] is True and model in decision['human_message']
        save('model-authorization.json', {'path': str(authorization), 'sha256': hashlib.sha256(authorization.read_bytes()).hexdigest()})
    else:
        assert model == 'llama3.1:8b' and settings['enabled_models'] == [model]
    assert settings['preferred_models']['fallback'] is None
    # Reuse the established dynamic main-worker-only admission reader. It asserts idle.
    admission = json.loads(subprocess.check_output([sys.executable, str(GOAL / 'read_provider.py'), '--model', model], text=True))
    assert admission['busy_slots'] == 0 and admission['loaded_models'] in ([], [model])
    save('admission.json', admission)
    prepared, target, full_schema, _ = batch_case(8)
    schema, codec = r._reference_compact_inventory_schema(full_schema)
    save("request-local-codec.json", codec)
    messages = [{'role': 'system', 'content': 'This is a synthetic grammar counterprobe, never a real hardware design. Return only JSON matching the supplied schema.'},
                {'role': 'user', 'content': json.dumps({'instruction':
                    'Produce each of these eight independent synthetic sensor decisions in inventory_choices under its exact name. '
                    'The schema omits fixed identity, quantity and source fields; NIS restores those exact offered constants. Use empty field_references. '
                    + ('Use the owner specified below and null purpose. ' if args.cohort_context else 'Use null owner and purpose. ')
                    + 'Short rationale. All eight slots required. '
                    'devices=[], unresolved=[], inventory_complete=true. No physical or safety qualification is claimed.',
                    'target': target, 'synthetic_source_fact': prepared['facts'][target['fact_id']]}, ensure_ascii=False)}]
    existing = []
    expected_owner = None
    segment_tables = 0
    if args.packed_context:
        from backend.tests.test_reference_inventory_context_capacity import authored_context, read_selection
        current = authored_context(12, 2)
        if args.many_cohort_context:
            from backend.tests.test_reference_inventory_context_capacity import authored_many_cohort_context
            current = authored_many_cohort_context(251)
        existing = current['current_candidate']['devices']
        if args.cohort_context:
            for index, row in enumerate(existing):
                if args.many_cohort_context:
                    row.update(kind='CONTROLLER', source_fact_ids=['Authored-CONTROLLER'])
                    continue
                kind = ['CONTROLLER', 'SENSOR', 'ACTUATOR'][index // 4]
                row.update(kind=kind, source_fact_ids=['Authored-' + kind], source_member_bindings={},
                           purpose=('Existing independently authored ' + kind + ' cohort; no real hardware qualification. ') * 4,
                           rationale=('Preserve every existing ' + kind + ' identity and source binding in this synthetic counter. ') * 4)
            selected = existing[248 if args.many_cohort_context else 1]
            selected['purpose'] = 'Responsible for the authored temperature measurement chain.'
            expected_owner = selected['id']
            current['existing_inventory_for_this_stage'] = '/current_candidate/devices'
        current['inventory_target_for_this_stage'] = target
        current.update(json.loads(messages[-1]['content']))
        current['instruction'] += (f' All {len(existing)} authored existing devices remain present and unchanged. '
            'They belong to other source groups, not the eight requested new sensors. '
            'For each new sensor use as owner the existing CONTROLLER whose purpose is '
            'Responsible for the authored temperature measurement chain. '
            'Read its exact ID and purpose from the complete context; names alone do not identify it. '
            'Do not select another controller, sensor or actuator.' if args.cohort_context else
            ' The twelve authored existing controllers remain present and unchanged. They are not the eight requested new sensors.')
        if args.shared_owner_clarification:
            assert args.cohort_context
            current['instruction'] += (' All eight new sensors share the SAME matching existing owner. '
                'Repeat that exact owner ID in all eight owner_device_id fields. IDs are opaque identities; '
                'never increment, cycle or distribute them. The expected ID is determined only by the '
                'existing controller purpose, not by the sensor index.')
        messages, _, _ = r._reference_context_messages([], None, current, messages[0]['content'], 131072)
        if args.cohort_context:
            def count_segments(value):
                if isinstance(value, dict):
                    return int('segments' in value) + sum(count_segments(item) for item in value.values())
                return sum(count_segments(item) for item in value) if isinstance(value, list) else 0
            segment_tables = count_segments(json.loads(messages[-1]['content']))
            if args.column_dictionaries:
                packed = json.loads(messages[-1]['content'])
                def purpose_dictionary(value):
                    if isinstance(value, dict):
                        return ('Responsible for the authored temperature measurement chain.'
                                in value.get('dictionaries', {}).get('purpose', [])
                                or any(purpose_dictionary(item) for item in value.values()))
                    return any(purpose_dictionary(item) for item in value) if isinstance(value, list) else False
                assert purpose_dictionary(packed), 'The selected purpose must actually be dictionary encoded.'
            else:
                assert segment_tables > 0, 'The native probe must actually exercise segmented tables.'
            if args.many_cohort_context and not args.column_dictionaries:
                def largest_segment_count(value):
                    if isinstance(value, dict):
                        return max([len(value.get('segments', [])), *(largest_segment_count(v) for v in value.values())])
                    return max([0, *(largest_segment_count(v) for v in value)]) if isinstance(value, list) else 0
                assert largest_segment_count(json.loads(messages[-1]['content'])) > 16
        selection = json.loads(messages[-1]['content'])['nis_current_selection']
        from backend.tests.test_reference_reasoner import effective_reference_context
        assert selection['existing_inventory'] == '/current_candidate/devices'
        assert len(read_selection(selection, effective_reference_context(messages))) == len(existing)
        full_schema = r._reference_schema_for_stage(prepared, {'devices'}, inventory_target=target, existing_devices=existing)
        schema, codec = r._reference_compact_inventory_schema(full_schema)
        save('request-local-codec.json', codec)
    payload = {'model': model, 'messages': messages, 'format': schema, 'think': False,
               'stream': True, 'keep_alive': '10m', 'options': {'temperature': 0, 'num_predict': 8192,
                   'num_ctx': r._reference_context_window(messages, 131072)}}
    save('request.json', payload)
    with (OUT / 'events.ndjson').open('w', encoding='utf8') as log:
        def report(value):
            log.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **value}) + '\n'); log.flush()
        async with httpx.AsyncClient(timeout=1200, trust_env=False) as client:
            body = await r._reference_stream_response(client, 'http://127.0.0.1:11434/api/chat', payload, report)
    save('response.json', body)
    assert body['done'] is True and body.get('done_reason') != 'length' and body['model'] == model
    value = document_response_json(body['message']['content'])
    Draft202012Validator(schema).validate(value)
    rows = r._reference_expand_inventory_choices(existing, value['inventory_choices'], inventory_target=target, inventory_codec=codec)
    rows = ReferenceDesignProposal.model_validate({'devices': rows}).model_dump(mode='json')['devices']
    rows = r._reference_scoped_inventory_delta(existing, rows, inventory_target=target)
    merged = r._reference_merge_inventory_devices(existing, rows, target, prepared['facts'])
    assert len(merged) == len({row['id'] for row in merged}) == len(existing) + 8
    assert merged[:len(existing)] == existing
    assert [row['name'] for row in merged[len(existing):]] == target['names']
    if args.cohort_context:
        assert all(row['owner_device_id'] == expected_owner for row in merged[len(existing):])
    assert value['inventory_complete'] is True and r._reference_inventory_progress(existing, merged)
    result = {'status': 'PASS', 'model': model, 'actual_inference_requests': 1, 'native_devices': len(merged) - len(existing),
              'preserved_existing_devices': len(existing), 'packed_context': args.packed_context,
              'segmented_tables': segment_tables, 'native_owner_selection': args.cohort_context,
              'native_owner_selection_basis': 'purpose_only_in_complete_context' if args.cohort_context else None,
              'many_cohort_context': args.many_cohort_context, 'expected_owner': expected_owner,
              'shared_owner_clarification': args.shared_owner_clarification,
              'column_dictionaries': args.column_dictionaries,
              'schema_and_public_validation_and_scoped_merge': True,
              'source_code_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
              'original_acceptance': False, 'simulation_acceptance': False,
              'metrics': {key: body.get(key) for key in ('prompt_eval_count', 'eval_count', 'prompt_eval_duration', 'eval_duration', 'total_duration')}}
    save('result.json', result)
    print(json.dumps(result), flush=True)


asyncio.run(main())
