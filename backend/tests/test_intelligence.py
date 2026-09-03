from backend.engineering.intelligence.reports import IntelligenceReportService
from backend.engineering.intelligence.services import (
    AnomalyDetectionService,
    DataQualityService,
    GraphAnalyticsService,
    MaturityAssessmentService,
    RecommendationEngine,
    correlation,
)
from backend.engineering.project_bundle import normalize_project_id
from backend.engineering.workflow.models import default_statuses, default_versions, transition_state
from backend.app import create_app
from backend.engineering.intelligence.service import IntelligenceService
from backend.engineering.intelligence.review_learning import enrich_with_review_history


def _objects():
    return {
        "HardwareNode": [
            {"id": "node-a", "name": "A", "device_type": "ECU", "approval_state": "approved", "provenance": {"source": "test"}},
            {"id": "node-b", "name": "B", "device_type": "Gateway", "approval_state": "approved", "provenance": {"source": "test"}},
            {"id": "node-c", "name": "C", "device_type": "ECU", "approval_state": "pending", "provenance": {}},
        ],
        "Function": [{"id": "function-a", "name": "Drive", "hardware_node_id": "node-a", "approval_state": "approved", "provenance": {"source": "test"}}],
        "Interface": [{"id": "interface-a", "name": "CAN", "function_id": "function-a", "interface_type": "CAN_FD", "approval_state": "approved", "provenance": {"source": "test"}}],
        "Message": [{"id": "message-a", "name": "Status", "interface_id": "interface-a", "direction": "tx", "cycle_ms": 10, "dlc": 8, "approval_state": "approved", "provenance": {"source": "test"}}],
        "Signal": [{"id": "signal-a", "name": "Speed", "message_id": "message-a", "data_type": "uint16", "unit": "km/h", "length_bits": 16, "approval_state": "approved", "provenance": {"source": "test"}}],
    }


def test_device_type_is_not_part_of_the_name_but_distinguishes_duplicates():
    objects = _objects()
    objects["HardwareNode"] = [
        {"id": "s", "name": "Airbag", "device_type": "SensorController"},
        {"id": "e", "name": "Airbag", "device_type": "ECU"},
    ]
    assert DataQualityService().analyze(objects)["duplicate_candidates"] == 0
    objects["HardwareNode"].append({"id": "s2", "name": "Airbag", "device_type": "SensorController"})
    assert DataQualityService().analyze(objects)["duplicate_candidates"] == 1


def test_review_experience_is_reused_without_auto_approval_or_hiding_errors():
    recommendations = [{"category": "Network Segmentation", "problem": "90%", "affected_objects": ["airbag"], "priority": 95, "status": "CANDIDATE"}]
    proposals = [
        {"proposal_id": "old", "category": "Network Segmentation", "problem": "85%", "affected_objects": ["airbag"], "status": "REJECTED", "review_reason": "Timing must stay unchanged"},
        {"proposal_id": "unrelated", "category": "Network Segmentation", "affected_objects": ["climate"], "status": "ACCEPTED"},
        {"proposal_id": "pending", "category": "Network Segmentation", "affected_objects": ["airbag"], "status": "PROPOSED"},
    ]
    result = enrich_with_review_history(recommendations, proposals)
    assert result == {"reviewed_proposals": 2, "matched_recommendations": 1}
    assert recommendations[0]["review_history"][0]["proposal_id"] == "old"
    assert len(recommendations[0]["review_history"]) == 1
    assert recommendations[0]["requires_fresh_review"] is True
    assert recommendations[0]["status"] == "CANDIDATE"
    assert recommendations[0]["priority"] == 95


