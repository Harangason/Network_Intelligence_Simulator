"""Function partners are stable; hardware and transport paths are realizations."""
from copy import deepcopy


class FunctionalArchitecture:
    def __init__(self, objects):
        self.functions = {str(x['id']): x for x in objects['Function']}
        self.interfaces = {str(x['id']): x for x in objects['Interface']}
        self.hardware = {str(x['id']): x for x in objects['HardwareNode']}
        self.messages = {str(x['id']): x for x in objects['Message']}

    def resolve(self, endpoint, recorded=None, *, message_ids=()):
        evidence = 'Gespeicherte Funktionskommunikation' if recorded else 'Kanonische Kommunikationsschnittstelle'
        anchor = recorded or endpoint
        interface_id = anchor.get('interface_id')
        interface = self.interfaces.get(str(interface_id))
        function_id = anchor.get('function_id') or (interface or {}).get('function_id')
        if not interface and not function_id and message_ids:
            candidates = {str(self.messages[m].get('interface_id')) for m in message_ids if m in self.messages}
            if len(candidates) == 1:
                interface = self.interfaces.get(next(iter(candidates)))
                interface_id = (interface or {}).get('id')
                function_id = (interface or {}).get('function_id')
                evidence = 'Kanonischer Nachrichten-Publisher'
        if not function_id:
            # A recorded hardware recipient with exactly one assigned function is
            # usable evidence. Names, wire neighbors and gateway hops are not.
            node_id = str(anchor.get('hardware_node_id') or anchor.get('node_id') or '')
            functions = [f for f in self.functions.values() if str(f.get('hardware_node_id')) == node_id]
            if len(functions) == 1:
                function_id = str(functions[0]['id'])
                evidence = 'Einzige kanonisch zugeordnete Funktion des bisherigen Kommunikationspartners'
        function = self.functions.get(str(function_id))
        io_node_id = str(anchor.get('hardware_node_id') or anchor.get('node_id') or '')
        io_node = self.hardware.get(io_node_id, {})
        if not function_id and not (interface or {}).get('function_id') and io_node.get('device_type') in {'SensorController','ActuatorController'}:
            # Basic devices legitimately expose signal I/O without a separate
            # Function object. Preserve that exact I/O partner and identify it.
            identity = {'function_id': None, 'interface_id': str(interface_id) if interface_id else None,
                'hardware_node_id': io_node_id, 'partner_type': 'hardware_io', 'evidence': 'Kanonische Geräte-I/O des bisherigen Kommunikationspartners'}
            view = {**identity, 'function': 'Geräte-I/O: ' + io_node['name'], 'hardware': io_node['name'], 'issue': None}
            return {**endpoint, 'node_id': io_node_id, 'interface_id': identity['interface_id']}, identity, view
        issue = None
        if not function:
            issue = 'Die bisherige Partnerfunktion fehlt oder ist nicht eindeutig zugeordnet.'
        elif interface and str(interface.get('function_id')) != str(function['id']):
            issue = 'Die gespeicherte Schnittstelle gehört inzwischen zu einer anderen Funktion.'
        elif str(function.get('hardware_node_id')) not in self.hardware:
            issue = 'Die Partnerfunktion besitzt keine aktuelle Hardwarezuordnung.'
        node_id = str((function or {}).get('hardware_node_id') or anchor.get('hardware_node_id') or endpoint.get('node_id') or '')
        if not issue and not interface:
            from .routing.validation import INTERFACE_PROTOCOLS
            interfaces = [i for i in self.interfaces.values() if str(i.get('function_id')) == str(function_id)
                and endpoint.get('protocol') in INTERFACE_PROTOCOLS.get(i.get('interface_type'), set())]
            if len(interfaces) == 1:
                interface = interfaces[0]; interface_id = str(interface['id'])
            elif interface_id:
                issue = 'Die bisherige Kommunikationsschnittstelle fehlt; ihr Ersatz ist nicht eindeutig.'
        current = {**endpoint, 'node_id': node_id, 'function_id': str(function_id) if function_id else None,
            'interface_id': str(interface_id) if interface_id else None}
        if node_id != str(endpoint.get('node_id')):
            # Addresses and labels belong to the current hardware, not its old host.
            for key in ('node_name', 'logical_node_address', 'formatted_logical_node_address', 'address_namespace'):
                current.pop(key, None)
        identity = {'function_id': current['function_id'], 'interface_id': current['interface_id'],
            'hardware_node_id': node_id, 'evidence': evidence}
        view = {**identity, 'function': (function or {}).get('name', 'Partnerfunktion offen'),
            'hardware': self.hardware.get(node_id, {}).get('name', 'Hardwarezuordnung offen'), 'issue': issue}
        return current, identity, view

    def project(self, route, message_ids=()):
        recorded = (route.get('route') or {}).get('functional_intent') or {}
        endpoints = [route['source'], *route['destinations']]
        anchors = [recorded.get('source'), *(recorded.get('destinations') or [])]
        if len(anchors) < len(endpoints): anchors.extend([None] * (len(endpoints) - len(anchors)))
        results = [self.resolve(e, anchors[i], message_ids=message_ids if i == 0 else ()) for i,e in enumerate(endpoints)]
        projected = {**route, 'source': results[0][0], 'destinations': [r[0] for r in results[1:]]}
        intent = {'version': 1, 'source': results[0][1], 'destinations': [r[1] for r in results[1:]]}
        views = [r[2] for r in results]
        issues = [v['issue'] for v in views if v['issue']]
        if any(e['hardware_node_id'] == views[0]['hardware_node_id'] for e in views[1:]):
            issues.append('Partnerfunktionen liegen jetzt auf demselben Gerät. Dafür muss lokale Kommunikation statt eines externen Buswegs ausgelegt werden.')
        if recorded.get('destinations') and len(recorded['destinations']) != len(route['destinations']):
            issues.append('Die Anzahl der Empfänger weicht von der gespeicherten Funktionskommunikation ab.')
        changed = any(any(str(a.get(k) or '') != str(b.get(k) or '') for k in ('node_id','interface_id')) for a,b in zip(endpoints,[projected['source'],*projected['destinations']]))
        changed = changed or any(str(self.interfaces.get(str(e.get('interface_id')), {}).get('hardware_node_id')) != str(e['node_id'])
            for e in [projected['source'], *projected['destinations']] if e.get('interface_id') in self.interfaces)
        return projected, intent, {'source': views[0], 'destinations': views[1:], 'issues': list(dict.fromkeys(issues)), 'changed': changed}


