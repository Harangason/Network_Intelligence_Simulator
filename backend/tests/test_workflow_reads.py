"""Status polling must not wait for or overwrite a concurrent project writer."""
import os
import json
import threading
from uuid import uuid4

import pytest

from backend.engineering.db import get_connection
from backend.engineering.workflow.service import WorkflowStatusService


pytestmark = pytest.mark.skipif(
    not os.environ.get('ENGINEERING_TEST_DATABASE_URL'),
    reason='isolated verification database required',
)


def project_with_default_artifacts(*, stale_parameters=False):
    project = 'workflow-read-' + uuid4().hex
    WorkflowStatusService(project).get(summary=True)
    if stale_parameters:
        with get_connection() as connection:
            connection.execute(
                "UPDATE engineering_workflow_projects SET statuses = "
                "jsonb_set(statuses, '{parameters}', '\"IN_PROGRESS\"') WHERE project_id = %s",
                (project,),
            )
    return project


def test_single_snapshot_metadata_preserves_scope_and_excludes_heavy_payloads():
    project = project_with_default_artifacts()
    snapshot_id = str(uuid4())
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO engineering_simulation_snapshots "
            "(id, project_id, source_versions, configuration, calculated_metrics, result) "
            "VALUES (%s, %s, '{\"simulation\":0}', '{\"large_model\":[]}', '{\"routes\":[]}', '{\"events\":[]}')",
            (snapshot_id, project))
    service = WorkflowStatusService(project)
    detail = service.get_simulation_snapshot(snapshot_id)
    metadata = service.get_simulation_snapshot(snapshot_id, metadata_only=True)
    assert metadata['id'] == detail['id'] == snapshot_id
    assert metadata['source_versions'] == detail['source_versions']
    assert set(metadata).isdisjoint({'configuration', 'calculated_metrics', 'result'})
    assert service.get_simulation_snapshot(snapshot_id, require_current=True, metadata_only=True) == metadata
    assert WorkflowStatusService('other-' + project).get_simulation_snapshot(snapshot_id, metadata_only=True) is None


def start_read(service, *, summary=True):
    finished = threading.Event()
    result = {}

    def read():
        try:
            result['state'] = service.get(summary=summary)
        except Exception as error:
            result['error'] = error
        finally:
            finished.set()

    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    return worker, finished, result


@pytest.mark.parametrize('summary', [True, False])
@pytest.mark.parametrize('stale_parameters', [True, False])
def test_status_read_finishes_while_an_existing_project_writer_is_uncommitted(summary, stale_parameters):
    project = project_with_default_artifacts(stale_parameters=stale_parameters)
    service = WorkflowStatusService(project)
    worker = None
    try:
        with get_connection() as writer:
            writer.execute(
                "UPDATE engineering_workflow_projects SET statuses = "
                "jsonb_set(statuses, '{capacity_timing}', '\"COMPLETE\"'), updated_at = now() "
                "WHERE project_id = %s", (project,),
            )
            worker, finished, result = start_read(service, summary=summary)
            # The writer deliberately remains uncommitted until this assertion.
            # Both INSERT-on-conflict and a blocking bootstrap UPDATE fail here.
            assert finished.wait(3), 'Status polling waited for the active project transaction.'
            assert 'error' not in result, result
            assert result['state']['statuses']['capacity_timing'] == 'EMPTY'
            assert result['state']['statuses']['parameters'] == 'APPROVED'
    finally:
        # On a regression release/rollback the writer before joining the read.
        if worker is not None:
            worker.join(3)
    assert worker is not None
    assert not worker.is_alive()
    with get_connection() as connection:
        stored = connection.execute(
            'SELECT statuses FROM engineering_workflow_projects WHERE project_id = %s', (project,),
        ).fetchone()['statuses']
    assert stored['capacity_timing'] == 'COMPLETE'
    assert stored['parameters'] == ('IN_PROGRESS' if stale_parameters else 'APPROVED')


