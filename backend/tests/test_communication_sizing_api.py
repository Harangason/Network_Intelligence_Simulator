"""SQL roundtrip, stale plan rejection and all-or-nothing model adoption."""
import json
import os
import pytest
from backend.tests.test_engineering_api import _client
from backend.tests.test_bus_transfer import same_cluster

pytestmark = pytest.mark.skipif(not os.environ.get("ENGINEERING_TEST_DATABASE_URL"), reason="Requires isolated test database")


def test_dimensioning_persists_canonical_periods_and_rolls_back_failed_adoption(monkeypatch):
    from backend.engineering.project_context import activate_project, reset_project
    from backend.engineering.repository import create_object, get_object
    from backend.engineering.routing.repository import create_route, get_route, save_validation, approve_routes
    from backend.engineering.routing.validation import RoutingValidator
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.capacity import sizing_service

    client = _client()
    project = client.environ_base["HTTP_X_PROJECT_ID"]
    token = activate_project(project)
    try:
        state, objects, routes = same_cluster()
        ids = {}
        def remap(value):
            if isinstance(value, dict): return {ids.get(k, k): v if k in {"name", "node_name"} else remap(v) for k, v in value.items()}
            if isinstance(value, list): return [remap(v) for v in value]
            return ids.get(value, value) if isinstance(value, str) else value
        for kind in ("HardwareNode", "HardwareNetworkInterface", "Interface", "Message", "Signal"):
            for original in objects[kind]:
                data = remap({k: v for k, v in original.items() if k != "id"})
                if kind == "HardwareNode":
                    data["device_type"] = {"ecu": "ECU", "gateway": "Gateway", "sensor": "SensorController", "actuator": "ActuatorController"}[data["device_type"]]
                    data["identity"] = {}
                if kind == "Message":
                    data.update(source="ai_generated", cycle_ms=5, dlc=2)
                if kind == "Signal":
                    data.update(communication={"cycle_time_ms": 5}, data_type="unsigned")
                ids[original["id"]] = str(create_object(kind, data)["id"])
        signal = get_object("Signal", ids["statusSignal"])
        for route in routes:
            if route['id'] == 'AB':
                route['route'] = {'hops': [{'node_id': n, 'name': n} for n in ('A', 'Gateway', 'B')],
                                  'gateways': [{'node_id': 'Gateway', 'name': 'Gateway'}]}
            data = remap({k: v for k, v in route.items() if k not in {"id", "approval_state", "status", "validation"}})
            data["timing"] = {"cycle_time_ms": 5, "max_latency_ms": 20, "freshness_ms": 100}
            ids[route["id"]] = str(create_route(data)["id"])
        workflow = WorkflowStatusService(project)
        workflow.get()
        workflow.save_parameters({**state["parameters"], "industry": "automotive"})
        workflow.save_topology(remap(state["topology"]))
        validator = RoutingValidator(project)
        for route in routes:
            current = get_route(ids[route["id"]])
            validation = validator.validate(current, exclude_route_id=str(current["id"]))
            save_validation(str(current["id"]), validation)
            if validation["valid"]:
                approve_routes([str(current["id"])])
        response = client.post("/api/engineering/capacity/dimension", json={})
        assert response.status_code == 200, response.get_json()
        plan = response.get_json()
        assert plan["changes"], plan
        old = get_object("Message", ids["status"])
        payload = {"source_token": plan["source_token"], "policy": plan["policy"], "approve_valid": True}
        assert client.post("/api/engineering/capacity/dimension/apply", json={**payload, "source_token": "stale"}).status_code == 409
        original_save = WorkflowStatusService.save_parameters
        def fail(*args, **kwargs): raise RuntimeError("injected after canonical writes")
        monkeypatch.setattr(WorkflowStatusService, "save_parameters", fail)
        failed = client.post("/api/engineering/capacity/dimension/apply", json=payload)
        assert failed.status_code >= 400
        assert get_object("Message", ids["status"])["version"] == old["version"]
        assert get_object("Signal", str(signal["id"]))["communication"]["cycle_time_ms"] == 5
        monkeypatch.setattr(WorkflowStatusService, "save_parameters", original_save)
        applied = client.post("/api/engineering/capacity/dimension/apply", json=payload)
        assert applied.status_code == 200, applied.get_json()
        current = get_object("Message", ids["status"])
        assert current["cycle_ms"] >= 20
        assert current["configuration"]["communication_contract"]["transmission"]["period_ms"] == current["cycle_ms"]
        assert get_object("Signal", str(signal["id"]))["communication"]["cycle_time_ms"] == current["cycle_ms"]
        assert workflow.get()["parameters"]["communication_schedule"]["networks"]
        assert workflow.get()["context"]["communication_sizing_history"]
        assert client.post("/api/engineering/capacity/dimension/apply", json=payload).status_code == 409
    finally:
        reset_project(token)
