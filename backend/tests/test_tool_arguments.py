import pytest
from backend.agent_core.orchestration.tool_arguments import prepare_arguments

SCHEMA = {'type': 'object', 'required': ['hardware'], 'additionalProperties': False, 'properties': {
    'hardware': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
    'cycle': {'anyOf': [{'type': 'number'}, {'type': 'null'}]},
    'network_id': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
}}

def test_decode_typed_json_without_changing_string_fields_or_inventing_values():
    assert prepare_arguments({'hardware': '{"name":"null"}', 'cycle': 'null'}, SCHEMA) == {
        'hardware': {'name': 'null'}, 'cycle': None}

@pytest.mark.parametrize('arguments', [
    {'hardware': "{'name': 'PLC'}"}, {'hardware': {}, 'network_id': 'null'},
    {'hardware': {}, 'cycle': 'unknown'}, {'hardware': {}, 'unknown': 'field'}, {},
])
def test_invalid_arguments_are_repairable_before_execution(arguments):
    with pytest.raises(ValueError):
        prepare_arguments(arguments, SCHEMA)
