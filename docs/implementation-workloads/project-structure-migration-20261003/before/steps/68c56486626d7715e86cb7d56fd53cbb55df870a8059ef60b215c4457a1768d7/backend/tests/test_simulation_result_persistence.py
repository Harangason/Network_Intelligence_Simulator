"""Complete simulation evidence is persisted once behind the original guards."""
from contextlib import contextmanager
from copy import deepcopy
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from backend.engineering.db import get_connection
from backend.engineering.workflow import service as workflow_module
from backend.engineering.workflow.models import default_versions
from backend.engineering.workflow.service import WorkflowStatusService
from backend.tests.test_model_ownership import db_project


def _snapshot(project, *, status="RUNNING", outdated=False, stale=False):
    service = WorkflowStatusService(project)
    config = {
        "engineering_model": {"messages": [{"id": "message"}],
                              "signals": [{"id": "signal", "message_id": "message"}]},
        "communications": [{"id": "transport", "routing_entry_id": "route",
                            "message_ids": ["message"], "signal_ids": ["signal"]}],
        "networks": [{"id": "network"}], "simulation_scope": {"mode": "ALL"},
        "unchanged_configuration": {"encoding": [0, 1, 7, 255]},
    }
    snapshot_id = str(uuid4())
    versions = {**default_versions(), "simulation": 9 if stale else 0}
    with get_connection() as connection:
        service._ensure(connection)
        connection.execute(
            "INSERT INTO engineering_simulation_snapshots "
            "(id, project_id, source_versions, configuration, status, is_outdated, job_id, result) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'original-job', %s)",
            (snapshot_id, project, Jsonb(versions), Jsonb(config), status, outdated,
             Jsonb({"previous": "retained"})),
        )
    return service, snapshot_id, config


def _result():
    return {
        "status": "completed", "trace": {"events": 123}, "warnings": [],
        "model_simulation": {"signals": [{"signal_id": "signal"}],
                             "events": [{"id": "event", "raw": [0, 1, 7, 255]}]},
        "runtime_metrics": {"available": True, "routes": [{"route_id": "transport", "status": "PASS"}],
                            "networks": [{"network_id": "network"}]},
    }


def _observe_statements(monkeypatch):
    statements = []

    class Connection:
        def __init__(self, underlying):
            self.underlying = underlying

        def execute(self, query, parameters=None):
            statements.append(" ".join(str(query).split()))
            return self.underlying.execute(query, parameters)

    @contextmanager
    def tracked_connection():
        with get_connection() as connection:
            yield Connection(connection)

    monkeypatch.setattr(workflow_module, "get_connection", tracked_connection)
    return statements


def test_completed_evidence_is_serialized_and_written_once_with_full_assessment(db_project, monkeypatch):
    service, snapshot_id, config = _snapshot(db_project)
    result = _result()
    before = deepcopy(result)
    expected_assessment = workflow_module.assess_simulation(config, result)
    statements = _observe_statements(monkeypatch)
    serialized_results = []
    original_json = workflow_module._json

    def observed_json(value):
        if value is result:
            serialized_results.append(deepcopy(value))
        return original_json(value)

    monkeypatch.setattr(workflow_module, "_json", observed_json)
    service.update_simulation_snapshot(snapshot_id, status="COMPLETED", job_id="stable-job", result=result)

    with get_connection() as connection:
        snapshot = connection.execute("SELECT * FROM engineering_simulation_snapshots WHERE id = %s",
                                      (snapshot_id,)).fetchone()
        analysis = connection.execute("SELECT * FROM engineering_analysis_snapshots WHERE project_id = %s",
                                      (db_project,)).fetchone()
    expected = {**before, "assessment": expected_assessment}
    assert snapshot["configuration"] == config
    assert snapshot["result"] == result == expected
    assert snapshot["job_id"] == "stable-job" and snapshot["status"] == "COMPLETED"
    assert analysis["input_data"]["configuration"] == config
    assert analysis["results"]["simulation_snapshot_id"] == snapshot_id
    assert analysis["results"]["assessment"] == expected_assessment
    assert analysis["status"] == "COMPLETE"
    assert serialized_results == [expected]
    writes = [q for q in statements if q.startswith("UPDATE engineering_simulation_snapshots")]
    assert len(writes) == 1
    assert all("RETURNING *" not in q for q in writes)


@pytest.mark.parametrize("status", ["RUNNING", "FAILED", "CANCELED"])
def test_status_updates_preserve_result_without_loading_bulk_snapshot(db_project, monkeypatch, status):
    service, snapshot_id, _ = _snapshot(db_project)
    statements = _observe_statements(monkeypatch)
    service.update_simulation_snapshot(snapshot_id, status=status, job_id="stable-job")
    with get_connection() as connection:
        row = connection.execute("SELECT status, result FROM engineering_simulation_snapshots WHERE id = %s",
                                 (snapshot_id,)).fetchone()
    assert row == {"status": status, "result": {"previous": "retained"}}
    snapshot_reads = [q for q in statements if "engineering_simulation_snapshots" in q]
    assert snapshot_reads and all("RETURNING *" not in q and "SELECT *" not in q for q in snapshot_reads)
    assert all("configuration" not in q for q in snapshot_reads)


