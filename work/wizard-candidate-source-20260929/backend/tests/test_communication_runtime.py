from copy import deepcopy
from backend.engineering.capacity.runtime_plan import apply_runtime_plan
from backend.tests.test_model_based_simulation import simulation_config
from hardware_profile import normalize_hardware_config
from universal_trace import generate_universal_events


def test_runtime_splits_frames_and_uses_canonical_period_over_old_route_copy():
    config = {"communications": [{"id": "r", "routing_entry_id": "r", "network_id": "lin", "cycle_ms": 5, "message_ids": ["a", "b"]}],
              "parameters": {"communication_schedule": {"version": "v1", "networks": [{"network_id": "lin", "slots": [
                  {"message_id": "a", "route_ids": ["r"], "period_ms": 50, "offset_ms": 10, "duration_ms": 5}]}]}}}
    messages = [{"id": "a", "cycle_ms": 5, "dlc": 2, "message_id_hex": "0x10", "configuration": {"communication_contract": {"transmission": {"period_ms": 50}}}},
                {"id": "b", "cycle_ms": 100, "dlc": 4}]
    apply_runtime_plan(config, messages)
    a, b = config["communications"]
    assert a["cycle_ms"] == 50 and b["cycle_ms"] == 100
    assert a["phase_ms"] == 10 and a["arbitration_id"] == 16
    assert a["payload_bytes"] == 2 and b["payload_bytes"] == 4


def test_runtime_can_arbitrates_waiting_arrivals_not_only_simultaneous_releases(tmp_path):
    config = simulation_config(tmp_path)
    config["engineering_model"] = {}
    config["duration_s"] = .003
    base = config["communications"][0]
    config["communications"] = [{**base, "id": name, "phase_ms": phase, "arbitration_id": identifier, "cycle_ms": 50,
                                 "signal_ids": [], "message_ids": [name]} for name, phase, identifier in
                                 [("blocking", 0, 10), ("low", .005, 200), ("high", .006, 1)]]
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    assert [event["route_id"] for event in events] == ["blocking", "high", "low"]
    assert all(events[i]["tx_end_s"] <= events[i+1]["tx_start_s"] for i in range(2))


def test_runtime_broadcast_does_not_occupy_the_wire_twice(tmp_path):
    config = simulation_config(tmp_path)
    base = config["communications"][0]
    base["message_ids"] = ["msg-1"]
    config["communications"].append({**deepcopy(base), "id": "second-consumer"})
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    first = [item for item in events if item["sequence"] == 0]
    assert len(first) == 2
    assert first[0]["tx_start_s"] == first[1]["tx_start_s"]
    assert first[0]["physical_transmission_id"] == first[1]["physical_transmission_id"]
    assert sum(bool(item.get("shared_transmission_observation")) for item in first) == 1


def test_gateway_does_not_inherit_source_bus_schedule():
    config = {'duration_s': .25, 'seed': 42, 'max_events': 100, 'formats': [],
        'networks': [{'id': 'local', 'technology': 'lin', 'bitrate': 19200},
                     {'id': 'backbone', 'technology': 'can_fd', 'bitrate': 500000, 'data_bitrate': 2000000}],
        'hardware': {'devices': [
            {'id': 'sensor', 'name': 'Sensor', 'type': 'sensor', 'interfaces': [{'id': 's', 'technology': 'lin', 'network': 'local'}]},
            {'id': 'gateway', 'name': 'Gateway', 'type': 'gateway', 'interfaces': [
                {'id': 'gin', 'technology': 'lin', 'network': 'local'}, {'id': 'gout', 'technology': 'can_fd', 'network': 'backbone'}]},
            {'id': 'ecu', 'name': 'ECU', 'type': 'ecu', 'interfaces': [{'id': 'd', 'technology': 'can_fd', 'network': 'backbone'}]}]},
        'communications': [{'id': 'route', 'network_id': 'local', 'technology': 'lin', 'cycle_ms': 100,
            'payload_bytes': 2, 'message_ids': ['m'], 'lin_slot': {'period_ms': 100, 'offset_ms': 0, 'duration_ms': 5},
            'phase_ms': 0, 'segments': [
                {'id': 'route-0', 'segment_index': 0, 'segment_count': 2, 'network_id': 'local', 'technology': 'lin', 'sender_interface': 's', 'receiver_interfaces': ['gin']},
                {'id': 'route-1', 'segment_index': 1, 'segment_count': 2, 'network_id': 'backbone', 'technology': 'can_fd', 'sender_interface': 'gout', 'receiver_interfaces': ['d']}]}]}
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1700000000)
    output = [event for event in events if event['network'] == 'backbone']
    assert len(output) == 3
    assert all(event['lin_slot'] is None and event['status'] == 'transmitted' for event in output)
    assert max(event['end_to_end_latency_ms'] for event in output) < 10
