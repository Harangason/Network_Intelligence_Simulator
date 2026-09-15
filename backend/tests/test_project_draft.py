"""Draft integrity and persistence, using the isolated test database only."""
from uuid import uuid4

from backend.engineering.agent_tools.project_draft import parse_requirement, command, inspect
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.agent_core.api.tool_contract import Permission


def test_real_project_does_not_invent_sensor_kinds_or_transports():
    draft = parse_requirement('Ich möchte ein Projekt mit drei Sensoren.', 'custom')
    assert [d['name'] for d in draft['devices']] == ['Sensor1', 'Sensor2', 'Sensor3']
    assert all(not d['known_kind'] and d['technology'] is None for d in draft['devices'])
    assert any(i['code'] == 'CONTROLLER_REQUIRED' for i in draft['issues'])
    assert sum(i['code'] == 'DEVICE_KIND_REQUIRED' for i in draft['issues']) == 3


def test_inflected_valves_keep_exact_inventory_and_no_automotive():
    draft = parse_requirement('Projekt mit einem Raspberry-Pi, drei Temperatursensoren und zwei Ventilen')
    assert draft['industry'] == 'embedded_systems'
    assert len(draft['devices']) == 6
    assert [d['name'] for d in draft['devices'] if d['role'] == 'ACTUATOR'] == ['Ventilaktor1', 'Ventilaktor2']
    assert all(d['technology'] is None for d in draft['devices'])


def test_unknown_count_is_not_zero_or_a_guessed_quantity():
    draft = parse_requirement('Ein Projekt mit Raspberry Pi und Ventilen')
    assert 'ACTUATOR' not in draft['declared_counts']
    assert any(i['code'] == 'ACTUATOR_COUNT_REQUIRED' for i in draft['issues'])


def test_draft_operation_revision_isolation_and_reload():
    authority = ToolAuthority('draft-' + uuid4().hex)
    operation = {'action': 'CREATE', 'operation_id': uuid4().hex,
                 'requirement': 'Projekt mit drei Temperatursensoren', 'industry': 'embedded_systems'}
    def send(data):
        return execute(authority, 'draft_command', Permission.GENERATE_PROPOSAL, data, command)
    first = send(operation)
    assert first.success
    assert first.data['draft']['revision'] == 1
    assert send(operation).data == first.data
    assert not send({**operation, 'requirement': 'anderer Text'}).success
    amendment = {'action': 'AMEND', 'operation_id': uuid4().hex, 'revision': 1,
                 'requirement': 'Controller namens "RaspberryPi".'}
    updated = send(amendment)
    assert updated.success
    assert updated.data['draft']['revision'] == 2
    assert not any(i['code'] == 'CONTROLLER_REQUIRED' for i in updated.data['draft']['issues'])
    assert not send({**amendment, 'operation_id': uuid4().hex}).success
    loaded = execute(authority, 'draft_read', Permission.READ_MODEL, {}, inspect)
    assert loaded.data == updated.data['draft']
    other = execute(ToolAuthority('draft-' + uuid4().hex), 'draft_read', Permission.READ_MODEL, {}, inspect)
    assert other.data is None


def test_confirmed_connections_survive_amendment_and_invalid_edit_is_atomic():
    authority = ToolAuthority('draft-' + uuid4().hex)
    def send(data):
        return execute(authority, 'draft_command', Permission.GENERATE_PROPOSAL, data, command)
    created = send({'action': 'CREATE', 'operation_id': uuid4().hex,
                    'requirement': 'Raspberry Pi und drei Temperatursensoren'})
    assert created.success
    devices = created.data['draft']['devices']
    controller = next(d for d in devices if d['role'] == 'CONTROLLER')
    sensor = next(d for d in devices if d['role'] == 'SENSOR')
    resolved = send({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 1,
                     'devices': [{'device_id': sensor['id'], 'owner_id': controller['id'], 'technology': 'ethernet'}]})
    assert resolved.success
    amended = send({'action': 'AMEND', 'operation_id': uuid4().hex, 'revision': 2,
                    'requirement': 'Zusätzlich zwei Ventile.'})
    assert amended.success
    preserved = next(d for d in amended.data['draft']['devices'] if d['id'] == sensor['id'])
    assert preserved['owner_id'] == controller['id']
    assert preserved['technology'] == 'ethernet'
    assert amended.data['draft']['original_requirement'] == 'Raspberry Pi und drei Temperatursensoren'
    bad = send({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 3,
                'devices': [{'device_id': sensor['id'], 'name': '   '}]})
    assert not bad.success
    loaded = execute(authority, 'draft_read', Permission.READ_MODEL, {}, inspect)
    assert loaded.data == amended.data['draft']


