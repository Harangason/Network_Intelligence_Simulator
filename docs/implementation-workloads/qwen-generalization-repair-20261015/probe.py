"""Capture actual local Qwen interpretation of complete, diverse source files.

This verification script never opens a database or writes canonical model data.
Semantic review is recorded separately, rather than inferred from schema success.
"""
import asyncio
import os
import hashlib
import json
import runpy
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.nis.engineering.goal_execution.progress import sink

OUT = Path(os.environ.get('NIS_NATIVE_EVIDENCE_DIR', str(Path(__file__).parent)))
OUT.mkdir(parents=True, exist_ok=True)
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


def semantic_oracle(case_id, result):
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    data = result['interpretation']; facts = data['components']; tech = data['technologies']
    failures = []
    def has(fragment, kind, role):
        if not any(fragment.casefold() in c['source_quote'].casefold() and c['kind'] == kind and c['role'] == role for c in facts):
            failures.append(f'Missing correct fact: {fragment} / {kind} / {role}')
    expectations = {
        'building': [('Raumcontroller','CATEGORY','CONTROLLER'),('Sensorik','CATEGORY','SENSOR'),('Aktoren','CATEGORY','ACTUATOR'),('Sollwertführung','FUNCTION','OTHER')],
        'chemical': [('Prozesssensorik','CATEGORY','SENSOR'),('Aktoren','CATEGORY','ACTUATOR'),('SPS/DCS','CATEGORY','CONTROLLER'),('Rezepturablauf','FUNCTION','OTHER')],
        'cobot': [('Gelenkaktuatoren','CATEGORY','ACTUATOR'),('Kraft-/Momentensensorik','CATEGORY','SENSOR'),('Sicherheitssteuerung','CATEGORY','CONTROLLER'),('Bahnplanung','FUNCTION','OTHER')],
        'medical': [('Pumpenmechanik','CATEGORY','ACTUATOR'),('Sensorik für Fluss/Luft','CATEGORY','SENSOR'),('Embedded Controller','CATEGORY','CONTROLLER'),('Förderprofilsteuerung','FUNCTION','OTHER')],
        'telecom': [('Funkmodul','CATEGORY','OTHER'),('Baseband-Processing','FUNCTION','OTHER'),('Scheduling','FUNCTION','OTHER')],
        'space': [('On-Board-Computer','CATEGORY','CONTROLLER'),('Sternsensor','CATEGORY','SENSOR'),('Reaktionsräder','CATEGORY','ACTUATOR'),('Mode Management','FUNCTION','OTHER')],
        'mobile_robot': [('Raspberry Pi 5 (Hauptrechner)','INSTANCE','CONTROLLER'),('Mikrocontroller (STM32, Arduino, ESP32)','CATEGORY','CONTROLLER'),('Motorcontroller (z.','CATEGORY','CONTROLLER'),('Ultraschallsensoren (8','CATEGORY','SENSOR'),('Navigation','FUNCTION','OTHER'),('Manipulation','FUNCTION','OTHER'),('Autonomie','FUNCTION','OTHER'),('Teleoperation','FUNCTION','OTHER')],
    }
    for expected in expectations[case_id]: has(*expected)
    instances = [f for f in facts if f['kind'] == 'INSTANCE']
    if case_id != 'mobile_robot' and instances: failures.append('Unquantified overview must not assert installed instances')
    if case_id == 'mobile_robot':
        for label in ('Servomotoren', 'Greifer mit Kraftsensor', 'Einzelradantrieb'):
            has(label, 'CATEGORY', 'ACTUATOR')
        unresolved = {t['name'] for t in tech if t['kind'] == 'UNRESOLVED'}
        if not {'Bluetooth', 'CSI', 'Serial'} <= unresolved:
            failures.append('Unspecified Bluetooth/CSI/Serial families must remain unresolved')
        if any(c['source_quote'].startswith('/') or 'GPS-Modul' in c['source_quote'] or 'TC-SEN-002' in c['source_quote'] for c in facts):
            failures.append('Software paths, future extensions or test examples became installed scope')
        if len(instances) != 1 or instances[0]['quantity'] != 1 or 'Raspberry Pi 5' not in instances[0]['name']:
            failures.append('Only the explicitly designated main computer may be a concrete instance')
        ids = {DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(t['name']) for t in tech if t['kind'] == 'TRANSPORT'}
        if not {'can','i2c','uart','wifi','gpio','pwm','ros2'} <= ids: failures.append('Missing separately grounded robot transports')
        if any(t['kind']=='UNRESOLVED' and t['name'] in {'I²C','WLAN'} for t in tech): failures.append('Canonical aliases unresolved')
    if case_id == 'space':
        if any(t['kind']=='TRANSPORT' and DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(t['name'])=='uart' for t in tech): failures.append('UART-like is not confirmed UART')
        if not any(t['kind']=='UNRESOLVED' and 'uart' in t['name'].casefold() for t in tech): failures.append('Qualified UART mention must remain visibly unresolved')
    if case_id in {'building','chemical','cobot','medical'} and any(t['kind']=='TRANSPORT' for t in tech): failures.append('Invented transport in unspecified overview')
    if any(c['quantity'] is not None for c in facts if c['kind'] != 'INSTANCE'): failures.append('Invented category quantity')
    if not instances and 'bereits benannten Instanzen' in ' '.join(data['open_questions']): failures.append('Questions imply nonexistent named instances')
    if not data['open_questions']: failures.append('Missing questions for open hardware and connection scope')
    if not any(c['kind']=='FUNCTION' for c in facts): failures.append('Functions lost')
    if not any(c['kind']=='REQUIREMENT' for c in facts): failures.append('Requirements lost')
    original = (BENCH / dict(CASES)[case_id]).read_bytes().decode('utf-8')
    for line in original.splitlines():
        if 'REQ' in line[:24] or line.startswith('Anforderungen:'):
            if not any(line in c['source_quote'] for c in facts if c['kind'] == 'REQUIREMENT'):
                failures.append('Explicit requirement omitted: ' + line)
    return failures


