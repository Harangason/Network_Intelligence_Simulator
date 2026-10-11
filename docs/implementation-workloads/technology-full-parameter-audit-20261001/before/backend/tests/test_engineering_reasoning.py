from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4
import pytest
from pydantic import ValidationError

from backend.engineering.reasoning.contracts import ReasoningRequest, SimulationReasoningResult
from backend.engineering.reasoning.engine import EngineeringReasoningEngine
from backend.engineering.reasoning.correlation import correlate_time, FirstDivergenceAnalyzer
from backend.engineering.reasoning.service import TraceWindowResolver


def frame(**changes):
    return {"route_id": "route", "sequence": 1, "time_s": 1.02, "scheduled_time_s": 1,
        "network": "bus", "technology": "can_fd", "sender_hardware": "camera", "sender_interface": "camera-if",
        "source_logical_address": "1", "receiver_hardware": ["ecu"], "receiver_interfaces": ["ecu-if"], "gateway_ids": ["gateway"],
        "status": "transmitted", "end_to_end_latency_ms": 20, "transmission_latency_ms": 2,
        "queue_delay_ms": 15, "queue_depth_estimate": 2, "deadline_ms": 10,
        "signals": [], "faults": [], **changes}


def context(**changes):
    return {"snapshot_available": True, "trusted_simulation": True, "routes": [],
        "configuration": {}, "faults": [], "dependencies": {}, "state_models": {}, **changes}


def analyze(events, **options):
    return EngineeringReasoningEngine().analyze(project_id="p", job_id="j", events=events,
        context=options.pop("context", context()), **options)


def test_queue_causal_component_supported_and_no_time_only_claim():
    result = analyze([frame()])
    assert result.completion_status == "COMPLETE"
    assert any(h.status == "SUPPORTED" and h.id.startswith("queue:") for h in result.hypotheses)
    assert any(c.relation == "VALIDATED_LATENCY_COMPONENT" for c in result.causal_chain)
    assert not any(c.relation == "CAUSE_PRECEDES_EFFECT" for c in result.causal_chain)
    assert result.confidence_factors["deterministic_validation"]


def test_queue_hypothesis_rejected_if_queue_is_zero():
    result = analyze([frame(queue_delay_ms=0, queue_depth_estimate=0)])
    assert result.rejected_hypotheses
    assert not result.confirmed_causes
    assert result.conclusion.startswith("ROOT_CAUSE_UNCONFIRMED")


def test_dense_bounded_fault_window_keeps_all_observations_for_confirmation():
    events = [frame(sequence=index, time_s=1 + index * .001, status="dropped",
                    faults=["GATEWAY_DROP"], configured_latency_ms=1)
              for index in range(130)]
    fault = {"type": "GATEWAY_DROP", "start_s": 1, "end_s": 1.2,
             "target": {"id": "gateway"}}
    result = analyze(events, context=context(faults=[fault], trusted_simulation=True))
    assert len(result.observations) > 500
    assert "OBSERVATION_BUDGET" not in {gap["code"] for gap in result.data_gaps}
    assert result.completion_status == "COMPLETE"
    assert "fault:0:GATEWAY_DROP" in result.confirmed_causes


def test_normal_signal_samples_do_not_exhaust_fault_evidence_budget():
    events = [frame(sequence=index, time_s=1 + index * .001, scheduled_time_s=1 + index * .001,
                    signals=[{"signal_id": f"normal-{signal}", "value": 1, "quality": "GOOD"}
                             for signal in range(6)])
              for index in range(351)]
    events[200]["status"] = "dropped"
    events[200]["faults"] = ["MESSAGE_LOSS"]
    fault = {"type": "MESSAGE_LOSS", "start_s": 1.2, "end_s": 1.21,
             "target": {"id": "route"}}
    result = analyze(events, context=context(faults=[fault]))
    assert "EVIDENCE_BUDGET" not in {gap["code"] for gap in result.data_gaps}
    assert result.completion_status == "COMPLETE"
    assert "fault:0:MESSAGE_LOSS" in result.confirmed_causes
    assert not any(ref.source_type == "SignalSeries" for ref in result.evidence_refs)


