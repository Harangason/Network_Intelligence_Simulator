

# Reference design is a separate planning result, never a source interpretation.
ReferenceField = Literal['quantity', 'device_type', 'function_hosts', 'ports',
                         'measurements', 'commands', 'communication']


class _ReferenceModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)


class ReferenceSource(_ReferenceModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=180)
    role: Literal['REFERENCE_SUPPLEMENT', 'USER_CLARIFICATION']
    text: str = Field(min_length=1, max_length=DOCUMENT_SOURCE_MAX_CHARS)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    allowed_fields: list[ReferenceField] = Field(min_length=1, max_length=7)


class ReferenceDesignRequest(_ReferenceModel):
    mode: Literal['EXAMPLE_PROJECT']
    prompt: str = Field(min_length=1, max_length=4 * DOCUMENT_SOURCE_MAX_CHARS + 100_000)
    reference_sources: list[ReferenceSource] = Field(default_factory=list, max_length=16)
    source_request_id: str | None = Field(default=None, min_length=8, max_length=120)


class _ReferenceChoice(_ReferenceModel):
    rationale: str = Field(min_length=1, max_length=2000)
    field_references: dict[ReferenceField, list[str]] = Field(default_factory=dict)


class ReferenceDevice(_ReferenceChoice):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    kind: Literal['CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR', 'PHYSICAL_CONTEXT']
    context_kind: Literal['PASSIVE', 'ASSEMBLY', 'SOFTWARE_SERVICE'] | None = None
    quantity: int = Field(strict=True, ge=1, le=1000)
    source_fact_ids: list[str] = Field(min_length=1, max_length=1000)
    owner_device_id: str | None = None
    purpose: str | None = Field(default=None, min_length=1, max_length=500)
    contained_device_ids: list[str] = Field(default_factory=list, max_length=1000)


class ReferenceFunction(_ReferenceChoice):
    source_fact_id: str
    realization: Literal['ATOMIC', 'COMPOSITE']
    executor_device_ids: list[str] = Field(default_factory=list, max_length=1000)
    realized_by_fact_ids: list[str] = Field(default_factory=list, max_length=1000)


class ReferencePort(_ReferenceChoice):
    id: str = Field(min_length=1, max_length=120)
    device_id: str
    technology: str = Field(min_length=1, max_length=80)
    role: Literal['LOCAL', 'BACKBONE']
    network_scope: str = Field(min_length=1, max_length=120)
    parameters: dict = Field(default_factory=dict)


class ReferenceMeasurement(_ReferenceChoice):
    device_id: str
    measurement_id: str = Field(min_length=1, max_length=80)


class ReferenceWireDefinition(_ReferenceModel):
    length_bits: int = Field(strict=True, ge=1, le=524288)
    data_type: Literal['unsigned', 'signed', 'float', 'double', 'float32', 'float64']
    unit: str = Field(min_length=1, max_length=40)
    factor: float
    offset_value: float = 0
    min_value: float | None = None
    max_value: float | None = None
    byte_order: Literal['little_endian', 'big_endian'] = 'little_endian'
    semantic: dict
    data: dict


class ReferenceCommand(_ReferenceChoice):
    device_id: str
    definition: ReferenceWireDefinition


class ReferenceCommunication(_ReferenceChoice):
    id: str = Field(min_length=1, max_length=120)
    producer_device_id: str
    consumer_device_ids: list[str] = Field(min_length=1, max_length=1000)
    producer_fact_id: str | None = None
    consumer_fact_ids: list[str] = Field(default_factory=list, max_length=1000)
    source_port_id: str
    consumer_port_ids: list[str] = Field(min_length=1, max_length=1000)
    scope: Literal['LOCAL_IO', 'DEVICE_IO', 'FUNCTION_OUTPUT']
    role: Literal['MEASUREMENT', 'COMMAND', 'FEEDBACK', 'STATUS', 'FUNCTION_OUTPUT'] | None = None
    signal_name: str = Field(min_length=1, max_length=120)
    encoding: ReferenceWireDefinition
    transmission_mode: Literal['CYCLIC', 'EVENT', 'ON_REQUEST', 'MIXED']
    cycle_ms: float | None = Field(default=None, gt=0)
    min_interval_ms: float | None = Field(default=None, gt=0)
    trigger: Literal['on_change', 'explicit'] | None = None
    trigger_description: str | None = Field(default=None, min_length=1, max_length=500)
    release_times_ms: list[float] | None = Field(default=None, max_length=10000)
    request_source: Literal['bus_message', 'external_application'] | None = None
    request_communication_id: str | None = None
    response_processing_ms: float | None = Field(default=None, ge=0)
    request_times_ms: list[float] | None = Field(default=None, max_length=10000)


class ReferenceFinding(_ReferenceModel):
    code: str = Field(min_length=1, max_length=120)
    target_ref: str = Field(min_length=1, max_length=2000)
    message: str = Field(min_length=1, max_length=2000)


class ReferenceFunctionalDependency(_ReferenceChoice):
    id: str = Field(min_length=1, max_length=120)
    producer_fact_id: str
    consumer_fact_ids: list[str] = Field(min_length=1, max_length=1000)
    executor_device_id: str
    signal_name: str = Field(min_length=1, max_length=120)
    encoding: ReferenceWireDefinition


