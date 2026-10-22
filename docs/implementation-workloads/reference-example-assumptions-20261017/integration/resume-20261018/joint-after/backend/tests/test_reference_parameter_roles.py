"""Proof flags stay unknown; configuration booleans remain editable scenarios."""
import pytest

from backend.nis.communication.catalog import parameter_value_role
from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry


@pytest.mark.parametrize('ending', ['confirmed', 'verified', 'proven', 'validated'])
@pytest.mark.parametrize('spec', [{'type': 'boolean'}, {'boolean': True}])
def test_proof_booleans_are_evidence(ending, spec):
    assert parameter_value_role('example_' + ending, spec) == 'EVIDENCE'


@pytest.mark.parametrize('name', ['lin_diode_present', 'lin_tx_enabled', 'lin_flow_control'])
def test_real_lin_configuration_booleans_remain_configuration(name):
    assert registry.parameter_roles('lin')[name] == 'CONFIGURATION'


@pytest.mark.parametrize('name', ['lin_capacity_confirmed', 'lin_schedule_confirmed'])
def test_real_lin_proof_flags_have_no_generated_simulation_confirmation(name):
    assert registry.parameter_roles('lin')[name] == 'EVIDENCE'
    field = next(row for row in registry.parameter_fields('lin') if row['native_key'] == name)
    assert field['value_role'] == 'EVIDENCE'
    assert field['simulation_default'] is None
    assert field['simulation_default_provenance']['status'] == 'UNKNOWN'
    assert field['simulation_default_provenance']['hardware_evidence'] is False


@pytest.mark.parametrize('role', ['CONFIGURATION', 'REFERENCE', 'EVIDENCE'])
def test_explicit_profile_role_remains_authoritative(role):
    assert parameter_value_role('example_confirmed', {'type': 'boolean', 'value_role': role}) == role


def test_non_boolean_names_are_not_reinterpreted_as_proof_flags():
    assert parameter_value_role('example_confirmed', {'type': 'text'}) == 'CONFIGURATION'
    assert parameter_value_role('example_verified', {'type': 'number'}) == 'CONFIGURATION'
    assert parameter_value_role('example_proven', {'options': ['one', 'two']}) == 'CONFIGURATION'
