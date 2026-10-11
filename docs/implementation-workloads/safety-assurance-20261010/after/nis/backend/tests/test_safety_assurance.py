from copy import deepcopy
import pytest

from backend.nis.engineering.safety_assurance import assess_requirements, export_snapshot, validate_requirement, digest
from backend.nis.domain.vocabulary import EngineeringValidationError
from backend.nis.communication.services.sources import directory_from_profiles


def requirement():
    return {"id": "safety-1", "name": "Lenkung sicher abschalten", "version": 1, "function_id": "fn-1", "configuration": {
        "profile": {"standard": "ISO 26262", "edition": "2018", "domain": "road_vehicle", "applicability": "APPLICABLE", "reason": "Approved item scope"},
        "hazard_ref": "H-1", "safety_goal_ref": "SG-1", "route_ids": ["route-1"],
        "eip": {"project_id": "eip-1", "requirement_ref": "SR-1", "source_revisions": {"SR-1": 2}},
        "criteria": {"deadline_ms": 20, "freshness_ms": 30, "required_protections": ["CRC"],
            "fault_cases": [{"id": "loss-test", "type": "LOSS", "detection_ms": 10, "ftti_ms": 20, "safe_state": "torque_zero", "receiver_id": "rx"}]}}}


def events():
    return [
        {"event_id": "tx", "transaction_id": "transaction-1", "route_id": "route-1", "status": "transmitted", "time_s": 1.001,
         "origin_release_time_s": 1., "data_generation_time_s": 1., "segment_index": 0, "segment_count": 1, "final_segment": True},
        {"event_id": "accept", "transaction_id": "transaction-1", "route_id": "route-1", "event_type": "RECEIVER_ACCEPTANCE", "receiver_status": "ACCEPTED",
         "time_s": 1.002, "receiver_accept_time_s": 1.002, "protection_checks": {"CRC": "PASS"}},
        {"event_id": "fault", "safety_requirement_id": "safety-1", "fault_case_id": "loss-test", "fault_occurrence_id": "occurrence-1", "receiver_id": "rx", "event_type": "SAFETY_FAULT", "fault_type": "LOSS", "time_s": 2., "time_basis": "SIMULATION_CLOCK"},
        {"event_id": "detect", "safety_requirement_id": "safety-1", "fault_case_id": "loss-test", "fault_occurrence_id": "occurrence-1", "receiver_id": "rx", "event_type": "SAFETY_DETECTION", "caused_by_event_id": "fault", "time_s": 2.005, "time_basis": "SIMULATION_CLOCK"},
        {"event_id": "react", "safety_requirement_id": "safety-1", "fault_case_id": "loss-test", "fault_occurrence_id": "occurrence-1", "receiver_id": "rx", "event_type": "SAFETY_REACTION", "caused_by_event_id": "fault", "time_s": 2.01, "time_basis": "SIMULATION_CLOCK", "physical_state_observed": True, "observed_state": "torque_zero"},
    ]


def assess(rows=None, req=None, routes=None, basis="SIMULATION_CLOCK"):
    return assess_requirements([req or requirement()], rows if rows is not None else events(), routes or {"route-1": {}}, time_basis=basis)


def test_explicit_causal_proof_passes_technical_only():
    result = assess()
    assert result["technical_status"] == "PASS"
    assert result["normative_status"] == "NOT_EVALUATED"
    assert result["release_approved"] is False
    assert set(result["requirements"][0]["evidence_event_ids"]) == {"tx", "accept", "fault", "detect", "react"}


@pytest.mark.parametrize("mutation", ["reaction_missing", "label_only", "receiver", "causal_id", "clock", "negative_time", "duplicate_reaction", "protection_missing", "acceptance_missing"])
def test_incomplete_or_ambiguous_evidence_never_passes(mutation):
    rows = events()
    if mutation == "reaction_missing": rows.pop()
    if mutation == "label_only": rows[-1]["physical_state_observed"] = False
    if mutation == "receiver": rows[-1]["receiver_id"] = "other"
    if mutation == "causal_id": rows[-1]["caused_by_event_id"] = "nearby-but-unrelated"
    if mutation == "clock": rows[-1]["time_basis"] = "unsynchronized"
    if mutation == "negative_time": rows[-1]["time_s"] = -1
    if mutation == "duplicate_reaction": rows.append({**rows[-1], "event_id": "other-reaction"})
    if mutation == "protection_missing": rows[1].pop("protection_checks")
    if mutation == "acceptance_missing": rows.pop(1)
    assert assess(rows)["technical_status"] != "PASS"


