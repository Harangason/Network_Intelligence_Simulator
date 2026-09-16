"""DE: Gemeinsamer, versionierter Projektentwurf für Chat und Wizard.

EN: Shared, revisioned project draft for chat and wizard. Drafts are not
canonical hardware and never grant proposal approval or invent a transport.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..db import ConcurrentUpdateError
from ..project_context import current_project_id
from . import conversation


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    device_id: str = Field(min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    known_kind: bool | None = None
    owner_id: str | None = Field(default=None, max_length=80)
    technology: str | None = Field(default=None, min_length=1, max_length=80)
    technologies: list[str] | None = Field(default=None, min_length=1, max_length=32)
    command: dict | None = None
    purpose: str | None = Field(default=None, min_length=1, max_length=500)


class DraftCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: str = Field(pattern='^(CREATE|AMEND|RESOLVE)$')
    operation_id: str = Field(min_length=8, max_length=120)
    revision: int | None = Field(default=None, ge=1)
    requirement: str = Field(default='', max_length=16000)
    industry: str | None = Field(default=None, max_length=80)
    devices: list[DeviceUpdate] = Field(default_factory=list, max_length=1000)
    remove_device_ids: list[str] = Field(default_factory=list, max_length=1000)
    allow_simulation_defaults: bool | None = None


_COUNTS = {'ein': 1, 'eine': 1, 'einen': 1, 'einem': 1, 'one': 1,
           'zwei': 2, 'two': 2, 'drei': 3, 'three': 3, 'vier': 4,
           'four': 4, 'fünf': 5, 'fuenf': 5, 'five': 5, 'sechs': 6,
           'six': 6, 'sieben': 7, 'seven': 7, 'acht': 8, 'eight': 8,
           'neun': 9, 'nine': 9, 'zehn': 10, 'ten': 10}
_NUMBER = r'(\d+|' + '|'.join(_COUNTS) + ')'


def _negated(text, match):
    """Ignore explicitly excluded alternatives, without discarding later clauses."""
    prefix = re.split(r'[.!?;,\n]|\b(?:sondern|but|instead|und|and)\b', text[:match.start()], flags=re.I)[-1]
    if re.search(r'\b(?:kein\w*|nicht|ohne|nix|no|not|non)\b', ' '.join(prefix.split()[-4:]), re.I):
        return True
    return bool(re.match(r'\s+(?:(?:ist|is)\s+)?(?:ausgeschlossen|unerwünscht|nicht\s+gewünscht|excluded)\b', text[match.end():], re.I))


def industry_candidates(text):
    patterns = {
        'building_automation': r'\b(?:gebäude\w*|gebaeude\w*|building\s+automation|gebäudeautomation)\b',
        'industrial_automation': r'\b(?:industrieautomation|industrieanlage\w*|industrial\s+automation|fabrik\w*)\b',
        'automotive': r'\b(?:automotive|fahrzeug\w*|auto|car|vehicle)\b',
        'embedded_systems': r'\b(?:embedded\w*|eingebettete\s+systeme)\b',
        'robotics_ros': r'\b(?:robotik|robotics)\b',
        'aerospace': r'\b(?:luftfahrt|aerospace)\b',
        'energy': r'\b(?:energietechnik|energieversorgung|power\s+grid)\b',
    }
    found = set()
    for industry, pattern in patterns.items():
        for match in re.finditer(pattern, text, re.I):
            if _negated(text, match):
                continue
            found.add(industry)
    return found


def explicit_industry(text):
    found = industry_candidates(text)
    return next(iter(found)) if len(found) == 1 else None


def migrate_draft(value):
    """Read v1 without changing identity/revision; persist v2 on the next edit.

    Unknown future versions must never be interpreted as today's schema.
    """
    if value is None:
        return None
    draft = deepcopy(value)
    version = draft.get('schema_version')
    if version not in {1, 2}:
        raise ValueError(f'Nicht unterstützte Entwurfsversion {version}. Gespeicherten Entwurf nicht überschreiben.')
    if draft.get('project_id') != current_project_id():
        raise ValueError('Der gespeicherte Entwurf gehört nicht zum aktuellen Projekt.')
    if type(draft.get('revision')) is not int or draft['revision'] < 1 or not draft.get('draft_id'):
        raise ValueError('Die Identität des gespeicherten Entwurfs ist ungültig.')
    if not isinstance(draft.get('devices'), list) or len({d['id'] for d in draft['devices']}) != len(draft['devices']):
        raise ValueError('Der gespeicherte Entwurf besitzt ungültige Geräteidentitäten.')
    draft.setdefault('removed_device_ids', [])
    draft['schema_version'] = 2
    return draft


def parse_requirement(requirement: str, industry: str | None = None) -> dict:
    """Extract only explicit inventory. Missing facts become actionable gaps."""
    devices = {}
    counts = {}
    issues = []
    pi = any(not _negated(requirement, match) for match in re.finditer(
        r'\b(?:raspberry|rasberry|rasperry|respary)[\s-]*pi\b|\braspi\b', requirement, re.I))

    def add(name, role, source, *, known_kind=True):
        key = name.casefold()
        existing = devices.get(key)
        if existing and existing['role'] != role:
            issues.append({'code': 'DEVICE_ROLE_CONFLICT', 'device': name,
                           'message': f'{name}: widersprüchliche Gerätearten.', 'action': 'CORRECT_REQUIREMENT'})
            return
        devices[key] = {'id': hashlib.sha256((role + ':' + key).encode()).hexdigest()[:20],
                        'name': name, 'role': role, 'source': source,
                        'known_kind': known_kind, 'source_known_kind': known_kind, 'technology': None, 'owner_id': None}

    if pi:
        add('RaspberryPi', 'CONTROLLER', 'Raspberry Pi in der Nutzeranforderung')
    for match in re.finditer(r'\b(Controller|ECU|SPS|PLC|Sensor|Aktor|Gateway)\s*(?:namens|named|:)\s*["„\']([^"“\'\n]+)["“\']', requirement, re.I):
        if _negated(requirement, match):
            continue
        role = {'sensor': 'SENSOR', 'aktor': 'ACTUATOR', 'gateway': 'GATEWAY'}.get(match[1].lower(), 'CONTROLLER')
        add(match[2].strip(), role, match[0])
    for role, pattern, stem, known in [
        ('SENSOR', r'temperatur(?:mess)?sensor(?:en|s)?|temperature\s+sensors?|sensor(?:en|s)?\s+(?:(?:für|fuer|zur messung von)\s+temperatur(?:en)?|(?:die\s+)?temperatur(?:en)?\s+messen|for\s+temperatures?)', 'Temperatursensor', True),
        ('SENSOR', r'drucksensor(?:en|s)?|pressure\s+sensors?', 'Drucksensor', True),
        ('SENSOR', r'feuchtigkeits(?:mess)?sensor(?:en|s)?|humidity\s+sensors?', 'Feuchtigkeitssensor', True),
        ('SENSOR', r'stromsensor(?:en|s)?|current\s+sensors?', 'Stromsensor', True),
        ('SENSOR', r'spannungssensor(?:en|s)?|voltage\s+sensors?', 'Spannungssensor', True),
        ('ACTUATOR', r'ventilaktor(?:en)?|ventil(?:e|en)?|valves?|aktor(?:en)?\s+(?:(?:für|fuer)\s+ventile|zum\s+(?:steuern\s+von\s+ventilen|ventil\s+steuern))', 'Ventilaktor', True),
        ('SENSOR', r'sensor(?:en|s)?', 'Sensor', False),
        ('ACTUATOR', r'aktor(?:en)?|actuators?', 'Aktor', False),
    ]:
        matches = [match for match in re.finditer(r'\b' + _NUMBER + r'\s+(?:' + pattern + r')\b', requirement, re.I)
                   if not _negated(requirement, match)]
        if not matches or (not known and any(d['role'] == role for d in devices.values())):
            continue
        match = matches[-1]
        number = int(match[1]) if match[1].isdigit() else _COUNTS[match[1].lower()]
        if number > 1000:
            raise ValueError('Maximal 1000 Geräte pro Geräteart.')
        counts[role] = counts.get(role, 0) + number
        for i in range(number):
            add(f'{stem}{i + 1}', role, match[0], known_kind=known)
    if re.search(r'\b(?:ventile(?:n)?|valves|aktoren|actuators)\b', requirement, re.I) and 'ACTUATOR' not in counts and not any(d['role'] == 'ACTUATOR' for d in devices.values()):
        issues.append({'code': 'ACTUATOR_COUNT_REQUIRED', 'message': 'Wie viele Ventile bzw. Aktoren sollen gesteuert werden?', 'action': 'SPECIFY_COUNT'})
    # Preserve the entire requested inventory, including qualified/compound
    # roles. Unspecified identities are draft slots, never confirmed hardware
    # capabilities, connections or canonical model objects.
    from .inventory_quantities import quantities
    from .inventory_details import details
    explicit_groups = details(requirement)
    for role in {g['role'] for g in explicit_groups}:
        # Prefer explicit typed lines to the earlier prose fallback for this
        # role. Keep user-named objects when there is no matching line group.
        for key in [k for k, d in devices.items() if d['role'] == role]:
            del devices[key]
        for group in (g for g in explicit_groups if g['role'] == role):
            stem = re.sub(r'[^\w]', '', group['name'])
            if re.search(r'raspberry', stem, re.I): stem = 'RaspberryPi'
            for index in range(group['count']):
                name = stem if group['count'] == 1 and role in {'CONTROLLER', 'GATEWAY'} else f'{stem}{index + 1}'
                add(name, role, group['source'], known_kind=group['known_kind'])
                devices[name.casefold()].update(technology=group['technology'],
                    connection_candidates=group['connection_candidates'], purpose=group['name'] if group['known_kind'] else None)
    scope = quantities(requirement)
    for key, role, stem in [('sensors', 'SENSOR', 'Sensor'), ('actuators', 'ACTUATOR', 'Aktor'),
                            ('ecus', 'CONTROLLER', 'Controller'), ('gateways', 'GATEWAY', 'Gateway')]:
        current = sum(d['role'] == role for d in devices.values())
        target = max(current, scope[key])
        if target:
            counts[role] = target
        index = 0
        while current < target:
            index += 1
            name = f'{stem}{index}'
            if name.casefold() in devices:
                continue
            add(name, role, f'Aus ausdrücklich genanntem Geräteumfang ({scope[key]}), Typ/Funktion noch zu klären',
                known_kind=False)
            current += 1
    controllers = [d for d in devices.values() if d['role'] in {'CONTROLLER', 'GATEWAY'}]
    endpoints = [d for d in devices.values() if d['role'] in {'SENSOR', 'ACTUATOR'}]
    if endpoints and not controllers:
        issues.append({'code': 'CONTROLLER_REQUIRED', 'message': 'Welcher Controller verarbeitet die Messwerte oder steuert die Aktoren?', 'action': 'ADD_CONTROLLER'})
    for device in endpoints:
        if not device['known_kind']:
            issues.append({'code': 'DEVICE_KIND_REQUIRED', 'device': device['name'],
                           'message': f"{device['name']}: Welcher Gerätetyp und welche Aufgabe?", 'action': 'SPECIFY_DEVICE'})
        if controllers:
            issues.append({'code': 'OWNER_REQUIRED', 'device': device['name'],
                           'message': f"{device['name']}: Controller-Zuordnung bestätigen.",
                           'action': 'ASSIGN_CONTROLLER', 'candidates': [d['id'] for d in controllers]})
    if not devices:
        issues.append({'code': 'INVENTORY_REQUIRED', 'message': 'Welche Geräte und Funktionen soll das Projekt enthalten?', 'action': 'SPECIFY_DEVICE'})
    candidates = industry_candidates(requirement)
    resolved_industry = industry or (next(iter(candidates)) if len(candidates) == 1 else None)
    if not candidates and not resolved_industry and pi:
        resolved_industry = 'embedded_systems'
    if not resolved_industry:
        issues.append({'code': 'INDUSTRY_REQUIRED', 'message': 'Für welchen Einsatzbereich wird das Projekt geplant?', 'action': 'SET_INDUSTRY'})
    for device in devices.values():
        if device['technology']:
            continue
        issues.append({'code': 'CONNECTION_REQUIRED', 'device': device['name'],
                       'message': f"{device['name']}: Physische Anschlüsse sind noch offen.", 'action': 'SPECIFY_CONNECTION'})
    for issue in issues:
        issue['id'] = hashlib.sha256((issue['code'] + ':' + issue.get('device', '')).encode()).hexdigest()[:20]
    return {'devices': list(devices.values()), 'declared_counts': counts,
            'industry': resolved_industry, 'issues': issues}


def inspect(_=None):
    """Return the persisted draft in the authoritative project context."""
    return migrate_draft(conversation.snapshot(current_project_id()).get('engineering_draft'))


def resolve_devices(draft, updates):
    """Validate explicit edits against this draft, without implicit references."""
    devices = {d['id']: d for d in draft['devices']}
    for update in updates:
        if update.device_id not in devices:
            raise ValueError('Das Gerät gehört nicht zu diesem Entwurf.')
        device = devices[update.device_id]
        changes = update.model_dump(exclude_unset=True, exclude={'device_id'})
        if changes.get('owner_id'):
            owner = devices.get(changes['owner_id'])
            if not owner or owner['role'] not in {'CONTROLLER', 'GATEWAY'} or owner['id'] == device['id']:
                raise ValueError('Die Controller-Zuordnung ist ungültig.')
        if changes.get('technology'):
            from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
            # Only actual register technologies can resolve a connection gap.
            technology_id = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(changes['technology'])
            DEFAULT_TECHNOLOGY_REGISTRY.profile(technology_id)
            changes['technology'] = technology_id
        if changes.get('technologies'):
            from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
            ids = list(dict.fromkeys(DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(value) for value in changes['technologies']))
            for technology_id in ids:
                DEFAULT_TECHNOLOGY_REGISTRY.profile(technology_id)
            if device['role'] not in {'CONTROLLER', 'GATEWAY'} and len(ids) > 1:
                raise ValueError('Mehrere Endpunktanschlüsse benötigen eine explizite Zuordnung der Messwerte oder Befehle.')
            if changes.get('technology') and changes['technology'] not in ids:
                raise ValueError('Der primäre Anschluss fehlt in den bestätigten Geräteanschlüssen.')
            changes['technologies'] = ids
            # Legacy consumers require a primary interface. This is only the
            # first explicitly listed connection, not an inferred capability.
            changes.setdefault('technology', ids[0])
        confirmed_connections = changes.get('technologies', device.get('technologies'))
        primary_connection = changes.get('technology', device.get('technology'))
        if confirmed_connections and primary_connection not in confirmed_connections:
            raise ValueError('Der primäre Anschluss fehlt in den bestätigten Geräteanschlüssen. Die Anschlussliste ausdrücklich aktualisieren.')
        if 'name' in changes:
            if changes['name'] is None or not changes['name'].strip():
                raise ValueError('Ein Gerätename darf nicht leer sein.')
            changes['name'] = changes['name'].strip()
        if changes.get('purpose'):
            if not changes['purpose'].strip():
                raise ValueError('Die Geräteaufgabe darf nicht leer sein.')
            changes['known_kind'] = True
        elif 'purpose' in changes and 'known_kind' not in changes:
            changes['known_kind'] = device.get('source_known_kind',
                device.get('known_kind', False) if not device.get('confirmed_fields', {}).get('purpose') else False)
        device.update(changes)
        if changes:
            device.setdefault('confirmed_fields', {}).update(deepcopy(changes))
    names = [d['name'].strip().casefold() for d in devices.values()]
    if len(set(names)) != len(names):
        raise ValueError('Gerätenamen müssen im Entwurf eindeutig sein.')
    reevaluated = {'CONTROLLER_REQUIRED', 'OWNER_REQUIRED', 'DEVICE_KIND_REQUIRED', 'CONNECTION_REQUIRED', 'INDUSTRY_REQUIRED', 'ACTUATOR_COMMAND_REQUIRED', 'INVENTORY_REQUIRED'}
    draft['issues'] = [i for i in draft['issues'] if i['code'] not in reevaluated]
    controllers = [d for d in devices.values() if d['role'] in {'CONTROLLER', 'GATEWAY'}]
    def issue(code, message, action, device=None):
        draft['issues'].append({'id': hashlib.sha256((code + ':' + (device or {}).get('id', '')).encode()).hexdigest()[:20],
                                'code': code, 'message': message, 'action': action,
                                **({'device': device['name'], 'device_id': device['id']} if device else {})})
    if not draft['industry']:
        issue('INDUSTRY_REQUIRED', 'Für welchen Einsatzbereich wird das Projekt geplant?', 'SET_INDUSTRY')
    if not devices:
        issue('INVENTORY_REQUIRED', 'Welche Geräte soll das Projekt enthalten?', 'SPECIFY_DEVICE')
    for device in devices.values():
        if device['role'] in {'SENSOR', 'ACTUATOR'}:
            if not controllers:
                issue('CONTROLLER_REQUIRED', f"{device['name']}: Controller ergänzen.", 'ADD_CONTROLLER', device)
            elif not device.get('owner_id'):
                issue('OWNER_REQUIRED', f"{device['name']}: Controller zuordnen.", 'ASSIGN_CONTROLLER', device)
            if not device.get('known_kind'):
                issue('DEVICE_KIND_REQUIRED', f"{device['name']}: Typ und Aufgabe angeben.", 'SPECIFY_DEVICE', device)
        if not device.get('technology'):
            issue('CONNECTION_REQUIRED', f"{device['name']}: Physische Anschlüsse angeben.", 'SPECIFY_CONNECTION', device)
        if device['role'] == 'ACTUATOR' and not device.get('command'):
            issue('ACTUATOR_COMMAND_REQUIRED', f"{device['name']}: Stellbefehl und Kodierung festlegen (zum Beispiel Auf/Zu oder Stellposition).", 'SPECIFY_COMMAND', device)
    return draft


def command(arguments):
    """Atomically persist source, revision and operation receipt, never a model."""
    request = DraftCommand.model_validate({k: v for k, v in arguments.items() if not k.startswith('_')})
    state = conversation.read()
    operations = state.setdefault('engineering_draft_operations', {})
    payload = request.model_dump(mode='json')
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    previous = operations.get(request.operation_id)
    if previous:
        if previous['signature'] != signature:
            raise ConcurrentUpdateError('Diese Operations-ID gehört zu einer anderen Eingabe.')
        return deepcopy(previous['result'])
    old = migrate_draft(state.get('engineering_draft'))
    if request.action == 'CREATE' and old:
        raise ConcurrentUpdateError('Ein Entwurf ist vorhanden. Diesen ergänzen oder ein neues Projekt anlegen.')
    if request.action != 'CREATE' and (not old or old['revision'] != request.revision):
        raise ConcurrentUpdateError('Der Entwurf wurde inzwischen geändert. Bitte den aktuellen Stand laden.')
    if request.action in {'CREATE', 'AMEND'} and not request.requirement.strip():
        raise ValueError('Eine konkrete Projektanforderung ist erforderlich.')
    sources = [*(old or {}).get('sources', []), {'text': request.requirement, 'source': 'USER', 'operation_id': request.operation_id}]
    text = '\n'.join(item['text'] for item in sources)
    if len(text) > 60000 and not (old and old.get('source_format') == 'WIZARD_V2'):
        raise ValueError('Der Entwurf überschreitet 60000 Zeichen.')
    if old and old.get('source_format') == 'WIZARD_V2':
        from .structured_project_draft import amend
        draft = amend(old, request)
        result = {'draft': draft, 'receipt': {'operation_id': request.operation_id, 'revision': draft['revision'], 'accepted': True}}
        state['engineering_draft'] = draft
        operations[request.operation_id] = {'signature': signature, 'result': deepcopy(result)}
        conversation.write(state)
        return result
    new_industries = industry_candidates(request.requirement)
    selected_industry = request.industry or explicit_industry(request.requirement)
    if not selected_industry and not new_industries:
        selected_industry = (old or {}).get('industry')
    draft = {**parse_requirement(text, selected_industry),
             'schema_version': 2, 'draft_id': (old or {}).get('draft_id') or str(uuid4()),
             'project_id': current_project_id(), 'revision': (old or {}).get('revision', 0) + 1,
             'mode': 'REAL_PROJECT', 'original_requirement': sources[0]['text'], 'sources': sources,
             'edits': deepcopy((old or {}).get('edits', []))}
    if request.action == 'RESOLVE':
        draft = {**deepcopy(old), 'revision': old['revision'] + 1,
                 'industry': (request.industry.strip() or None) if request.industry is not None else
                     None if 'industry' in request.model_fields_set else old.get('industry')}
    elif old:
        # Re-extraction may discover new devices, but must not discard human
        # decisions for unchanged device identities. References are rechecked.
        previous_devices = {d['id']: d for d in old['devices']}
        current_ids = {d['id'] for d in draft['devices']}
        for device in draft['devices']:
            confirmed = deepcopy(previous_devices.get(device['id'], {}).get('confirmed_fields', {}))
            if confirmed.get('owner_id') not in current_ids:
                confirmed.pop('owner_id', None)
            device.update(confirmed)
            device['confirmed_fields'] = confirmed
    draft.setdefault('edits', []).append({
        'revision': draft['revision'], 'operation_id': request.operation_id,
        'action': request.action, 'devices': [d.model_dump(exclude_unset=True) for d in request.devices],
        'industry': request.industry,
        'remove_device_ids': request.remove_device_ids,
    })
    # Explicit removal is a draft decision, not a canonical delete. Preserve it
    # across later source re-extraction; never silently resurrect removed parts.
    removed = set((old or {}).get('removed_device_ids', []))
    known_ids = {d['id'] for d in draft['devices']} | removed
    if set(request.remove_device_ids) - known_ids:
        raise ValueError('Ein zu entfernendes Gerät gehört nicht zu diesem Entwurf.')
    removed.update(request.remove_device_ids)
    draft['removed_device_ids'] = sorted(removed)
    draft['devices'] = [d for d in draft['devices'] if d['id'] not in removed]
    for device in draft['devices']:
        if device.get('owner_id') in removed:
            device['owner_id'] = None
            device.get('confirmed_fields', {}).pop('owner_id', None)
    draft['allow_simulation_defaults'] = (request.allow_simulation_defaults if request.allow_simulation_defaults is not None
                                         else (old or {}).get('allow_simulation_defaults', False))
    draft = resolve_devices(draft, request.devices)
    draft['status'] = 'NEEDS_DECISION' if draft['issues'] else 'READY_TO_PLAN'
    result = {'draft': draft, 'receipt': {'operation_id': request.operation_id, 'revision': draft['revision'], 'accepted': True}}
    state['engineering_draft'] = draft
    operations[request.operation_id] = {'signature': signature, 'result': deepcopy(result)}
    conversation.write(state)
    return result


def assert_proposal_source(row):
    """Review and apply must bind to the exact source draft revision."""
    if (row.get('engineering_contract') or {}).get('status') == 'APPLIED':
        return  # An accepted operation remains replayable after later draft edits.
    for evidence in row.get('evidence') or []:
        if evidence.get('source') != 'engineering_draft':
            continue
        current = inspect()
        if not current or current['draft_id'] != evidence.get('draft_id') or current['revision'] != evidence.get('revision'):
            raise ConcurrentUpdateError('Der Projektentwurf wurde nach der Planung geändert. Vorschlag neu erzeugen und prüfen.')


def planning_prompt(draft):
    """Versioned adapter into the shared model generator, not a second generator."""
    if draft.get('source_format') == 'WIZARD_V2':
        from .wizard_commands import effective_wizard_prompt
        return effective_wizard_prompt(draft['structured_source']['prompt'])
    if draft['issues']:
        raise ValueError('Offene Entwurfsangaben: ' + '; '.join(i['message'] for i in draft['issues'][:8]))
    if not draft.get('allow_simulation_defaults'):
        raise ValueError('Technische Parameter fehlen. Simulations-Defaults ausdrücklich wählen oder die Gerätespezifikation ergänzen.')
    devices = draft['devices']
    labels = {'CONTROLLER': 'Controller', 'GATEWAY': 'Gateway', 'SENSOR': 'Sensor', 'ACTUATOR': 'Aktor'}
    counts = {key: sum(d['role'] == role for d in devices) for key, role in
              [('ecus', 'CONTROLLER'), ('gateways', 'GATEWAY'), ('sensors', 'SENSOR'), ('actuators', 'ACTUATOR')]}
    lines = []
    by_id = {d['id']: d for d in devices}
    clusters = []
    for controller in devices:
        if controller['role'] not in {'CONTROLLER', 'GATEWAY'}:
            continue
        clusters.append({'id': 'draft-' + controller['id'], 'name': controller['name'], 'active': True,
                         'network_id': controller['technology'], 'bus_name': controller['name'],
                         'controller_status_scope': 'INTERNAL',
                         'controllers': [{'ecu': controller['name'],
                                          **({'device_type': 'Gateway'} if controller['role'] == 'GATEWAY' else {}),
                                          'sensors': [d['name'] for d in devices if d['role'] == 'SENSOR' and d['owner_id'] == controller['id']],
                                          'actuators': [d['name'] for d in devices if d['role'] == 'ACTUATOR' and d['owner_id'] == controller['id']]}]})
    for device in devices:
        name = json.dumps(device['name'], ensure_ascii=False)
        purpose = ' mit der Funktion ' + device['purpose'] if device.get('purpose') else ''
        lines.append(f"{labels[device['role']]} namens {name} mit {device['technology']}{purpose}.")
        if device.get('owner_id'):
            lines.append(f"{device['name']} wird von {by_id[device['owner_id']]['name']} ausgewertet.")
    technologies = sorted({tech for d in devices for tech in (d.get('technologies') or [d['technology']])})
    return '\n'.join([
        'Strukturierte Vorgaben fuer den Engineering-Agenten:',
        '- Generierungsmodus: REAL_PROJECT',
        '- Projekt-Modelltyp: ' + draft['industry'],
        '- Projektentwurf: ' + draft['draft_id'] + ' Revision ' + str(draft['revision']),
        '- Hardware-Sollwerte: ' + json.dumps(counts),
        '- Netzwerktechnologien: ' + ', '.join(f'{tech} ({tech})' for tech in technologies),
        '- Systemcluster-Graph: ' + json.dumps(clusters, ensure_ascii=False),
        '- Geräteanschlüsse: ' + json.dumps({d['name']: d['technology'] for d in devices}, ensure_ascii=False),
        '- Bestätigte-Geräteanschlüsse: ' + json.dumps({d['name']: d.get('technologies') or [d['technology']] for d in devices}, ensure_ascii=False),
        '- Geräte-Spezifikationen: ' + json.dumps({d['name']: d.get('source', '') for d in devices}, ensure_ascii=False),
        '- Aktor-Befehle: ' + json.dumps({d['name']: d['command'] for d in devices if d['role'] == 'ACTUATOR'}, ensure_ascii=False),
        '- Fachliche-Anforderungen: ' + json.dumps([source['text'] for source in draft['sources']], ensure_ascii=False),
        '- Parameter: Technologie-Defaults für Simulation; reale Hardwareeignung bleibt unbestätigt.',
        'Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:',
        *lines,
        'Lokale Messwerte und Stellbefehle bleiben im lokalen System. Keine externe Weiterleitung beauftragt.',
    ])


def plan_model(arguments):
    from . import wizard_generation, proposal_service
    state = conversation.read()
    draft = migrate_draft(state.get('engineering_draft'))
    if not draft or draft['draft_id'] != arguments['draft_id'] or draft['revision'] != arguments['revision']:
        raise ConcurrentUpdateError('Der Entwurf wurde inzwischen geändert.')
    prompt = planning_prompt(draft)
    result = wizard_generation.generate({'prompt': prompt}, source_evidence=[{
        'source': 'engineering_draft', 'draft_id': draft['draft_id'], 'revision': draft['revision'],
        'requirement': draft['original_requirement'], 'requirements': [source['text'] for source in draft['sources']], 'adapter_version': 2}])
    if not result.get('proposal_id'):
        return result
    proposal = proposal_service.validate(result['proposal_id'])
    draft['model_proposal_id'] = proposal['proposal_id']
    state['engineering_draft'] = draft
    conversation.write(state)
    return proposal


def workflow_request(arguments):
    """Adapt the same draft to the existing durable nine-stage executor."""
    from datetime import datetime, timezone
    from ..workflow.models import WORKFLOW_STEPS
    draft = inspect()
    if not draft or draft['draft_id'] != arguments['draft_id'] or draft['revision'] != arguments['revision']:
        raise ConcurrentUpdateError('Der Entwurf wurde inzwischen geändert. Aktuellen Stand laden.')
    scopes = arguments['scope_ids']
    if not scopes or len(set(scopes)) != len(scopes) or any(scope not in WORKFLOW_STEPS for scope in scopes):
        raise ValueError('Ein gültiger Workflowumfang ist erforderlich.')
    scopes = [scope for scope in WORKFLOW_STEPS if scope in scopes]
    name = arguments['project_name'].strip()
    if not name:
        raise ValueError('Projektname fehlt.')
    run_id = arguments['run_id']
    if draft.get('source_format') == 'WIZARD_V2':
        from .structured_project_draft import workflow
        return workflow(draft, run_id, name, scopes)
    prompt = planning_prompt(draft)
    prompt = prompt.replace('Strukturierte Vorgaben fuer den Engineering-Agenten:',
        'Strukturierte Vorgaben fuer den Engineering-Agenten:\n- Lauf-ID: ' + run_id +
        '\n- Projektname: ' + name + '\n- Workflowumfang: ' + '; '.join(scopes), 1)
    context = {'project_id': current_project_id(), 'run_id': run_id, 'project_name': name,
               'confirmed_at': datetime.now(timezone.utc).isoformat(), 'mode': 'full',
               'industry': draft['industry'], 'model_type': draft['industry'],
               'scope': scopes, 'scope_ids': scopes, 'process': [], 'process_ids': [],
               'notes': '', 'attachments': [], 'parameters': 'Technologie-Defaults für Simulation',
               'technologies': sorted({tech for d in draft['devices'] for tech in (d.get('technologies') or [d['technology']])}),
               'task': '\n\n'.join(source['text'] for source in draft['sources']),
               'agent_prompt': prompt,
               'engineering_draft_ref': {'draft_id': draft['draft_id'], 'revision': draft['revision']}}
    return {'prompt': prompt, 'context': context, 'target': scopes[-1]}
