"""Graph-backed routing proposal generation without approval permissions."""

from __future__ import annotations

from collections import defaultdict, deque
from contextlib import contextmanager
from typing import Any

from ..db import get_connection
from ..models import EngineeringValidationError
from ..project_context import current_project_id
from ..message_bindings import message_hardware_interface_ids, explicit_transmit_interface_ids
from .repository import create_proposal
from .retrieval import HybridRoutingRetriever
from .validation import RoutingValidator, is_gateway_fanout_interface, INTERFACE_PROTOCOLS
from .timing import generated_timing

INTERFACE_TO_PROTOCOL = {
    "CAN": "CAN",
    "CANopen": "CAN",
    "CAN_FD": "CAN_FD",
    "LIN": "LIN",
    "FlexRay": "FLEXRAY",
    "Ethernet": "ETHERNET",
    "EtherCAT": "ETHERCAT",
    "ProfiNET": "PROFINET",
    "ModbusTCP": "MODBUS_TCP",
    "ModbusRTU": "MODBUS_RTU",
    "I2C": "I2C",
    "UART": "UART",
    "IO_LINK": "IO_LINK",
    "SPI": "SPI",
    "GPIO": "GPIO",
    "PWM": "PWM",
    "OPCUA": "OPC_UA",
    "ARINC": "ARINC",
    "MIL_STD_1553": "MIL_STD_1553",
    "MVB": "MVB",
    "WTB": "WTB",
    "ETB": "ETB",
    "TRDP": "TRDP",
    "PCIe": "PCIE",
}


@contextmanager
def routing_candidate_batch(service):
    """Share immutable candidate reads within one proposal, never across calls."""
    previous = getattr(service, '_candidate_context', None)
    service._candidate_context = {'project_id': current_project_id()}
    try:
        yield service
    finally:
        service._candidate_context = previous
        service._candidate_planner = None


