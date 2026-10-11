"""Run connection persistence checks in a separate PostgreSQL database."""
import os
import sys
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

sys.path[:0] = ['/app', '/app/backend', '/app/backend/simulator']
url = urlsplit(os.environ['DATABASE_URL'].replace('postgresql+psycopg', 'postgresql'))
database = 'nis_port_attachment_tests'
assert url.path != '/' + database
with psycopg.connect(urlunsplit(url._replace(path='/postgres')), autocommit=True) as connection:
    if not connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', (database,)).fetchone():
        connection.execute('CREATE DATABASE nis_port_attachment_tests')
os.environ['ENGINEERING_TEST_DATABASE_URL'] = urlunsplit(url._replace(path='/' + database))
os.environ['DATABASE_URL'] = os.environ['ENGINEERING_TEST_DATABASE_URL']
raise SystemExit(pytest.main(['backend/tests/test_port_attachment.py', '-q', '-p', 'no:cacheprovider', '--basetemp', '/tmp/pytest-port-attachment']))
