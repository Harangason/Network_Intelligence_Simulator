from __future__ import annotations

import pytest

from backend.engineering.models import EngineeringValidationError
from backend.engineering.routing.generation import RoutingGenerationService
from backend.engineering.routing.models import normalize_route
from backend.engineering.routing.network_sync import build_network_route_candidates, enrich_route_from_linked_topology
from backend.engineering.routing import repository as routing_repository
from backend.engineering.routing.validation import RoutingValidator, detect_routing_loop


SOURCE = "00000000-0000-0000-0000-000000000001"
TARGET = "00000000-0000-0000-0000-000000000002"
SOURCE_INTERFACE = "00000000-0000-0000-0000-000000000011"
TARGET_INTERFACE = "00000000-0000-0000-0000-000000000012"
MESSAGE = "00000000-0000-0000-0000-000000000021"
MESSAGE_2 = "00000000-0000-0000-0000-000000000022"
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


def test_routing_entry_model_preserves_multiple_messages_with_legacy_primary():
    route = normalize_route(route_payload(payload={
        "message_id": MESSAGE,
        "message_ids": [MESSAGE, MESSAGE_2, MESSAGE],
        "signal_ids": [SIGNAL],
    }))

    assert route["payload"]["message_id"] == MESSAGE
    assert route["payload"]["message_ids"] == [MESSAGE, MESSAGE_2]
    assert route["payload"]["signal_ids"] == [SIGNAL]


def test_routing_validator_accepts_signals_from_any_selected_message():
    result = FakeValidator().validate(route_payload(payload={
        "message_id": MESSAGE,
        "message_ids": [MESSAGE, MESSAGE_2],
        "signal_ids": [SIGNAL],
    }))

    assert not any(error["code"] in {"MESSAGE_NOT_FOUND", "SIGNAL_MESSAGE_MISMATCH"} for error in result["errors"])


def test_network_editor_governance_values_are_supported():
    route = normalize_route(
        route_payload(origin="NETWORK_EDITOR", status="PENDING_CONFIRMATION")
    )
    assert route["origin"] == "NETWORK_EDITOR"
    assert route["status"] == "PENDING_CONFIRMATION"


def test_route_listing_keeps_edited_revisions_in_their_logical_position(monkeypatch):
    class Connection:
        def __init__(self):
            self.query = ""
            self.values = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, values):
            self.query = query.as_string()
            self.values = values
            return self

        def fetchall(self):
            return []

    connection = Connection()
    monkeypatch.setattr(routing_repository, "get_connection", lambda: connection)
    monkeypatch.setattr(routing_repository, "current_project_id", lambda: "project-a")

    assert routing_repository.list_routes() == []
    assert "MIN(history.created_at)" in connection.query
    assert "revision DESC" in connection.query
    assert "modified_at DESC" not in connection.query
    assert connection.values == ["project-a", 200, 0]


def test_editing_approved_route_updates_same_record(monkeypatch):
    route_id = "00000000-0000-0000-0000-000000000099"
    current = {
        **normalize_route(route_payload()),
        "id": route_id,
        "route_code": "RT-EXAMPLE",
        "revision": 3,
        "status": "APPROVED",
        "review_state": "REVIEWED",
        "approval_state": "APPROVED",
        "approved_at": "2026-08-28T10:00:00+00:00",
        "approved_by": "reviewer",
    }

    class Connection:
        def __init__(self):
            self.queries = []
            self.row = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, values):
            query_text = query.as_string() if hasattr(query, "as_string") else str(query)
            self.queries.append((query_text, values))
            if query_text.startswith("UPDATE engineering_routing_entries"):
                self.row = {
                    **current,
                    "name": "Updated route",
                    "revision": 4,
                    "status": "DRAFT",
                    "review_state": "UNREVIEWED",
                    "approval_state": "PENDING",
                    "approved_at": None,
                    "approved_by": None,
                }
            return self

        def fetchone(self):
            return self.row

        def commit(self):
            return None

    connection = Connection()
    monkeypatch.setattr(routing_repository, "get_route", lambda _route_id: current)
    monkeypatch.setattr(routing_repository, "get_connection", lambda: connection)
    monkeypatch.setattr(routing_repository, "current_project_id", lambda: "project-a")

    updated = routing_repository.update_route(route_id, {"name": "Updated route", "actor": "routing-ui"})

    assert updated["id"] == route_id
    assert updated["revision"] == 4
    assert updated["approval_state"] == "PENDING"
    assert any("WHERE id = %s" in query for query, _values in connection.queries)
    assert not any("INSERT INTO engineering_routing_entries" in query for query, _values in connection.queries)


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


