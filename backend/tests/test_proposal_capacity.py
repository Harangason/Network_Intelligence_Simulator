from backend.engineering.agent_tools import proposal_service


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
