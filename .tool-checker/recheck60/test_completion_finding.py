"""S29: actual articulation finding and scripted decision lifecycle in disposable SQL."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4

pytest_plugins = ['backend.tests.conftest']


def test_spof_assessment_uses_persisted_calculated_finding():
    from backend.agent_core.api.agent_response import AgentResponse
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.agent_core.api.tool_contract import Permission
    from backend.agent_core.context.agent_context import AgentContext
    from backend.agent_core.core.engineering_agent import EngineeringAgent
    from backend.engineering.agent_tools.runtime import ToolAuthority, execute
    from backend.engineering.agent_tools import conversation
    from backend.engineering.repository import create_object
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.intelligence.service import IntelligenceService
    from backend.simulator_engineering_mcp.server import create_server
    authority = ToolAuthority('nis-e2e-industry60-s29-' + uuid4().hex)
    def call(fn):
        result = execute(authority, 'isolated-s29-fixture', Permission.GENERATE_PROPOSAL, {}, lambda _: fn())
        assert result.success, result.model_dump()
        return result.data
    nodes = [call(lambda name=name, kind=kind: create_object('HardwareNode', {'name': name, 'device_type': kind}))
             for name, kind in [('SourceController', 'ECU'), ('CentralGateway', 'Gateway'), ('DestinationController', 'ECU')]]
    topology = {'nodes': [{'id': node['id'], 'label': node['name'], 'ports': []} for node in nodes],
                'edges': [{'id': 'test-edge-' + str(i), 'source': nodes[i]['id'], 'target': nodes[i+1]['id']} for i in (0, 1)]}
    call(lambda: WorkflowStatusService(authority.project_id).save_topology(topology, actor='isolated-test'))
    assessment = call(lambda: IntelligenceService(authority.project_id).assess())
    issue = next(item for item in assessment['findings'] if item['code'] == 'SINGLE_POINT_OF_FAILURE')
    assert issue['object_id'] == nodes[1]['id'] and issue['requires_user_confirmation']
    assert issue['approval_state'] == 'PENDING_CONFIRMATION'
    context = AgentContext(active_project_id=authority.project_id)
    turn = call(lambda: conversation.begin('Berechneten Graphbefund prüfen', context))
    finding = AgentResponse(type='FINDING', title=issue['code'], text=issue['problem'], severity=issue['severity'],
        context_refs=[{'id': nodes[1]['id'], 'type': 'HardwareNode'}],
        metadata={'analysis_snapshot_id': str(assessment['snapshot_id']), 'calculated_issue': issue}).model_dump(mode='json', exclude_none=True)
    call(lambda: conversation.record_event(turn['run_id'], finding))
    call(lambda: conversation.finish(turn['run_id']))
    async def run():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client).run('Bewerte SINGLE_POINT_OF_FAILURE am CentralGateway.', context)
    result = asyncio.run(run())
    assert result['status'] == 'ANSWERED', result
    assert any(event.get('id') == finding['id'] for event in result['events'])
    persisted = call(conversation.inspect)
    assert persisted.get('decisions', {}).get(finding['id'], {}).get('status') != 'ACCEPTED_RISK'
    # The manifest's risk-decision lifecycle is exercised on a disposable graph.
    # This is SCRIPTED_TEST, not acceptance of a user's engineering risk.
    rationale = 'SCRIPTED_TEST: isolierte Drei-Knoten-Fixture; keine produktive Risikoakzeptanz.'
    call(lambda: conversation.decide(finding['id'], 'ACCEPTED_RISK', rationale, True))
    accepted = call(conversation.inspect)
    decision = accepted['decisions'][finding['id']]
    assert decision['status'] == 'ACCEPTED_RISK'
    assert rationale in json.dumps(decision, ensure_ascii=False)
    call(lambda: create_object('HardwareNode', {'name': 'ChangedArchitecture', 'device_type': 'ECU'}))
    changed = call(conversation.inspect)
    assert changed['decisions'][finding['id']]['status'] == 'NEEDS_REVIEW'
    folder = Path(__file__).resolve().parents[1] / 'evidence/industry60-completion/S29'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'calculated-finding-mcp.json').write_text(json.dumps({'topology': topology, 'assessment': assessment,
        'finding': finding, 'agent': result, 'conversation': persisted, 'accepted': accepted, 'after_change': changed,
        'scope': 'SCRIPTED_TEST graph and decision lifecycle; no productive risk acceptance or physical-network validation'}, indent=2), encoding='utf8')