@pytest.mark.parametrize("change,expected", [({"snapshot_available": False}, "MISSING_SIMULATION_SNAPSHOT"), ({"data_gaps": [{"code": "MISSING_DECODE", "message": "No decoder"}]}, "MISSING_DECODE")])
def test_missing_data_blocks_confirmation(change, expected):
    result = analyze([frame()], context=context(**change))
    assert not result.confirmed_causes
    assert result.completion_status == "INCOMPLETE"
    assert expected in {g["code"] for g in result.data_gaps}
    assert result.confidence <= .49


@pytest.mark.parametrize("timestamp,relation", [(0, "BEFORE"), (1, "SIMULTANEOUS"), (2, "AFTER")])
def test_temporal_order_is_not_causality(timestamp, relation):
    assert correlate_time(timestamp, 1) == relation
    assert correlate_time(0, 1, mechanism_validated=True) == "CAUSE_PRECEDES_EFFECT"
    assert correlate_time(2, 1, mechanism_validated=True) == "AFTER"


def test_fault_requires_time_target_marker_and_effect():
    fault = {"type": "GATEWAY_DROP", "start_s": .9, "end_s": 1.1, "target": {"id": "gateway"}}
    event = frame(status="dropped", faults=["GATEWAY_DROP"], queue_delay_ms=0, deadline_ms=100)
    result = analyze([event], context=context(faults=[fault]))
    assert result.confirmed_causes == ["fault:0:GATEWAY_DROP"]
    assert any(o.classification == "INJECTED_CAUSE" for o in result.observations)
    for bad in ({**fault, "start_s": 2}, {**fault, "target": {"id": "unrelated"}}):
        denied = analyze([event], context=context(faults=[bad]))
        assert not denied.confirmed_causes
    assert not analyze([{**event, "faults": []}], context=context(faults=[fault])).confirmed_causes


def test_signal_dependencies_and_state_transitions_are_explicit():
    a = frame(time_s=.1, sequence=0, deadline_ms=100, queue_delay_ms=0, signals=[{"signal_id": "command", "value": 200, "maximum": 100, "quality": "GOOD"}, {"signal_id": "state", "value": 1, "state": "ACTIVE"}])
    b = frame(time_s=.2, sequence=1, deadline_ms=100, queue_delay_ms=0, signals=[{"signal_id": "state", "value": 2, "state": "DEGRADED", "source_dependencies": ["command"]}])
    result = analyze([a, b], context=context(state_models={"state": {"transitions": [{"from": "ACTIVE", "to": "DEGRADED"}]}}))
    assert result.downstream_effects
    assert result.downstream_effects[0]["relation"] == "EXPLICIT_DEPENDENCY"
    assert not result.downstream_effects[0]["causality_proven"]
    assert next(o for o in result.observations if o.type == "STATE_CHANGE").metrics["transition_valid"] is True
    b["signals"][0].pop("source_dependencies")
    assert not analyze([a, b]).downstream_effects


def test_golden_first_divergence_is_chronological_and_not_automatically_causal():
    baseline = [frame(sequence=i, time_s=i, message_ids=["message"], signals=[{"signal_id": "s", "value": i}]) for i in range(3)]
    actual = deepcopy(baseline)
    actual[1]["signals"][0]["value"] = 42
    actual[2]["route_id"] = "other-route"
    result = FirstDivergenceAnalyzer.analyze(actual, baseline)
    assert result["first_divergence"]["timestamp"] == 1
    assert "SIGNAL_DEVIATION" in result["first_divergence"]["types"]
    assert not result["causality_proven"]
    assert result["first_credible_causal_deviation"] is None


def test_window_resolver_has_bounded_pages_and_continuation():
    calls = []
    def read(path):
        calls.append(path)
        return {"events": [frame()], "next_cursor": len(calls)*100}
    events, window = TraceWindowResolver(read).resolve(ReasoningRequest(job_id="job", focus_s=1))
    assert len(calls) == 3 and len(events) == 3
    assert window["next_cursor"] == 300 and window["pre_window"] == [.9, 1]
    result = analyze(events, window=window)
    assert result.continuation and not result.confirmed_causes
    assert result.completion_status == "INCOMPLETE"


def test_golden_causal_association_is_in_the_returned_contract():
    baseline = frame(queue_delay_ms=0, end_to_end_latency_ms=2, time_s=1.002)
    actual = frame()
    comparison = FirstDivergenceAnalyzer.analyze([actual], [baseline])
    result = analyze([actual], comparison=comparison)
    assert result.comparison["first_credible_causal_deviation"]["causality_proven"]
    assert result.comparison["first_credible_causal_deviation"]["evidence_refs"]
    # The independent comparator alone must still make no causal claim.
    assert comparison["first_credible_causal_deviation"] is None


