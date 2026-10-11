from backend.engineering.generation_experience import collect_generation_experience
from backend.engineering.generation_rule_manager import resolve_generation_policy


def _row(status: str, proposal_id: str, policy: dict):
    return {
        'proposal_id': proposal_id,
        'status': 'READY_FOR_REVIEW',
        'engineering_contract': {'status': status},
        'evidence': [{'source': 'wizard-specification-generator', 'generation_policy': policy}],
    }


def test_generation_experience_uses_only_reviewed_matching_outcomes():
    current = resolve_generation_policy(
        'Industrieanlage mit EtherCAT',
        industry='industrial_automation',
        bus_types=['ethercat'],
    )
    other = resolve_generation_policy(
        'Fahrzeug mit CAN-FD',
        industry='automotive',
        bus_types=['can_fd'],
    )
    rows = [
        _row('APPLIED', 'accepted-1', current),
        _row('REJECTED', 'rejected-1', current),
        _row('APPLIED', 'other-industry', other),
        {
            'proposal_id': 'not-reviewed',
            'engineering_contract': {'status': 'VALIDATED'},
            'evidence': [{'generation_policy': current}],
        },
    ]

    result = collect_generation_experience(rows, current)

    assert result['reviewed_generation_proposals'] == 3
    assert result['model_weights_changed'] is False
    assert result['authority'] == 'advisory_only'
    assert len(result['matching_suggestions']) == 1
    suggestion = result['matching_suggestions'][0]
    assert suggestion['applied'] == 1
    assert suggestion['rejected'] == 1
    assert suggestion['requires_current_validation'] is True
    assert suggestion['generator_sources']


def test_unreviewed_history_never_becomes_learning_evidence():
    current = resolve_generation_policy(
        'Gebäudeautomation mit BACnet/IP',
        industry='building_automation',
        bus_types=['bacnet_ip'],
    )
    result = collect_generation_experience([
        {
            'proposal_id': 'draft-only',
            'engineering_contract': {'status': 'PROPOSED'},
            'evidence': [{'generation_policy': current}],
        }
    ], current)

    assert result['reviewed_generation_proposals'] == 0
    assert result['matching_suggestions'] == []

def test_functional_choices_require_review_and_exact_industry_identity():
    policy = resolve_generation_policy('Fahrzeug CAN-FD', industry='automotive', bus_types=['can_fd'])
    def row(status, identifier):
        value = _row(status, identifier, policy)
        value['evidence'][0]['functional_route_choices'] = [{'source': 'Motorsteuerung', 'target': 'Getriebesteuerung', 'signals': ['MomentIst'], 'excluded_signals': ['PrivateStatus'], 'review_status': 'USER_REJECTED' if status == 'REJECTED' else 'USER_CONFIRMED'}]
        return value
    result = collect_generation_experience([row('APPLIED', 'yes'), row('REJECTED', 'no'), row('VALIDATED', 'pending')], policy)
    choices = result['functional_partner_suggestions']
    selected = next(choice for choice in choices if choice['signal'] == 'MomentIst')
    assert selected['accepted'] == 1 and selected['rejected'] == 1
    assert selected['proposal_refs'] == ['yes', 'no'] and selected['requires_current_confirmation']
    assert next(choice for choice in choices if choice['signal'] == 'PrivateStatus')['accepted'] == 0
    rail = resolve_generation_policy('Zug CAN-FD', industry='rail', bus_types=['can_fd'])
    assert collect_generation_experience([row('APPLIED', 'yes')], rail)['functional_partner_suggestions'] == []

def test_rejected_model_without_partner_verdict_does_not_suppress_functional_choice():
    policy = resolve_generation_policy('Fahrzeug CAN-FD', industry='automotive', bus_types=['can_fd'])
    row = _row('REJECTED', 'capacity-problem', policy)
    row['evidence'][0]['functional_route_choices'] = [{'source': 'Motor', 'target': 'Getriebe', 'signals': ['MomentIst'], 'excluded_signals': []}]
    assert collect_generation_experience([row], policy)['functional_partner_suggestions'] == []