@pytest.mark.parametrize("mutation", ["late_detect", "late_react", "wrong_state", "deadline", "freshness", "protection_fail"])
def test_observed_violations_fail(mutation):
    rows = events()
    if mutation == "late_detect": rows[-2]["time_s"] = 2.015
    if mutation == "late_react": rows[-1]["time_s"] = 2.030
    if mutation == "wrong_state": rows[-1]["observed_state"] = "torque_active"
    if mutation == "deadline": rows[1]["receiver_accept_time_s"] = rows[1]["time_s"] = 1.1
    if mutation == "freshness": rows[0]["data_generation_time_s"] = .8
    if mutation == "protection_fail": rows[1]["protection_checks"]["CRC"] = "FAIL"
    assert assess(rows)["technical_status"] == "FAIL"


def test_every_required_fault_case_and_fanout_destination_needs_evidence():
    req = requirement(); req["configuration"]["criteria"]["fault_cases"].append({"id": "corrupt", "type": "CORRUPTION", "detection_ms": 5, "ftti_ms": 10, "safe_state": "off", "receiver_id": "rx"})
    assert assess(req=req)["technical_status"] == "NOT_EVALUATED"
    rows = events()
    for row in rows[:2]: row["route_id"] = "route-a"
    routes = {"route-a": {"canonical_route_id": "route-1"}, "route-b": {"canonical_route_id": "route-1"}}
    assert assess(rows, routes=routes)["technical_status"] == "NOT_EVALUATED"
    assert assess(basis="UNKNOWN")["technical_status"] == "NOT_EVALUATED"


@pytest.mark.parametrize("key,value", [("deadline_ms", True), ("deadline_ms", float("nan")), ("freshness_ms", -1), ("required_protections", [{}]), ("fault_cases", {})])
def test_invalid_technical_defaults_rejected(key, value):
    config = requirement()["configuration"]; config["criteria"][key] = value
    with pytest.raises(EngineeringValidationError): validate_requirement(config)


def test_no_implicit_asil_or_normative_approval():
    config = requirement()["configuration"]
    config["profile"]["release_approved"] = True
    with pytest.raises(EngineeringValidationError): validate_requirement(config)
    config["profile"].pop("release_approved"); config["integrity"] = {"model": "ASIL", "level": "D"}
    with pytest.raises(EngineeringValidationError): validate_requirement(config)


def test_export_freezes_original_result_and_detects_revision_drift():
    req = requirement(); report = assess()
    snapshot = {"id": "snapshot-1", "job_id": "job-1", "status": "COMPLETED", "is_outdated": False, "source_versions": {"engineering_model": 1},
        "configuration": {"engineering_model": {"safety_requirements": [deepcopy(req)]}}, "result": {"runtime_metrics": {"safety_assurance": report}}}
    bundle = export_snapshot("nis-1", snapshot, [req])
    assert digest(bundle["payload"]) == bundle["sha256"]
    assert bundle["payload"]["freshness"] == "CURRENT"
    req["version"] = 2
    assert export_snapshot("nis-1", snapshot, [req])["payload"]["freshness"] == "OUTDATED"
    assert bundle["payload"]["requirement_revisions"] == {"safety-1": 1}
    assert export_snapshot("nis-1", None, [req])["payload"]["assessment"]["technical_status"] == "NOT_EVALUATED"


def test_norm_sources_visible_without_technology_or_license_fabrication():
    data = directory_from_profiles([])
    assert data["technology_count"] == 0
    assert len(data["sources"]) == 4
    assert all(not row["technologies"] and row["categories"] and row["rights"]["publication"] == "UNRESOLVED" for row in data["sources"])
    assert any("155" in row["name"] for row in data["sources"])
    assert any("156" in row["name"] for row in data["sources"])


def test_export_uses_runtime_evidence_not_legacy_job_pass():
    snapshot = {"id": "snapshot-1", "status": "COMPLETED", "result": {"status": "completed", "validation": {"passed": True}}}
    assert export_snapshot("nis-1", snapshot, [requirement()])["payload"]["assessment"]["technical_status"] == "NOT_EVALUATED"


def test_exact_ftti_boundary_passes_and_wrong_receiver_or_duplicate_identity_does_not():
    rows = events(); rows[-1]["time_s"] = 2.020
    assert assess(rows)["technical_status"] == "PASS"
    for row in rows[2:]: row["receiver_id"] = "unrelated-receiver"
    assert assess(rows)["technical_status"] == "NOT_EVALUATED"
    rows = events(); rows[-1]["event_id"] = "fault"
    assert assess(rows)["technical_status"] == "NOT_EVALUATED"


def test_runtime_monitor_freezes_safety_report_from_original_emitted_trace(tmp_path):
    import json
    from backend.nis.simulation.runtime_analysis import analyze_runtime_trace
    trace = tmp_path / "universal_trace.jsonl"
    trace.write_text('\n'.join(json.dumps(row) for row in events()), encoding="utf-8")
    report = analyze_runtime_trace({"artifacts": [str(trace)]}, {"engineering_model": {"safety_requirements": [requirement()]},
        "communications": [{"id": "route-1"}], "networks": []})
    assert report["safety_assurance"]["technical_status"] == "PASS"
    assert report["safety_assurance"]["requirements"][0]["checks"][0]["observed_max_latency_ms"] == 2
