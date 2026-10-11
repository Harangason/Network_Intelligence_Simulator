import os
from uuid import uuid4
import pytest
from backend.nis.app import create_app
from backend.nis.infrastructure.persistence.db import close_pool
from backend.nis.engineering.projects.project_context import activate_project, reset_project
from backend.nis.engineering.routing.repository import create_route
from backend.tests.test_safety_assurance import requirement

pytestmark = pytest.mark.skipif(not os.environ.get("ENGINEERING_TEST_DATABASE_URL"), reason="Disposable SQL database required")


def test_canonical_requirement_crud_binding_revision_history_and_project_isolation():
    os.environ["DATABASE_URL"] = os.environ["ENGINEERING_TEST_DATABASE_URL"]; close_pool()
    client = create_app(testing=True).test_client(); project = "pytest-safety-" + uuid4().hex
    client.environ_base["HTTP_X_PROJECT_ID"] = project
    node = client.post("/api/engineering/hardware-nodes", json={"name": "Lenkung", "device_type": "ECU"}).get_json()
    function = client.post("/api/engineering/functions", json={"name": "Lenkung regeln", "hardware_node_id": node["id"]}).get_json()
    token = activate_project(project)
    try: route = create_route({"name": "Lenkungspfad", "source": {"node_id": node["id"]}, "destinations": [{"node_id": node["id"]}]})
    finally: reset_project(token)
    config = requirement()["configuration"]; config["route_ids"] = [str(route["id"])]
    config["criteria"]["fault_cases"][0]["receiver_id"] = node["id"]
    response = client.post("/api/engineering/safety-requirements", json={"name": "Safety Lenkung", "function_id": function["id"], "configuration": config})
    assert response.status_code == 201, response.get_json()
    row = response.get_json(); assert row["version"] == 1 and row["approval_state"] == "pending"
    model = client.get("/api/engineering/intelligence/safety").get_json()
    assert model["requirements"][0]["id"] == row["id"]
    assert model["bundle"]["payload"]["assessment"]["technical_status"] == "NOT_EVALUATED"
    assert client.patch(f"/api/engineering/safety-requirements/{row['id']}", json={"name": "Updated", "expected_version": 1}).status_code == 200
    assert client.patch(f"/api/engineering/safety-requirements/{row['id']}", json={"name": "Stale", "expected_version": 1}).status_code == 409
    assert len(client.get(f"/api/engineering/safety-requirements/{row['id']}/versions").get_json()["items"]) == 2
    assert client.patch(f"/api/engineering/safety-requirements/{row['id']}", json={"approval_state": "approved", "expected_version": 2}).status_code == 409
    other = create_app(testing=True).test_client(); other.environ_base["HTTP_X_PROJECT_ID"] = "pytest-other-" + uuid4().hex
    assert other.get(f"/api/engineering/safety-requirements/{row['id']}").status_code == 404
    assert other.post("/api/engineering/safety-requirements", json={"name": "Cross project", "function_id": function["id"], "configuration": config}).status_code == 404
    bad = {**config, "criteria": {"deadline_ms": True}}
    assert client.patch(f"/api/engineering/safety-requirements/{row['id']}", json={"configuration": bad, "expected_version": 2}).status_code == 400
    assert client.get(f"/api/engineering/safety-requirements/{row['id']}").get_json()["version"] == 2
    assert client.patch(f"/api/engineering/safety-requirements/{row['id']}", json={"name": "Unversioned"}).status_code == 400
    token = activate_project(project)
    try:
        from backend.nis.engineering.simulation import load_engineering_simulation_model
        frozen = load_engineering_simulation_model(project)
    finally: reset_project(token)
    assert frozen["safety_requirements"][0]["version"] == 2
    assert client.get('/api/engineering/intelligence/safety?snapshot=' + str(uuid4())).status_code == 404
    # Browser project files and clones preserve the canonical requirement chain.
    from backend.nis.engineering.projects.project_bundle import ProjectBundleService
    service = ProjectBundleService()
    exported = service.export(project)
    assert exported['source_data']['engineering_safety_requirements'][0]['id'] == row['id']
    # Even a well-formed project file can carry a fabricated technical PASS.
    # Import must not turn this client-provided result into server evidence.
    exported['project_data']['engineering_simulation_snapshots'] = [{
        'id': str(uuid4()), 'project_id': project, 'source_versions': {'engineering_model': 1},
        'configuration': {'engineering_model': {'safety_requirements': [row]}},
        'status': 'COMPLETED', 'job_id': 'operator-provided-job', 'is_outdated': False,
        'result': {'runtime_metrics': {'safety_assurance': {'technical_status': 'PASS'}, 'delivery_pct': 100}},
    }]
    clone_project = 'pytest-safety-clone-' + uuid4().hex
    service.import_bundle(exported, target_project_id=clone_project)
    cloned = service.export(clone_project)['source_data']
    cloned_requirement = cloned['engineering_safety_requirements'][0]
    assert cloned_requirement['id'] != row['id']
    assert cloned_requirement['function_id'] == cloned['engineering_functions'][0]['id']
    assert cloned_requirement['configuration']['route_ids'] == [cloned['engineering_routing_entries'][0]['id']]
    assert cloned_requirement['configuration']['criteria']['fault_cases'][0]['receiver_id'] == cloned['engineering_hardware_nodes'][0]['id']
    assert cloned_requirement['version'] == 2
    assert cloned_requirement['configuration']['eip'] == config['eip']
    imported_snapshot = service.export(clone_project)['project_data']['engineering_simulation_snapshots'][0]
    assert imported_snapshot['is_outdated'] is True
    assert 'safety_assurance' not in imported_snapshot['result']['runtime_metrics']
    assert imported_snapshot['result']['runtime_metrics']['delivery_pct'] == 100
    from backend.nis.engineering.safety_assurance import export_snapshot
    imported_report = export_snapshot(clone_project, imported_snapshot, [cloned_requirement])
    assert imported_report['payload']['assessment']['technical_status'] == 'NOT_EVALUATED'
    assert imported_report['payload']['freshness'] == 'OUTDATED'
    assert exported['project_data']['engineering_simulation_snapshots'][0]['result']['runtime_metrics']['safety_assurance']['technical_status'] == 'PASS', 'Import must not mutate the caller bundle'
    service.reset_workspace(clone_project)
    assert not service.export(clone_project)['source_data']['engineering_safety_requirements']
    assert client.get(f"/api/engineering/safety-requirements/{row['id']}").status_code == 200
