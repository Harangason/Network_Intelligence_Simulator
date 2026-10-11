from uuid import uuid4

from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools.services import TOOLS


def call(authority, name, data):
    definition = TOOLS[name]
    parsed = definition.input_model.model_validate(data).model_dump(mode='json')
    return execute(authority, name, definition.permission, parsed, definition.handler)


def test_model_creation_is_a_real_validated_proposal_not_a_direct_write():
    authority = ToolAuthority('creation-' + uuid4().hex)
    result = call(authority, 'create_objects_via_proposal', {
        'objects': [{'object_type': 'HardwareNode', 'local_ref': 'sensor',
                     'data': {'name': 'Temperaturmessstelle', 'device_type': 'SensorController'}}],
        'rationale': 'Eine ausdrücklich angeforderte Temperaturmessstelle vorbereiten.',
    })
    assert result.success, result.findings
    assert result.data['proposal_id']
    assert result.data['validation_result']
    assert result.data['changes'][0]['data']['name'] == 'Temperaturmessstelle'
    assert call(authority, 'search_model', {'query': 'Temperaturmessstelle'}).data['items'] == []


def test_creation_rejects_hidden_governance_fields_and_mutation_actions():
    authority = ToolAuthority('creation-' + uuid4().hex)
    base = {'object_type': 'HardwareNode', 'data': {'name': 'Temperaturmessstelle', 'device_type': 'SensorController'}}
    for item in [{**base, 'action': 'DELETE'}, {**base, 'data': {**base['data'], 'approval_state': 'APPROVED'}}]:
        result = call(authority, 'create_objects_via_proposal', {'objects': [item], 'rationale': 'Test'})
        assert not result.success
    assert call(authority, 'search_model', {'query': ''}).data['items'] == []


def test_schema_discovery_exposes_real_canonical_fields():
    authority = ToolAuthority('creation-' + uuid4().hex)
    result = call(authority, 'describe_model_object_fields', {'object_type': 'HardwareNode'})
    assert result.success
    assert 'name' in result.data['required']
    assert 'device_type' in result.data['fields']
    assert 'EmbeddedController' in result.data['enum_fields']['device_type']
    assert 'approval_state' not in result.data['fields']
