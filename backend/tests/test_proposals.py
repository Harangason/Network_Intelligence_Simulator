from __future__ import annotations

from backend.engineering import proposals, repository


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


def test_hardware_resolution_reuses_controlled_system_synonym(monkeypatch):
    monkeypatch.setattr(
        repository,
        "list_objects",
        lambda object_type, **_kwargs: (
            [
                {
                    "id": SOURCE,
                    "name": "ADAS",
                    "device_type": "ECU",
                    "domain": "automotive",
                    "review_state": "reviewed",
                    "approval_state": "approved",
                },
                {
                    "id": TARGET,
                    "name": "Airbag-ECU",
                    "device_type": "ECU",
                    "domain": "automotive",
                },
            ]
            if object_type == "HardwareNode"
            else [{"id": "function-1"}]
        ),
    )

    resolution = repository.find_equivalent_hardware_node(
        {"name": "Fahrerassistenz-ECU", "device_type": "ECU", "domain": "automotive"}
    )
    unrelated = repository.find_equivalent_hardware_node(
        {"name": "Abgasnachbehandlung-ECU", "device_type": "ECU", "domain": "automotive"}
    )

    assert resolution is not None
    assert resolution["hardware"]["id"] == SOURCE
    assert resolution["similarity"] == 1.0
    assert resolution["child_count"] == 1
    assert unrelated is None


def test_hardware_resolution_prefers_the_populated_canonical_system(monkeypatch):
    hardware = [
        {
            "id": SOURCE,
            "name": "ADAS",
            "device_type": "ECU",
            "domain": "automotive",
            "review_state": "reviewed",
            "approval_state": "approved",
        },
        {
            "id": TARGET,
            "name": "Fahrerassistenz-ECU",
            "device_type": "ECU",
            "domain": "automotive",
            "review_state": "reviewed",
            "approval_state": "approved",
        },
    ]

    def list_objects(object_type, **kwargs):
        if object_type == "HardwareNode":
            return hardware
        parent_id = str((kwargs.get("filters") or {}).get("hardware_node_id") or "")
        return [{"id": f"function-{index}"} for index in range(4 if parent_id == SOURCE else 0)]

    monkeypatch.setattr(repository, "list_objects", list_objects)

    resolution = repository.find_equivalent_hardware_node(
        {"name": "Driver Assistance ECU", "device_type": "ECU", "domain": "automotive"}
    )

    assert resolution is not None
    assert resolution["hardware"]["id"] == SOURCE
    assert resolution["child_count"] == 4


def test_proposal_approval_reuses_semantic_hardware_without_creating_duplicate(monkeypatch):
    proposal = {
        "proposal_id": "proposal-1",
        "status": "READY_FOR_REVIEW",
        "target_object": {"resource": "hardware-nodes"},
        "prompt": "Projektanlage",
        "model": "pytest",
        "evidence": [],
        "proposed_objects": [
            {
                "object_type": "HardwareNode",
                "resource": "hardware-nodes",
                "name": "Fahrerassistenz-ECU",
                "device_type": "ECU",
                "domain": "automotive",
            }
        ],
    }
    state = dict(proposal)

    monkeypatch.setattr(proposals, "get_proposal", lambda _proposal_id: dict(state))
    monkeypatch.setattr(
        proposals,
        "_resolve_or_create_object",
        lambda _object_type, _payload: (
            {"id": SOURCE, "name": "ADAS"},
            {
                "hardware": {"id": SOURCE, "name": "ADAS"},
                "similarity": 1.0,
                "reason": "kontrolliertes Fachsynonym",
            },
        ),
    )

    def fake_update(_proposal_id, **changes):
        for key in ("proposed_objects", "validation_results", "status"):
            if changes.get(key) is not None:
                state[key] = changes[key]
        return dict(state)

    monkeypatch.setattr(proposals, "_update_proposal_row", fake_update)

    approved = proposals.approve_proposal("proposal-1", actor="engineering-chat-agent")
    item = approved["proposed_objects"][0]

    assert approved["status"] == "APPROVED"
    assert item["canonical_id"] == SOURCE
    assert item["canonical_resolution"] == {
        "strategy": "semantic_hardware_reuse",
        "requested_name": "Fahrerassistenz-ECU",
        "canonical_name": "ADAS",
        "similarity": 1.0,
        "reason": "kontrolliertes Fachsynonym",
    }
