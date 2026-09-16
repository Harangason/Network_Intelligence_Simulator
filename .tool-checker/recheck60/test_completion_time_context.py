"""S35: actual MCP transport over a project-scoped imported HTTP trace."""
import asyncio
import json
from pathlib import Path

pytest_plugins = ['backend.tests.conftest']
ROOT = Path(__file__).resolve().parents[2]


def test_live_synchronized_context_and_clock_rejection(monkeypatch):
    receipt = json.loads((ROOT / 'backend/test-output/industry60-completion/d8a5a6840084/receipt.json').read_text())
    assert receipt['base_url'] == 'http://127.0.0.1:56335'
    assert receipt['containers']['app'] == 'nis-e2e-app-d8a5a6840084'
    monkeypatch.setenv('SIMULATOR_JOB_API_URL', receipt['base_url'] + '/api')
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.simulator_engineering_mcp.server import create_server
    from backend.engineering.agent_tools.runtime import ToolAuthority
    session = 'ca36ff7307b8417a83480c6e112f9eb1'
    arguments = {'session_id': session, 'time_s': 12.5, 'time_basis': 'relative'}
    async def probe():
        results = {}
        async with EngineeringMCPClient(create_server(ToolAuthority('nis-e2e-industry60-trace-completion'))) as client:
            for label, tool, extra in [
                ('position', 'resolve_trace_time', {}),
                ('context', 'resolve_trace_event_context', {'event_id': session + ':1'}),
                ('wrong_clock', 'resolve_trace_time', {'time_basis': 'utc'}),
                ('wrong_event', 'resolve_trace_event_context', {'event_id': session + ':2'}),
            ]:
                results[label] = (await client.call(tool, {**arguments, **extra})).model_dump(mode='json')
        async with EngineeringMCPClient(create_server(ToolAuthority('nis-e2e-industry60-foreign-context'))) as client:
            results['foreign_session'] = (await client.call('resolve_trace_time', arguments)).model_dump(mode='json')
        return results
    results = asyncio.run(probe())
    assert results['position']['success'], results['position']
    assert results['context']['success'], results['context']
    assert results['context']['data']['event']['time_s'] == 12.5
    assert results['context']['data']['event']['signals']['HealthState']['value'] == 'WARNING'
    assert not results['wrong_clock']['success']
    assert 'TRACE_TIMEBASE_MISMATCH' in json.dumps(results['wrong_clock'])
    assert not results['wrong_event']['success']
    assert not results['foreign_session']['success']
    target = ROOT / '.tool-checker/evidence/industry60-completion/S35'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'live-mcp-time-context.json').write_text(json.dumps(results, indent=2), encoding='utf8')
