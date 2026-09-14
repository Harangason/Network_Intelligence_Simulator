"""Arbitration order, causal arrivals and bounded work for the CAN dispatcher."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from event_scheduler import EventScheduler
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events


REFERENCE = json.loads((Path(__file__).parent / "fixtures/can_scheduler_reference.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda case: case["name"])
def test_trace_matches_seeded_reference_captured_before_dispatcher_change(case):
    config = deepcopy(case["config"])
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=REFERENCE["seeded_start_utc"])
    actual = [{key: event[key] for key in REFERENCE["event_fields"] if key in event} for event in events]
    assert actual == case["expected"]


def request(name, release=0.0, *, network="a", priority=10, route=None, technology="can_fd"):
    return {"event_id": name, "route_id": route or name, "network": network,
            "technology": technology, "time_s": release, "arbitration_id": priority}


def transmit(event, available, duration):
    network = event["network"]
    start = max(event["time_s"], available.get(network, 0.0))
    available[network] = start + duration
    return start


def test_arrival_during_frame_joins_next_grant_without_preempting_current_frame():
    available = {}
    scheduler = EventScheduler([
        request("blocking", priority=10), request("waiting-low", .001, priority=200),
        request("ethernet-delivery", .002, technology="ethernet", network="ethernet"),
    ], available)
    blocking = scheduler.pop()
    assert blocking["event_id"] == "blocking"
    assert transmit(blocking, available, .010) == 0
    assert scheduler.pop()["event_id"] == "ethernet-delivery"
    # A received gateway segment/ACK enqueues a fresh request while CAN is busy.
    scheduler.enqueue(request("late-high", .003, priority=1))
    high = scheduler.pop()
    assert high["event_id"] == "late-high"
    assert transmit(high, available, .001) == .010
    low = scheduler.pop()
    assert low["event_id"] == "waiting-low"
    assert transmit(low, available, .001) == pytest.approx(.011)
    assert scheduler.pop() is None


def test_new_earlier_request_replaces_future_grant_without_duplicate_execution():
    available = {}
    scheduler = EventScheduler([request("future", .010), request("delivery", .001, technology="ethernet")], available)
    assert scheduler.pop()["event_id"] == "delivery"
    scheduler.enqueue(request("arrived", .002))
    arrived = scheduler.pop()
    assert arrived["event_id"] == "arrived"
    assert transmit(arrived, available, .001) == .002
    future = scheduler.pop()
    assert future["event_id"] == "future"
    assert transmit(future, available, .001) == .010
    assert scheduler.pop() is None


def test_enqueue_on_current_bus_waits_for_actual_serializer_completion():
    available = {}
    scheduler = EventScheduler([request("first"), request("old-low", .001, priority=100)], available)
    first = scheduler.pop()
    scheduler.enqueue(request("new-high", .002, priority=1))
    transmit(first, available, .010)
    high = scheduler.pop()
    assert high["event_id"] == "new-high"
    assert transmit(high, available, .001) == .010
    low = scheduler.pop()
    assert low["event_id"] == "old-low"
    transmit(low, available, .001)
    assert scheduler.pop() is None


def test_independent_bus_grants_do_not_wait_for_other_bus_completion():
    available = {}
    scheduler = EventScheduler([
        request("a-first"), request("a-waiting", .002),
        request("b-first", .001, network="b", technology="can"),
        request("b-second", .003, network="b", technology="can"),
    ], available)
    order = []
    while (event := scheduler.pop()) is not None:
        order.append((event["event_id"], transmit(event, available, .010 if event["network"] == "a" else .001)))
    assert order == [("a-first", 0), ("b-first", .001), ("b-second", .003), ("a-waiting", .010)]


def test_equal_identifier_and_route_are_fifo_by_release_then_insertion_order():
    available = {}
    scheduler = EventScheduler([
        request("blocking", priority=0),
        request("late", .003, route="same"),
        request("first-equal", .001, route="same"),
        request("second-equal", .001, route="same"),
        request("middle", .002, route="same"),
    ], available)
    first = scheduler.pop()
    transmit(first, available, .010)
    order = []
    while (event := scheduler.pop()) is not None:
        order.append(event["event_id"])
        transmit(event, available, .001)
    assert order == ["first-equal", "second-equal", "middle", "late"]


def test_route_name_still_breaks_same_can_identifier_priority_before_fifo():
    available = {"a": .010}
    scheduler = EventScheduler([
        request("z", .001, priority=2), request("a", .003, priority=2),
        request("unspecified", .002, priority=None),
    ], available)
    order = []
    while (event := scheduler.pop()) is not None:
        order.append(event["event_id"])
        transmit(event, available, .001)
    assert order == ["a", "z", "unspecified"]


def test_multicast_observation_does_not_occupy_wire_between_other_frames():
    config = deepcopy(next(case["config"] for case in REFERENCE["cases"] if case["name"] == "multicast"))
    # Force the second observer to be considered after an unrelated frame.
    config["communications"][2]["arbitration_id"] = 30
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=REFERENCE["seeded_start_utc"])
    by_route = {event["route_id"]: event for event in events}
    first, second, middle = (by_route[name] for name in ("first-consumer", "second-consumer", "middle"))
    assert first["physical_transmission_id"] == second["physical_transmission_id"]
    assert second["shared_transmission_observation"]
    assert (first["tx_start_s"], first["tx_end_s"]) == (second["tx_start_s"], second["tx_end_s"])
    assert middle["tx_start_s"] == first["tx_end_s"]


def test_injected_duplicates_remain_separate_transmissions_and_corruption_is_retained():
    config = deepcopy(REFERENCE["cases"][0]["config"])
    config.update(duration_s=.001, duplicate_probability=1, corruption_probability=1)
    config["scenario"] = {"mode": "USER_DEFINED_FAULT", "faults": []}
    config["communications"] = config["communications"][:1]
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=REFERENCE["seeded_start_utc"])
    assert len(events) == 2
    assert all(event["status"] == "corrupted" and event["duplicate_injected"] for event in events)
    assert all(not event.get("shared_transmission_observation") for event in events)
    assert events[1]["tx_start_s"] == events[0]["tx_end_s"]


def test_gateway_upstream_drop_and_max_events_are_preserved():
    config = deepcopy(next(case["config"] for case in REFERENCE["cases"] if case["name"] == "late_gateway_arbitration"))
    config.update(duration_s=.001, max_events=4, dropout_probability=1)
    config["scenario"] = {"mode": "USER_DEFINED_FAULT", "faults": []}
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=REFERENCE["seeded_start_utc"])
    assert len(events) == 4
    forwarded = [event for event in events if event.get("caused_by_event_id")]
    assert forwarded
    by_id = {event["event_id"]: event for event in events}
    for event in forwarded:
        upstream = by_id[event["caused_by_event_id"]]
        assert event["scheduled_time_s"] == upstream["time_s"]
        assert event["status"] == upstream["status"] == "dropped"
        assert event["transmission_attempted"] is False
        assert event["drop_reason"] == "upstream_dropped"


@pytest.mark.parametrize("busy", [False, True], ids=["future-releases", "busy-backlog"])
def test_queue_work_grows_linearly_instead_of_scanning_all_waiters(monkeypatch, busy):
    import event_scheduler

    operations = 0
    inspections = 0
    original_push, original_pop = event_scheduler.heapq.heappush, event_scheduler.heapq.heappop

    def push(*args):
        nonlocal operations
        operations += 1
        return original_push(*args)

    def pop(*args):
        nonlocal operations
        operations += 1
        return original_pop(*args)

    class CountedRequest(dict):
        def get(self, *args):
            nonlocal inspections
            inspections += 1
            return super().get(*args)

        def __getitem__(self, key):
            nonlocal inspections
            inspections += 1
            return super().__getitem__(key)

    monkeypatch.setattr(event_scheduler.heapq, "heappush", push)
    monkeypatch.setattr(event_scheduler.heapq, "heappop", pop)
    work = []
    for count in (500, 1000, 2000):
        operations = inspections = 0
        available = {}
        scheduler = EventScheduler([CountedRequest(request(str(i), 0 if busy else i * .010,
            priority=count - i)) for i in range(count)], available)
        processed = 0
        while (event := scheduler.pop()) is not None:
            transmit(event, available, .001)
            processed += 1
        assert processed == count
        assert operations <= 8 * count + 10
        assert inspections <= 12 * count + 10
        work.append(operations + inspections)
    assert work[1] <= 2 * work[0] + 10
    assert work[2] <= 2 * work[1] + 10
