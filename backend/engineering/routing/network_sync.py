"""Synchronize physical network paths into reviewable routing proposals."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from ..db import get_connection
from ..project_context import activate_project
from ..physical_segments import physical_port_networks
from .models import normalize_route
from .repository import _audit, _insert_route, _route_code
from .validation import RoutingValidator


BUS_PROTOCOLS = {
    "can_fd": "CAN_FD",
    "lin": "LIN",
    "automotive_ethernet": "ETHERNET",
    "flexray": "FLEXRAY",
}

BUS_CYCLES_MS = {
    "can_fd": 10.0,
    "lin": 20.0,
    "automotive_ethernet": 5.0,
    "flexray": 5.0,
}


def _signature(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _engineering_id(node: dict[str, Any]) -> str:
    return str(node.get("engineeringId") or node.get("engineering_id") or "").strip()


def _port(node: dict[str, Any], port_id: str) -> dict[str, Any]:
    ports = node.get("ports") if isinstance(node.get("ports"), list) else []
    return next((item for item in ports if isinstance(item, dict) and item.get("id") == port_id), {})


def _edge_route_ids(edge: dict[str, Any]) -> set[str]:
    route_ids = {
        str(item).strip()
        for item in edge.get("routingEntryIds", [])
        if str(item).strip()
    } if isinstance(edge.get("routingEntryIds"), list) else set()
    direct = str(edge.get("routingEntryId") or edge.get("routing_entry_id") or "").strip()
    if direct:
        route_ids.add(direct)
    return route_ids


def enrich_route_from_linked_topology(
    route: dict[str, Any],
    topology: dict[str, Any],
    port_networks: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Project physical bus and port assignments back into one logical route."""
    route_id = str(route.get("id") or "").strip()
    if not route_id:
        return deepcopy(route)
    nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
    if port_networks is None:
        port_networks = physical_port_networks(topology)
    nodes_by_id = {str(node.get("id")): node for node in nodes if isinstance(node, dict)}
    edges = topology.get("edges") if isinstance(topology.get("edges"), list) else []
    topology_by_engineering_id = {
        _engineering_id(node): str(node.get("id"))
        for node in nodes
        if isinstance(node, dict) and node.get("id") and _engineering_id(node)
    }
    linked_edges = [
        edge
        for edge in edges
        if isinstance(edge, dict) and route_id in _edge_route_ids(edge)
    ]
    if not linked_edges:
        return deepcopy(route)

    def enrich_endpoint(endpoint: dict[str, Any]) -> dict[str, Any]:
        engineering_id = str(endpoint.get("node_id") or "")
        topology_id = topology_by_engineering_id.get(engineering_id)
        if not topology_id:
            return deepcopy(endpoint)
        incident = [
            edge
            for edge in linked_edges
            if str(edge.get("source") or "") == topology_id
            or str(edge.get("target") or "") == topology_id
        ]
        if not incident:
            return deepcopy(endpoint)
        protocol = str(endpoint.get("protocol") or "").upper()
        matching = [edge for edge in incident if BUS_PROTOCOLS.get(str(edge.get("bus") or "")) == protocol]
        edge = sorted(matching or incident, key=lambda item: str(item.get("id") or ""))[0]
        bus = str(edge.get("bus") or "").strip()
        if not bus:
            return deepcopy(endpoint)
        is_source = str(edge.get("source") or "") == topology_id
        port_id = str(
            (edge.get("sourcePort") if is_source else edge.get("targetPort")) or ""
        ).strip()
        port = _port(nodes_by_id.get(topology_id, {}), port_id)
        hardware_interface_id = str(
            port.get("hardwareInterfaceId") or port.get("hardware_interface_id") or ""
        ).strip()
        logical_interface_id = (
            endpoint.get("interface_id")
            if hardware_interface_id
            else port.get("engineeringId") or endpoint.get("interface_id")
        )
        return {
            **endpoint,
            "port_id": hardware_interface_id or port_id or endpoint.get("port_id"),
            "interface_id": logical_interface_id,
            "network_id": port_networks.get(port_id, f"network-{bus}"),
        }

    enriched = deepcopy(route)
    enriched["source"] = enrich_endpoint(route.get("source") or {})
    enriched["destinations"] = [
        enrich_endpoint(destination)
        for destination in route.get("destinations", [])
        if isinstance(destination, dict)
    ]
    return enriched


