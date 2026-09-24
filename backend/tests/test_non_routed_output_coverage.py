"""Explicit transport exclusions do not hide missing local or authored paths."""
from copy import deepcopy

import pytest

from backend.engineering.simulation_coverage import assess_simulation, simulation_coverage
from backend.engineering.simulation import _apply_simulation_scope
from backend.tests.test_model_ownership import db_project, _chain


def output_configuration():
    return {"routing": {"enabled": False}, "communication_contract": {"scope": "FUNCTION_OUTPUT"}}


def inventory():
    return {"messages": [
        {"id": "local", "name": "HallMeasurement", "configuration": {"routing": {"enabled": False},
            "communication_contract": {"scope": "LOCAL_IO", "role": "MEASUREMENT"}}},
        {"id": "output", "name": "MotorCalculatedStatus", "configuration": output_configuration()},
    ], "signals": [{"id": "hall", "message_id": "local"},
                    {"id": "state", "message_id": "output"}, {"id": "error", "message_id": "output"}]}


def test_only_complete_unused_function_output_is_excluded_with_traceable_reason():
    model = inventory()
    before = deepcopy(model)
    coverage = simulation_coverage(**model, transports=[{"message_ids": ["local"]}])
    assert coverage["complete"]
    assert coverage["total_messages"] == 2 and coverage["total_signals"] == 3
    assert coverage["required_message_ids"] == ["local"] and coverage["required_signal_ids"] == ["hall"]
    assert coverage["excluded_message_ids"] == ["output"] and coverage["excluded_signal_ids"] == ["error", "state"]
    exclusion, = coverage["transport_exclusions"]
    assert exclusion["message_id"] == "output" and exclusion["message_name"] == "MotorCalculatedStatus"
    assert exclusion["signal_ids"] == ["error", "state"]
    assert exclusion["reason_code"] == "EXPLICIT_FUNCTION_OUTPUT_NOT_ROUTED"
    assert "keine funktionale Beobachtung" in exclusion["reason"]
    assert model == before


def test_confirmed_internal_controller_status_has_no_bus_transport_obligation():
    model = inventory()
    model['messages'][1]['configuration'] = {
        'routing': {'enabled': False},
        'communication_contract': {'scope': 'INTERNAL', 'role': 'INTERNAL_STATE', 'consumer_refs': []},
        'transport_unit': {'consumer_refs': [], 'provenance': {'generator': 'wizard-generation'}},
    }
    coverage = simulation_coverage(**model, transports=[{'message_ids': ['local']}])
    assert coverage['complete']
    assert coverage['excluded_message_ids'] == ['output']
    assert coverage['excluded_signal_ids'] == ['error', 'state']
    assert coverage['transport_exclusions'][0]['reason_code'] == 'INTERNAL_STATE_NOT_ROUTED'
    assert 'keine funktionale Beobachtung' in coverage['transport_exclusions'][0]['reason']


def test_internal_status_with_declared_export_still_requires_confirmed_transport():
    model = inventory()
    model['messages'][1]['configuration'] = {
        'routing': {'enabled': False},
        'communication_contract': {'scope': 'INTERNAL', 'role': 'INTERNAL_STATE', 'consumer_refs': []},
        'transport_unit': {'consumer_refs': [], 'provenance': {'generator': 'wizard-generation'}},
    }
    coverage = simulation_coverage(**model, transports=[{'message_ids': ['local']}],
                                   declared_transports=[{'payload': {'message_id': 'output'}, 'status': 'DRAFT'}])
    assert not coverage['complete']
    assert coverage['missing_message_ids'] == ['output']
    assert coverage['missing_signal_ids'] == ['error', 'state']


