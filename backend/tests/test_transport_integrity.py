"""End-to-end regressions for the September 2026 workflow audit findings."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.app.runtime_analysis import analyze_runtime_trace
from backend.engineering.routing import config_builder
from communication_simulator import run_simulation
from hardware_profile import normalize_hardware_config, validate_hardware_profile
from model_based_simulation import MessageCodec, SignalDefinition
from universal_trace import generate_universal_events


@pytest.fixture
def gateway_config(monkeypatch):
    nodes = [{"id": key, "name": key, "device_type": kind, "logical_node_address": index + 1}
        for index, (key, kind) in enumerate((("source", "ECU"), ("gateway", "Gateway"), ("target", "ECU")))]
    interfaces = [{"id": key, "hardware_node_id": node, "name": key, "interface_type": protocol, "configuration": {}}
        for key, node, protocol in (("source-if", "source", "CAN_FD"), ("gateway-in", "gateway", "CAN_FD"),
            ("gateway-out", "gateway", "LIN"), ("target-if", "target", "LIN"))]
    physical = [{"id": item["id"] + "-hw", "hardware_node_id": item["hardware_node_id"],
        "physical_port_ref": item["id"], "capabilities": {}} for item in interfaces]

    class Connection:
        def execute(self, query, _parameters):
            self.rows = (nodes if "FROM engineering_hardware_nodes " in query else
                physical if "FROM engineering_hardware_interfaces " in query else
                interfaces if "FROM engineering_interfaces " in query else [])
            return self

        def fetchall(self):
            return deepcopy(self.rows)

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(config_builder, "get_connection", connection)
    topology = {"nodes": [{"id": item["id"], "engineeringId": item["id"], "ports": [
        {"id": interface["id"], "engineeringId": interface["id"], "hardwareInterfaceId": interface["id"] + "-hw",
            "bus": "can_fd" if interface["interface_type"] == "CAN_FD" else "lin",
            "physicalNetworkId": "input-bus" if interface["interface_type"] == "CAN_FD" else "output-bus"}
        for interface in interfaces if interface["hardware_node_id"] == item["id"]]} for item in nodes],
        "edges": [
            {"id": "edge-in", "source": "source", "target": "gateway", "sourcePort": "source-if", "targetPort": "gateway-in",
                "bus": "can_fd", "physicalNetworkId": "input-bus", "routingEntryId": "canonical-route"},
            {"id": "edge-out", "source": "gateway", "target": "target", "sourcePort": "gateway-out", "targetPort": "target-if",
                "bus": "lin", "physicalNetworkId": "output-bus", "routingEntryId": "canonical-route"},
        ]}
    route = {"id": "canonical-route", "route_code": "RT-1", "name": "Source through gateway to target", "approval_state": "APPROVED",
        "source": {"node_id": "source", "interface_id": "source-if", "network_id": "input-bus", "protocol": "CAN_FD"},
        "destinations": [{"node_id": "target", "interface_id": "target-if", "network_id": "output-bus", "protocol": "LIN"}],
        "route": {"gateways": [{"node_id": "gateway"}]},
        "timing": {"cycle_time_ms": 20, "max_latency_ms": 20, "jitter_limit_ms": 5, "timeout_ms": 50},
        "payload": {"message_id": "message", "signal_ids": ["temperature"], "payload_bytes": 2}}
    config = config_builder.CommunicationConfigBuilder().build([route], topology=topology,
        parameters={"technology": "can_fd", "bitrate": 500_000, "jitter_ms": 1, "gateway_delay_ms": 2,
            "networks": [{"id": "input-bus", "bitrate": 500_000, "data_bitrate": 2_000_000},
                         {"id": "output-bus", "bitrate": 19_200} ]})["config"]
    config.update(duration_s=.12, seed=0, formats=["universal-jsonl", "universal-csv"],
        topology=topology,
        scenario={"mode": "NORMAL", "faults": []},
        engineering_model={"nodes": nodes, "routes": [route], "interfaces": interfaces, "hardware_interfaces": physical,
            "messages": [{"id": "message", "cycle_ms": 20, "interface_id": "source-if"}],
            "signals": [{"id": "temperature", "name": "Temperature", "message_id": "message", "start_bit": 0,
                "length_bits": 16, "byte_order": "little_endian", "factor": .1, "offset_value": -40,
                "min_value": -40, "max_value": 215, "unit": "degC"}],
            "behaviors": [{"signal_id": "temperature", "behavior_type": "CONSTANT", "parameters": {"value": 100}}]})
    return config


def test_capacity_uses_the_same_protocol_bitrate_and_physical_ports_per_segment(gateway_config, monkeypatch):
    from backend.engineering.capacity import service as capacity
    from backend.engineering.workflow.models import default_versions, default_statuses
    config = gateway_config
    model = config["engineering_model"]
    object_keys = {"HardwareNode": "nodes", "Interface": "interfaces", "HardwareNetworkInterface": "hardware_interfaces",
        "Signal": "signals", "Message": "messages"}
    monkeypatch.setattr(capacity, "list_objects", lambda kind, **_: deepcopy(model.get(object_keys.get(kind), [])))
    monkeypatch.setattr(capacity, "list_routes", lambda **_: deepcopy(model["routes"]))
    service = capacity.CapacityTimingService("isolated-segments")
    monkeypatch.setattr(service.workflow, "get", lambda: {"project_id": "isolated-segments", "versions": default_versions(),
        "statuses": {key: "COMPLETE" for key in default_statuses()}, "parameters": config["parameters"], "topology": config["topology"]})
    monkeypatch.setattr(service, "latest", lambda: None)
    results = service.calculate(persist=False)["results"]
    networks = {item["network_id"]: item for item in results["networks"]}
    assert (networks["input-bus"]["protocol"], networks["input-bus"]["bitrate"]) == ("CAN_FD", 500_000)
    assert (networks["output-bus"]["protocol"], networks["output-bus"]["bitrate"]) == ("LIN", 19_200)
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)
    for metric in results["routes"]:
        event = next(item for item in events if item["network"] == metric["network_id"])
        assert metric["physical_path_resolved"]
        assert metric["segment_transmission_latency_ms"] == pytest.approx(event["transmission_latency_ms"])
        expected = event["transmission_latency_ms"] / config["communications"][0]["cycle_ms"] * 100
        assert metric["average_load_percent"] == pytest.approx(expected, abs=.0001)


def test_canonical_requirements_and_both_physical_segments_reach_actual_trace(gateway_config):
    config = gateway_config
    communication = config["communications"][0]
    assert (communication["maximum_latency_ms"], communication["deadline_ms"], communication["jitter_limit_ms"], communication["timeout_ms"]) == (20, 20, 5, 50)
    profile = normalize_hardware_config(config)
    assert validate_hardware_profile(profile)["valid"]
    _, events = generate_universal_events(config, profile, start_utc=1_700_000_000)
    assert {event["network"] for event in events} == {"input-bus", "output-bus"}
    by_id = {event["event_id"]: event for event in events}
    outputs = [event for event in events if event["final_segment"]]
    assert outputs and len(outputs) * 2 == len(events)
    for event in outputs:
        upstream = by_id[event["caused_by_event_id"]]
        assert event["scheduled_time_s"] == upstream["time_s"]
        assert event["sender_hardware"] == "gateway" and event["receiver_hardware"] == ["target"]
        assert event["sender_interface"] == "gateway-out"
        assert event["payload_hex"] == upstream["payload_hex"]
        assert event["configured_bitrate"] == 19_200
        assert upstream["configured_bitrate"] == 500_000
        assert event["end_to_end_latency_ms"] >= upstream["transmission_latency_ms"] + event["transmission_latency_ms"] + 2
        assert event["route_ref"] == event["canonical_route_id"] == "canonical-route"
    runtime = analyze_runtime_trace({"model_simulation": {"frames": events}}, config)
    assert len(runtime["routes"]) == 1 and len(runtime["networks"]) == 2
    assert runtime["routes"][0]["canonical_route_id"] == "canonical-route"
    assert runtime["routes"][0]["status"] == "PASS"
    assert runtime["routes"][0]["jitter_limit_ms"] == 5


def test_message_owned_signals_are_transported_without_redundant_signal_ids(gateway_config):
    config = gateway_config
    config["communications"][0]["signal_ids"] = []
    for segment in config["communications"][0]["segments"]:
        segment["signal_ids"] = []
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)
    assert events and all(event["signals"][0]["signal_id"] == "temperature" for event in events)


@pytest.mark.parametrize("amplitude", [0, .1])
def test_runtime_uses_configured_jitter_amplitude_in_milliseconds(gateway_config, amplitude):
    config = gateway_config
    config["parameters"]["jitter_ms"] = amplitude
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)
    assert all(abs(event["injected_jitter_ms"]) <= amplitude for event in events)
    if amplitude:
        assert any(event["injected_jitter_ms"] != 0 for event in events)


@pytest.mark.parametrize("protocol", ["udp", "tcp"])
def test_forwarded_ethernet_has_its_own_session_and_acknowledges_actual_arrival(gateway_config, protocol, tmp_path):
    config = gateway_config
    config.update(output_dir=str(tmp_path), transport_protocol=protocol,
        restbus_session={"enabled": True, "response_delay_ms": 1, "heartbeat_interval_s": .05})
    config["engineering_model"]["behaviors"][0]["parameters"].update(formula="upstream",
        transport_inputs={"upstream": {"signal_id": "temperature", "fallback": 100, "max_age_ms": 100}})
    network = next(item for item in config["networks"] if item["id"] == "output-bus")
    network.update(technology="ethernet", bitrate=1_000_000)
    config["communications"][0]["segments"][1]["technology"] = "ethernet"
    for device in config["hardware"]["devices"]:
        for interface in device["interfaces"]:
            if interface["network"] == "output-bus":
                interface["technology"] = "ethernet"
    result = run_simulation(config)
    path = next(Path(item) for item in result["artifacts"] if str(item).endswith("universal_trace.jsonl"))
    events = [json.loads(line) for line in path.read_text().splitlines()]
    output = [event for event in events if event["network"] == "output-bus"]
    assert {"DATA", "DATA_ACK", "HEARTBEAT", "HEARTBEAT_ACK"} <= {event.get("protocol_event") for event in output}
    handshake = "TCP_ACK" if protocol == "tcp" else "SESSION_HELLO_ACK"
    assert any(event.get("protocol_event") == handshake for event in output)
    assert all(not event.get("signals") and not event.get("caused_by_event_id")
        for event in output if event.get("traffic_type") == "CONTROL")
    data = [event for event in output if event.get("protocol_event") == "DATA"]
    acknowledgements = {event["event_id"].split(":ack:")[0]: event for event in output if event.get("protocol_event") == "DATA_ACK"}
    for event in data:
        assert event["sender_hardware"] == "gateway" and event["signals"][0]["signal_id"] == "temperature"
        if event["time_s"] + .002 < config["duration_s"]:
            ack = acknowledgements[event["event_id"]]
            assert ack["scheduled_time_s"] == pytest.approx(event["time_s"] + .001)
            assert ack["session_id"] == event["session_id"]
    metric = analyze_runtime_trace(result, config)["routes"][0]
    assert metric["requirement_statuses"]["timeout"] == "PASS"
    # TCP establishment can violate the configured 5 ms reception jitter;
    # session setup must remain visible in the requirement verdict.
    assert metric["status"] == ("FAIL" if metric["jitter_violations"] else "PASS")


@pytest.mark.parametrize("network", ["input-bus", "output-bus"])
def test_segment_failure_changes_final_delivery_without_fictitious_other_bus_traffic(gateway_config, network):
    config = gateway_config
    config["scenario"] = {"mode": "USER_DEFINED_FAULT", "faults": [{"scope": "NETWORK", "type": "BUS_OFF",
        "target": {"id": network}, "start_s": 0, "end_s": 1}]}
    _, events = generate_universal_events(config, normalize_hardware_config(config), start_utc=1_700_000_000)
    assert all(event["status"] == "dropped" for event in events if event["final_segment"])
    if network == "output-bus":
        assert all(event["status"] == "transmitted" for event in events if not event["final_segment"])
    else:
        assert all(event["transmission_attempted"] is False and event["transmission_latency_ms"] == 0
            for event in events if event["final_segment"])
    runtime = analyze_runtime_trace({"model_simulation": {"frames": events}}, config)
    assert runtime["routes"][0]["status"] == "FAIL"
    assert runtime["routes"][0]["drop_rate"] == 1
    assert runtime["routes"][0]["timeouts"] > 0


@pytest.mark.parametrize("receptions", [[], [.08], [.001]])
def test_no_first_or_final_reception_cannot_pass_timeout(receptions):
    frames = [{"route_id": "r", "network": "n", "status": "transmitted", "time_s": time,
        "configured_cycle_ms": 10, "end_to_end_latency_ms": 1} for time in receptions]
    config = {"duration_s": .1, "communications": [{"id": "r", "cycle_ms": 10, "timeout_ms": 20}]}
    metric = analyze_runtime_trace({"model_simulation": {"frames": frames}}, config)["routes"][0]
    assert metric["status"] == "FAIL" and metric["timeouts"] >= 1


def test_absent_requirements_or_insufficient_samples_are_not_evaluated():
    frames = [{"route_id": "r", "network": "n", "status": "transmitted", "time_s": .001,
        "configured_cycle_ms": 10, "end_to_end_latency_ms": 1}]
    config = {"duration_s": .01, "communications": [{"id": "r"}]}
    assert analyze_runtime_trace({"model_simulation": {"frames": frames}}, config)["routes"][0]["status"] == "NOT_EVALUATED"
    config["communications"][0]["jitter_limit_ms"] = 5
    assert analyze_runtime_trace({"model_simulation": {"frames": frames}}, config)["routes"][0]["status"] == "NOT_EVALUATED"


@pytest.mark.parametrize("fault", [
    {"scope": "SIGNAL", "type": "SIGNAL_OFFSET", "target": {"id": "temperature"}, "magnitude": 20},
    {"scope": "NETWORK", "type": "GATEWAY_DELAY", "target": {"id": "gateway"}, "delay_ms": 40},
    {"scope": "NETWORK", "type": "BUS_OFF", "target": {"id": "output-bus"}},
])
def test_golden_export_is_an_independent_normal_transport_with_consistent_payload(gateway_config, tmp_path, fault):
    config = gateway_config
    config["output_dir"] = str(tmp_path)
    config["scenario"] = {"mode": "USER_DEFINED_FAULT", "faults": [{**fault, "start_s": .02, "end_s": .09}]}
    result = run_simulation(config)
    golden_path = next(Path(path) for path in result["artifacts"] if str(path).endswith("golden_trace.jsonl"))
    golden = [json.loads(line) for line in golden_path.read_text().splitlines()]
    clean = deepcopy(config)
    clean["scenario"] = {"mode": "NORMAL", "faults": []}
    start = golden[0]["timestamp_unix"] - golden[0]["time_s"]
    _, normal = generate_universal_events(clean, normalize_hardware_config(clean), start_utc=start)
    assert [(event["event_id"], event["time_s"], event["payload_hex"], event["status"]) for event in golden] == [
        (event["event_id"], event["time_s"], event["payload_hex"], event["status"]) for event in normal]
    definition = SignalDefinition.from_record(config["engineering_model"]["signals"][0])
    for event in golden:
        assert event["faults"] == []
        for sample in event["signals"]:
            assert sample["fault_state"] == []
            assert sample["value"] == pytest.approx(MessageCodec.decode(event["payload_hex"], definition))
            assert sample["actual_value"] == sample["value"]
