"""Proposed-model routing uses real rules and never falls back to persisted rows."""
from copy import deepcopy
from uuid import uuid4

import pytest

from backend.engineering.routing import validation
from backend.engineering.routing.validation import RoutingValidator
from backend.tests.test_agent_recipient_repair_runtime import sql_seed, scoped


@pytest.fixture
def candidate():
    from backend.engineering.communication_repair import load_plan
    from backend.engineering.communication_contract_repair import scan_signal_recipients
    from backend.engineering.repository import ENTITY_SPECS
    from backend.engineering.agent_tools.model import json_safe
    authority, _ = sql_seed()
    def capture():
        planner, state = load_plan()
        route = scan_signal_recipients(planner, RoutingValidator().validate)['changes'][0]['data']
        snapshot = {'project_id': authority.project_id, 'topology': state['topology'], 'parameters': state['parameters'],
                    'tables': {ENTITY_SPECS[kind].table: rows for kind, rows in planner.objects.items()}}
        snapshot['tables']['engineering_routing_entries'] = planner.routes
        return json_safe({'snapshot': snapshot, 'route': route, 'baseline': RoutingValidator().validate(route)})
    return scoped(authority, capture)


def forbid_database():
    raise AssertionError('A complete proposed model must not read or write a database.')


def test_real_sql_route_and_snapshot_use_identical_validation(candidate, monkeypatch):
    monkeypatch.setattr(validation, 'get_connection', forbid_database)
    snap = candidate['snapshot']; before = deepcopy(snap)
    validator = RoutingValidator(snap['project_id'], model_snapshot=snap)
    observed = validator.validate(candidate['route'])
    assert observed['valid'] is True
    assert {k: v for k, v in observed.items() if k != 'validation_timestamp'} == {
        k: v for k, v in candidate['baseline'].items() if k != 'validation_timestamp'}
    assert snap == before


def test_new_unpersisted_identifiers_are_validated_in_proposed_graph(candidate, monkeypatch):
    monkeypatch.setattr(validation, 'get_connection', forbid_database)
    # Replace every object identity with a new UUID. These rows do not exist in SQL.
    mapping = {str(row['id']): str(uuid4()) for rows in candidate['snapshot']['tables'].values() for row in rows}
    def remap(value):
        if isinstance(value, dict): return {k: remap(v) for k, v in value.items()}
        if isinstance(value, list): return [remap(v) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    snap, route = remap(candidate['snapshot']), remap(candidate['route'])
    result = RoutingValidator(snap['project_id'], model_snapshot=snap).validate(route)
    assert result['valid'], result


@pytest.mark.parametrize('change,code', [
    ('missing-source', 'SOURCE_NOT_FOUND'), ('missing-destination', 'DESTINATION_NOT_FOUND'),
    ('missing-interface', 'SOURCE_INTERFACE_NOT_FOUND'), ('missing-wire', 'PHYSICAL_PATH_REMOVED'),
    ('signal-too-long', 'SIGNAL_EXCEEDS_MESSAGE'), ('loop', 'ROUTING_LOOP'),
    ('duplicate-route', 'DUPLICATE_ROUTE'),
])
def test_invalid_proposed_graph_cannot_be_rescued_by_valid_database(candidate, monkeypatch, change, code):
    monkeypatch.setattr(validation, 'get_connection', forbid_database)
    snap, route = candidate['snapshot'], candidate['route']; tables = snap['tables']
    if change == 'missing-source':
        tables['engineering_hardware_nodes'] = [r for r in tables['engineering_hardware_nodes'] if str(r['id']) != route['source']['node_id']]
    elif change == 'missing-destination':
        tables['engineering_hardware_nodes'] = [r for r in tables['engineering_hardware_nodes'] if str(r['id']) != route['destinations'][0]['node_id']]
    elif change == 'missing-interface':
        tables['engineering_interfaces'] = [r for r in tables['engineering_interfaces'] if str(r['id']) != route['source']['interface_id']]
    elif change == 'missing-wire': snap['topology']['edges'] = []
    elif change == 'signal-too-long':
        next(r for r in tables['engineering_signals'] if str(r['id']) == route['payload']['signal_ids'][0])['length_bits'] = 10000
    elif change == 'loop': route['route']['hops'].append(route['route']['hops'][0])
    elif change == 'duplicate-route':
        tables['engineering_routing_entries'].append({**deepcopy(route), 'id': str(uuid4()), 'route_code': 'DUPLICATE', 'status': 'APPROVED'})
    result = RoutingValidator(snap['project_id'], model_snapshot=snap).validate(route)
    assert result['valid'] is False
    assert code in {f['code'] for f in result['errors']}, result


@pytest.mark.parametrize('change', ['foreign-project', 'foreign-row', 'missing-table', 'duplicate-id', 'invalid-row', 'missing-topology', 'mixed-planner'])
def test_incomplete_or_foreign_snapshot_is_rejected(candidate, monkeypatch, change):
    monkeypatch.setattr(validation, 'get_connection', forbid_database)
    snap = candidate['snapshot']; project = snap['project_id']; options = {}
    if change == 'foreign-project': snap['project_id'] = 'foreign'
    elif change == 'foreign-row': snap['tables']['engineering_hardware_nodes'][0]['project_id'] = 'foreign'
    elif change == 'missing-table': del snap['tables']['engineering_signals']
    elif change == 'duplicate-id': snap['tables']['engineering_hardware_nodes'].append(deepcopy(snap['tables']['engineering_hardware_nodes'][0]))
    elif change == 'invalid-row': snap['tables']['engineering_messages'] = [None]
    elif change == 'missing-topology': del snap['topology']
    elif change == 'mixed-planner': options['physical_planner'] = object()
    with pytest.raises(ValueError): RoutingValidator(project, model_snapshot=snap, **options)


def test_caller_cannot_change_validated_snapshot_after_construction(candidate, monkeypatch):
    monkeypatch.setattr(validation, 'get_connection', forbid_database)
    snap = candidate['snapshot']; validator = RoutingValidator(snap['project_id'], model_snapshot=snap)
    snap['tables']['engineering_hardware_nodes'].clear(); snap['topology']['edges'].clear()
    assert validator.validate(candidate['route'])['valid'] is True