def reconcile_linked_routes(
    project_id: str,
    topology: dict[str, Any],
    *,
    actor: str,
) -> list[dict[str, Any]]:
    """Refresh linked routes after the agent materializes their physical topology."""
    raw_edges = topology.get("edges") if isinstance(topology.get("edges"), list) else []
    raw_ids = sorted({route_id for edge in raw_edges if isinstance(edge, dict) for route_id in _edge_route_ids(edge)})
    route_ids: list[str] = []
    for route_id in raw_ids:
        try:
            route_ids.append(str(UUID(route_id)))
        except ValueError:
            continue
    if not route_ids:
        return []

    reconciled: list[dict[str, Any]] = []
    port_networks = physical_port_networks(topology)
    validator = RoutingValidator(project_id)
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM engineering_routing_entries "
            "WHERE id = ANY(%s::uuid[]) AND project_id = %s FOR UPDATE",
            (route_ids, project_id),
        ).fetchall()
        for current in rows:
            enriched = enrich_route_from_linked_topology(current, topology, port_networks)
            validation = validator.validate(enriched, exclude_route_id=str(current["id"]))
            current_validation = {
                key: value
                for key, value in (current.get("validation") or {}).items()
                if key != "validation_timestamp"
            }
            next_validation = {
                key: value
                for key, value in validation.items()
                if key != "validation_timestamp"
            }
            if (
                enriched.get("source") == current.get("source")
                and enriched.get("destinations") == current.get("destinations")
                and next_validation == current_validation
            ):
                continue
            updated = connection.execute(
                "UPDATE engineering_routing_entries "
                "SET source = %s, destinations = %s, validation = %s, modified_by = %s, modified_at = now() "
                "WHERE id = %s AND project_id = %s RETURNING *",
                (
                    Jsonb(enriched["source"]),
                    Jsonb(enriched["destinations"]),
                    Jsonb(validation),
                    actor,
                    current["id"],
                    project_id,
                ),
            ).fetchone()
            _audit(
                connection,
                str(current["id"]),
                "ROUTE_PHYSICAL_CONTEXT_RECONCILED",
                actor=actor,
                before=current,
                after=updated,
                reason="Physical topology was projected back into the logical route.",
            )
            reconciled.append(updated)
        connection.commit()
    return reconciled