class RoutingGenerationService:
    """Finds, ranks and stores route candidates as proposals only."""

    def _node(self, value: str) -> dict[str, Any]:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM engineering_hardware_nodes WHERE (id::text = %s OR lower(name) = lower(%s)) "
                "AND project_id = %s ORDER BY CASE WHEN id::text = %s THEN 0 ELSE 1 END LIMIT 1",
                (value, value, current_project_id(), value),
            ).fetchone()
        if row is None:
            raise EngineeringValidationError(f"Hardware Node {value!r} wurde nicht gefunden.")
        return row

    def _interface_candidates(self, node_id: str) -> list[dict[str, Any]]:
        with get_connection() as connection:
            return connection.execute(
                "SELECT i.*, ARRAY(SELECT DISTINCT m.hardware_interface_id::text FROM engineering_messages m "
                "WHERE m.interface_id=i.id AND m.project_id=i.project_id AND m.hardware_interface_id IS NOT NULL) || "
                "ARRAY(SELECT DISTINCT binding->>'hardware_interface_id' FROM engineering_messages m "
                "CROSS JOIN LATERAL jsonb_array_elements(COALESCE(m.configuration->'physical_transmit_bindings', '[]'::jsonb)) binding "
                "WHERE m.interface_id=i.id AND m.project_id=i.project_id) "
                "AS physical_interface_ids FROM engineering_interfaces i WHERE i.hardware_node_id = %s "
                "AND i.project_id = %s ORDER BY i.created_at",
                (node_id, current_project_id()),
            ).fetchall()

    def _hardware_interface_candidates(self, node_id: str) -> list[dict[str, Any]]:
        with get_connection() as connection:
            return connection.execute(
                "SELECT * FROM engineering_hardware_interfaces WHERE hardware_node_id = %s "
                "AND project_id = %s ORDER BY channel_index, created_at",
                (node_id, current_project_id()),
            ).fetchall()

    def _message_context(self, message_id: str | None) -> dict[str, Any] | None:
        if not message_id:
            return None
        with get_connection() as connection:
            return connection.execute(
                "SELECT m.*, i.hardware_node_id, i.interface_type "
                "FROM engineering_messages m "
                "LEFT JOIN engineering_interfaces i ON i.id = m.interface_id AND i.project_id = m.project_id "
                "WHERE m.id = %s AND m.project_id = %s LIMIT 1",
                (message_id, current_project_id()),
            ).fetchone()

    @staticmethod
    def _logical_endpoint(interfaces, physical, *, preferred_id=None, bound_id=None, name="Empfänger"):
        """Resolve a logical partner against the final physical receiving channel.

        Message bindings are authoritative at the source. At the destination an
        explicit relation may identify the function; source technology never does.
        Equal transport support alone cannot choose between different functions.
        """
        by_id = {str(item['id']): item for item in interfaces}
        if bound_id:
            return by_id.get(str(bound_id))  # A missing binding stays visibly missing.
        protocol = INTERFACE_TO_PROTOCOL.get(str((physical or {}).get('technology') or ''))
        compatible = [item for item in interfaces if not protocol or protocol in
                      INTERFACE_PROTOCOLS.get(str(item.get('interface_type')), set())]
        preferred = by_id.get(str(preferred_id))
        if preferred in compatible:
            return preferred
        if physical:
            bound = [item for item in compatible if str(physical['id']) in
                     set(map(str, [*(item.get('physical_interface_ids') or []),
                                   *((item.get('configuration') or {}).get('physical_interface_ids') or [])]))]
            if bound:
                compatible = bound
        controller_endpoints = [item for item in compatible
                                if (item.get('configuration') or {}).get('endpoint_role') == 'SYSTEM_CONTROLLER']
        if len(controller_endpoints) == 1:
            return controller_endpoints[0]
        if len(compatible) == 1:
            return compatible[0]
        if len(compatible) > 1:
            # Different channels of the same logical function remain equivalent
            # only when their identity has already been explicitly supplied.
            labels = ', '.join(str(item.get('name') or item['id']) for item in compatible)
            raise EngineeringValidationError(f'{name}: logische Schnittstelle ist mehrdeutig ({labels}). '
                                             'Empfangende Funktion/Schnittstelle explizit auswählen.')
        return None

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
                "WHERE r.relation_type = 'CONNECTED_TO' AND r.project_id = %s "
                "AND si.project_id = r.project_id AND ti.project_id = r.project_id",
                (current_project_id(),),
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
        # Canonical bus membership is a physical connection, independent of
        # whether a logical route has already published CONNECTED_TO relations.
        with get_connection() as connection:
            ports = connection.execute(
                "SELECT * FROM engineering_hardware_interfaces WHERE project_id = %s AND network_ref IS NOT NULL",
                (current_project_id(),),
            ).fetchall()
        for left in ports:
            for right in ports:
                source, target = str(left['hardware_node_id']), str(right['hardware_node_id'])
                if source == target or not left.get('network_ref') or left['network_ref'] != right.get('network_ref') or left['technology'] != right['technology']:
                    continue
                adjacency[source].add(target)
                edge_data[(source, target)] = {'source_interface_type': left['technology'], 'target_interface_type': right['technology'],
                                              'source_network_id': left['network_ref'], 'target_network_id': right['network_ref']}
        return adjacency, edge_data

    def find_candidate_paths(self, source_node_id: str, target_node_id: str, limit: int = 5) -> list[dict[str, Any]]:
        source = self._node(source_node_id)
        target = self._node(target_node_id)
        source_id = str(source["id"])
        target_id = str(target["id"])
        context = getattr(self, '_candidate_context', None)
        if context is None or context.get('project_id') != current_project_id():
            context = {'project_id': current_project_id()}
        if 'hardware_graph' not in context:
            context['hardware_graph'] = self._hardware_graph()
        adjacency, edge_data = context['hardware_graph']
        queue = deque([[source_id]])
        # A dense shared bus has exponentially many simple walks. Keep only a
        # bounded number of shortest arrivals at each node, including when the
        # destination is disconnected. Queue size is at most limit * nodes.
        arrivals = {source_id: 1}
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
                if neighbor not in path and arrivals.get(neighbor, 0) < max(1, limit):
                    arrivals[neighbor] = arrivals.get(neighbor, 0) + 1
                    queue.append([*path, neighbor])

        # A direct candidate remains useful for incomplete imported graphs; validation marks missing interfaces.
        if not paths:
            paths = [[source_id, target_id]]
        if 'hardware_nodes' not in context:
            with get_connection() as connection:
                context['hardware_nodes'] = {
                    str(row["id"]): row
                    for row in connection.execute(
                        "SELECT id, name, device_type, identity FROM engineering_hardware_nodes "
                        "WHERE project_id = %s",
                        (current_project_id(),),
                    ).fetchall()
                }
        nodes = context['hardware_nodes']
        candidates = []
        for path in paths:
            connections = [edge_data.get((left, right), {}) for left, right in zip(path, path[1:])]
            # A node-level graph cannot prove a change between an ECU's ports.
            # Such transitions need the exact directed physical path below.
            if any(nodes.get(node_id, {}).get('device_type') != 'Gateway'
                   and (not connections[index].get('target_network_id')
                        or connections[index].get('target_network_id') != connections[index + 1].get('source_network_id'))
                   for index, node_id in enumerate(path[1:-1])):
                continue
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
        from .forwarding_candidates import confirmed_ecu_candidates
        candidates.extend(confirmed_ecu_candidates(source_id, target_id, nodes, limit, context=context))
        self._candidate_planner = context.get('forwarding_planner')
        if not candidates:
            # Keep an unresolved proposal reviewable, without inventing a relay.
            candidates.append({'nodes': [{'node_id': source_id, 'name': source['name']},
                                          {'node_id': target_id, 'name': target['name']}],
                               'connections': [], 'gateways': [], 'protocol': 'CUSTOM', 'hop_count': 1})
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
        timing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = self._node(source_node_id)
        destination = self._node(destination_node_id)
        self._candidate_planner = None
        candidates = self.find_candidate_paths(str(source["id"]), str(destination["id"]))
        message = self._message_context(message_id)
        allowed_source_ids = message_hardware_interface_ids(message)
        candidate = next((item for item in candidates if not item.get('physical_paths') or not allowed_source_ids
                          or item['physical_paths'][0]['ports'][0] in allowed_source_ids), candidates[0])
        connections = candidate.get("connections") or []
        source_interfaces = self._interface_candidates(str(source["id"]))
        destination_interfaces = self._interface_candidates(str(destination["id"]))
        if message:
            from .payload_scope import message_scope, scope_allows
            scope = message_scope(message)
            options = destination_interfaces or [{}]
            if not any(scope_allows(scope, {"node_id": str(destination["id"]), "interface_id": str(item.get("id") or "")},
                {str(item.get("id") or ""): item}) for item in options):
                raise EngineeringValidationError(f"{message.get('name')}: lokale Sensor-/Aktordaten sind für diesen Empfänger nicht vorgesehen. Einen Funktionsausgang wählen.")
        source_hardware_interfaces = self._hardware_interface_candidates(str(source["id"]))
        destination_hardware_interfaces = self._hardware_interface_candidates(str(destination["id"]))
        if destination.get("device_type") == "Gateway":
            stable_gateway_interfaces = [
                item for item in destination_interfaces
                if not is_gateway_fanout_interface(item)
            ]
            if stable_gateway_interfaces:
                destination_interfaces = stable_gateway_interfaces

        source_interface_id = connections[0].get("source_interface_id") if connections else None
        bound_source_id = str((message or {}).get('interface_id') or '')
        source_interface = next((item for item in source_interfaces
            if str(item['id']) == str(bound_source_id or source_interface_id)), None)
        destination_interface_id = connections[-1].get("target_interface_id") if connections else None
        source_interface_type = str((source_interface or {}).get("interface_type") or "")

        message_hardware_interface_id = str((message or {}).get("hardware_interface_id") or "")
        allowed_source_ids = message_hardware_interface_ids(message)
        explicit_source_ids = explicit_transmit_interface_ids(message)
        source_hardware_interfaces.sort(key=lambda item: (bool(explicit_source_ids) and str(item['id']) not in explicit_source_ids,
            str(item['id']) != message_hardware_interface_id))
        shared_hardware_pair = next(
            (
                (source_hardware, destination_hardware)
                for source_hardware in source_hardware_interfaces
                for destination_hardware in destination_hardware_interfaces
                if source_hardware.get("network_ref")
                and source_hardware.get("network_ref") == destination_hardware.get("network_ref")
                and source_hardware.get("technology") == destination_hardware.get("technology")
                and (
                    not allowed_source_ids
                    or str(source_hardware.get("id")) in allowed_source_ids
                )
            ),
            None,
        )
        if shared_hardware_pair is None and not allowed_source_ids:
            shared_hardware_pair = next(
                (
                    (source_hardware, destination_hardware)
                    for source_hardware in source_hardware_interfaces
                    for destination_hardware in destination_hardware_interfaces
                    if source_hardware.get("network_ref")
                    and source_hardware.get("network_ref") == destination_hardware.get("network_ref")
                    and source_hardware.get("technology") == destination_hardware.get("technology")
                ),
                None,
            )
        source_hardware_interface = shared_hardware_pair[0] if shared_hardware_pair else next(
            (item for item in source_hardware_interfaces if str(item.get("id")) in (explicit_source_ids or allowed_source_ids)),
            source_hardware_interfaces[0] if source_hardware_interfaces else None,
        )
        destination_hardware_interface = shared_hardware_pair[1] if shared_hardware_pair else next(
            (
                item for item in destination_hardware_interfaces
                if source_hardware_interface
                and item.get("technology") == source_hardware_interface.get("technology")
            ),
            destination_hardware_interfaces[0] if destination_hardware_interfaces else None,
        )

        # Equal technology does not connect independent buses. Leave an unknown
        # receiving port unbound rather than choosing the first local sensor bus.
        if shared_hardware_pair is None and not candidate.get("gateways"):
            destination_hardware_interface = None

        if not shared_hardware_pair and connections and candidate.get('gateways'):
            destination_network = connections[-1].get('target_network_id')
            if destination_network:
                destination_hardware_interface = next((item for item in destination_hardware_interfaces if item.get('network_ref') == destination_network), None)
        if not shared_hardware_pair and candidate.get('physical_paths'):
            physical_ports = candidate['physical_paths'][0]['ports']
            source_hardware_interface = next((item for item in source_hardware_interfaces
                if str(item['id']) == physical_ports[0] and (not allowed_source_ids or str(item['id']) in allowed_source_ids)), None)
            destination_hardware_interface = next((item for item in destination_hardware_interfaces
                if str(item['id']) == physical_ports[-1]), None)
        if shared_hardware_pair:
            candidate = {**candidate, 'nodes': [{'node_id': str(source['id']), 'name': source['name']}, {'node_id': str(destination['id']), 'name': destination['name']}], 'gateways': [], 'hop_count': 1, 'physical_paths': []}
            connections = [{'source_network_id': shared_hardware_pair[0]['network_ref'],
                            'target_network_id': shared_hardware_pair[1]['network_ref'],
                            'source_interface_type': shared_hardware_pair[0]['technology']}]
        source_interface = self._logical_endpoint(source_interfaces, source_hardware_interface,
            preferred_id=source_interface_id, bound_id=bound_source_id, name=source['name'])
        destination_interface = self._logical_endpoint(destination_interfaces, destination_hardware_interface,
            preferred_id=destination_interface_id, name=destination['name'])
        transport_type = str((source_hardware_interface or {}).get("technology") or source_interface_type)
        protocol = INTERFACE_TO_PROTOCOL.get(transport_type, str(candidate.get("protocol") or "CUSTOM"))
        source_interface_id = str(source_interface["id"]) if source_interface else None
        destination_interface_id = (
            str(destination_interface["id"]) if destination_interface else None
        )
        cycle_time_ms = float(message.get("cycle_ms") or 100) if message else 100
        route = {
            "name": f"{source['name']} → {destination['name']}",
            "description": "Graphbasierter Routing-Vorschlag des Engineering-Agenten.",
            "source": {
                "node_id": str(source["id"]),
                "port_id": str(source_hardware_interface["id"]) if source_hardware_interface else None,
                "interface_id": source_interface_id,
                "network_id": (source_hardware_interface or {}).get("network_ref"),
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
                    "port_id": str(destination_hardware_interface["id"]) if destination_hardware_interface else None,
                    "interface_id": destination_interface_id,
                    "network_id": (destination_hardware_interface or {}).get("network_ref"),
                    "protocol": INTERFACE_TO_PROTOCOL.get(
                        str((destination_hardware_interface or {}).get("technology") or (destination_interface or {}).get("interface_type") or ""),
                        protocol,
                    ),
                }
            ],
            "route": {
                "hops": candidate["nodes"],
                "gateways": candidate["gateways"],
                **({'physical_paths': candidate['physical_paths']} if candidate.get('physical_paths') else {}),
                "transport_segments": [
                    {'source_node_id': candidate['nodes'][index]['node_id'],
                     'target_node_id': candidate['nodes'][index + 1]['node_id'],
                     'network_id': connection['source_network_id'],
                     'protocol': INTERFACE_TO_PROTOCOL.get(str(connection.get('source_interface_type') or ''), protocol)}
                    for index, connection in enumerate(connections)
                    if connection.get('source_network_id') and index + 1 < len(candidate['nodes'])
                ],
                "transformations": [],
                "priority": "NORMAL",
            },
            "timing": generated_timing(cycle_time_ms, message, timing),
            "routing_policy": {
                "routing_type": routing_type,
                "redundancy": "NONE",
                "fallback_route_id": None,
                "conditions": [],
            },
            "origin": "AI_GENERATED",
            "confidence": candidate["score"],
        }
        validation = RoutingValidator(physical_planner=self._candidate_planner).validate(route)
        scope_error = next((issue for issue in validation.get("errors", []) if issue.get("code") in {
            "LOCAL_IO_RECIPIENT_MISMATCH", "MESSAGE_ROUTING_DISABLED", "SIGNAL_ROUTING_DISABLED"}), None)
        if scope_error:
            raise EngineeringValidationError(scope_error["message"])
        return {**route, "validation": validation, "candidate": candidate}

    def generate_routes(self, data: dict[str, Any]) -> dict[str, Any]:
        source_value = str(data.get("source_node_id") or data.get("source") or "").strip()
        destinations = data.get("destination_node_ids") or data.get("destinations") or []
        if isinstance(destinations, str):
            destinations = [destinations]
        if not source_value or not destinations:
            raise EngineeringValidationError("source_node_id und destination_node_ids sind erforderlich.")
        routing_type = "MULTICAST" if len(destinations) > 1 else str(data.get("routing_type") or "UNICAST")
        with routing_candidate_batch(self):
            generated = [
                self.generate_route(
                    source_node_id=source_value,
                    destination_node_id=str(destination),
                    message_id=data.get("message_id"),
                    signal_ids=data.get("signal_ids") or [],
                    routing_type="UNICAST" if len(destinations) > 1 else routing_type,
                    timing=data.get("timing"),
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
        model_review = None
        if data.get('model_review'):
            from ..agent_tools.specialist import review_candidates
            model_review = review_candidates('Routing: angeforderte Funktionspartner, Payload-Scope und technische Wegführung prüfen. ' + prompt,
                [{'id': str(index), **item} for index, item in enumerate(generated)])
            evidence.append({'kind': 'specialist_review', **model_review})
            for decision in model_review['decisions']:
                item = generated[int(decision['id'])]
                item['description'] = (item.get('description') or '') + '\nFachagent: ' + decision['reason']
                if not decision['recommended']:
                    # Keep every requested recipient in the editable draft; never
                    # silently drop a destination to turn the proposal green.
                    item['validation']['valid'] = False
                    item['validation'].setdefault('errors', []).append({'code': 'AGENT_REVIEW_REQUIRED', 'message': decision['reason']})
        proposal = create_proposal(
            {
                "prompt": prompt,
                "target_objects": [source_value, *map(str, destinations)],
                "generated_routes": [{key: value for key, value in item.items() if key != "candidate"} for item in generated],
                "retrieved_context": retrieved_context,
                "evidence": evidence,
                "confidence": min(item["confidence"] for item in generated),
                "validation_results": [item["validation"] for item in generated],
                "model": model_review['model'] if model_review else data.get("model") or "routing-generation-service",
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
                "AND project_id = %s ORDER BY CASE device_type WHEN 'Gateway' THEN 1 ELSE 0 END, name LIMIT 20",
                (source["id"], current_project_id()),
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
