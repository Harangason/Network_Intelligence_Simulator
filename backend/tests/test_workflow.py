from contextlib import nullcontext

from backend.engineering.capacity.calculators import (
    clock_drift_ms,
    classify_load,
    estimate_frame,
    queueing_delay_ms,
    scheduled_queueing_delay_ms,
    utilization_percent,
)
from backend.engineering.capacity import service as capacity_service_module
from backend.engineering.capacity.service import CapacityTimingService, PreflightService
from backend.engineering.workflow.models import default_statuses, default_versions, set_step_status, transition_state
from backend.engineering.workflow import service as workflow_service_module
from backend.engineering.workflow.service import WorkflowStatusService, is_topology_layout_only_change


def test_engineering_change_marks_existing_dependent_results_outdated():
    state = {
        "versions": default_versions(),
        "statuses": {step: "COMPLETE" for step in default_statuses()},
        "stale_reasons": {},
    }

    changed = transition_state(state, "engineering_model", "Model changed")

    assert changed["versions"]["engineering_model"] == 1
    assert changed["statuses"]["engineering_model"] == "COMPLETE"
    assert changed["statuses"]["routing"] == "OUTDATED"
    assert changed["statuses"]["results_analysis"] == "OUTDATED"
    assert changed["stale_reasons"]["simulation"] == "Model changed"
    assert state["versions"]["engineering_model"] == 0


def test_parameter_change_only_invalidates_calculation_and_later_steps():
    state = {
        "versions": default_versions(),
        "statuses": {step: "COMPLETE" for step in default_statuses()},
        "stale_reasons": {},
    }

    changed = transition_state(state, "parameters", "Parameters changed")

    assert changed["statuses"]["engineering_model"] == "COMPLETE"
    assert changed["statuses"]["network_editor"] == "COMPLETE"
    assert changed["statuses"]["capacity_timing"] == "OUTDATED"
    assert changed["statuses"]["validation"] == "OUTDATED"
    assert changed["statuses"]["simulation"] == "OUTDATED"


def test_parameters_are_approved_by_default_and_ignore_upstream_changes():
    state = {
        "versions": default_versions(),
        "statuses": default_statuses(),
        "stale_reasons": {},
    }

    changed = transition_state(state, "engineering_model", "Model changed")

    assert default_statuses()["parameters"] == "APPROVED"
    assert changed["statuses"]["parameters"] == "APPROVED"
    assert "parameters" not in changed["stale_reasons"]


def test_parameter_artifact_approves_defaults_and_complete_configuration():
    defaults = WorkflowStatusService._parameter_artifact_check({})
    complete = WorkflowStatusService._parameter_artifact_check({
        "industry": "automotive",
        "technology": "can_fd",
        "formats": ["universal-jsonl"],
        "bitrate": 2_000_000,
        "cycle_ms": 10,
        "payload_bytes": 64,
        "queue_size": 256,
        "warning_threshold": 45,
        "critical_threshold": 60,
        "overload_threshold": 75,
        "target_bus_load_percent": 45,
    })

    assert defaults == {
        "status": "APPROVED",
        "complete": True,
        "uses_defaults": True,
        "required": {},
        "invalid_numeric": [],
    }
    assert complete["status"] == "APPROVED"
    assert complete["complete"] is True
    assert complete["uses_defaults"] is False


def test_empty_future_steps_stay_empty_until_a_result_exists():
    state = {
        "versions": default_versions(),
        "statuses": default_statuses(),
        "stale_reasons": {},
    }

    changed = transition_state(state, "routing", "Route changed")

    assert changed["statuses"]["routing"] == "COMPLETE"
    assert changed["statuses"]["capacity_timing"] == "EMPTY"
    assert "capacity_timing" not in changed["stale_reasons"]


