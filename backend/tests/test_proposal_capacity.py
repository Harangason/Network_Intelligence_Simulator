from backend.engineering.agent_tools import proposal_service
import pytest


@pytest.mark.parametrize('technology', ['I2C', 'ModbusRTU', 'ModbusTCP', 'SPI', 'GPIO', 'CAN_FD'])
def test_named_network_preserves_registered_technology(technology):
    from backend.engineering.agent_tools.wizard_generation import _network_protocol
    from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
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