class ReferenceDesignProposal(_ReferenceModel):
    devices: list[ReferenceDevice] = Field(default_factory=list, max_length=2000)
    functions: list[ReferenceFunction] = Field(default_factory=list, max_length=4000)
    ports: list[ReferencePort] = Field(default_factory=list, max_length=10000)
    measurements: list[ReferenceMeasurement] = Field(default_factory=list, max_length=2000)
    commands: list[ReferenceCommand] = Field(default_factory=list, max_length=2000)
    communication: list[ReferenceCommunication] = Field(default_factory=list, max_length=10000)
    functional_dependencies: list[ReferenceFunctionalDependency] = Field(default_factory=list, max_length=10000)
    unresolved: list[ReferenceFinding] = Field(default_factory=list, max_length=4000)


def reference_design_schema(prepared: dict | None = None) -> dict:
    """Use one public grammar for Qwen candidates and server validation."""
    schema = ReferenceDesignProposal.model_json_schema()
    if prepared is not None:
        schema['$defs']['ReferenceMeasurement']['properties']['measurement_id']['enum'] = [
            item['id'] for item in prepared['catalog']['measurements']]
        schema['$defs']['ReferenceDevice']['properties']['source_fact_ids']['items']['enum'] = list(prepared['facts'])
        schema['$defs']['ReferenceFunction']['properties']['source_fact_id']['enum'] = [
            key for key, fact in prepared['facts'].items() if fact['kind'] == 'FUNCTION']
        schema['$defs']['ReferencePort']['properties']['technology']['enum'] = prepared['catalog']['technology_ids']
    return schema


def _reference_digest(value) -> str:
    import hashlib
    import json
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def prepare_reference_design(arguments: dict) -> dict:
    """Validate full primary evidence and field-scoped supplements without writes."""
    import hashlib
    from backend.nis.agent.context.limits import MAX_REQUIREMENT_LENGTH
    from backend.nis.agent.tools.wizard_generation import reference_design_catalog
    from backend.nis.engineering.projects.project_context import current_project_id
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    request = ReferenceDesignRequest.model_validate(arguments)
    if len(request.prompt) > MAX_REQUIREMENT_LENGTH:
        raise ValueError('Der vollständige Referenzauftrag überschreitet die Auftragsgrenze.')
    if sum(len(source.text) for source in request.reference_sources) > MAX_REQUIREMENT_LENGTH:
        raise ValueError('Die vollständigen Referenzquellen überschreiten die Auftragsgrenze.')
    evidence = reviewed_document_evidence(request.prompt, include_source=True)
    if evidence is None:
        raise ValueError('Eine vollständig geprüfte unveränderte Dokumentquelle ist erforderlich.')
    references = {}
    for source in request.reference_sources:
        if not source.id.strip() or not source.name.strip() or source.id in references:
            raise ValueError('Referenzquellen benötigen eindeutige nichtleere Identitäten.')
        if hashlib.sha256(source.text.encode('utf-8')).hexdigest() != source.source_sha256:
            raise ValueError(f'Referenzquelle {source.id}: vollständiger Quellentext und SHA stimmen nicht überein.')
        if len(set(source.allowed_fields)) != len(source.allowed_fields):
            raise ValueError(f'Referenzquelle {source.id}: doppelte Feldfreigabe.')
        references[source.id] = source.model_dump(mode='json')
    fact_id_map = {'F' + hashlib.sha256(document_fact_identity(fact).encode('utf-8')).hexdigest()[:12]:
                   document_fact_identity(fact) for fact in evidence['components']}
    facts = {'F' + hashlib.sha256(document_fact_identity(fact).encode('utf-8')).hexdigest()[:12]:
             fact for fact in evidence['components']}
    if len(facts) != len(evidence['components']):
        raise ValueError('Die ursprünglichen Quellenbefunde besitzen doppelte Identitäten.')
    payload = request.model_dump(mode='json')
    catalog = reference_design_catalog(request.prompt)
    if not isinstance(catalog, dict) or not catalog.get('measurements'):
        raise ValueError('Der vorhandene Messgrößenkatalog ist nicht verfügbar.')
    _reference_unique(catalog['measurements'], 'id', 'Messgrößenkatalog')
    technology_profiles = DEFAULT_TECHNOLOGY_REGISTRY.profiles()
    catalog['technology_ids'] = sorted(profile['id'] for profile in technology_profiles)
    catalog['technology_catalog_sha256'] = _reference_digest(technology_profiles)
    catalog['technology_parameter_roles_sha256'] = _reference_digest({
        profile['id']: DEFAULT_TECHNOLOGY_REGISTRY.parameter_roles(profile['id']) for profile in technology_profiles})
    catalog_digest = _reference_digest(catalog)
    project_id = current_project_id()
    return {'request': payload, 'project_id': project_id,
            'request_sha256': _reference_digest({'project_id': project_id, 'request': payload, 'catalog': catalog_digest}),
            'catalog': catalog, 'catalog_sha256': catalog_digest,
            'source_sha256': evidence['source_sha256'], 'source_evidence': evidence,
            'facts': facts, 'fact_id_map': fact_id_map, 'reference_sources': references,
            'canonical_writes': False, 'approval_required': True}


def _reference_unique(items: list[dict], field: str, label: str) -> dict:
    result = {}
    for item in items:
        key = item[field]
        if not isinstance(key, str) or not key.strip() or key in result:
            raise ValueError(f'{label}: doppelte oder leere Identität {key!r}.')
        result[key] = item
    return result


def _reference_preserves_fields(previous, candidate, *, field='') -> bool:
    """Retain explicit values, including complete raw-code vocabularies."""
    if isinstance(previous, dict):
        if not isinstance(candidate, dict):
            return False
        if field in {'enum_values', 'reserved_values', 'invalid_values'}:
            return previous == candidate
        return all(key in candidate and _reference_preserves_fields(value, candidate[key], field=key)
                   for key, value in previous.items())
    return previous == candidate


