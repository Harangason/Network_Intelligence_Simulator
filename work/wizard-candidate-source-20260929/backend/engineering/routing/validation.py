"""Technical consistency checks for routing entries and routing tables."""

from __future__ import annotations

from datetime import UTC, datetime
from copy import deepcopy
from math import ceil
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from ..db import get_connection
from ..project_context import current_project_id
from ...communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
from ...communication.technologies.catalog import DIRECT_IO_TECHNOLOGIES
from ..capacity.dimensioning import SUPPORTED_CAPACITY_PROTOCOLS

PROTOCOL_CAPACITY = {
    "CAN": (500_000, 8),
    "CAN_FD": (2_000_000, 64),
    "CAN_XL": (10_000_000, 2048),
    "LIN": (19_200, 8),
    "FLEXRAY": (10_000_000, 254),
    "ETHERNET": (100_000_000, 65_535),
    "SOME_IP": (100_000_000, 65_535),
    "TCP": (100_000_000, 65_535),
    "UDP": (100_000_000, 65_507),
    "DDS": (100_000_000, 65_535),
    "ROS_2": (100_000_000, 65_535),
    "OPC_UA": (100_000_000, 65_535),
    "ETHERCAT": (100_000_000, 1486),
    "PROFINET": (100_000_000, 1440),
    "MODBUS": (100_000, 253),
    "MODBUS_RTU": (115_200, 253),
    "MODBUS_TCP": (100_000_000, 253),
    "I2C": (400_000, 255),
    "UART": (115_200, 65_535),
    "IO_LINK": (230_400, 32),
    "SPI": (50_000_000, 65_535),
    "ARINC": (100_000, 4),
    "MIL_STD_1553": (1_000_000, 4),
    "MVB": (1_500_000, 32),
    "WTB": (1_000_000, 128),
    "ETB": (100_000_000, 1_500),
    "TRDP": (100_000_000, 65_507),
    "PCIE": (8_000_000_000, 4096),
}

INTERFACE_PROTOCOLS = {
    "CAN": {"CAN"},
    "CANopen": {"CAN"},
    "CAN_FD": {"CAN", "CAN_FD"},
    "CAN_XL": {"CAN", "CAN_FD", "CAN_XL"},
    "LIN": {"LIN"},
    "FlexRay": {"FLEXRAY"},
    "Ethernet": {"ETHERNET", "SOME_IP", "TCP", "UDP", "DDS", "ROS_2", "OPC_UA"},
    "EtherCAT": {"ETHERCAT"},
    "ProfiNET": {"PROFINET"},
    "ModbusTCP": {"MODBUS_TCP", "MODBUS", "TCP"},
    "ModbusRTU": {"MODBUS_RTU", "MODBUS"},
    "I2C": {"I2C"},
    "UART": {"UART"},
    "IO_LINK": {"IO_LINK"},
    "SPI": {"SPI"},
    "GPIO": {"GPIO"},
    "PWM": {"PWM"},
    "ADC": {"ADC"},
    "DAC": {"DAC"},
    "OPCUA": {"OPC_UA"},
    "ARINC": {"ARINC"},
    "MIL_STD_1553": {"MIL_STD_1553"},
    "MVB": {"MVB"},
    "WTB": {"WTB"},
    "ETB": {"ETB", "TRDP"},
    "TRDP": {"TRDP"},
    "PCIe": {"PCIE"},
    "Other": set(PROTOCOL_CAPACITY),
}
DIRECT_SIGNAL_PROTOCOLS = frozenset(item.upper() for item in DIRECT_IO_TECHNOLOGIES)


def physical_route_technology(value):
    """Resolve an application interface to the physical layer in its profile."""
    registry = DEFAULT_TECHNOLOGY_REGISTRY
    identifier = registry.normalize_id(str(value or ''))
    profile = registry.profile(identifier)
    stack = tuple(profile.get('default_stack') or ())
    if profile.get('layer') == 'APPLICATION' and stack and stack[0].upper() in PROTOCOL_CAPACITY:
        return stack[0].upper()
    return str(value or '')


def detect_routing_loop(hops: list[Any]) -> list[str]:
    identities: list[str] = []
    for hop in hops:
        if isinstance(hop, dict):
            identity = str(hop.get("node_id") or hop.get("network_id") or hop.get("id") or hop.get("name") or "")
        else:
            identity = str(hop)
        if identity:
            identities.append(identity)
    seen: set[str] = set()
    duplicates: list[str] = []
    for identity in identities:
        if identity in seen and identity not in duplicates:
            duplicates.append(identity)
        seen.add(identity)
    return duplicates


def is_gateway_fanout_interface(interface: dict[str, Any]) -> bool:
    name = str(interface.get("name") or "").strip().lower()
    parts = name.split("_")
    return len(parts) == 3 and parts[0] == "system" and all(part.isdigit() for part in parts[1:])


