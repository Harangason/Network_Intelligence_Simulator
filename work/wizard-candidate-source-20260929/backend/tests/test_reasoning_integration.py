"""Real PostgreSQL/API/MCP boundaries; only the remote job transport is stubbed."""
import asyncio
from copy import deepcopy
import os
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from backend.engineering.db import get_connection
from backend.engineering.project_context import activate_project, reset_project, current_project_id
from backend.engineering.repository import NotFoundError
from backend.engineering.workflow.service import WorkflowStatusService
from backend.engineering.reasoning.service import ReasoningService
from backend.engineering.reasoning import service as services
from backend.tests.test_engineering_reasoning import frame


@pytest.fixture
def setup(monkeypatch):
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("isolated PostgreSQL required")
    project = "reasoning-test-" + uuid4().hex
    token = activate_project(project)
    workflow = WorkflowStatusService(project)
    versions = workflow.get(summary=True)["versions"]
    jobs = {}

    def add_job(events=None, status="completed", config=None):
        job_id, snapshot_id = uuid4().hex, str(uuid4())
        config = config or {"seed": 42, "duration_s": 2, "scenario": {"mode": "NORMAL", "faults": []}}
        with get_connection() as connection:
            connection.execute("INSERT INTO engineering_simulation_snapshots (id,project_id,source_versions,configuration,status,job_id) VALUES (%s,%s,%s,%s,'COMPLETE',%s)",
                (snapshot_id, project, Jsonb(versions), Jsonb(config), job_id))
        jobs[job_id] = {"metadata": {"id": job_id, "project_id": project, "status": status, "updated_at": "revision-1", "workflow_snapshot_id": snapshot_id},
            "events": [frame()] if events is None else events, "cursor": None}
        return job_id

    def request(path, **_):
        job_id = path.split("/")[2].split("?")[0]
        job = jobs.get(job_id)
        if not job or current_project_id() != project:
            raise NotFoundError("job not found")
        if "trace-window" in path:
            if job["events"] == "missing":
                raise NotFoundError("trace not found")
            return {"events": deepcopy(job["events"]), "next_cursor": job["cursor"]}
        assert "view=metadata" in path, "Whole job/trace reads are forbidden"
        return deepcopy(job["metadata"])

    monkeypatch.setattr(services.gateway, "request_json", request)
    from backend.app import create_app
    client = create_app(testing=True).test_client()
    try:
        yield project, jobs, add_job, client, workflow
    finally:
        reset_project(token)


def test_api_persists_without_changing_workflow_and_isolates_projects(setup):
    project, jobs, add, client, workflow = setup
    job = add()
    versions = workflow.get(summary=True)["versions"]
    headers = {"X-Project-ID": project}
    response = client.post("/api/engineering/reasoning", json={"job_id": job}, headers=headers)
    assert response.status_code == 201, response.json
    data = response.json
    assert data["completion_status"] == "COMPLETE", data
    assert workflow.get(summary=True)["versions"] == versions
    path = "/api/engineering/reasoning/" + data["reasoning_id"]
    assert client.get(path, headers=headers).json["validation_status"] == "CURRENT"
    assert client.get(path, headers={"X-Project-ID": "other-project"}).status_code == 404
    assert client.get("/api/engineering/reasoning", headers=headers).json["items"][0]["id"] == data["reasoning_id"]
    assert client.post(path + "/continue", json={}, headers=headers).status_code == 409
    assert client.post("/api/engineering/reasoning", json={"job_id": job, "cursor": -1}, headers=headers).status_code == 400
    assert client.post("/api/engineering/reasoning", json={"job_id": job, "hidden_reasoning": "invalid"}, headers=headers).status_code == 400


def test_changed_trace_or_source_blocks_proposal(setup):
    project, jobs, add, client, workflow = setup
    job = add()
    result = ReasoningService().analyze({"job_id": job})
    jobs[job]["metadata"]["updated_at"] = "revision-2"
    assert ReasoningService().get(result.reasoning_id).validation_status == "STALE"
    response = client.post(f"/api/engineering/reasoning/{result.reasoning_id}/proposal", json={"action_id": "capacity-repair"}, headers={"X-Project-ID": project})
    assert response.status_code == 409
    jobs[job]["metadata"]["updated_at"] = "revision-1"
    with get_connection() as connection:
        connection.execute("UPDATE engineering_workflow_projects SET versions=jsonb_set(versions,'{engineering_model}',to_jsonb((versions->>'engineering_model')::int+1)) WHERE project_id=%s", (project,))
    assert ReasoningService().get(result.reasoning_id).validation_status == "STALE"


