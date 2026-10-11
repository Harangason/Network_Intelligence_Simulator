"""Use the separate verification database, never the user project database."""
import os
from urllib.parse import urlsplit, urlunsplit
source = urlsplit(os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://'))
target = urlunsplit(source._replace(path='/nis_bus_naming_tests'))
os.environ['DATABASE_URL'] = os.environ['ENGINEERING_TEST_DATABASE_URL'] = target
assert urlsplit(os.environ['DATABASE_URL']).path == '/nis_bus_naming_tests'
import pytest
code = pytest.main(['backend/tests/test_goal_execution.py', 'backend/tests/test_goal_execution_sql.py',
    'backend/tests/test_engineering_mcp.py', 'backend/tests/test_agent_chat_ux.py', 'backend/tests/test_agent_core.py',
    'backend/tests/test_project_bundle.py', 'backend/tests/test_workflow.py', '-q', '-p', 'no:cacheprovider', '--tb=short'])
from backend.engineering.db import close_pool
close_pool()
raise SystemExit(code)