def build_network_route_candidates(
    project_id: str,
    topology: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Build one deterministic proposal per directed producer-to-consumer path."""
    raw_nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
    port_networks = physical_port_networks(topology)
    raw_edges = topology.get("edges") if isinstance(topology.get("edges"), list) else []
    nodes = {
        str(node.get("id")): node
        for node in raw_nodes
        if isinstance(node, dict) and node.get("id")
    }
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in raw_edges:
        if not isinstance(edge, dict) or not edge.get("id"):
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in nodes and target in nodes:
            adjacency.setdefault(source, []).append(edge)
    for edges in adjacency.values():
        edges.sort(key=lambda item: str(item.get("id")))

    paths: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def walk(start: str, current: str, path: list[dict[str, Any]], visited: set[str]) -> None:
        for edge in adjacency.get(current, []):
            target = str(edge.get("target"))
            if target in visited:
                continue
            next_path = [*path, edge]
            target_node = nodes[target]
            if str(target_node.get("kind") or "").lower() != "gateway":
                if target != start:
                    key = (start, target)
                    previous = paths.get(key)
                    if previous is None or (
                        len(next_path), [str(item.get("id")) for item in next_path]
                    ) < (
                        len(previous), [str(item.get("id")) for item in previous]
                    ):
                        paths[key] = next_path
                continue
            walk(start, target, next_path, {*visited, target})

    for node_id, node in sorted(nodes.items()):
        if str(node.get("kind") or "").lower() != "gateway":
            walk(node_id, node_id, [], {node_id})

    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for (source_topology_id, target_topology_id), path_edges in sorted(paths.items()):
        routing_entry_ids = {
            str(edge.get("routingEntryId") or edge.get("routing_entry_id") or "").strip()
            for edge in path_edges
        }
        routing_entry_ids.discard("")
        if routing_entry_ids and all(
            edge.get("routingEntryId") or edge.get("routing_entry_id")
            for edge in path_edges
        ):
            # Every segment already belongs to an accepted routing entry. A
            # gateway may join segments from multiple entries, but that must
            # not synthesize another route and reopen the human-review gate.
            continue
        source_node = nodes[source_topology_id]
        target_node = nodes[target_topology_id]
        path_topology_ids = [source_topology_id, *[str(edge.get("target")) for edge in path_edges]]
        path_nodes = [nodes[node_id] for node_id in path_topology_ids]
        unresolved = [str(node.get("name") or node.get("id")) for node in path_nodes if not _engineering_id(node)]
        relation_key = f"{project_id}:network-path:{source_topology_id}:{target_topology_id}"
        if unresolved:
            skipped.append(
                {
                    "source_id": relation_key,
                    "reason": f"Engineering-Verknuepfung fehlt: {', '.join(unresolved)}",
                }
            )
            continue

        buses = [str(edge.get("bus") or "") for edge in path_edges]
        first_edge = path_edges[0]
        last_edge = path_edges[-1]
        source_port = _port(source_node, str(first_edge.get("sourcePort") or ""))
        target_port = _port(target_node, str(last_edge.get("targetPort") or ""))
        gateways = [node for node in path_nodes[1:-1] if str(node.get("kind") or "").lower() == "gateway"]
        transformations = [
            f"{BUS_PROTOCOLS.get(left, left.upper())}_TO_{BUS_PROTOCOLS.get(right, right.upper())}"
            for left, right in zip(buses, buses[1:])
            if left != right
        ]
        path_signature = _signature(
            [
                {
                    "id": edge.get("id"),
                    "source": edge.get("source"),
                    "sourcePort": edge.get("sourcePort"),
                    "target": edge.get("target"),
                    "targetPort": edge.get("targetPort"),
                    "bus": edge.get("bus"),
                }
                for edge in path_edges
            ]
        )
        source_name = str(source_node.get("name") or source_topology_id)
        target_name = str(target_node.get("name") or target_topology_id)
        protocol = BUS_PROTOCOLS.get(buses[0], "CUSTOM")
        target_protocol = BUS_PROTOCOLS.get(buses[-1], "CUSTOM")
        candidates.append(
            {
                "name": f"{source_name} -> {target_name}",
                "description": "Proposed from Network Editor",
                "source": {
                    "node_id": _engineering_id(source_node),
                    "port_id": str(source_port.get("id") or "") or None,
                    "interface_id": str(source_port.get("engineeringId") or source_port.get("engineering_id") or "") or None,
                    "network_id": port_networks.get(str(source_port.get("id")), f"network-{buses[0]}"),
                    "protocol": protocol,
                },
                "payload": {
                    "interface_definition_id": None,
                    "message_id": None,
                    "signal_ids": [],
                    "topic": None,
                    "data_object": None,
                },
                "destinations": [
                    {
                        "node_id": _engineering_id(target_node),
                        "port_id": str(target_port.get("id") or "") or None,
                        "interface_id": str(target_port.get("engineeringId") or target_port.get("engineering_id") or "") or None,
                        "network_id": port_networks.get(str(target_port.get("id")), f"network-{buses[-1]}"),
                        "protocol": target_protocol,
                    }
                ],
                "route": {
                    "hops": [
                        {"node_id": _engineering_id(node), "name": node.get("name")}
                        for node in path_nodes
                    ],
                    "gateways": [
                        {"node_id": _engineering_id(node), "name": node.get("name")}
                        for node in gateways
                    ],
                    "transformations": transformations,
                    "priority": "NORMAL",
                },
                "timing": {
                    "cycle_time_ms": max(BUS_CYCLES_MS.get(bus, 100.0) for bus in buses),
                    "timeout_ms": 500.0,
                    "max_latency_ms": 20.0,
                    "jitter_limit_ms": 5.0,
                },
                "routing_policy": {
                    "routing_type": "GATEWAY_ROUTED" if gateways else "UNICAST",
                    "redundancy": "NONE",
                    "conditions": [
                        {
                            "kind": "NETWORK_EDITOR_PROPOSAL",
                            "label": "Proposed from Network Editor",
                            "project_id": project_id,
                            "topology_edge_ids": [str(edge.get("id")) for edge in path_edges],
                            "path_signature": path_signature,
                        }
                    ],
                },
                "validation": {},
                "status": "PENDING_CONFIRMATION",
                "origin": "NETWORK_EDITOR",
                "review_state": "UNREVIEWED",
                "approval_state": "PENDING",
                "source_id": relation_key,
                "source_version": path_signature,
                "created_by": "network-editor",
                "modified_by": "network-editor",
            }
        )
    return candidates, skipped


def synchronize_network_routes(
    project_id: str,
    topology: dict[str, Any],
    *,
    actor: str | None = None,
) -> dict[str, Any]:
    """Version network-derived routes without ever approving them automatically."""
    activate_project(project_id)
    actor = actor or "network-editor"
    reconciled = reconcile_linked_routes(project_id, topology, actor=actor)
    candidates, skipped = build_network_route_candidates(project_id, topology)
    desired = {str(candidate["source_id"]): candidate for candidate in candidates}
    prefix = f"{project_id}:network-path:%"
    created: list[dict[str, Any]] = []
    outdated: list[dict[str, Any]] = []
    unchanged: list[str] = []

    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM engineering_routing_entries "
            "WHERE origin = 'NETWORK_EDITOR' AND source_id LIKE %s AND project_id = %s "
            "ORDER BY source_id, revision DESC, modified_at DESC",
            (prefix, project_id),
        ).fetchall()
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row.get("source_id") or "")
            latest.setdefault(key, row)

        for key, current in latest.items():
            candidate = desired.get(key)
            physical_changed = candidate is None or current.get("source_version") != candidate.get("source_version")
            if not physical_changed or current.get("status") in {"OUTDATED", "REJECTED", "SUPERSEDED"}:
                continue
            validation = deepcopy(current.get("validation") or {})
            warnings = [
                item
                for item in validation.get("warnings", [])
                if isinstance(item, dict) and item.get("code") != "PHYSICAL_PATH_CHANGED"
            ]
            warnings.append(
                {
                    "code": "PHYSICAL_PATH_CHANGED",
                    "message": "Physical network path changed.",
                }
            )
            validation.update(
                {
                    "valid": False,
                    "warnings": warnings,
                    "outdated_reason": "Physical network path changed.",
                }
            )
            row = connection.execute(
                "UPDATE engineering_routing_entries SET status = 'OUTDATED', "
                "approval_state = 'PENDING', review_state = 'IN_REVIEW', validation = %s, "
                "modified_by = %s, modified_at = now() "
                "WHERE id = %s AND project_id = %s RETURNING *",
                (Jsonb(validation), actor, current["id"], project_id),
            ).fetchone()
            _audit(
                connection,
                str(current["id"]),
                "NETWORK_PATH_OUTDATED",
                actor=actor,
                before=current,
                after=row,
                reason="Physical network path changed.",
            )
            outdated.append(row)

        for key, candidate in desired.items():
            current = latest.get(key)
            if (
                current
                and current.get("source_version") == candidate.get("source_version")
                and current.get("status") != "OUTDATED"
            ):
                unchanged.append(str(current["id"]))
                continue
            normalized = normalize_route({**candidate, "actor": actor})
            normalized["status"] = "PENDING_CONFIRMATION"
            normalized["approval_state"] = "PENDING"
            normalized["review_state"] = "UNREVIEWED"
            normalized["created_by"] = actor
            normalized["modified_by"] = actor
            row = _insert_route(
                connection,
                normalized,
                route_code=str(current["route_code"]) if current else _route_code(),
                revision=int(current["revision"]) + 1 if current else 1,
                supersedes_id=str(current["id"]) if current else None,
            )
            _audit(
                connection,
                str(row["id"]),
                "NETWORK_ROUTING_PROPOSAL_CREATED",
                actor=actor,
                before=current,
                after=row,
                reason="Physical network relationship created or changed.",
                evidence=[
                    {
                        "origin": "NETWORK_EDITOR",
                        "source_id": key,
                        "path_signature": candidate.get("source_version"),
                    }
                ],
            )
            created.append(row)
        connection.commit()

    return {
        "created": created,
        "outdated": outdated,
        "unchanged": unchanged,
        "reconciled": reconciled,
        "skipped": skipped,
        "counts": {
            "created": len(created),
            "outdated": len(outdated),
            "unchanged": len(unchanged),
            "reconciled": len(reconciled),
            "skipped": len(skipped),
        },
    }