def test_diagnosis_persists_capacity_errors_without_a_successful_simulation(monkeypatch):
    service = IntelligenceService("diagnostic-test")
    monkeypatch.setattr(service.workflow, "latest_analysis", lambda *args, **kwargs: None)
    collected = {
        "objects": _objects(), "state": {"versions": default_versions(), "parameters": {}, "topology": {}},
        "routes": [], "relations": [], "preflight": {}, "simulations": [], "history": [],
        "capacity": {"id": "overload", "status": "ERROR", "results": {}, "findings": [
            {"severity": "ERROR", "code": "CAPACITY_OVERLOAD", "object_id": "network-lin", "message": "LIN overload"},
        ]},
    }
    monkeypatch.setattr(service, "_collect", lambda: collected)
    monkeypatch.setattr(service, "_rag_insights", lambda issues: [])
    persisted = []

    def persist(kind, **data):
        persisted.append((kind, data))
        return {"id": "diagnosis", **data}

    monkeypatch.setattr(service.workflow, "create_analysis_snapshot", persist)
    result = service.assess()
    assert result["status"] == "ERROR"
    assert result["results"]["assessment_mode"] == "DIAGNOSTIC"
    assert result["results"]["missing_evidence"]
    assert result["results"]["recommendations"]
    assert any(issue["code"] == "CAPACITY_OVERLOAD" for issue in result["results"]["critical_issues"])
    assert [kind for kind, _ in persisted] == ["intelligence"]
    assert not result["provenance"]["ai_interpretation"]


def test_step_nine_is_invalidated_by_earlier_changes():
    state = {
        "versions": default_versions(),
        "statuses": {step: "COMPLETE" for step in default_statuses()},
        "stale_reasons": {},
    }

    changed = transition_state(state, "routing", "Routing changed")

    assert changed["statuses"]["data_science_intelligence"] == "OUTDATED"
    assert changed["stale_reasons"]["data_science_intelligence"] == "Routing changed"


def test_data_quality_is_deterministic_and_reports_missing_signal_metadata():
    objects = _objects()
    objects["Signal"][0]["unit"] = None
    objects["Signal"][0]["data_type"] = None

    result = DataQualityService().analyze(objects)

    assert result["objects_analyzed"] == 7
    assert result["missing_units"] == 1
    assert result["missing_data_types"] == 1
    assert result["score"] < 100
    assert {item["code"] for item in result["issues"]} >= {"MISSING_REQUIRED_DATA"}


def test_data_quality_accepts_unitless_status_signals():
    objects = _objects()
    objects["Signal"][0].update(
        {
            "id": "status-signal",
            "name": "ProcessStatus",
            "data_type": "unsigned",
            "unit": None,
            "length_bits": 8,
        }
    )

    result = DataQualityService().analyze(objects)

    assert result["missing_units"] == 0
    assert not any(
        item["code"] == "MISSING_REQUIRED_DATA" and item["object_id"] == "status-signal"
        for item in result["issues"]
    )


def test_data_quality_accepts_direct_hardware_owned_interfaces():
    objects = _objects()
    objects["Interface"][0].update({"function_id": None, "hardware_node_id": "node-a"})

    result = DataQualityService().analyze(objects)

    assert not any(
        item["code"] == "MISSING_REQUIRED_DATA" and item["object_id"] == "interface-a"
        for item in result["issues"]
    )


def test_graph_analytics_finds_articulation_point_and_isolated_node():
    objects = _objects()
    result = GraphAnalyticsService().analyze(
        objects["HardwareNode"],
        objects["Interface"],
        objects["Signal"],
        {"nodes": [{"id": "node-a"}, {"id": "node-b"}, {"id": "node-c"}], "edges": [{"source": "node-a", "target": "node-b"}]},
        [],
        [],
    )

    assert result["isolated_nodes"] == [{"object_id": "node-c", "name": "C"}]
    assert result["node_count"] == 3


def test_gateway_single_point_issue_requires_user_confirmation():
    objects = _objects()
    result = GraphAnalyticsService().analyze(
        objects["HardwareNode"],
        objects["Interface"],
        [],
        {
            "nodes": [{"id": "node-a"}, {"id": "node-b"}, {"id": "node-c"}],
            "edges": [{"source": "node-a", "target": "node-b"}, {"source": "node-b", "target": "node-c"}],
        },
        [],
        [],
    )

    issue = next(item for item in result["issues"] if item["code"] == "SINGLE_POINT_OF_FAILURE")
    assert issue["object_id"] == "node-b"
    assert issue["requires_user_confirmation"] is True
    assert issue["approval_state"] == "PENDING_CONFIRMATION"


