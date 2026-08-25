from __future__ import annotations

from backend.engineering import proposals


SOURCE = "00000000-0000-0000-0000-000000000001"
TARGET = "00000000-0000-0000-0000-000000000002"


def test_object_proposal_validation_accepts_industry_neutral_hardware():
    proposal = {
        "target_object": {"resource": "hardware-nodes"},
        "proposed_objects": [{"name": "Flight Controller", "device_type": "FlightComputer", "domain": "aerospace"}],
    }

    assert proposals.validate_proposed_items(proposal) == [
        {"index": 0, "object_type": "HardwareNode", "valid": True, "errors": []}
    ]


def test_relation_proposal_validation_checks_endpoints_without_mutation(monkeypatch):
    observed = []
    monkeypatch.setattr(proposals, "get_object", lambda object_type, object_id: observed.append((object_type, object_id)) or {"id": object_id})
    proposal = {
        "target_object": {},
        "proposed_objects": [
            {
                "object_type": "Relation",
                "relation_type": "COMMUNICATES_WITH",
                "source_type": "HardwareNode",
                "source_id": SOURCE,
                "target_type": "HardwareNode",
                "target_id": TARGET,
            }
        ],
    }

    result = proposals.validate_proposed_items(proposal)

    assert result[0]["valid"] is True
    assert observed == [("HardwareNode", SOURCE), ("HardwareNode", TARGET)]


def test_invalid_proposal_remains_reviewable_instead_of_auto_approving():
    proposal = {
        "target_object": {"resource": "signals"},
        "proposed_objects": [{"name": "BatteryVoltage"}],
    }

    result = proposals.validate_proposed_items(proposal)

    assert result[0]["valid"] is False
    assert "message_id" in result[0]["errors"][0]
