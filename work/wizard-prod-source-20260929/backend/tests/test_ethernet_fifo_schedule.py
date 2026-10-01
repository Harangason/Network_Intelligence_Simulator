"""Ethernet timing uses a bounded FIFO model per confirmed full-duplex TX port."""

from copy import deepcopy

import pytest

from backend.engineering.capacity.dimensioning import bus_schedule
from backend.engineering.capacity import service as capacity_service_module
from backend.engineering.capacity.service import CapacityTimingService
from backend.engineering.workflow.models import default_statuses, default_versions


def stream(stream_id, *, port="port-a", node="ecu-a", period=10, duration=0.1, **extra):
    return {
        "stream_id": stream_id,
        "route_id": f"route-{stream_id}",
        "message_id": f"message-{stream_id}",
        "network_id": "ethernet-backbone",
        "protocol": "ETHERNET",
        "cycle_ms": period,
        "bitrate": 1_000_000_000,
        "payload_bytes": 64,
        "calculation_model": "ETHERNET_WIRE_ESTIMATE",
        "segment_transmission_latency_ms": duration,
        "physical_path_resolved": True,
        "physical_source": {"node_id": node, "physical_port_ref": port},
        "queue_policy": "FIFO",
        **extra,
    }


def test_ethernet_bounds_contention_on_same_egress_port():
    rows = [stream("a"), stream("b", period=20, duration=0.2)]

    result = bus_schedule(rows, {})

    assert result["status"] == "FEASIBLE_UNDER_ASSUMPTIONS"
    assert result["model"] == "ETHERNET_FULL_DUPLEX_FIFO_RESPONSE_BOUND_V1"
    assert result["responses"] == pytest.approx({"a": 0.3, "b": 0.3})
    assert len(result["port_schedules"]) == 1
    assert result["port_schedules"][0]["source_port_id"] == "port-a"
    assert any("Kein TAS/CBS/TSN" in item for item in result["assumptions"])


def test_ethernet_full_duplex_ports_are_scheduled_independently():
    rows = [stream("a", port="port-a", duration=1), stream("b", port="port-b", duration=1)]

    result = bus_schedule(rows, {})

    assert result["status"] == "FEASIBLE_UNDER_ASSUMPTIONS"
    assert result["nominal_load_percent"] == 10
    assert len(result["port_schedules"]) == 2
    assert result["responses"] == pytest.approx({"a": 1, "b": 1})


def test_ethernet_does_not_claim_bounds_without_confirmed_physical_egress():
    row = stream("a")
    row["physical_path_resolved"] = False

    result = bus_schedule([row], {})

    assert result["status"] == "MODEL_INCONSISTENT"
    row = stream("a")
    row["physical_source"] = {"node_id": "ecu-a"}
    result = bus_schedule([row], {})
    assert result["status"] == "PROFILE_INCOMPLETE"
    assert "TX-Port" in result["reasons"][0]


def test_ethernet_only_accepts_profile_rates_and_fifo_queueing():
    row = stream("a", bitrate=123_456_789)
    result = bus_schedule([row], {})
    assert result["status"] == "PROFILE_INCOMPLETE"

    row = stream("a", queue_policy="STRICT_PRIORITY")
    result = bus_schedule([row], {})
    assert result["status"] == "PROFILE_INCOMPLETE"
    assert "FIFO" in result["reasons"][0]


def test_ethernet_overload_is_checked_per_transmit_port():
    rows = [stream("a", duration=6), stream("b", duration=6)]

    result = bus_schedule(rows, {})

    assert result["status"] == "OVERLOAD"
    assert result["nominal_load_percent"] == 120


def test_ethernet_response_bounds_honor_existing_latency_constraints():
    rows = [stream("a", duration=1, max_latency_ms=0.5)]

    result = bus_schedule(deepcopy(rows), {})

    assert result["status"] == "CONSTRAINT_VIOLATION"
    assert result["responses"]["a"] == pytest.approx(1)
    assert "max_latency_ms" in result["reasons"][0]


