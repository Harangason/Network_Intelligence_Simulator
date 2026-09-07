from backend.engineering.assignment_learning import collect_assignment_suggestions


def test_previous_wizard_graph_is_retrieved_for_a_new_project():
    rows = [{
        "project_id": "previous-project",
        "context": {
            "agent_wizard_status": {
                "system_cluster_assignments": [{
                    "selected": True,
                    "tree": [{
                        "name": "Motorsteuerung",
                        "sensors": [{"name": "EngineSpeed"}],
                        "actuators": [],
                    }],
                }],
            },
        },
    }]
    result = collect_assignment_suggestions(
        rows,
        [{"name": "EngineSpeed-2", "device_type": "SensorController"}],
        ["Motorsteuerung", "Diagnose"],
        "automotive",
    )

    assert result["corpus_projects"] == 1
    assert result["suggestions"][0]["controller_name"] == "Motorsteuerung"
    assert result["suggestions"][0]["source_projects"] == ["previous-project"]


def test_explicit_correction_outweighs_an_older_generated_assignment():
    rows = [{
        "project_id": "old-project",
        "context": {"agent_wizard_status": {"system_cluster_assignments": [{
            "selected": True,
            "tree": [{"name": "Diagnose", "sensors": ["EngineSpeed"], "actuators": []}],
        }]}},
    }, {
        "project_id": "review-project",
        "context": {"equipment_assignment_feedback": [
            {"endpoint_name": "EngineSpeed", "controller_name": "Diagnose", "accepted": False, "domain": "automotive"},
            {"endpoint_name": "EngineSpeed", "controller_name": "Motorsteuerung", "accepted": True, "domain": "automotive"},
        ]},
    }]
    result = collect_assignment_suggestions(
        rows,
        [{"name": "EngineSpeed"}],
        ["Motorsteuerung", "Diagnose"],
        "automotive",
    )

    assert result["suggestions"][0]["controller_name"] == "Motorsteuerung"
