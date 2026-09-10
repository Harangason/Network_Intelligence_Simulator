"""Run connection persistence checks in a separate PostgreSQL database."""
import os
import sys
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

sys.path[:0] = ['/app', '/app/backend', '/app/backend/simulator']
url = urlsplit(os.environ['DATABASE_URL'].replace('postgresql+psycopg', 'postgresql'))
database = 'nis_bus_naming_tests'
assert url.path != '/' + database
with psycopg.connect(urlunsplit(url._replace(path='/postgres')), autocommit=True) as connection:
    if not connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,)).fetchone():
        connection.execute('CREATE DATABASE nis_bus_naming_tests')
os.environ['ENGINEERING_TEST_DATABASE_URL'] = urlunsplit(url._replace(path='/' + database))
os.environ['DATABASE_URL'] = os.environ['ENGINEERING_TEST_DATABASE_URL']
result = pytest.main(['backend/tests/test_relationship_editing.py', 'backend/tests/test_network_naming.py', 'backend/tests/test_engineering_naming.py', 'backend/tests/test_physical_ports.py', 'backend/tests/test_wizard_generation.py', '-q', '-p', 'no:cacheprovider', '--basetemp', '/tmp/pytest-bus-naming', *sys.argv[1:]])
from backend.engineering.db import close_pool
close_pool()
raise SystemExit(result)
