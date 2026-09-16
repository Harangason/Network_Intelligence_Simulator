"""Source-derived whole-project intent regressions; no SQL or model writes."""
import json
from pathlib import Path

import pytest

from backend.agent_core.orchestration.project_intake import is_project_request


CASES = json.loads((Path(__file__).resolve().parents[2] / 'tests/fixtures/industry40.json').read_text(encoding='utf8'))['cases']


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_full_inventory_is_not_a_single_function_request(case):
    assert is_project_request(case['input'])


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_chat_draft_preserves_full_scope_without_inventing_connections(case):
    from backend.engineering.agent_tools.project_draft import parse_requirement
    draft = parse_requirement(case['input'], 'custom')
    for key, role in [('sensors', 'SENSOR'), ('actuators', 'ACTUATOR'), ('ecus', 'CONTROLLER'), ('gateways', 'GATEWAY')]:
        expected = case['counts'][key]
        if expected is not None:
            assert sum(d['role'] == role for d in draft['devices']) == expected, role
    # Explicit device-local connections must survive; open variants still
    # cannot inherit technologies from unrelated networks or prior projects.
    if case['id'].endswith('-B'):
        assert all(device['technology'] is None for device in draft['devices'])
    for device in draft['devices']:
        if device['technology']:
            assert device['connection_candidates'] == [device['technology']]


@pytest.mark.parametrize('prompt', [
    'Erzeuge 20 Temperatursignale für den ausgewählten Controller.',
    'Wie verbinde ich 3 Sensoren und 4 Aktoren?',
    'Zeige 3 Sensoren und 4 Aktoren.',
    'Lösche 3 Sensoren und 4 Aktoren.',
    'Bitte prüfe 3 Sensoren und 4 Aktoren im bestehenden Modell.',
    'Ändere 3 Sensoren und 4 Aktoren.',
    'Erstelle eine Funktion am Controller.',
    'Strukturierte Vorgaben fuer den Engineering-Agenten: 3 Sensoren, 4 Aktoren',
])
def test_queries_and_single_object_operations_are_not_project_intake(prompt):
    assert not is_project_request(prompt)


def test_industry_neutral_is_not_an_industry_selection():
    from backend.engineering.agent_tools.project_draft import industry_candidates
    assert industry_candidates('Ein industrieneutrales Kommunikationssystem mit CAN-FD und Ethernet') == set()
    assert industry_candidates('Industrial Automation mit Sensoren') == {'industrial_automation'}
