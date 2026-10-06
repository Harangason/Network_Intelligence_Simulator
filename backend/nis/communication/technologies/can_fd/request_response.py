"""Existing bounded CAN-FD unicast request/response proof."""
from backend.nis.engineering.capacity.transmission import profile, positive

def bus_request_pairs(rows):
    """Validate explicit single-bus unicast exchanges in a complete traffic set.

    Both assessment and simulation supply these same canonical stream fields.
    Multi-hop and chained requests remain unsupported, never approximated.
    """
    pairs = []
    for response in rows:
        contract = response.get('transmission_contract') or {}
        if contract.get('request_source') != 'bus_message':
            continue
        if contract.get('mode') != 'ON_REQUEST' or profile(contract, response.get('cycle_ms'))['errors']:
            raise ValueError('Bus-Anfrageprofil ist unvollständig.')
        requests = [row for row in rows if row.get('message_id') == contract['request_message_ref']]
        if len(requests) != 1:
            raise ValueError('Bus-Anfragenachricht fehlt oder ist mehrdeutig.')
        request = requests[0]
        request_contract = request.get('transmission_contract') or {}
        if (request is response or str(request_contract.get('mode') or 'CYCLIC').upper() != 'CYCLIC'
                or request_contract.get('request_source') == 'bus_message'
                or profile(request_contract, request.get('cycle_ms'))['errors']
                or any(row.get('route_segment_count', 1) != 1 for row in (request, response))
                or any(str(row.get('protocol')).upper() != 'CAN_FD' for row in (request, response))
                or not request.get('network_id') or request.get('network_id') != response.get('network_id')
                or not request.get('producer') or not response.get('producer')
                or request.get('consumers') != [response['producer']]
                or response.get('consumers') != [request['producer']]
                or positive(request.get('cycle_ms')) is None
                or float(contract['minimum_interval_ms']) > float(request['cycle_ms'])):
            raise ValueError('Bus-Anfrage und Antwort benötigen einen eindeutigen zyklischen CAN-FD-Unicast-Pfad mit umgekehrten Endpunkten und begrenzter Antwortrate.')
        pairs.append((request, response))
    return pairs