def test_completed_simulation_drops_previous_recalculation_reason():
    state = {
        "versions": default_versions(),
        "statuses": {**default_statuses(), "simulation": "OUTDATED"},
        "stale_reasons": {"simulation": "Validation / Preflight wurde neu ausgefuehrt."},
    }

    completed = set_step_status(state, "simulation", "COMPLETE")

    assert completed["statuses"]["simulation"] == "COMPLETE"
    assert "simulation" not in completed["stale_reasons"]


def test_can_fd_uses_separate_arbitration_and_data_phases():
    estimate = estimate_frame(
        "CAN_FD",
        64,
        {"bitrate": 2_000_000, "arbitration_bitrate": 500_000, "data_bitrate": 2_000_000},
    )

    assert estimate.calculation_model == "CAN_FD_PHASE_ESTIMATE"
    assert estimate.frame_bits > 64 * 8
    assert estimate.transmission_time_s > 0
    assert estimate.is_generic_estimate is False


def test_ethernet_applies_minimum_wire_footprint():
    estimate = estimate_frame("ETHERNET", 1, {"bitrate": 100_000_000})

    assert estimate.frame_bits == 84 * 8
    assert estimate.calculation_model == "ETHERNET_WIRE_ESTIMATE"


def test_unknown_protocol_is_explicitly_generic():
    estimate = estimate_frame("CUSTOM_RADIO", 20, {"bitrate": 1_000_000})

    assert estimate.is_generic_estimate is True
    assert estimate.calculation_model == "GENERIC_ESTIMATE"


def test_utilization_queueing_and_thresholds_are_monotonic():
    load = utilization_percent(0.001, 10)

    assert load == 10
    assert queueing_delay_ms(0.001, 70) > queueing_delay_ms(0.001, 20)
    assert classify_load(59.9, {"warning": 60, "critical": 80, "overload": 100}) == "NORMAL"
    assert classify_load(85, {"warning": 60, "critical": 80, "overload": 100}) == "CRITICAL"
    assert classify_load(105, {"warning": 60, "critical": 80, "overload": 100}) == "OVERLOAD"


def test_scheduling_policy_and_priority_change_queueing_estimate():
    fifo = scheduled_queueing_delay_ms(0.001, 70, "FIFO", 50)
    strict_high = scheduled_queueing_delay_ms(0.001, 70, "STRICT_PRIORITY", 100)
    strict_low = scheduled_queueing_delay_ms(0.001, 70, "STRICT_PRIORITY", 0)

    assert strict_high < fifo < strict_low


def test_clock_drift_is_reported_in_milliseconds():
    assert clock_drift_ms(20, 10) == 0.2


def test_workflow_state_always_exposes_complete_agent_context():
    row = {
        "project_id": "project-a",
        "active_step": "capacity_timing",
        "versions": {},
        "statuses": {},
        "stale_reasons": {},
        "context": {"selected_network": "can-a"},
        "parameters": {},
        "topology": {},
        "updated_at": None,
    }

    state = WorkflowStatusService._state(row)

    assert state["context"] == {
        "active_project": "project-a",
        "active_workflow_step": "capacity_timing",
        "selected_object": None,
        "selected_route": None,
        "selected_network": "can-a",
        "selected_signal": None,
        "selected_simulation": None,
    }


def test_workflow_state_hides_stale_reason_after_step_is_complete():
    row = {
        "project_id": "project-a",
        "active_step": "simulation",
        "versions": {},
        "statuses": {"simulation": "COMPLETE", "results_analysis": "ERROR"},
        "stale_reasons": {
            "simulation": "Validation / Preflight wurde neu ausgefuehrt.",
            "results_analysis": "Kein Ergebnisartefakt vorhanden.",
        },
        "context": {},
        "parameters": {},
        "topology": {},
        "updated_at": None,
    }

    state = WorkflowStatusService._state(row)

    assert "simulation" not in state["stale_reasons"]
    assert state["stale_reasons"]["results_analysis"] == "Kein Ergebnisartefakt vorhanden."


