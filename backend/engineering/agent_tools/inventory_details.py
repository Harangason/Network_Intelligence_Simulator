"""Extract explicit inventory lines without treating network lists as devices.

Section totals are not additional devices. Unquantified lists under a larger
total describe candidate kinds, not a license to distribute that total evenly.
Connection alternatives remain unresolved and retain their original source.
"""
import re

TECHNOLOGIES = [
    (r'CAN[- ]?FD', 'CAN_FD'), (r'CANopen', 'CANopen'),
    (r'PROFINET', 'PROFINET'), (r'PROFIBUS(?: PA)?', 'PROFIBUS'),
    (r'EtherCAT', 'EtherCAT'), (r'IO[- ]Link', 'IO_LINK'),
    (r'Modbus[- ]RTU', 'Modbus_RTU'), (r'RS[- ]485', 'RS485'),
    (r'I[²2]C', 'I2C'), (r'SPI(?:-ADC)?', 'SPI'),
    (r'GPIO(?: Counter)?', 'GPIO'), (r'PWM', 'PWM'),
    (r'LIN', 'LIN'), (r'Ethernet', 'Ethernet'),
]


def details(text):
    if '\n' not in text:
        return []  # Prose uses the quantity/parser path, not the line grammar.
    groups = []
    section = None
    total = None
    pending = []
    declared = {}

    def flush():
        nonlocal pending
        # Explicit per-kind counts are safe. Bare labels only define a complete
        # inventory when each is one device and matches the declared total.
        if pending and (sum(g['count'] for g in pending) == total or all(g['quantified'] for g in pending)):
            groups.extend(pending)
        pending = []

    for raw in text.splitlines():
        line = raw.strip()
        header = re.fullmatch(r'(?:(\d+)\s+)?(Sensoren|Sensorik|Sensorgruppen|Aktoren|Aktuatoren)\s*:', line, re.I)
        if header:
            flush()
            section = 'SENSOR' if header[2].lower().startswith('sensor') else 'ACTUATOR'
            total = int(header[1]) if header[1] else declared.get(section)
            continue
        if not line:
            continue
        bullet = line.startswith('- ')
        body = line[2:] if bullet else line
        if re.match(r'(?:keine?\b|ohne\b|nicht\b|no\b|not\b)', body, re.I):
            continue
        match = re.match(r'(\d+)\s+(.+)', body)
        quantity, label = (int(match[1]), match[2]) if match else (1, body)
        role = section if bullet else None
        if not bullet:
            flush()
            section, total = None, None
        if role is None and match:
            if re.search(r'\bgateway\b', label, re.I): role = 'GATEWAY'
            elif re.search(r'controller|\bPLCs?\b|\bSPS\b|raspberry|computer|compute|rechner|\bPC\b|echtzeitsteuerung', label, re.I): role = 'CONTROLLER'
            elif re.search(r'sensor|encoder', label, re.I): role = 'SENSOR'
            elif re.search(r'aktor|actuator|antrieb|drives?|ventil|lüfter', label, re.I): role = 'ACTUATOR'
        if role is None:
            if not bullet: section = None
            continue
        if quantity > 1000: raise ValueError('Maximal 1000 Geräte pro Geräteart.')
        # A plain heading ("24 Sensoren") is a total, not a typed group.
        name = re.split(r'\s+(?:über|ueber|via|mit)\s+|,', label, maxsplit=1, flags=re.I)[0].strip()
        generic = bool(re.fullmatch(r'(?:weitere\s+|zusätzliche\s+)?(?:Sensoren|Aktoren|Actuators?|Controllers?|Funktionscontroller)', name, re.I))
        if generic and match: declared[role] = quantity
        technologies = [canonical for pattern, canonical in TECHNOLOGIES if re.search(r'(?<!\w)' + pattern + r'(?!\w)', label, re.I)]
        group = {'role': role, 'count': quantity, 'name': name, 'source': raw,
                 'known_kind': not generic, 'technology': technologies[0] if len(technologies) == 1 else None,
                 'connection_candidates': technologies, 'quantified': bool(match)}
        if section: pending.append(group)
        elif not generic: groups.append(group)
    flush()
    # Repeated identical inventory lines (e.g. the central gateway) refer to
    # the same group, not another piece of hardware.
    unique = {}
    for group in groups:
        key = (group['role'], group['name'].casefold())
        if key not in unique or group['count'] > unique[key]['count']: unique[key] = group
    result = list(unique.values())
    # Only explicit communication sections may bind separate technology lines.
    # A network catalogue with several buses is never a device assignment.
    communication = re.search(r'(?im)^Kommunikation:\s*\n(.*?)(?=\n\s*\n|\Z)', text, re.S)
    if communication:
        body = communication[1]
        for group in result:
            if group['technology']:
                continue
            candidates = set()
            sources = []
            for line in body.splitlines():
                scope, separator, binding = line.strip('- ').partition(':')
                if separator:
                    # Plural endings do not change the named device family.
                    labels = [re.sub(r'[^\w]', '', part).casefold().rstrip('s') for part in scope.split('/')]
                    name = re.sub(r'[^\w]', '', group['name']).casefold().rstrip('s')
                    applies = any(label and (name == label or name == label + 's') for label in labels)
                else:
                    binding = scope
                    applies = len(body.strip().splitlines()) == 1
                if applies:
                    found = [canonical for pattern, canonical in TECHNOLOGIES if re.search(r'(?<!\w)' + pattern + r'(?!\w)', binding, re.I)]
                    candidates.update(found)
                    if found: sources.append(line.strip())
            if candidates:
                group['connection_candidates'] = sorted(candidates)
                group['technology'] = next(iter(candidates)) if len(candidates) == 1 else None
                group['source'] += '\n' + '\n'.join(sources)
    return result