@pytest.mark.parametrize("config", [
    {}, {"routing": {"enabled": False}},
    *[{"routing": {"enabled": value}, "communication_contract": {"scope": "FUNCTION_OUTPUT"}}
      for value in (True, None, "false", 0)],
    *[{"routing": {"enabled": False}, "communication_contract": {"scope": scope}}
      for scope in ("LOCAL_IO", "DEVICE_IO", "UNKNOWN")],
    *[{"routing": {"enabled": False}, "communication_contract": {"scope": "FUNCTION_OUTPUT", "role": role}}
      for role in ("MEASUREMENT", "FEEDBACK", "COMMAND")],
    {**output_configuration(), "transport_unit": {"provenance": {"generator": "wizard-local-actuator-command"}}},
])
def test_missing_or_other_scope_and_local_semantics_never_exclude_transport(config):
    model = inventory()
    model["messages"][1]["configuration"] = config
    coverage = simulation_coverage(**model, transports=[{"message_ids": ["local"]}])
    assert not coverage["complete"] and coverage["missing_message_ids"] == ["output"]
    assert coverage["missing_signal_ids"] == ["error", "state"] and coverage["transport_exclusions"] == []


@pytest.mark.parametrize("disabled", [["state"], ["state", "error"]])
def test_signal_off_never_removes_an_enabled_message_from_scope(disabled):
    model = inventory()
    model["messages"][1]["configuration"]["routing"]["enabled"] = True
    for signal in model["signals"]:
        if signal["id"] in disabled:
            signal["configuration"] = {"routing": {"enabled": False}}
    coverage = simulation_coverage(**model, transports=[{"message_ids": ["local"]}])
    assert not coverage["complete"] and coverage["missing_signal_ids"] == ["error", "state"]
    assert coverage["transport_exclusions"] == []


@pytest.mark.parametrize("config", [True, ["legacy"],
    {**output_configuration(), "routing": False},
    {**output_configuration(), "communication_contract": ["FUNCTION_OUTPUT"]},
    {**output_configuration(), "transport_unit": True},
    {**output_configuration(), "transport_unit": {"provenance": ["unknown"]}},
    *[{**output_configuration(), "communication_contract": {"scope": "FUNCTION_OUTPUT", "role": value}}
      for value in ([], {})],
    {**output_configuration(), "transport_unit": {"provenance": {"generator": {"unresolved": True}}}},
])
def test_malformed_legacy_contract_never_grants_exclusion_or_crashes_scope(config):
    model = inventory()
    model["messages"][1]["configuration"] = config
    coverage = simulation_coverage(**model, transports=[{"message_ids": ["local"]}])
    assert not coverage["complete"] and coverage["missing_message_ids"] == ["output"]
    assert coverage["transport_exclusions"] == []


@pytest.mark.parametrize("scope", [
    {"mode": "MESSAGE", "message_ids": ["output"]},
    {"mode": "SIGNAL", "signal_ids": ["state"]},
    {"mode": "SELECTED", "message_ids": ["output"], "signal_ids": ["state"]},
])
def test_explicit_selection_is_never_reduced(scope):
    coverage = simulation_coverage(**inventory(), transports=[], scope=scope)
    assert not coverage["complete"] and coverage["missing_message_ids"] == ["output"]
    assert "state" in coverage["missing_signal_ids"] and coverage["transport_exclusions"] == []


@pytest.mark.parametrize("payload", [{"message_id": "output"}, {"message_ids": ["output"]}, {"signal_ids": ["state"]}])
@pytest.mark.parametrize("status", ["DRAFT", "PENDING", "APPROVED", "INVALID", "OUTDATED"])
def test_current_authored_transport_blocks_exclusion_even_if_not_executable(payload, status):
    coverage = simulation_coverage(**inventory(), transports=[{"message_ids": ["local"]}],
        declared_transports=[{"payload": payload, "status": status}])
    assert not coverage["complete"] and coverage["missing_message_ids"] == ["output"]
    assert coverage["missing_signal_ids"] == ["error", "state"] and coverage["transport_exclusions"] == []