async def main():
    reasoner = LocalEngineeringReasoner()
    build_manifest = runpy.run_path(str(ROOT / 'scripts/write-build-info.py'))['build_manifest']
    manifest = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Native inference on other original project files; semantic review separate',
        'database_access': False,
        'model': reasoner.model,
        'endpoint': reasoner.chat_url,
        'full_application_source_sha256': build_manifest()['source_sha256'],
        'application_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                               for p in ('backend/nis/agent/orchestration/local_reasoner.py',
                                         'backend/nis/agent/orchestration/project_intake.py', 'backend/nis/communication/technologies/i2c/profile.json', 'backend/nis/communication/technologies/wifi/profile.json')},
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
                                 'url': str(response.request.url), 'http_status': response.status_code,
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
                failures = semantic_oracle(case_id, result)
                item.update(status='SEMANTIC_FAILED' if failures else 'RETEST_PASSED', semantic_failures=failures)
            except Exception as error:
                item.update(status='NATIVE_FAILED', error=str(error), error_type=type(error).__name__)
            item.update(seconds=round(time.monotonic() - started, 2), calls=len(current['calls']))
            save(OUT / 'manifest.json', manifest)
            print(json.dumps(item, ensure_ascii=True), flush=True)
            if item['status'] != 'RETEST_PASSED':
                break
    finally:
        sink.reset(token)
        await reasoner.client.aclose()
    manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
    assert build_manifest()['source_sha256'] == manifest['full_application_source_sha256']
    for path, digest in manifest['application_hashes'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    manifest['final_application_integrity_verified'] = True
    save(OUT / 'manifest.json', manifest)
    if any(c['status'] != 'RETEST_PASSED' for c in manifest['cases']):
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
