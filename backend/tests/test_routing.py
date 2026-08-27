from __future__ import annotations

import pytest

from backend.engineering.models import EngineeringValidationError
from backend.engineering.routing.generation import RoutingGenerationService
from backend.engineering.routing.models import normalize_route
from backend.engineering.routing.network_sync import build_network_route_candidates
from backend.engineering.routing.validation import RoutingValidator, detect_routing_loop


SOURCE = "00000000-0000-0000-0000-000000000001"
TARGET = "00000000-0000-0000-0000-000000000002"
SOURCE_INTERFACE = "00000000-0000-0000-0000-000000000011"
TARGET_INTERFACE = "00000000-0000-0000-0000-000000000012"
MESSAGE = "00000000-0000-0000-0000-000000000021"
SIGNAL = "00000000-0000-0000-0000-000000000031"


def route_payload(**overrides):
    route = {
        "name": "Battery status to display",
        "source": {"node_id": SOURCE, "interface_id": SOURCE_INTERFACE, "protocol": "CAN_FD"},
        "payload": {"message_id": MESSAGE, "signal_ids": [SIGNAL]},
        "destinations": [{"node_id": TARGET, "interface_id": TARGET_INTERFACE, "protocol": "CAN_FD"}],
        "route": {"hops": [SOURCE, TARGET], "gateways": [], "transformations": [], "priority": "HIGH"},
        "timing": {"cycle_time_ms": 10, "timeout_ms": 100, "max_latency_ms": 10, "jitter_limit_ms": 2},
        "routing_policy": {"routing_type": "UNICAST", "redundancy": "NONE", "conditions": []},
    }
    route.update(overrides)
    return route


class FakeValidator(RoutingValidator):
    def __init__(self, *, signal_bits=32, source_type="CAN_FD", target_type="CAN_FD", gateway=False):
        self.signal_bits = signal_bits
        self.source_type = source_type
        self.target_type = target_type
        self.gateway = gateway

    def _rows(self, table, ids):
        rows = {}
        for item_id in ids:
            if table == "engineering_hardware_nodes":
                rows[item_id] = {"id": item_id, "name": item_id, "device_type": "Gateway" if self.gateway else "ECU"}
            elif table == "engineering_interfaces":
                rows[item_id] = {
                    "id": item_id,
                    "name": item_id,
                    "hardware_node_id": SOURCE if item_id == SOURCE_INTERFACE else TARGET,
                    "interface_type": self.source_type if item_id == SOURCE_INTERFACE else self.target_type,
                }
            elif table == "engineering_messages":
                rows[item_id] = {"id": item_id, "name": "BatteryStatus", "dlc": 8, "cycle_ms": 10}
            elif table == "engineering_signals":
                rows[item_id] = {"id": item_id, "name": "BatteryVoltage", "message_id": MESSAGE, "length_bits": self.signal_bits}
        return rows

    def _find_duplicates(self, source_node_id, payload, destinations, exclude_route_id):
        return []


class UnmappedValidator(FakeValidator):
    def _physical_path_mapping(self, source_node_id, destination_node_ids):
        return False, destination_node_ids


def test_routing_entry_model_normalizes_governance_and_signal_selection():
    route = normalize_route(route_payload())
    assert route["routing_policy"]["routing_type"] == "UNICAST"
    assert route["payload"]["signal_ids"] == [SIGNAL]
    assert route["status"] == "DRAFT"
    assert route["approval_state"] == "PENDING"


def test_network_editor_governance_values_are_supported():
    route = normalize_route(
        route_payload(origin="NETWORK_EDITOR", status="PENDING_CONFIRMATION")
    )
    assert route["origin"] == "NETWORK_EDITOR"
    assert route["status"] == "PENDING_CONFIRMATION"


def test_manual_route_requires_source_and_destination():
    with pytest.raises(EngineeringValidationError):
        normalize_route({"name": "Broken", "source": {}, "destinations": []})


def test_routing_loop_detection():
    assert detect_routing_loop([SOURCE, TARGET, SOURCE]) == [SOURCE]
    result = FakeValidator().validate(route_payload(route={"hops": [SOURCE, TARGET, SOURCE], "gateways": []}))
    assert any(error["code"] == "ROUTING_LOOP" for error in result["errors"])


def test_protocol_validation_requires_translation():
    result = FakeValidator(target_type="LIN").validate(route_payload())
    assert any(error["code"] == "PROTOCOL_INCOMPATIBLE" for error in result["errors"])


def test_payload_and_latency_validation():
    payload_result = FakeValidator(signal_bits=1024).validate(route_payload())
    assert any(error["code"] == "PAYLOAD_TOO_LARGE" for error in payload_result["errors"])
    latency_route = route_payload(timing={"cycle_time_ms": 10, "max_latency_ms": 0.1, "jitter_limit_ms": 1})
    latency_result = FakeValidator().validate(latency_route)
    assert any(error["code"] == "LATENCY_UNACHIEVABLE" for error in latency_result["errors"])


def test_conditional_and_fallback_validation():
    conditional = route_payload(
        routing_policy={"routing_type": "CONDITIONAL", "redundancy": "PRIMARY", "conditions": []}
    )
    result = FakeValidator().validate(conditional)
    assert any(error["code"] == "CONDITION_MISSING" for error in result["errors"])
    assert any(warning["code"] == "FALLBACK_MISSING" for warning in result["warnings"])