def test_project_creation_is_explicit_idempotent_and_preserves_origin():
    from backend.engineering.agent_tools import project_creation
    authority = ToolAuthority('origin-' + uuid4().hex)
    created = execute(authority, 'draft', Permission.GENERATE_PROPOSAL,
                      {'action': 'CREATE', 'operation_id': uuid4().hex, 'requirement': 'Raspberry Pi und drei Temperatursensoren'}, command)
    assert created.success
    draft = created.data['draft']
    request = {'operation_id': uuid4().hex, 'draft_id': draft['draft_id'], 'revision': 1, 'name': 'Temperaturregelung'}
    def create(data):
        return execute(authority, 'new_project', Permission.GENERATE_PROPOSAL, data, project_creation.create)
    result = create(request)
    assert result.success, result.findings
    assert result.data['project_id'] != authority.project_id
    assert create(request).data == result.data
    assert not create({**request, 'name': 'Anderes Projekt'}).success
    original = execute(authority, 'draft_read', Permission.READ_MODEL, {}, inspect)
    assert original.data == draft
    target = execute(ToolAuthority(result.data['project_id']), 'draft_read', Permission.READ_MODEL, {}, inspect)
    assert target.data['origin']['project_id'] == authority.project_id
    assert target.data['devices'] == draft['devices']
    assert target.data['draft_id'] != draft['draft_id']
    from backend.engineering.agent_tools.capabilities import catalog
    target_catalog = execute(ToolAuthority(result.data['project_id']), 'catalog', Permission.READ_MODEL, {}, catalog)
    assert target_catalog.success, target_catalog.findings
    assert target_catalog.data['project_name'] == request['name']


def test_model_proposal_has_real_apply_and_stale_draft_cannot_be_approved():
    from backend.engineering.agent_tools.project_draft import plan_model
    from backend.engineering.agent_tools import proposal_service
    from backend.engineering.repository import list_objects
    authority = ToolAuthority('model-' + uuid4().hex)
    def call(name, arguments, handler):
        return execute(authority, name, Permission.GENERATE_PROPOSAL, arguments, handler)
    created = call('draft', {'action': 'CREATE', 'operation_id': uuid4().hex,
                           'requirement': 'Raspberry Pi, drei Temperatursensoren und zwei Ventile'}, command)
    draft = created.data['draft']
    controller = next(d for d in draft['devices'] if d['role'] == 'CONTROLLER')
    resolved = call('resolve', {'action': 'RESOLVE', 'revision': 1, 'operation_id': uuid4().hex,
                               'allow_simulation_defaults': True,
                               'devices': [{'device_id': d['id'], 'technology': 'ethernet',
                                            **({'command': {'length_bits': 1, 'data_type': 'boolean', 'factor': 1,
                                                            'unit': 'code', 'min_value': 0, 'max_value': 1,
                                                            'semantic': {'semantic_type': 'BOOLEAN'},
                                                            'data': {'enum_values': {'CLOSE': 0, 'OPEN': 1}}}} if d['role'] == 'ACTUATOR' else {}),
                                            **({'owner_id': controller['id']} if d['role'] != 'CONTROLLER' else {})}
                                           for d in draft['devices']]}, command)
    assert resolved.success, resolved.findings
    inputs = {'draft_id': draft['draft_id'], 'revision': 2}
    planned = call('plan', inputs, plan_model)
    assert planned.success, planned.findings
    assert planned.data['validation_result']['valid'], {'validation': planned.data['validation_result'], 'messages': [c for c in planned.data['changes'] if c['object_type'] == 'Message']}
    assert sum(c['object_type'] == 'HardwareNode' for c in planned.data['changes']) == 6
    assert call('plan', inputs, plan_model).data['proposal_id'] == planned.data['proposal_id']
    changed = call('amend', {'action': 'AMEND', 'revision': 2, 'operation_id': uuid4().hex,
                            'requirement': 'Die Messwerte bleiben lokal.'}, command)
    assert changed.success
    old = planned.data
    assert call('get', {}, lambda _: proposal_service.get(old['proposal_id'])).data['status'] == 'OUTDATED'
    rejected = call('review', {}, lambda _: proposal_service.review(old['proposal_id'], revision=old['revision'], decision='approve', actor='test-human', trace_id=uuid4().hex))
    assert not rejected.success
    fresh = call('plan', {**inputs, 'revision': 3}, plan_model)
    assert fresh.success
    proposal = fresh.data
    approved = call('review', {}, lambda _: proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='test-human', trace_id=uuid4().hex))
    assert approved.success
    applied = call('apply', {}, lambda _: proposal_service.apply(proposal['proposal_id'], actor='test-human', trace_id=uuid4().hex))
    assert applied.success, applied.findings
    assert applied.data['status'] == 'APPLIED'
    assert call('amend', {'action': 'AMEND', 'revision': 3, 'operation_id': uuid4().hex,
                         'requirement': 'Weitere spätere Prüfung der Regelungsaufgabe.'}, command).success
    replay = call('apply', {}, lambda _: proposal_service.apply(proposal['proposal_id'], actor='test-human', trace_id=uuid4().hex))
    assert replay.success
    assert replay.data['canonical_ids'] == applied.data['canonical_ids']
    inventory = call('read', {}, lambda _: list_objects('HardwareNode', limit=100))
    assert sorted(d['name'] for d in inventory.data) == sorted(['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Ventilaktor1', 'Ventilaktor2'])
