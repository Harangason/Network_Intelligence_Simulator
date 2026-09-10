"""Logical receive interfaces must agree with their actual physical transport."""
from copy import deepcopy


def align_receive_interfaces(route, interfaces, hardware_interfaces):
    """Repair only uniquely determined receive bindings; never choose alphabetically.

    The sender's interface is owned by its message and cannot be substituted here.
    Ambiguous destinations stay unchanged for validation and explicit selection.
    """
    from .validation import INTERFACE_PROTOCOLS
    result = deepcopy(route)
    by_id = {str(item['id']): item for item in interfaces}
    ports = {str(item['id']): item for item in hardware_interfaces}
    for endpoint in result.get('destinations', []):
        port = ports.get(str(endpoint.get('port_id')))
        if not port or str(port.get('hardware_node_id')) != str(endpoint.get('node_id')):
            continue
        if endpoint.get('network_id') and port.get('network_ref') and endpoint['network_id'] != port['network_ref']:
            continue
        protocol = endpoint.get('protocol') or result.get('source', {}).get('protocol')
        current = by_id.get(str(endpoint.get('interface_id')))
        if (not current or str(current.get('hardware_node_id')) != str(endpoint.get('node_id'))
                or protocol not in INTERFACE_PROTOCOLS.get(port.get('technology'), set())):
            continue
        if protocol in INTERFACE_PROTOCOLS.get(current.get('interface_type'), set()):
            continue
        candidates = [item for item in interfaces
                      if str(item.get('hardware_node_id')) == str(endpoint.get('node_id'))
                      and protocol in INTERFACE_PROTOCOLS.get(item.get('interface_type'), set())]
        if len(candidates) == 1:
            endpoint['interface_id'] = str(candidates[0]['id'])
    return result