def test_failed_run_without_trace_is_structured_incomplete(setup):
    _, _, add, _, _ = setup
    result = ReasoningService().analyze({"job_id": add(events="missing", status="failed")})
    assert result.completion_status == "INCOMPLETE"
    assert not result.confirmed_causes
    assert "SIMULATION_FAILED" in {g["code"] for g in result.data_gaps}


def test_mcp_and_agent_cannot_treat_partial_tool_success_as_completion(setup):
    project, jobs, add, _, _ = setup
    job = add()
    jobs[job]["metadata"].pop("workflow_snapshot_id")
    from backend.agent_core.api.mcp_client import EngineeringMCPClient
    from backend.engineering.agent_tools.runtime import ToolAuthority
    from backend.simulator_engineering_mcp.server import create_server
    from backend.agent_core.core.engineering_agent import EngineeringAgent
    from backend.agent_core.context.agent_context import AgentContext
    async def run():
        async with EngineeringMCPClient(create_server(ToolAuthority(project))) as client:
            result = await client.call("analyze_trace_root_cause", {"job_id": job})
            assert result.success and result.status == "PARTIAL", result
            assert result.evidence_refs and result.affected_objects
            denied = await client.call("get_trace_events", {"job_id": uuid4().hex})
            assert denied.status == "NOT_FOUND"
            answer = await EngineeringAgent(client).run(f"Untersuche Ursache im Trace {job}", AgentContext(active_project_id=project))
            assert answer["status"] == "INCOMPLETE", answer
            assert not answer["proposals"]
    asyncio.run(run())


def test_run_comparison_demands_equal_fault_scenario_and_coverage(setup):
    _, jobs, add, _, _ = setup
    service = ReasoningService()
    first = service.analyze({"job_id": add()})
    good_job = add([frame(queue_delay_ms=0, queue_depth_estimate=0, end_to_end_latency_ms=4, transmission_latency_ms=1)])
    good = service.analyze({"job_id": good_job})
    assert good.completion_status == "NO_ANOMALY_IN_WINDOW", good
    comparison = service.compare_runs(first.reasoning_id, good.reasoning_id)
    assert comparison["status"] == "IMPROVEMENT_VERIFIED_IN_WINDOW", comparison
    changed = service.analyze({"job_id": add(jobs[good_job]["events"], config={"seed": 7, "duration_s": 2, "scenario": {"mode": "NORMAL", "faults": []}})})
    assert service.compare_runs(first.reasoning_id, changed.reasoning_id)["status"] == "IMPROVEMENT_NOT_VERIFIED"
    missing = service.analyze({"job_id": add([*jobs[good_job]["events"], frame(sequence=2)])})
    assert not service.compare_runs(first.reasoning_id, missing.reasoning_id)["same_transport_and_signal_coverage"]


def test_proposal_reuses_governed_planner_without_apply(setup, monkeypatch):
    _, _, add, _, _ = setup
    from backend.engineering.agent_tools import wizard_generation, proposal_service
    invoked = []
    monkeypatch.setattr(wizard_generation, "generate_capacity_network_repair", lambda args: invoked.append(args) or {"proposal_id": "proposal", "status": "PROPOSED", "changes": []})
    validated = []
    monkeypatch.setattr(proposal_service, "validate", lambda identifier: validated.append(identifier) or {"proposal_id": identifier, "status": "VALIDATED"})
    service = ReasoningService()
    result = service.analyze({"job_id": add([frame(transmission_latency_ms=8)])})
    assert any(a["id"] == "capacity-repair" for a in result.recommended_actions)
    assert service.propose(result.reasoning_id, "capacity-repair")["status"] == "VALIDATED"
    assert result.reasoning_id in invoked[0]["prompt"]
    assert validated == ["proposal"]
    with pytest.raises(ValueError):
        service.propose(result.reasoning_id, "measurement")


def test_measured_improvement_is_distinct_from_unresolved_explanation(setup, monkeypatch):
    _, _, add, _, _ = setup
    service = ReasoningService()
    before = service.analyze({'job_id': add()})
    after = service.analyze({'job_id': add([frame(queue_delay_ms=0, queue_depth_estimate=0, end_to_end_latency_ms=4, transmission_latency_ms=1, injected_jitter_ms=.01)])})
    assert after.completion_status == 'INCOMPLETE'
    result = service.compare_runs(before.reasoning_id, after.reasoning_id)
    assert result['status'] == 'IMPROVEMENT_VERIFIED_IN_WINDOW'
    assert result['cause_explanation_complete']['after'] is False
    after.data_gaps.append({'code': 'MISSING_DECODE', 'blocking': True})
    monkeypatch.setattr(service, 'get', lambda rid: before if rid == before.reasoning_id else after)
    assert service.compare_runs(before.reasoning_id, after.reasoning_id)['status'] == 'IMPROVEMENT_NOT_VERIFIED'