def test_approved_gateway_single_point_issue_no_longer_blocks_assessment():
    issue = {
        "severity": "WARNING",
        "category": "Graph",
        "code": "SINGLE_POINT_OF_FAILURE",
        "object_type": "HardwareNode",
        "object_id": "node-b",
        "status": "OPEN",
        "recommendation": "Redundanten Pfad vorsehen.",
    }
    reviewed = IntelligenceService._apply_issue_reviews(
        [issue],
        {
            IntelligenceService.issue_key(issue): {
                "status": "APPROVED",
                "reviewed_by": "tester",
                "reviewed_at": "2026-09-02T10:00:00Z",
                "note": "Gateway ist fachlich als erwarteter Single Point bestaetigt.",
            }
        },
    )

    assert reviewed[0]["status"] == "APPROVED"
    assert reviewed[0]["severity"] == "INFO"
    assert reviewed[0]["original_severity"] == "WARNING"
    assert IntelligenceService._assessment_status(reviewed) == "COMPLETE"


def test_graph_analytics_normalizes_agent_topology_and_interface_edges():
    hardware = [
        {"id": "node-a", "name": "A"},
        {"id": "node-b", "name": "B"},
    ]
    interfaces = [
        {"id": "interface-a", "hardware_node_id": "node-a"},
        {"id": "interface-b", "hardware_node_id": "node-b"},
    ]
    topology = {
        "nodes": [
            {"id": "engineering-node-a", "engineeringId": "node-a"},
            {"id": "engineering-node-b", "engineeringId": "node-b"},
        ],
        "edges": [
            {"source": "engineering-node-a", "target": "engineering-node-b"},
        ],
    }
    relations = [
        {
            "relation_type": "CONNECTED_TO",
            "source_type": "Interface",
            "source_id": "interface-a",
            "target_type": "Interface",
            "target_id": "interface-b",
        }
    ]

    result = GraphAnalyticsService().analyze(
        hardware,
        interfaces,
        [],
        topology,
        relations,
        [],
    )

    assert result["node_count"] == 2
    assert result["edge_count"] == 1
    assert result["isolated_nodes"] == []
    assert not any(issue["code"] == "ISOLATED_NODE" for issue in result["issues"])


def test_graph_analytics_projects_hardware_interface_relations_to_hardware_nodes():
    hardware = [
        {"id": "node-a", "name": "A"},
        {"id": "node-b", "name": "B"},
    ]
    hardware_interfaces = [
        {"id": "port-a", "hardware_node_id": "node-a"},
        {"id": "port-b", "hardware_node_id": "node-b"},
    ]
    relations = [
        {
            "relation_type": "CONNECTED_TO",
            "source_type": "HardwareNetworkInterface",
            "source_id": "port-a",
            "target_type": "HardwareNetworkInterface",
            "target_id": "port-b",
        }
    ]

    result = GraphAnalyticsService().analyze(
        hardware, [], [], {}, relations, [], hardware_interfaces,
    )

    assert result["node_count"] == 2
    assert result["edge_count"] == 1
    assert result["isolated_nodes"] == []
    assert set(result["single_points_of_failure"]) <= {"node-a", "node-b"}


def test_anomaly_detection_marks_unusual_cycle_without_calling_it_an_error():
    routes = [
        {"id": "r1", "name": "Fast", "payload": {"payload_bytes": 8}, "timing": {"cycle_time_ms": 1}},
        {"id": "r2", "name": "Normal", "payload": {"payload_bytes": 8}, "timing": {"cycle_time_ms": 100}},
        {"id": "r3", "name": "Normal 2", "payload": {"payload_bytes": 8}, "timing": {"cycle_time_ms": 100}},
    ]

    anomalies = AnomalyDetectionService().analyze(routes, {})

    assert anomalies[0]["status"] == "ANOMALY"
    assert anomalies[0]["category"] == "Cycle Time"