def test_workflow_summary_omits_heavy_simulation_and_model_payloads(monkeypatch):
    row = {
        "project_id": "project-summary",
        "active_step": "data_science_intelligence",
        "versions": {},
        "statuses": {},
        "stale_reasons": {},
        "context": {},
        "parameters": {"bitrate": 2_000_000},
        "topology": {"nodes": [{"id": "node-1"}], "edges": []},
        "updated_at": None,
    }

    class Result:
        def __init__(self, value):
            self.value = value

        def fetchone(self):
            return self.value

        def fetchall(self):
            return self.value

    class Connection:
        def execute(self, query, _params=None):
            statement = str(query)
            if "INSERT INTO engineering_workflow_projects" in statement:
                return Result(None)
            if "SELECT * FROM engineering_workflow_projects" in statement:
                return Result(row)
            if "FROM engineering_analysis_snapshots" in statement:
                return Result([])
            if "FROM engineering_simulation_snapshots" in statement:
                raise AssertionError("Summary must not load simulation details.")
            raise AssertionError(statement)

    monkeypatch.setattr(workflow_service_module, "get_connection", lambda: nullcontext(Connection()))
    monkeypatch.setattr(WorkflowStatusService, "_bootstrap_statuses", lambda *_args: {})

    state = WorkflowStatusService("project-summary").get(summary=True)

    assert state["project_id"] == "project-summary"
    assert len(state["steps"]) == 9
    assert state["parameters"] == {}
    assert state["topology"] == {}
    assert state["simulation_snapshots"] == []


def test_topology_layout_change_ignores_only_visual_fields():
    current = {
        "nodes": [
            {
                "id": "gateway",
                "kind": "gateway",
                "name": "Gateway",
                "x": 10,
                "y": 20,
                "ports": [
                    {"id": "port-a", "name": "CAN", "bus": "can_fd", "side": "left", "offset": 0.5}
                ],
            }
        ],
        "edges": [],
    }
    rearranged = {
        "nodes": [
            {
                **current["nodes"][0],
                "x": 500,
                "y": 160,
                "width": 190,
                "height": 100,
                "ports": [{**current["nodes"][0]["ports"][0], "side": "right", "offset": 0.75}],
            }
        ],
        "edges": [],
    }
    renamed = {
        **rearranged,
        "nodes": [{**rearranged["nodes"][0], "name": "Changed Gateway"}],
    }

    assert is_topology_layout_only_change(current, rearranged) is True
    assert is_topology_layout_only_change(current, current) is False
    assert is_topology_layout_only_change(current, renamed) is False


