"""Deterministic calculators used by the Intelligence orchestrator."""

from __future__ import annotations

from collections import Counter, defaultdict
from math import sqrt
from statistics import mean, median, pstdev
from typing import Any, Iterable


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _issue(
    severity: str,
    category: str,
    code: str,
    problem: str,
    *,
    object_type: str = "System",
    object_id: str = "project",
    cause: str = "Technische Quelldaten sind unvollstaendig oder inkonsistent.",
    affected: Iterable[str] = (),
    recommendation: str = "Quelldaten pruefen und Analyse erneut ausfuehren.",
    evidence: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "severity": severity,
        "category": category,
        "code": code,
        "object_type": object_type,
        "object_id": str(object_id),
        "problem": problem,
        "detected_cause": cause,
        "affected_objects": [str(item) for item in affected if item],
        "recommendation": recommendation,
        "status": "OPEN",
        "evidence": list(evidence),
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_semantic_type(row: dict[str, Any]) -> str:
    semantic = row.get("semantic") if isinstance(row.get("semantic"), dict) else {}
    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    configuration = row.get("configuration") if isinstance(row.get("configuration"), dict) else {}
    explicit = _text(
        semantic.get("semantic_type")
        or semantic.get("semanticType")
        or data.get("semantic_type")
        or configuration.get("semantic_type")
    ).upper().replace("-", "_").replace(" ", "_")
    if explicit:
        return explicit
    data_type = _text(row.get("data_type")).lower()
    if data_type in {"bool", "boolean"}:
        return "BOOLEAN"
    if isinstance(data.get("enum_values") or configuration.get("enum_values"), dict):
        return "ENUM"
    name = _text(row.get("display_name") or row.get("name")).lower().replace("_", " ").replace("-", " ")
    tokens = name.split()
    if any(token in {"status", "state", "mode", "zustand"} for token in tokens) or name.endswith(
        ("status", "state", "mode", "zustand", "diagnose", "fehler", "error", "warning", "warnung")
    ):
        return "STATE"
    return "UNKNOWN"


def _signal_unit_required(row: dict[str, Any]) -> bool:
    semantic_type = _normalized_semantic_type(row)
    if semantic_type in {"STATE", "ENUM", "BOOLEAN", "FLAG", "BITFIELD", "RAW", "STRING", "BYTE_ARRAY"}:
        return False
    return True


class DataQualityService:
    CALCULATION_VERSION = "1.0"
    REQUIRED_FIELDS = {
        "HardwareNode": ("name", "device_type"),
        "Function": ("name", "hardware_node_id"),
        "Interface": ("name", "interface_type"),
        "Message": ("name", "interface_id", "direction", "cycle_ms", "dlc"),
        "Signal": ("name", "message_id", "data_type", "length_bits"),
    }

    def analyze(self, objects: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        total_fields = complete_fields = 0
        missing_units = missing_types = missing_provenance = unapproved = 0
        duplicate_candidates = 0
        conflicting_signals = 0
        broken_relations = 0
        names: dict[tuple[str, str, str], list[str]] = defaultdict(list)

        for object_type, rows in objects.items():
            required = self.REQUIRED_FIELDS[object_type]
            for row in rows:
                object_id = str(row.get("id"))
                missing = []
                for field in required:
                    total_fields += 1
                    value = row.get(field)
                    if value is None or value == "" or value == {} or value == []:
                        missing.append(field)
                    else:
                        complete_fields += 1
                if object_type == "Interface":
                    total_fields += 1
                    if row.get("function_id") or row.get("hardware_node_id"):
                        complete_fields += 1
                    else:
                        missing.append("function_id oder hardware_node_id")
                if object_type == "Signal" and _signal_unit_required(row):
                    total_fields += 1
                    if row.get("unit"):
                        complete_fields += 1
                    else:
                        missing.append("unit")
                if missing:
                    issues.append(
                        _issue(
                            "WARNING",
                            "Data Quality",
                            "MISSING_REQUIRED_DATA",
                            f"{row.get('name') or object_id}: {', '.join(missing)} fehlt.",
                            object_type=object_type,
                            object_id=object_id,
                            cause="Pflichtattribute sind nicht gepflegt.",
                            recommendation="Fehlende Attribute im Engineering-Modell ergaenzen.",
                        )
                    )
                if not row.get("provenance"):
                    missing_provenance += 1
                if str(row.get("approval_state") or "pending").lower() != "approved":
                    unapproved += 1
                if object_type == "Signal":
                    missing_units += int(_signal_unit_required(row) and not row.get("unit"))
                    missing_types += int(not row.get("data_type"))
                    if row.get("min_value") is not None and row.get("max_value") is not None:
                        if _number(row.get("min_value")) > _number(row.get("max_value")):
                            conflicting_signals += 1
                            issues.append(
                                _issue(
                                    "ERROR",
                                    "Data Quality",
                                    "INVALID_SIGNAL_RANGE",
                                    f"{row.get('name')}: Minimalwert liegt ueber dem Maximalwert.",
                                    object_type=object_type,
                                    object_id=object_id,
                                    cause="Der konfigurierte Wertebereich ist widerspruechlich.",
                                    recommendation="Min-/Max-Werte des Signals korrigieren.",
                                )
                            )
                role = str(row.get("device_type") or "") if object_type == "HardwareNode" else ""
                names[(object_type, role, str(row.get("name") or "").strip().lower())].append(object_id)

        for (object_type, _role, name), ids in names.items():
            if name and len(ids) > 1:
                duplicate_candidates += len(ids) - 1
                issues.append(
                    _issue(
                        "WARNING",
                        "Data Quality",
                        "DUPLICATE_CANDIDATE",
                        f"{len(ids)} {object_type}-Objekte tragen den Namen '{name}'.",
                        object_type=object_type,
                        object_id=ids[0],
                        cause="Name und Objekttyp sind mehrfach vorhanden.",
                        affected=ids,
                        recommendation="Objekte fachlich vergleichen und bei Bedarf konsolidieren.",
                    )
                )

        total_objects = sum(len(rows) for rows in objects.values())
        completeness = _clamp(complete_fields / max(total_fields, 1) * 100)
        provenance = _clamp((total_objects - missing_provenance) / max(total_objects, 1) * 100)
        approval = _clamp((total_objects - unapproved) / max(total_objects, 1) * 100)
        score = _clamp(completeness * 0.55 + provenance * 0.25 + approval * 0.2)
        return {
            "score": score,
            "objects_analyzed": total_objects,
            "completeness_percent": completeness,
            "provenance_percent": provenance,
            "approval_percent": approval,
            "missing_provenance": missing_provenance,
            "duplicate_candidates": duplicate_candidates,
            "conflicting_signals": conflicting_signals,
            "missing_units": missing_units,
            "missing_data_types": missing_types,
            "broken_relations": broken_relations,
            "unapproved_data": unapproved,
            "issues": issues,
            "calculation_version": self.CALCULATION_VERSION,
        }


class GraphAnalyticsService:
    CALCULATION_VERSION = "1.0"

    @staticmethod
    def _edges(
        topology: dict[str, Any],
        relations: list[dict[str, Any]],
        interfaces: list[dict[str, Any]],
        hardware_interfaces: list[dict[str, Any]],
    ) -> list[tuple[str, str]]:
        edges: set[tuple[str, str]] = set()
        topology_nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
        topology_to_hardware = {
            str(node.get("id")): str(
                node.get("engineeringId")
                or node.get("engineering_id")
                or node.get("id")
            )
            for node in topology_nodes
            if isinstance(node, dict) and node.get("id")
        }
        interface_to_hardware = {
            str(interface.get("id")): str(interface.get("hardware_node_id"))
            for interface in [*interfaces, *hardware_interfaces]
            if interface.get("id") and interface.get("hardware_node_id")
        }
        for edge in topology.get("edges") or []:
            source = edge.get("source") or edge.get("sourceId") or edge.get("from")
            target = edge.get("target") or edge.get("targetId") or edge.get("to")
            if source and target:
                source_id = topology_to_hardware.get(str(source), str(source))
                target_id = topology_to_hardware.get(str(target), str(target))
                if source_id != target_id:
                    edges.add((source_id, target_id))
        for relation in relations:
            if relation.get("relation_type") == "CONNECTED_TO":
                source_id = str(relation.get("source_id") or "")
                target_id = str(relation.get("target_id") or "")
                if str(relation.get("source_type") or "").lower() in {
                    "interface", "hardwarenetworkinterface", "hardware_network_interface",
                }:
                    source_id = interface_to_hardware.get(source_id, source_id)
                if str(relation.get("target_type") or "").lower() in {
                    "interface", "hardwarenetworkinterface", "hardware_network_interface",
                }:
                    target_id = interface_to_hardware.get(target_id, target_id)
                if source_id and target_id and source_id != target_id:
                    edges.add((source_id, target_id))
        return sorted(edges)

    @staticmethod
    def _articulation_points(nodes: set[str], adjacency: dict[str, set[str]]) -> set[str]:
        visited: set[str] = set()
        discovery: dict[str, int] = {}
        low: dict[str, int] = {}
        parent: dict[str, str | None] = {}
        result: set[str] = set()
        clock = 0

        def visit(node: str) -> None:
            nonlocal clock
            visited.add(node)
            clock += 1
            discovery[node] = low[node] = clock
            children = 0
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    parent[neighbor] = node
                    children += 1
                    visit(neighbor)
                    low[node] = min(low[node], low[neighbor])
                    if parent.get(node) is None and children > 1:
                        result.add(node)
                    if parent.get(node) is not None and low[neighbor] >= discovery[node]:
                        result.add(node)
                elif neighbor != parent.get(node):
                    low[node] = min(low[node], discovery[neighbor])

        for node in nodes:
            if node not in visited:
                parent[node] = None
                visit(node)
        return result

    def analyze(
        self,
        hardware: list[dict[str, Any]],
        interfaces: list[dict[str, Any]],
        signals: list[dict[str, Any]],
        topology: dict[str, Any],
        relations: list[dict[str, Any]],
        routes: list[dict[str, Any]],
        hardware_interfaces: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        nodes = {str(item.get("id")) for item in hardware}
        node_names = {str(item.get("id")): str(item.get("name") or item.get("id")) for item in hardware}
        node_types = {str(item.get("id")): str(item.get("device_type") or "") for item in hardware}
        edges = self._edges(topology, relations, interfaces, hardware_interfaces or [])
        adjacency: dict[str, set[str]] = defaultdict(set)
        for source, target in edges:
            nodes.update((source, target))
            adjacency[source].add(target)
            adjacency[target].add(source)
        for node in nodes:
            adjacency[node]
        isolated = sorted(node for node in nodes if not adjacency[node])
        articulation = self._articulation_points(nodes, adjacency)
        high_degree = sorted(nodes, key=lambda node: len(adjacency[node]), reverse=True)
        critical = [
            {"object_id": node, "name": node_names.get(node, node), "degree": len(adjacency[node])}
            for node in high_degree
            if node in articulation or len(adjacency[node]) >= 4
        ]
        linked_interface_ids = {
            str(item)
            for route in routes
            for item in [
                (route.get("source") or {}).get("interface_id"),
                *[(destination or {}).get("interface_id") for destination in route.get("destinations") or []],
            ]
            if item
        }
        unused_interfaces = [
            {"object_id": str(item.get("id")), "name": item.get("name")}
            for item in interfaces
            if str(item.get("id")) not in linked_interface_ids
        ]
        orphan_signals = [
            {"object_id": str(item.get("id")), "name": item.get("name")}
            for item in signals
            if not item.get("message_id")
        ]
        route_lengths = [
            {
                "route_id": str(route.get("id")),
                "name": route.get("name"),
                "hop_count": len((route.get("route") or {}).get("hops") or []),
            }
            for route in routes
        ]
        route_lengths.sort(key=lambda item: item["hop_count"], reverse=True)
        issues = [
            _issue(
                "WARNING",
                "Network",
                "ISOLATED_NODE",
                f"{node_names.get(node, node)} ist physisch isoliert.",
                object_type="HardwareNode",
                object_id=node,
                cause="Der Knoten besitzt keine technische Verbindung.",
                recommendation="Netzwerkpfad ergaenzen oder Knoten als bewusst isoliert kennzeichnen.",
            )
            for node in isolated
        ]
        for node in articulation:
            issue = _issue(
                "WARNING",
                "Graph",
                "SINGLE_POINT_OF_FAILURE",
                f"{node_names.get(node, node)} ist ein Single Point of Failure.",
                object_type="HardwareNode",
                object_id=node,
                cause="Der Knoten ist ein Artikulationspunkt der physischen Topologie.",
                recommendation="Redundanten Pfad oder alternatives Gateway vorsehen.",
            )
            node_label = f"{node_names.get(node, node)} {node_types.get(node, '')}".lower()
            if "gateway" in node_label:
                issue.update(
                    {
                        "requires_user_confirmation": True,
                        "approval_state": "PENDING_CONFIRMATION",
                        "review_state": "UNREVIEWED",
                        "confirmation_label": "Gateway-Single-Point bestätigen",
                        "detected_cause": (
                            "Gateway ist Artikulationspunkt der physischen Topologie. "
                            "Das kann in E/E-Systemen fachlich erwartet sein und benoetigt eine bewusste Nutzerbestaetigung."
                        ),
                        "recommendation": (
                            "Wenn dieses Gateway bewusst allein im System steht, als erwartete Topologie bestaetigen; "
                            "andernfalls redundanten Pfad oder alternatives Gateway vorsehen."
                        ),
                    }
                )
            issues.append(issue)
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "isolated_nodes": [{"object_id": node, "name": node_names.get(node, node)} for node in isolated],
            "critical_nodes": critical,
            "single_points_of_failure": [node for node in articulation],
            "unused_interfaces": unused_interfaces,
            "orphan_signals": orphan_signals,
            "longest_routes": route_lengths[:10],
            "highly_connected_gateways": critical[:10],
            "redundancy_gaps": len(articulation),
            "issues": issues,
            "calculation_version": self.CALCULATION_VERSION,
        }


class AnomalyDetectionService:
    CALCULATION_VERSION = "1.0"

    def analyze(self, routes: list[dict[str, Any]], capacity: dict[str, Any]) -> list[dict[str, Any]]:
        payloads = [_number((route.get("payload") or {}).get("payload_bytes")) for route in routes]
        payloads = [value for value in payloads if value > 0]
        cycles = [_number((route.get("timing") or {}).get("cycle_time_ms")) for route in routes]
        cycles = [value for value in cycles if value > 0]
        payload_mid = median(payloads) if payloads else 0
        cycle_mid = median(cycles) if cycles else 0
        anomalies: list[dict[str, Any]] = []
        for route in routes:
            route_id = str(route.get("id"))
            payload = _number((route.get("payload") or {}).get("payload_bytes"))
            cycle = _number((route.get("timing") or {}).get("cycle_time_ms"))
            if payload_mid and payload >= payload_mid * 2 and payload > 8:
                anomalies.append({
                    "status": "ANOMALY", "category": "Payload", "object_type": "RoutingEntry",
                    "object_id": route_id, "name": route.get("name"), "current_value": payload,
                    "reference_value": payload_mid, "impact": "Ueberdurchschnittliche Frame-Groesse kann Lastspitzen erhoehen.",
                })
            if cycle_mid and cycle <= cycle_mid / 5:
                anomalies.append({
                    "status": "ANOMALY", "category": "Cycle Time", "object_type": "RoutingEntry",
                    "object_id": route_id, "name": route.get("name"), "current_value": cycle,
                    "reference_value": cycle_mid, "impact": "Hohe Frequenz erhoeht Netzlast und Queueing-Risiko.",
                })
        route_metrics = (capacity.get("results") or {}).get("routes") or []
        latencies = [_number(item.get("end_to_end_latency_ms")) for item in route_metrics]
        if len(latencies) >= 3:
            avg = mean(latencies)
            deviation = pstdev(latencies)
            for item in route_metrics:
                value = _number(item.get("end_to_end_latency_ms"))
                if deviation and value > avg + 2 * deviation:
                    anomalies.append({
                        "status": "ANOMALY", "category": "Latency Outlier", "object_type": "RoutingEntry",
                        "object_id": str(item.get("route_id")), "name": item.get("name"),
                        "current_value": value, "reference_value": avg,
                        "impact": "Latenz liegt mehr als zwei Standardabweichungen ueber dem Mittelwert.",
                    })
        return anomalies


class SystemHealthService:
    CALCULATION_VERSION = "1.0"

    def calculate(
        self,
        objects: dict[str, list[dict[str, Any]]],
        routes: list[dict[str, Any]],
        topology: dict[str, Any],
        capacity: dict[str, Any],
        preflight: dict[str, Any],
        simulations: list[dict[str, Any]],
        data_quality: dict[str, Any],
    ) -> dict[str, Any]:
        capacity_results = capacity.get("results") or {}
        capacity_findings = capacity.get("findings") or []
        preflight_results = preflight.get("results") or {}
        valid_routes = [
            route for route in routes
            if route.get("status") not in {"CONFLICT", "REJECTED", "OUTDATED", "SUPERSEDED"}
        ]
        route_signals = {
            str(signal_id)
            for route in routes
            for signal_id in (route.get("payload") or {}).get("signal_ids") or []
        }
        interfaces = objects["Interface"]
        route_metrics = capacity_results.get("routes") or []
        current_runs = [item for item in simulations if not item.get("is_outdated")]
        completed = [item for item in current_runs if item.get("status") == "COMPLETED"]
        categories = (preflight_results.get("category_statuses") or {}).values()
        category_values = list(categories)
        physical_nodes = topology.get("nodes") or []
        connected_ids = {
            str(value)
            for edge in topology.get("edges") or []
            for value in (edge.get("source"), edge.get("target"), edge.get("sourceId"), edge.get("targetId"))
            if value
        }
        networks = capacity_results.get("networks") or []
        metrics = {
            "routing_coverage": _clamp(len(valid_routes) / max(len(routes), 1) * 100),
            "signal_coverage": _clamp(len(route_signals) / max(len(objects["Signal"]), 1) * 100),
            "interface_completeness": _clamp(sum(bool(item.get("function_id") and item.get("interface_type")) for item in interfaces) / max(len(interfaces), 1) * 100),
            "network_reachability": _clamp(len(connected_ids) / max(len(physical_nodes), 1) * 100),
            "validation_pass_rate": _clamp(sum(value == "PASS" for value in category_values) / max(len(category_values), 1) * 100),
            "timing_compliance": _clamp(sum(item.get("requirement_status") == "PASS" for item in route_metrics) / max(len(route_metrics), 1) * 100),
            "capacity_reserve": _clamp(_number((capacity_results.get("overview") or {}).get("minimum_capacity_reserve_percent"))),
            "simulation_pass_rate": _clamp(len(completed) / max(len(current_runs), 1) * 100),
            "data_quality": data_quality["score"],
            "requirement_coverage": _clamp(sum(bool((item.get("timing") or {}).get("max_latency_ms")) for item in routes) / max(len(routes), 1) * 100),
        }
        return {
            "counts": {
                "nodes": len(objects["HardwareNode"]),
                "networks": len(networks),
                "routes": len(routes),
                "messages": len(objects["Message"]),
                "signals": len(objects["Signal"]),
                "routing_errors": sum(route.get("status") == "CONFLICT" for route in routes),
                "timing_violations": sum(str(item.get("code", "")).startswith("TIMING_") for item in capacity_findings),
                "capacity_warnings": sum(str(item.get("code", "")).startswith("CAPACITY_") for item in capacity_findings),
                "unmapped_signals": max(0, len(objects["Signal"]) - len(route_signals)),
                "simulation_failures": sum(item.get("status") in {"FAILED", "CANCELED"} for item in simulations),
            },
            "metrics": metrics,
            "score": _clamp(mean(metrics.values()) if metrics else 0),
            "calculation_version": self.CALCULATION_VERSION,
        }


class MaturityAssessmentService:
    CALCULATION_VERSION = "1.0"
    LEVEL_CRITERIA = {
        "L0": "Kein strukturiertes Engineering-Modell vorhanden.",
        "L1": "Engineering-Modell mindestens 40 Prozent vollstaendig.",
        "L2": "Modell, Interfaces, Routing und Topologie jeweils mindestens 60 Prozent.",
        "L3": "Validation mindestens 70 Prozent und kein blockierender Modellfehler.",
        "L4": "Aktuelle Simulationsevidenz mindestens 60 Prozent.",
        "L5": "Gesamtreife, Datenqualitaet und Knowledge Coverage mindestens 85/85/70 Prozent.",
    }

    def assess(
        self,
        health: dict[str, Any],
        objects: dict[str, list[dict[str, Any]]],
        routes: list[dict[str, Any]],
        state: dict[str, Any],
        data_quality: dict[str, Any],
        relations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        configured = (state.get("parameters") or {}).get("maturity_criteria") or {}
        thresholds = {
            "l1_engineering_model": _number(configured.get("l1_engineering_model"), 40.0),
            "l2_connected_dimensions": _number(configured.get("l2_connected_dimensions"), 60.0),
            "l3_validation": _number(configured.get("l3_validation"), 70.0),
            "l4_simulation_evidence": _number(configured.get("l4_simulation_evidence"), 60.0),
            "l5_overall": _number(configured.get("l5_overall"), 85.0),
            "l5_data_quality": _number(configured.get("l5_data_quality"), 85.0),
            "l5_knowledge_coverage": _number(configured.get("l5_knowledge_coverage"), 70.0),
        }
        metrics = health["metrics"]
        total_objects = sum(len(items) for items in objects.values())
        approved = sum(
            str(item.get("approval_state") or "").lower() == "approved"
            for items in objects.values() for item in items
        )
        populated_types = sum(bool(items) for items in objects.values())
        type_coverage = populated_types / max(len(objects), 1) * 100
        dimensions = {
            "Engineering Model": _clamp(type_coverage),
            "Interfaces & Signals": _clamp((metrics["interface_completeness"] + metrics["signal_coverage"]) / 2),
            "Routing": metrics["routing_coverage"],
            "Network Topology": metrics["network_reachability"],
            "Parameter Completeness": 100.0 if state.get("parameters") else 0.0,
            "Capacity & Timing": _clamp((metrics["timing_compliance"] + metrics["capacity_reserve"]) / 2),
            "Validation": metrics["validation_pass_rate"],
            "Simulation Evidence": metrics["simulation_pass_rate"],
            "Data Quality": data_quality["score"],
            "Knowledge Coverage": _clamp(len(relations) / max(total_objects, 1) * 100),
        }
        dimensions["Engineering Model"] = _clamp(
            dimensions["Engineering Model"] * 0.5 + approved / max(total_objects, 1) * 100 * 0.5
        )
        level = "L0"
        if dimensions["Engineering Model"] >= thresholds["l1_engineering_model"]:
            level = "L1"
        if min(dimensions[name] for name in ("Engineering Model", "Interfaces & Signals", "Routing", "Network Topology")) >= thresholds["l2_connected_dimensions"]:
            level = "L2"
        health_counts = health.get("counts") or {}
        if level == "L2" and dimensions["Validation"] >= thresholds["l3_validation"] and health_counts.get("routing_errors", 0) == 0:
            level = "L3"
        if level == "L3" and dimensions["Simulation Evidence"] >= thresholds["l4_simulation_evidence"]:
            level = "L4"
        overall = _clamp(mean(dimensions.values()))
        if level == "L4" and overall >= thresholds["l5_overall"] and dimensions["Data Quality"] >= thresholds["l5_data_quality"] and dimensions["Knowledge Coverage"] >= thresholds["l5_knowledge_coverage"]:
            level = "L5"
        names = {
            "L0": "Undefined", "L1": "Structured", "L2": "Connected",
            "L3": "Validated", "L4": "Simulated", "L5": "Evidence-backed / Mature",
        }
        order = ["L0", "L1", "L2", "L3", "L4", "L5"]
        target = order[min(order.index(level) + 1, len(order) - 1)]
        gaps = [
            {"dimension": name, "current": value, "target": 70 if target in {"L3", "L4"} else 85,
             "gap": round(max(0, (70 if target in {"L3", "L4"} else 85) - value), 2)}
            for name, value in dimensions.items()
            if value < (70 if target in {"L3", "L4"} else 85)
        ]
        gaps.sort(key=lambda item: item["gap"], reverse=True)
        return {
            "overall_score": overall,
            "level": level,
            "level_name": names[level],
            "target_level": target,
            "target_level_name": names[target],
            "dimensions": dimensions,
            "gaps": gaps,
            "criteria": self.LEVEL_CRITERIA,
            "configured_thresholds": thresholds,
            "calculation_version": self.CALCULATION_VERSION,
        }


class TrendAnalysisService:
    CALCULATION_VERSION = "1.0"

    def analyze(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        points = sorted(history, key=lambda item: str(item.get("created_at") or ""))
        return {
            "comparison_modes": ["CURRENT_VS_PREVIOUS", "BASELINE_VS_BASELINE", "SIMULATION_VS_SIMULATION", "CURRENT_VS_RELEASED"],
            "points": points[-20:],
            "direction": self._direction(points),
            "calculation_version": self.CALCULATION_VERSION,
        }

    @staticmethod
    def _direction(points: list[dict[str, Any]]) -> str:
        if len(points) < 2:
            return "INSUFFICIENT_HISTORY"
        first = _number(points[-2].get("maturity"))
        last = _number(points[-1].get("maturity"))
        return "IMPROVING" if last > first else "DECLINING" if last < first else "STABLE"


class RootCauseAnalysisService:
    CALCULATION_VERSION = "1.0"

    def analyze(self, issues: list[dict[str, Any]], capacity: dict[str, Any]) -> list[dict[str, Any]]:
        route_metrics = {
            str(item.get("route_id")): item for item in (capacity.get("results") or {}).get("routes") or []
        }
        output = []
        for issue in issues[:20]:
            route = route_metrics.get(str(issue.get("object_id")))
            chain = [f"{issue.get('object_type')}:{issue.get('object_id')}"]
            evidence = list(issue.get("evidence") or [])
            if route:
                chain.extend(str(item) for item in route.get("gateways") or [])
                bottleneck = route.get("bottleneck") or {}
                if bottleneck:
                    chain.append(str(bottleneck.get("component")))
                    evidence.append({"metric": "bottleneck_delay_ms", "value": bottleneck.get("delay_ms")})
            output.append({
                "issue_code": issue.get("code"),
                "object_id": issue.get("object_id"),
                "most_likely_cause": issue.get("detected_cause"),
                "dependency_chain": chain,
                "evidence": evidence,
                "confidence": 0.85 if route else 0.65,
            })
        return output


class RecommendationEngine:
    CALCULATION_VERSION = "1.0"
    SEVERITY_SCORE = {"ERROR": 45, "WARNING": 28, "INFO": 10}

    def generate(self, issues: list[dict[str, Any]], rag: list[dict[str, Any]]) -> list[dict[str, Any]]:
        recommendations = []
        for issue in issues:
            affected = issue.get("affected_objects") or [issue.get("object_id")]
            requirement = int("TIMING" in str(issue.get("code")) or "ROUT" in str(issue.get("code")))
            safety = int("SAFETY" in str(issue).upper())
            score = min(100, self.SEVERITY_SCORE.get(str(issue.get("severity")), 10) + min(len(affected) * 3, 18) + requirement * 12 + safety * 15)
            recommendations.append({
                "candidate_id": f"REC-{str(issue.get('code'))[:20]}-{str(issue.get('object_id'))[:8]}",
                "category": issue.get("category"),
                "problem": issue.get("problem"),
                "affected_objects": affected,
                "recommendation": issue.get("recommendation"),
                "expected_impact": {
                    "risk_reduction": "HIGH" if score >= 70 else "MEDIUM",
                    "affected_objects": len(affected),
                    "requires_revalidation": True,
                },
                "evidence": issue.get("evidence") or [],
                "graph_context": [{"object_id": issue.get("object_id"), "category": issue.get("category")}],
                "rag_context": rag[:3],
                "confidence": 0.9 if issue.get("evidence") else 0.7,
                "priority": score,
                "priority_factors": {
                    "severity": self.SEVERITY_SCORE.get(str(issue.get("severity")), 10),
                    "system_impact": min(len(affected) * 3, 18),
                    "requirement_violation": requirement * 12,
                    "safety_criticality": safety * 15,
                },
                "implementation_effort": "MEDIUM",
                "status": "CANDIDATE",
                "governance": "Validate -> Human Review -> Approval",
            })
        recommendations.sort(key=lambda item: item["priority"], reverse=True)
        return recommendations[:25]


def correlation(name: str, left: list[float], right: list[float]) -> dict[str, Any]:
    pairs = [(x, y) for x, y in zip(left, right) if x is not None and y is not None]
    if len(pairs) < 3:
        return {"metric_pair": name, "coefficient": None, "sample_size": len(pairs), "status": "INSUFFICIENT_DATA"}
    xs, ys = zip(*pairs)
    x_avg, y_avg = mean(xs), mean(ys)
    numerator = sum((x - x_avg) * (y - y_avg) for x, y in pairs)
    denominator = sqrt(sum((x - x_avg) ** 2 for x in xs) * sum((y - y_avg) ** 2 for y in ys))
    coefficient = numerator / denominator if denominator else 0.0
    return {
        "metric_pair": name,
        "coefficient": round(coefficient, 4),
        "sample_size": len(pairs),
        "status": "CORRELATION_NOT_CAUSATION",
    }
