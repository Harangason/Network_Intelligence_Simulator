"""Real profile constraints for proposed IDs; not physical protocol acceptance."""
from copy import deepcopy
import pytest

from backend.nis.agent.tools.wizard_generation import _assign_reference_message_identifiers


def chains(count, technology='CAN', network='local'):
    return [{'interface_type': technology, 'message_name': 'm' + str(index),
             'transport_network_ref': network, 'configuration': {'reference_port': {'parameters': {
                 'lin_edition': 'LIN_2_2A_2010', 'lin_frame_kind': 'UNCONDITIONAL'}}}} for index in range(count)]


def test_can_identifiers_reuse_existing_allocator_per_physical_network():
    one, two = chains(2), chains(1, network='separate')
    spec = {'chains': [*one, *two]}
    existing = {'HardwareNetworkInterface': [{'id': 'p', 'network_ref': 'local'}],
                'Message': [{'id': 'old', 'name': 'persisted', 'hardware_interface_id': 'p', 'message_id_hex': '0x100'}]}
    before = deepcopy(existing)
    _assign_reference_message_identifiers(spec, existing)
    assert [row['message_id_hex'] for row in spec['chains']] == ['0x101', '0x102', '0x100']
    assert existing == before
    assert all(row['configuration']['reference_identifier_design']['hardware_evidence'] is False for row in spec['chains'])


def test_lin_normal_frames_never_consume_diagnostic_or_reserved_ids():
    spec = {'chains': chains(61, 'LIN')}
    with pytest.raises(ValueError, match='kein freier gültiger Identifier'):
        _assign_reference_message_identifiers(spec, {})
    assert [int(row['message_id_hex'], 16) for row in spec['chains'][:60]] == list(range(60))
    assert 'message_id_hex' not in spec['chains'][60]


def test_lin_allocator_requires_reviewed_edition_and_frame_kind():
    spec = {'chains': chains(1, 'LIN')}
    spec['chains'][0]['configuration']['reference_port']['parameters'] = {}
    with pytest.raises(ValueError, match='Edition und Frameart'):
        _assign_reference_message_identifiers(spec, {})


def test_receive_only_port_gets_no_fabricated_identifier():
    spec = {'chains': chains(1, 'LIN')}
    spec['chains'][0]['configuration']['reference_receive_only'] = True
    _assign_reference_message_identifiers(spec, {})
    assert 'message_id_hex' not in spec['chains'][0]
