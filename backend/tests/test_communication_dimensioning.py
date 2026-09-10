from backend.engineering.capacity.dimensioning import bus_schedule, dimension_communications, policy_for, unique_streams
from backend.engineering.capacity.calculators import estimate_frame


def stream(index, period=20, protocol="LIN", **extra):
    frame = estimate_frame(protocol, 2, {"bitrate": 19200 if protocol == "LIN" else 500000})
    return {"stream_id": str(index), "route_id": f"r{index}", "message_id": f"m{index}", "name": f"Messung {index}",
            "network_id": "bus", "producer": f"p{index}", "cycle_ms": period, "protocol": protocol,
            "payload_bytes": 2, "bitrate": 19200 if protocol == "LIN" else 500000,
            "segment_transmission_latency_ms": frame.transmission_time_s * 1000,
            "arbitration_id": index + 1, **extra}


PARAMETERS = {"industry": "automotive"}


def test_complete_lin_frame_counts_checksum():
    assert estimate_frame("LIN", 2, {"bitrate": 19200}).frame_bits == 64


def test_eight_lin_measurements_dimension_to_fifty_and_reserve_real_slots():
    result = dimension_communications([stream(i) for i in range(8)], PARAMETERS)
    bus = result["networks"][0]
    assert bus["selected_floor_ms"] == 50
    assert bus["schedule"]["slot_load_percent"] == 80
    assert round(bus["schedule"]["nominal_load_percent"], 3) == 53.333
    assert {c["after_ms"] for c in result["changes"]} == {50}
    occupied = set()
    for slot in bus["schedule"]["slots"]:
        for start in range(int(slot["offset_ms"]), int(bus["schedule"]["hyperperiod_ms"]), int(slot["period_ms"])):
            positions = set(range(start, start + int(slot["duration_ms"])))
            assert not positions & occupied
            occupied |= positions


def test_slow_periods_and_explicit_locks_are_preserved():
    result = dimension_communications([stream(0, 100), stream(1, 25, transmission_contract={"period_locked": True})], PARAMETERS)
    assert {c["message_id"]: c["after_ms"] for c in result["changes"]} == {"m0": 100}


def test_hard_freshness_cannot_be_relaxed_to_make_bus_green():
    result = dimension_communications([stream(i, freshness_ms=25) for i in range(8)], PARAMETERS)
    assert result["status"] == "PARTIAL"
    assert result["changes"] == []


def test_explicit_jitter_limit_is_not_replaced_by_a_load_based_estimate():
    result = dimension_communications([stream(0, jitter_budget_ms=0.1)], PARAMETERS)
    assert result["status"] == "PARTIAL"
    assert result["changes"] == []
    assert any("Jittergrenze" in reason for attempt in result["networks"][0]["attempts"] for reason in attempt["reasons"])


def test_broadcast_counts_once_and_uses_strictest_consumer_deadline():
    first = stream(1, max_latency_ms=20)
    second = {**first, "route_id": "other", "max_latency_ms": 10}
    unique = unique_streams([first, second])
    assert len(unique) == 1
    assert unique[0]["max_latency_ms"] == 10
    assert len(unique[0]["route_ids"]) == 2
    assert unique_streams(unique) == unique


def test_inconsistent_duplicate_not_silently_deduplicated():
    rows = unique_streams([stream(1), stream(1, 50)])
    assert bus_schedule(rows, policy_for(PARAMETERS))["status"] == "MODEL_INCONSISTENT"


def test_can_priority_includes_lower_priority_blocking_and_competing_traffic():
    rows = [stream(0, protocol="CAN"), stream(1, protocol="CAN"), stream(2, protocol="CAN")]
    result = bus_schedule(rows, policy_for(PARAMETERS))
    assert result["status"] == "FEASIBLE_UNDER_ASSUMPTIONS"
    own = rows[0]["segment_transmission_latency_ms"]
    assert result["responses"]["0"] >= own * 2
    assert result["responses"]["2"] >= own * 3


def test_missing_identifier_and_event_bounds_never_pass():
    assert bus_schedule([stream(0, protocol="CAN", arbitration_id=None)], policy_for(PARAMETERS))["status"] == "PROFILE_INCOMPLETE"
    assert bus_schedule([stream(0, traffic_profile_incomplete=True)], policy_for(PARAMETERS))["status"] == "PROFILE_INCOMPLETE"


def test_history_is_rechecked_not_inherited():
    baseline = dimension_communications([stream(i) for i in range(8)], PARAMETERS)
    history = [{**baseline["networks"][0], "selected_floor_ms": 20, "snapshot_id": "old"}]
    result = dimension_communications([stream(i) for i in range(8)], PARAMETERS, history)
    assert result["networks"][0]["selected_floor_ms"] == 50
    assert result["history_matches"] == ["bus"]


def test_rule_not_silently_applied_to_other_industries():
    assert dimension_communications([stream(0, 5)], {"industry": "medical"})["status"] == "DISABLED"


def test_shared_can_ethernet_period_obeys_policy_without_claiming_ethernet_timing():
    can = stream(0, 10, protocol="CAN")
    ethernet = {**can, "network_id": "eth", "protocol": "ETHERNET", "segment_transmission_latency_ms": .01}
    plan = dimension_communications([can, ethernet], PARAMETERS)
    assert plan["status"] == "PARTIAL"
    assert plan["changes"][0]["after_ms"] == 20
    assert plan["changes"][0]["evaluation"] == "POLICY_ONLY_UNVERIFIED"
    assert next(n for n in plan["networks"] if n["network_id"] == "eth")["status"] == "UNRESOLVED"
    # An explicit locked contract still wins over generated project defaults.
    for row in (can, ethernet): row["transmission_contract"] = {"period_locked": True}
    assert dimension_communications([can, ethernet], PARAMETERS)["changes"] == []
