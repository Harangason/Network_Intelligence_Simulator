"""Native decision order is deliberate; accepted schema language stays strict."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from backend.nis.agent.orchestration import local_reasoner as reasoner
from backend.nis.agent.orchestration import project_intake as intake
from backend.tests.test_reference_port_intent_allocation import prepared_schema
from backend.tests.test_reference_port_group_completion import groups
from backend.tests.test_reference_planning_throughput import existing_batch_fixture


def test_inventory_decisions_precede_questions_without_reordering_identity_bindings():
    _, _, _, _, schema, _ = existing_batch_fixture()
    for node in [schema, *schema.get('anyOf', [])]:
        keys = list(node['properties'])
        assert keys[:2] == ['inventory_choices', 'inventory_complete']
        assert keys[-1] == 'unresolved'
    bindings = [node for name, node in schema['$defs'].items()
                if name.startswith('NativeReferenceBinding_')]
    assert bindings
    for node in bindings:
        assert node['anyOf']
        assert all(len(alternative['properties']) == 1 for alternative in node['anyOf'])


@pytest.mark.parametrize(('allowed', 'options', 'first'), [
    ({'ports'}, {'port_groups': True, 'device_ids': ('owner-a', 'owner-b')}, 'port_groups_by_device'),
    ({'ports'}, {'port_intent': True, 'device_ids': ('owner-a', 'owner-b')}, 'port_intents'),
    ({'ports'}, {'port_ids': ('port-1',)}, 'port_parameters'),
    ({'functions', 'functional_dependencies'}, {'function_ids': ('fact-1',)}, 'functions_by_fact'),
])
def test_private_task_fields_precede_questions_in_every_native_alternative(allowed, options, first):
    prepared, _ = prepared_schema()
    public_before = intake.reference_model_output_schema(prepared)
    schema = reasoner._reference_schema_for_stage(prepared, allowed, **options)
    for node in [schema, *schema.get('anyOf', [])]:
        keys = list(node['properties'])
        assert keys[0] == first
        assert keys[-1] == 'unresolved'
        assert node['properties']['unresolved']
    assert intake.reference_model_output_schema(prepared) == public_before


def test_reordered_complete_and_open_port_branches_keep_all_strict_counterexamples():
    prepared, _ = prepared_schema()
    owners = ('owner-a', 'owner-b')
    schema = reasoner._reference_schema_for_stage(prepared, {'ports'}, port_groups=True, device_ids=owners)
    value = {**intake.ReferenceDesignProposal().model_dump(mode='json'),
             'port_groups_by_device': groups(3, owners), 'port_plan_complete': True}
    check = Draft202012Validator(schema)
    assert check.is_valid(value)
    invalid = deepcopy(value)
    invalid['port_groups_by_device'][owners[1]]['connections'] = []
    assert not check.is_valid(invalid)
    invalid['port_plan_complete'] = False
    assert not check.is_valid(invalid)
    invalid['unresolved'] = [{'code': 'PHY_UNKNOWN', 'target_ref': owners[1],
                              'message': 'The physical source does not specify an external connection.'}]
    assert check.is_valid(invalid)
    invalid['unresolved'][0]['target_ref'] = 'foreign-owner'
    assert not check.is_valid(invalid)
    assert schema['properties']['port_plan_complete'] == {'type': 'boolean'}
