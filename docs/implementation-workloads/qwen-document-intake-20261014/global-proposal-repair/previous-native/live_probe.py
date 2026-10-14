"""Exercise native document interpretation without product database access."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.nis.engineering.goal_execution.progress import sink

SOURCE = '''2.1 Powertrain Domain Controller (PDC)
2.2 Chassis Domain Controller (CDC)
2.3 ADAS Domain Controller (ADC)
Sensorik (Radar, Kamera)
Aktorik (Bremsaktuator, Lenkaktuator)
Sensor: Probe, Anschluss: ADC Eingang.
Kommunikationsnetzwerke: CAN‑FD.
Connectivity: Bluetooth, Mobilfunk.
Funktion: Fusion.
REQ-SAFE-14: Fusion MUSS bei Ausfall eines Sensors degradieren.
Unbekannte Schnittstelle: GMSL.
'''


async def main():
    reasoner = LocalEngineeringReasoner()
    responses = []
    request_scopes = []
    async def capture(response):
        if response.request.url.path == '/api/chat':
            await response.aread()
            responses.append(response.json())
            payload = json.loads(response.request.content)
            request_scopes.append({'call': len(responses),
                'input': json.loads(payload['messages'][1]['content']),
                'format': payload['format']})
            Path(__file__).with_name('live-qwen-request-scopes.json').write_text(json.dumps(request_scopes, ensure_ascii=False, indent=2), encoding='utf-8')
            Path(__file__).with_name('live-qwen-response-capture.json').write_text(json.dumps(responses, ensure_ascii=False, indent=2), encoding='utf-8')
            actual = responses[-1]
            print(json.dumps({'status': 'MODEL_RESPONSE_RECEIVED', 'call': len(responses),
                'model': actual.get('model'), 'tokens': actual.get('eval_count'),
                'seconds': round(actual.get('total_duration', 0) / 1e9, 2)}, ensure_ascii=True), flush=True)
    reasoner.client.event_hooks['response'] = [capture]
    started = time.monotonic()
    progress_token = sink.set(lambda event: print(json.dumps(event, ensure_ascii=True), flush=True))
    try:
        source = Path(sys.argv[1]).read_bytes().decode('utf-8') if len(sys.argv) > 1 else SOURCE
        result = await reasoner.interpret_document(source, 'Fahrzeug komplett.txt' if len(sys.argv) > 1 else 'Semantikprobe.txt')
        assert result['source_complete'] is True and result['canonical_writes'] is False
        assert result['status'] == 'REVIEW_REQUIRED' and result['provider'] == 'local_ollama'
        output = Path(__file__).with_name('live-qwen-full-proposal.json' if len(sys.argv) > 1 else 'live-qwen-compact-proposal.json')
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        if len(sys.argv) == 1:
            components = result['interpretation']['components']
            technologies = result['interpretation']['technologies']
            for name in ('Powertrain', 'Chassis', 'ADAS'):
                assert any(c['kind'] == 'INSTANCE' and c['role'] == 'CONTROLLER' and name in c['name'] for c in components)
            assert any(c['kind'] == 'CATEGORY' and c['role'] == 'SENSOR' and c['quantity'] is None for c in components)
            assert any(c['kind'] == 'CATEGORY' and c['role'] == 'ACTUATOR' and c['quantity'] is None for c in components)
            assert any(c['kind'] == 'FUNCTION' and c['name'] == 'Fusion' for c in components)
            assert any(c['kind'] == 'REQUIREMENT' for c in components)
            assert any(t['kind'] == 'DEVICE_ALIAS' and t['name'] == 'ADC' for t in technologies)
            assert any(t['kind'] == 'TRANSPORT' and t['name'] == 'ADC' for t in technologies)
            assert any(t['kind'] == 'UNRESOLVED' and t['name'] == 'GMSL' for t in technologies)
            for name in ('Bluetooth', 'Mobilfunk'):
                assert any(t['kind'] == 'UNRESOLVED' and t['name'] == name for t in technologies)
        else:
            components = result['interpretation']['components']
            for name in ('Powertrain', 'Chassis', 'ADAS', 'Body', 'Infotainment'):
                assert any(c['kind'] == 'INSTANCE' and c['role'] == 'CONTROLLER' and name in c['name'] for c in components)
            for role in ('SENSOR', 'ACTUATOR'):
                assert any(c['kind'] == 'CATEGORY' and c['role'] == role and c['quantity'] is None for c in components)
            assert result['source_chars'] == 19088
        print(json.dumps({'status': 'PASS', 'seconds': round(time.monotonic() - started, 2), 'model': result['model'], 'source_chars': result['source_chars'], 'segments': len(result['segments']), 'proposal': str(output)}, ensure_ascii=False), flush=True)
    finally:
        sink.reset(progress_token)
        await reasoner.client.aclose()


asyncio.run(main())