def test_continuation_preserves_evidence_but_does_not_invent_cross_page_metrics():
    first = analyze([frame()], window={"start_s": 0, "end_s": 2, "next_cursor": 100})
    result = analyze([frame(sequence=2)], previous=first, window={"start_s": 0, "end_s": 2, "next_cursor": None})
    assert result.completion_status == "INCOMPLETE"
    assert "PAGINATED_AGGREGATION" in {g["code"] for g in result.data_gaps}
    assert not result.continuation
    assert len({o.id for o in result.observations}) == len(result.observations)
    refs = {e.id for e in result.evidence_refs}
    assert all(set(o.evidence_refs) <= refs for o in result.observations)


@pytest.mark.parametrize("field,value", [("focus_s", float("nan")), ("start_s", -1), ("cursor", -1), ("hidden_reasoning", "not allowed")])
def test_invalid_request_and_cot_fields_rejected(field, value):
    with pytest.raises(ValidationError):
        ReasoningRequest.model_validate({"job_id": "j", field: value})


def test_no_raw_events_or_private_reasoning_persisted():
    result = analyze([frame()])
    payload = result.model_dump(mode="json")
    assert "events" not in payload and "raw_reasoning" not in payload
    with pytest.raises(ValidationError):
        SimulationReasoningResult.model_validate({**payload, "chain_of_thought": "private"})
    assert len(json.dumps(payload)) < 100000


@pytest.mark.parametrize("technologies,fault", [
    (["can_fd", "can_fd"], {"type": "GATEWAY_DROP", "scope": "NETWORK", "target": {"id": "node-1"}}),
    (["profinet"], {"type": "MESSAGE_DELAY", "scope": "MESSAGE", "target": {"id": "route-0"}, "delay_ms": 50}),
    (["dds_rtps"], {"type": "MESSAGE_LOSS", "scope": "MESSAGE", "target": {"id": "route-0"}}),
    (["ethernet"], {"type": "MESSAGE_DELAY", "scope": "MESSAGE", "target": {"id": "route-0"}, "delay_ms": 50}),
    (["ethernet"], {"type": "MESSAGE_LOSS", "scope": "MESSAGE", "target": {"id": "route-0"}}),
])
def test_real_simulator_fault_reasoning_or_explicit_model_gap(tmp_path, technologies, fault):
    from backend.tests.test_acceptance_scenarios import case_config, assert_timing_model_unavailable
    from communication_simulator import run_simulation
    config = case_config(tmp_path, technologies)
    config["scenario"] = {"mode": "USER_DEFINED_FAULT", "faults": [{**fault, "start_s": .02, "end_s": .05}]}
    if technologies[0] in {'profinet', 'dds_rtps'}:
        assert_timing_model_unavailable(config, technologies)
        with pytest.raises(ValueError, match='TIMING_UNVERIFIED'):
            run_simulation(config)
        assert not list(tmp_path.rglob('universal_trace.jsonl'))
        return
    simulation = run_simulation(config)
    path = next(Path(p) for p in simulation["artifacts"] if str(p).endswith("universal_trace.jsonl"))
    events = [json.loads(line) for line in path.read_text().splitlines()]
    result = analyze(events, context=context(configuration=config, faults=config["scenario"]["faults"]))
    assert result.completion_status == "COMPLETE", result.model_dump()
    assert any(h.status == "SUPPORTED" and h.id.startswith("fault:") for h in result.hypotheses)
    assert result.confirmed_causes


def test_reasoning_tools_registered_and_selected():
    from backend.engineering.agent_tools.services import TOOLS
    from backend.agent_core.orchestration.tool_selection import select_tools
    required = {"get_trace_window", "get_trace_events", "get_signal_series", "get_route", "get_network_load", "get_interface_load", "get_timing_metrics", "get_fault_events", "get_state_transitions", "compare_golden_trace", "find_first_divergence", "correlate_events"}
    assert required <= TOOLS.keys()
    chosen = select_tools("Untersuche Ursache einer Deadline im CAN Trace", [{"name": name} for name in TOOLS])
    assert "investigate_deadline_miss" in {t["name"] for t in chosen}
