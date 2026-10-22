"""Capture actual local Qwen interpretation of complete, diverse source files.

This verification script never opens a database or writes canonical model data.
Semantic review is recorded separately, rather than inferred from schema success.
"""
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.nis.engineering.goal_execution.progress import sink

OUT = Path(__file__).parent
BENCH = Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle')
CASES = [
    ('building', 'Intelligentes HLK-Regelsystem.txt'),
    ('chemical', 'Chemieanlagen-Modul.txt'),
    ('cobot', 'Kollaborativer Roboterarm.txt'),
    ('medical', 'Infusionspumpe.txt'),
    ('telecom', '5G-RAN-Komponente.txt'),
    ('space', 'Satelliten-Avionik.txt'),
    ('mobile_robot', 'Mobiler Service‑Roboter mit Greifarm und 360°‑Sensorik.txt'),
]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


async def main():
    reasoner = LocalEngineeringReasoner()
    manifest = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Native inference on other original project files; semantic review separate',
        'database_access': False,
        'model': reasoner.model,
        'endpoint': str(reasoner.client.base_url),
        'application_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                               for p in ('backend/nis/agent/orchestration/local_reasoner.py',
                                         'backend/nis/agent/orchestration/project_intake.py')},
        'cases': [],
    }
    tags = await reasoner.client.get(reasoner.chat_url.removesuffix('/chat') + '/tags')
    tags.raise_for_status()
    installed = next(m for m in tags.json()['models'] if m['name'] == reasoner.model)
    assert installed['details']['family'].startswith('qwen')
    manifest['installed_model'] = installed
    save(OUT / 'manifest.json', manifest)
    current = {}

    async def capture(response):
        if response.request.url.path != '/api/chat':
            return
        await response.aread()
        current['calls'].append({'request': json.loads(response.request.content),
                                 'http_status': response.status_code,
                                 'response': response.json()})
        save(OUT / f"{current['id']}-wire.json", current['calls'])
        actual = response.json()
        print(json.dumps({'case': current['id'], 'event': 'MODEL_RESPONSE',
                          'call': len(current['calls']), 'model': actual.get('model'),
                          'tokens': actual.get('eval_count'),
                          'seconds': round(actual.get('total_duration', 0) / 1e9, 2)}), flush=True)

    reasoner.client.event_hooks['response'] = [capture]
    token = sink.set(lambda event: print(json.dumps({'case': current.get('id'), **event}, ensure_ascii=True), flush=True))
    try:
        selected = set(sys.argv[1:])
        for case_id, filename in CASES:
            if selected and case_id not in selected:
                continue
            current = {'id': case_id, 'calls': []}
            raw = (BENCH / filename).read_bytes()
            source = raw.decode('utf-8')
            (OUT / f'{case_id}-source.txt').write_bytes(raw)
            item = {'id': case_id, 'file': filename, 'original_path': str(BENCH / filename),
                    'source_sha256': hashlib.sha256(raw).hexdigest(), 'source_chars': len(source),
                    'source_bytes': len(raw), 'status': 'RUNNING'}
            manifest['cases'].append(item)
            save(OUT / 'manifest.json', manifest)
            print(json.dumps({'case': case_id, 'event': 'START', 'file': filename,
                              'chars': len(source)}, ensure_ascii=True), flush=True)
            started = time.monotonic()
            try:
                result = await reasoner.interpret_document(source, filename)
                save(OUT / f'{case_id}-proposal.json', result)
                assert result['source_complete'] is True
                assert result['canonical_writes'] is False and result['approval_required'] is True
                assert result['model'] == reasoner.model and result['provider'] == 'local_ollama'
                assert result['source_sha256'] == item['source_sha256']
                transmitted = []
                for call in current['calls']:
                    payload = json.loads(call['request']['messages'][1]['content'])
                    text = ''.join(payload['source_lines'].values())
                    if not payload.get('validation_feedback'):
                        transmitted.append(text)
                    assert call['response']['model'] == reasoner.model
                    assert call['response'].get('eval_count', 0) > 0
                assert ''.join(transmitted) == source, 'Wire input must preserve the complete original source'
                item.update(status='NATIVE_RETURNED', segments=len(result['segments']),
                            components=len(result['interpretation']['components']),
                            technologies=len(result['interpretation']['technologies']))
            except Exception as error:
                item.update(status='NATIVE_FAILED', error=str(error), error_type=type(error).__name__)
            item.update(seconds=round(time.monotonic() - started, 2), calls=len(current['calls']))
            save(OUT / 'manifest.json', manifest)
            print(json.dumps(item, ensure_ascii=True), flush=True)
    finally:
        sink.reset(token)
        await reasoner.client.aclose()
    manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
    save(OUT / 'manifest.json', manifest)


if __name__ == '__main__':
    asyncio.run(main())
