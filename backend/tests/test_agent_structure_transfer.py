from uuid import uuid4

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import proposal_service
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools.services import TOOLS
from backend.engineering.repository import create_object, get_object, list_objects
from backend.engineering.structure_transfer import analyze_ecu_transfer


def test_transfer_uses_real_hierarchy_proposal_review_and_apply():
    authority = ToolAuthority('agent-transfer-' + uuid4().hex)
    def run(operation):
        result = execute(authority, 'transfer-test', Permission.READ_MODEL, {}, lambda _: operation())
        assert result.success, result.findings
        return result.data
    def setup():
        source = create_object('HardwareNode', {'name': 'Source', 'device_type': 'ECU'})
        target = create_object('HardwareNode', {'name': 'Target', 'device_type': 'ECU'})
        function = create_object('Function', {'name': 'SourceTemperature', 'hardware_node_id': str(source['id'])})
        interface = create_object('Interface', {'name': 'SourceCAN', 'function_id': str(function['id']), 'interface_type': 'CAN_FD'})
        message = create_object('Message', {'name': 'SourceStatus', 'interface_id': str(interface['id']), 'cycle_ms': 100, 'dlc': 1})
        create_object('Signal', {'name': 'SourceEnabled', 'message_id': str(message['id']), 'start_bit': 0, 'length_bits': 1,
                                'byte_order': 'little_endian', 'data_type': 'boolean', 'factor': 1, 'offset_value': 0,
                                'min_value': 0, 'max_value': 1, 'unit': 'code', 'semantic': {'semantic_type': 'BOOLEAN'},
                                'data': {'enum_values': {'OFF': 0, 'ON': 1}}})
        return str(source['id']), str(target['id'])
    source, target = run(setup)
    analysis = run(lambda: analyze_ecu_transfer({'source_hardware_id': source, 'target_hardware_ids': [target]}))
    transfer_id = analysis['targets'][0]['proposal_id']
    tool = TOOLS['plan_structure_transfer']
    args = tool.input_model.model_validate({'transfer_proposal_id': transfer_id, 'rationale': 'Bestätigte Referenzstruktur auf Target übertragen.'}).model_dump()
    result = execute(authority, tool.name, tool.permission, args, tool.handler)
    assert result.success, result.findings
    proposal = result.data
    assert proposal['status'] == 'VALIDATED', proposal['validation_result']
    assert len(proposal['changes']) == 4
    repeated = execute(authority, tool.name, tool.permission, args, tool.handler)
    assert repeated.success and repeated.data['proposal_id'] == proposal['proposal_id']
    for change in proposal['changes']:
        assert not {'approval_state', 'review_state', 'actor', 'created_by'} & change['data'].keys()
    assert len(run(lambda: list_objects('Function'))) == 1
    run(lambda: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human', trace_id=uuid4().hex))
    applied = run(lambda: proposal_service.apply(proposal['proposal_id'], actor='human', trace_id=uuid4().hex))
    assert applied['status'] == 'APPLIED'
    functions = run(lambda: list_objects('Function'))
    assert len(functions) == 2
    new_function = next(item for item in functions if str(item['hardware_node_id']) == target)
    interfaces = run(lambda: list_objects('Interface'))
    new_interface = next(item for item in interfaces if str(item.get('function_id')) == str(new_function['id']))
    assert str(new_interface['hardware_node_id']) == target
    run(lambda: proposal_service.apply(proposal['proposal_id'], actor='human', trace_id=uuid4().hex))
    assert len(run(lambda: list_objects('Signal'))) == 2
    repeated = execute(authority, tool.name, tool.permission, args, tool.handler)
    assert repeated.success and repeated.data['status'] == 'APPLIED'
    assert repeated.data['canonical_ids'] == applied['canonical_ids']
    fresh = run(lambda: analyze_ecu_transfer({'source_hardware_id': source, 'target_hardware_ids': [target]}))['targets'][0]
    assert all(item['action'] == 'reuse' for item in fresh['items']), [(item['object_type'], item['recommended_name'], item['action'], item.get('reason')) for item in fresh['items']]
    reuse_args = tool.input_model.model_validate({**args, 'transfer_proposal_id': fresh['proposal_id']}).model_dump()
    reused = execute(authority, tool.name, tool.permission, reuse_args, tool.handler)
    assert reused.success, reused.findings
    assert reused.data['agent_response']['metadata']['model_changed'] is False
    assert len(reused.data['agent_response']['metadata']['canonical_ids']) == 4
    root_item = next(item for item in fresh['items'] if item['object_type'] == 'Function')
    skipped_args = {**reuse_args, 'decisions': [{'plan_key': root_item['plan_key'], 'action': 'skip'}]}
    skipped = execute(authority, tool.name, tool.permission, skipped_args, tool.handler)
    assert skipped.success, skipped.findings
    assert len(skipped.data['agent_response']['metadata']['skipped_plan_keys']) == 4
    assert len(run(lambda: list_objects('Signal'))) == 2
