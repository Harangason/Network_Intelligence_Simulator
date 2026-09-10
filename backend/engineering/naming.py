"""Concise generated labels. Identifiers and physical bindings are never renamed."""
import re
import unicodedata


def concise_name(kind, name):
    value = str(name or '').strip()
    if kind == 'Function':
        return re.sub(r'_(?:Sensor_Erfassung|Actuator_Steuerung|Gateway_Kommunikation|Steuerung)$', '', value) or value
    if kind == 'Interface':
        return re.sub(r'_1$', '', value) or value
    if kind == 'Message':
        clean = re.sub(r'(?:Sensor_?Erfassung|Actuator_?Steuerung|Gateway_?Kommunikation|Steuerung)?_?Data(?=\d*$)', '', value)
        clean = re.sub(r'_(?:Command)$', ' Befehl', clean)
        clean = re.sub(r'(?<=[a-zäöüß0-9])(?=[A-ZÄÖÜ])', ' ', clean)
        return re.sub(r'[_\s]+', ' ', clean).strip() or value
    return value


def bus_family(identifier):
    base = re.sub(r'_\d+$', '', str(identifier).split('-IO-')[0].split('-S')[0])
    return {'Antriebsstrang': 'Antrieb', 'Karosserie_Komfort': 'Komfort', 'Fahrwerk_Fahrdynamik': 'Fahrwerk'}.get(base, base)


def new_bus_name(identifier, networks, *, technology='', context=''):
    family = ('ETH_' + ethernet_name_component(context or ethernet_context({'id': identifier}))) if is_ethernet(technology) else bus_family(identifier)
    used = {str(row.get('name') or '').casefold() for row in networks}
    index = 1
    while f'{family}_{index:02d}'.casefold() in used:
        index += 1
    return f'{family}_{index:02d}'


def concise_bus_names(networks):
    """Preserve already assigned/custom names; allocate distinct labels once."""
    result, pending = {}, []
    for row in networks:
        name, identifier = str(row.get('name') or row['id']), str(row['id'])
        generated = name == identifier or bool(re.search(r' Segment \d+$| I/O', name))
        if generated:
            pending.append(row)
        else:
            result[identifier] = name
    for row in sorted(pending, key=lambda item: str(item['id'])):
        identifier = str(row['id'])
        result[identifier] = new_bus_name(identifier, [{'name': name} for name in result.values()])
    return result


def is_ethernet(technology):
    return re.sub(r'[-_\s]', '', str(technology)).casefold() in {'ethernet', 'automotiveethernet', 'eth'}


def ethernet_name_component(value):
    for char, replacement in {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'}.items():
        value = str(value).replace(char, replacement)
    value = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Za-z0-9]+', '_', value).strip('_')[:90].rstrip('_') or 'Netz'


def ethernet_context(network, topology=None, hardware=()):
    """Resolve label context only; never derive physical identity from a name."""
    if network.get('name_context'):
        return network['name_context']
    topology = topology or {}
    nodes = topology.get('nodes') or []
    by_id = {str(n.get('engineeringId') or n.get('id')): n for n in nodes}
    by_id.update({str(h['id']): h for h in hardware})
    members = [n for n in nodes if any(p.get('physicalNetworkId') == network['id'] for p in n.get('ports', []))]
    owners = {str(n.get('systemOwnerId') or (by_id.get(str(n.get('engineeringId')), {}).get('identity') or {}).get('system_owner_id'))
              for n in members if n.get('systemOwnerId') or (by_id.get(str(n.get('engineeringId')), {}).get('identity') or {}).get('system_owner_id')}
    if len(owners) == 1:
        owner = by_id.get(next(iter(owners)))
        if owner and owner.get('name'):
            return owner['name']
    controllers = [n for n in members if n.get('kind') == 'ecu']
    if len(controllers) == 1:
        return controllers[0]['name']
    member_ids = {n['id'] for n in members if n.get('kind') != 'gateway'}
    for cluster in (topology.get('scene') or {}).get('clusters', []):
        if member_ids and member_ids <= set(cluster.get('memberIds') or []) and cluster.get('label'):
            return cluster['label']
    identifier = str(network.get('id') or '')
    local = re.match(r'^.+-IO-(.+)-automotive-ethernet-S\d+', identifier, re.I)
    backbone = re.match(r'^(.+?)(?:_\d+)?-S\d+', identifier)
    candidate = local[1].replace('-', ' ') if local else backbone[1] if backbone else ''
    if candidate:
        matching = next((n['name'] for n in by_id.values() if str(n.get('name', '')).casefold() == candidate.casefold()), None)
        return matching or candidate[0].upper() + candidate[1:]
    return 'Netz'


def ethernet_names(networks, *, topology=None, hardware=()):
    """Allocate persistent labels, stable across order/rebuild and custom labels."""
    result = {str(n['id']): dict(n) for n in networks}
    pending = []
    for identifier, row in result.items():
        if not is_ethernet(row.get('technology')) or row.get('name_source') == 'user':
            continue
        name = str(row.get('name') or '')
        context = ethernet_context(row, topology, hardware)
        expected = 'ETH_' + ethernet_name_component(context) + '_'
        if re.fullmatch(re.escape(expected) + r'\d{2,}', name):
            continue
        legacy = not name or name in {identifier, new_bus_name(identifier, [])} or bool(re.search(r' Segment \d+$| I/O', name))
        if row.get('name_source') == 'generated' or legacy:
            pending.append((identifier, context))
    for identifier, _ in pending:
        result[identifier]['name'] = ''  # Reserve only accepted names, including custom ones.
    for identifier, context in sorted(pending):
        result[identifier].update(name=new_bus_name(identifier, result.values(), technology='ETHERNET', context=context),
                                  name_source='generated', name_context=context)
    return result