def test_linked_agent_route_receives_physical_network_and_ports():
    route_id = "00000000-0000-0000-0000-000000000099"
    route = {
        **normalize_route(route_payload()),
        "id": route_id,
        "source": {**route_payload()["source"], "network_id": None, "port_id": None},
        "destinations": [
            {**route_payload()["destinations"][0], "network_id": None, "port_id": None}
        ],
    }
    topology = {
        "nodes": [
            {"id": "source", "engineeringId": SOURCE},
            {"id": "target", "engineeringId": TARGET},
        ],
        "edges": [
            {
                "id": "routing-edge",
                "source": "source",
                "sourcePort": "source-port",
                "target": "target",
                "targetPort": "target-port",
                "bus": "can_fd",
                "routingEntryIds": [route_id],
            }
        ],
    }

    enriched = enrich_route_from_linked_topology(route, topology)

    assert enriched["source"]["network_id"] == "network-can_fd"
    assert enriched["source"]["port_id"] == "source-port"
    assert enriched["destinations"][0]["network_id"] == "network-can_fd"
    assert enriched["destinations"][0]["port_id"] == "target-port"


def test_gateway_path_composed_from_accepted_routes_does_not_reopen_review():
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
                "id": "gateway",
                "name": "Gateway",
                "kind": "gateway",
                "engineeringId": "00000000-0000-0000-0000-000000000003",
                "ports": [
                    {"id": "gateway-left", "bus": "can_fd"},
                    {"id": "gateway-right", "bus": "can_fd"},
                ],
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
                "id": "route-a-edge",
                "source": "source",
                "sourcePort": "source-port",
                "target": "gateway",
                "targetPort": "gateway-left",
                "bus": "can_fd",
                "origin": "ROUTING_TABLE",
                "routingEntryId": "route-a",
            },
            {
                "id": "route-b-edge",
                "source": "gateway",
                "sourcePort": "gateway-right",
                "target": "target",
                "targetPort": "target-port",
                "bus": "can_fd",
                "origin": "ROUTING_TABLE",
                "routingEntryId": "route-b",
            },
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


def test_graph_publication_uses_project_scoped_relation_conflict_key():
    class Connection:
        def __init__(self):
            self.queries = []

        def execute(self, query, _params):
            self.queries.append(query)

    connection = Connection()
    routing_repository._publish_graph(
        connection,
        {
            "id": "00000000-0000-0000-0000-000000000099",
            "route_code": "RT-PROJECT",
            "source": {"node_id": SOURCE},
            "destinations": [{"node_id": TARGET}],
            "payload": {"signal_ids": []},
        },
        "test",
    )

    assert connection.queries[0].startswith("DELETE FROM engineering_relations")
    assert "attributes ->> 'route_id'" in connection.queries[0]
    assert any("ON CONFLICT (project_id, relation_type" in query for query in connection.queries)


def test_generation_reuses_canonical_interfaces_protocol_and_message_cycle(monkeypatch):
    service = RoutingGenerationService()
    nodes = {
        SOURCE: {"id": SOURCE, "name": "Sensor", "device_type": "SensorController"},
        TARGET: {"id": TARGET, "name": "ECU", "device_type": "ECU"},
    }
    interfaces = {
        SOURCE: [{"id": SOURCE_INTERFACE, "hardware_node_id": SOURCE, "interface_type": "CAN_FD"}],
        TARGET: [{"id": TARGET_INTERFACE, "hardware_node_id": TARGET, "interface_type": "CAN_FD"}],
    }
    monkeypatch.setattr(service, "_node", lambda node_id: nodes[node_id])
    monkeypatch.setattr(service, "_interface_candidates", lambda node_id: interfaces[node_id])
    monkeypatch.setattr(
        service,
        "_message_context",
        lambda message_id: {
            "id": message_id,
            "interface_id": SOURCE_INTERFACE,
            "hardware_node_id": SOURCE,
            "interface_type": "CAN_FD",
            "cycle_ms": 10,
        },
    )
    monkeypatch.setattr(
        service,
        "find_candidate_paths",
        lambda source_id, target_id: [
            {
                "nodes": [
                    {"node_id": source_id, "name": "Sensor"},
                    {"node_id": target_id, "name": "ECU"},
                ],
                "connections": [],
                "gateways": [],
                "protocol": "CUSTOM",
                "score": 0.93,
            }
        ],
    )
    monkeypatch.setattr(
        "backend.engineering.routing.generation.RoutingValidator.validate",
        lambda validator, route: {"valid": True, "errors": [], "warnings": []},
    )

    route = service.generate_route(
        source_node_id=SOURCE,
        destination_node_id=TARGET,
        message_id=MESSAGE,
        signal_ids=[SIGNAL],
    )

    assert route["source"]["interface_id"] == SOURCE_INTERFACE
    assert route["destinations"][0]["interface_id"] == TARGET_INTERFACE
    assert route["source"]["protocol"] == "CAN_FD"
    assert route["destinations"][0]["protocol"] == "CAN_FD"
    assert route["timing"]["cycle_time_ms"] == 10
