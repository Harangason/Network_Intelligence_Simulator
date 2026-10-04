from backend.tests.native_transport_fixtures import lin_design, ethernet_mac
from backend.nis.agent.tools import proposal_service as proposal_service
import pytest


@pytest.mark.parametrize('technology', ['I2C', 'ModbusRTU', 'ModbusTCP', 'SPI', 'GPIO', 'CAN_FD'])
def test_named_network_preserves_registered_technology(technology):
    from backend.nis.agent.tools.wizard_generation import _network_protocol
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    protocol = _network_protocol(technology)
    assert DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(protocol) == DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(technology)
    result = proposal_service._validate_changes([{
        'object_type': 'Network', 'action': 'CREATE', 'local_ref': 'network',
        'data': {'id': 'local-control', 'technology': protocol},
    }])
    assert result['valid'], result


def test_unknown_network_technology_is_not_accepted():
    result = proposal_service._validate_changes([{
        'object_type': 'Network', 'action': 'CREATE', 'local_ref': 'network',
        'data': {'id': 'local-control', 'technology': 'UnspecifiedBus'},
    }])
    assert not result['valid']
    assert any('Unbekannte Netzwerktechnologie' in finding['message'] for finding in result['findings'])


def test_wizard_scale_proposal_exceeds_the_old_2000_change_ceiling(monkeypatch):
    captured = {}

    def fake_create(payload):
        captured["payload"] = payload
        return {"proposal_id": "large-proposal"}

    def fake_write(proposal_id, contract, **_kwargs):
        return {"proposal_id": proposal_id, "changes": contract["changes"]}

    monkeypatch.setattr(proposal_service.legacy, "create_proposal", fake_create)
    monkeypatch.setattr(proposal_service, "_write", fake_write)
    changes = [
        {"object_type": "Network", "data": {"id": f"network-{index}", "technology": "CAN_FD"}}
        for index in range(3000)
    ]

    proposal = proposal_service.create("WIZARD_ENGINEERING_MODEL", changes, "large wizard model")

    assert len(proposal["changes"]) == 3000
    assert len(captured["payload"]["proposed_objects"]) == 3000

@pytest.mark.parametrize('technology,confirmed,network,expected', [
    ('LIN', {'technology': 'CAN', 'bitrate': 500000}, {}, True),
    ('LIN', {'technology': 'LIN', 'protocol': 'CAN', 'bitrate': 500000}, {}, True),
    ('LIN', {'technology': 'CAN', 'networks': [{'id': 'bus', 'technology': 'LIN', 'protocol': 'CAN', 'bitrate': 500000}]}, {}, True),
    ('LIN', {'technology': 'CAN', 'networks': [{'id': 'bus', 'technology': 'CAN', 'bitrate': 500000}]}, {}, True),
    ('LIN', {'technology': 'CAN', 'networks': [{'id': 'bus', 'technology': 'unknown', 'bitrate': 500000}]}, {}, True),
    ('LIN', {'technology': 'CAN', 'networks': [{'id': 'bus', 'technology': 'LIN', **lin_design(), 'bitrate': 19200}]}, {}, False),
    ('LIN', {}, {'technology': 'CAN', 'bitrate': 500000}, True),
    ('LIN', {}, {'technology': 'LIN', **lin_design(), 'bitrate': 19200}, False),
    ('CAN_FD', {'technology': 'CAN_FD', 'arbitration_bitrate': 500000}, {}, True),
    ('CAN_FD', {'technology': 'CAN_FD', 'arbitration_bitrate': 500000, 'data_bitrate': 2000000}, {}, False),
    ('Ethernet', {'technology': 'Ethernet', **ethernet_mac(), 'bitrate': 100000000}, {}, False),
])
def test_proposal_capacity_resolves_only_matching_confirmed_rates(monkeypatch, technology, confirmed, network, expected):
    from backend.nis.agent.tools import validation as validation
    from backend.nis.workflow.services.service import WorkflowStatusService
    node = {'id': 'ecu', 'name': 'Motor', 'device_type': 'ECU'}
    port = {'id': 'port', 'name': 'MotorPort', 'hardware_node_id': 'ecu', 'technology': technology, 'network_ref': 'bus', 'bitrate': None}
    message = {'id': 'message', 'name': 'Moment', 'interface_id': 'logical', 'hardware_interface_id': 'port', 'dlc': 1, 'cycle_ms': 100}
    logical = {'id': 'logical', 'hardware_node_id': 'ecu', 'interface_type': technology}
    rows = {'HardwareNode': [node], 'HardwareNetworkInterface': [port], 'Message': [message], 'Interface': [logical]}
    monkeypatch.setattr(validation, 'objects', lambda kind: rows.get(kind, []))
    monkeypatch.setattr(validation, 'networks', lambda: [{'id': 'bus', 'technology': technology, **network}])
    monkeypatch.setattr(WorkflowStatusService, 'get', lambda self: {'parameters': confirmed, 'context': {}})
    findings = validation.validate_effective_model([{'action': 'UPDATE', 'object_type': 'HardwareNetworkInterface', 'object_id': 'port', 'data': {}}])
    capacity = [finding for finding in findings if finding.get('code') == 'CAPACITY_UNVERIFIED']
    assert bool(capacity) is expected
    if expected:
        assert capacity[0]['object_name'] == 'MotorPort' and capacity[0]['node_name'] == 'Motor'
        assert capacity[0]['missing_fields'] and capacity[0]['repair_action'] == 'REVIEW_TECHNOLOGY_PARAMETERS'
        if technology == 'CAN_FD':
            assert capacity[0]['missing_fields'] == ['data_bitrate']
