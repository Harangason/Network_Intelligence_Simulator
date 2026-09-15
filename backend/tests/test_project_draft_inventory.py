from uuid import uuid4
import pytest

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import project_draft, proposal_service
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.repository import list_objects


@pytest.mark.parametrize('text, industry', [
    ('Raspberry Pi für Gebäudeautomation, kein Auto, drei Temperatursensoren', 'building_automation'),
    ('Raspberry Pi für Industrial Automation mit drei Sensoren', 'industrial_automation'),
    ('Ein Fahrzeugprojekt mit Raspberry Pi und drei Sensoren', 'automotive'),
    ('Raspberry Pi, nicht Automotive, sondern Embedded Systems, drei Sensoren', 'embedded_systems'),
])
def test_explicit_application_wins_over_controller_family(text, industry):
    draft = project_draft.parse_requirement(text)
    assert draft['industry'] == industry
    assert len(draft['devices']) == 4
    assert all(d['technology'] is None for d in draft['devices'])


@pytest.mark.parametrize('text', [
    'Kein Raspberry Pi, drei Temperatursensoren.',
    'Ohne Raspi und drei Temperatursensoren.',
    'Nicht Controller namens "Pi", sondern drei Temperatursensoren.',
])
def test_excluded_controller_does_not_resolve_missing_owner(text):
    draft = project_draft.parse_requirement(text)
    assert len(draft['devices']) == 3
    assert all(d['role'] == 'SENSOR' for d in draft['devices'])
    assert any(i['code'] == 'CONTROLLER_REQUIRED' for i in draft['issues'])


def test_competing_industries_require_a_decision_even_with_raspberry_pi():
    draft = project_draft.parse_requirement('Raspberry Pi für Gebäudeautomation oder Automotive, drei Sensoren')
    assert draft['industry'] is None
    assert any(i['code'] == 'INDUSTRY_REQUIRED' for i in draft['issues'])
    confirmed = project_draft.parse_requirement('Raspberry Pi für Gebäudeautomation oder Automotive, drei Sensoren', 'building_automation')
    assert confirmed['industry'] == 'building_automation'


def test_ambiguous_amendment_does_not_silently_keep_previous_industry():
    authority = ToolAuthority('draft-domain-conflict-' + uuid4().hex)
    def send(data):
        result = execute(authority, 'draft', Permission.GENERATE_PROPOSAL, data, project_draft.command)
        assert result.success, result.findings
        return result.data['draft']
    first = send({'action': 'CREATE', 'operation_id': uuid4().hex, 'requirement': 'Raspberry Pi und drei Sensoren'})
    assert first['industry'] == 'embedded_systems'
    updated = send({'action': 'AMEND', 'operation_id': uuid4().hex, 'revision': 1,
                    'requirement': 'Gebäudeautomation oder Automotive steht noch zur Auswahl.'})
    assert updated['industry'] is None
    assert updated['draft_id'] == first['draft_id']
    assert any(i['code'] == 'INDUSTRY_REQUIRED' for i in updated['issues'])


def test_clearing_confirmed_purpose_and_industry_reopens_the_decisions():
    authority = ToolAuthority('draft-clear-' + uuid4().hex)
    def send(data):
        result = execute(authority, 'draft', Permission.GENERATE_PROPOSAL, data, project_draft.command)
        assert result.success, result.findings
        return result.data['draft']
    first = send({'action': 'CREATE', 'operation_id': uuid4().hex, 'requirement': 'Raspberry Pi und drei Sensoren'})
    sensor = next(d for d in first['devices'] if d['role'] == 'SENSOR')
    resolved = send({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 1,
        'devices': [{'device_id': sensor['id'], 'purpose': 'Raumtemperatur messen'}]})
    assert next(d for d in resolved['devices'] if d['id'] == sensor['id'])['known_kind']
    cleared = send({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 2, 'industry': None,
        'devices': [{'device_id': sensor['id'], 'purpose': None}]})
    assert cleared['industry'] is None
    assert not next(d for d in cleared['devices'] if d['id'] == sensor['id'])['known_kind']
    assert any(i['code'] == 'DEVICE_KIND_REQUIRED' and i.get('device_id') == sensor['id'] for i in cleared['issues'])


