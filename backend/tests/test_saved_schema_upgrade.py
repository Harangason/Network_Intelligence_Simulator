from uuid import uuid4
from backend.engineering.db import get_connection
from backend.engineering.schema import ensure_schema, SCHEMA_VERSION
from backend.engineering.workflow.service import WorkflowStatusService


def test_existing_v26_database_receives_project_deletion_table():
    project = 'upgrade-' + uuid4().hex
    WorkflowStatusService(project).set_context({'engineering_wizard_settings': {'project_name': 'Existing project','model_type':'custom'}})
    with get_connection() as connection:
        # Roll back the complete synthetic downgrade after the upgrade check.
        with connection.transaction(force_rollback=True):
            connection.execute('DROP TABLE engineering_deleted_projects')
            connection.execute('DELETE FROM engineering_schema_migrations WHERE version > 26')
            connection.execute('INSERT INTO engineering_schema_migrations(version) VALUES(26) ON CONFLICT DO NOTHING')
            ensure_schema(connection)
            assert connection.execute("SELECT to_regclass('engineering_deleted_projects') AS table_name").fetchone()['table_name']
            assert connection.execute('SELECT 1 FROM engineering_schema_migrations WHERE version=%s',(SCHEMA_VERSION,)).fetchone()
            row = connection.execute('SELECT context FROM engineering_workflow_projects WHERE project_id=%s',(project,)).fetchone()
            assert row['context']['engineering_wizard_settings']['project_name'] == 'Existing project'
