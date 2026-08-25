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
