"""Ownership contracts across generator, structure edits and migration."""
import os
from uuid import uuid4

import pytest

from backend.engineering.system_ownership import confirmed_system_owner_plan, migrate_confirmed_system_owners


def test_confirmed_plan_preserves_explicit_ownership_and_rejects_ambiguous_names():
    hardware = [
        {"id": "ecu", "name": "Exhaust", "device_type": "ECU", "version": 1},
        {"id": "sensor", "name": "EGRValvePosition", "device_type": "SensorController", "version": 2, "identity": {"serial": "keep"}},
    ]
    evidence = [{"endpoint_name": "EGRValvePosition", "controller_name": "Exhaust", "accepted": True}]
    plan = confirmed_system_owner_plan(hardware, evidence)
    assert plan["count"] == 1
    assert plan["changes"][0]["identity"]["serial"] == "keep"
    hardware[1]["identity"] = plan["changes"][0]["identity"]
    assert confirmed_system_owner_plan(hardware, evidence)["count"] == 0
    hardware[1]["identity"]["system_owner_id"] = "manual-choice"
    assert confirmed_system_owner_plan(hardware, evidence)["skipped"][0]["reason"] == "Explizite Zuordnung bleibt erhalten"
    hardware[1]["identity"] = {}
    assert confirmed_system_owner_plan(hardware + [{**hardware[0], "id": "duplicate"}], evidence)["count"] == 0
    assert confirmed_system_owner_plan(hardware, evidence + [{**evidence[0], "accepted": False}])["count"] == 0


@pytest.fixture
def db_project(monkeypatch):
    url = os.environ.get("ENGINEERING_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated ENGINEERING_TEST_DATABASE_URL required")
    monkeypatch.setenv("DATABASE_URL", url)
    from backend.engineering.project_context import activate_project, reset_project
    from backend.engineering.db import close_pool
    close_pool()
    project = f"pytest-model-ownership-{uuid4()}"
    token = activate_project(project)
    try:
        yield project
    finally:
        reset_project(token)
        close_pool()


def _chain():
    from backend.engineering.repository import create_object
    sensor = create_object("HardwareNode", {"name": "EGRValvePosition", "device_type": "SensorController", "device_class": 1})
    port = create_object("HardwareNetworkInterface", {"name": "SensorCAN", "hardware_node_id": str(sensor["id"]), "technology": "CAN_FD"})
    interface = create_object("Interface", {"name": "Measurement", "hardware_node_id": str(sensor["id"]), "interface_type": "CAN_FD"})
    message = create_object("Message", {"name": "PositionData", "interface_id": str(interface["id"]), "hardware_interface_id": str(port["id"]), "dlc": 8, "cycle_ms": 20})
    signal = create_object("Signal", {"name": "AGRVentilstellung", "message_id": str(message["id"]), "start_bit": 0, "length_bits": 8, "byte_order": "little_endian", "data_type": "unsigned"})
    return sensor, port, interface, message, signal


def test_structure_wizard_accepts_direct_sensor_without_function(db_project):
    from backend.engineering.structure import evaluate_structure, apply_structure
    from backend.engineering.repository import get_object
    sensor, _port, interface, message, signal = _chain()
    selections = {"HardwareNode": [str(sensor["id"])], "Function": [], "Interface": [str(interface["id"])], "Message": [str(message["id"])], "Signal": [str(signal["id"])]}
    evaluation = evaluate_structure({"selections": selections})
    assignment = next(item for item in evaluation["suggestions"] if item["child_type"] == "Interface")
    assert assignment["parent_type"] == "HardwareNode"
    assert assignment["parent_field"] == "hardware_node_id"
    apply_structure({"assignments": evaluation["suggestions"]})
    assert get_object("Interface", str(interface["id"]))["function_id"] is None
    assert str(get_object("Signal", str(signal["id"]))["message_id"]) == str(message["id"])


def test_reparent_keeps_physical_bindings_and_rejects_cross_hardware_move(db_project):
    from backend.engineering.repository import create_object, update_object, get_object
    from backend.engineering.models import EngineeringValidationError
    from backend.engineering.relations import list_relations
    sensor, _port, interface, _message, _signal = _chain()
    legacy_function = create_object("Function", {"name": "OldFunction", "hardware_node_id": str(sensor["id"])})
    parented = update_object("Interface", str(interface["id"]), {"function_id": str(legacy_function["id"])})
    direct = update_object("Interface", str(interface["id"]), {"function_id": None, "expected_version": parented["version"]})
    assert direct["function_id"] is None
    links = list_relations(object_type="Interface", object_id=str(interface["id"]), relation_type="HAS_INTERFACE")
    assert len(links) == 1
    assert links[0]["source_type"] == "HardwareNode"
    ecu = create_object("HardwareNode", {"name": "Exhaust", "device_type": "ECU", "device_class": 4})
    function = create_object("Function", {"name": "Control", "hardware_node_id": str(ecu["id"])})
    with pytest.raises(EngineeringValidationError, match="vollständige Nachrichten-/Portzuordnung"):
        update_object("Interface", str(interface["id"]), {"function_id": str(function["id"])})
    assert str(get_object("Interface", str(interface["id"]))["hardware_node_id"]) == str(sensor["id"])