def test_schema_migration_keeps_revision_and_unknown_versions_are_not_overwritten():
    from backend.engineering.agent_tools import conversation
    authority = ToolAuthority('draft-schema-' + uuid4().hex)
    def run(handler, data=None):
        return execute(authority, 'schema-test', Permission.GENERATE_PROPOSAL, data or {}, handler)
    created = run(project_draft.command, {'action': 'CREATE', 'operation_id': uuid4().hex,
                                        'requirement': 'Raspberry Pi und drei Temperatursensoren'})
    assert created.success
    def old_schema(_):
        state = conversation.read()
        state['engineering_draft']['schema_version'] = 1
        state['engineering_draft'].pop('removed_device_ids')
        conversation.write(state)
    assert run(old_schema).success
    migrated = run(project_draft.inspect)
    assert migrated.success and migrated.data['schema_version'] == 2
    assert migrated.data['revision'] == 1
    assert migrated.data['draft_id'] == created.data['draft']['draft_id']
    assert migrated.data['devices'] == created.data['draft']['devices']
    def future_schema(_):
        state = conversation.read()
        state['engineering_draft']['schema_version'] = 999
        conversation.write(state)
    assert run(future_schema).success
    assert not run(project_draft.inspect).success
    assert not run(project_draft.command, {'action': 'AMEND', 'operation_id': uuid4().hex, 'revision': 1,
                                          'requirement': 'Zwei Ventile zusätzlich.'}).success
    assert run(lambda _: conversation.read()['engineering_draft']).data['schema_version'] == 999


def test_mixed_explicit_sensor_kinds_are_not_replaced_by_generic_templates():
    draft = project_draft.parse_requirement('SPS namens "Regler", zwei Temperatursensoren, drei Drucksensoren und ein Feuchtigkeitssensor', 'building')
    assert draft['declared_counts']['SENSOR'] == 6
    assert len(draft['devices']) == 7
    assert {d['name'] for d in draft['devices']} == {'Regler', 'Temperatursensor1', 'Temperatursensor2',
                                                   'Drucksensor1', 'Drucksensor2', 'Drucksensor3', 'Feuchtigkeitssensor1'}
    assert all(d['technology'] is None for d in draft['devices'])
    assert draft['industry'] == 'building'


def test_explicit_removal_survives_amend_and_clears_owner_atomically():
    authority = ToolAuthority('draft-removal-' + uuid4().hex)
    def send(data):
        result = execute(authority, 'draft', Permission.GENERATE_PROPOSAL, data, project_draft.command)
        assert result.success, result.findings
        return result.data['draft']
    first = send({'action': 'CREATE', 'operation_id': uuid4().hex, 'requirement': 'Raspberry Pi und drei Temperatursensoren'})
    owner = next(d for d in first['devices'] if d['role'] == 'CONTROLLER')
    sensor = next(d for d in first['devices'] if d['role'] == 'SENSOR')
    send({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 1,
          'devices': [{'device_id': sensor['id'], 'owner_id': owner['id']}]})
    removed = send({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 2, 'remove_device_ids': [owner['id']]})
    assert len(removed['devices']) == 3
    assert all(not d.get('owner_id') for d in removed['devices'])
    assert any(i['code'] == 'CONTROLLER_REQUIRED' for i in removed['issues'])
    amended = send({'action': 'AMEND', 'operation_id': uuid4().hex, 'revision': 3, 'requirement': 'Zwei Drucksensoren zusätzlich.'})
    assert len(amended['devices']) == 5
    assert all(d['role'] == 'SENSOR' for d in amended['devices'])
    empty = send({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 4,
                  'remove_device_ids': [d['id'] for d in amended['devices']]})
    assert any(i['code'] == 'INVENTORY_REQUIRED' for i in empty['issues'])


def test_gateway_can_own_local_sensors_without_invented_ecu():
    authority = ToolAuthority('draft-gateway-' + uuid4().hex)
    def call(data, handler):
        result = execute(authority, 'gateway-draft', Permission.GENERATE_PROPOSAL, data, handler)
        if not result.success:
            print(result.findings)
        assert result.success, result.findings
        return result.data
    draft = call({'action': 'CREATE', 'operation_id': uuid4().hex, 'industry': 'building',
                  'requirement': 'Gateway namens "Raumregler" und drei Temperatursensoren'}, project_draft.command)['draft']
    owner = next(d for d in draft['devices'] if d['role'] == 'GATEWAY')
    draft = call({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 1, 'allow_simulation_defaults': True,
                  'devices': [{'device_id': d['id'], 'technology': 'ethernet',
                               **({'owner_id': owner['id']} if d['role'] == 'SENSOR' else {})} for d in draft['devices']]}, project_draft.command)['draft']
    proposal = call({'draft_id': draft['draft_id'], 'revision': 2}, project_draft.plan_model)
    assert proposal['validation_result']['valid'], proposal['validation_result']
    assert sum(c['object_type'] == 'HardwareNode' for c in proposal['changes']) == 4
    call({}, lambda _: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='human', trace_id=uuid4().hex))
    call({}, lambda _: proposal_service.apply(proposal['proposal_id'], actor='human', trace_id=uuid4().hex))
    nodes = call({}, lambda _: list_objects('HardwareNode'))
    assert len(nodes) == 4
    assert next(n for n in nodes if n['name'] == 'Raumregler')['device_type'] == 'Gateway'