def capture_route_intent(data, current=None):
    """Keep established partners when the network editor replaces physical ends.

    Ordinary routing-form edits may deliberately change function partners; their
    new intent is captured. Physical changes keep the previous logical anchors.
    """
    from .db import get_connection
    from .project_context import current_project_id
    from uuid import UUID
    route = data.get('route') or {}
    actor = str(data.get('modified_by') or data.get('created_by') or '')
    physical_edit = actor.startswith('network-editor') or actor == 'communication-repair-agent'
    existing = ((current or {}).get('route') or {}).get('functional_intent')
    if physical_edit and existing:
        # The repair planner may resolve previously open anchors, but must keep
        # every already established partner identity.
        proposed = route.get('functional_intent') if actor == 'communication-repair-agent' else None
        if proposed:
            old = [existing.get('source') or {}, *(existing.get('destinations') or [])]
            new = [proposed.get('source') or {}, *(proposed.get('destinations') or [])]
            if len(old) == len(new) and all(not a.get('function_id') or a['function_id'] == b.get('function_id') for a,b in zip(old,new)):
                return data
        return {**data, 'route': {**route, 'functional_intent': deepcopy(existing)}}
    if not current and route.get('functional_intent'): return data
    source = current if physical_edit and current else data
    endpoints = [source.get('source') or {}, *(source.get('destinations') or [])]
    identifiers = []
    for e in endpoints:
        try: identifiers.append(str(UUID(str(e.get('interface_id')))))
        except ValueError: pass
    if not identifiers: return data
    with get_connection() as connection:
        rows = connection.execute('SELECT id, function_id FROM engineering_interfaces WHERE project_id=%s AND id=ANY(%s::uuid[])',
            (current_project_id(), identifiers)).fetchall()
    interfaces = {str(i['id']):i for i in rows}
    anchors = [{'function_id': str(f) if (f := interfaces.get(str(e.get('interface_id')), {}).get('function_id')) else None,
        'interface_id': e.get('interface_id'), 'hardware_node_id': e.get('node_id'), 'evidence': 'Kanonische Route vor Hardwareänderung' if physical_edit else 'Kanonische Funktionskommunikation'} for e in endpoints]
    # A freshly computed repair intent contains more complete canonical evidence.
    if actor == 'communication-repair-agent' and route.get('functional_intent'): return data
    return {**data, 'route': {**route, 'functional_intent': {'version':1,'source':anchors[0],'destinations':anchors[1:]}}}
