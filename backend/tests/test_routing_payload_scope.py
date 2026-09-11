from copy import deepcopy
import pytest
from backend.engineering.routing.payload_scope import message_scope, scope_allows, payload_scope_issues
from backend.engineering.models import EngineeringValidationError


def local_message(role="MEASUREMENT"):
    return {"id": "local", "name": "Local I/O", "dlc": 2, "cycle_ms": 20,
        "configuration": {"communication_contract": {"role": role, "consumer_refs": ["controller"]}}}


def test_function_boundary_is_not_inferred_from_technology_or_names():
    message = local_message()
    scope = message_scope(message)
    assert scope_allows(scope, {"node_id": "controller"})
    assert not scope_allows(scope, {"node_id": "adas"})
    assert message_scope({**message, "name": "CAN-FD Function Status"}) == scope
    assert not message_scope({"name": "Thermometer LIN IO", "configuration": {}})["restricted"]
    assert not message_scope(local_message("DEVICE_STATUS"))["restricted"]


def test_explicit_standalone_sensor_and_function_receiver_identity():
    message = local_message()
    message["configuration"]["communication_contract"].update(scope="DEVICE_IO")
    assert scope_allows(message_scope(message), {"node_id": "adas"})
    message["configuration"]["communication_contract"].update(scope="LOCAL_IO", consumer_refs=["supervisor-function"])
    scope = message_scope(message)
    interfaces = {"rx": {"function_id": "supervisor-function"}, "other": {"function_id": "unrelated"}}
    assert scope_allows(scope, {"node_id": "ecu", "interface_id": "rx"}, interfaces)
    assert not scope_allows(scope, {"node_id": "ecu", "interface_id": "other"}, interfaces)


def test_generated_commands_and_signal_only_routes_cannot_bypass_boundary():
    message = {"id": "local", "name": "Command", "configuration": {"transport_unit": {
        "provenance": {"generator": "wizard-local-actuator-command"}, "consumer_refs": ["actuator"]}}}
    route = {"payload": {"signal_ids": ["signal"]}, "destinations": [{"node_id": "adas"}]}
    issues = payload_scope_issues(route, {"local": message}, {"signal": {"message_id": "local"}})
    assert [i["code"] for i in issues] == ["LOCAL_IO_RECIPIENT_MISMATCH"]
    route["destinations"] = [{"node_id": "actuator"}]
    assert not payload_scope_issues(route, {"local": message}, {"signal": {"message_id": "local"}})


def test_routing_validator_blocks_both_message_and_signal_selection():
    from backend.tests.test_routing import FakeValidator, MESSAGE, SIGNAL, route_payload
    message = local_message()
    validator = FakeValidator(message_bindings={MESSAGE: message})
    for payload in ({"message_id": MESSAGE, "signal_ids": []}, {"signal_ids": [SIGNAL]}):
        result = validator.validate(route_payload(payload=payload))
        assert "LOCAL_IO_RECIPIENT_MISMATCH" in {i["code"] for i in result["errors"]}


def test_approved_simulation_config_rechecks_scope_before_export(monkeypatch):
    from backend.engineering.routing import payload_scope, config_builder
    monkeypatch.setattr(payload_scope, "load_payload_context", lambda: ({"local": local_message()}, {}, {}))
    route = {"approval_state": "APPROVED", "payload": {"message_id": "local"}, "destinations": [{"node_id": "adas"}]}
    with pytest.raises(EngineeringValidationError, match="lokale Sensor"):
        config_builder.CommunicationConfigBuilder().build([route])


def test_capacity_counts_local_frame_only_on_local_bus_and_output_on_system_bus(monkeypatch):
    from backend.engineering.capacity import service as capacity
    from backend.engineering.workflow.models import default_statuses, default_versions
    command = local_message("COMMAND")
    command["configuration"]["communication_contract"]["consumer_refs"] = ["actuator"]
    status = {"id": "status", "name": "Function output", "dlc": 1, "cycle_ms": 20,
        "configuration": {"communication_contract": {"role": "DEVICE_STATUS"}}}
    def route(identifier, mid, destination, network, protocol):
        return {"id": identifier, "name": identifier, "approval_state": "APPROVED", "status": "APPROVED",
            "source": {"node_id": "controller", "network_id": network, "protocol": protocol},
            "destinations": [{"node_id": destination, "network_id": network, "protocol": protocol}],
            "payload": {"message_id": mid}, "route": {"gateways": []}, "timing": {"cycle_time_ms": 20}}
    rows = [route("local-route", "local", "actuator", "local-bus", "LIN"), route("output-route", "status", "adas", "system-bus", "CAN_FD")]
    objects = {"Message": [command, status], "HardwareNode": [{"id": "controller", "name": "Controller", "device_type": "ECU"}]}
    monkeypatch.setattr(capacity, "list_objects", lambda kind, **kw: deepcopy(objects.get(kind, [])))
    monkeypatch.setattr(capacity, "list_routes", lambda **kw: deepcopy(rows))
    service = capacity.CapacityTimingService("scope-test")
    monkeypatch.setattr(service.workflow, "get", lambda: {"project_id": "scope-test", "versions": default_versions(),
        "statuses": {k: "COMPLETE" for k in default_statuses()}, "parameters": {}, "topology": {}})
    monkeypatch.setattr(service, "latest", lambda: None)
    before = service.calculate(persist=False)
    rows.append(route("invalid-forward", "local", "adas", "system-bus", "CAN_FD"))
    after = service.calculate(persist=False)
    assert before["results"]["networks"] == after["results"]["networks"]
    assert {r["route_id"] for r in after["results"]["routes"]} == {"local-route", "output-route"}
    assert any(f["code"] == "LOCAL_IO_RECIPIENT_MISMATCH" and f["excluded_from_load"] for f in after["findings"])
