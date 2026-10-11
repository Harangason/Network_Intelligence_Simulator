import pytest
from backend.engineering.agent_tools.proposal_service import order_change_dependencies, _resolve
from backend.engineering.models import EngineeringValidationError


def test_nested_transmit_bindings_are_available_before_message_apply():
    changes = [
        {'local_ref': 'message', 'data': {'hardware_interface_id': '$port1',
            'configuration': {'physical_transmit_bindings': [{'hardware_interface_id': '$port2'}]}}},
        {'local_ref': 'port1', 'data': {'hardware_node_id': '$device'}},
        {'local_ref': 'device', 'data': {'name': 'ECU'}},
        {'local_ref': 'port2', 'data': {'hardware_node_id': '$device'}},
    ]
    resolved = {}
    for change in order_change_dependencies(changes):
        _resolve(change['data'], resolved)
        resolved[change['local_ref']] = change['local_ref'] + '-canonical'
    assert len(resolved) == 4


@pytest.mark.parametrize('changes', [
    [{'local_ref': 'a', 'data': {'nested': ['$missing']}}],
    [{'local_ref': 'a', 'data': {'parent': '$b'}}, {'local_ref': 'b', 'data': {'parent': '$a'}}],
    [{'local_ref': 'a', 'data': {}}, {'local_ref': 'a', 'data': {}}],
])
def test_invalid_dependencies_are_rejected_before_review(changes):
    with pytest.raises(EngineeringValidationError):
        order_change_dependencies(changes)