@pytest.mark.parametrize("condition", ["canceled", "outdated", "source_revision", "other_project"])
@pytest.mark.parametrize("transition", ["COMPLETED", "RUNNING", "FAILED", "CANCELED"])
def test_invalid_snapshot_cannot_change_results_or_create_analysis(db_project, monkeypatch, condition, transition):
    initial = "CANCELED" if condition == "canceled" else "RUNNING"
    service, snapshot_id, _ = _snapshot(db_project, status=initial,
                                       outdated=condition == "outdated", stale=condition == "source_revision")
    if condition == "other_project":
        service = WorkflowStatusService(db_project + "-other")
    result = _result()
    statements = _observe_statements(monkeypatch)
    service.update_simulation_snapshot(snapshot_id, status=transition, job_id="late-job", result=result)
    with get_connection() as connection:
        row = connection.execute("SELECT status, job_id, result FROM engineering_simulation_snapshots WHERE id = %s",
                                 (snapshot_id,)).fetchone()
        count = connection.execute("SELECT count(*) AS count FROM engineering_analysis_snapshots WHERE project_id = %s",
                                   (db_project,)).fetchone()["count"]
    assert row == {"status": initial, "job_id": "original-job", "result": {"previous": "retained"}}
    assert count == 0 and "assessment" not in result
    assert not any(q.startswith("UPDATE engineering_simulation_snapshots") for q in statements)


def test_completion_without_new_result_retains_existing_data_but_does_not_claim_evidence(db_project):
    service, snapshot_id, _ = _snapshot(db_project)
    service.update_simulation_snapshot(snapshot_id, status="COMPLETED")
    with get_connection() as connection:
        snapshot = connection.execute("SELECT status, job_id, result FROM engineering_simulation_snapshots WHERE id = %s",
                                      (snapshot_id,)).fetchone()
        statuses = connection.execute("SELECT statuses FROM engineering_workflow_projects WHERE project_id = %s",
                                      (db_project,)).fetchone()["statuses"]
        count = connection.execute("SELECT count(*) AS count FROM engineering_analysis_snapshots WHERE project_id = %s",
                                   (db_project,)).fetchone()["count"]
    assert snapshot == {"status": "COMPLETED", "job_id": "original-job", "result": {"previous": "retained"}}
    assert statuses["simulation"] == "WARNING" and statuses["results_analysis"] == "ERROR"
    assert count == 0


def test_completion_without_replacement_job_id_retains_identity_in_analysis(db_project):
    service, snapshot_id, _ = _snapshot(db_project)
    service.update_simulation_snapshot(snapshot_id, status="COMPLETED", result=_result())
    with get_connection() as connection:
        snapshot = connection.execute("SELECT job_id FROM engineering_simulation_snapshots WHERE id = %s",
                                      (snapshot_id,)).fetchone()
        analysis = connection.execute("SELECT results, provenance FROM engineering_analysis_snapshots WHERE project_id = %s",
                                      (db_project,)).fetchone()
    assert snapshot["job_id"] == analysis["results"]["job_id"] == "original-job"
    assert analysis["results"]["simulation_snapshot_id"] == snapshot_id


def test_optional_large_result_before_after_benchmark(db_project, monkeypatch):
    """Opt-in benchmark uses captured evidence in the disposable test DB only."""
    import ast
    import json
    import os
    from pathlib import Path
    from time import perf_counter

    data_path = os.environ.get("NIS_SNAPSHOT_BENCHMARK_DATA")
    before_path = os.environ.get("NIS_SNAPSHOT_BENCHMARK_BEFORE")
    if not data_path or not before_path:
        pytest.skip("Opt-in captured large-result benchmark")
    evidence = json.loads(Path(data_path).read_text(encoding="utf-8"))
    before_source = ast.parse(Path(before_path).read_text(encoding="utf-8-sig"))
    service_class = next(node for node in before_source.body if isinstance(node, ast.ClassDef)
                         and node.name == "WorkflowStatusService")
    method = next(node for node in service_class.body if isinstance(node, ast.FunctionDef)
                  and node.name == "update_simulation_snapshot")
    namespace = dict(vars(workflow_module))
    exec(compile(ast.Module(body=[method], type_ignores=[]), before_path, "exec"), namespace)
    old_method = namespace["update_simulation_snapshot"]
    records = []
    hashes = []
    # Alternate order to expose warmed-cache bias rather than concealing it.
    for label in ["before", "after", "after", "before"]:
        service, snapshot_id, _ = _snapshot(db_project)
        with get_connection() as connection:
            connection.execute("UPDATE engineering_simulation_snapshots SET configuration = %s WHERE id = %s",
                               (Jsonb(evidence["configuration"]), snapshot_id))
        result = deepcopy(evidence["result"])
        start = perf_counter()
        method = old_method if label == "before" else WorkflowStatusService.update_simulation_snapshot
        method(service, snapshot_id, status="COMPLETED", job_id="benchmark-job", result=result)
        duration = perf_counter() - start
        with get_connection() as connection:
            persisted = connection.execute(
                "SELECT md5(result::text) AS result_hash, octet_length(result::text) AS result_bytes, "
                "md5(configuration::text) AS configuration_hash FROM engineering_simulation_snapshots WHERE id = %s",
                (snapshot_id,),
            ).fetchone()
        hashes.append((persisted["result_hash"], persisted["configuration_hash"]))
        records.append({"version": label, "seconds": round(duration, 4), **persisted})
    assert len(set(hashes)) == 1, "Optimization changed full result or frozen configuration"
    output = {"database_isolated": True, "snapshot_evidence": Path(data_path).name, "runs": records,
              "equal_full_result_and_configuration": True}
    print("SNAPSHOT_PERSISTENCE_BENCHMARK=" + json.dumps(output))
    if destination := os.environ.get("NIS_SNAPSHOT_BENCHMARK_OUTPUT"):
        Path(destination).write_text(json.dumps(output, indent=2), encoding="utf-8")
