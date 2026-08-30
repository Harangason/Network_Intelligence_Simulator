from collections import Counter

import pytest

from backend.engineering.models import EngineeringValidationError
from backend.engineering import structure_transfer
from backend.engineering.structure_transfer import _merge_transfer_decisions, _target_plan, analyze_system_duplicates


def test_target_plan_reuses_semantic_duplicates_and_creates_only_missing_children():
    source_hardware = {
        "id": "source-hardware",
        "object_type": "HardwareNode",
        "name": "Thermal-ECU",
    }
    target_hardware = {
        "id": "target-hardware",
        "object_type": "HardwareNode",
        "name": "Temperatur-ECU",
    }
    source_function = {
        "id": "source-function",
        "object_type": "Function",
        "name": "ThermalECU_Steuerung",
        "hardware_node_id": "source-hardware",
    }
    target_function = {
        "id": "target-function",
        "object_type": "Function",
        "name": "Temperatur ECU Control",
        "hardware_node_id": "target-hardware",
    }
    source_interface = {
        "id": "source-interface",
        "object_type": "Interface",
        "name": "ThermalECU_CAN_FD",
        "function_id": "source-function",
    }
    objects = {
        "HardwareNode": [source_hardware, target_hardware],
        "Function": [source_function, target_function],
        "Interface": [source_interface],
        "Message": [],
        "Signal": [],
    }
    by_id = {item["id"]: item for group in objects.values() for item in group}
    children = {("Function", "target-hardware"): [target_function]}

    plan = _target_plan(
        source_hardware,
        target_hardware,
        objects,
        by_id,
        children,
        Counter(),
        Counter(),
    )

    assert plan[0]["action"] == "reuse"
    assert plan[0]["target_id"] == "target-function"
    assert plan[1]["action"] == "create"
    assert plan[1]["target_parent_id"] == "target-function"
    assert plan[1]["recommended_name"] == "TemperaturECU_CAN_FD"


def test_target_plan_does_not_merge_unrelated_ecu_domains_by_generic_role():
    source_hardware = {"id": "source", "object_type": "HardwareNode", "name": "Abgasnachbehandlung-ECU"}
    target_hardware = {"id": "target", "object_type": "HardwareNode", "name": "Airbag-ECU"}
    source_function = {
        "id": "source-function",
        "object_type": "Function",
        "name": "AbgasnachbehandlungECU_Steuerung",
        "hardware_node_id": "source",
    }
    target_function = {
        "id": "target-function",
        "object_type": "Function",
        "name": "AirbagECU_Steuerung",
        "hardware_node_id": "target",
    }
    objects = {
        "HardwareNode": [source_hardware, target_hardware],
        "Function": [source_function, target_function],
        "Interface": [],
        "Message": [],
        "Signal": [],
    }
    by_id = {item["id"]: item for group in objects.values() for item in group}

    plan = _target_plan(
        source_hardware,
        target_hardware,
        objects,
        by_id,
        {("Function", "target"): [target_function]},
        Counter(),
        Counter(),
    )

    assert plan[0]["action"] == "create"
    assert plan[0]["suggested_action"] == "create"
    assert plan[0]["target_id"] is None
    assert plan[0]["recommended_name"] == "AirbagECU_Steuerung"
    assert plan[0]["similarity"] < 0.78
    assert "fachlicher Elternkontext" in plan[0]["reason"]


def test_transfer_decisions_can_replace_reuse_with_create_or_skip():
    item = {
        "plan_key": "Function:source-function",
        "action": "reuse",
        "target_id": "target-function",
        "target_name": "AirbagECU_Steuerung",
        "recommended_name": "AirbagECU_Steuerung",
    }

    create = _merge_transfer_decisions(
        [item],
        [{"plan_key": item["plan_key"], "action": "create", "recommended_name": "Airbag_Airbagsteuerung"}],
    )[0]
    skipped = _merge_transfer_decisions([item], [{"plan_key": item["plan_key"], "action": "skip"}])[0]

    assert create["suggested_action"] == "reuse"
    assert create["action"] == "create"
    assert create["recommended_name"] == "Airbag_Airbagsteuerung"
    assert create["target_id"] is None
    assert skipped["action"] == "skip"
    assert skipped["target_id"] is None

    with pytest.raises(EngineeringValidationError, match="Unbekannte Transferposition"):
        _merge_transfer_decisions([item], [{"plan_key": "Function:unknown", "action": "skip"}])


def test_system_duplicate_analysis_recognizes_adas_synonym_but_not_airbag(monkeypatch):
    hardware = [
        {"id": "driver", "object_type": "HardwareNode", "name": "Fahrerassistenz-ECU", "device_type": "ECU", "domain": "automotive"},
        {"id": "adas", "object_type": "HardwareNode", "name": "ADAS", "device_type": "ECU", "domain": "automotive"},
        {"id": "exhaust", "object_type": "HardwareNode", "name": "Abgasnachbehandlung-ECU", "device_type": "ECU", "domain": "automotive"},
        {"id": "airbag", "object_type": "HardwareNode", "name": "Airbag-ECU", "device_type": "ECU", "domain": "automotive"},
    ]
    functions = [
        {"id": "adas-function", "object_type": "Function", "name": "Radarverarbeitung", "hardware_node_id": "adas"},
        {"id": "exhaust-function", "object_type": "Function", "name": "AbgasnachbehandlungECU_Steuerung", "hardware_node_id": "exhaust"},
        {"id": "airbag-function", "object_type": "Function", "name": "AirbagECU_Steuerung", "hardware_node_id": "airbag"},
    ]
    objects = {
        "HardwareNode": hardware,
        "Function": functions,
        "Interface": [],
        "Message": [],
        "Signal": [],
    }
    by_id = {item["id"]: item for group in objects.values() for item in group}
    children = {
        ("Function", "adas"): [functions[0]],
        ("Function", "exhaust"): [functions[1]],
        ("Function", "airbag"): [functions[2]],
    }
    monkeypatch.setattr(structure_transfer, "_load_graph", lambda: (objects, by_id, children))

    result = analyze_system_duplicates()

    assert result["count"] == 1
    assert result["items"][0]["canonical_hardware"]["id"] == "adas"
    assert result["items"][0]["duplicate_hardware"]["id"] == "driver"
    assert result["items"][0]["name_similarity"] == 1.0

    hardware[0]["lifecycle_state"] = "superseded"
    assert analyze_system_duplicates()["count"] == 0
