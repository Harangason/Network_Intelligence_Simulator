"""Original report inputs and negative scope checks for R01/R02."""
import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.agent_core.orchestration.project_intake import is_project_request, project_intake_text
from backend.engineering.agent_tools import capabilities, project_draft
from backend.engineering.agent_tools.inventory_details import details


PROMPTS = json.loads((Path(__file__).resolve().parents[2] /
                     'tests/fixtures/industry60-intake-regressions.json').read_text(encoding='utf-8'))


def test_meta_typing_request_is_not_converted_into_a_project_draft():
    prompt = (
        'Klassifiziere die Eingaben: Verbinde ParkAssist mit DriverAssistance.; '
        'Prüfe MotorRPM.; Analysiere den letzten Trace.; '
        'Erzeuge eine Architektur für 3 Sensoren, 4 Aktoren und einen Rechner.'
    )
    assert is_project_request(prompt) is False


def test_direct_hardware_brief_remains_a_project_request():
    assert is_project_request(
        'Erzeuge eine Architektur für 3 Sensoren, 4 Aktoren und einen Rechner.'
    ) is True


def test_mixed_inventory_summary_uses_every_actual_device():
    draft = project_draft.parse_requirement(PROMPTS['S01-A'])
    assert len(draft['devices']) == 8
    text = project_intake_text(PROMPTS['S01-A'], draft['devices'])
    summary = text.split('Geräte im Entwurf:')[1]
    assert all(device['name'] in summary for device in draft['devices'])
    assert 'respary' not in text and '→' not in text
    assert 'Steuerfunktion' not in summary


def test_ethercat_assignment_from_original_requirement():
    draft = project_draft.parse_requirement(PROMPTS['S12-A'])
    drives = [d for d in draft['devices'] if d['role'] == 'ACTUATOR']
    assert len(drives) == 10
    assert all(d['technology'] == 'EtherCAT' for d in drives)
    assert all('EtherCAT für Drives' in d['source'] for d in drives)
    assert not [i for i in draft['issues'] if i['code'] == 'CONNECTION_REQUIRED'
                and i.get('device') in {d['name'] for d in drives}]
    # Fifteen unspecified sensors cannot be arbitrarily split into fast/simple.
    assert all(d['technology'] is None for d in draft['devices'] if d['role'] == 'SENSOR')
    assert draft['industry'] is None


@pytest.mark.parametrize('assignment', [
    'EtherCAT für Drives und schnelle Positionssensoren',
    'EtherCAT fuer Drives', 'EtherCAT for Drives', 'Drives: EtherCAT',
])
def test_named_drive_family_only(assignment):
    groups = details('2 Motor Drives\n3 Drucksensoren\n\nKommunikation:\n- ' + assignment)
    assert groups[0]['technology'] == 'EtherCAT'
    assert groups[1]['technology'] is None


@pytest.mark.parametrize('assignment', [
    'EtherCAT oder CAN-FD für Drives',
    'EtherCAT für Drives\n- CAN-FD für Drives',
    'kein EtherCAT für Drives',
    'EtherCAT für schnelle Drives',
])
def test_alternatives_negation_and_unmatched_qualifiers_stay_open(assignment):
    groups = details('2 Motor Drives\n\nKommunikation:\n- ' + assignment)
    assert groups[0]['technology'] is None


def test_conflicting_inline_and_separate_assignment_remain_visible():
    group = details('2 Motor Drives über CAN-FD\n\nKommunikation:\n- EtherCAT für Drives')[0]
    assert group['technology'] is None
    assert set(group['connection_candidates']) == {'EtherCAT', 'CAN_FD'}


def test_persisted_draft_and_reply_share_inventory(monkeypatch):
    monkeypatch.setattr(capabilities, 'catalog', lambda _: {'capabilities': [{
        'available': True, 'action': {'type': 'CAPABILITY', 'capability_id': 'project'},
    }]})
    first = capabilities.prepare_project_request({'requirement': PROMPTS['S12-A'], 'operation_id': uuid4().hex})
    draft = project_draft.inspect()
    drives = [d for d in draft['devices'] if d['role'] == 'ACTUATOR']
    assert len(drives) == 10 and all(d['technology'] == 'EtherCAT' for d in drives)
    assert first['agent_response']['metadata']['draft_revision'] == draft['revision']
    second = capabilities.prepare_project_request({'requirement': 'Zusätzlich 2 Drucksensoren.',
                                                   'revision': draft['revision'], 'operation_id': uuid4().hex})
    persisted = project_draft.inspect()
    summary = second['agent_response']['text'].split('Geräte im Entwurf:')[1]
    assert all(d['name'] in summary for d in persisted['devices'])
