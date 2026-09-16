"""S37 actual MCP calls for every required deviation class, labelled inline fixture."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4

pytest_plugins = ['backend.tests.conftest']


def test_golden_deviation_matrix_via_mcp():
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.simulator_engineering_mcp.server import create_server
    from backend.engineering.agent_tools.runtime import ToolAuthority
    golden = {'time_s': 12.5, 'time_basis': 'relative', 'route_id': 'route', 'sequence': 10,
              'signals': {'Temperature': 20, 'OperatingState': 'RUN'}, 'route_ref': 'r', 'network_id': 'n'}
    variants = {'value': {'signals': {'Temperature': 30, 'OperatingState': 'RUN'}},
                'state': {'signals': {'Temperature': 20, 'OperatingState': 'FAULT'}},
                'timing': {'time_s': 12.6}, 'route': {'route_ref': 'other'}, 'network': {'network_id': 'other'}}
    async def calls():
        results = {}
        async with EngineeringMCPClient(create_server(ToolAuthority('nis-e2e-golden-' + uuid4().hex))) as client:
            for label, change in variants.items():
                results[label] = (await client.call('compare_golden_trace',
                    {'events': [{**golden, **change}], 'golden_events': [golden]})).model_dump(mode='json')
            for label, actual, reference in [
                ('additional', [golden, {**golden, 'sequence': 11, 'time_s': 13}], [golden]),
                ('missing', [golden], [golden, {**golden, 'sequence': 11, 'time_s': 13}]),
                ('unknown_clock', [{**golden, 'time_basis': 'unknown'}], [golden]),
                ('duplicate', [golden, golden], [golden]),
                ('missing_time', [{'route_id': 'route', 'sequence': 10}], [golden]),
            ]:
                results[label] = (await client.call('compare_golden_trace',
                    {'events': actual, 'golden_events': reference})).model_dump(mode='json')
        return results
    results = asyncio.run(calls())
    for label in [*variants, 'additional', 'missing']:
        assert results[label]['success'], results[label]
        assert results[label]['data']['deviation_count'] == 1
        assert results[label]['data']['first_divergence']['time_s'] == (13 if label in {'additional', 'missing'} else 12.5)
    for label in ['unknown_clock', 'duplicate', 'missing_time']:
        assert not results[label]['success'], results[label]
    folder = Path(__file__).resolve().parents[1] / 'evidence/industry60-completion/S37'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'mcp-matrix.json').write_text(json.dumps({'origin': 'Explicit synthetic inline comparison fixture; no simulation provenance claimed',
        'golden': golden, 'variants': variants, 'results': results}, indent=2), encoding='utf8')