def _reference_wire_compatible(expected: dict, candidate: dict) -> bool:
    """Compare physical and raw encodings, independent of display labels."""
    defaults = {'offset_value': 0, 'byte_order': 'little_endian'}
    for key in ('length_bits', 'data_type', 'unit', 'factor', 'offset_value', 'min_value', 'max_value', 'byte_order'):
        if key in expected or key in defaults:
            if expected.get(key, defaults.get(key)) != candidate.get(key, defaults.get(key)):
                return False
    semantic = expected.get('semantic', {})
    if any(candidate.get('semantic', {}).get(key) != value for key, value in semantic.items() if key != 'meaning'):
        return False
    return _reference_preserves_fields(expected.get('data', {}), candidate.get('data', {}), field='data')


def _reference_acyclic(graph: dict[str, list[str]], label: str) -> None:
    from collections import deque
    incoming = {key: 0 for key in graph}
    for children in graph.values():
        for child in children:
            incoming[child] = incoming.get(child, 0) + 1
    ready = deque(key for key, count in incoming.items() if count == 0)
    visited = 0
    while ready:
        key = ready.popleft()
        visited += 1
        for child in graph.get(key, []):
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    if visited != len(incoming):
        raise ValueError(f'{label}: zyklische Zuordnung.')


def _validate_reference_wire(definition: dict) -> None:
    """Reuse canonical signal checks; never reinterpret physical/raw values."""
    from backend.nis.engineering.signals.signal_integrity import integrity_checks
    from backend.nis.engineering.signals.signal_audit import required_signal_bits
    import math
    if definition['factor'] <= 0:
        raise ValueError('Referenzkodierung: Faktor muss positiv sein.')
    semantic = definition['semantic'].get('semantic_type')
    meaning = definition['semantic'].get('meaning')
    if (not isinstance(meaning, str) or not meaning.strip() or len(meaning) > 2000
            or not isinstance(semantic, str) or semantic not in {
            'NUMERIC', 'STATE', 'ENUM', 'BOOLEAN', 'FLAG', 'COUNTER', 'RAW', 'STRING', 'BYTE_ARRAY'}):
        raise ValueError('Referenzkodierung: explizite Signalbedeutung und bekannte Semantik fehlen.')
    if not definition['unit'].strip():
        raise ValueError('Referenzkodierung: Einheit fehlt.')
    for field, kind in [('enum_values', dict), ('reserved_values', list), ('invalid_values', list)]:
        if field in definition['data'] and not isinstance(definition['data'][field], kind):
            raise ValueError('Referenzkodierung: Value-Domain besitzt eine ungültige Struktur.')
    errors = integrity_checks(definition)
    if errors:
        raise ValueError('Referenzkodierung: ' + '; '.join(item['code'] for item in errors))
    bits = definition['length_bits']
    if semantic == 'NUMERIC':
        lo, hi = definition.get('min_value'), definition.get('max_value')
        if lo is None or hi is None or lo >= hi:
            raise ValueError('Referenzkodierung: vollständiger physikalischer Wertebereich fehlt.')
        if definition['data_type'] in {'float', 'float32', 'double', 'float64'}:
            expected = 64 if definition['data_type'] in {'double', 'float64'} else 32
            if bits != expected:
                raise ValueError('Referenzkodierung: Gleitkommaformat und Bitlänge widersprechen sich.')
        else:
            required = required_signal_bits(definition)
            # required_signal_bits owns scaling/offset and raw-width reasoning.
            if required is None or required > bits or bits > 64:
                raise ValueError('Referenzkodierung: Wertebereich passt nicht in die Rohkodierung.')
            for value in (lo, hi):
                raw = (value - definition['offset_value']) / definition['factor']
                lower = -(2 ** (bits - 1)) if definition['data_type'] == 'signed' else 0
                upper = 2 ** (bits - (1 if definition['data_type'] == 'signed' else 0)) - 1
                if not math.isfinite(raw) or not lower <= raw <= upper:
                    raise ValueError('Referenzkodierung: Rohwerte außerhalb des Datentyps.')
    elif semantic in {'STATE', 'ENUM', 'BOOLEAN', 'FLAG'}:
        if not definition['data'].get('enum_values') or bits > 64:
            raise ValueError('Referenzkodierung: diskrete Value-Domain fehlt.')


def reference_transmission_contract(item: dict, *, message_refs: dict | None = None) -> dict:
    """Project authored scenario release fields into the existing native model."""
    contract = {'mode': item['transmission_mode']}
    for source, target in [('cycle_ms', 'period_ms'), ('min_interval_ms', 'minimum_interval_ms'),
                           ('trigger', 'trigger'), ('trigger_description', 'trigger_description'),
                           ('release_times_ms', 'release_times_ms'), ('request_source', 'request_source'),
                           ('response_processing_ms', 'response_processing_ms'), ('request_times_ms', 'request_times_ms')]:
        if item.get(source) is not None:
            contract[target] = item[source]
    if item.get('request_communication_id'):
        identifier = item['request_communication_id']
        contract['request_message_ref'] = (message_refs or {}).get(identifier, identifier)
    return contract


def validate_reference_design(result: dict, prepared: dict) -> dict:
    return _validate_reference_design(result, prepared)


def validate_reference_design_profile(result: dict, prepared: dict, profile) -> dict:
    """Internal planner feedback only; final acceptance always validates all profiles."""
    if not isinstance(profile, (list, tuple)) or any(not isinstance(value, str) for value in profile):
        raise ValueError('Profilprüfung benötigt eine ursprüngliche Systemidentität.')
    return _validate_reference_design(result, prepared, profile=tuple(profile))


