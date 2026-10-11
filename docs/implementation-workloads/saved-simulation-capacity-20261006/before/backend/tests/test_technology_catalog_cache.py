"""A complete revision-bound catalog remains immutable and updates on onboarding."""
from copy import deepcopy
import json

import pytest

from backend.nis.simulation import service as module
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
from backend.nis.communication.registry import TechnologyRegistry


@pytest.fixture
def catalog_case(monkeypatch):
    registry = TechnologyRegistry()
    registry.register_defaults([DEFAULT_TECHNOLOGY_REGISTRY.profile('can')])
    monkeypatch.setattr(module, 'COMMUNICATION_TECHNOLOGY_REGISTRY', registry)
    service = module.SimulationService()
    calls = []
    build = service._build_catalog
    def counted():
        calls.append(registry.revision)
        return build()
    monkeypatch.setattr(service, '_build_catalog', counted)
    return service, registry, calls


def generated(label='Generated Test Bus'):
    return {**DEFAULT_TECHNOLOGY_REGISTRY.profile('can'), 'id': 'generated_test_bus',
            'label': label, 'aliases': [], 'default_stack': ['generated_test_bus'],
            'domain': 'custom', 'knowledge_origin': 'GENERATED_TECHNOLOGY_PACK'}


def profiles(catalog):
    return {p['id']: p for d in catalog['domains'] for p in d['technologies']}


def test_complete_http_bytes_are_reused_but_mutable_callers_are_detached(catalog_case):
    service, registry, calls = catalog_case
    original = service.catalog_json()
    first = service.catalog()
    assert first == json.loads(original)
    profiles(first)['can']['parameter_schema'].clear()
    first['technology_count'] = 35
    assert service.catalog_json() is original
    assert service.catalog()['technology_count'] == 1
    assert profiles(service.catalog())['can']['parameter_schema']
    assert len(calls) == 1


def test_onboarding_and_generated_update_replace_the_whole_cached_revision(catalog_case):
    service, registry, calls = catalog_case
    initial = service.catalog_json()
    registry.register_generated_profile(generated())
    new = service.catalog_json()
    assert new != initial
    assert json.loads(new)['technology_count'] == 2
    registry.register_generated_profile(generated('Updated Generated Test Bus'))
    assert profiles(service.catalog())['generated_test_bus']['label'] == 'Updated Generated Test Bus'
    assert len(calls) == 3
    # An unsuccessful import cannot publish a half-updated registry snapshot.
    before = service.catalog_json()
    with pytest.raises(ValueError, match='alias'):
        registry.register_generated_profile({**generated(), 'aliases': ['CAN']})
    assert service.catalog_json() == before
    assert profiles(service.catalog())['generated_test_bus']['label'] == 'Updated Generated Test Bus'


@pytest.mark.parametrize('method', ['register_binding', 'register_generator', 'register_validator',
    'register_encoder', 'register_decoder', 'register_load_calculator', 'register_timing_model'])
def test_executable_component_change_invalidates_the_catalog_revision(catalog_case, method):
    service, registry, calls = catalog_case
    service.catalog_json()
    previous = registry.revision
    getattr(registry, method)('can', object())
    assert registry.revision > previous
    service.catalog_json()
    assert len(calls) == 2


def test_i2c_device_editor_standard_mode_is_only_a_sourced_review_proposal():
    profile = DEFAULT_TECHNOLOGY_REGISTRY.profile('i2c')
    local = {f['key']: f for f in profile['local_timing_schema']}
    assert local['i2c_mode']['default'] == 'STANDARD'
    assert local['i2c_mode']['default_status'] == 'PROPOSED'
    assert 'UM10204' in local['i2c_mode']['source_revision']
    assert 'default' not in local['slave_address']
    assert 'default' not in local['master_node_id']
    assert 'default' not in local['clock_stretch_limit_us']
    supplied = {'local_timing_evidence': {'i2c_mode': 'STANDARD', 'bitrate_bps': 100000, 'confirmed': False}}
    before = deepcopy(supplied)
    validation = DEFAULT_TECHNOLOGY_REGISTRY.validate_parameters('i2c', supplied)
    assert validation['status'] != 'VALID'
    assert supplied == before