def test_preflight_maps_network_editor_status_to_network_category(monkeypatch):
    state = {
        "versions": default_versions(),
        "statuses": {
            **default_statuses(),
            "engineering_model": "COMPLETE",
            "routing": "COMPLETE",
            "network_editor": "IN_PROGRESS",
            "parameters": "COMPLETE",
            "capacity_timing": "COMPLETE",
        },
        "parameters": {},
        "topology": {"nodes": [], "edges": []},
    }
    service = PreflightService("analysis-project")
    monkeypatch.setattr(service.workflow, "get", lambda: state)
    monkeypatch.setattr(service.workflow, "latest_analysis", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service.workflow,
        "create_analysis_snapshot",
        lambda *_args, **_kwargs: {"id": "preflight-snapshot"},
    )
    monkeypatch.setattr(capacity_service_module, "list_objects", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(capacity_service_module, "list_routes", lambda **_kwargs: [])

    response = service.run()

    network_codes = {item["code"] for item in response["category_checks"]["network"]}
    assert "WORKFLOW_STEP_NOT_READY" in network_codes


def test_capacity_timing_analysis_covers_load_requirements_gateway_reliability_and_sync(monkeypatch):
    state = {
        "project_id": "analysis-project",
        "versions": default_versions(),
        "statuses": {step: "COMPLETE" for step in default_statuses()},
        "parameters": {
            "technology": "can_fd",
            "bitrate": 500_000,
            "arbitration_bitrate": 500_000,
            "data_bitrate": 500_000,
            "payload_bytes": 64,
            "cycle_ms": 10,
            "peak_factor": 1.2,
            "burst_factor": 1.5,
            "target_bus_load_percent": 1,
            "gateway_delay_ms": 1.0,
            "gateway_queue_delay_ms": 0.5,
            "protocol_conversion_delay_ms": 0.25,
            "gateway_maximum_throughput": 100,
            "queue_policy": "STRICT_PRIORITY",
            "packet_loss_probability": 0.1,
            "required_reliability": 0.99,
            "clock_drift_ppm": 200,
            "sync_precision_ms": 0.2,
            "maximum_sync_error_ms": 0.1,
            "duration_s": 10,
        },
        "topology": {"nodes": [], "edges": []},
    }
    route = {
        "id": "route-1",
        "route_code": "RT-1",
        "name": "Critical route",
        "status": "APPROVED",
        "approval_state": "APPROVED",
        "validation": {"valid": True, "errors": [], "warnings": []},
        "source": {"node_id": "producer", "protocol": "can_fd", "network_id": "can-a"},
        "payload": {"message_id": "message-1", "signal_ids": ["signal-1"], "payload_bytes": 64},
        "destinations": [{"node_id": "consumer"}],
        "route": {"gateways": ["gateway-1"]},
        "timing": {"cycle_time_ms": 10, "max_latency_ms": 0.1, "jitter_limit_ms": 0.01, "timeout_ms": 0.1, "freshness_ms": 5},
        "routing_policy": {"priority": "SAFETY_CRITICAL"},
    }
    objects = {
        "Message": [{"id": "message-1", "name": "Critical message", "interface_id": "interface-1", "dlc": 64, "cycle_ms": 10, "configuration": {}}],
        "Signal": [{"id": "signal-1", "name": "EmergencyStop", "message_id": "message-1", "communication": {"priority": "SAFETY_CRITICAL"}}],
        "Interface": [{"id": "interface-1", "interface_type": "can_fd", "configuration": {"network_id": "can-a"}}],
        "HardwareNode": [{"id": "gateway-1", "name": "Gateway 1", "hardware_information": {"maximum_throughput": 100}}],
    }
    service = CapacityTimingService("analysis-project")
    monkeypatch.setattr(service.workflow, "get", lambda: state)
    monkeypatch.setattr(service, "latest", lambda: None)
    monkeypatch.setattr(capacity_service_module, "list_routes", lambda limit=500: [route])
    monkeypatch.setattr(
        capacity_service_module,
        "list_objects",
        lambda object_type, limit=500: objects.get(object_type, []),
    )

    response = service.calculate(persist=False)
    results = response["results"]
    network = results["networks"][0]
    analyzed_route = results["routes"][0]
    codes = {item["code"] for item in response["findings"]}

    assert network["average_load_percent"] < network["peak_load_percent"] < network["burst_load_percent"]
    assert network["capacity_reserve_percent"] == round(100 - network["average_load_percent"], 4)
    assert network["target_status"] == "EXCEEDED"
    assert analyzed_route["gateway_latency_ms"] == 1.75
    assert analyzed_route["requirement_status"] == "FAIL"
    assert results["gateways"][0]["status"] == "OVERLOAD"
    assert results["reliability"]["status"] == "FAIL"
    assert results["synchronization"]["status"] == "FAIL"
    assert results["critical_paths"][0]["route_id"] == "route-1"
    assert results["bottlenecks"]
    assert {"CAPACITY_TARGET_LOAD_EXCEEDED", "TIMING_DEADLINE_MISS", "TIMING_JITTER_EXCEEDED", "TIMING_TIMEOUT_RISK", "TIMING_FRESHNESS_RISK", "GATEWAY_OVERLOAD", "RELIABILITY_REQUIREMENT_MISS", "SYNCHRONIZATION_REQUIREMENT_MISS"} <= codes
    assert response["provenance"]["calculation_model"] == "TECHNOLOGY_AWARE_CAPACITY_TIMING"
