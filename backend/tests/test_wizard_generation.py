"""Real MCP regression for combined wizard creation, without local LLM calls."""
import asyncio
from collections import Counter
from uuid import uuid4

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.engineering.agent_tools.runtime import ToolAuthority
from backend.engineering.agent_tools.runtime import execute
from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import wizard_generation, model, proposal_service
from backend.simulator_engineering_mcp.server import create_server
from backend.engineering.workflow.service import WorkflowStatusService
from backend.engineering.repository import create_object, update_object, get_object
from backend.engineering.agent_tools import conversation
from backend.engineering.agent_tools.run_status import reconcile_model_apply
import pytest


def test_combined_wizard_creates_validated_model_without_reasoner():
    authority = ToolAuthority(f'pytest-wizard-generator-{uuid4()}')
    prompt = '''Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: test-wizard-12345678
- Industrie: Automotive
- Hardware-Sollwerte: {"gateways":1,"ecus":50,"sensors":100,"actuators":100}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge ein Fahrzeugnetzwerk mit 100 Sensoren, 100 Aktuatoren, 50 ECUs und 1 Gateway.
25 LIN, 10 CAN-FD und 5 Automotive Ethernet. Prüfe, welche Nachrichten das Gateway passieren.
'''

    class NoReasoner:
        async def next(self, *args):
            raise AssertionError('Confirmed mass creation must not depend on an LLM tool decision')

    async def invoke():
        async with EngineeringMCPClient(create_server(authority)) as client:
            return await EngineeringAgent(client, reasoner=NoReasoner()).run(
                prompt, AgentContext(active_project_id=authority.project_id))

    result = asyncio.run(invoke())
    assert result['status'] == 'READY_FOR_REVIEW', result
    proposal = result['proposals'][0]
    assert proposal['status'] == 'VALIDATED', proposal['validation_result']
    hardware = [c for c in proposal['changes'] if c['object_type'] == 'HardwareNode']
    assert len(hardware) == 251
    assert len({c['data']['name'] for c in hardware}) == 251
    assert not proposal['canonical_ids']  # Review remains required.
    assert any(event.get('workload', {}).get('completed', 0) > 0 for event in result['events'] if event.get('workload'))
    by_ref = {'$' + c['local_ref']: c for c in proposal['changes']}
    signal_counts = Counter()
    for change in proposal['changes']:
        if change['object_type'] != 'Signal':
            continue
        message = by_ref[change['data']['message_id']]
        port = by_ref[message['data']['hardware_interface_id']]
        signal_counts[port['data']['hardware_node_id']] += 1
    assert all(signal_counts['$' + c['local_ref']] >= 5 for c in hardware if c['data']['device_type'] == 'ECU')
    duplicate = execute(authority, 'test_retry', Permission.GENERATE_PROPOSAL, {}, lambda _: wizard_generation.generate({'prompt': prompt}))
    assert duplicate.success, duplicate
    assert duplicate.data['proposal_id'] == proposal['proposal_id']
    untouched = execute(authority, 'test_canonical', Permission.READ_MODEL, {}, lambda _: model.objects('HardwareNode'))
    assert untouched.data == []
    # Simulate the two explicit human actions in this isolated test project only.
    approved = execute(authority, 'test_human_review', Permission.READ_MODEL, {}, lambda _: proposal_service.review(
        proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='test-human', trace_id=str(uuid4())))
    assert approved.success and approved.data['status'] == 'APPROVED', approved
    applied = execute(authority, 'test_human_apply', Permission.READ_MODEL, {}, lambda _: proposal_service.apply(
        proposal['proposal_id'], actor='test-human', trace_id=str(uuid4())))
    assert applied.success and applied.data['status'] == 'APPLIED', applied
    assert len(applied.data['canonical_ids']) == len(proposal['changes'])
    check = WorkflowStatusService(authority.project_id).get(summary=True)['artifact_checks']['engineering_model']
    assert check['complete'], check
    assert check['consistency']['functions_unexpected'] == 0
    def restore_review_state():
        state = conversation.read()
        state.update(active_proposal=proposal['proposal_id'], current_requirement=prompt)
        conversation.write(state)
        WorkflowStatusService(authority.project_id).set_context({'agent_execution': {
            'run_id': 'test-wizard-12345678', 'state': 'REVIEW_REQUIRED', 'step': 'engineering_model',
            'completed': 1, 'total': 1}})
        reconcile_model_apply(authority.project_id, applied.data)
        return WorkflowStatusService(authority.project_id).get(summary=True)['context']['agent_execution']
    reconciled = execute(authority, 'test_apply_status', Permission.READ_MODEL, {}, lambda _: restore_review_state())
    assert reconciled.success and reconciled.data['state'] == 'READY_TO_CONTINUE', reconciled
@pytest.mark.parametrize('device_class', [0, 1, 2])
def test_basic_sensor_interfaces_reparent_without_losing_children(device_class):
    authority = ToolAuthority(f'pytest-class-reparent-{uuid4()}')
    def operation():
        hardware = create_object('HardwareNode', {'name': 'TemperatureProbe', 'device_type': 'SensorController', 'device_class': device_class})
        function = create_object('Function', {'name': 'ObsoleteFunction', 'hardware_node_id': str(hardware['id'])})
        interface = create_object('Interface', {'name': 'TemperaturePort', 'function_id': str(function['id']), 'interface_type': 'CAN_FD'})
        message = create_object('Message', {'name': 'TemperatureFrame', 'interface_id': str(interface['id']),
            'direction': 'tx', 'cycle_ms': 10, 'dlc': 8})
        signal = create_object('Signal', {'name': 'Temperature', 'message_id': str(message['id']),
            'start_bit': 0, 'length_bits': 8, 'byte_order': 'little_endian', 'data_type': 'unsigned',
            'factor': 1, 'offset_value': 0})
        moved = update_object('Interface', str(interface['id']), {'function_id': None,
            'hardware_node_id': str(hardware['id']), 'expected_version': interface['version'], 'actor': 'test'})
        assert moved['function_id'] is None
        assert str(moved['hardware_node_id']) == str(hardware['id'])
        assert str(get_object('Message', str(message['id']))['interface_id']) == str(interface['id'])
        assert str(get_object('Signal', str(signal['id']))['message_id']) == str(message['id'])
        proposal = proposal_service.create('TEST_CLASS_POLICY', [{'object_type':'Function', 'data':{
            'name':'InvalidGeneratedFunction', 'hardware_node_id':str(hardware['id'])}}], 'test')
        assert not proposal_service.validate(proposal['proposal_id'])['validation_result']['valid']
        return {'ok': True}
    result = execute(authority, 'test_reparent', Permission.READ_MODEL, {}, lambda _: operation())
    assert result.success, result.findings