def test_capacity_service_exposes_the_verified_ethernet_bound_to_preflight(monkeypatch):
    state = {
        "project_id": "ethernet-capacity-test",
        "versions": default_versions(),
        "statuses": {**default_statuses(), "engineering_model": "COMPLETE", "routing": "APPROVED",
                     "network_editor": "COMPLETE", "parameters": "APPROVED"},
        "parameters": {"technology": "ethernet", "bitrate": 1_000_000_000, "cycle_ms": 20,
                        "payload_bytes": 64, "queue_policy": "FIFO"},
        "topology": {
            "nodes": [
                {"id": "graph-source", "engineeringId": "source-node",
                 "ports": [{"id": "source-port", "hardwareInterfaceId": "source-eth-port", "bus": "ETHERNET"}]},
                {"id": "graph-switch", "engineeringId": "switch-node", "kind": "switch",
                 "ports": [{"id": "switch-in", "hardwareInterfaceId": "switch-eth-in", "bus": "ETHERNET"},
                           {"id": "switch-out", "hardwareInterfaceId": "switch-eth-out", "bus": "ETHERNET"}]},
                {"id": "graph-target", "engineeringId": "target-node",
                 "ports": [{"id": "target-port", "hardwareInterfaceId": "target-eth-port", "bus": "ETHERNET"}]},
            ],
            "edges": [
                {"id": "ethernet-edge-1", "source": "graph-source", "sourcePort": "source-port",
                 "target": "graph-switch", "targetPort": "switch-in", "bus": "ETHERNET",
                 "physicalNetworkId": "eth-backbone", "routingEntryIds": ["ethernet-route"]},
                {"id": "ethernet-edge-2", "source": "graph-switch", "sourcePort": "switch-out",
                 "target": "graph-target", "targetPort": "target-port", "bus": "ETHERNET",
                 "physicalNetworkId": "eth-backbone", "routingEntryIds": ["ethernet-route"]},
            ],
        },
    }
    route = {
        "id": "ethernet-route", "route_code": "ETH-01", "name": "Ethernet telemetry",
        "status": "APPROVED", "approval_state": "APPROVED",
        "source": {"node_id": "source-node", "protocol": "ETHERNET", "network_id": "eth-backbone"},
        "payload": {"message_id": "ethernet-message", "signal_ids": [], "payload_bytes": 64},
        "destinations": [{"node_id": "target-node", "protocol": "ETHERNET", "network_id": "eth-backbone"}],
        "route": {"gateways": []}, "timing": {"cycle_time_ms": 20, "max_latency_ms": 10},
        "routing_policy": {"priority": "NORMAL"},
    }
    objects = {
        "Message": [{"id": "ethernet-message", "name": "Telemetry", "dlc": 64, "cycle_ms": 20, "configuration": {}}],
        "Signal": [], "Interface": [], "HardwareNode": [], "HardwareNetworkInterface": [],
    }
    service = CapacityTimingService("ethernet-capacity-test")
    monkeypatch.setattr(service.workflow, "get", lambda: state)
    monkeypatch.setattr(service, "latest", lambda: None)
    monkeypatch.setattr(capacity_service_module, "list_routes", lambda limit=500, offset=0: [route])
    monkeypatch.setattr(capacity_service_module, "list_objects",
                        lambda object_type, limit=500, offset=0: objects.get(object_type, []))

    result = service.calculate(persist=False)
    network = result["results"]["networks"][0]

    assert network["communication_schedule"]["model"] == "ETHERNET_FULL_DUPLEX_FIFO_RESPONSE_BOUND_V1"
    assert network["timing_verified"] is True
    assert network["response_time_bound_ms"] is not None
    assert len(network["communication_schedule"]["port_schedules"]) == 2
    assert not any(item["code"].startswith("COMMUNICATION_") for item in result["findings"])
    assert all(item["timing_verified"] is False for item in result["results"]["routes"])
    assert all(item["response_time_bound_ms"] is None for item in result["results"]["routes"])
    assert any(item["code"] == "ETHERNET_SWITCH_DELAY_UNVERIFIED" for item in result["findings"])
