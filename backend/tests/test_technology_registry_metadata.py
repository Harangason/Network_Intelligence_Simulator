"""Registry identity is enumerable; registration cannot stand in for evidence."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.nis.app import create_app
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as REGISTRY
from backend.nis.communication.registry import TechnologyRegistry


def definition(label, **extra):
    return {"label": label, "layer": "DATA_LINK", "implementation_status": "PLANNED",
            "rate_model": {"fields": []}, **extra}


def validation_registry():
    registry = TechnologyRegistry()
    registry.register_defaults([definition('Session Bus', id='session_bus',
        parameter_schema={'flag': {'type': 'boolean', 'default': False}})])
    return registry


def test_native_validation_session_preserves_results_and_does_not_escape_calculation(monkeypatch):
    registry = validation_registry()
    original = registry._validate_parameters
    calls = []
    def observed(technology, values):
        calls.append((technology, deepcopy(values)))
        return original(technology, values)
    monkeypatch.setattr(registry, '_validate_parameters', observed)
    expected = registry.validate_parameters('session_bus', {'flag': True})
    assert expected['status'] == 'VALID'
    with registry.parameter_validation_session():
        for _ in range(25):
            actual = registry.validate_parameters('session_bus', {'flag': True})
            assert actual == expected
            actual['findings'].append({'code': 'CALLER_MUTATION'})
        invalid = registry.validate_parameters('session_bus', {'flag': 'true'})
        assert invalid['status'] == 'INVALID'
        assert registry.validate_parameters('session_bus', {'flag': 'true'}) == invalid
    assert len(calls) == 3
    registry.validate_parameters('session_bus', {'flag': True})
    assert len(calls) == 4
    with pytest.raises(RuntimeError), registry.parameter_validation_session():
        registry.validate_parameters('session_bus', {'flag': True})
        raise RuntimeError('calculation aborted')
    registry.validate_parameters('session_bus', {'flag': True})
    assert len(calls) == 6


def test_native_validation_session_separates_input_types_technologies_and_registry_revisions(monkeypatch):
    registry = validation_registry()
    registry.register_defaults([definition('Other Session Bus', id='other_session_bus',
        parameter_schema={'flag': {'type': 'number', 'default': 0}})])
    original = registry._validate_parameters
    calls = []
    def observed(technology, values):
        calls.append((technology, deepcopy(values)))
        return original(technology, values)
    monkeypatch.setattr(registry, '_validate_parameters', observed)
    with registry.parameter_validation_session():
        assert registry.validate_parameters('session_bus', {'flag': True})['status'] == 'VALID'
        assert registry.validate_parameters('session_bus', {'flag': 1})['status'] == 'INVALID'
        assert registry.validate_parameters('other_session_bus', {'flag': 1})['status'] == 'VALID'
        assert registry.validate_parameters('session_bus', {'flag': True})['status'] == 'VALID'
        registry.register_defaults([definition('Revision Bus', id='revision_bus')])
        assert registry.validate_parameters('session_bus', {'flag': True})['status'] == 'VALID'
    assert len(calls) == 4


def test_custom_validator_is_never_skipped_even_with_identical_parameter_inputs():
    registry = validation_registry()
    calls = []
    class ExternalEvidenceValidator:
        def validate(self, payload):
            calls.append(payload)
            return [] if len(calls) == 1 else [SimpleNamespace(stage='EXTERNAL_EVIDENCE',
                code='EVIDENCE_EXPIRED', severity='BLOCKER', message='External evidence changed.')]
    registry.register_validator('session_bus', ExternalEvidenceValidator())
    with registry.parameter_validation_session():
        assert registry.validate_parameters('session_bus', {'flag': True})['status'] == 'VALID'
        assert registry.validate_parameters('session_bus', {'flag': True})['status'] == 'INVALID'
    assert len(calls) == 2


def test_native_validation_session_avoids_non_json_coercion_and_nested_session_leakage(monkeypatch):
    registry = validation_registry()
    original = registry._validate_parameters
    calls = []
    def observed(technology, values):
        calls.append(values)
        return original(technology, values)
    monkeypatch.setattr(registry, '_validate_parameters', observed)
    with registry.parameter_validation_session():
        registry.validate_parameters('session_bus', {'flag': True})
        with registry.parameter_validation_session():
            registry.validate_parameters('session_bus', {'flag': True})
        registry.validate_parameters('session_bus', {'flag': True})
        for _ in range(2):
            registry.validate_parameters('session_bus', {'flag': (True,)})
            registry.validate_parameters('session_bus', {'flag': float('nan')})
    assert len(calls) == 6


def test_parameter_key_snapshots_refresh_after_registration_and_generated_update():
    registry = TechnologyRegistry()
    generated = definition('Generated Bus', id='generated_bus',
        knowledge_origin='GENERATED_TECHNOLOGY_PACK', aliases=['GBUS'],
        parameter_schema={'first_feature': {'type': 'boolean', 'default': False}})
    registry.register_generated_profile(generated)
    assert 'first_feature' in registry.parameter_keys()
    local = registry.parameter_keys('GBUS')
    local.clear()
    assert 'first_feature' in registry.parameter_keys('generated_bus')
    registry.register_profile('second_bus', definition('Second Bus',
        parameter_schema={'second_feature': {'type': 'boolean', 'default': True}}))
    assert 'second_feature' in registry.parameter_keys()
    assert 'second_feature' not in registry.parameter_keys('generated_bus')
    registry.register_generated_profile({**generated,
        'parameter_schema': {'replacement_feature': {'type': 'boolean', 'default': True}}})
    assert 'replacement_feature' in registry.parameter_keys('GBUS')
    assert 'first_feature' not in registry.parameter_keys('GBUS')
    assert 'replacement_feature' in registry.parameter_keys()
    assert 'first_feature' not in registry.parameter_keys()


def test_selected_profile_fields_preserve_native_identity_and_nested_isolation():
    for technology in ('lin', 'can_fd', 'ethernet', 'someip'):
        full = REGISTRY.profile(technology)
        selected = REGISTRY.profile(full['aliases'][0], fields=('layer', 'default_stack', 'parameter_schema'))
        assert selected == {name: full[name] for name in ('layer', 'default_stack', 'parameter_schema') if name in full}
        selected['parameter_schema'].clear()
        assert REGISTRY.profile(technology)['parameter_schema'] == full['parameter_schema']
    with pytest.raises(KeyError, match='unknown technology'):
        REGISTRY.profile('unknown_bus', fields=('layer', 'default_stack'))


def test_saved_value_roles_match_ui_metadata_and_refresh_without_cached_defaults():
    for technology in ('lin', 'can_fd', 'ethernet', 'i2c', 'modbus_rtu'):
        expected = {field['native_key']: field['value_role'] for field in REGISTRY.parameter_fields(technology)}
        roles = REGISTRY.parameter_roles(technology)
        assert roles == expected
        roles.clear()
        assert REGISTRY.parameter_roles(technology) == expected
    registry = TechnologyRegistry()
    first = definition('Generated Roles', id='generated_roles', knowledge_origin='GENERATED_TECHNOLOGY_PACK',
                       parameter_schema={'device_source': {'label':'Source', 'type':'text'}})
    registry.register_generated_profile(first)
    assert registry.parameter_roles('generated_roles') == {'device_source':'EVIDENCE'}
    registry.register_generated_profile({**first, 'parameter_schema': {
        'native_rate': {'label':'Rate', 'type':'number', 'value_role':'CONFIGURATION'}}})
    assert registry.parameter_roles('generated_roles') == {'native_rate':'CONFIGURATION'}


def test_transport_owned_keys_match_current_native_schema_and_are_detached():
    for technology in ('lin', 'can_fd', 'ethernet', 'i2c', 'modbus_rtu', 'someip'):
        schema = REGISTRY.profile(technology)['parameter_schema']
        expected = {key for key, spec in schema.items()
                    if spec.get('parameter_origin') in {'TRANSPORT_PROFILE', 'DEVICE_CONFIGURATION'}}
        keys = REGISTRY.transport_parameter_keys(technology)
        assert keys == expected
        keys.clear()
        assert REGISTRY.transport_parameter_keys(technology) == expected
    registry = TechnologyRegistry()
    first = definition('Generated Ingress', id='generated_ingress', knowledge_origin='GENERATED_TECHNOLOGY_PACK',
                       parameter_schema={'native_rate': {'type': 'number', 'parameter_origin': 'TRANSPORT_PROFILE'}})
    registry.register_generated_profile(first)
    assert registry.transport_parameter_keys('generated_ingress') == {'native_rate'}
    registry.register_generated_profile({**first, 'parameter_schema': {
        'device_clock': {'type': 'number', 'parameter_origin': 'DEVICE_CONFIGURATION'},
        'analysis_control': {'type': 'number', 'parameter_origin': 'ANALYSIS'}}})
    assert registry.transport_parameter_keys('generated_ingress') == {'device_clock'}


def test_simulation_constraint_values_match_native_rules_and_keep_fixed_inputs():
    from backend.nis.communication.catalog import _constrained_simulation_proposals, simulation_parameter_values
    profile = REGISTRY.profile('lin')
    values = {key:proposal['value'] for key,proposal in simulation_parameter_values('lin',profile).items()}
    values.update(lin_data_octets=8,lin_frame_nominal_bits=1)
    fixed = set(values)-{'lin_frame_nominal_bits','lin_response_nominal_bits'}
    expected = _constrained_simulation_proposals('lin',profile,
        {key:{'value':value} for key,value in values.items()},fixed)
    actual = REGISTRY.constrain_simulation_values('LIN',values,fixed)
    assert actual=={key:item['value'] for key,item in expected.items()}
    assert actual['lin_frame_nominal_bits']==124
    assert all(actual[key]==values[key] for key in fixed)


def test_simulation_constraint_values_are_detached_and_follow_profile_updates():
    registry = TechnologyRegistry()
    first = definition('Generated Derivation',id='generated_derivation',knowledge_origin='GENERATED_TECHNOLOGY_PACK',
        parameter_schema={'layout':{'type':'text'},'source':{'type':'number'},'derived':{'type':'number'}},
        parameter_constraints=[{'parameter':'derived','equal_parameter':'source'}])
    registry.register_generated_profile(first)
    values={'layout':{'slots':[1]},'source':2,'derived':0}
    actual=registry.constrain_simulation_values('generated_derivation',values,{'layout','source'})
    assert actual['derived']==2
    actual['layout']['slots'].append(3)
    assert values['layout']=={'slots':[1]}
    registry.register_generated_profile({**first,'parameter_constraints':[
        {'parameter':'derived','equal_parameter':'source','equal_parameter_offset':3}]})
    assert registry.constrain_simulation_values('generated_derivation',values,{'layout','source'})['derived']==5
    assert registry.constrain_simulation_values('generated_derivation',values,values)==values


def test_every_profile_exposes_canonical_identity_aliases_and_honest_verification():
    profiles = REGISTRY.list_all()
    assert profiles == REGISTRY.profiles()
    assert len(profiles) == len({p["canonical_id"] for p in profiles})
    assert {p["id"] for p in profiles} == set(REGISTRY._profiles)
    for profile in profiles:
        assert profile["canonical_id"] == profile["id"] == REGISTRY.normalize_id(profile["id"])
        assert profile["display_name"] == profile["label"]
        assert profile["classification"]
        assert isinstance(profile["aliases"], list)
        assert profile["verification_status"] == "UNVERIFIED"
        assert profile["verification_scope"] == "REGISTRY_TEMPLATE"
        assert profile["fallback_allowed"] is False
        for alias in profile["aliases"]:
            assert REGISTRY.profile(alias)["canonical_id"] == profile["id"], (profile["id"], alias)
    assert set(REGISTRY._aliases.values()) <= {p["id"] for p in profiles}


def test_ros_aliases_are_exported_and_can_xl_never_becomes_can_fd():
    assert {"ROS2", "ROS_2", "ros-2"} <= set(REGISTRY.profile("ros2")["aliases"])
    for alias in ("ROS2", "ROS_2", "ros-2", "ROS 2"):
        assert REGISTRY.profile(alias)["id"] == "ros2"
    assert REGISTRY.profile("CANXL")["id"] == "can_xl"
    assert REGISTRY.profile("CANFD")["id"] == "can_fd"
    assert REGISTRY.profile("CANXL")["capacity_evidence"]["status"] == "MODEL_MISSING"
    # A device class must not be translated to a non-existent technology identity.
    assert REGISTRY.normalize_id("SPS") == "sps"
    assert REGISTRY.validate_parameters("SPS", {})["status"] == "UNKNOWN"


@pytest.mark.parametrize("alias", ["First Bus", "first_bus"])
def test_alias_cannot_hijack_an_existing_canonical_profile(alias):
    registry = TechnologyRegistry()
    registry.register_profile("first_bus", definition("First Bus"))
    before = registry.profiles(), deepcopy(registry._aliases)
    with pytest.raises(ValueError, match="alias"):
        registry.register_profile("second_bus", definition("Second Bus", aliases=[alias]))
    assert (registry.profiles(), registry._aliases) == before


def test_alias_cannot_hijack_a_reserved_builtin_identity():
    registry = TechnologyRegistry()
    with pytest.raises(ValueError, match="alias"):
        registry.register_profile("custom_bus", definition("Custom Bus", aliases=["CANFD"]))
    assert registry.profiles() == [] and registry._aliases == {}


def test_description_cannot_assert_project_verification_or_foreign_canonical_id():
    registry = TechnologyRegistry()
    registry.register_profile("custom_bus", definition("Custom Bus", canonical_id="can_fd",
        verification_status="VERIFIED", fallback_allowed=True))
    profile = registry.profile("custom_bus")
    assert profile["canonical_id"] == "custom_bus"
    assert profile["verification_status"] == "UNVERIFIED"
    assert profile["fallback_allowed"] is False
    profile["aliases"].append("mutated")
    assert "mutated" not in registry.profile("custom_bus")["aliases"]


def test_rejected_generated_profile_update_preserves_previous_registration():
    registry = TechnologyRegistry()
    profile = definition("Generated Bus", id="generated_bus", aliases=["GBUS"],
                         knowledge_origin="GENERATED_TECHNOLOGY_PACK")
    registry.register_generated_profile(profile)
    before = registry.profiles(), deepcopy(registry._aliases)
    with pytest.raises(ValueError, match="alias"):
        registry.register_generated_profile({**profile, "aliases": ["CANFD"]})
    assert (registry.profiles(), registry._aliases) == before
    assert registry.profile("GBUS")["id"] == "generated_bus"


def test_generated_profile_update_via_alias_preserves_canonical_identity():
    registry = TechnologyRegistry()
    profile = definition("Generated Bus", id="generated_bus", aliases=["GBUS"],
                         knowledge_origin="GENERATED_TECHNOLOGY_PACK")
    registry.register_generated_profile(profile)
    registry.register_generated_profile({**profile, "id": "GBUS", "aliases": ["SECOND"]})
    assert registry.profile("SECOND")["id"] == "generated_bus"
    assert registry.profile("generated_bus")["canonical_id"] == "generated_bus"
    assert len(registry.profiles()) == 1


def test_http_catalog_preserves_registry_identity_and_verification_metadata():
    response = create_app().test_client().get('/api/technologies')
    assert response.status_code == 200
    catalog = response.get_json()
    exported = {p['id']: p for domain in catalog['domains'] for p in domain['technologies']}
    assert set(exported) == {p['id'] for p in REGISTRY.list_all()}
    for tid, profile in exported.items():
        assert profile['canonical_id'] == tid
        assert profile['verification_status'] == 'UNVERIFIED'
        assert profile['aliases'] == REGISTRY.profile(tid)['aliases']
