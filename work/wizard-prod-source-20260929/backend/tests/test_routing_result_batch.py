"""Bulk route observations retain project isolation, evidence and audit history."""
from contextlib import contextmanager
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from backend.engineering.db import get_connection
from backend.engineering.routing import repository as routes
from backend.tests.test_model_ownership import db_project


def seed(project, count=3):
    ids = [str(uuid4()) for _ in range(count)]
    with get_connection() as connection:
        for identifier in ids:
            connection.execute("INSERT INTO engineering_routing_entries (id, project_id, route_code, name, source) "
                               "VALUES (%s, %s, %s, 'local route', '{}')",
                               (identifier, project, 'RT-' + uuid4().hex))
    return ids


def result(events=99):
    return {"status": "completed", "trace": {"events": events, "technologies": ["LIN", "CAN_FD"]},
            "hardware_validation": {"valid": True}, "warnings": ["measured warning"],
            "model_simulation": {"signals": [{"raw": 12345}]}}


def stored(project):
    with get_connection() as connection:
        relations = connection.execute(
            "SELECT source_id, target_id, attributes, source, provenance, review_state, approval_state, created_by "
            "FROM engineering_relations WHERE project_id = %s ORDER BY source_id", (project,)).fetchall()
        audit = connection.execute(
            "SELECT route_id, action, actor, agent, model, before_state, after_state, reason, evidence "
            "FROM engineering_routing_audit WHERE project_id = %s ORDER BY id", (project,)).fetchall()
    return relations, audit


def test_batch_keeps_duplicate_audit_order_and_skips_foreign_or_missing_routes(db_project):
    first, second, untouched = seed(db_project)
    foreign = seed(db_project + '-other', 1)[0]
    job = str(uuid4())
    routes.record_simulation_results([second, foreign, str(uuid4()), first, second], job, result())
    relations, audit = stored(db_project)
    assert {str(row['source_id']) for row in relations} == {first, second}
    assert [str(row['route_id']) for row in audit] == [second, first, second]
    expected = {"status": "completed", "events": 99, "technologies": ["LIN", "CAN_FD"],
                "hardware_valid": True, "warnings": ["measured warning"]}
    attributes = {"job_id": job, "observation": expected}
    for row in relations:
        assert str(row['target_id']) == job
        assert row['attributes'] == attributes
        assert row['source'] == 'simulation_derived'
        assert row['provenance'] == {"origin": "communication-simulator"}
        assert (row['review_state'], row['approval_state'], row['created_by']) == ('reviewed', 'approved', 'simulation-service')
    for row in audit:
        assert row['action'] == 'ROUTE_USED_IN_SIMULATION' and row['actor'] == 'simulation-service'
        assert all(row[key] is None for key in ('agent', 'model', 'before_state', 'reason'))
        assert row['after_state'] == attributes and row['evidence'] == [expected]
    assert stored(db_project + '-other') == ([], [])


def test_repeat_updates_only_relation_attributes_and_appends_audit(db_project):
    route = seed(db_project, 1)[0]
    job = str(uuid4())
    routes.record_simulation_results([route], job, result())
    with get_connection() as connection:
        connection.execute("UPDATE engineering_relations SET source = 'retained', provenance = %s WHERE project_id = %s",
                           (Jsonb({"prior": True}), db_project))
    routes.record_simulation_results([route], job, result(101))
    relations, audit = stored(db_project)
    assert len(relations) == 1 and len(audit) == 2
    assert relations[0]['source'] == 'retained' and relations[0]['provenance'] == {"prior": True}
    assert relations[0]['attributes']['observation']['events'] == 101
    assert [row['after_state']['observation']['events'] for row in audit] == [99, 101]


@pytest.mark.parametrize('bad', ['not-a-uuid', ''])
def test_invalid_route_leaves_no_partial_observations(db_project, bad):
    route = seed(db_project, 1)[0]
    with pytest.raises(ValueError):
        routes.record_simulation_results([route, bad], str(uuid4()), result())
    assert stored(db_project) == ([], [])


def test_audit_failure_rolls_back_relation_batch(db_project, monkeypatch):
    route = seed(db_project, 1)[0]
    class Connection:
        def __init__(self, connection): self.connection = connection
        def execute(self, query, parameters=None):
            if str(query).startswith('INSERT INTO engineering_routing_audit'):
                raise RuntimeError('injected audit failure')
            return self.connection.execute(query, parameters)
    @contextmanager
    def failing_connection():
        with get_connection() as connection: yield Connection(connection)
    monkeypatch.setattr(routes, 'get_connection', failing_connection)
    with pytest.raises(RuntimeError, match='injected audit failure'):
        routes.record_simulation_results([route], str(uuid4()), result())
    assert stored(db_project) == ([], [])


def test_large_request_uses_bounded_sql_without_changing_route_rows(db_project, monkeypatch):
    ids = seed(db_project, 838)
    statements = []
    class Connection:
        def __init__(self, connection): self.connection = connection
        def execute(self, query, parameters=None):
            statements.append(str(query))
            return self.connection.execute(query, parameters)
    @contextmanager
    def observed_connection():
        with get_connection() as connection: yield Connection(connection)
    monkeypatch.setattr(routes, 'get_connection', observed_connection)
    routes.record_simulation_results(ids, str(uuid4()), result())
    assert len(statements) == 3
    relations, audit = stored(db_project)
    assert len(relations) == len(audit) == 838
    with get_connection() as connection:
        counts = connection.execute("SELECT count(*) AS n FROM engineering_routing_entries "
                                    "WHERE project_id = %s AND revision = 1 AND source = '{}'::jsonb", (db_project,)).fetchone()
    assert counts['n'] == 838
