"""Snapshot dispatch returns metadata without changing frozen execution evidence."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy

import pytest
from psycopg.types.json import Jsonb

from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.engineering.agent_tools.runtime import ToolAuthority
from backend.engineering.db import get_connection
from backend.engineering.workflow import service as workflow_module
from backend.engineering.workflow.service import WorkflowStatusService
from backend.simulator_engineering_mcp.server import create_server
from backend.tests.test_model_ownership import db_project

METADATA = {"id", "project_id", "source_versions", "validation_snapshot_id", "status", "job_id",
            "created_at", "updated_at", "is_outdated", "outdated_reason"}


def ready_project(project):
    service = WorkflowStatusService(project)
    with get_connection() as connection:
        service._ensure(connection)
        row = connection.execute("SELECT versions FROM engineering_workflow_projects WHERE project_id = %s",
                                 (project,)).fetchone()
        validation = connection.execute(
            "INSERT INTO engineering_analysis_snapshots (project_id, analysis_type, source_versions, status) "
            "VALUES (%s, 'preflight', %s, 'COMPLETE') RETURNING id",
            (project, Jsonb(row["versions"]))).fetchone()
        connection.execute(
            "INSERT INTO engineering_analysis_snapshots (project_id, analysis_type, source_versions, status, results) "
            "VALUES (%s, 'capacity_timing', %s, 'COMPLETE', %s)",
            (project, Jsonb(row["versions"]), Jsonb({"networks": [{"id": "local", "slots": [0, 7, 42]}]})))
    return service, str(validation["id"])


def frozen_config():
    return {"duration_s": 1.071, "networks": [{"id": "local", "bitrate": 19200}],
            "communications": [{"id": "local-route", "signal_ids": ["hall"],
                                "encoding": {"bits": 12, "factor": 0.125}}],
            "nested_contract": {"samples": list(range(2000))}}


@pytest.mark.parametrize("metadata_only", [False, True])
def test_creation_projection_preserves_complete_snapshot_and_revision(db_project, monkeypatch, metadata_only):
    service, validation_id = ready_project(db_project)
    config = frozen_config()
    original = deepcopy(config)
    statements = []
    class Connection:
        def __init__(self, connection): self.connection = connection
        def execute(self, query, parameters=None):
            statements.append(" ".join(str(query).split()))
            return self.connection.execute(query, parameters)
    @contextmanager
    def observed_connection():
        with get_connection() as connection: yield Connection(connection)
    monkeypatch.setattr(workflow_module, "get_connection", observed_connection)
    response = service.create_simulation_snapshot(config, metadata_only=metadata_only)
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM engineering_simulation_snapshots WHERE id = %s",
                                 (response["id"],)).fetchone()
    assert config == original
    assert all(row["configuration"][key] == value for key, value in original.items())
    assert row["calculated_metrics"] == {"networks": [{"id": "local", "slots": [0, 7, 42]}]}
    detail = service.get_simulation_snapshot(response["id"])
    assert detail["configuration"] == row["configuration"]
    assert response["source_versions"]["simulation"] == 1
    assert response["project_id"] == db_project and response["validation_snapshot_id"] == validation_id
    assert response["status"] == "READY" and response["job_id"] is None
    assert {key: response[key] for key in METADATA} == {key: detail[key] for key in METADATA}
    insert = next(q for q in statements if q.startswith("INSERT INTO engineering_simulation_snapshots"))
    if metadata_only:
        assert set(response) == METADATA
        assert "RETURNING *" not in insert
        assert "configuration" not in insert.split("RETURNING", 1)[1]
    else:
        assert response == detail
        assert "RETURNING *" in insert


@pytest.mark.parametrize("metadata_only", [None, True])
def test_mcp_snapshot_default_full_and_explicit_metadata_keep_same_detail(db_project, monkeypatch, metadata_only):
    service, _ = ready_project(db_project)
    from backend.engineering import simulation
    # Only bypass input construction: the actual service, transaction, MCP
    # transport and persisted detail read stay real in the isolated database.
    config = frozen_config()
    monkeypatch.setattr(simulation, "prepare_workflow_simulation_config", lambda value, project: value)
    async def run():
        async with EngineeringMCPClient(create_server(ToolAuthority(db_project))) as client:
            args = {"configuration": config}
            if metadata_only is not None: args["metadata_only"] = metadata_only
            return await client.call("create_simulation_snapshot", args)
    result = asyncio.run(run())
    assert result.success, result
    detail = service.get_simulation_snapshot(result.data["id"])
    assert all(detail["configuration"][key] == value for key, value in config.items())
    assert {key: result.data[key] for key in METADATA} == {key: detail[key] for key in METADATA}
    if metadata_only:
        assert set(result.data) == METADATA
    else:
        assert result.data == detail
    assert WorkflowStatusService(db_project + "-other").get_simulation_snapshot(result.data["id"]) is None
