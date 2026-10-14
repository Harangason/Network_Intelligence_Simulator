"""Recheck the exact failed original segment; never claim full-file acceptance."""
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK.parents[2]))
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner


async def main():
    source = (WORK / 'failed-source-segment2.txt').read_bytes().decode('utf-8')
    reasoner = LocalEngineeringReasoner()
    captures = []

    async def capture(response):
        if response.request.url.path == '/api/chat':
            await response.aread()
            captures.append(response.json())
            (WORK / 'live-failed-segment-responses.json').write_text(
                json.dumps(captures, ensure_ascii=False, indent=2), encoding='utf-8')

    reasoner.client.event_hooks['response'] = [capture]
    started = time.monotonic()
    try:
        result = await reasoner.interpret_document(source, 'Fahrzeug komplett.txt – Abschnitt 2 (Regression)')
        assert result['source_complete'] is True
        assert result['source_chars'] == len(source)
        assert result['source_sha256'] == hashlib.sha256(source.encode()).hexdigest()
        assert result['canonical_writes'] is False
        assert result['status'] == 'REVIEW_REQUIRED'
        technologies = result['interpretation']['technologies']
        assert any(t['kind'] == 'TRANSPORT' and t['name'].lower().replace('-', '_') == 'can_fd'
                   for t in technologies)
        for item in [*result['interpretation']['components'], *technologies]:
            assert item['source_quote'] in source
        (WORK / 'live-failed-segment-proposal.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'status': 'PASS', 'probe_scope': 'failed_original_segment_2_only',
            'seconds': round(time.monotonic() - started, 2), 'model': result['model'],
            'source_chars': result['source_chars'], 'source_sha256': result['source_sha256']},
            ensure_ascii=True), flush=True)
    finally:
        await reasoner.client.aclose()


asyncio.run(main())
