from uuid import uuid4

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import capabilities, generation, proposal_service
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.repository import create_object
from backend.engineering.simulation import propose_faults, list_scenarios


def test_fault_scenario_needs_review_and_uses_actual_project_target():
    authority = ToolAuthority('fault-activation-' + uuid4().hex)
    def call(operation):
        result = execute(authority, 'fault-test', Permission.GENERATE_PROPOSAL, {}, lambda _: operation())
        assert result.success, result.findings
        return result.data
    def setup():
        hardware = create_object('HardwareNode', {'name': 'Sensor', 'device_type': 'SensorController'})
        interface = create_object('Interface', {'name': 'SensorEthernet', 'hardware_node_id': str(hardware['id']), 'interface_type': 'Ethernet'})
        message = create_object('Message', {'name': 'Temperature', 'interface_id': str(interface['id']), 'dlc': 8, 'cycle_ms': 100})
        return str(message['id'])
    message_id = call(setup)
    faults = call(lambda: propose_faults(model_review=False))
    fault = next(item for item in faults if item['fault_type'] == 'MESSAGE_LOSS')
    proposal = call(lambda: capabilities.plan_fault_activation({'fault_proposal_ids': [str(fault['proposal_id'])],
                    'name': 'Ausfall prüfen', 'duration_s': 1, 'rationale': 'Empfänger-Timeout prüfen.'}))
    assert proposal['status'] == 'VALIDATED'
    assert not proposal['changes'][0]['data']['faults'][0]['approved']
    assert call(list_scenarios) == []
    denied = execute(authority, 'apply', Permission.GENERATE_PROPOSAL, {},
                     lambda _: proposal_service.apply(proposal['proposal_id'], actor='agent', trace_id=uuid4().hex))
    assert not denied.success
    call(lambda: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human', trace_id=uuid4().hex))
    first = call(lambda: proposal_service.apply(proposal['proposal_id'], actor='human', trace_id=uuid4().hex))
    replay = call(lambda: proposal_service.apply(proposal['proposal_id'], actor='human', trace_id=uuid4().hex))
    assert first['canonical_ids'] == replay['canonical_ids']
    scenarios = call(list_scenarios)
    assert len(scenarios) == 1
    assert scenarios[0]['faults'][0]['approved'] is True
    assert scenarios[0]['faults'][0]['target']['id'] == message_id
    invalid = call(lambda: generation.scenario({'scenario': {'name': 'Falsches Ziel', 'mode': 'AI_GENERATED_FAULT',
                           'faults': [{'scope': 'MESSAGE', 'type': 'MESSAGE_LOSS', 'target': {'id': str(uuid4())}}]}}))
    checked = call(lambda: proposal_service.validate(invalid['proposal_id']))
    assert not checked['validation_result']['valid']
    assert len(call(list_scenarios)) == 1
