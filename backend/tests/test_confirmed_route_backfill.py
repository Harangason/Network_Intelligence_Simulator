"""Only evidence-backed missing transports are eligible for backfill."""
from backend.engineering.confirmed_routes import confirmed_route_candidates, route_keys, repair_confirmed_routes
from backend.tests.test_model_ownership import db_project, _chain


def test_candidates_use_confirmed_owners_consumers_and_existing_hmi_pairs_without_duplicates():
    hardware = [{"id": "sensor", "name": "Sensor", "device_type": "SensorController", "version": 1,
                 "identity": {"system_owner_id": "ecu"}},
                {"id": "act", "name": "Actuator", "device_type": "ActuatorController", "version": 1,
                 "identity": {"system_owner_id": "ecu"}},
                {"id": "ecu", "name": "Controller", "device_type": "ECU", "version": 1},
                {"id": "hmi", "name": "Display", "device_type": "ECU", "version": 1},
                {"id": "other", "name": "UnassignedECU", "device_type": "ECU", "version": 1}]
    interfaces = [{"id": key + "-if", "hardware_node_id": key} for key in ("sensor", "act", "ecu", "hmi", "other")]
    messages = [{"id": key, "name": key, "interface_id": owner + "-if", "direction": "tx"}
                for key, owner in (("measure", "sensor"), ("feedback", "act"), ("status", "ecu"), ("status2", "ecu"), ("unknown", "other"))]
    messages.append({"id": "command", "name": "command", "interface_id": "ecu-if", "direction": "tx",
                     "configuration": {"transport_unit": {"consumer_refs": ["act"]}}})
    signals = [{"id": "measure-signal", "message_id": "measure"}]
    routes = [{"id": "sensor-route", "source": {"node_id": "sensor"}, "destinations": [{"node_id": "ecu"}], "payload": {"signal_ids": ["measure-signal"]}, "approval_state": "APPROVED", "validation": {"valid": True}},
              {"id": "hmi-route", "source": {"node_id": "ecu", "interface_id": "ecu-if"}, "destinations": [{"node_id": "hmi"}], "payload": {"message_id": "status"}, "approval_state": "APPROVED", "validation": {"valid": True}}]
    plan = confirmed_route_candidates(hardware, interfaces, messages, signals, routes, [])
    keys = {(row["source_id"], row["target_id"], row["message_id"]) for row in plan["candidates"]}
    assert keys == {("act", "ecu", "feedback"), ("ecu", "act", "command"), ("ecu", "hmi", "status2")}
    assert [row["message_id"] for row in plan["unconfirmed_messages"]] == ["unknown"]
    assert ("sensor", "ecu", "measure") in route_keys(routes, signals)


def test_backfill_preview_apply_and_retry_are_idempotent(db_project):
    from backend.engineering.repository import create_object, update_object
    from backend.engineering.agent_tools import model

    sensor, _port, _interface, message, _signal = _chain()
    ecu = create_object("HardwareNode", {"name": "Controller", "device_type": "ECU", "device_class": 4})
    create_object("HardwareNetworkInterface", {"name": "ControllerCAN", "hardware_node_id": str(ecu["id"]), "technology": "CAN_FD"})
    function = create_object("Function", {"name": "Control", "hardware_node_id": str(ecu["id"])})
    create_object("Interface", {"name": "ControlData", "function_id": str(function["id"]), "interface_type": "CAN_FD"})
    update_object("HardwareNode", str(sensor["id"]), {"identity": {"system_owner_id": str(ecu["id"])}})
    preview = repair_confirmed_routes(db_project)
    assert preview["new_route_count"] == 1 and not preview["invalid"]
    assert not model.routes()
    applied = repair_confirmed_routes(db_project, apply=True)
    assert applied["applied"] and applied["new_route_count"] == 1
    assert applied["after"]["complete"]
    assert len(model.routes()) == 1
    assert model.routes()[0]["approval_state"] == "APPROVED"
    repeated = repair_confirmed_routes(db_project, apply=True)
    assert repeated["new_route_count"] == 0 and not repeated["applied"]
    assert len(model.routes()) == 1
