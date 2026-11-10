"""Real small-model planner through port closure on authored sources, not neu9 acceptance."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import httpx

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration import local_reasoner as r, project_intake as intake
from backend.nis.engineering.goal_execution.progress import sink
from backend.tests.test_reference_reasoner import effective_reference_context

OUT = Path(__file__).resolve().parent / 'native-counter'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def authored_request(technologies):
    device = 'Gateway G'
    function = 'G verbindet ' + ', '.join(technologies) + '; jede Technologie besitzt genau ein separates physisches Segment.'
    source = ('Industrie: allgemeine industrielle Protokollkopplung.\nGenau ein Gateway G.\n'
              'Funktion: ' + function + '\n'
              'Jedes genannte Segment ist am Gateway physisch angeschlossen. Keine weiteren Teilnehmer, '
              'keine Sensoren oder Aktoren, keine parallelen Anschlüsse pro Segment. '
              'Dies ist ein selbst erstelltes Planungsbeispiel ohne Hardwarequalifikation.\n'
              + '\n'.join('Transport: ' + technology for technology in technologies))
    facts = [
        {'name': device, 'kind': 'INSTANCE', 'role': 'GATEWAY', 'quantity': 1,
         'source_quote': 'Genau ein Gateway G.', 'source_context': []},
        {'name': function, 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None,
         'source_quote': 'Funktion: ' + function, 'source_context': []}]
    envelope = {'source_text': source, 'source_name': 'authored-port-counter.txt',
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'source_chars': len(source),
        'devices': [{'name': device, 'role': 'GATEWAY', 'quantity': 1,
                     'source_quote': 'Genau ein Gateway G.', 'source_context': [], 'minimum': False}],
        'questions': [], 'facts': facts, 'technologies': [
            {'name': technology, 'kind': 'TRANSPORT', 'source_quote': 'Transport: ' + technology}
            for technology in technologies], 'answers': [], 'function_assignments': {}}
    return {'mode': 'EXAMPLE_PROJECT', 'prompt': source + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False),
            'reference_sources': []}


class CounterComplete(BaseException):
    pass


class RecordingStream(httpx.AsyncByteStream):
    def __init__(self, original, path):
        self.original, self.path = original, path

    async def __aiter__(self):
        with self.path.open('wb') as log:
            async for chunk in self.original:
                log.write(chunk)
                log.flush()
                yield chunk

    async def aclose(self):
        await self.original.aclose()


class CounterTransport(httpx.AsyncBaseTransport):
    def __init__(self, directory):
        self.inner = httpx.AsyncHTTPTransport()
        self.directory, self.count, self.candidate = directory, 0, None

    async def handle_async_request(self, request):
        if request.url.path == '/api/chat':
            payload = json.loads(request.content)
            context = effective_reference_context(payload['messages'])
            if context['port_ids_for_this_stage']:
                # All prior native responses have ended and the actual planner
                # has validated/expanded its port group. No parameter request is sent.
                self.candidate = context['current_candidate']
                save(self.directory / 'validated-port-candidate.json', self.candidate)
                raise CounterComplete()
            self.count += 1
            save(self.directory / f'request-{self.count}.json', payload)
            response = await self.inner.handle_async_request(request)
            response.stream = RecordingStream(response.stream, self.directory / f'response-{self.count}.ndjson')
            return response
        return await self.inner.handle_async_request(request)

    async def aclose(self):
        await self.inner.aclose()


async def main():
    OUT.mkdir(exist_ok=False)
    assert os.environ['LOCAL_AI_MODEL'] == 'qwen3.5:9b'
    async with httpx.AsyncClient(timeout=1200, trust_env=False) as client:
        ps = (await client.get('http://127.0.0.1:11434/api/ps')).json()
        save(OUT / 'before-loaded-models.json', ps)
        if not ps.get('models'):
            # Explicitly authorized model, empty preload only; no competing model
            # is unloaded and every actual request is admitted again below.
            response = await client.post('http://127.0.0.1:11434/api/generate', json={
                'model': 'qwen3.5:9b', 'stream': False, 'keep_alive': '10m',
                'options': {'num_ctx': 131072, 'num_predict': 0}})
            response.raise_for_status()
            save(OUT / 'empty-load.json', response.json())
    results = []
    for name, technologies in [('mixed-bus', ('lin', 'can_fd', 'ethernet')),
                                ('industrial', ('i2c', 'modbus_rtu'))]:
        case = OUT / name
        case.mkdir()
        admission = json.loads(subprocess.check_output([
            sys.executable, str(OUT.parent.parent / 'read_provider.py'), '--model', 'qwen3.5:9b'], encoding='utf-8'))
        save(case / 'admission.json', admission)
        request = authored_request(technologies)
        save(case / 'source-request.json', request)
        prepared = intake.prepare_reference_design(request)
        instance = r.LocalEngineeringReasoner()
        assert instance.context_tokens == 131072 and instance.client.timeout.read == 1200
        await instance.client.aclose()
        transport = CounterTransport(case)
        instance.client = httpx.AsyncClient(transport=transport, timeout=1200, trust_env=False)
        with (case / 'events.ndjson').open('w', encoding='utf-8') as log:
            def progress(event):
                log.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), **event}, ensure_ascii=False) + '\n')
                log.flush()
            token = sink.set(progress)
            try:
                await instance.plan_reference_design(prepared)
                raise AssertionError('Counter must stop before any parameter request.')
            except CounterComplete:
                pass
            finally:
                sink.reset(token)
                await instance.client.aclose()
        candidate = intake.ReferenceDesignProposal.model_validate(transport.candidate).model_dump(mode='json')
        assert len(candidate['devices']) == 1 and candidate['devices'][0]['kind'] == 'GATEWAY'
        owner = candidate['devices'][0]['id']
        assert len(candidate['functions']) == 1 and candidate['functions'][0]['executor_device_ids'] == [owner]
        assert len(candidate['ports']) == len(technologies)
        assert {row['technology'] for row in candidate['ports']} == set(technologies)
        assert all(row['device_id'] == owner and row['parameters'] == {} for row in candidate['ports'])
        assert len({row['id'] for row in candidate['ports']}) == len(technologies)
        item = {'name': name, 'status': 'PASS', 'actual_native_requests': transport.count,
                'planned_ports': len(candidate['ports']), 'technologies': list(technologies),
                'unresolved': candidate['unresolved'], 'original_acceptance': False, 'canonical_writes': False}
        save(case / 'result.json', item)
        results.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    save(OUT / 'result.json', {'status': 'PASS', 'cases': results, 'model': 'qwen3.5:9b',
         'original_acceptance': False, 'simulation_acceptance': False,
         'reasoner_sha256': hashlib.sha256((ROOT / 'backend/nis/agent/orchestration/local_reasoner.py').read_bytes()).hexdigest()})


if __name__ == '__main__':
    asyncio.run(main())