@pytest.mark.parametrize("payload", [{"message_id": "output"}, {"signal_ids": ["state"]}])
@pytest.mark.parametrize("status", ["REJECTED", "SUPERSEDED", "DEPRECATED"])
def test_explicitly_discarded_history_does_not_block_unused_output(payload, status):
    retired = {"payload": payload, "status": status}
    coverage = simulation_coverage(**inventory(), transports=[{"message_ids": ["local"]}, retired],
        declared_transports=[retired])
    assert coverage["complete"] and coverage["excluded_message_ids"] == ["output"]
    assert coverage["covered_messages"] == 1 and coverage["covered_signals"] == 1
    current = {"payload": payload, "status": "OUTDATED"}
    reopened = simulation_coverage(**inventory(), transports=[{"message_ids": ["local"]}],
        declared_transports=[retired, current])
    assert not reopened["complete"] and reopened["missing_message_ids"] == ["output"]
    assert reopened["transport_exclusions"] == []


def test_outdated_transport_and_inactive_signal_reference_cannot_disappear_into_exclusion():
    model = inventory()
    model["signals"].append({"id": "retired", "message_id": "output", "lifecycle_state": "DEPRECATED"})
    coverage = simulation_coverage(**model, transports=[{"message_ids": ["local"]},
        {"status": "OUTDATED", "payload": {"signal_ids": ["retired"]}}])
    assert not coverage["complete"] and coverage["transport_exclusions"] == []
    assert coverage["required_signal_ids"] == ["error", "hall", "state"]


def test_disabled_local_hall_still_requires_local_transport():
    coverage = simulation_coverage(**inventory(), transports=[])
    assert not coverage["complete"]
    assert coverage["missing_message_ids"] == ["local"] and coverage["missing_signal_ids"] == ["hall"]


def test_inventory_and_assessment_do_not_claim_observed_unused_function_outputs():
    config = {"engineering_model": inventory(), "networks": [{"id": "local-lin"}],
        "communications": [{"id": "hall-route", "network_id": "local-lin", "message_ids": ["local"]}]}
    _apply_simulation_scope(config)
    assert len(config["engineering_model"]["signals"]) == 3
    actual = {"model_simulation": {"signals": [{"signal_id": "hall"}]}, "runtime_metrics": {
        "available": True, "routes": [{"route_id": "hall-route", "status": "PASS"}],
        "networks": [{"network_id": "local-lin"}]}}
    assessment = assess_simulation(config, actual)
    assert assessment["conformance"] == "PASS" and assessment["observed_signal_count"] == 1
    assert assessment["scope_coverage"]["excluded_signal_ids"] == ["error", "state"]
    assert assessment["missing_observed_signal_ids"] == []
    assert assess_simulation(config, {})["conformance"] == "NOT_EVALUATED"
    config["engineering_model"]["routes"] = [{"status": "OUTDATED", "payload": {"signal_ids": ["state"]}}]
    _apply_simulation_scope(config)
    assert config["scope_coverage"]["missing_message_ids"] == ["output"]
    assert not config["scope_coverage"]["transport_exclusions"]


def test_legacy_full_inventory_has_no_new_exclusions():
    messages = [{"id": f"m{i}"} for i in range(653)]
    signals = [{"id": f"s{i}", "message_id": f"m{i % 653}"} for i in range(1404)]
    coverage = simulation_coverage(messages, signals, [{"message_ids": [message["id"]]} for message in messages])
    assert coverage["complete"] and coverage["required_signals"] == 1404
    assert coverage["required_messages"] == 653 and coverage["transport_exclusions"] == []


