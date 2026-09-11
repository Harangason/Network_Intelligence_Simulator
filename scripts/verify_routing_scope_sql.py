"""Run routing scope and transport regressions in the separate verification DB."""
import os
from urllib.parse import urlsplit, urlunsplit
source = urlsplit(os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://'))
assert source.path != '/nis_bus_naming_tests'
target = urlunsplit(source._replace(path='/nis_bus_naming_tests'))
os.environ['DATABASE_URL'] = os.environ['ENGINEERING_TEST_DATABASE_URL'] = target
import pytest
raise SystemExit(pytest.main(['backend/tests/test_routing_payload_scope.py', 'backend/tests/test_routing.py',
    'backend/tests/test_transport_integrity.py', 'backend/tests/test_workflow.py', '-q', '-p', 'no:cacheprovider', '--tb=short']))