def _validate_reference_design(result: dict, prepared: dict, *, profile=None) -> dict:
    """Stamp a detached review candidate; no approval, model writes or readiness."""
    from copy import deepcopy
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    # Revalidate the complete primary input, not caller-supplied prepared facts.
    current = prepare_reference_design(prepared['request'])
    if current['request_sha256'] != prepared.get('request_sha256'):
        raise ValueError('Der Referenzentwurf gehört zu einer veralteten Auftragsrevision.')
    full_source = deepcopy(current['source_evidence'])
    full_protected = {field: deepcopy(current['catalog'].get('confirmed_' + field, {}))
                      for field in ('commands', 'measurements', 'connections', 'owners')}
    if profile is not None:
        if profile not in {tuple(document_system_scope(fact.get('source_context', [])))
                           for fact in current['facts'].values() if fact['kind'] != 'REQUIREMENT'}:
            raise ValueError('Profilprüfung darf keine neue oder verkürzte Systemidentität erfinden.')
        current['facts'] = {key: fact for key, fact in current['facts'].items()
            if tuple(document_system_scope(fact.get('source_context', []))) == profile
            or fact['kind'] == 'REQUIREMENT' and not document_system_scope(fact.get('source_context', []))}
        current['source_evidence']['answers'] = [answer for answer in full_source['answers']
            if tuple(document_system_scope(answer.get('source_context', []))) == profile]
        current['catalog']['source_devices'] = [row for row in current['catalog'].get('source_devices', [])
            if tuple(document_system_scope((row.get('evidence') or {}).get('source_context', []))) == profile]
        aliases = current['catalog'].get('name_aliases', {})
        names = [fact['name'] for fact in current['facts'].values() if fact['kind'] in {'CATEGORY', 'INSTANCE'}]
        names.extend(row['name'] for row in current['catalog']['source_devices'])
        identities = {aliases.get(name, name.casefold()) for name in names}
        for field in full_protected:
            current['catalog']['confirmed_' + field] = {name: choice for name, choice in full_protected[field].items()
                if aliases.get(name, name.casefold()) in identities}
    value = ReferenceDesignProposal.model_validate(result).model_dump(mode='json')
    _reference_digest(value)  # Reject non-JSON or nonfinite nested data as well.
    facts, sources = current['facts'], current['reference_sources']
    devices = _reference_unique(value['devices'], 'id', 'Teilnehmer')
    functions = _reference_unique(value['functions'], 'source_fact_id', 'Funktionen')
    ports = _reference_unique(value['ports'], 'id', 'Anschlüsse')
    _reference_unique(value['communication'], 'id', 'Kommunikation')
    _reference_unique(value['functional_dependencies'], 'id', 'Funktionsabhängigkeiten')
    _reference_unique(value['measurements'], 'device_id', 'Messgrößen')
    _reference_unique(value['commands'], 'device_id', 'Stellbefehle')
    findings = value['unresolved']
    qualification_findings = []
    scopes, bound = {}, {}
    decision_evidence = []
    aliases = current['catalog'].get('name_aliases', {})

    def name_identity(name):
        return aliases.get(name, name.casefold())

    def scope(fact_id):
        if fact_id not in facts:
            raise ValueError(f'Unbekannter ursprünglicher Quellenbefund {fact_id}.')
        return tuple(document_system_scope(facts[fact_id].get('source_context', [])))

    def same_scope(ids, expected):
        if any(scope(fact_id) != expected for fact_id in ids):
            raise ValueError('Referenzentwurf überschreitet ursprüngliche System-/Profilgrenzen.')

    def stamp(item, fields, target, fact_ids):
        if not item['rationale'].strip():
            raise ValueError('Jede Referenzannahme benötigt eine fachliche Begründung.')
        if set(item['field_references']) - set(fields):
            raise ValueError('Referenzbeleg wurde einem fremden Entscheidungsfeld zugeordnet.')
        for field in fields:
            reference_ids = item['field_references'].get(field, [])
            if len(reference_ids) != len(set(reference_ids)):
                raise ValueError('Doppelte Referenzbelege für ein Entscheidungsfeld.')
            for reference_id in reference_ids:
                if reference_id not in sources or field not in sources[reference_id]['allowed_fields']:
                    raise ValueError('Referenzquelle darf dieses Entscheidungsfeld nicht ergänzen.')
            decision_evidence.append({'kind': 'REFERENCE_ASSUMPTION', 'target_ref': target,
                'field': field, 'rationale': item['rationale'], 'source_fact_ids': fact_ids,
                'source_fact_kinds': {fact_id: facts[fact_id]['kind'] for fact_id in fact_ids},
                'reference_sources': [{'id': reference_id, 'role': sources[reference_id]['role'],
                    'source_sha256': sources[reference_id]['source_sha256']} for reference_id in reference_ids]})

    for device_id, device in devices.items():
        ids = device['source_fact_ids']
        if len(ids) != len(set(ids)):
            raise ValueError('Teilnehmer besitzt doppelte Quellenbindungen.')
        device_scope = scope(ids[0])
        same_scope(ids, device_scope)
        scopes[device_id] = device_scope
        if not device['name'].strip():
            raise ValueError('Ein Referenzteilnehmer benötigt einen Namen.')
        physical = device['kind'] == 'PHYSICAL_CONTEXT'
        if not physical and device['quantity'] != 1:
            raise ValueError('Elektronische Referenzteilnehmer benötigen einzelne Identitäten, Anschlüsse und Ausführer; Gruppenmenge ist keine Adressierung.')
        if physical != bool(device['context_kind']) or (device['contained_device_ids'] and not physical):
            raise ValueError('Physischer/Software-Kontext benötigt eine explizite getrennte Realisierung.')
        for fact_id in ids:
            fact = facts[fact_id]
            # Requirements/functions may motivate *proposed* additional devices.
            # They remain their original kinds in source_evidence; this binding
            # never promotes them into confirmed source inventory.
            if fact['role'] != 'OTHER' and device['kind'] != fact['role']:
                raise ValueError('Belegte Geräteart darf durch die Referenzannahme nicht ersetzt werden.')
            bound.setdefault(fact_id, []).append(device_id)
        device_fields = ['quantity', 'device_type']
        if device['owner_device_id'] is not None:
            device_fields.append('function_hosts')
        stamp(device, device_fields, device_id, ids)
    names = [name_identity(device['name']) for device in devices.values()]
    if len(names) != len(set(names)):
        raise ValueError('Referenzteilnehmer benötigen projektweit eindeutige Namen.')
    for device_id, device in devices.items():
        for child in device['contained_device_ids']:
            if child not in devices or scopes[child] != scopes[device_id]:
                raise ValueError('Kontextbindung verweist auf fremden oder unbekannten Teilnehmer.')
        owner = device['owner_device_id']
        if owner is not None and (device['kind'] not in {'SENSOR', 'ACTUATOR', 'PHYSICAL_CONTEXT'}
                or owner not in devices or devices[owner]['kind'] not in {'CONTROLLER', 'GATEWAY'}
                or scopes[owner] != scopes[device_id]):
            raise ValueError('Lokale Gerätezuordnung benötigt einen Controller im selben Profil.')
        if device['kind'] == 'PHYSICAL_CONTEXT' and not device['contained_device_ids'] and owner is None:
            findings.append({'code': 'REFERENCE_CONTEXT_UNBOUND', 'target_ref': device_id,
                'message': 'Passiver, Baugruppen- oder Softwarekontext benötigt eine explizite Zuordnung zu seinen tatsächlichen Geräten, damit er im kanonischen Modell erhalten bleibt.'})
    _reference_acyclic({key: item['contained_device_ids'] for key, item in devices.items()}, 'Kontextbindung')
    for fact_id, fact in facts.items():
        if fact['kind'] not in {'CATEGORY', 'INSTANCE'}:
            continue
        represented = bound.get(fact_id, [])
        if not represented:
            findings.append({'code': 'REFERENCE_INVENTORY_UNCOVERED', 'target_ref': fact_id,
                             'message': 'Ursprünglicher Gerätebefund ist im Referenzentwurf noch nicht abgebildet.'})
        if fact['kind'] == 'INSTANCE' and represented:
            count = sum(devices[device_id]['quantity'] for device_id in represented)
            if count != fact['quantity']:
                raise ValueError('Explizite ursprüngliche Instanzmenge darf nicht ersetzt werden.')
            expected_names = {name_identity(row['name']) for row in current['catalog'].get('source_devices', [])
                if (row.get('evidence') or {}).get('source_quote') == fact['source_quote']
                and (row.get('evidence') or {}).get('source_context', []) == fact.get('source_context', [])}
            if expected_names and {name_identity(devices[key]['name']) for key in represented} != expected_names:
                raise ValueError('Explizite ursprüngliche Instanzidentität muss im bestehenden quellenbezogenen Namenspfad erhalten bleiben.')
    for answer in current['source_evidence']['answers']:
        if answer.get('coverage_confirmed'):
            continue
        matching = [fact_id for fact_id, fact in facts.items() if fact['kind'] == 'CATEGORY'
                    and fact['name'] == answer.get('label')
                    and fact.get('source_context', []) == answer.get('source_context', [])]
        if not matching:
            findings.append({'code': 'REFERENCE_REVIEWED_INVENTORY_UNMAPPED', 'target_ref': str(answer.get('id') or 'inventory'),
                             'message': 'Die vorher bestätigte Geräteentscheidung benötigt eine eindeutige Quellenbindung.'})
            continue
        represented = {device_id for fact_id in matching for device_id in bound.get(fact_id, [])
                       if devices[device_id]['kind'] != 'PHYSICAL_CONTEXT'}
        quantity = answer.get('quantity')
        if type(quantity) is not int or quantity < 0 or quantity > 1000:
            raise ValueError('Vorherige bestätigte Geräteentscheidung besitzt keine gültige Menge.')
        count = sum(devices[device_id]['quantity'] for device_id in represented)
        if (answer.get('minimum') and count < quantity) or (not answer.get('minimum') and count != quantity):
            raise ValueError('Vorher bestätigte Gerätemenge darf nicht ersetzt oder unterschritten werden.')
        if any(answer.get('role') and devices[device_id]['kind'] != answer['role'] for device_id in represented):
            raise ValueError('Vorher bestätigte Geräteart darf nicht ersetzt werden.')

    for fact_id, function in functions.items():
        if fact_id not in facts or facts[fact_id]['kind'] != 'FUNCTION':
            raise ValueError('Funktionsrealisierung benötigt einen ursprünglichen Funktionsbefund.')
        executors, children = function['executor_device_ids'], function['realized_by_fact_ids']
        confirmed_assignments = {**current['catalog'].get('source_function_assignments', {}),
                                 **current['source_evidence']['function_assignments']}
        confirmed = confirmed_assignments.get(current['fact_id_map'][fact_id])
        if confirmed and function['realization'] != 'ATOMIC':
            raise ValueError('Bereits bestätigte atomare Funktionszuordnung darf nicht ersetzt werden.')
        if len(executors) != len(set(executors)) or len(children) != len(set(children)):
            raise ValueError('Doppelte Funktionsrealisierung.')
        if function['realization'] == 'ATOMIC':
            if not executors or children:
                raise ValueError('Atomare Funktion benötigt Ausführer und keine zusammengesetzten Teilverweise.')
            for executor in executors:
                if executor not in devices or devices[executor]['kind'] not in {'CONTROLLER', 'GATEWAY'}:
                    raise ValueError('Funktionsausführer ist kein elektronischer Controller.')
                if scopes[executor] != scope(fact_id):
                    raise ValueError('Funktionsausführer überschreitet die ursprüngliche Profilgrenze.')
            if confirmed and {name_identity(devices[key]['name']) for key in executors} != {name_identity(confirmed)}:
                raise ValueError('Bereits bestätigter Funktionsausführer darf nicht ersetzt werden.')
        elif executors or not children or any(child not in functions for child in children):
            raise ValueError('Zusammengesetzte Funktion benötigt gültige Teilfunktionen und keinen eigenen Ausführer.')
        same_scope(children, scope(fact_id))
        stamp(function, ['function_hosts'], fact_id, [fact_id])
    _reference_acyclic({key: item['realized_by_fact_ids'] for key, item in functions.items()}, 'Funktionsabdeckung')
    for fact_id, fact in facts.items():
        if fact['kind'] == 'FUNCTION' and fact_id not in functions:
            findings.append({'code': 'REFERENCE_FUNCTION_UNCOVERED', 'target_ref': fact_id,
                             'message': 'Ursprünglicher Funktionsbefund benötigt noch eine Realisierung.'})

    def electronic(device_id, kinds=None):
        if device_id not in devices or devices[device_id]['kind'] == 'PHYSICAL_CONTEXT':
            raise ValueError('Kommunikation benötigt einen realisierbaren elektronischen Teilnehmer.')
        if kinds and devices[device_id]['kind'] not in kinds:
            raise ValueError('Entscheidung passt nicht zur Geräteart.')
        return devices[device_id]

    network_scopes = {}
    for port_id, port in ports.items():
        device = electronic(port['device_id'])
        network_identity = (scopes[port['device_id']], port['technology'])
        if port['network_scope'] in network_scopes and network_scopes[port['network_scope']] != network_identity:
            raise ValueError('Netzsegmentidentität darf keine Profile oder fremden Technologien zusammenführen.')
        network_scopes[port['network_scope']] = network_identity
        identity = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(port['technology'])
        try:
            DEFAULT_TECHNOLOGY_REGISTRY.profile(identity)
        except (KeyError, ValueError) as error:
            raise ValueError('Referenzanschluss benötigt eine registrierte Technologie.') from error
        if identity != port['technology']:
            raise ValueError('Referenzanschluss benötigt die kanonische Technologieidentität.')
        roles = DEFAULT_TECHNOLOGY_REGISTRY.parameter_roles(identity)
        normalized_parameters = DEFAULT_TECHNOLOGY_REGISTRY.normalize_parameters(identity, port['parameters'])
        for parameter in normalized_parameters:
            if roles.get(parameter) != 'CONFIGURATION':
                raise ValueError(f'Referenzanschluss {port_id}: {parameter} ist kein zulässiger CONFIGURATION-Wert; Qwen darf keine Hardware-, Referenz- oder Abnahmebelege erzeugen.')
        review = DEFAULT_TECHNOLOGY_REGISTRY.validate_parameters(identity, port['parameters'])
        for finding in review.get('findings', []):
            parameter = finding.get('parameter')
            if finding.get('code') == 'TECHNOLOGY_PARAMETER_MISSING' and roles.get(parameter) in {'EVIDENCE', 'REFERENCE'}:
                qualification_findings.append({'target_ref': port_id, 'technology': identity,
                    'parameter': parameter, 'value_role': roles[parameter],
                    'qualification': 'UNVERIFIED', 'hardware_evidence': False, 'finding': deepcopy(finding)})
                continue
            if finding.get('severity') in {'ERROR', 'BLOCKER', 'OPEN', 'REVIEW'}:
                findings.append({'code': 'REFERENCE_PORT_' + finding.get('code', 'REVIEW_REQUIRED'),
                    'target_ref': port_id, 'message': finding.get('message') or str(finding)})
        stamp(port, ['ports'], port_id, device['source_fact_ids'])
    for field, kind in [('measurements', 'SENSOR'), ('commands', 'ACTUATOR')]:
        for item in value[field]:
            device = electronic(item['device_id'], {kind})
            if field == 'commands':
                _validate_reference_wire(item['definition'])
            elif item['measurement_id'] not in {row['id'] for row in current['catalog']['measurements']}:
                raise ValueError('Messgröße gehört nicht zum vorhandenen Messgrößenkatalog.')
            stamp(item, [field], item['device_id'], device['source_fact_ids'])
    for item in value['communication']:
        producer = electronic(item['producer_device_id'])
        consumers = item['consumer_device_ids']
        if len(consumers) != len(set(consumers)):
            raise ValueError('Doppelte Kommunikationsempfänger.')
        if item['producer_device_id'] in consumers:
            raise ValueError('Lokale Verarbeitung ist kein physischer Selbsttransport.')
        for consumer in consumers:
            electronic(consumer)
            if scopes[consumer] != scopes[item['producer_device_id']]:
                raise ValueError('Kommunikation überschreitet unabhängige ursprüngliche Profilgrenzen.')
        function_ids = [*item['consumer_fact_ids'], *([item['producer_fact_id']] if item['producer_fact_id'] else [])]
        if any(fact_id not in functions for fact_id in function_ids):
            raise ValueError('Kommunikation verweist auf unbekannte Funktionsrealisierung.')
        if any(functions[fact_id]['realization'] != 'ATOMIC' for fact_id in function_ids):
            raise ValueError('Physische Kommunikation benötigt konkrete atomare Funktionspartner, keine Zusammenfassung.')
        same_scope(function_ids, scopes[item['producer_device_id']])
        def executors(fact_id):
            pending, seen, hosts = [fact_id], set(), set()
            while pending:
                current_id = pending.pop()
                if current_id in seen:
                    continue
                seen.add(current_id)
                function = functions[current_id]
                hosts.update(function['executor_device_ids'])
                pending.extend(function['realized_by_fact_ids'])
            return hosts
        if item['producer_fact_id'] and item['producer_device_id'] not in executors(item['producer_fact_id']):
            raise ValueError('Funktionaler Sender passt nicht zum bestätigten Referenzausführer.')
        if any(not executors(fact_id).intersection(consumers) for fact_id in item['consumer_fact_ids']):
            raise ValueError('Funktionaler Empfänger passt nicht zum bestätigten Referenzausführer.')
        if item['scope'] == 'LOCAL_IO':
            owners = {key if devices[key]['kind'] in {'CONTROLLER', 'GATEWAY'} else devices[key]['owner_device_id']
                      for key in [item['producer_device_id'], *consumers]}
            if None in owners or len(owners) != 1:
                raise ValueError('Lokale Kommunikation darf ihre bestätigte Gerätezuordnung nicht verlassen.')
        if item['source_port_id'] not in ports or ports[item['source_port_id']]['device_id'] != item['producer_device_id']:
            raise ValueError('Kommunikation benötigt den tatsächlichen Senderanschluss.')
        if len(item['consumer_port_ids']) != len(consumers) or len(set(item['consumer_port_ids'])) != len(consumers):
            raise ValueError('Kommunikation benötigt je Empfänger einen eindeutigen Anschluss.')
        for consumer, port_id in zip(consumers, item['consumer_port_ids']):
            if port_id not in ports or ports[port_id]['device_id'] != consumer:
                raise ValueError('Kommunikation benötigt den tatsächlichen Empfängeranschluss.')
        if item['transmission_mode'] in {'CYCLIC', 'MIXED'} and item['cycle_ms'] is None:
            raise ValueError('Zyklischer Referenzverkehr benötigt einen expliziten Zyklus.')
        if item['transmission_mode'] == 'CYCLIC' and item['trigger']:
            raise ValueError('Ereignisanteil benötigt einen entsprechenden Übertragungsmodus.')
        if item['transmission_mode'] != 'CYCLIC' and (not item['trigger'] or not item['trigger'].strip() or item['min_interval_ms'] is None):
            if item['transmission_mode'] != 'ON_REQUEST':
                raise ValueError('Ereignisverkehr benötigt Auslöser und Mindestabstand; kein erfundener periodischer Ersatz.')
        from backend.nis.engineering.capacity.transmission import profile as transmission_profile
        release = transmission_profile(reference_transmission_contract(item), item['cycle_ms'])
        if release['errors']:
            raise ValueError('Referenz-Sendeverhalten: ' + '; '.join(release['errors']))
        if item['transmission_mode'] == 'ON_REQUEST' and item['request_source'] == 'bus_message':
            request = next((row for row in value['communication'] if row['id'] == item['request_communication_id']), None)
            if (request is None or request['id'] == item['id']
                    or item['producer_device_id'] not in request['consumer_device_ids']
                    or request['producer_device_id'] not in consumers):
                raise ValueError('Busantwort benötigt die zugehörige tatsächliche Anfrage im selben Kommunikationsmodell.')
        _validate_reference_wire(item['encoding'])
        role = item['role'] or ('MEASUREMENT' if producer['kind'] == 'SENSOR' else
            'FEEDBACK' if producer['kind'] == 'ACTUATOR' else
            'COMMAND' if all(devices[key]['kind'] == 'ACTUATOR' for key in consumers) else 'FUNCTION_OUTPUT')
        wire = item['encoding']
        if role == 'COMMAND':
            actuators = [devices[key] for key in consumers if devices[key]['kind'] == 'ACTUATOR']
            if not actuators:
                raise ValueError('Stellbefehl benötigt einen tatsächlichen Aktorempfänger.')
            for actuator in actuators:
                command = next((row['definition'] for row in value['commands'] if row['device_id'] == actuator['id']), None)
                if command is None:
                    command = next((definition for name, definition in current['catalog'].get('confirmed_commands', {}).items()
                                    if name_identity(name) == name_identity(actuator['name'])), None)
                if command is None or not _reference_wire_compatible(command, wire):
                    raise ValueError('Kommunikationskodierung passt nicht zur Stellgröße des Aktorempfängers.')
        if role == 'MEASUREMENT':
            if producer['kind'] != 'SENSOR':
                raise ValueError('Messdaten benötigen einen tatsächlichen Sensorproduzenten.')
            measurement = next((row['measurement_id'] for row in value['measurements'] if row['device_id'] == producer['id']), None)
            if measurement is None:
                measurement = next((choice for name, choice in current['catalog'].get('confirmed_measurements', {}).items()
                                    if name_identity(name) == name_identity(producer['name'])), None)
            measurement_profile = next((row for row in current['catalog']['measurements'] if row['id'] == measurement), None)
            expected_semantics = ({measurement_profile['semanticType']} if measurement_profile and 'semanticType' in measurement_profile else
                                  {'STATE', 'ENUM', 'BOOLEAN', 'FLAG'} if measurement_profile and measurement_profile['unit'] in {'code', 'state'} else {'NUMERIC'})
            if (measurement_profile is None or measurement_profile['unit'] != wire['unit']
                    or wire['semantic']['semantic_type'] not in expected_semantics
                    or ('payloadBytes' in measurement_profile and measurement_profile['payloadBytes'] * 8 != wire['length_bits'])):
                raise ValueError('Kommunikationskodierung passt nicht zur gewählten Messgröße.')
        stamp(item, ['communication'], item['id'], producer['source_fact_ids'])
    for item in value['functional_dependencies']:
        electronic(item['executor_device_id'], {'CONTROLLER', 'GATEWAY'})
        producer = item['producer_fact_id']
        consumers = item['consumer_fact_ids']
        if len(consumers) != len(set(consumers)) or producer in consumers:
            raise ValueError('Funktionsabhängigkeit benötigt getrennte eindeutige Funktionspartner.')
        for fact_id in [producer, *consumers]:
            if fact_id not in functions or functions[fact_id]['realization'] != 'ATOMIC':
                raise ValueError('Lokale Funktionsabhängigkeit benötigt bekannte atomare Funktionen.')
            if item['executor_device_id'] not in functions[fact_id]['executor_device_ids']:
                raise ValueError('Lokale Funktionsabhängigkeit benötigt denselben tatsächlichen Ausführer.')
        same_scope([producer, *consumers], scopes[item['executor_device_id']])
        _validate_reference_wire(item['encoding'])
        stamp(item, ['communication'], item['id'], [producer, *consumers])
    # The planner fills gaps. Omitting an unchanged old choice inherits it from
    # the original request; supplying a candidate may add missing fields but
    # cannot rewrite explicit values, vocabularies, recipients or ports.
    participants = {name_identity(device['name']): device_id for device_id, device in devices.items()}
    commands = {item['device_id']: item['definition'] for item in value['commands']}
    measurements = {item['device_id']: item['measurement_id'] for item in value['measurements']}
    protected_fields = {}
    for field in ('commands', 'measurements', 'connections', 'owners'):
        previous = current['catalog'].get('confirmed_' + field, {})
        protected_fields[field] = deepcopy(previous)
        for name, existing_choice in previous.items():
            if field == 'connections' and str(existing_choice).casefold() in {'other', 'unknown', ''}:
                continue
            device_id = participants.get(name_identity(name))
            if device_id is None or devices[device_id]['kind'] == 'PHYSICAL_CONTEXT':
                raise ValueError('Ein zuvor bestätigter Teilnehmer darf nicht entfallen oder umbenannt werden.')
            if field == 'commands' and device_id in commands and not _reference_preserves_fields(existing_choice, commands[device_id]):
                raise ValueError('Vorher bestätigte Aktorkodierung darf nicht überschrieben werden.')
            if field == 'measurements' and device_id in measurements and existing_choice != measurements[device_id]:
                raise ValueError('Vorher bestätigte Messgröße darf nicht überschrieben werden.')
            if field == 'connections':
                expected = existing_choice if isinstance(existing_choice, list) else [existing_choice]
                proposed = {port['technology'] for port in ports.values() if port['device_id'] == device_id}
                if not proposed:
                    findings.append({'code': 'REFERENCE_CONFIRMED_PORT_UNPLANNED', 'target_ref': device_id,
                        'message': 'Vorher bestätigter Anschluss benötigt im Referenzentwurf seine konkrete physische Portidentität.'})
                if proposed and not {DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(item) for item in expected}.issubset(proposed):
                    raise ValueError('Vorher bestätigte Anschlüsse dürfen nicht ersetzt werden.')
            if field == 'owners' and devices[device_id]['owner_device_id'] is not None:
                owner_name = devices[devices[device_id]['owner_device_id']]['name']
                if name_identity(owner_name) != name_identity(existing_choice):
                    raise ValueError('Vorher bestätigte Gerätezuordnung darf nicht ersetzt werden.')
    return {'schema_version': 1, 'status': 'REVIEW_REQUIRED', 'mode': 'EXAMPLE_PROJECT',
        'project_id': current['project_id'],
        'request_sha256': current['request_sha256'], 'source_sha256': current['source_sha256'],
        'source_evidence': full_source,
        'request': deepcopy(current['request']), 'fact_id_map': deepcopy(current['fact_id_map']),
        'catalog_sha256': current['catalog_sha256'],
        'protected_fields': full_protected,
        'reference_sources': deepcopy(current['reference_sources']),
        'proposal': value, 'decision_evidence': decision_evidence,
        'processing_evidence': 'NONE', 'timing_evidence': 'NONE',
        'hardware_evidence': False, 'qualification': 'UNVERIFIED', 'qualification_findings': qualification_findings,
        'coverage': {'inventory_fact_ids': [key for key, fact in facts.items() if fact['kind'] in {'INSTANCE', 'CATEGORY'}],
            'function_fact_ids': [key for key, fact in facts.items() if fact['kind'] == 'FUNCTION'],
            'requirement_fact_ids': [key for key, fact in facts.items() if fact['kind'] == 'REQUIREMENT'],
            'inventory_bindings': {key: ids for key, ids in bound.items() if facts[key]['kind'] in {'INSTANCE', 'CATEGORY'}},
            'derived_device_bindings': {key: ids for key, ids in bound.items() if facts[key]['kind'] in {'FUNCTION', 'REQUIREMENT'}}},
        'canonical_writes': False, 'approval_required': True,
        **({'validation_scope': 'PROFILE_ONLY', 'source_profile': list(profile)} if profile is not None else {})}
