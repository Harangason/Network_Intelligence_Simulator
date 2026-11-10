"""Actual small-model multi-participant counter; no original or simulation acceptance."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('previous_native_counter',
    HERE.parent / 'port-function-context-repair/native_counter.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
from backend.nis.agent.orchestration import local_reasoner as reasoner, project_intake as intake
from backend.nis.engineering.goal_execution.progress import sink
import httpx


def source_request():
    declarations = [f'Steuergerät ID: C{number}' for number in range(1, 5)]
    function = 'C1 verarbeitet die empfangenen Statusmeldungen.'
    requirement = ('Jedes der vier Steuergeräte C1, C2, C3 und C4 sendet und empfängt '
        'Statusmeldungen über genau einen physischen CAN-FD-Anschluss am gemeinsamen Segment S. '
        'Keine weiteren Anschlüsse, Geräte, Sensoren oder Aktoren. '
        'Auch ohne einzeln zugeordnete Funktion sind C2, C3 und C4 aktive Kommunikationsteilnehmer.')
    source = ('Industrie: allgemeine industrielle Statuskommunikation.\n' + '\n'.join(declarations)
        + '\nFunktion: ' + function + '\nREQ-001: ' + requirement
        + '\nTransport: can_fd\nDies ist ein selbst erstellter Gegenbeispielfall ohne Hardwarequalifikation.')
    devices = [{'name': quote, 'role': 'CONTROLLER', 'quantity': 1,
        'source_quote': quote, 'source_context': [], 'minimum': False}
        for index, quote in enumerate(declarations, 1)]
    facts = [{key: value for key, value in row.items() if key != 'minimum'} | {'kind': 'INSTANCE'}
        for row in devices]
    facts += [{'name': function, 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None,
        'source_quote': 'Funktion: ' + function, 'source_context': []},
        {'name': 'REQ-001',
        'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None,
        'source_quote': 'REQ-001: ' + requirement, 'source_context': []}]
    envelope = {'source_text': source, 'source_name': 'authored-four-participants.txt',
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'source_chars': len(source),
        'devices': devices, 'facts': facts, 'questions': [], 'answers': [], 'function_assignments': {},
        'technologies': [{'name': 'can_fd', 'kind': 'TRANSPORT', 'source_quote': 'Transport: can_fd'}]}
    return {'mode': 'EXAMPLE_PROJECT', 'prompt': source + '\n- Dokument-Geräte: '
            + json.dumps(envelope, ensure_ascii=False), 'reference_sources': []}


async def main():
    out = HERE / 'native-counter'
    out.mkdir(exist_ok=False)
    assert os.environ['LOCAL_AI_MODEL'] == os.environ['LOCAL_AI_FAST_MODEL'] == 'qwen3.5:9b'
    admission = json.loads(subprocess.check_output([sys.executable, str(HERE.parent / 'read_provider.py'),
        '--model', 'qwen3.5:9b'], encoding='utf-8'))
    support.save(out / 'admission.json', admission)
    request = source_request()
    support.save(out / 'source-request.json', request)
    prepared = intake.prepare_reference_design(request)
    instance = reasoner.LocalEngineeringReasoner()
    assert instance.model == 'qwen3.5:9b' and instance.context_tokens == 131072
    assert instance.client.timeout.read == 1200
    await instance.client.aclose()
    transport = support.CounterTransport(out)
    instance.client = httpx.AsyncClient(transport=transport, timeout=1200, trust_env=False)
    with (out / 'events.ndjson').open('w', encoding='utf-8') as log:
        def progress(event):
            log.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **event}, ensure_ascii=False) + '\n')
            log.flush()
        token = sink.set(progress)
        try:
            await instance.plan_reference_design(prepared)
            raise AssertionError('Counter must finish before any parameter request.')
        except support.CounterComplete:
            pass
        except BaseException as error:
            support.save(out / 'failure.json', {'type': type(error).__name__, 'error': str(error),
                'at': datetime.now(timezone.utc).isoformat(), 'native_requests': transport.count})
            raise
        finally:
            sink.reset(token)
            await instance.client.aclose()
    candidate = intake.ReferenceDesignProposal.model_validate(transport.candidate).model_dump(mode='json')
    assert len(candidate['devices']) == 4 and all(row['kind'] == 'CONTROLLER' for row in candidate['devices'])
    owners = {row['id'] for row in candidate['devices']}
    assert len(candidate['ports']) == 4 and {row['device_id'] for row in candidate['ports']} == owners
    assert all(row['technology'] == 'can_fd' and row['parameters'] == {} for row in candidate['ports'])
    assert len(candidate['functions']) == 1
    assert len(candidate['functions'][0]['executor_device_ids']) == 1
    result = {'status': 'PASS', 'actual_native_requests': transport.count, 'model': instance.model,
        'participants': 4, 'planned_ports': 4, 'source_sha256': hashlib.sha256(request['prompt'].encode()).hexdigest(),
        'reasoner_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest(),
        'unresolved': candidate['unresolved'], 'original_acceptance': False,
        'simulation_acceptance': False, 'canonical_writes': False}
    support.save(out / 'result.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
