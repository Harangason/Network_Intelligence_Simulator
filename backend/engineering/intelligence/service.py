"""Orchestration for workflow step 9: calculate first, interpret second."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from ..db import get_connection
from ..knowledge import CanonicalKnowledgeService
from ..relations import list_relations
from ..repository import list_objects
from ..routing.repository import list_routes
from ..routing.validation import detect_routing_loop
from ..workflow.service import WorkflowConflictError, WorkflowStatusService
from .repository import (
    create_optimization_proposal,
    list_optimization_proposals,
    update_optimization_proposal,
)
from .services import (
    AnomalyDetectionService,
    DataQualityService,
    GraphAnalyticsService,
    MaturityAssessmentService,
    RecommendationEngine,
    RootCauseAnalysisService,
    SystemHealthService,
    TrendAnalysisService,
    _issue,
    _number,
    correlation,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class IntelligenceService:
    CALCULATION_VERSION = "1.0"

    def __init__(self, project_id: str = "default") -> None:
        self.project_id = str(project_id or "default")
        self.workflow = WorkflowStatusService(self.project_id)

    def _collect(self) -> dict[str, Any]:
        objects = {
            object_type: list_objects(object_type, limit=5000)
            for object_type in ("HardwareNode", "Function", "Interface", "Message", "Signal")
        }
        state = self.workflow.get()
        return {
            "state": state,
            "objects": objects,
            "routes": list_routes(limit=5000),
            "relations": list_relations(limit=10000),
            "capacity": self.workflow.latest_analysis("capacity_timing", include_outdated=True) or {},
            "preflight": self.workflow.latest_analysis("preflight", include_outdated=True) or {},
            "simulations": state.get("simulation_snapshots") or [],
            "history": self._history(),
        }

    def _history(self) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, analysis_type, results, findings, status, is_outdated, created_at
                FROM engineering_analysis_snapshots
                WHERE project_id = %s
                ORDER BY created_at DESC LIMIT 60
                """,
                (self.project_id,),
            ).fetchall()
            simulations = connection.execute(
                """
                SELECT id, status, result, is_outdated, created_at
                FROM engineering_simulation_snapshots
                WHERE project_id = %s
                ORDER BY created_at DESC LIMIT 40
                """,
                (self.project_id,),
            ).fetchall()
            project_benchmarks = connection.execute(
                """
                SELECT DISTINCT ON (project_id)
                       project_id, id, status, results, is_outdated, created_at
                FROM engineering_analysis_snapshots
                WHERE analysis_type = 'intelligence' AND project_id = %s
                ORDER BY project_id, created_at DESC
                LIMIT 100
                """,
                (self.project_id,),
            ).fetchall()
        points = []
        for row in rows:
            results = row.get("results") or {}
            overview = results.get("overview") or {}
            maturity = results.get("maturity") or {}
            points.append(
                {
                    "id": str(row.get("id")),
                    "kind": row.get("analysis_type"),
                    "status": row.get("status"),
                    "outdated": bool(row.get("is_outdated")),
                    "routes": overview.get("route_count") or (results.get("counts") or {}).get("routes"),
                    "errors": sum(item.get("severity") == "ERROR" for item in row.get("findings") or []),
                    "peak_load": overview.get("max_peak_load_percent"),
                    "maturity": maturity.get("overall_score"),
                    "created_at": row.get("created_at").isoformat(),
                }
            )
        for row in simulations:
            result = row.get("result") or {}
            runtime = result.get("runtime_metrics") or {}
            networks = runtime.get("networks") or []
            points.append(
                {
                    "id": str(row.get("id")),
                    "kind": "simulation",
                    "status": row.get("status"),
                    "outdated": bool(row.get("is_outdated")),
                    "peak_load": max((_number(item.get("peak_load_percent")) for item in networks), default=None),
                    "errors": (runtime.get("summary") or {}).get("error_count"),
                    "created_at": row.get("created_at").isoformat(),
                }
            )
        for row in project_benchmarks:
            results = row.get("results") or {}
            health = results.get("system_health") or {}
            maturity = results.get("maturity") or {}
            counts = health.get("counts") or {}
            points.append(
                {
                    "id": str(row.get("id")),
                    "project_id": row.get("project_id"),
                    "kind": "project_benchmark",
                    "status": row.get("status"),
                    "outdated": bool(row.get("is_outdated")),
                    "routes": counts.get("routes"),
                    "errors": counts.get("routing_errors"),
                    "maturity": maturity.get("overall_score"),
                    "created_at": row.get("created_at").isoformat(),
                }
            )
        return points

    @staticmethod
    def _routing_analysis(routes: list[dict[str, Any]]) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        keys: Counter[tuple[str, tuple[str, ...], str]] = Counter()
        statuses: Counter[str] = Counter()
        for route in routes:
            route_id = str(route.get("id"))
            source = route.get("source") or {}
            destinations = route.get("destinations") or []
            payload = route.get("payload") or {}
            path = route.get("route") or {}
            statuses[str(route.get("status") or "UNKNOWN")] += 1
            destination_ids = tuple(sorted(str(item.get("node_id")) for item in destinations if item.get("node_id")))
            message_key = ",".join(sorted(str(item) for item in payload.get("message_ids", []) if item)) or str(payload.get("message_id") or payload.get("name") or "")
            key = (str(source.get("node_id") or ""), destination_ids, message_key)
            keys[key] += 1
            if not source.get("node_id"):
                issues.append(_issue("ERROR", "Routing", "MISSING_PRODUCER", "Route besitzt keinen Producer.", object_type="RoutingEntry", object_id=route_id, cause="source.node_id ist leer.", recommendation="Producer im Routing Manager setzen."))
            if not destinations or not destination_ids:
                issues.append(_issue("ERROR", "Routing", "MISSING_CONSUMER", "Route besitzt keinen Consumer.", object_type="RoutingEntry", object_id=route_id, cause="destinations ist leer.", recommendation="Mindestens einen Consumer zuordnen."))
            if not source.get("interface_id"):
                issues.append(_issue("WARNING", "Routing", "SOURCE_INTERFACE_MISSING", "Source Interface ist nicht zugeordnet.", object_type="RoutingEntry", object_id=route_id, cause="Logische Route ist nicht vollstaendig auf Interfaces abgebildet.", recommendation="Source Interface im Routing Manager auswaehlen."))
            if any(not item.get("interface_id") for item in destinations):
                issues.append(_issue("WARNING", "Routing", "DESTINATION_INTERFACE_MISSING", "Mindestens ein Destination Interface fehlt.", object_type="RoutingEntry", object_id=route_id, cause="Consumer ist nicht vollstaendig technisch gemappt.", recommendation="Destination Interface ergaenzen."))
            if not payload.get("message_id") and not payload.get("message_ids") and not payload.get("signal_ids"):
                issues.append(_issue("WARNING", "Routing", "PAYLOAD_UNSPECIFIED", "Route besitzt keine Message oder Signale.", object_type="RoutingEntry", object_id=route_id, cause="Der transportierte Informationsumfang ist nicht definiert.", recommendation="Message und Signale zuordnen."))
            loop_nodes = detect_routing_loop(path.get("hops") or [])
            if loop_nodes:
                issues.append(_issue("ERROR", "Routing", "ROUTING_LOOP", "Routingpfad enthaelt eine Schleife.", object_type="RoutingEntry", object_id=route_id, cause="Knoten werden im Pfad mehrfach durchlaufen.", affected=loop_nodes, recommendation="Pfad ohne Schleife konfigurieren."))
            if len(path.get("hops") or []) > 6:
                issues.append(_issue("WARNING", "Routing", "LONG_ROUTING_PATH", "Routingpfad besitzt mehr als sechs Hops.", object_type="RoutingEntry", object_id=route_id, cause="Der technische Pfad ist ungewoehnlich lang.", recommendation="Direkteren Pfad oder Segmentierung pruefen."))
            if len(path.get("gateways") or []) > 2:
                issues.append(_issue("WARNING", "Routing", "UNNECESSARY_GATEWAY_HOPS", "Route durchlaeuft mehr als zwei Gateways.", object_type="RoutingEntry", object_id=route_id, cause="Mehrere Gateway-Uebergaenge erhoehen Latenz und Ausfallrisiko.", recommendation="Gateway-Hops reduzieren."))
            if route.get("status") == "OUTDATED":
                issues.append(_issue("WARNING", "Routing", "OUTDATED_ROUTE", "Routing-Revision ist veraltet.", object_type="RoutingEntry", object_id=route_id, cause=str(route.get("outdated_reason") or "Physischer Pfad wurde geaendert."), recommendation="Neuen Routing-Vorschlag validieren und bestaetigen."))
        duplicates = [key for key, count in keys.items() if count > 1 and any(key)]
        for source, destinations, payload in duplicates:
            issues.append(_issue("WARNING", "Routing", "DUPLICATE_ROUTE", "Mehrere Routen beschreiben dieselbe Kommunikationsbeziehung.", object_type="RoutingEntry", object_id=source or "unknown", cause="Producer, Consumer und Payload stimmen ueberein.", affected=destinations, recommendation="Redundanz fachlich bestaetigen oder Routen konsolidieren."))
        return {
            "route_count": len(routes),
            "status_counts": dict(statuses),
            "missing_routes": sum(issue["code"] in {"MISSING_PRODUCER", "MISSING_CONSUMER"} for issue in issues),
            "duplicate_routes": len(duplicates),
            "routing_loops": sum(issue["code"] == "ROUTING_LOOP" for issue in issues),
            "unmapped_logical_routes": sum(issue["code"] in {"SOURCE_INTERFACE_MISSING", "DESTINATION_INTERFACE_MISSING"} for issue in issues),
            "issues": issues,
        }

    @staticmethod
    def _capacity_analytics(snapshot: dict[str, Any]) -> dict[str, Any]:
        results = snapshot.get("results") or {}
        rows = []
        for network in results.get("networks") or []:
            reserve = _number(network.get("capacity_reserve_percent"))
            rows.append({
                "category": "Capacity",
                "object_id": str(network.get("network_id")),
                "metric": "Peak Load",
                "current_value": _number(network.get("peak_load_percent")),
                "requirement": 75.0,
                "deviation": round(_number(network.get("peak_load_percent")) - 75.0, 4),
                "severity": "ERROR" if network.get("status") == "OVERLOAD" else "WARNING" if network.get("status") in {"WARNING", "CRITICAL"} else "INFO",
                "capacity_reserve": reserve,
                "affected_objects": [item.get("route_id") for item in network.get("top_contributors") or []],
            })
        for route in results.get("routes") or []:
            requirement = route.get("max_latency_ms")
            if requirement:
                rows.append({
                    "category": "Timing", "object_id": str(route.get("route_id")), "metric": "End-to-End Latency",
                    "current_value": _number(route.get("end_to_end_latency_ms")), "requirement": _number(requirement),
                    "deviation": round(_number(route.get("end_to_end_latency_ms")) - _number(requirement), 6),
                    "severity": "ERROR" if route.get("latency_status") == "FAIL" else "INFO",
                    "affected_objects": [route.get("route_id")],
                })
        return {
            "overview": results.get("overview") or {},
            "timing": results.get("timing") or {},
            "reliability": results.get("reliability") or {},
            "synchronization": results.get("synchronization") or {},
            "networks": results.get("networks") or [],
            "gateways": results.get("gateways") or [],
            "requirements": rows,
            "source_snapshot_id": snapshot.get("id"),
            "source_outdated": bool(snapshot.get("is_outdated")),
        }

    @staticmethod
    def _convert_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted = []
        for finding in findings:
            converted.append(
                _issue(
                    str(finding.get("severity") or "WARNING"),
                    str(finding.get("category") or "Capacity & Timing").replace("_", " ").title(),
                    str(finding.get("code") or "ANALYSIS_FINDING"),
                    str(finding.get("message") or "Technischer Befund"),
                    object_type=str(finding.get("object_type") or "System"),
                    object_id=str(finding.get("object_id") or "project"),
                    cause=str(finding.get("cause") or "Deterministische Analyse hat eine Abweichung erkannt."),
                    recommendation=str(finding.get("recommendation") or "Befund im fachlichen Workflow pruefen."),
                    evidence=finding.get("evidence") or [],
                )
            )
        return converted

    @staticmethod
    def _correlations(capacity: dict[str, Any]) -> list[dict[str, Any]]:
        routes = (capacity.get("results") or {}).get("routes") or []
        loads = [_number(item.get("peak_load_percent")) for item in routes]
        latency = [_number(item.get("end_to_end_latency_ms")) for item in routes]
        jitter = [_number(item.get("estimated_jitter_ms")) for item in routes]
        gateway_delay = [_number(item.get("gateway_latency_ms")) for item in routes]
        cycles = [_number(item.get("cycle_ms")) for item in routes]
        return [
            correlation("Peak Load <-> End-to-End Latency", loads, latency),
            correlation("Peak Load <-> Jitter", loads, jitter),
            correlation("Gateway Delay <-> End-to-End Latency", gateway_delay, latency),
            correlation("Cycle Time <-> Network Load", cycles, loads),
        ]

    @staticmethod
    def _rag_insights(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not issues:
            return []
        query = " ".join(str(item.get("problem") or "") for item in issues[:3])[:800]
        selected = [str(item.get("object_id")) for item in issues[:3] if item.get("object_id") not in {None, "project"}]
        try:
            result = CanonicalKnowledgeService().search(query, selected_object_ids=selected, limit=8)
        except Exception:
            return []
        return [
            {
                "object_id": item.get("object_id"),
                "object_type": item.get("object_type"),
                "text": item.get("text"),
                "source_id": item.get("source_id"),
                "score": item.get("score"),
                "evidence": item.get("evidence") or [],
            }
            for item in result.get("items") or []
        ]

    def assess(self, *, persist: bool = True) -> dict[str, Any]:
        results_analysis = self.workflow.latest_analysis("results_analysis")
        if not results_analysis or results_analysis.get("status") not in {"COMPLETE", "APPROVED", "WARNING"}:
            raise WorkflowConflictError(
                "Eine aktuelle Results-/Analysis-Auswertung ist vor der Intelligence-Bewertung erforderlich."
            )
        data = self._collect()
        objects = data["objects"]
        data_quality = DataQualityService().analyze(objects)
        graph = GraphAnalyticsService().analyze(
            objects["HardwareNode"], objects["Interface"], objects["Signal"],
            data["state"].get("topology") or {}, data["relations"], data["routes"],
        )
        routing = self._routing_analysis(data["routes"])
        capacity_timing = self._capacity_analytics(data["capacity"])
        health = SystemHealthService().calculate(
            objects, data["routes"], data["state"].get("topology") or {}, data["capacity"],
            data["preflight"], data["simulations"], data_quality,
        )
        maturity = MaturityAssessmentService().assess(
            health, objects, data["routes"], data["state"], data_quality, data["relations"]
        )
        anomalies = AnomalyDetectionService().analyze(data["routes"], data["capacity"])
        issues = [
            *routing["issues"],
            *graph["issues"],
            *data_quality["issues"],
            *self._convert_findings(data["capacity"].get("findings") or []),
            *self._convert_findings(data["preflight"].get("findings") or []),
        ]
        issues.sort(key=lambda item: {"ERROR": 0, "WARNING": 1, "INFO": 2}.get(item["severity"], 3))
        rag = self._rag_insights(issues)
        recommendations = RecommendationEngine().generate(issues, rag)
        results = {
            "system_health": health,
            "maturity": maturity,
            "critical_issues": issues,
            "data_quality": {key: value for key, value in data_quality.items() if key != "issues"},
            "routing_analytics": {key: value for key, value in routing.items() if key != "issues"},
            "network_analytics": {key: value for key, value in graph.items() if key != "issues"},
            "capacity_timing_analytics": capacity_timing,
            "anomalies": anomalies,
            "trends": TrendAnalysisService().analyze(data["history"]),
            "root_causes": RootCauseAnalysisService().analyze(issues, data["capacity"]),
            "correlations": self._correlations(data["capacity"]),
            "recommendations": recommendations,
            "rag_knowledge_insights": rag,
            "graph_insights": {
                "critical_nodes": graph["critical_nodes"],
                "single_points_of_failure": graph["single_points_of_failure"],
                "longest_routes": graph["longest_routes"],
            },
            "governance": {
                "rule": "Analyze / Generate Proposal -> Validate -> Human Review -> Approval",
                "engineering_objects_are_source_of_truth": True,
                "automatic_changes": False,
            },
        }
        status = "ERROR" if any(item["severity"] == "ERROR" for item in issues) else "WARNING" if issues else "COMPLETE"
        source_objects = [
            {"object_type": object_type, "object_id": str(item.get("id")), "version": item.get("version")}
            for object_type, items in objects.items() for item in items
        ]
        provenance = {
            "metric": "system_intelligence_assessment",
            "source_objects": source_objects,
            "source_versions": data["state"]["versions"],
            "calculation_service": "IntelligenceService",
            "calculation_version": self.CALCULATION_VERSION,
            "timestamp": _now(),
            "baseline": data["state"].get("project_id"),
            "simulation_run": next((item.get("id") for item in data["simulations"] if not item.get("is_outdated")), None),
            "deterministic_calculation": True,
            "ai_interpretation": False,
        }
        if not persist:
            return {"project_id": self.project_id, "status": status, "results": results, "findings": issues, "provenance": provenance}
        snapshot = self.workflow.create_analysis_snapshot(
            "intelligence",
            input_data={
                "source_versions": data["state"]["versions"],
                "capacity_snapshot_id": data["capacity"].get("id"),
                "preflight_snapshot_id": data["preflight"].get("id"),
                "simulation_snapshot_ids": [item.get("id") for item in data["simulations"][:20]],
            },
            results=results,
            findings=issues,
            provenance=provenance,
            status=status,
        )
        return {**snapshot, "snapshot_id": snapshot["id"]}

    def latest(self, *, include_outdated: bool = True) -> dict[str, Any] | None:
        return self.workflow.latest_analysis("intelligence", include_outdated=include_outdated)

    def create_proposal(self, data: dict[str, Any]) -> dict[str, Any]:
        latest = self.latest(include_outdated=False)
        return create_optimization_proposal(
            self.project_id,
            {
                **data,
                "source_snapshot_id": data.get("source_snapshot_id") or (latest or {}).get("id"),
                "provenance": {
                    "calculation_service": "RecommendationEngine",
                    "calculation_version": self.CALCULATION_VERSION,
                    "created_at": _now(),
                    **(data.get("provenance") or {}),
                },
            },
        )

    def proposals(self, *, status: str | None = None) -> list[dict[str, Any]]:
        return list_optimization_proposals(self.project_id, status=status)

    def review_proposal(self, proposal_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return update_optimization_proposal(self.project_id, proposal_id, data)
