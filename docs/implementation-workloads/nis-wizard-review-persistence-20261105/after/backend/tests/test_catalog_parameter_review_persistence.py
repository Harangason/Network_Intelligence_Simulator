"""The user's catalog approval is revision-bound, durable and never PHY evidence."""
from copy import deepcopy
import json

from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.communication.catalog import TECHNOLOGY_IDS, technology_review
from backend.nis.communication.registry import TechnologyRegistry
from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol
from backend.nis.workflow.services.service import WorkflowStatusService


def test_all_125_user_reviews_are_persisted_for_exact_current_values():
    assert len(TECHNOLOGY_IDS) == 125
    for technology in TECHNOLOGY_IDS:
        persisted = technology_review(technology)['parameter_values_review']
        review = registry.parameter_value_review(technology)
        assert review['status'] == 'CONFIRMED', technology
        assert persisted['revision_sha256'] == review['revision_sha256']
        assert persisted['values'] == review['values']
        assert review['hardware_evidence'] is False
        assert review['source'] == 'EXPLICIT_USER_CATALOG_REVIEW'
        assert review['values'] == {field['key']: field['simulation_default']
                                    for field in registry.parameter_fields(technology)}


def test_profile_change_cannot_reuse_a_review_for_the_old_revision():
    local = TechnologyRegistry()
    profile = registry.profile('lin')
    local.register_defaults([profile])
    assert local.parameter_value_review('lin')['status'] == 'CONFIRMED'
    profile['parameter_schema']['lin_bitrate_bps']['label'] += ' revised'
    local = TechnologyRegistry()
    local.register_defaults([profile])
    assert local.parameter_value_review('lin')['status'] == 'REVIEW_REQUIRED'


def test_review_cache_keeps_callers_detached_and_tracks_registry_revision():
    local = TechnologyRegistry()
    local.register_defaults([registry.profile('lin')])
    first = local.parameter_value_review('lin')
    first['values']['lin_bitrate_bps'] = 1
    first['status'] = 'INVALID'
    assert local.parameter_value_review('lin')['values']['lin_bitrate_bps'] == 19200
    assert local.parameter_value_review('lin')['status'] == 'CONFIRMED'
    local.register_defaults([registry.profile('can')])
    assert local.parameter_value_review('lin')['status'] == 'CONFIRMED'


def test_one_changed_technology_invalidates_only_its_own_review():
    parameters = registry.simulation_defaults_for_project({'technology': 'can_fd'}, ['can_fd', 'lin'])
    original = deepcopy(parameters)
    parameters['simulation_parameter_assumptions']['lin']['values']['lin_bitrate_bps'] = 9600
    result = registry.with_parameter_reviews(parameters)
    assert result['technology_parameter_reviews']['can_fd']['status'] == 'CONFIRMED'
    review = result['technology_parameter_reviews']['lin']
    assert review['status'] == 'REVIEW_REQUIRED'
    assert review['changed_parameters'] == [{'scope': 'simulation', 'parameter': 'lin_bitrate_bps', 'value': 9600}]
    assert parameters['technology_parameter_reviews'] == original['technology_parameter_reviews']
    parameters['simulation_parameter_assumptions']['lin']['values']['lin_bitrate_bps'] = original['simulation_parameter_assumptions']['lin']['values']['lin_bitrate_bps']
    assert registry.with_parameter_reviews(parameters)['technology_parameter_reviews']['lin']['status'] == 'CONFIRMED'


def test_confirmed_user_override_is_preserved_and_does_not_change_catalog():
    parameters = registry.simulation_defaults_for_project({'technology': 'lin'}, ['lin'])
    parameters['technology_parameters'] = {'lin': {'values': {'bitrate': 9600}, 'provenance': {
        'bitrate': {'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'value': 9600}}}}
    result = registry.with_parameter_reviews(parameters)
    assert result['technology_parameter_reviews']['lin']['status'] == 'CONFIRMED'
    assert result['technology_parameters']['lin']['values']['bitrate'] == 9600
    assert registry.parameter_value_review('lin')['values']['lin_bitrate_bps'] == 19200


def test_network_edits_are_compared_to_exact_technology_and_value():
    parameters = registry.simulation_defaults_for_project({'technology': 'lin', 'networks': [
        {'id': 'LIN_MAIN', 'technology': 'lin', 'bitrate': 9600}]}, ['lin'])
    assert parameters['technology_parameter_reviews']['lin']['status'] == 'REVIEW_REQUIRED'
    parameters['networks'][0]['parameter_provenance'] = {'bitrate': {
        'source': 'USER_CONFIRMED', 'status': 'CONFIRMED', 'technology': 'can_fd', 'value': 9600}}
    assert registry.with_parameter_reviews(parameters)['technology_parameter_reviews']['lin']['status'] == 'REVIEW_REQUIRED'
    parameters['networks'][0]['parameter_provenance']['bitrate']['technology'] = 'lin'
    assert registry.with_parameter_reviews(parameters)['technology_parameter_reviews']['lin']['status'] == 'CONFIRMED'


def test_review_survives_sql_roundtrip_but_forged_unchanged_status_does_not():
    workflow = WorkflowStatusService()
    parameters = registry.simulation_defaults_for_project({'technology': 'lin'}, ['lin'])
    saved = workflow.save_parameters(parameters)['parameters']
    assert json.loads(json.dumps(saved['technology_parameter_reviews'])) == parameters['technology_parameter_reviews']
    edited = deepcopy(saved)
    group = edited['simulation_parameter_assumptions']['lin']
    group['values']['lin_bitrate_bps'] = 9600
    group['provenance']['lin_bitrate_bps']['value'] = 9600
    assert edited['technology_parameter_reviews']['lin']['status'] == 'CONFIRMED'
    result = workflow.save_parameters(edited)
    assert result['parameters']['technology_parameter_reviews']['lin']['status'] == 'REVIEW_REQUIRED'
    assert result['artifact_checks']['parameters']['required']['parameter_reviews'] is False


def test_catalog_approval_never_promotes_scenario_values_to_hardware_evidence():
    parameters = registry.simulation_defaults_for_project({'technology': 'can_fd'}, ['can_fd'])
    result = simulation_parameters_for_protocol('can_fd', parameters, confirmed_parameters=parameters)
    assert parameters['technology_parameter_reviews']['can_fd']['status'] == 'CONFIRMED'
    assert result['_simulation_parameters_usable']
    assert result['_simulation_assumption_fields']
    assert result['_simulation_hardware_evidence'] is False
    assert result['_rate_evidenced'] is False


def test_explicit_review_of_an_edited_simulation_setting_does_not_confirm_hardware():
    parameters = registry.simulation_defaults_for_project({'technology': 'lin'}, ['lin'])
    group = parameters['simulation_parameter_assumptions']['lin']
    group['values']['lin_bitrate_bps'] = 9600
    proof = group['provenance']['lin_bitrate_bps']
    proof['value'] = 9600
    proof['parameter_review'] = {'source': 'EXPLICIT_USER_PARAMETER_REVIEW', 'status': 'CONFIRMED', 'value': 9600}
    reviewed = registry.with_parameter_reviews(parameters)
    assert reviewed['technology_parameter_reviews']['lin']['status'] == 'CONFIRMED'
    assert proof['hardware_evidence'] is False
    proof['value'] = group['values']['lin_bitrate_bps'] = 10400
    assert registry.with_parameter_reviews(parameters)['technology_parameter_reviews']['lin']['status'] == 'REVIEW_REQUIRED'