def test_migration_is_dry_run_by_default_and_idempotent(db_project):
    from backend.engineering.repository import create_object, get_object
    from backend.engineering.assignment_learning import EquipmentAssignmentLearningService
    from backend.engineering.system_clusters import system_owners
    from backend.engineering.workflow.service import WorkflowStatusService
    sensor, _port, _interface, _message, _signal = _chain()
    ecu = create_object("HardwareNode", {"name": "Abgasnachbehandlung", "device_type": "ECU", "device_class": 4})
    WorkflowStatusService(db_project).save_topology({"nodes": [
        {"id": "sensor-node", "engineeringId": str(sensor["id"]), "name": sensor["name"], "kind": "sensor", "ports": []},
        {"id": "ecu-node", "engineeringId": str(ecu["id"]), "name": ecu["name"], "kind": "ecu", "ports": []},
    ], "edges": []})
    EquipmentAssignmentLearningService(db_project).record({"records": [{"endpoint_name": sensor["name"], "controller_name": ecu["name"], "accepted": True}]})
    plan = migrate_confirmed_system_owners(db_project)
    assert plan["count"] == 1 and plan["applied"] is False
    assert plan["topology_changes"] == [{"node_id": "sensor-node", "owner_id": str(ecu["id"])}]
    assert not get_object("HardwareNode", str(sensor["id"]))["identity"].get("system_owner_id")
    assert migrate_confirmed_system_owners(db_project, apply=True)["count"] == 1
    migrated = get_object("HardwareNode", str(sensor["id"]))
    assert migrated["identity"]["system_owner_id"] == str(ecu["id"])
    assert migrate_confirmed_system_owners(db_project, apply=True)["count"] == 0
    topology = WorkflowStatusService(db_project).get()["topology"]
    assert topology["nodes"][0]["systemOwnerId"] == str(ecu["id"])
    assert get_object("HardwareNode", str(sensor["id"]))["version"] == migrated["version"]
    migrated["name"] = "RenamedWithoutSemanticClue"
    assert system_owners([migrated, ecu], {})[str(sensor["id"])]["id"] == str(ecu["id"])


def test_topology_sync_preserves_canonical_owner_when_wiring_changes(monkeypatch):
    from backend.engineering import api
    hardware = [
        {"id": "sensor", "name": "EGRValvePosition", "device_type": "SensorController", "identity": {"system_owner_id": "owner", "system_owner_source": "wizard-confirmed"}},
        {"id": "owner", "name": "Abgasnachbehandlung", "device_type": "ECU"},
        {"id": "neighbor", "name": "OtherController", "device_type": "ECU"},
    ]
    monkeypatch.setattr(api, "list_objects", lambda *_args, **_kwargs: hardware)
    topology = {"nodes": [{"id": item["id"], "engineeringId": item["id"], "name": item["name"], "kind": "sensor" if item["id"] == "sensor" else "ecu", "ports": []} for item in hardware],
                "edges": [{"id": "wire", "source": "sensor", "target": "neighbor"}]}
    output = api._topology_with_engineering_links(topology, {})
    assert output["nodes"][0]["systemOwnerId"] == "owner"


@pytest.mark.parametrize('explicit_command', [False, True])
def test_generated_owner_local_references_are_resolved_on_apply(db_project, explicit_command):
    from backend.engineering.agent_tools import wizard_generation, proposal_service, model
    prompt = '''- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd)
- Hardware-Sollwerte: {"gateways":1,"ecus":1,"sensors":1,"actuators":1}
- Systemcluster-Graph: [{"network_id":"can_fd","bus_name":"Drive","controllers":[{"ecu":"Motorsteuerung","sensors":["MotorTemperature"],"actuators":["MotorValve"]}]}]
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge ein Netzwerk mit einem Gateway, einer Motorsteuerung, einem Temperatursensor und einem Stellglied.
'''
    if explicit_command:
        # Ownership does not define an actuator's command encoding. A valid
        # apply fixture must supply that independent, explicit user contract.
        prompt = ('- Aktor-Befehle: {"MotorValve":{"length_bits":1,"data_type":"boolean",'
                  '"factor":1,"unit":"code","min_value":0,"max_value":1,'
                  '"semantic":{"semantic_type":"BOOLEAN"},'
                  '"data":{"enum_values":{"CLOSE":0,"OPEN":1}}}}\n' + prompt)
    proposal = wizard_generation.generate({"prompt": prompt})
    proposal = proposal_service.validate(proposal["proposal_id"])
    if not explicit_command:
        assert not proposal['validation_result']['valid']
        assert any(finding.get('code') == 'COMMAND_SIGNALS_MISSING'
                   for finding in proposal['validation_result']['findings'])
        assert not model.objects('HardwareNode'), 'An incomplete command proposal must not create canonical devices.'
        return
    assert proposal["validation_result"]["valid"], proposal["validation_result"]
    approved = proposal_service.review(proposal["proposal_id"], revision=proposal["revision"], decision="approve", actor="test-human", trace_id=str(uuid4()))
    proposal_service.apply(approved["proposal_id"], actor="test-human", trace_id=str(uuid4()))
    nodes = {node["name"]: node for node in model.objects("HardwareNode")}
    for name in ("MotorTemperature", "MotorValve"):
        assert nodes[name]["identity"]["system_owner_id"] == str(nodes["Motorsteuerung"]["id"])
