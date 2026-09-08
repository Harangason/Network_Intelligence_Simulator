"""Real database regressions for concurrent editors and request atomicity."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import os
import uuid

import pytest

from backend.app import create_app
from backend.engineering import api as api_module
from backend.engineering.db import close_pool, get_connection
from backend.engineering.project_context import (
    activate_project, reset_project, current_project_id,
    compact_context_project_id, normalize_context_project_id,
)
from backend.engineering.workflow.service import edit_token, check_edit_token, WorkflowConflictError


def test_project_links_round_trip_without_changing_identity():
    for project in ("default", "network-project-test", "network-project-20260906", "network-project-20260906120000123-abcd", "custom"):
        assert normalize_context_project_id(compact_context_project_id(project)) == project


def test_edit_tokens_are_order_independent_but_detect_content_changes():
    assert edit_token({"a": 1, "b": 2}) == edit_token({"b": 2, "a": 1})
    with pytest.raises(WorkflowConflictError):
        check_edit_token(edit_token({"a": 1}), {"a": 2})


def test_http_route_method_registrations_are_unique():
    seen = set()
    for rule in create_app(testing=True).url_map.iter_rules():
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            key = (rule.rule, method)
            assert key not in seen, key
            seen.add(key)


def test_empty_workflow_payloads_are_validation_errors(workspace):
    _project, call = workspace

    parameters = call("PATCH", "/workflow/parameters", {})
    topology = call("PUT", "/workflow/topology", {})

    assert parameters.status_code == 400
    assert parameters.get_json()["error"] == "parameters muss ein nicht-leeres Objekt sein."
    assert topology.status_code == 400
    assert topology.get_json()["error"] == "topology.nodes muss eine Liste sein."


@pytest.fixture
def workspace(monkeypatch):
    url = os.environ.get("ENGINEERING_TEST_DATABASE_URL")
    if not url:
        pytest.skip("ENGINEERING_TEST_DATABASE_URL is required for real concurrent transactions")
    monkeypatch.setenv("DATABASE_URL", url)
    close_pool()
    project = f"audit-{uuid.uuid4()}"
    app = create_app(testing=True)
    headers = {"X-Project-ID": project}
    def call(method, path, payload=None):
        with app.test_client() as client:
            return client.open(f"/api/engineering{path}", method=method, headers=headers, json=payload)
    call("GET", "/workflow")
    yield project, call
    # Only this test's generated project is removed.
    with get_connection() as connection:
        connection.execute("DELETE FROM engineering_workflow_projects WHERE project_id = %s", (project,))
    close_pool()


def test_parallel_stale_object_updates_have_one_winner(workspace):
    project, call = workspace
    created = call("POST", "/hardware-nodes", {"name": "Controller", "device_type": "ECU"})
    assert created.status_code == 201, created.get_json()
    node = created.get_json()
    gate = Barrier(6)
    def update(index):
        gate.wait(timeout=10)
        return call("PATCH", f"/hardware-nodes/{node['id']}", {
            "description": f"browser-{index}", "expected_version": 1,
        })
    with ThreadPoolExecutor(max_workers=6) as executor:
        responses = list(executor.map(update, range(6)))
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409, 409]
    saved = call("GET", f"/hardware-nodes/{node['id']}").get_json()
    assert saved["version"] == 2
    assert len(call("GET", f"/hardware-nodes/{node['id']}/versions").get_json()["items"]) == 2
    assert call("GET", "/workflow").get_json()["versions"]["engineering_model"] == 2
    with create_app(testing=True).test_client() as other:
        assert other.get(f"/api/engineering/hardware-nodes/{node['id']}", headers={"X-Project-ID": "another-project"}).status_code == 404


def test_parameter_conflict_does_not_overwrite_and_other_objects_can_be_edited(workspace):
    _, call = workspace
    initial = call("GET", "/workflow").get_json()
    token = initial["edit_tokens"]["parameters"]
    first = call("PATCH", "/workflow/parameters", {"parameters": {"technology": "can_fd", "bitrate": 500000}, "expected_token": token})
    assert first.status_code == 200, first.get_json()
    second = call("PATCH", "/workflow/parameters", {"parameters": {"technology": "lin"}, "expected_token": token})
    assert second.status_code == 409
    assert call("GET", "/workflow").get_json()["parameters"]["technology"] == "can_fd"
    assert call("POST", "/hardware-nodes", {"name": "Another controller", "device_type": "ECU"}).status_code == 201


def test_failed_invalidation_rolls_back_object_and_history(workspace, monkeypatch):
    _, call = workspace
    def fail(*args, **kwargs):
        raise RuntimeError("Injected invalidation failure")
    monkeypatch.setattr(api_module.WorkflowStatusService, "mark_changed", fail)
    response = call("POST", "/hardware-nodes", {"name": "Must roll back", "device_type": "ECU"})
    assert response.status_code == 503
    assert call("GET", "/hardware-nodes").get_json()["count"] == 0


def topology():
    return {
        "nodes": [
            {"id": "a", "name": "Source", "kind": "sensor", "ports": [{"id": "a-p", "name": "CAN", "bus": "can_fd"}]},
            {"id": "b", "name": "Target", "kind": "ecu", "ports": [{"id": "b-p", "name": "CAN", "bus": "can_fd"}]},
        ],
        "edges": [{"id": "a-b", "source": "a", "sourcePort": "a-p", "target": "b", "targetPort": "b-p", "bus": "can_fd"}],
    }


def test_parallel_topology_sync_is_idempotent_and_partial_failure_rolls_back(workspace):
    _, call = workspace
    gate = Barrier(4)
    def sync(_):
        gate.wait(timeout=10)
        return call("POST", "/topology/sync", {**topology(), "persist_workflow": False})
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(sync, range(4)))
    assert all(r.status_code == 200 for r in responses), [r.get_json() for r in responses]
    assert all(r.get_json()["nodes"] == responses[0].get_json()["nodes"] for r in responses)
    assert call("GET", "/hardware-nodes").get_json()["count"] == 2
    assert call("GET", "/interfaces").get_json()["count"] == 2
    bad = topology()
    bad["nodes"][0]["id"] = "new-node"
    bad["nodes"][1]["kind"] = "invalid"
    response = call("POST", "/topology/sync", {**bad, "persist_workflow": False})
    assert response.status_code == 400
    assert call("GET", "/hardware-nodes").get_json()["count"] == 2


def test_stale_topology_rejected_before_sync_side_effects(workspace):
    _, call = workspace
    token = call("GET", "/workflow").get_json()["edit_tokens"]["topology"]
    response = call("PUT", "/workflow/topology", {"topology": topology(), "expected_token": token})
    assert response.status_code == 200, response.get_json()
    stale = topology()
    stale["nodes"][0]["id"] = "should-not-exist"
    response = call("PUT", "/workflow/topology", {"topology": stale, "expected_token": token})
    assert response.status_code == 409
    assert call("GET", "/hardware-nodes").get_json()["count"] == 2


def test_layouts_of_distinct_views_do_not_delete_each_other(workspace):
    _, call = workspace
    for key in ("view-a", "view-b"):
        response = call("PUT", "/workflow/topology-layout", {"topology_key": key, "layout_version": 1, "nodes": [{"node_id": "n", "x": 10, "y": 20}]})
        assert response.status_code == 200, response.get_json()
    assert len(call("GET", "/workflow/topology-layout?topology_key=view-a&layout_version=1").get_json()["nodes"]) == 1


def test_request_restores_prior_project_context(workspace):
    _, call = workspace
    token = activate_project("outside-request")
    try:
        call("GET", "/workflow")
        assert current_project_id() == "outside-request"
    finally:
        reset_project(token)


def test_hardware_defaults_and_multiple_distinct_ecu_functions(workspace):
    _, call = workspace
    node = call("POST", "/hardware-nodes", {"name": "Multi function ECU", "device_type": "ECU"}).get_json()
    port = call("POST", "/hardware-interfaces", {"name": "CAN controller", "technology": "CAN_FD", "hardware_node_id": node["id"]})
    assert port.status_code == 201, port.get_json()
    assert port.get_json()["status"] == "UNMAPPED"
    assert port.get_json()["message_refs"] == []
    for name in ("Temperature control", "Pressure control"):
        assert call("POST", "/functions", {"name": name, "hardware_node_id": node["id"]}).status_code == 201
    check = call("GET", "/workflow").get_json()["artifact_checks"]["engineering_model"]["consistency"]
    assert check["functions_duplicate"] == 0


def test_identical_topology_can_be_reconfirmed_after_routing_edit(workspace):
    _, call = workspace
    saved = call("PUT", "/workflow/topology", {"topology": topology()}).get_json()
    call("POST", "/workflow/changed", {"step": "routing", "reason": "Routing changed"})
    assert call("GET", "/workflow").get_json()["statuses"]["network_editor"] == "OUTDATED"
    response = call("PUT", "/workflow/topology", {"topology": saved["topology"]})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["statuses"]["network_editor"] == "COMPLETE"


def test_parallel_simulation_start_uses_one_frozen_snapshot(workspace, monkeypatch):
    from importlib import import_module
    simulation_api = import_module("backend.app.api")
    from psycopg.types.json import Jsonb
    project, _ = workspace
    with get_connection() as connection:
        snapshot = connection.execute(
            "INSERT INTO engineering_simulation_snapshots (project_id, source_versions, configuration) VALUES (%s, '{}'::jsonb, %s) RETURNING id",
            (project, Jsonb({"technology": "can_fd", "duration_s": 0.1, "seed": 42})),
        ).fetchone()
    submitted = []
    def submit(payload):
        submitted.append(payload)
        return {"id": "one-job", "status": "queued"}
    monkeypatch.setattr(simulation_api.JOBS, "submit", submit)
    gate = Barrier(4)
    def start(_):
        with create_app(testing=True).test_client() as client:
            gate.wait(timeout=10)
            return client.post("/api/simulations", headers={"X-Project-ID": project}, json={
                "workflow_snapshot_id": str(snapshot["id"]), "workflow_managed": True,
                "project_id": project, "technology": "lin", "duration_s": 999,
            })
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(start, range(4)))
    assert sorted(r.status_code for r in responses) == [202, 409, 409, 409]
    assert len(submitted) == 1
    assert submitted[0]["config"]["technology"] == "can_fd"
    assert submitted[0]["config"]["duration_s"] == 0.1


def test_parallel_route_edits_reject_stale_revisions(workspace):
    _, call = workspace
    assert call("PUT", "/workflow/topology", {"topology": topology()}).status_code == 200
    route = call("GET", "/routing").get_json()["items"][0]
    gate = Barrier(4)
    def edit(index):
        gate.wait(timeout=10)
        return call("PATCH", f"/routing/{route['id']}", {"description": f"Editor {index}", "expected_revision": route["revision"]})
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(edit, range(4)))
    assert sorted(response.status_code for response in responses) == [200, 409, 409, 409]


def test_snapshot_transport_uses_canonical_values_and_frozen_model(monkeypatch):
    import json
    from backend.engineering import simulation
    model = {"nodes": [], "functions": [], "interfaces": [{"id": "port", "configuration": {"bitrate": 500000, "data_bitrate": 2000000}}],
             "messages": [{"id": "msg", "cycle_ms": 20, "dlc": 8}], "signals": [], "behaviors": [],
             "routes": [{"id": "route", "approval_state": "APPROVED", "source": {"interface_id": "port", "protocol": "CAN_FD"}, "payload": {"message_id": "msg"}}]}
    monkeypatch.setattr(simulation, "load_engineering_simulation_model", lambda _: model)
    model["nodes"] = [{"id": uuid.uuid4()}]
    monkeypatch.setattr("backend.engineering.workflow.service.WorkflowStatusService.get", lambda _: {"topology": {"nodes": []}, "parameters": {"technology": "can_fd", "bitrate": 1000000}})
    def transport(_, routes):
        assert routes[0]["timing"]["cycle_time_ms"] == 20
        assert routes[0]["validation"]["metrics"]["payload_bytes"] == 8
        return {"communications": [{"network_id": "net", "routing_entry_id": "route", "cycle_ms": 20}], "networks": [{"id": "net"}], "hardware": {}, "routing_entry_ids": ["route"]}
    monkeypatch.setattr(simulation, "_load_project_transport_config", transport)
    frozen = simulation.prepare_workflow_simulation_config({"duration_s": 2, "communications": [{"cycle_ms": 999}]}, "audit")
    json.dumps(frozen)
    assert frozen["communications"][0]["cycle_ms"] == 20
    assert frozen["networks"][0]["bitrate"] == 500000
    assert frozen["networks"][0]["data_bitrate"] == 2000000
    monkeypatch.setattr(simulation, "load_engineering_simulation_model", lambda _: pytest.fail("Frozen run read the current model"))
    resumed = simulation.enrich_simulation_config(frozen, "audit", model=frozen["engineering_model"])
    assert resumed["engineering_model"]["messages"][0]["cycle_ms"] == 20


def test_canonical_transport_has_executable_ports_and_produces_frames(workspace, tmp_path):
    from backend.engineering.simulation import prepare_workflow_simulation_config
    from communication_simulator import run_simulation
    project, call = workspace
    assert call("PUT", "/workflow/topology", {"topology": topology()}).status_code == 200
    route = call("GET", "/routing").get_json()["items"][0]
    assert call("POST", f"/routing/{route['id']}/validate", {}).status_code == 200
    approved = call("POST", "/routing/approve-selected", {"route_ids": [route["id"]], "actor": "test-reviewer"})
    assert approved.status_code == 200, approved.get_json()
    config = prepare_workflow_simulation_config({"duration_s": 0.1, "formats": ["universal-jsonl"], "seed": 42, "output_dir": str(tmp_path)}, project)
    assert all(node["interfaces"] for node in config["hardware"]["devices"])
    result = run_simulation(config)
    assert result["trace"]["events"] > 0
    assert result["trace"]["networks"] == [config["networks"][0]["id"]]
