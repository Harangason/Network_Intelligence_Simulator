"""Run assistant/MCP integration tests only in the separate verification database."""
import os
from urllib.parse import urlsplit, urlunsplit

source = urlsplit(os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://'))
target = urlunsplit(source._replace(path='/nis_bus_naming_tests'))
assert source.path != '/nis_bus_naming_tests'
os.environ['DATABASE_URL'] = os.environ['ENGINEERING_TEST_DATABASE_URL'] = target
import pytest
raise SystemExit(pytest.main([
    'backend/tests/test_specialist_execution.py', 'backend/tests/test_communication_repair.py',
    'backend/tests/test_assistant_capabilities.py', 'backend/tests/test_agent_chat_ux.py',
    'backend/tests/test_engineering_mcp.py', 'backend/tests/test_agent_core.py',
    'backend/tests/test_agent_audit_regressions.py', '-q', '-p', 'no:cacheprovider', '--tb=short',
]))