def test_maturity_and_recommendation_priorities_are_explainable():
    objects = _objects()
    health = {
        "metrics": {
            "interface_completeness": 100,
            "signal_coverage": 100,
            "routing_coverage": 90,
            "network_reachability": 90,
            "timing_compliance": 80,
            "capacity_reserve": 70,
            "validation_pass_rate": 90,
            "simulation_pass_rate": 80,
        }
    }
    maturity = MaturityAssessmentService().assess(
        health,
        objects,
        [{"id": "route-a"}],
        {"parameters": {"bitrate": 1_000_000}},
        {"score": 90},
        [{"id": index} for index in range(7)],
    )
    recommendations = RecommendationEngine().generate(
        [{
            "severity": "ERROR", "category": "Routing", "code": "ROUTING_SAFETY_MISSING",
            "problem": "Safety route missing", "affected_objects": ["a", "b"],
            "object_id": "a", "recommendation": "Create route", "evidence": [{"source": "preflight"}],
        }],
        [],
    )

    assert maturity["level"] in {"L3", "L4", "L5"}
    assert maturity["criteria"]["L4"]
    assert maturity["configured_thresholds"]["l3_validation"] == 70.0
    assert recommendations[0]["priority_factors"]["requirement_violation"] > 0
    assert recommendations[0]["governance"].endswith("Approval")


def test_maturity_thresholds_can_be_configured_per_project():
    health = {
        "metrics": {
            "interface_completeness": 100,
            "signal_coverage": 100,
            "routing_coverage": 100,
            "network_reachability": 100,
            "timing_compliance": 100,
            "capacity_reserve": 100,
            "validation_pass_rate": 50,
            "simulation_pass_rate": 0,
        },
        "counts": {"routing_errors": 0},
    }

    maturity = MaturityAssessmentService().assess(
        health,
        _objects(),
        [{"id": "route-a"}],
        {"parameters": {"maturity_criteria": {"l3_validation": 45}}},
        {"score": 90},
        [{"id": index} for index in range(7)],
    )

    assert maturity["level"] == "L3"
    assert maturity["configured_thresholds"]["l3_validation"] == 45.0


def test_correlations_are_labeled_as_non_causal_and_reports_export_csv():
    result = correlation("Load <-> Latency", [10, 20, 30], [1, 2, 3])
    csv_content = IntelligenceReportService().csv_report(
        {"results": {"critical_issues": [{"severity": "ERROR", "problem": "No path"}]}},
    )

    assert result["coefficient"] == 1.0
    assert result["status"] == "CORRELATION_NOT_CAUSATION"
    assert "severity" in csv_content and "No path" in csv_content


def test_project_ids_are_restricted_to_portable_file_safe_values():
    assert normalize_project_id("demo-01") == "demo-01"


def test_intelligence_assessment_endpoint_uses_active_project(monkeypatch):
    class FakeIntelligenceService:
        def __init__(self, project_id):
            self.project_id = project_id

        def assess(self):
            return {"project_id": self.project_id, "status": "WARNING", "results": {"critical_issues": []}}

    monkeypatch.setattr("backend.engineering.api.IntelligenceService", FakeIntelligenceService)
    client = create_app(testing=True).test_client()

    response = client.post(
        "/api/engineering/intelligence/assess",
        json={},
        headers={"X-Project-ID": "project-intelligence"},
    )

    assert response.status_code == 200
    assert response.get_json()["project_id"] == "project-intelligence"


def test_intelligence_issue_approval_endpoint_uses_active_project(monkeypatch):
    class FakeIntelligenceService:
        def __init__(self, project_id):
            self.project_id = project_id

        def approve_issue(self, data):
            return {"project_id": self.project_id, "approved": data["object_id"]}

    monkeypatch.setattr("backend.engineering.api.IntelligenceService", FakeIntelligenceService)
    client = create_app(testing=True).test_client()

    response = client.post(
        "/api/engineering/intelligence/issues/approve",
        json={"code": "SINGLE_POINT_OF_FAILURE", "object_type": "HardwareNode", "object_id": "node-b"},
        headers={"X-Project-ID": "project-intelligence"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"project_id": "project-intelligence", "approved": "node-b"}


def test_project_import_endpoint_never_treats_bundle_as_engineering_mutation(monkeypatch):
    class FakeProjectBundleService:
        def import_bundle(self, bundle, *, target_project_id=None):
            return {"project_id": target_project_id or bundle["project_id"], "report": {"inserted": 0}}

    monkeypatch.setattr("backend.engineering.api.ProjectBundleService", FakeProjectBundleService)
    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/engineering/projects/import",
        json={
            "bundle": {
                "format": "network-intelligence-project",
                "bundle_version": 1,
                "project_id": "opened-project",
            }
        },
    )

    assert response.status_code == 200
    assert response.get_json()["project_id"] == "opened-project"