@pytest.mark.parametrize("reference", [None, "message", "signal"])
def test_snapshot_uses_canonical_toggle_and_authored_transport_inventory(db_project, reference):
    from psycopg.types.json import Jsonb
    from backend.engineering.db import get_connection
    from backend.engineering.repository import create_object
    from backend.engineering.workflow.service import WorkflowStatusService, WorkflowConflictError
    from backend.engineering.capacity.service import PreflightService

    _sensor, port, interface, local, hall = _chain()
    output = create_object("Message", {"name": "CanonicalCalculatedOutput", "interface_id": str(interface["id"]),
        "hardware_interface_id": str(port["id"]), "dlc": 8, "cycle_ms": 20, "configuration": output_configuration()})
    signal = create_object("Signal", {"name": "Calculated", "message_id": str(output["id"]), "start_bit": 0,
        "length_bits": 8, "byte_order": "little_endian", "data_type": "unsigned"})
    service = WorkflowStatusService(db_project)
    if reference:
        from uuid import uuid4
        payload = {"message_id": str(output["id"])} if reference == "message" else {"signal_ids": [str(signal["id"])]}
        # A pre-existing invalid path must remain a visible design problem.
        with get_connection() as connection:
            connection.execute("INSERT INTO engineering_routing_entries (project_id, route_code, name, source, payload, status) "
                "VALUES (%s, %s, 'Retired output path', %s, %s, 'OUTDATED')",
                (db_project, f"RT-{uuid4().hex[:8]}", Jsonb({"node_id": str(_sensor["id"]), "interface_id": str(interface["id"])}), Jsonb(payload)))
    preflight = PreflightService(db_project).run()["scope_coverage"]
    assert str(local["id"]) in preflight["missing_message_ids"]
    if reference:
        assert str(output["id"]) in preflight["missing_message_ids"] and preflight["transport_exclusions"] == []
    else:
        assert preflight["excluded_message_ids"] == [str(output["id"])]
        assert service.get()["artifact_checks"]["routing"]["coverage"]["excluded_message_ids"] == [str(output["id"])]
    service.create_analysis_snapshot("preflight", input_data={}, provenance={}, status="APPROVED", results={}, findings=[])
    config = {"engineering_model": {"messages": []}, "communications": [
        {"message_ids": [str(local["id"])], "signal_ids": [str(hall["id"])]}],
        "scope_coverage": {"complete": True, "transport_exclusions": [{"message_id": "forged"}]}}
    if reference:
        with pytest.raises(WorkflowConflictError, match="ohne Transport"):
            service.create_simulation_snapshot(config)
        coverage = service.get()["artifact_checks"]["routing"]["coverage"]
        assert str(output["id"]) in coverage["missing_message_ids"] and not coverage["transport_exclusions"]
        with get_connection() as connection:
            connection.execute("UPDATE engineering_routing_entries SET status='REJECTED' WHERE project_id=%s", (db_project,))
        retired_coverage = PreflightService(db_project).run()["scope_coverage"]
        assert retired_coverage["excluded_message_ids"] == [str(output["id"])]
        service.create_analysis_snapshot("preflight", input_data={}, provenance={}, status="APPROVED", results={}, findings=[])
        resumed = service.create_simulation_snapshot(config)["configuration"]["scope_coverage"]
        assert resumed["complete"] and resumed["excluded_message_ids"] == [str(output["id"])]
    else:
        frozen = service.create_simulation_snapshot(config)["configuration"]
        coverage = frozen["scope_coverage"]
        assert coverage["total_messages"] == 2 and coverage["total_signals"] == 2 and coverage["complete"]
        excluded, = coverage["transport_exclusions"]
        assert excluded["message_name"] == "CanonicalCalculatedOutput" and excluded["message_id"] == str(output["id"])
        assert excluded["signal_ids"] == [str(signal["id"])]


def test_snapshot_does_not_trust_a_supplied_disabled_output_over_canonical_intent(db_project):
    from backend.engineering.workflow.service import WorkflowStatusService, WorkflowConflictError

    _sensor, _port, _interface, message, signal = _chain()
    service = WorkflowStatusService(db_project)
    service.create_analysis_snapshot("preflight", input_data={}, provenance={}, status="APPROVED", results={}, findings=[])
    config = {"engineering_model": {"messages": [{"id": str(message["id"]), "configuration": output_configuration()}],
        "signals": [{"id": str(signal["id"]), "message_id": str(message["id"])}]}, "communications": [],
        "scope_coverage": {"complete": True, "transport_exclusions": [{"message_id": str(message["id"])}]}}
    with pytest.raises(WorkflowConflictError, match="ohne Transport"):
        service.create_simulation_snapshot(config)
