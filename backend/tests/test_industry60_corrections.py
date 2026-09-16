import asyncio
import pytest
from backend.engineering.reasoning.engine import EngineeringReasoningEngine
from backend.engineering.agent_tools.analysis import window
from backend.agent_core.api.tool_contract import ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent


def test_gateway_segments_do_not_count_as_route_changes():
    events = [dict(time_s=i, route_id=route, message_ids=['message'], sender_interface=port, network=net,
                   receiver_interfaces=['target']) for i, (route, port, net) in enumerate([
        ('ingress','source','CAN'), ('egress','gateway','ETH'), ('ingress','source','CAN'), ('egress','gateway','ETH')])]
    def analyze(rows):
        return EngineeringReasoningEngine().analyze(project_id='test', job_id='run', events=rows, context={})
    assert not [o for o in analyze(events).observations if o.type == 'ROUTE_CHANGE']
    events.append({**events[-1], 'time_s': 5, 'network':'ETH-new'})
    assert len([o for o in analyze(events).observations if o.type == 'ROUTE_CHANGE']) == 1


@pytest.mark.parametrize('event', [{'message_id':'missing'}, {'time_s':None}, {'time_s':float('nan')}, {'time_s':-1}])
def test_inline_trace_never_invents_time_zero(event):
    with pytest.raises(ValueError):
        window({'events':[event]})


def test_explicit_connection_overrides_create_entry_mode():
    class Client:
        async def call(self, name, arguments=None):
            assert name == 'prepare_engineering_connection'
            assert arguments['source_ref'] == 'ParkAssist'
            assert arguments['target_ref'] == 'DriverAssistance'
            return ToolResult(data={'workload_id':'goal-test','status':'INCOMPLETE', 'agent_response':
                {'type':'RESULT','status':'INCOMPLETE','text':'Portentscheidung erforderlich.'}})
    result = asyncio.run(EngineeringAgent(Client()).run(
        'Verbinde ParkAssist mit DriverAssistance, prüfe die Kommunikation in einer kurzen Simulation und analysiere auftretende Timingprobleme.',
        AgentContext(active_project_id='test', requested_mode='CREATE_ARCHITECTURE')))
    assert result['context']['current_workload'] == 'goal-test'

def test_import_session_keeps_all_records_and_is_project_scoped(tmp_path, monkeypatch):
    import json
    from flask import Flask
    from backend.app.trace_import import trace_import_api
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path))
    app = Flask(__name__)
    app.register_blueprint(trace_import_api)
    client = app.test_client()
    content = '\n'.join(json.dumps({'time_s':i / 10, 'message_id':str(i)}) for i in range(100501))
    response = client.post('/trace-import?filename=large.jsonl', data=content, headers={'X-Project-ID':'audit'})
    assert response.status_code == 200, response.json
    first = response.json
    assert first['total_events'] == 100501
    assert len(first['events']) == 2000 and not first['truncated']
    url = '/trace-import/' + first['session_id']
    assert client.get(url, headers={'X-Project-ID':'other'}).status_code == 404
    second = client.get(url + '?cursor=' + str(first['next_cursor']), headers={'X-Project-ID':'audit'}).json
    assert second['events'][0]['message_id'] == '2000'
    reloaded = client.get(url, headers={'X-Project-ID':'audit'}).json
    assert reloaded['events'][0]['event_id'] == first['events'][0]['event_id']
    assert len(first['source_sha256']) == 64

def test_trace_analysis_stops_at_complete_page_without_continuation_loop():
    class Client:
        async def call(self, name, arguments=None):
            assert name == 'analyze_trace_root_cause'
            assert arguments['job_id'] == 'job-test'
            return ToolResult(status='PARTIAL', data={'conclusion':'Snapshot fehlt.', 'continuation': None})
    result = asyncio.run(EngineeringAgent(Client()).run('Analysiere den Trace', AgentContext(
        active_project_id='test', requested_mode='ANALYZE_TRACE', selected_object_refs=[{'object_type':'SimulationRun','id':'job-test'}])))
    assert result['status'] == 'INCOMPLETE'
    assert len(result['trace']) == 1


def test_mcp_invalid_input_has_field_and_schema():
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.engineering.agent_tools.runtime import ToolAuthority
    from backend.simulator_engineering_mcp.server import create_server
    async def check():
        async with EngineeringMCPClient(create_server(ToolAuthority('industry60-test'))) as client:
            result = await client.call('calculate_message_size', {'technology':'CAN_FD','payload_bytes':-2})
            assert result.status.value == 'INVALID_INPUT'
            assert any('payload_bytes' in f['field'] and f['expected_schema'] for f in result.findings)
    asyncio.run(check())

def test_raw_mcp_input_errors_are_structured():
    from mcp import Client
    from backend.engineering.agent_tools.runtime import ToolAuthority
    from backend.simulator_engineering_mcp.server import create_server
    async def check():
        async with Client(create_server(ToolAuthority('industry60-test'))) as client:
            response = await client.call_tool('calculate_message_size', {'request':{'technology':'CAN_FD','payload_bytes':-2}})
            assert response.is_error
            data = response.structured_content
            assert data['status'] == 'INVALID_INPUT'
            assert data['findings'][0]['field'] == ['request','payload_bytes']
    asyncio.run(check())

def test_mdf_session_does_not_truncate_supported_channels(tmp_path, monkeypatch):
    import numpy as np
    from asammdf import MDF, Signal
    from flask import Flask
    from backend.app.trace_import import trace_import_api
    monkeypatch.setenv('SIMULATOR_SAVED_ROOT', str(tmp_path / 'saved'))
    path = tmp_path / 'long.mf4'
    with MDF(version='4.10') as mdf:
        mdf.append(Signal(samples=np.arange(4500), timestamps=np.arange(4500)/10, name='temperature'))
        mdf.save(path)
    app = Flask(__name__)
    app.register_blueprint(trace_import_api)
    response = app.test_client().post('/trace-import?filename=long.mf4', data=path.read_bytes())
    assert response.status_code == 200, response.json
    assert response.json['total_events'] == 4500
    assert not response.json['partial']

def test_original_gateway_trace_shares_route_id_across_distinct_segments():
    import json
    from pathlib import Path
    events=json.loads((Path(__file__).parents[2] / 'tests/fixtures/industry60-gateway-segments.json').read_text())
    assert len({e['route_id'] for e in events}) == 1
    assert len({e['segment_id'] for e in events}) == 2
    def analyze(rows):
        return EngineeringReasoningEngine().analyze(project_id='test',job_id='original',events=rows,context={})
    assert not any(o.type == 'ROUTE_CHANGE' for o in analyze(events).observations)
    events.append({**events[-1], 'time_s':20,'network':'changed-network'})
    assert sum(o.type == 'ROUTE_CHANGE' for o in analyze(events).observations) == 1
