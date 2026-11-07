"""Post-delivery component check inside the exact running image; no project writes."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.nis.agent.context.agent_context import AgentContext
from backend.nis.agent.tools.function_blocks import QwenBlockGenerator
from backend.nis.infrastructure.local_model_identity import local_model_author
from backend.nis.simulation.signals.core.function_block import EcuRuntime, validate_function_spec, verify_function_cases


report = {'scope': 'Actual deployed-image component check, no project tools, canonical model writes or full Original acceptance.',
          'checks': [], 'started_at_epoch': time.time()}
build = json.loads(Path('/app/backend/nis/app/build-info.json').read_bytes())
assert build['source_sha256'] == os.environ['NIS_PROBE_EXPECTED_SOURCE']
assert os.environ['LOCAL_AI_MODEL'] == os.environ['LOCAL_AI_FAST_MODEL'] == 'llama3.1:8b'
report['build'] = build
report['model'] = os.environ['LOCAL_AI_MODEL']
assert local_model_author('local-completion:4b', {'details': {'family': 'gemma', 'format': 'gguf'},
    'model_info': {'general.parameter_count': 4_000_000_000}, 'capabilities': ['completion']}) == 'LOCAL_LLM'
report['checks'].append('generic_identity_pure_no_inference')


async def document_check():
    reasoner = LocalEngineeringReasoner()
    try:
        source = 'Sensor: Temperatursensor'
        result = await reasoner.interpret_document(source, 'deployed-model-independence-check.txt')
        print(json.dumps({'stage': 'document_response', 'result': result}, ensure_ascii=False), file=sys.stderr, flush=True)
        assert result['model'] == report['model'] and result['source_complete'] is True
        assert result['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()
        assert result['status'] == 'REVIEW_REQUIRED' and result['canonical_writes'] is False
        component, = result['interpretation']['components']
        assert (component['name'], component['role'], component['quantity']) == ('Temperatursensor', 'SENSOR', None)
        report['document'] = result
        report['checks'].append('real_llama_source_bound_document')
        decision = await reasoner.next([{'role': 'user', 'content':
            'Prüfe den aktuellen Projektstand. Rufe dafür zuerst ausschließlich inspect_project ohne Argumente auf. Behaupte noch keinen Befund.'}],
            AgentContext(active_project_id='deployed-model-independent-readonly'), [{'name': 'inspect_project',
                'description': 'Read the actual current project without writes. Call this before reporting project findings.',
                'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}])
        print(json.dumps({'stage': 'native_tool_decision', 'result': decision}, ensure_ascii=False), file=sys.stderr, flush=True)
        assert len(decision['calls']) == 1 and decision['calls'][0]['name'] == 'inspect_project'
        assert decision['calls'][0]['arguments'] == {}
        report['native_tool_decision'] = decision
        report['checks'].append('real_llama_native_tool_decision_no_tool_executed')
    finally:
        await reasoner.close()


asyncio.run(document_check())
bindings = {'temperature': {'signal_id': 'isolated-check-temperature', 'type': 'number', 'unit': 'degC',
    'max_age_ms': 25., 'on_stale': 'fallback', 'fallback': 20.}}
parameters = {'threshold': 20.}
definition = QwenBlockGenerator().generate(
    'Stateless temperature threshold: return Boolean true exactly when inputs temperature in degC is '
    'strictly greater than parameters threshold in degC. Equality or below is false. Read the parameter, '
    'never hardcode it. No state or other parameters.',
    {'purpose': 'Bounded deployed component verification, no hardware qualification'}, bindings, parameters)
print(json.dumps({'stage': 'generated_function_response', 'definition': definition}, ensure_ascii=False), file=sys.stderr, flush=True)
definition['verification_cases'] = [{'source': 'Independent explicit threshold boundary requirements',
    'steps': [{'inputs': {'temperature': value}, 'dt_s': .1, 'expected': expected}
              for value, expected in [(19., False), (20., False), (21., True), (-40., False), (100., True)]]}]
definition['verification'] = verify_function_cases(definition, parameters, bindings)
spec = {'function_block': definition, 'block_parameters': parameters, 'transport_inputs': bindings,
        'on_invalid': 'hold_output', 'invalid_output': False}
validate_function_spec(spec)
runtime = EcuRuntime()
values = [runtime.evaluate('isolated-check-ecu', 'isolated-check-command', spec, {'temperature': value},
                         index * .1, True)[0] for index, value in enumerate([19., 20., 21.])]
assert values == [False, False, True]
report['definition'] = definition
report['actual_values'] = values
report['checks'].append('real_llama_code_independent_cases_and_bounded_runtime')
report['status'] = 'PASSED'
report['seconds'] = round(time.time() - report['started_at_epoch'], 3)
print(json.dumps(report, ensure_ascii=False))
