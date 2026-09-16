"""S31 live HTTP job/import metadata through the actual MCP server."""
import asyncio
import json
from pathlib import Path

pytest_plugins = ['backend.tests.conftest']
ROOT = Path(__file__).resolve().parents[2]


def test_live_trace_session_sources(monkeypatch):
    receipt = json.loads((ROOT / 'backend/test-output/industry60-completion/0b317d9b014d/receipt.json').read_text())
    assert receipt['status'] == 'PREPARED' and receipt['containers']['app'].startswith('nis-e2e-app-')
    assert receipt['base_url'] == 'http://127.0.0.1:60295'
    monkeypatch.setenv('SIMULATOR_JOB_API_URL', receipt['base_url'] + '/api')
    report = json.loads((ROOT / '.tool-checker/evidence/industry60-completion/S01-A/nis-e2e-completion-s01-8fbae1d7/nine-stage-http.json').read_text())
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.simulator_engineering_mcp.server import create_server
    from backend.engineering.agent_tools.runtime import ToolAuthority
    async def probe():
        results = {}
        async with EngineeringMCPClient(create_server(ToolAuthority(report['project']))) as client:
            for label, extra in [('simulation', {}), ('golden', {'golden': True})]:
                results[label] = (await client.call('inspect_trace_session', {'job_id': report['job_id'], **extra})).model_dump(mode='json')
        async with EngineeringMCPClient(create_server(ToolAuthority('nis-e2e-industry60-s32-profiles'))) as client:
            results['import'] = (await client.call('inspect_trace_session', {'session_id': '083ba459126c409eac3eb3cefe4472ee'})).model_dump(mode='json')
            results['import_window'] = (await client.call('load_trace', {'session_id': '083ba459126c409eac3eb3cefe4472ee',
                'start_s': 2, 'end_s': 3, 'query': 'DDS', 'limit': 1})).model_dump(mode='json')
            results['foreign_job'] = (await client.call('inspect_trace_session', {'job_id': report['job_id']})).model_dump(mode='json')
        return results
    results = asyncio.run(probe())
    for label, source_type in [('simulation', 'SimulationTrace'), ('golden', 'GoldenTrace'), ('import', 'ImportTrace')]:
        assert results[label]['success'], results[label]
        data = results[label]['data']
        assert data['source_type'] == source_type
        assert data['total_events'] > 0 and data['technologies'] and data['networks']
        assert data['timebase']['bases'] and data['time_range']['end_s'] >= data['time_range']['start_s']
        assert data['simulation_run_ref'] == (None if label == 'import' else report['job_id'])
    assert not results['foreign_job']['success']
    assert results['import_window']['success'], results['import_window']
    assert len(results['import_window']['data']['events']) == 1
    assert results['import_window']['data']['events'][0]['technology'] == 'DDS'
    folder = ROOT / '.tool-checker/evidence/industry60-completion/S31'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'live-mcp-sessions.json').write_text(json.dumps({'receipt': receipt, 'results': results}, indent=2), encoding='utf8')