def test_unmapped_route_is_visible_without_becoming_an_automatic_approval():
    result = UnmappedValidator().validate(route_payload())
    assert result["valid"] is True
    assert result["metrics"]["physical_path_mapped"] is False
    assert any(warning["code"] == "UNMAPPED_ROUTE" for warning in result["warnings"])


def test_empty_routing_table_is_not_reported_as_valid():
    result = FakeValidator().validate_table([])

    assert result["valid"] is False
    assert result["route_count"] == 0
    assert result["error_count"] == 1
    assert result["table_errors"][0]["code"] == "ROUTING_TABLE_EMPTY"


def test_network_path_becomes_reviewable_gateway_routing_proposal():
    topology = {
        "nodes": [
            {
                "id": "powertrain",
                "name": "Powertrain",
                "kind": "ecu",
                "engineeringId": SOURCE,
                "ports": [
                    {
                        "id": "pt-can",
                        "bus": "can_fd",
                        "engineeringId": SOURCE_INTERFACE,
                    }
                ],
            },
            {
                "id": "gateway-01",
                "name": "Gateway 01",
                "kind": "gateway",
                "engineeringId": "00000000-0000-0000-0000-000000000003",
                "ports": [
                    {
                        "id": "gw-can",
                        "bus": "can_fd",
                        "engineeringId": "00000000-0000-0000-0000-000000000013",
                    },
                    {
                        "id": "gw-eth",
                        "bus": "automotive_ethernet",
                        "engineeringId": "00000000-0000-0000-0000-000000000014",
                    },
                ],
            },
            {
                "id": "display",
                "name": "VehicleDisplay",
                "kind": "actuator",
                "engineeringId": TARGET,
                "ports": [
                    {
                        "id": "display-eth",
                        "bus": "automotive_ethernet",
                        "engineeringId": TARGET_INTERFACE,
                    }
                ],
            },
        ],
        "edges": [
            {
                "id": "edge-can",
                "source": "powertrain",
                "sourcePort": "pt-can",
                "target": "gateway-01",
                "targetPort": "gw-can",
                "bus": "can_fd",
            },
            {
                "id": "edge-eth",
                "source": "gateway-01",
                "sourcePort": "gw-eth",
                "target": "display",
                "targetPort": "display-eth",
                "bus": "automotive_ethernet",
            },
        ],
    }

    candidates, skipped = build_network_route_candidates("project-a", topology)

    assert skipped == []
    assert len(candidates) == 1
    proposal = candidates[0]
    assert proposal["origin"] == "NETWORK_EDITOR"
    assert proposal["status"] == "PENDING_CONFIRMATION"
    assert proposal["source"]["node_id"] == SOURCE
    assert proposal["destinations"][0]["node_id"] == TARGET
    assert proposal["route"]["gateways"][0]["name"] == "Gateway 01"
    assert proposal["route"]["transformations"] == ["CAN_FD_TO_ETHERNET"]
    assert proposal["description"] == "Proposed from Network Editor"


def test_network_path_without_engineering_identity_is_not_persistable():
    topology = {
        "nodes": [
            {"id": "source", "name": "Source", "kind": "ecu", "ports": []},
            {
                "id": "target",
                "name": "Target",
                "kind": "ecu",
                "engineeringId": TARGET,
                "ports": [],
            },
        ],
        "edges": [
            {
                "id": "edge",
                "source": "source",
                "sourcePort": "source-port",
                "target": "target",
                "targetPort": "target-port",
                "bus": "can_fd",
            }
        ],
    }

    candidates, skipped = build_network_route_candidates("project-a", topology)

    assert candidates == []
    assert skipped[0]["source_id"].startswith("project-a:network-path:")


def test_network_path_accepted_from_routing_table_does_not_duplicate_route():
    topology = {
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "kind": "ecu",
                "engineeringId": SOURCE,
                "ports": [{"id": "source-port", "bus": "can_fd"}],
            },
            {
                "id": "target",
                "name": "Target",
                "kind": "ecu",
                "engineeringId": TARGET,
                "ports": [{"id": "target-port", "bus": "can_fd"}],
            },
        ],
        "edges": [
            {
                "id": "routing-edge",
                "source": "source",
                "sourcePort": "source-port",
                "target": "target",
                "targetPort": "target-port",
                "bus": "can_fd",
                "origin": "ROUTING_TABLE",
                "routingEntryId": "route-existing",
            }
        ],
    }

    candidates, skipped = build_network_route_candidates("project-a", topology)

    assert candidates == []
    assert skipped == []


def test_candidate_ranking_prefers_fewer_hops_and_gateways():
    ranked = RoutingGenerationService().rank_candidate_paths(
        [
            {"hop_count": 4, "gateways": [{"id": "g1"}, {"id": "g2"}], "protocol": "CAN_FD"},
            {"hop_count": 1, "gateways": [], "protocol": "CAN_FD"},
        ]
    )
    assert ranked[0]["hop_count"] == 1
    assert ranked[0]["score"] > ranked[1]["score"]
