"""Binding execution validates explicit lower layers without synthesizing them."""
from copy import deepcopy

import pytest

from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies.core.models import TechnologyProfile, TechnologyStack


def bind(stack, model=None):
    return registry.resolve_binding(stack).bind('functional-interface', tuple(stack),
        stack_model=TechnologyStack(tuple(model if model is not None else stack)),
        hardware_interface_ref='physical-port', network_ref='network', parameters={'explicit': True})


@pytest.mark.parametrize('stack', [
    ('ethernet', 'ip', 'udp', 'someip'), ('ethernet', 'ip', 'tcp', 'someip'),
    ('ethernet', 'profinet'), ('can', 'canopen'), ('can_fd',),
])
def test_explicit_supported_stack_is_preserved(stack):
    actual = bind(stack)
    assert actual.stack.technology_ids == stack
    assert actual.parameters == {'explicit': True}
    assert actual.hardware_interface_ref == 'physical-port'


@pytest.mark.parametrize('stack', [
    ('someip',), ('can', 'profinet'), ('ethernet', 'canopen'),
    ('ethernet', 'ip', 'tcp', 'someip_sd'), ('ethernet', 'ip', 'udp', 'udp', 'someip'),
    ('ip', 'ethernet', 'udp', 'someip'),
])
def test_missing_foreign_or_unordered_layers_are_rejected(stack):
    with pytest.raises(ValueError, match='TECHNOLOGY_STACK'):
        bind(stack)


def test_binding_cannot_ignore_contradictory_stack_model():
    with pytest.raises(ValueError, match='TECHNOLOGY_STACK'):
        bind(('ethernet', 'ip', 'udp', 'someip'), ('can',))


def test_aliases_persist_canonical_identity_without_adding_layers():
    actual = bind(('ETHERNET', 'IP', 'UDP', 'SOME/IP'))
    assert actual.stack.technology_ids == ('ethernet', 'ip', 'udp', 'someip')


def test_metadata_inspection_is_separate_from_executable_binding():
    resolved = registry.resolve_stack(('someip',))
    assert resolved['profiles'][0]['id'] == 'someip'
    with pytest.raises(ValueError, match='TECHNOLOGY_STACK'):
        resolved['binding'].bind('function', ('someip',), stack_model=TechnologyStack(('someip',)))


@pytest.mark.parametrize('invalid', [None, [], ['ethernet'], [[]], [['ethernet', 'ethernet']], [['']]])
def test_malformed_stack_metadata_is_rejected(invalid):
    profile = deepcopy(registry.profile('someip'))
    profile['stack_variants'] = invalid
    with pytest.raises(ValueError, match='stack_variants'):
        TechnologyProfile.from_dict(profile)


def test_profile_variants_are_defensive_copies():
    value = registry.profile('someip')
    value['stack_variants'][0].clear()
    assert registry.profile('someip')['stack_variants'][0] == ['ethernet', 'ip', 'udp', 'someip']
