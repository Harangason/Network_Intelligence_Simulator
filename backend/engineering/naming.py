"""Concise generated labels. Identifiers and physical bindings are never renamed."""
import re


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


def new_bus_name(identifier, networks):
    family = bus_family(identifier)
    used = {str(row.get('name') or '') for row in networks}
    index = 1
    while f'{family}_{index:02d}' in used:
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
