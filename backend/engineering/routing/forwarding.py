"""Explicit forwarding between canonical channels; a plain ECU is not a gateway."""


def forwarding_permitted(hardware, source, target):
    if not source or not target or str(source.get('hardware_node_id')) != str(hardware.get('id')) or str(target.get('hardware_node_id')) != str(hardware.get('id')):
        return False
    if hardware.get('device_type') == 'Gateway':
        return True
    return any(rule.get('confirmed') is True
        and str(rule.get('input_port_id')) == str(source['id'])
        and str(rule.get('output_port_id')) == str(target['id'])
        and rule.get('input_network_id') == source.get('network_ref')
        and rule.get('output_network_id') == target.get('network_ref')
        for rule in (hardware.get('identity') or {}).get('communication_forwarding', []) if isinstance(rule, dict))


def forwarding_rule(source, target):
    return {'input_port_id': str(source['id']), 'output_port_id': str(target['id']),
        'input_network_id': source['network_ref'], 'output_network_id': target['network_ref'],
        'confirmed': True, 'source': 'communication-repair-choice'}
