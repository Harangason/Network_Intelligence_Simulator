"""Independent per-technology checks for the approved complete parameter audit."""
from backend.app.simulation_service import SimulationService
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies.catalog import PARAMETER_UI_ALIASES
from backend.engineering.agent_tools.wizard_generation import _parameter_defaults


def test_http_schema_is_registered_profile_schema_for_every_technology():
    # Detect future API-local definitions that silently replace the canonical schema.
    for profile in registry.profiles():
        expected = [{**spec, 'key': PARAMETER_UI_ALIASES.get(key, key)}
                    for key, spec in profile['parameter_schema'].items() if spec.get('label')]
        assert SimulationService._parameter_schema(profile['id'], profile) == expected
        assert all(field.get('parameter_origin') and field.get('source') for field in expected)


def test_5g_has_no_historical_peak_rate_as_a_standard_default():
    fields = registry.parameter_fields('5g')
    rate = next(field for field in fields if field['key'] == 'bitrate')
    assert 'default' not in rate
    assert registry.parameter_defaults_review('5g')['values'] == {}
    assert 'bitrate' not in _parameter_defaults('5g')
    assert rate['default_review']['source'].startswith('https://www.etsi.org/')
    device = [field for field in fields if field['key'].startswith('nr_')]
    assert len(device) == 9
    assert all(field['parameter_origin'] == 'DEVICE_CONFIGURATION' and 'default' not in field for field in device)
    assert registry.profile('5g')['capacity_evidence']['status'] == 'MODEL_MISSING'
    assert not {'arbitration_bitrate', 'data_bitrate', 'sample_point_percent', 'duplex', 'mtu_bytes', 'vlan_id'} & {field['key'] for field in fields}


def test_5g_general_analysis_controls_are_explicit_nis_scenarios():
    fields = registry.parameter_fields('5g')
    for field in fields:
        if field['parameter_origin'] == 'NIS_SCENARIO':
            assert field['source_revision'] == 'NIS_SCENARIO_POLICY_V1'
            assert not field['required']
            assert field['default_status'] in {'PROPOSED', 'UNKNOWN'}


def test_5g_radio_settings_validate_types_modes_and_counts_without_guessing():
    assert registry.validate_parameters('5g', {'bitrate_bps': 1_000_000, 'nr_carrier_count': 1,
                                             'nr_direction': 'UL', 'nr_scaling_factor': '0.8'})['status'] == 'VALID'
    for name, value in [('nr_carrier_count', 1.5), ('nr_carrier_count', True),
                        ('nr_channel_bandwidth_mhz', 0), ('nr_direction', 'SEND'),
                        ('nr_subcarrier_spacing_khz', '999'), ('nr_scaling_factor', '0')]:
        assert registry.validate_parameters('5g', {'bitrate_bps': 1_000_000, name: value})['status'] == 'INVALID', name
    result = registry.validate_parameters('can', {'bitrate_bps': 10_000, 'nr_direction': 'UL'})
    assert result['status'] == 'INVALID'
    assert 'TECHNOLOGY_PARAMETER_NOT_APPLICABLE' in {finding['code'] for finding in result['findings']}
    changed = registry.change_parameters('5g', 'can', {'nr_direction': 'UL', 'note': 'preserve'})
    assert changed['parameters'] == {'note': 'preserve'}
    assert changed['invalidated_fields'] == ['nr_direction']
