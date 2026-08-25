"""Graph-backed routing proposal generation without approval permissions."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from ..db import get_connection
from ..models import EngineeringValidationError
from .repository import create_proposal
from .retrieval import HybridRoutingRetriever
from .validation import RoutingValidator

INTERFACE_TO_PROTOCOL = {
    "CAN": "CAN",
    "CAN_FD": "CAN_FD",
    "LIN": "LIN",
    "FlexRay": "FLEXRAY",
    "Ethernet": "ETHERNET",
    "EtherCAT": "ETHERCAT",
    "ProfiNET": "PROFINET",
    "ModbusTCP": "MODBUS",
    "ModbusRTU": "MODBUS",
    "OPCUA": "OPC_UA",
}


class RoutingGenerationService:
    """Finds, ranks and stores route candidates as proposals only."""

    def _node(self, value: str) -> dict[str, Any]:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM engineering_hardware_nodes WHERE id::text = %s OR lower(name) = lower(%s) "
                "ORDER BY CASE WHEN id::text = %s THEN 0 ELSE 1 END LIMIT 1",
                (value, value, value),
            ).fetchone()
        if row is None:
            raise EngineeringValidationError(f"Hardware Node {value!r} wurde nicht gefunden.")
        return row

    def _interface_candidates(self, node_id: str) -> list[dict[str, Any]]:
        with get_connection() as connection:
            return connection.execute(
                "SELECT * FROM engineering_interfaces WHERE hardware_node_id = %s ORDER BY created_at",
                (node_id,),
            ).fetchall()

    def _hardware_graph(self) -> tuple[dict[str, set[str]], dict[tuple[str, str], dict[str, Any]]]:
        adjacency: dict[str, set[str]] = defaultdict(set)
        edge_data: dict[tuple[str, str], dict[str, Any]] = {}
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT r.*, si.hardware_node_id AS source_node_id, ti.hardware_node_id AS target_node_id, "
                "si.id AS source_interface_id, ti.id AS target_interface_id, si.interface_type AS source_type_name, "
                "ti.interface_type AS target_type_name FROM engineering_relations r "
                "JOIN engineering_interfaces si ON r.source_type = 'Interface' AND r.source_id = si.id "
                "JOIN engineering_interfaces ti ON r.target_type = 'Interface' AND r.target_id = ti.id "
                "WHERE r.relation_type = 'CONNECTED_TO'"
            ).fetchall()
        for row in rows:
            source = str(row["source_node_id"])
            target = str(row["target_node_id"])
            adjacency[source].add(target)
            adjacency[target].add(source)
            data = {
                "source_interface_id": str(row["source_interface_id"]),
                "target_interface_id": str(row["target_interface_id"]),
                "source_interface_type": row["source_type_name"],
                "target_interface_type": row["target_type_name"],
                "relation_id": str(row["id"]),
            }
            edge_data[(source, target)] = data
            edge_data[(target, source)] = {
                **data,
                "source_interface_id": data["target_interface_id"],
                "target_interface_id": data["source_interface_id"],
                "source_interface_type": data["target_interface_type"],
                "target_interface_type": data["source_interface_type"],
            }
        return adjacency, edge_data

    def find_candidate_paths(self, source_node_id: str, target_node_id: str, limit: int = 5) -> list[dict[str, Any]]:
        source = self._node(source_node_id)
        target = self._node(target_node_id)
        source_id = str(source["id"])
        target_id = str(target["id"])
        adjacency, edge_data = self._hardware_graph()
        queue = deque([[source_id]])
        paths: list[list[str]] = []
        while queue and len(paths) < limit:
            path = queue.popleft()
            current = path[-1]
            if current == target_id:
                paths.append(path)
                continue
            if len(path) >= 8:
                continue
            for neighbor in sorted(adjacency.get(current, set())):
                if neighbor not in path:
                    queue.append([*path, neighbor])

        # A direct candidate remains useful for incomplete imported graphs; validation marks missing interfaces.
        if not paths:
            paths = [[source_id, target_id]]
        node_ids = sorted({node_id for path in paths for node_id in path})
        with get_connection() as connection:
            nodes = {
                str(row["id"]): row
                for row in connection.execute(
                    "SELECT id, name, device_type FROM engineering_hardware_nodes WHERE id = ANY(%s::uuid[])",
                    (node_ids,),
                ).fetchall()
            }
        candidates = []
        for path in paths:
            connections = [edge_data.get((left, right), {}) for left, right in zip(path, path[1:])]
            gateways = [
                {"node_id": node_id, "name": nodes[node_id]["name"]}
                for node_id in path[1:-1]
                if nodes.get(node_id, {}).get("device_type") == "Gateway"
            ]
            interface_type = connections[0].get("source_interface_type") if connections else None
            protocol = INTERFACE_TO_PROTOCOL.get(str(interface_type), "CUSTOM")
            candidates.append(
                {
                    "nodes": [
                        {"node_id": node_id, "name": nodes.get(node_id, {}).get("name", node_id)}
                        for node_id in path
                    ],
                    "connections": connections,
                    "gateways": gateways,
                    "protocol": protocol,
                    "hop_count": len(path) - 1,
                }
            )
        return self.rank_candidate_paths(candidates)

    def rank_candidate_paths(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked = []
        for candidate in candidates:
            hops = int(candidate.get("hop_count", 1))
            gateways = len(candidate.get("gateways", []))
            protocol_bonus = 0.08 if candidate.get("protocol") != "CUSTOM" else 0.0
            score = max(0.0, min(1.0, 1.0 - hops * 0.07 - gateways * 0.08 + protocol_bonus))
            ranked.append(
                {
                    **candidate,
                    "score": round(score, 3),
                    "ranking": {
                        "protocol_compatibility": candidate.get("protocol") != "CUSTOM",
                        "hop_count": hops,
                        "gateway_count": gateways,
                        "estimated_latency_ms": round(0.2 + hops * 0.35 + gateways * 0.8, 3),
                    },
                }
            )
        return sorted(ranked, key=lambda item: item["score"], reverse=True)

    def generate_route(
        self,
        *,
        source_node_id: str,
        destination_node_id: str,
        message_id: str | None = None,
        signal_ids: list[str] | None = None,
        routing_type: str = "UNICAST",
    ) -> dict[str, Any]:
        source = self._node(source_node_id)
        destination = self._node(destination_node_id)
        candidate = self.find_candidate_paths(str(source["id"]), str(destination["id"]))[0]
        source_interface = candidate.get("connections", [{}])[0].get("source_interface_id") if candidate.get("connections") else None
        destination_interface = candidate.get("connections", [{}])[-1].get("target_interface_id") if candidate.get("connections") else None
        protocol = candidate["protocol"]
        route = {
            "name": f"{source['name']} → {destination['name']}",
            "description": "Graphbasierter Routing-Vorschlag des Engineering-Agenten.",
            "source": {
                "node_id": str(source["id"]),
                "port_id": None,
                "interface_id": source_interface,
                "network_id": None,
                "protocol": protocol,
            },
            "payload": {
                "interface_definition_id": None,
                "message_id": message_id,
                "signal_ids": signal_ids or [],
                "topic": None,
                "data_object": None,
            },
            "destinations": [
                {
                    "node_id": str(destination["id"]),
                    "interface_id": destination_interface,
                    "network_id": None,
                    "protocol": protocol,
                }
            ],
            "route": {
                "hops": candidate["nodes"],
                "gateways": candidate["gateways"],
                "transformations": [],
                "priority": "NORMAL",
            },
            "timing": {
                "cycle_time_ms": 100,
                "timeout_ms": 500,
                "max_latency_ms": 20,
                "jitter_limit_ms": 5,
            },
            "routing_policy": {
                "routing_type": routing_type,
                "redundancy": "NONE",
                "fallback_route_id": None,
                "conditions": [],
            },
            "origin": "AI_GENERATED",
            "confidence": candidate["score"],
        }
        validation = RoutingValidator().validate(route)
        return {**route, "validation": validation, "candidate": candidate}

    def generate_routes(self, data: dict[str, Any]) -> dict[str, Any]:
        source_value = str(data.get("source_node_id") or data.get("source") or "").strip()
        destinations = data.get("destination_node_ids") or data.get("destinations") or []
        if isinstance(destinations, str):
            destinations = [destinations]
        if not source_value or not destinations:
            raise EngineeringValidationError("source_node_id und destination_node_ids sind erforderlich.")
        routing_type = "MULTICAST" if len(destinations) > 1 else str(data.get("routing_type") or "UNICAST")
        generated = [
            self.generate_route(
                source_node_id=source_value,
                destination_node_id=str(destination),
                message_id=data.get("message_id"),
                signal_ids=data.get("signal_ids") or [],
                routing_type="UNICAST" if len(destinations) > 1 else routing_type,
            )
            for destination in destinations
        ]
        prompt = str(data.get("prompt") or "Erzeuge technisch geeignete Kommunikationsrouten.")
        evidence = [
            {
                "route": item["name"],
                "graph_path": item["candidate"]["nodes"],
                "selected_because": ["highest candidate score", "lowest available hop count", "protocol compatibility"],
                "confidence": item["confidence"],
            }
            for item in generated
        ]
        retrieved_context = HybridRoutingRetriever().retrieve(
            query=prompt,
            graph_paths=[item["candidate"] for item in generated],
            target_ids=[source_value, *map(str, destinations), str(data.get("message_id") or ""), *map(str, data.get("signal_ids") or [])],
            protocol=generated[0]["source"].get("protocol") if generated else None,
        )
        proposal = create_proposal(
            {
                "prompt": prompt,
                "target_objects": [source_value, *map(str, destinations)],
                "generated_routes": [{key: value for key, value in item.items() if key != "candidate"} for item in generated],
                "retrieved_context": retrieved_context,
                "evidence": evidence,
                "confidence": min(item["confidence"] for item in generated),
                "validation_results": [item["validation"] for item in generated],
                "model": data.get("model") or "routing-generation-service",
                "model_version": data.get("model_version") or "1.0",
                "actor": data.get("actor") or "engineering-agent",
            }
        )
        return proposal

    def suggest_consumers(self, source_node_id: str) -> list[dict[str, Any]]:
        source = self._node(source_node_id)
        with get_connection() as connection:
            return connection.execute(
                "SELECT id, name, device_type FROM engineering_hardware_nodes WHERE id <> %s "
                "ORDER BY CASE device_type WHEN 'Gateway' THEN 1 ELSE 0 END, name LIMIT 20",
                (source["id"],),
            ).fetchall()

    def suggest_gateway(self, source_node_id: str, target_node_id: str) -> list[dict[str, Any]]:
        candidates = self.find_candidate_paths(source_node_id, target_node_id)
        return [
            {"path_score": item["score"], "gateways": item.get("gateways", [])}
            for item in candidates if item.get("gateways")
        ]

    def suggest_network(self, source_node_id: str, target_node_id: str) -> list[dict[str, Any]]:
        candidates = self.find_candidate_paths(source_node_id, target_node_id)
        return [
            {"protocol": item.get("protocol"), "connections": item.get("connections", []), "score": item["score"]}
            for item in candidates
        ]

    def suggest_protocol(self, source_node_id: str, target_node_id: str) -> list[dict[str, Any]]:
        return [
            {"protocol": item.get("protocol"), "score": item["score"], "hop_count": item["hop_count"]}
            for item in self.find_candidate_paths(source_node_id, target_node_id)
        ]

    def suggest_fallback_route(self, source_node_id: str, target_node_id: str) -> dict[str, Any] | None:
        candidates = self.find_candidate_paths(source_node_id, target_node_id)
        return candidates[1] if len(candidates) > 1 else None

    def optimize_routes(self, routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        suggestions = []
        for route in routes:
            hops = route.get("route", {}).get("hops", [])
            gateways = route.get("route", {}).get("gateways", [])
            if len(hops) > 2 or len(gateways) > 1:
                suggestions.append(
                    {
                        "route_id": str(route.get("id") or ""),
                        "type": "SIMPLIFY_PATH",
                        "current_hops": len(hops),
                        "gateway_hops": len(gateways),
                        "reason": "Weniger Hops reduzieren Latenz, Gateway-Last und Fehlerfläche.",
                        "proposal_only": True,
                    }
                )
        return suggestions