@pytest.mark.parametrize('advance_timestamp', [True, False])
def test_status_reconciliation_does_not_overwrite_a_commit_after_its_read(advance_timestamp):
    project = project_with_default_artifacts(stale_parameters=True)
    initial_read = threading.Event()
    continue_read = threading.Event()

    class PausedRead(WorkflowStatusService):
        def _bootstrap_statuses(self, connection, state):
            initial_read.set()
            assert continue_read.wait(5)
            return super()._bootstrap_statuses(connection, state)

    worker, finished, result = start_read(PausedRead(project))
    try:
        assert initial_read.wait(3)
        with get_connection() as writer:
            timestamp = ', updated_at = now()' if advance_timestamp else ''
            writer.execute(
                "UPDATE engineering_workflow_projects SET statuses = "
                "jsonb_set(statuses, '{capacity_timing}', '\"COMPLETE\"')" + timestamp +
                ' WHERE project_id = %s', (project,),
            )
    finally:
        continue_read.set()
        worker.join(5)
    assert finished.is_set() and 'error' not in result, result
    with get_connection() as connection:
        stored = connection.execute(
            'SELECT statuses FROM engineering_workflow_projects WHERE project_id = %s', (project,),
        ).fetchone()['statuses']
    assert stored['capacity_timing'] == 'COMPLETE'
    # The read must leave the entire newer row untouched, even when its source
    # status still needs reconciliation. The next uncontended read can do that.
    assert stored['parameters'] == 'IN_PROGRESS'


def test_uncontended_status_read_still_persists_verified_source_statuses():
    project = project_with_default_artifacts(stale_parameters=True)
    result = WorkflowStatusService(project).get(summary=True)
    with get_connection() as connection:
        stored = connection.execute(
            'SELECT statuses FROM engineering_workflow_projects WHERE project_id = %s', (project,),
        ).fetchone()['statuses']
    assert result['statuses']['parameters'] == stored['parameters'] == 'APPROVED'


def test_large_workflow_details_remain_available_with_revision_tokens_under_the_status_budget():
    from backend.app import create_app
    from backend.engineering.workflow.service import edit_token

    project = project_with_default_artifacts()
    parameters = {'networks': [], 'description': 'p' * 900_000}
    topology = {'nodes': [], 'edges': [], 'scene': {'description': 't' * 1_200_000}}
    with get_connection() as connection:
        connection.execute(
            'UPDATE engineering_workflow_projects SET parameters = %s::jsonb, topology = %s::jsonb '
            'WHERE project_id = %s', (json.dumps(parameters), json.dumps(topology), project),
        )
    client = create_app(testing=True).test_client()
    headers = {'X-Project-ID': project}
    # The limit is retained. Editors now load the resources from their detail APIs.
    assert client.get('/api/engineering/workflow', headers=headers).status_code == 413
    response = client.get('/api/engineering/workflow?view=summary', headers=headers)
    assert response.status_code == 200
    assert len(response.data) < 512_000
    state = response.get_json()
    assert state['topology'] == state['parameters'] == {}
    for key, expected in [('parameters', parameters), ('topology', topology)]:
        response = client.get(f'/api/engineering/workflow/{key}', headers=headers)
        assert response.status_code == 200
        resource = response.get_json()
        assert resource[key] == expected
        assert resource['project_id'] == project
        assert resource['versions'] == state['versions']
        assert resource['edit_token'] == state['edit_tokens'][key] == edit_token(expected)


def test_editor_detail_and_metadata_reads_do_not_wait_for_an_active_project_writer():
    from backend.app import create_app

    project = project_with_default_artifacts()
    app = create_app(testing=True)
    done = threading.Event()
    responses = []
    errors = []

    def read():
        try:
            client = app.test_client()
            for path in ('parameters', 'topology', 'snapshots', '?view=summary'):
                suffix = path if path.startswith('?') else '/' + path
                response = client.get('/api/engineering/workflow' + suffix, headers={'X-Project-ID': project})
                responses.append((path, response.status_code))
        except Exception as error:
            errors.append(error)
        finally:
            done.set()

    worker = threading.Thread(target=read, daemon=True)
    try:
        with get_connection() as writer:
            writer.execute('UPDATE engineering_workflow_projects SET updated_at = now() WHERE project_id = %s', (project,))
            worker.start()
            assert done.wait(5), 'Editor resource or snapshot GET waited for an uncommitted project writer.'
            assert not errors
            assert len(responses) == 4 and all(status == 200 for _, status in responses), responses
    finally:
        worker.join(5)
    assert not worker.is_alive()
