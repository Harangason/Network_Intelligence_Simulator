"""Recognize project design requests without pretending that a search creates a model."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_DOCUMENT_CONTROLLER_LABEL = r'(?:Controller|Computer|ECU|Steuergerät|Steuergeraet|Rechner|PLC|SPS)'


class DocumentComponent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    kind: Literal['INSTANCE', 'CATEGORY', 'FUNCTION', 'REQUIREMENT']
    role: Literal['CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR', 'OTHER']
    quantity: int | None = Field(default=None, ge=1, le=1000)
    source_quote: str = Field(min_length=1, max_length=1200)


class DocumentTechnology(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    kind: Literal['TRANSPORT', 'DEVICE_ALIAS', 'UNRESOLVED']
    source_quote: str = Field(min_length=1, max_length=1200)


class DocumentInterpretation(BaseModel):
    """Source facts and proposed design remain separate review data."""
    model_config = ConfigDict(extra='forbid')
    summary: str = Field(min_length=1, max_length=1500)
    components: list[DocumentComponent] = Field(default_factory=list, max_length=60)
    technologies: list[DocumentTechnology] = Field(default_factory=list, max_length=32)
    proposed_task: str = Field(min_length=1, max_length=6000)
    assumptions: list[str] = Field(default_factory=list, max_length=16)
    open_questions: list[str] = Field(default_factory=list, max_length=16)


class DocumentIntakeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: str = Field(min_length=1, max_length=80000)
    source_name: str = Field(default='Projektbeschreibung', min_length=1, max_length=180)
    source_request_id: str | None = Field(default=None, min_length=8, max_length=80)


def document_segments(source: str, max_bytes=6000):
    """Cover every source character in bounded, contiguous inference windows."""
    segments = []
    start = 0
    while start < len(source):
        window = source[start:].encode()[:max_bytes].decode('utf-8', errors='ignore')
        boundary = window.rfind('\n')
        if boundary >= len(window) // 2 and start + len(window) < len(source):
            window = window[:boundary + 1]
        if not window:
            raise ValueError('Das lokale Kontextfenster ist zu klein.')
        segments.append({'start': start, 'end': start + len(window), 'text': window})
        start += len(window)
    if len(segments) > 8:
        raise ValueError('Die Quelle benötigt mehr als acht lokale Auswertungsabschnitte. Bitte aufteilen; sie wird nicht gekürzt.')
    return segments


def document_source_references(source: str):
    """Number original lines while preserving every character and line ending."""
    rows = []
    prefix = ''
    for line in source.splitlines(keepends=True):
        if not line.strip():
            prefix += line
            continue
        rows.append({'source_ref': f'R{len(rows) + 1:04d}', 'text': prefix + line})
        prefix = ''
    if prefix:
        if rows:
            rows[-1]['text'] += prefix
        else:
            rows.append({'source_ref': 'R0001', 'text': prefix})
    return rows


def resolve_document_references(value: dict, rows: list):
    """Project one selected source reference into its coupled display/citation."""
    from copy import deepcopy
    result = deepcopy(value)
    references = {row['source_ref']: row['text'].strip() for row in rows}
    seen_components = set()
    for field in ('components', 'technologies'):
        for item in result.get(field, []):
            reference = item.pop('source_ref', None)
            if reference not in references or not references[reference] or len(references[reference]) > 1200:
                raise ValueError(f'Ungültige Quellenreferenz: {reference}. Nur die übergebenen Referenzen verwenden.')
            if 'source_quote' in item or (field == 'components' and 'name' in item):
                raise ValueError('Name und Zitat werden aus einer Quellenreferenz gebildet; keine freien Quellenfelder zurückgeben.')
            if field == 'components':
                if reference in seen_components:
                    raise ValueError(f'{reference}: eine Quellenangabe nicht mehrfach als verschiedene Geräte/Kategorien ausgeben.')
                seen_components.add(reference)
                label = re.sub(r'^(?:\d+(?:\.\d+)*[.)]?\s+|#{1,6}\s+|[-*]\s+)', '', references[reference])
                label = re.sub(r'^(?:Funktion|Function|Sensor|Aktor|Actuator|Controller|Gateway)\s*:\s*', '', label, flags=re.I)
                item['name'] = label.rstrip('.')[:120]
            item['source_quote'] = references[reference]
    return result


def document_registered_transport_citation(name: str, quote: str, *, profiles=None):
    """Match source-proven aliases without silently choosing a richer variant."""
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    punctuation = str.maketrans({char: '-' for char in '\u2010\u2011\u2012\u2013\u2014\u2212'})
    def normalize(text):
        return text.translate(punctuation).casefold()
    try:
        profile = DEFAULT_TECHNOLOGY_REGISTRY.profile(normalize(name), fields=('id', 'aliases'))
    except KeyError:
        return False
    text = normalize(quote)
    if profiles is None:
        profiles = DEFAULT_TECHNOLOGY_REGISTRY.profiles()
    other_aliases = {normalize(alias) for other in profiles
                     if other['id'] != profile['id'] for alias in [other['id'], *other.get('aliases', [])]}
    for alias in [profile['id'], *profile.get('aliases', [])]:
        label = normalize(alias)
        for match in re.finditer(r'(?<![\w])' + re.escape(label) + r'(?![\w])', text):
            if not any(label in other and len(other) > len(label)
                       and any(outer.start() <= match.start() and outer.end() >= match.end()
                               for outer in re.finditer(r'(?<![\w])' + re.escape(other) + r'(?![\w])', text))
                       for other in other_aliases):
                return True
    return False


def document_device_aliases(source: str):
    return {match[1] for match in re.finditer(r'\b' + _DOCUMENT_CONTROLLER_LABEL + r'\s*\(([A-Z][A-Z0-9_-]{1,15})\)', source, re.I)}


def document_transport_candidates(source: str, profiles, *, context_aliases=None, candidates=None):
    """Registry-owned mentions; controller aliases never prove physical ports."""
    text = re.sub(r'\b' + _DOCUMENT_CONTROLLER_LABEL + r'\s*\([^)]+\)', '', source, flags=re.I)
    text = text.translate(str.maketrans({char: '-' for char in '\u2010\u2011\u2012\u2013\u2014\u2212'}))
    # Requirement IDs are references, not protocol declarations. A known
    # controller acting as a requirement subject is still a device alias.
    text = re.sub(r'\bREQ[-_][\w-]+', '', text, flags=re.I)
    for alias in document_device_aliases(source) if context_aliases is None else context_aliases:
        text = re.sub(r'\b' + re.escape(alias) + r'\b(?=\s+(?:MUSS|MÜSSEN|MUST|SHALL|SOLL)\b)', '', text, flags=re.I)
    return [profile for profile in profiles if candidates is None or profile in candidates
            if document_registered_transport_citation(profile['id'], text, profiles=profiles)]


def document_technology_grounding(schema: dict):
    """Ground model choices with the same source tuples as its output grammar."""
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    choices = {'registered_transports': {}, 'device_aliases': {}}
    for branch in schema['$defs']['DocumentTechnology'].get('oneOf', []):
        kind = branch['properties']['kind']['enum'][0]
        if kind not in {'TRANSPORT', 'DEVICE_ALIAS'}:
            continue
        target = choices['registered_transports' if kind == 'TRANSPORT' else 'device_aliases']
        for name in branch['properties']['name']['enum']:
            identity = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(name) if kind == 'TRANSPORT' else name
            target.setdefault(identity, set()).update(branch['properties']['source_ref']['enum'])
    return {key: {name: sorted(refs) for name, refs in values.items()} for key, values in choices.items()}


def document_output_schema(source: str, base_schema: dict, *, context_aliases=None):
    """Use ASCII source identities, not two independently selected text fields."""
    from copy import deepcopy
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    schema = deepcopy(base_schema)
    rows = [row for row in document_source_references(source)
            if row['text'].strip() and len(row['text'].strip()) <= 1200]
    references = [row['source_ref'] for row in rows]
    if not references:
        # An uninterpretable window is still supplied in full. It cannot
        # contribute fabricated extracted facts or hide a failed later window.
        schema['properties']['components']['maxItems'] = 0
        schema['properties']['technologies']['maxItems'] = 0
        return schema
    profiles = DEFAULT_TECHNOLOGY_REGISTRY.profiles()
    source_aliases = document_device_aliases(source) if context_aliases is None else context_aliases
    available_profiles = document_transport_candidates(source, profiles, context_aliases=source_aliases)
    for definition in ('DocumentComponent',):
        item_schema = schema['$defs'][definition]
        removed = {'source_quote', 'name'} if definition == 'DocumentComponent' else {'source_quote'}
        for field in removed:
            item_schema['properties'].pop(field)
        item_schema['required'] = [field for field in item_schema['required'] if field not in removed] + ['source_ref']
        item_schema['properties']['source_ref'] = {'type': 'string', 'enum': references}
    requirements = [row['source_ref'] for row in rows
                    if re.search(r'^\s*REQ\b|\b(?:muss|müssen|must|shall)\b', row['text'], re.I)]
    component_base = schema['$defs']['DocumentComponent']
    component_branches = []
    for selected, normative in [(requirements, True), ([ref for ref in references if ref not in requirements], False)]:
        if not selected:
            continue
        branch = deepcopy(component_base)
        branch['properties']['source_ref']['enum'] = selected
        if normative:
            branch['properties']['kind'] = {'type': 'string', 'enum': ['REQUIREMENT']}
            branch['properties']['role'] = {'type': 'string', 'enum': ['OTHER']}
            branch['properties']['quantity'] = {'type': 'null'}
        component_branches.append(branch)
    schema['$defs']['DocumentComponent'] = {'oneOf': component_branches}
    # A name, semantic kind and original reference form one allowed tuple.
    # Independent enums allowed valid names to cite unrelated valid rows.
    branches = []
    punctuation = str.maketrans({char: '-' for char in '\u2010\u2011\u2012\u2013\u2014\u2212'})
    def normalize(text):
        return text.translate(punctuation).casefold()
    for row in rows:
        text = row['text']
        labels = {match.group() for match in re.finditer(r'[^\W\d][\w\u2010\u2011\u2012\u2013\u2014\u2212-]*', text)
                  if len(match.group()) <= 80}
        aliases = document_device_aliases(text)
        transports = set()
        normalized_text = text.translate(punctuation)
        for profile in document_transport_candidates(text, profiles, context_aliases=source_aliases, candidates=available_profiles):
            transports.add(profile['id'])
            for alias in [profile['id'], *profile.get('aliases', [])]:
                for match in re.finditer(r'(?<![\w])' + re.escape(alias.translate(punctuation)) + r'(?![\w])', normalized_text, re.I):
                    # Preserve the original spelling, including CAN versus can
                    # and protected hyphens. Do not offer unmentioned aliases
                    # such as CAN 2.0A/B or automotive_ethernet.
                    label = text[match.start():match.end()]
                    if len(label) <= 80:
                        transports.add(label)
        known = {normalize(label) for label in transports | aliases | source_aliases}
        unresolved = {label for label in labels if normalize(label) not in known and not re.match(r'^REQ[-_]', normalize(label), re.I)}
        for kind, names in [('TRANSPORT', transports), ('DEVICE_ALIAS', aliases), ('UNRESOLVED', unresolved)]:
            if names:
                branches.append({'type': 'object', 'additionalProperties': False,
                    'properties': {'name': {'type': 'string', 'enum': sorted(names)},
                                   'kind': {'type': 'string', 'enum': [kind]},
                                   'source_ref': {'type': 'string', 'enum': [row['source_ref']]}},
                    'required': ['name', 'kind', 'source_ref']})
    schema['$defs']['DocumentTechnology'] = {'oneOf': branches} if branches else {'not': {}}
    if not branches:
        schema['properties']['technologies']['maxItems'] = 0
    return schema


def validate_document_interpretation(value, source: str, *, context_aliases=None):
    """Reject invented source claims before displaying a local-model proposal."""
    result = DocumentInterpretation.model_validate(value)
    from backend.nis.agent.tools.inventory_quantities import quantities
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    count_keys = {'SENSOR': 'sensors', 'ACTUATOR': 'actuators', 'CONTROLLER': 'ecus', 'GATEWAY': 'gateways'}
    punctuation = str.maketrans({char: '-' for char in '\u2010\u2011\u2012\u2013\u2014\u2212'})
    def normalized_label(text):
        return text.translate(punctuation).casefold()
    profiles = DEFAULT_TECHNOLOGY_REGISTRY.profiles()
    def transport_citation(item):
        return document_registered_transport_citation(item.name, item.source_quote, profiles=profiles)
    semantic_errors = []
    citation_errors = []
    quote_suggestions = {}
    source_punctuation = source.translate(punctuation)
    for item in [*result.components, *result.technologies]:
        if item.source_quote not in source:
            citation_errors.append(item.name)
            # Suggest the original text only for a unique, character-preserving
            # punctuation match. The changed quote is still rejected.
            candidate = item.source_quote.translate(punctuation)
            position = source_punctuation.find(candidate)
            if position >= 0 and source_punctuation.find(candidate, position + 1) < 0:
                quote_suggestions[item.source_quote] = source[position:position + len(candidate)]
        cited = normalized_label(item.name) in normalized_label(item.source_quote)
        if isinstance(item, DocumentTechnology) and item.kind == 'TRANSPORT':
            try:
                DEFAULT_TECHNOLOGY_REGISTRY.profile(normalized_label(item.name))
            except KeyError:
                pass  # The collected unsupported-transport finding below owns this case.
            else:
                cited = transport_citation(item)
        if not cited:
            semantic_errors.append(f'{item.name}: Die benannte Aussage ist im Quellenzitat nicht belegt.')
    if citation_errors:
        semantic_errors.append('Quellenzitat ist nicht im vollständigen Dokument enthalten: ' + ', '.join(dict.fromkeys(citation_errors)))
        if quote_suggestions:
            semantic_errors.append('Wortgetreue Originalzitate verwenden: ' + repr(list(quote_suggestions.values())))
    for component in result.components:
        logical = re.match(r'\s*(?:Funktion|Function)\s*:', component.source_quote, re.I) or re.search(r'\b[\w-]*(?:fusion|regelung|planung|kontrolle)\b', normalized_label(component.name))
        if component.kind == 'CATEGORY' and component.role == 'OTHER' and logical:
            semantic_errors.append(f'{component.name}: CATEGORY bezeichnet eine Gerätekategorie mit Geräterolle, keine logische Funktion. Funktionen als FUNCTION/OTHER einordnen; keine Hardware aus Funktionslisten ableiten.')
        if component.kind in {'FUNCTION', 'REQUIREMENT'} and component.role != 'OTHER':
            semantic_errors.append(f'{component.name}: Funktionen und Anforderungen benötigen role OTHER; sie bestätigen keine Geräterolle.')
        if component.kind != 'INSTANCE' and component.quantity is not None:
            raise ValueError('Kategorien, Funktionen und Anforderungen bestätigen keine Gerätestückzahl.')
        if component.kind == 'INSTANCE' and re.search(r'^\s*REQ\b|\b(?:muss|müssen|must|shall)\b', component.source_quote, re.I):
            raise ValueError('Ein Anforderungssatz bestätigt keine konkrete Geräteinstanz.')
        if component.quantity and component.quantity > 1:
            key = count_keys.get(component.role)
            if not key or quantities(component.source_quote).get(key, 0) != component.quantity:
                raise ValueError(f'{component.name}: Die Stückzahl ist nicht ausdrücklich belegt.')
    unknown_transports = []
    for technology in result.technologies:
        if technology.kind != 'TRANSPORT':
            continue
        if any(DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(normalized_label(match[1])) == DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(normalized_label(technology.name))
               for match in re.finditer(r'\b' + _DOCUMENT_CONTROLLER_LABEL + r'\s*\(([^)]+)\)', technology.source_quote, re.I)):
            raise ValueError('Ein Controller-Kürzel ist kein physischer Anschluss.')
        try:
            DEFAULT_TECHNOLOGY_REGISTRY.profile(DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(normalized_label(technology.name)))
        except KeyError:
            unknown_transports.append(technology.name)
    if unknown_transports:
        semantic_errors.append('Nicht eindeutig registrierte Transportnamen müssen UNRESOLVED bleiben: '
                               + ', '.join(unknown_transports) + '. Keine unbelegte Variante ergänzen.')
    missing_transports = [profile['id'] for profile in document_transport_candidates(source, profiles, context_aliases=context_aliases)
                          if not any(item.kind == 'TRANSPORT' and DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(normalized_label(item.name)) == profile['id']
                                     for item in result.technologies)]
    if missing_transports:
        semantic_errors.append('Alle eindeutig belegten registrierten Transportvarianten erfassen, ohne Duplikate als Ersatz: '
                               + ', '.join(missing_transports))
    combined_source = re.sub(r'\b(?:Controller|Computer|ECU)\s*\([^)]+\)', lambda match: ' ' * len(match.group()), source)
    for match in re.finditer(r'(?=\b([\w\u2010\u2011\u2012\u2013\u2014\u2212-]+)\s*[/|]\s*([\w\u2010\u2011\u2012\u2013\u2014\u2212-]+)\b)', combined_source):
        try:
            members = {DEFAULT_TECHNOLOGY_REGISTRY.profile(normalized_label(part))['id'] for part in match.groups()}
        except KeyError:
            continue
        if len(members) > 1 and not all(any(item.kind == 'TRANSPORT' and DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(normalized_label(item.name)) == member
                                           for item in result.technologies) for member in members):
            semantic_errors.append('Getrennte registrierte Transportvarianten benötigen eigene TRANSPORT-Einträge: '
                                   + ', '.join(sorted(members)) + '. Keine Variante auf ihre Basis reduzieren; kein gemeinsamer Transportname.')
    missing_aliases = []
    for match in re.finditer(r'\b' + _DOCUMENT_CONTROLLER_LABEL + r'\s*\(([A-Z][A-Z0-9_-]{1,15})\)', source, re.I):
        if not any(item.kind == 'DEVICE_ALIAS' and item.name == match[1]
                   and match.group() in item.source_quote for item in result.technologies):
            missing_aliases.append(match[1])
    if missing_aliases:
        semantic_errors.append('Alle Gerätekürzel brauchen DEVICE_ALIAS mit vollständigem Controller-/Computerzitat: ' + ', '.join(missing_aliases))
    for line in source.splitlines():
        if document_device_aliases(line) and not re.search(r'^\s*REQ\b|\b(?:muss|müssen|must|shall)\b', line, re.I):
            if not any(item.kind == 'INSTANCE' and item.role in {'CONTROLLER', 'GATEWAY'} and line.strip() in item.source_quote
                       for item in result.components):
                semantic_errors.append('Konkret benannten Controller aus seiner eigenen Deklaration als INSTANCE erfassen: ' + line.strip())
    for component in result.components:
        if component.kind in {'INSTANCE', 'CATEGORY'} and re.search(r'\bcontroller\b', normalized_label(component.name)) and component.role not in {'CONTROLLER', 'GATEWAY'}:
            semantic_errors.append(f'{component.name}: ausdrücklich als Controller benannt; role CONTROLLER erforderlich.')
    for line in source.splitlines():
        group = re.match(r'^\s*(?:[-*]\s*)?(Sensorik|Aktorik|Sensor\s+types|Sensortypen|Actuator\s+types|Aktortypen)\s*[:(]', line, re.I)
        if not group:
            continue
        role = 'SENSOR' if group[1].lower().startswith('sensor') else 'ACTUATOR'
        count_key = 'sensors' if role == 'SENSOR' else 'actuators'
        if quantities(line).get(count_key, 0):
            continue
        if not any(item.kind == 'CATEGORY' and item.role == role and line.strip() in item.source_quote for item in result.components):
            semantic_errors.append(f'{group[1]}: unquantifizierte Typenliste braucht CATEGORY, role {role}, quantity null und das vollständige Listen-Zitat; als eine Gruppe zusammenfassen.')
    if semantic_errors:
        raise ValueError(' '.join(semantic_errors))
    for component in result.components:
        if component.kind == 'REQUIREMENT' and re.match(r'\s*(?:Unbekannte\s+)?(?:Schnittstelle|Anschluss)\s*:', component.source_quote, re.I):
            raise ValueError('Eine Anschlussdeklaration gehört in technologies, nicht in REQUIREMENT.')
    if any(item.kind == 'CATEGORY' for item in result.components) and not result.open_questions:
        raise ValueError('Unquantifizierte Gerätekategorien benötigen eine sichtbare Klärung.')
    return result.model_dump(mode='json')


def interpret_project_document(arguments):
    """Native MCP/HTTP entry point; inference creates review data, no model writes."""
    import asyncio
    from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
    request = DocumentIntakeRequest.model_validate({key: value for key, value in arguments.items() if not key.startswith('_')})
    async def run():
        reasoner = LocalEngineeringReasoner()
        try:
            result = await reasoner.interpret_document(request.source, request.source_name)
            result['source_request_id'] = request.source_request_id
            return result
        finally:
            await reasoner.client.aclose()
    return asyncio.run(run())


def is_project_request(prompt: str) -> bool:
    text = prompt.strip()
    if len(text) > 16000 or 'Strukturierte Vorgaben fuer den Engineering-Agenten:' in text:
        return False
    if re.search(r'\b(?:kein(?:e[nsrm]?)?|nicht|no|not)\s+(?:neues?\s+)?(?:projekt|project|anlage|system)\b', text, re.I):
        return False
    if re.match(r'(?:bitte\s+)?(?:wie|warum|zeige|suche|finde|erkläre|prüfe|prüfen|pruefe|validiere|berechne|how|why|show|find|search|check|validate|calculate)\b', text, re.I):
        return False
    # Meta requests must reach the typing/reasoning path even when one of their
    # examples contains a complete hardware inventory.  Otherwise a request
    # such as "Klassifiziere diese Eingaben: ... Erzeuge eine Architektur ..."
    # is incorrectly converted into a project draft.
    if re.match(
        r'(?:bitte\s+)?(?:klassifiziere|klassifizieren|typisiere|ordne\s+die\s+'
        r'eingaben|classify|categorize|type\s+the\s+inputs)\b',
        text,
        re.I,
    ):
        return False
    # A hardware brief is a whole-design request even without the word
    # "project". Requiring that word routed inventories into signal/function
    # generators and silently reduced their scope. At least two quantified
    # device roles distinguish a brief from a single-object operation.
    number = r'(?:\d+|ein(?:e[nsrm]?)?|zwei|drei|vier|fünf|fuenf|sechs|sieben|acht|neun|zehn)'
    qualifier = r'(?:(?:lokale|zentrale[nrms]?|kleinen|digitale|intelligente|elektrische|funktionalen|sicherheitsrelevante|embedded|edge|motion|safety|zone|smart|io-link)\s+){0,3}'
    roles = [
        r'(?:[\w/-]*sensor(?:en|s)?|messstellen|messknoten|encoder|positionsrückführungen)',
        r'(?:[\w/-]*aktor(?:en)?|actuators?|(?:servo|motor)\s+drives?|[\w-]*antriebe|lüfter|schaltelemente)',
        r'(?:[\w/-]*controller|steuerung(?:en)?|[\w/-]*steuerungen?|plcs?|[\w-]*rechner|recheneinheiten|raspberry\s*pi|steuerungs-/rechenknoten)',
    ]
    quantified_roles = sum(bool(re.search(r'\b' + number + r'\s+' + qualifier + role + r'\b', text, re.I)) for role in roles)
    existing_edit = re.search(r'\b(?:lösche|entferne|delete|remove|benenne|rename|verschiebe|move|ändere|aendere|update|modify)\b', text, re.I)
    if quantified_roles >= 2 and not existing_edit:
        return True
    desire = re.search(r'\b(?:ich\s+(?:möchte|moechte|will|brauche|benötige)|i\s+(?:want|need)|'
                       r'erstelle|erzeuge|plane|entwickle|create|build|design)\b', text, re.I)
    project = re.search(r'\b(?:projekt|project|[\w-]*anlage|[\w-]*system)\b', text, re.I)
    equipment = re.search(r'sensor|aktor|actuator|ventil|valve|raspberry|respary|controller', text, re.I)
    brief = re.match(r'(?:(?:ein|das)\s+)?neues?\s+projekt\s+(?:mit|für|fuer)\b|(?:a\s+)?new\s+project\s+(?:with|for)\b', text, re.I)
    return bool((desire or brief) and project and equipment)


def project_intake_text(requirement: str, devices: list[dict] | None = None) -> str:
    """Describe the actual draft inventory without inventing a control chain."""
    if devices is None:
        from backend.nis.agent.tools.project_draft import parse_requirement
        devices = parse_requirement(requirement)['devices']
    labels = {'CONTROLLER': 'Controller', 'GATEWAY': 'Gateways',
              'SENSOR': 'Sensoren', 'ACTUATOR': 'Aktoren'}
    lines = ['Daraus lässt sich ein Projektentwurf entwickeln. Deine Vorgabe:', requirement]
    inventory = []
    for role, label in labels.items():
        members = [device for device in devices if device['role'] == role]
        if members:
            inventory.append(label + ': ' + ', '.join(device['name'] for device in members))
    if inventory:
        lines += ['Geräte im Entwurf:\n' + '\n'.join(inventory)]
    lines += [
        'Geräteaufgaben, Controller-Zuordnungen und das gewünschte Regelungsverhalten '
        'werden anhand deiner Angaben geprüft. Aus einer gemeinsamen Geräteliste '
        'folgt noch keine bestätigte Steuerkette.',
        'Lokale Messwerte und Stellbefehle bleiben im lokalen System; eine Weiterleitung '
        'an andere Systeme wird nur bei ausdrücklich gewünschter Nutzung eingeplant.',
        'Nicht angegebene Anschlüsse, geeignete Ausgangstreiber, Versorgung und '
        'Abtast-/Schaltzeiten bleiben bis zur Klärung offen. Eine direkte elektrische '
        'Ansteuerung ist damit nicht bestätigt.',
        'Du kannst den gespeicherten Entwurf hier ergänzen und einen Modellvorschlag erstellen. '
        'Die Übernahme ins Modell erfordert die Prüfung und Freigabe des konkreten Vorschlags. '
        'Bisher wurde kein Modell angelegt oder verändert.',
    ]
    return '\n\n'.join(lines)
