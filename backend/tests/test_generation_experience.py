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