class RoutingValidator:
    """Validates references, path semantics, timing, payload and estimated load."""

    def __init__(self, project_id: str | None = None, *, physical_planner=None, model_snapshot=None):
        self.project_id = project_id or current_project_id()
        # A caller validating one atomic batch can reuse its post-mutation snapshot.
        self.physical_planner = physical_planner
        self.model_snapshot = None
        if model_snapshot is not None:
            from ..communication_repair import RepairPlanner
            tables = {'HardwareNode': 'engineering_hardware_nodes',
                      'HardwareNetworkInterface': 'engineering_hardware_interfaces',
                      'Function': 'engineering_functions', 'Interface': 'engineering_interfaces',
                      'Message': 'engineering_messages', 'Signal': 'engineering_signals'}
            required = {*tables.values(), 'engineering_routing_entries'}
            if (not isinstance(model_snapshot, dict) or model_snapshot.get('project_id') != self.project_id
                    or physical_planner is not None
                    or not isinstance(model_snapshot.get('tables'), dict)
                    or not required <= model_snapshot['tables'].keys()
                    or not isinstance(model_snapshot.get('topology'), dict)
                    or not isinstance(model_snapshot.get('parameters'), dict)):
                raise ValueError('Routing preview requires a complete snapshot of the selected project.')
            for name in required:
                rows = model_snapshot['tables'][name]
                if (not isinstance(rows, list) or any(not isinstance(row, dict) or not row.get('id')
                        or row.get('project_id', self.project_id) != self.project_id for row in rows)
                        or len({str(row['id']) for row in rows}) != len(rows)):
                    raise ValueError('Routing preview contains invalid or foreign model rows: ' + name)
            self.model_snapshot = deepcopy(model_snapshot)
            self.physical_planner = RepairPlanner(
                {key: self.model_snapshot[key] for key in ('topology', 'parameters')},
                {kind: self.model_snapshot['tables'][name] for kind, name in tables.items()},
                self.model_snapshot['tables']['engineering_routing_entries'])

    def _snapshot_rows(self, table):
        snapshot = getattr(self, 'model_snapshot', None)
        return snapshot['tables'][table] if snapshot is not None else None

    def _physical_path_mapping(
        self,
        source_node_id: str,
        destination_node_ids: list[str],
    ) -> tuple[bool | None, list[str]]:
        project_id = getattr(self, "project_id", None)
        if not project_id or not source_node_id or not destination_node_ids:
            return None, []
        hardware_interfaces = self._snapshot_rows('engineering_hardware_interfaces')
        if hardware_interfaces is None:
            with get_connection() as connection:
                hardware_interfaces = connection.execute(
                    "SELECT hardware_node_id, network_ref FROM engineering_hardware_interfaces "
                    "WHERE project_id = %s AND network_ref IS NOT NULL AND network_ref <> ''",
                    (project_id,),
                ).fetchall()
        networks_by_node: dict[str, set[str]] = {}
        for item in hardware_interfaces:
            if item.get('network_ref'):
                networks_by_node.setdefault(str(item['hardware_node_id']), set()).add(str(item['network_ref']))
        source_networks = networks_by_node.get(source_node_id, set())
        hardware_unmapped = [destination_id for destination_id in destination_node_ids
            if not source_networks.intersection(networks_by_node.get(destination_id, set()))]
        if source_networks and not hardware_unmapped:
            return True, []
        gateways = self._snapshot_rows('engineering_hardware_nodes')
        if gateways is None:
            with get_connection() as connection:
                gateways = connection.execute(
                    "SELECT id FROM engineering_hardware_nodes WHERE project_id = %s AND device_type = 'Gateway'",
                    (project_id,),
                ).fetchall()
        else:
            gateways = [row for row in gateways if row.get('device_type') == 'Gateway']
        reachable_networks = set(source_networks)
        while True:
            before = len(reachable_networks)
            for gateway in gateways:
                gateway_networks = networks_by_node.get(str(gateway['id']), set())
                if reachable_networks.intersection(gateway_networks):
                    reachable_networks.update(gateway_networks)
            if len(reachable_networks) == before:
                break
        if reachable_networks and all(reachable_networks.intersection(networks_by_node.get(destination, set())) for destination in destination_node_ids):
            return True, []
        snapshot = getattr(self, 'model_snapshot', None)
        if snapshot is None:
            with get_connection() as connection:
                row = connection.execute("SELECT topology FROM engineering_workflow_projects WHERE project_id = %s", (project_id,)).fetchone()
            topology = row.get('topology') if row else None
        else:
            topology = snapshot['topology']
        if not isinstance(topology, dict):
            return False, destination_node_ids
        nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
        edges = topology.get("edges") if isinstance(topology.get("edges"), list) else []
        engineering_to_topology = {
            str(node.get("engineeringId") or node.get("engineering_id")): str(node.get("id"))
            for node in nodes
            if isinstance(node, dict)
            and node.get("id")
            and (node.get("engineeringId") or node.get("engineering_id"))
        }
        source_topology_id = engineering_to_topology.get(source_node_id)
        if not source_topology_id:
            return False, destination_node_ids
        adjacency: dict[str, set[str]] = {}
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            if source and target:
                adjacency.setdefault(source, set()).add(target)
                adjacency.setdefault(target, set()).add(source)

        reachable = {source_topology_id}
        frontier = [source_topology_id]
        while frontier:
            current = frontier.pop()
            for neighbor in adjacency.get(current, set()):
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    frontier.append(neighbor)
        unmapped = [
            destination_id
            for destination_id in destination_node_ids
            if engineering_to_topology.get(destination_id) not in reachable
        ]
        return not unmapped, unmapped

    def _rows(self, table: str, ids: list[str]) -> dict[str, dict[str, Any]]:
        if not ids:
            return {}
        preview = self._snapshot_rows(table)
        if preview is not None:
            return {str(row['id']): row for row in preview if str(row['id']) in ids}
        with get_connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE id = ANY(%s::uuid[]) AND project_id = %s",
                (ids, self.project_id),
            ).fetchall()
        return {str(row["id"]): row for row in rows}

    def _canonical_transport_segments(self, source, destinations, path):
        """Read each modeled hop's actual bus, including intermediate gateways.

        Stored segment IDs disambiguate parallel buses but are not trusted as
        technology evidence: both adjacent nodes must own ports on that bus.
        Legacy/test routes without a project retain their endpoint checks.
        """
        if not getattr(self, 'project_id', None):
            return []
        node_id = lambda item: str(item.get('node_id') or item.get('id') or '') if isinstance(item, dict) else str(item)
        hops = [node_id(item) for item in path.get('hops') or []]
        if len(hops) < 2:
            return []
        try:
            ids = [str(UUID(item)) for item in dict.fromkeys(hops)]
        except ValueError:
            return []  # Editor aliases are checked through physical_paths.
        ports = self._snapshot_rows('engineering_hardware_interfaces')
        if ports is None:
            with get_connection() as connection:
                ports = connection.execute(
                    'SELECT hardware_node_id, network_ref, technology FROM engineering_hardware_interfaces '
                    'WHERE project_id=%s AND hardware_node_id=ANY(%s::uuid[]) AND network_ref IS NOT NULL',
                    (self.project_id, ids),
                ).fetchall()
        else:
            ports = [port for port in ports if str(port['hardware_node_id']) in ids and port.get('network_ref')]
        by_node = {}
        for port in ports:
            network = str(port.get('network_ref') or '')
            if network:
                by_node.setdefault(str(port['hardware_node_id']), {}).setdefault(network, set()).add(
                    physical_route_technology(port['technology']))
        declared = {(str(item.get('source_node_id')), str(item.get('target_node_id'))): str(item.get('network_id') or '')
                    for item in path.get('transport_segments') or [] if isinstance(item, dict)}
        destination_networks = {str(item.get('node_id')): str(item.get('network_id') or '') for item in destinations}
        segments = []
        for index, (left, right) in enumerate(zip(hops, hops[1:])):
            shared = set(by_node.get(left, {})) & set(by_node.get(right, {}))
            preferred = (str(source.get('network_id') or '') if index == 0 else '') or \
                destination_networks.get(right) or declared.get((left, right))
            if preferred:
                shared &= {preferred}
            if len(shared) != 1:
                # Path existence is separately validated. Without unique channel
                # evidence no intermediate payload/technology acceptance is valid.
                segments.append({'error': 'PHYSICAL_SEGMENT_AMBIGUOUS' if len(shared) > 1 else 'PHYSICAL_SEGMENT_UNRESOLVED',
                                 'source_node_id': left, 'target_node_id': right})
                continue
            network = next(iter(shared))
            technologies = by_node[left][network] & by_node[right][network]
            if len(technologies) != 1:
                segments.append({'error': 'PHYSICAL_SEGMENT_TECHNOLOGY_MISMATCH', 'network_id': network,
                                 'source_node_id': left, 'target_node_id': right})
                continue
            technology = next(iter(technologies))
            # The canonical registered identity is retained even when no
            # capacity model exists. A foreign CUSTOM rate must not be inferred.
            segments.append({'network_id': network, 'protocol': technology.upper(),
                             'source_node_id': left, 'target_node_id': right})
        return segments

    def _find_duplicates(
        self,
        source_node_id: str,
        payload: dict[str, Any],
        destinations: list[dict[str, Any]],
        exclude_route_id: str | None,
    ) -> list[dict[str, Any]]:
        def key(content, endpoints):
            selected = {field: sorted({str(item) for item in [*(content.get(field) or []), *([content.get(single)] if content.get(single) else [])] if item})
                        for field, single in (("message_ids", "message_id"), ("interface_definition_ids", "interface_definition_id"), ("signal_ids", "signal_id"))}
            selected.update({field: value for field, value in content.items() if field not in {"message_ids", "message_id", "interface_definition_ids", "interface_definition_id", "signal_ids", "signal_id"} and value not in (None, "", [], {})})
            destinations_key = sorted(tuple(str(item.get(field) or "") for field in ("node_id", "interface_id", "port_id", "network_id")) for item in endpoints)
            return selected, destinations_key
        rows = self._snapshot_rows('engineering_routing_entries')
        if rows is None:
            with get_connection() as connection:
                rows = connection.execute(
                    "SELECT id, route_code, payload, destinations FROM engineering_routing_entries "
                    "WHERE source ->> 'node_id' = %s "
                    "AND (%s::uuid IS NULL OR id <> %s::uuid) "
                    "AND status NOT IN ('REJECTED', 'SUPERSEDED', 'OUTDATED', 'DEPRECATED') AND project_id = %s",
                    (source_node_id, exclude_route_id, exclude_route_id, self.project_id),
                ).fetchall()
        else:
            rows = [row for row in rows if str((row.get('source') or {}).get('node_id')) == source_node_id
                    and str(row['id']) != exclude_route_id
                    and row.get('status') not in {'REJECTED', 'SUPERSEDED', 'OUTDATED', 'DEPRECATED'}]
        expected = key(payload, destinations)
        return [row for row in rows if key(row["payload"], row["destinations"]) == expected]

    def _messages_with_signals(self, message_ids: list[str]) -> set[str]:
        if not message_ids:
            return set()
        preview = self._snapshot_rows('engineering_signals')
        if preview is not None:
            return {str(row['message_id']) for row in preview if str(row.get('message_id')) in message_ids}
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT DISTINCT message_id FROM engineering_signals "
                "WHERE project_id = %s AND message_id = ANY(%s::uuid[])",
                (self.project_id, message_ids),
            ).fetchall()
        return {str(row["message_id"]) for row in rows}

    def _non_routed_frame_signals(self, message_ids):
        if not message_ids or not getattr(self, "project_id", None):
            return {}
        preview = self._snapshot_rows('engineering_signals')
        if preview is not None:
            return {str(row['id']): row for row in preview if str(row.get('message_id')) in message_ids
                    and ((row.get('configuration') or {}).get('routing') or {}).get('enabled') is False}
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT id, message_id, name, configuration FROM engineering_signals "
                "WHERE project_id=%s AND message_id=ANY(%s::uuid[]) "
                "AND configuration->'routing'->'enabled' = 'false'::jsonb",
                (self.project_id, message_ids),
            ).fetchall()
        return {str(row["id"]): row for row in rows}

    def validate(self, route: dict[str, Any], *, exclude_route_id: str | None = None) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        evidence: list[dict[str, Any]] = []

        def error(code: str, message: str) -> None:
            errors.append({"code": code, "message": message})

        def warn(code: str, message: str) -> None:
            warnings.append({"code": code, "message": message})

        source = route.get("source") or {}
        destinations = route.get("destinations") or []
        payload = route.get("payload") or {}
        path = route.get("route") or {}
        timing = route.get("timing") or {}
        policy = route.get("routing_policy") or {}

        source_node_id = str(source.get("node_id") or "")
        destination_node_ids = [str(item.get("node_id") or "") for item in destinations if isinstance(item, dict)]
        node_ids = [item for item in [source_node_id, *destination_node_ids] if item]
        nodes = self._rows("engineering_hardware_nodes", node_ids)
        if source_node_id not in nodes:
            error("SOURCE_NOT_FOUND", "Der Source Hardware Node existiert nicht.")
        for node_id in destination_node_ids:
            if node_id not in nodes:
                error("DESTINATION_NOT_FOUND", f"Destination {node_id} existiert nicht.")
            if node_id == source_node_id:
                error("SOURCE_EQUALS_DESTINATION", "Source und Destination dürfen nicht identisch sein.")

        physical_path_mapped, unmapped_destinations = self._physical_path_mapping(
            source_node_id,
            destination_node_ids,
        )
        if physical_path_mapped is False:
            error(
                "UNMAPPED_ROUTE",
                "Für diese Route existiert im Netzwerk-Editor noch kein physischer Pfad.",
            )

        interface_ids = [str(source.get("interface_id") or "")]
        interface_ids.extend(str(item.get("interface_id") or "") for item in destinations if isinstance(item, dict))
        interface_ids = [item for item in interface_ids if item]
        interfaces = self._rows("engineering_interfaces", interface_ids)
        intent = path.get('functional_intent') or {}
        if intent:
            anchors = [intent.get('source') or {}, *(intent.get('destinations') or [])]
            actual = [source, *destinations]
            function_ids = [str(a['function_id']) for a in anchors if a.get('function_id')]
            functions = self._rows('engineering_functions', function_ids)
            if len(anchors) != len(actual):
                error('FUNCTION_PARTNERS_CHANGED', 'Die Route enthält nicht mehr alle gespeicherten Partnerfunktionen.')
            for anchor, endpoint in zip(anchors, actual):
                function_id = str(anchor.get('function_id') or '')
                if not function_id:
                    if anchor.get('partner_type') == 'hardware_io':
                        if str(anchor.get('hardware_node_id')) != str(endpoint.get('node_id')):
                            error('IO_PARTNER_CHANGED', 'Der physische Weg ersetzt den bisherigen Geräte-I/O-Partner.')
                        continue
                    warn('FUNCTION_PARTNER_UNRESOLVED', 'Eine bisherige Partnerfunktion ist noch nicht eindeutig belegt.')
                    continue
                function = functions.get(function_id)
                interface = interfaces.get(str(endpoint.get('interface_id')))
                if not function:
                    error('FUNCTION_PARTNER_MISSING', 'Eine gespeicherte Partnerfunktion fehlt im kanonischen Modell.')
                elif str(function.get('hardware_node_id')) != str(endpoint.get('node_id')):
                    error('FUNCTION_HARDWARE_MISMATCH', 'Die Route folgt nicht der aktuellen Hardwarezuordnung ihrer Partnerfunktion.')
                if interface and str(interface.get('function_id')) != function_id:
                    error('FUNCTION_PARTNERS_CHANGED', 'Ein Routing-Endpunkt ersetzt die bisherige Partnerfunktion durch eine andere Funktion.')
                if endpoint.get('function_id') and str(endpoint['function_id']) != function_id:
                    error('FUNCTION_PARTNERS_CHANGED', 'Die Funktion des Endpunkts widerspricht der gespeicherten Kommunikation.')
        source_interface_id = str(source.get("interface_id") or "")
        if source_interface_id:
            source_interface = interfaces.get(source_interface_id)
            if source_interface is None:
                error("SOURCE_INTERFACE_NOT_FOUND", "Das Source Interface existiert nicht.")
            elif source_interface.get("hardware_node_id") and str(source_interface["hardware_node_id"]) != source_node_id:
                error("SOURCE_INTERFACE_MISMATCH", "Das Source Interface gehört nicht zum Source Node.")
        else:
            warn("SOURCE_INTERFACE_MISSING", "Kein Source Interface ausgewählt.")

        for destination in destinations:
            interface_id = str(destination.get("interface_id") or "")
            if not interface_id:
                warn("DESTINATION_INTERFACE_MISSING", f"Für {destination.get('node_id')} ist kein Ziel-Interface gesetzt.")
                continue
            interface = interfaces.get(interface_id)
            if interface is None:
                error("DESTINATION_INTERFACE_NOT_FOUND", f"Destination Interface {interface_id} existiert nicht.")
            elif interface.get("hardware_node_id") and str(interface["hardware_node_id"]) != str(destination.get("node_id")):
                error("DESTINATION_INTERFACE_MISMATCH", "Ein Destination Interface gehört nicht zum gewählten Node.")

        raw_hardware_interface_ids = [str(source.get("port_id") or "")]
        raw_hardware_interface_ids.extend(str(item.get("port_id") or "") for item in destinations if isinstance(item, dict))
        hardware_interface_ids = []
        for item in raw_hardware_interface_ids:
            try:
                hardware_interface_ids.append(str(UUID(item)))
            except (ValueError, TypeError, AttributeError):
                # A synchronized topology uses stable port names instead of
                # canonical HardwareNetworkInterface UUIDs.
                continue
        hardware_interfaces = self._rows("engineering_hardware_interfaces", hardware_interface_ids)
        source_port_id = str(source.get("port_id") or "")
        if source_port_id in hardware_interface_ids:
            source_port = hardware_interfaces.get(source_port_id)
            if source_port is None:
                error("SOURCE_HARDWARE_INTERFACE_NOT_FOUND", "Das physische Source Hardware Interface existiert nicht.")
            elif str(source_port.get("hardware_node_id") or "") != source_node_id:
                error("SOURCE_HARDWARE_INTERFACE_MISMATCH", "Das physische Source Interface gehört nicht zum Source Node.")
        for destination in destinations:
            port_id = str(destination.get("port_id") or "")
            if port_id not in hardware_interface_ids:
                continue
            port = hardware_interfaces.get(port_id)
            if port is None:
                error("DESTINATION_HARDWARE_INTERFACE_NOT_FOUND", f"Hardware Interface {port_id} existiert nicht.")
            elif str(port.get("hardware_node_id") or "") != str(destination.get("node_id") or ""):
                error("DESTINATION_HARDWARE_INTERFACE_MISMATCH", "Ein physisches Destination Interface gehört nicht zum gewählten Node.")

        # Validate the selected channel, not another reachable channel on the device.
        for role, endpoint in [("SOURCE", source), *[("DESTINATION", item) for item in destinations]]:
            port = hardware_interfaces.get(str(endpoint.get("port_id") or ""))
            if port is None:
                continue  # Missing IDs/legacy aliases are handled separately above.
            network = str(port.get("network_ref") or "")
            if not network:
                error(f"{role}_HARDWARE_INTERFACE_UNASSIGNED",
                      f"Anschluss {port.get('name')} ist keinem physischen Bus zugeordnet.")
            elif network != str(endpoint.get("network_id") or ""):
                error(f"{role}_HARDWARE_NETWORK_MISMATCH",
                      f"Der Bus der Route stimmt nicht mit der aktuellen Buszuordnung von Anschluss {port.get('name')} überein.")

        # A valid hardware port does not excuse a stale logical interface after
        # a bus change. Check each endpoint's own protocol (gateway paths may differ).
        for role, endpoint in [("SOURCE", source), *[("DESTINATION", item) for item in destinations]]:
            interface = interfaces.get(str(endpoint.get("interface_id") or ""))
            endpoint_protocol = str(endpoint.get("protocol") or source.get("protocol") or "CUSTOM").upper()
            if interface and endpoint_protocol not in INTERFACE_PROTOCOLS.get(interface.get("interface_type"), set(PROTOCOL_CAPACITY)):
                error(f"{role}_LOGICAL_PROTOCOL_MISMATCH",
                      f"Kommunikationsschnittstelle {interface.get('name')} ({interface.get('interface_type')}) passt nicht zum {endpoint_protocol}-Anschluss.")

        message_ids = list(dict.fromkeys([
            *[str(item) for item in payload.get("message_ids", []) if item],
            *([str(payload.get("message_id"))] if payload.get("message_id") else []),
        ]))
        messages = self._rows("engineering_messages", message_ids)
        for message_id in message_ids:
            if message_id not in messages:
                error("MESSAGE_NOT_FOUND", f"Die referenzierte Message {message_id} existiert nicht.")
        generated_commands = [mid for mid, item in messages.items()
            if (((item.get("configuration") or {}).get("transport_unit") or {}).get("provenance") or {}).get("generator") == "wizard-local-actuator-command"]
        defined_commands = self._messages_with_signals(generated_commands) if generated_commands else set()
        for mid in generated_commands:
            if mid not in defined_commands:
                error("COMMAND_SIGNALS_MISSING", f"Befehl {messages[mid].get('name', mid)} ist unvollständig: Signale, Bitbelegung und Wertebereiche fehlen. Aktorfunktion nicht spezifiziert.")
        message = messages.get(message_ids[0]) if message_ids else None
        for message_id in message_ids:
            bound_message = messages.get(message_id)
            if bound_message is None:
                continue
            message_name = str(bound_message.get("name") or message_id)
            message_interface_id = str(bound_message.get("interface_id") or "")
            if message_interface_id and message_interface_id != source_interface_id:
                error(
                    "MESSAGE_SOURCE_INTERFACE_MISMATCH",
                    f"Message {message_name} ist an das logische Interface {message_interface_id} gebunden; "
                    f"die Route verwendet als Source {source_interface_id or 'kein logisches Interface'}.",
                )
            message_hardware_interface_id = str(bound_message.get("hardware_interface_id") or "")
            explicit_binding = any(
                str(binding.get('hardware_interface_id') or '') == source_port_id
                and str(binding.get('network_id') or '') == str(source.get('network_id') or '')
                and bool(binding.get('network_id'))
                and str((hardware_interfaces.get(source_port_id) or {}).get('network_ref') or '') == str(binding['network_id'])
                for binding in (bound_message.get('configuration') or {}).get('physical_transmit_bindings') or []
                if isinstance(binding, dict)
            )
            if message_hardware_interface_id and message_hardware_interface_id != source_port_id and not explicit_binding:
                error(
                    "MESSAGE_SOURCE_HARDWARE_INTERFACE_MISMATCH",
                    f"Message {message_name} ist an das physische Hardware Interface "
                    f"{message_hardware_interface_id} gebunden; die Route verwendet als Source "
                    f"{source_port_id or 'kein physisches Hardware Interface'}.",
                )

        signal_ids = [str(item) for item in payload.get("signal_ids", []) if item]
        signals = self._rows("engineering_signals", signal_ids)
        from .payload_scope import payload_scope_issues
        signal_message_ids = list({str(item.get("message_id")) for item in signals.values() if item.get("message_id")} - set(messages))
        scope_messages = {**messages, **(self._rows("engineering_messages", signal_message_ids) if signal_message_ids else {})}
        scope_signals = {**signals, **self._non_routed_frame_signals(list(scope_messages))}
        for issue in payload_scope_issues(route, scope_messages, scope_signals, interfaces):
            error(issue["code"], issue["message"])
        for signal_id in signal_ids:
            signal = signals.get(signal_id)
            if signal is None:
                error("SIGNAL_NOT_FOUND", f"Signal {signal_id} existiert nicht.")
            elif message_ids and str(signal.get("message_id") or "") not in message_ids:
                error("SIGNAL_MESSAGE_MISMATCH", f"Signal {signal.get('name')} gehört zu keiner gewählten Message.")
        if not message_ids and not signal_ids and not payload.get("topic") and not payload.get("data_object"):
            warn("PAYLOAD_UNSPECIFIED", "Die Route hat noch keinen konkreten Payload.")

        protocol = str(source.get("protocol") or "CUSTOM").upper()
        if protocol not in SUPPORTED_CAPACITY_PROTOCOLS and protocol not in DIRECT_SIGNAL_PROTOCOLS:
            warn("CAPACITY_MODEL_UNVERIFIED", f"Für {protocol} fehlt ein technologiespezifischer Kapazitäts- und Zeitnachweis.")
        if source.get("port_id") and any(not destination.get("port_id") for destination in destinations):
            error("DESTINATION_PHYSICAL_PORT_MISSING", "Empfänger besitzt keinen nachgewiesenen Anschluss für diesen Transport.")
        source_network_id = str(source.get("network_id") or "").strip().casefold()
        destination_network_ids = [
            str(destination.get("network_id") or "").strip().casefold()
            if isinstance(destination, dict)
            else ""
            for destination in destinations
        ]
        shared_network_transport = bool(
            source_network_id
            and destination_network_ids
            and all(
                network_id and network_id == source_network_id
                for network_id in destination_network_ids
            )
        )
        if source_network_id and any(destination_network_ids) and not shared_network_transport and not path.get("gateways"):
            error("INDEPENDENT_BUSES_WITHOUT_GATEWAY", "Unabhängige physische Busse benötigen einen expliziten Gateway-Pfad.")
        if shared_network_transport and path.get("gateways"):
            error(
                "GATEWAY_ON_SHARED_NETWORK",
                "Source und alle Destinations liegen explizit im selben Netzwerk; "
                "ein Gateway-Hop ist für diesen direkten Pfad nicht zulässig.",
            )
        protocol_interfaces = hardware_interfaces.values() if hardware_interface_ids \
            else [] if shared_network_transport \
            else interfaces.values()
        for interface in protocol_interfaces:
            if is_gateway_fanout_interface(interface):
                error(
                    "GATEWAY_FANOUT_INTERFACE",
                    f"Interface {interface.get('name')} ist ein Systemgateway-Fanout-Duplikat und darf nicht als Routing-Endpunkt verwendet werden.",
                )
            interface_type = str(interface.get("technology") or interface.get("interface_type") or "Other")
            supported = INTERFACE_PROTOCOLS.get(interface_type, set(PROTOCOL_CAPACITY))
            if protocol not in supported and not path.get("transformations"):
                error(
                    "PROTOCOL_INCOMPATIBLE",
                    f"Interface {interface.get('name')} unterstützt {protocol} nicht; eine Transformation fehlt.",
                )

        loop_nodes = detect_routing_loop(path.get("hops", []))
        if loop_nodes:
            error("ROUTING_LOOP", f"Routing loop detected: {', '.join(loop_nodes)}.")

        gateways = [str(item.get("node_id") if isinstance(item, dict) else item) for item in path.get("gateways", [])]
        gateway_rows = self._rows("engineering_hardware_nodes", [item for item in gateways if item])
        physical_paths = path.get('physical_paths') or []
        forwarding_evidence = set()
        physical_transport_segments = []
        if physical_paths:
            from ..communication_repair import load_plan
            from .forwarding import forwarding_permitted
            planner = getattr(self, 'physical_planner', None)
            if planner is None:
                planner, _ = load_plan()
            expected_source = str((planner.resolve(source.get('port_id')) or {}).get('id'))
            expected_targets = {str((planner.resolve(e.get('port_id')) or {}).get('id')) for e in destinations}
            reached = set()
            for physical in physical_paths:
                ports = physical.get('ports') or []
                if not ports or ports[0] != expected_source or ports[-1] not in expected_targets:
                    error('PHYSICAL_PATH_ENDPOINT_MISMATCH', 'Der gespeicherte Signalweg gehört nicht zu Quelle und Empfängern dieser Route.')
                    continue
                reached.add(ports[-1])
                if len(ports) != len(set(ports)):
                    error('PHYSICAL_PATH_LOOP', 'Der gespeicherte physische Signalweg enthält eine Schleife.')
                for a, b in zip(ports, ports[1:]):
                    matching = [(n, e) for n, e in planner.graph.get(a, []) if n == b]
                    if not matching:
                        error('PHYSICAL_PATH_REMOVED', 'Eine Verbindung oder bestätigte Weiterleitung des gespeicherten Signalwegs fehlt.')
                        continue
                    left, right = planner.active[a], planner.active[b]
                    if left['network_ref'] == right['network_ref']:
                        physical_transport_segments.append({'network_id': left['network_ref'],
                            'protocol': str(left.get('technology') or '').upper()})
                    if left['network_ref'] != right['network_ref']:
                        hw = planner.hardware[str(left['hardware_node_id'])]
                        if forwarding_permitted(hw, left, right): forwarding_evidence.add(str(hw['id']))
                if not planner.path_is_current(physical):
                    error('PHYSICAL_EDGE_MISMATCH', 'Die Kantenliste stimmt nicht mit dem gespeicherten physischen Signalweg überein.')
            if reached != expected_targets:
                error('PHYSICAL_RECIPIENT_PATH_MISSING', 'Für mindestens einen bisherigen Empfänger fehlt der neue Signalweg.')
        for gateway_id in gateways:
            gateway = gateway_rows.get(gateway_id)
            if gateway is None:
                error("GATEWAY_NOT_FOUND", f"Gateway {gateway_id} existiert nicht.")
            elif gateway.get("device_type") != "Gateway" and gateway_id not in forwarding_evidence:
                error("INVALID_GATEWAY", f"{gateway.get('name')} ist nicht als Gateway klassifiziert.")

        if policy.get("routing_type") == "MULTICAST" and len(destinations) < 2:
            warn("MULTICAST_SINGLE_TARGET", "MULTICAST hat nur einen Consumer.")
        if policy.get("routing_type") == "UNICAST" and len(destinations) > 1:
            error("UNICAST_MULTIPLE_TARGETS", "UNICAST darf nur eine Destination enthalten.")
        if policy.get("routing_type") == "CONDITIONAL" and not policy.get("conditions"):
            error("CONDITION_MISSING", "CONDITIONAL Routing benötigt mindestens eine Bedingung.")
        if policy.get("redundancy") not in (None, "NONE") and not policy.get("fallback_route_id"):
            warn("FALLBACK_MISSING", "Redundantes Routing besitzt keine Fallback-Route.")

        # A selected value still travels in its whole canonical frame. Selecting
        # fewer signals cannot repack it, remove padding, or reduce bus demand.
        frame_sizes = {mid: int(item.get('dlc') or 0) for mid, item in scope_messages.items()}
        from ..signal_audit import occupied_signal_bits
        for signal in signals.values():
            mid = str(signal.get('message_id') or 'unassigned')
            occupied = occupied_signal_bits(signal)
            extent = ceil((max(occupied) + 1) / 8) if occupied else \
                ceil((int(signal.get('start_bit') or 0) + int(signal.get('length_bits') or 0)) / 8)
            if mid in scope_messages and extent > frame_sizes[mid]:
                error('SIGNAL_EXCEEDS_MESSAGE', f"Signal {signal.get('name')} liegt außerhalb der gespeicherten Nachrichtengröße.")
            frame_sizes[mid] = max(frame_sizes.get(mid, 0), extent)
        frame_payload_bytes = max(frame_sizes.values(), default=0)
        payload_bytes = sum(frame_sizes.values())
        payload_bits = payload_bytes * 8
        transport_segments = physical_transport_segments or self._canonical_transport_segments(source, destinations, path)
        for segment in transport_segments:
            if segment.get('error'):
                error(segment['error'], f"Physischer Abschnitt {segment.get('source_node_id')} → {segment.get('target_node_id')} ist nicht eindeutig mit passenden Anschlüssen nachgewiesen.")
        segment_protocols = {str(segment.get('protocol') or '').upper() for segment in transport_segments if segment.get('protocol')}
        segment_protocols.update(str(item.get('protocol') or protocol).upper() for item in [source, *destinations])
        for segment_protocol in sorted(segment_protocols):
            if segment_protocol in DIRECT_SIGNAL_PROTOCOLS:
                continue
            try:
                profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(segment_protocol)
            except KeyError:
                profile = None
            capacity = PROTOCOL_CAPACITY.get(segment_protocol)
            max_payload = profile.get("max_payload_bytes") if profile else capacity[1] if capacity else None
            if max_payload is not None and frame_payload_bytes > max_payload:
                error("PAYLOAD_TOO_LARGE", f"Payload {frame_payload_bytes} Byte überschreitet {max_payload} Byte für {segment_protocol}. Eine Protokollübersetzung allein erzeugt keine kleinere kodierte Nachricht.")
        bitrate = source.get("bitrate") if protocol in SUPPORTED_CAPACITY_PROTOCOLS else None
        if not isinstance(bitrate, (int, float)) or isinstance(bitrate, bool) or bitrate <= 0:
            bitrate = None

        hop_count = max(1, len(path.get("hops", [])) - 1)
        gateway_count = len(gateways)
        estimated_latency_ms = round(0.2 + hop_count * 0.35 + gateway_count * 0.8, 3)
        max_latency = timing.get("max_latency_ms")
        if max_latency and estimated_latency_ms > float(max_latency):
            error(
                "LATENCY_UNACHIEVABLE",
                f"Geschätzte Latenz {estimated_latency_ms} ms überschreitet {max_latency} ms.",
            )
        jitter = timing.get("jitter_limit_ms")
        if jitter and float(jitter) < gateway_count * 0.1:
            warn("JITTER_TIGHT", "Das Jitter-Limit ist für die Gateway-Anzahl sehr knapp.")

        message_cycles = [float(item.get("cycle_ms")) for item in messages.values() if item.get("cycle_ms")]
        message_cycle_ms = min(message_cycles) if message_cycles else None
        cycle_ms = float(timing.get("cycle_time_ms") or message_cycle_ms or 100.0)
        cycle_ms = cycle_ms or 100.0
        requirement_sources = [timing, *[item.get("configuration") or {} for item in messages.values()],
            *[item.get("communication") or {} for item in signals.values()]]
        for field, code, label, aliases in (
            ("timeout_ms", "TIMEOUT_BELOW_CYCLE_BUDGET", "Timeout", ("timeout_ms", "timeout")),
            ("freshness_ms", "FRESHNESS_BELOW_CYCLE_BUDGET", "Freshness", ("freshness_ms", "data_freshness_limit")),
        ):
            limits = [float(source[key]) for source in requirement_sources for key in aliases
                if source.get(key) is not None and float(source[key]) > 0]
            if limits and min(limits) < cycle_ms + float(jitter or 0):
                warn(code, f"{label} {min(limits):g} ms liegt unter Zyklus plus zulässigem Jitter "
                    f"({cycle_ms:g} + {float(jitter or 0):g} ms). Der bestehende Grenzwert bleibt verbindlich; "
                    "Sendeplan oder Anforderung müssen fachlich geprüft werden.")
        route_load = (payload_bits / (cycle_ms / 1000.0) / bitrate * 100) if payload_bits and bitrate else None
        segment_loads = {}
        # Canonical physical technology wins over an endpoint's application
        # protocol when both describe the same bus.
        for item in [source, *destinations, *transport_segments]:
            network = str(item.get('network_id') or '').strip()
            if not network or item.get('error'):
                continue
            segment_protocol = str(item.get('protocol') or protocol).upper()
            if segment_protocol in DIRECT_SIGNAL_PROTOCOLS:
                continue
            segment_bitrate = item.get("bitrate")
            if (segment_protocol not in SUPPORTED_CAPACITY_PROTOCOLS
                    or not isinstance(segment_bitrate, (int, float))
                    or isinstance(segment_bitrate, bool) or segment_bitrate <= 0):
                continue
            segment_loads[network] = payload_bits / (cycle_ms / 1000.0) / segment_bitrate * 100
        segment_count = len(segment_loads) or 1
        # Preserve the route's aggregate demand indicator, deduplicating a shared
        # multicast bus. Detailed capacity/schedule evaluation remains separate.
        expected_load = sum(segment_loads.values()) if segment_loads else route_load
        peak_segment_load = max(segment_loads.values(), default=route_load)
        if peak_segment_load is not None and peak_segment_load > 90:
            error("BUS_LOAD_CRITICAL", f"Erwartete zusätzliche Buslast {peak_segment_load:.1f} % auf einem Abschnitt ist kritisch.")
        elif peak_segment_load is not None and peak_segment_load > 75:
            warn("BUS_LOAD_HIGH", f"Erwartete zusätzliche Buslast {peak_segment_load:.1f} % auf einem Abschnitt ist hoch.")

        if source_node_id and destination_node_ids:
            duplicates = self._find_duplicates(
                source_node_id, payload, destinations, exclude_route_id
            )
            if duplicates:
                error("DUPLICATE_ROUTE", f"Eine identische Route existiert bereits ({duplicates[0]['route_code']}).")

        evidence.extend(
            [
                {"type": "TOPOLOGY", "source_node": source_node_id, "destinations": destination_node_ids},
                {"type": "PROTOCOL", "protocol": protocol, "compatible": not any(item["code"] == "PROTOCOL_INCOMPATIBLE" for item in errors)},
                {"type": "TIMING", "estimated_latency_ms": estimated_latency_ms, "max_latency_ms": max_latency},
                {
                    "type": "LOAD",
                    "payload_bytes": payload_bytes,
                    "route_load_percent": round(expected_load, 3) if expected_load is not None else None,
                    "physical_segment_count": segment_count,
                    "peak_segment_load_percent": round(peak_segment_load, 3) if peak_segment_load is not None else None,
                    "network_load_percent": {network: round(load, 3) for network, load in sorted(segment_loads.items())},
                },
                {
                    "type": "PHYSICAL_NETWORK",
                    "mapped": physical_path_mapped,
                    "unmapped_destinations": unmapped_destinations,
                },
            ]
        )
        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "validation_timestamp": datetime.now(UTC).isoformat(),
            "metrics": {
                "payload_bytes": payload_bytes,
                "estimated_latency_ms": estimated_latency_ms,
                "route_load_percent": round(expected_load, 3) if expected_load is not None else None,
                "physical_segment_count": segment_count,
                "hop_count": hop_count,
                "gateway_count": gateway_count,
                "physical_path_mapped": physical_path_mapped,
            },
            "evidence": evidence,
        }

    def validate_table(self, routes: list[dict[str, Any]]) -> dict[str, Any]:
        results = [self.validate(route, exclude_route_id=str(route.get("id")) if route.get("id") else None) for route in routes]
        table_errors = [] if results else [
            {
                "code": "ROUTING_TABLE_EMPTY",
                "message": "Die Routing-Tabelle enthaelt noch keine Route.",
            }
        ]
        return {
            "valid": bool(results) and all(result["valid"] for result in results),
            "route_count": len(routes),
            "valid_count": sum(1 for result in results if result["valid"]),
            "error_count": len(table_errors) + sum(len(result["errors"]) for result in results),
            "warning_count": sum(len(result["warnings"]) for result in results),
            "table_errors": table_errors,
            "results": results,
        }
