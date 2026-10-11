"""E2E evidence must distinguish physical delivery from receiver acceptance."""

import pytest

from backend.app.e2e_assurance import build_e2e_transactions


def frame(index=0, count=1, **changes):
    event = {
        "transaction_id": "route:1", "event_id": f"route:1:segment:{index}",
        "route_id": "route", "origin_release_time_s": 1.0,
        "data_generation_time_s": 0.998, "segment_index": index,
        "segment_count": count, "final_segment": index == count - 1,
        "time_s": 1.008 + index * .004, "network": f"network-{index}",
        "technology": "CAN_FD" if index == 0 else "LIN", "status": "transmitted",
    }
    return {**event, **changes}


def test_delivery_without_receiver_evidence_is_not_e2e_pass():
    transaction = build_e2e_transactions([frame()], {"route": {"deadline_ms": 20}})[0]
    assert transaction["transport_status"] == "DELIVERED"
    assert transaction["transport_latency_ms"] == pytest.approx(8)
    assert transaction["receiver_status"] == "NOT_OBSERVED"
    assert transaction["e2e_latency_ms"] is None
    assert transaction["deadline_status"] == "NOT_EVALUATED"
    assert transaction["requirement_status"] == "NOT_EVALUATED"


def test_explicit_receiver_acceptance_proves_latency_and_data_age():
    accepted = {"transaction_id": "route:1", "event_id": "receiver:1",
                "event_type": "RECEIVER_ACCEPTANCE", "time_s": 1.014}
    route = {"route": {"timing": {"max_e2e_latency_ms": 20, "max_data_age_ms": 25}}}
    transaction = build_e2e_transactions([frame(), accepted], route)[0]
    assert transaction["receiver_status"] == "ACCEPTED"
    assert transaction["receiver_accept_time_s"] == 1.014
    assert transaction["e2e_latency_ms"] == pytest.approx(14)
    assert transaction["data_age_at_accept_ms"] == pytest.approx(16)
    assert transaction["timing_margin_ms"] == pytest.approx(6)
    assert transaction["data_age_margin_ms"] == pytest.approx(9)
    assert transaction["requirement_status"] == "PASS"
    assert transaction["evidence_event_ids"] == ["route:1:segment:0", "receiver:1"]


def test_missing_middle_hop_cannot_claim_delivery_or_acceptance():
    accepted = {"transaction_id": "route:1", "event_type": "RECEIVER_ACCEPTANCE", "time_s": 1.02}
    transaction = build_e2e_transactions([frame(0, 3), frame(2, 3), accepted])[0]
    assert transaction["transport_status"] == "INCOMPLETE"
    assert transaction["receiver_status"] == "UNVERIFIED"
    assert "ACCEPTANCE_EVIDENCE_INVALID" in transaction["findings"]
    assert transaction["requirement_status"] == "NOT_EVALUATED"


def test_late_arrival_proves_deadline_miss_even_without_receiver_observation():
    transaction = build_e2e_transactions([frame(time_s=1.035)],
                                          {"route": {"deadline_ms": 20}})[0]
    assert transaction["receiver_status"] == "NOT_OBSERVED"
    assert transaction["deadline_status"] == "FAIL"
    assert transaction["requirement_status"] == "FAIL"
    assert "E2E_DEADLINE_MISSED" in transaction["findings"]


def test_explicit_rejection_and_stale_data_are_not_passes():
    rejected = frame(receiver_status="REJECTED")
    result = build_e2e_transactions([rejected], {"route": {"deadline_ms": 20}})[0]
    assert result["receiver_status"] == "REJECTED"
    assert result["requirement_status"] == "FAIL"
    stale = frame(receiver_status="ACCEPTED", receiver_accept_time_s=1.015,
                  data_generation_time_s=.96)
    result = build_e2e_transactions([stale], {"route": {"max_data_age_ms": 30}})[0]
    assert result["freshness_status"] == "FAIL"
    assert result["data_age_at_accept_ms"] == pytest.approx(55)


def test_missing_generation_timestamp_does_not_invent_freshness():
    accepted = frame(data_generation_time_s=None, receiver_status="ACCEPTED",
                     receiver_accept_time_s=1.012)
    result = build_e2e_transactions([accepted], {"route": {"max_data_age_ms": 30}})[0]
    assert result["data_age_at_accept_ms"] is None
    assert result["freshness_status"] == "NOT_EVALUATED"
    assert result["requirement_status"] == "NOT_EVALUATED"


def test_explicit_protection_failure_overrides_on_time_acceptance():
    accepted = frame(receiver_status="ACCEPTED", receiver_accept_time_s=1.012,
                     protection_status="FAILED")
    result = build_e2e_transactions([accepted], {"route": {"deadline_ms": 20}})[0]
    assert result["deadline_status"] == "PASS"
    assert result["requirement_status"] == "FAIL"
    assert "E2E_PROTECTION_FAILED" in result["findings"]


def test_uncorrelated_frames_are_not_assigned_an_invented_transaction():
    assert build_e2e_transactions([{"event_id": "raw", "status": "transmitted"}]) == []
