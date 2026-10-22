"""Recognize project design requests without pretending that a search creates a model."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.nis.agent.context.limits import MAX_DOCUMENT_SOURCE_CHARS

DOCUMENT_SOURCE_MAX_CHARS = MAX_DOCUMENT_SOURCE_CHARS
# JSON can escape one non-BMP character as two six-byte surrogate escapes.
DOCUMENT_REQUEST_MAX_BYTES = 12 * DOCUMENT_SOURCE_MAX_CHARS + 16_384

_DOCUMENT_CONTROLLER_LABEL = r'(?:Controller|Computer|ECU|Steuergerät|Steuergeraet|Rechner|PLC|SPS|Gateway)'
_DOCUMENT_TRANSPORT_QUALIFIER = r'\s*[- ]?(?:ähnlich\w*|aehnlich\w*|like|artig\w*|optional\w*|möglich\w*|moeglich\w*)\b'
_DOCUMENT_ACTION = r'\b(?:erkennen|behandeln|verarbeitet|verarbeiten|steuert|steuern|erfasst|erfassen|überwachen|überwacht|bereitstellen|bereitstellt|protokollieren|sicherstellen|verwalten|detects?|process(?:es)?|controls?|monitors?|provides?)\b'


class DocumentComponent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    kind: Literal['INSTANCE', 'CATEGORY', 'FUNCTION', 'REQUIREMENT']
    role: Literal['CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR', 'OTHER']
    quantity: int | None = Field(default=None, ge=1, le=1000)
    source_quote: str = Field(min_length=1, max_length=1200)
    source_context: list[str] = Field(default_factory=list, max_length=64)


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
    source: str = Field(min_length=1, max_length=DOCUMENT_SOURCE_MAX_CHARS)
    source_name: str = Field(default='Projektbeschreibung', min_length=1, max_length=180)
    source_request_id: str | None = Field(default=None, min_length=8, max_length=80)


class DocumentProposalInterpretation(DocumentInterpretation):
    """Union of validated sections; per-inference limits do not cap the union."""
    components: list[DocumentComponent] = Field(default_factory=list)
    technologies: list[DocumentTechnology] = Field(default_factory=list)


def compose_document_proposal(parts: list[dict]):
    """Build a global review task from Qwen facts, never from local absences.

    A section's prose only knows that section. Its missing-context questions and
    assumptions cannot be promoted to assertions about the complete document.
    Keep the source-bound facts and derive the review steps from their union.
    """
    import json
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY

    components = list({json.dumps(item, sort_keys=True, ensure_ascii=False): item
                       for part in parts for item in part['components']}.values())
    technologies = list({(item['kind'], DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(item['name'])
                          if item['kind'] == 'TRANSPORT' else item['name'].casefold()): item
                         for part in parts for item in part['technologies']}.values())
    instances = [item for item in components if item['kind'] == 'INSTANCE']
    instance_count = sum(item.get('quantity') or 1 for item in instances)
    categories = [item for item in components if item['kind'] == 'CATEGORY']
    functions = [item for item in components if item['kind'] == 'FUNCTION']
    requirements = [item for item in components if item['kind'] == 'REQUIREMENT']
    unresolved = [item['name'] for item in technologies if item['kind'] == 'UNRESOLVED']
    task = ['Engineering-Vorschlag anhand der vollständigen quellengebundenen Qwen-Befunde prüfen.']
    if instances:
        if instance_count == len(instances):
            task.append(f'Die {instance_count} konkret benannten Geräte als Instanzen übernehmen und ihre Anschlüsse sowie Funktionszuordnungen bestätigen.')
        else:
            task.append(f'Die {instance_count} durch {len(instances)} Quellenangaben belegten Geräteinstanzen anhand der Stückzahlen planen; einzelne Identitäten, Anschlüsse und Funktionszuordnungen bestätigen.')
        names = '; '.join(item['name'] for item in instances)
        task.append('Benannte Geräte: ' + names + '.' if len(names) <= 3500
                    else 'Die vollständige Liste benannter Geräte steht in den Quellenbefunden unter INSTANCE.')
    if categories:
        task.append(f'Die {len(categories)} unquantifizierten Gerätegruppen getrennt halten; konkrete Instanzen und Stückzahlen vor einer Geräteerzeugung klären.')
    if functions:
        task.append('Die erfassten logischen Funktionen den bestätigten Geräten zuordnen und Funktionspartner klären.')
        names = '; '.join(item['name'] for item in functions)
        task.append('Funktionen: ' + names + '.' if len(names) <= 1500 else 'Die vollständige Funktionsliste mit ihren Zitaten steht in den Quellenbefunden unter FUNCTION.')
    if requirements:
        task.append(f'Die {len(requirements)} erfassten Anforderungsangaben einschließlich ihrer vollständigen Zitate als Prüfkriterien erhalten.')
    if any(item['kind'] == 'TRANSPORT' for item in technologies):
        task.append('Die belegten registrierten Kommunikationsvarianten getrennt planen und die tatsächlichen Geräteanschlüsse bestätigen.')
    if unresolved:
        task.append('Nicht eindeutig registrierte Schnittstellen vor einer technischen Zuordnung klären.')
    task.append('Änderungen erst nach Prüfung dieses Vorschlags bestätigen; keine Mengen, Topologien oder technischen Parameter ergänzen.')
    questions = []
    for role in dict.fromkeys(item['role'] for item in categories):
        names = '; '.join(item['name'] for item in categories if item['role'] == role)
        additional = ' zusätzlich zu den bereits benannten Instanzen' if instances else ''
        questions.append(f'Welche konkreten Geräte und Stückzahlen gehören{additional} zu diesen Gruppen: {names}?')
    if unresolved:
        questions.append('Welche technische Realisierung und gegebenenfalls registrierte Variante ist für diese noch ungeklärten Schnittstellen vorgesehen: ' + ', '.join(unresolved) + '?')
    if instances or categories:
        questions.append('Welche Anschlüsse und Funktionspartner sind für die Geräte und Gruppen vorgesehen? Welche Kommunikationsvarianten gehören zu den noch ungeklärten Schnittstellen?')
    return {
        'summary': f'Die vollständige Quelle wurde in {len(parts)} lokalen Qwen-Abschnitten ausgewertet: {instance_count} belegte Geräteinstanzen, {len(categories)} unquantifizierte Gerätegruppen. Der Prüfauftrag wird aus den zusammengeführten Quellenbefunden aufgebaut.',
        'components': components, 'technologies': technologies,
        'proposed_task': '\n'.join(task), 'assumptions': [], 'open_questions': questions,
    }


def document_segments(source: str, max_bytes=6000):
    """Cover every source character in bounded, contiguous inference windows."""
    if max_bytes < 1:
        raise ValueError('Das lokale Kontextfenster ist zu klein.')
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


def resolve_document_references(value: dict, rows: list, *, model_schema=None, scope_prefix=''):
    """Project one selected source reference into its coupled display/citation."""
    from copy import deepcopy
    result = deepcopy(value)
    if isinstance(result.get('components'), dict):
        if len(result['components']) > 24:
            raise ValueError('Höchstens 24 Komponenten pro Auswertungsabschnitt.')
        if any(not isinstance(claim, dict) or 'source_ref' in claim for claim in result['components'].values()):
            raise ValueError('Die Komponentenreferenz gehört ausschließlich in den eindeutigen Objektschlüssel.')
        result['components'] = [{'source_ref': reference, **claim} for reference, claim in result['components'].items()]
    if isinstance(result.get('technologies'), dict):
        if model_schema is None or len(result['technologies']) > 16:
            raise ValueError('Technologie-Schlüssel benötigen ihr Quellenschema und höchstens 16 Angaben.')
        allowed = model_schema['properties']['technologies']['properties']
        claims = []
        for key, reference in result['technologies'].items():
            if key not in allowed or reference not in allowed[key]['enum']:
                raise ValueError('Nicht belegter Technologie-Schlüssel oder Quellenbezug: ' + key)
            kind, name = key.split(':', 1)
            claims.append({'kind': kind, 'name': name, 'source_ref': reference})
        result['technologies'] = claims
    references = {row['source_ref']: row['text'].strip() for row in rows}
    component_units = {row['source_ref']: row for row in document_component_sources(rows, scope_prefix=scope_prefix)}
    component_references = {key: row['text'].strip() for key, row in component_units.items()}
    seen_components = set()
    for field in ('components', 'technologies'):
        for item in result.get(field, []):
            reference = item.pop('source_ref', None)
            selected = component_references if field == 'components' else references
            if reference not in selected or not selected[reference] or len(selected[reference]) > 1200:
                raise ValueError(f'Ungültige Quellenreferenz: {reference}. Nur die übergebenen Referenzen verwenden.')
            if 'source_quote' in item or (field == 'components' and ('name' in item or 'source_context' in item)):
                raise ValueError('Name und Zitat werden aus einer Quellenreferenz gebildet; keine freien Quellenfelder zurückgeben.')
            if field == 'components':
                if reference in seen_components:
                    raise ValueError(f'{reference}: eine Quellenangabe nicht mehrfach als verschiedene Geräte/Kategorien ausgeben.')
                seen_components.add(reference)
                lines = component_units[reference]['text'].splitlines()
                display = next((line for line in lines if line.strip() and not re.match(r'^\s*(?:\d+(?:\.\d+)*[.)]?\s+)?(?:Aufgaben|Responsibilities|Funktionsbeschreibung|Functional description|Funktionen|Functions)\s*:?\s*$', line, re.I)), lines[0])
                label = re.sub(r'^(?:\d+(?:\.\d+)*[.)]?\s+|#{1,6}\s+|[-*]\s+)', '', display)
                label = re.sub(r'^(?:Funktion|Function|Sensor|Aktor|Actuator|Controller|Gateway)\s*:\s*', '', label, flags=re.I)
                item['name'] = label.rstrip('.')[:120]
            item['source_quote'] = component_units[reference].get('source_quote', selected[reference]) if field == 'components' else selected[reference]
            if field == 'components':
                item['source_context'] = component_units[reference].get('source_context', [])
    return result


def document_component_policy(text: str):
    """Source constraints for a claim, independent of industry or filename."""
    from backend.nis.agent.tools.inventory_quantities import quantities
    text = text.translate(str.maketrans({char: '-' for char in '\u2010\u2011\u2012\u2013\u2014\u2212'}))
    if re.search(r'^\s*(?:[\w-]*REQ[-_]|Anforderungen\s*:|Requirements\s*:)|\b(?:muss|müssen|must|shall|soll|sollen|should)\b', text, re.I):
        return {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}
    # Bare architecture services describe logical responsibilities. Physical
    # server/controller qualifiers retain their separately proven device role.
    if re.fullmatch(r'\s*(?:[-*]\s*)?(?:Fleet Manager|Map|Traffic Service|MES|WMS-Anbindung|Lagerverwaltung|Warehouse Management|Safety Zones|Rezept- und Batchsystem|Historian|Alarmmanagement|Materialfluss|Qualitätsmanagement|Werkerassistenz|Traceability|Energieplattform|Datenbank)\s*\.?\s*', text, re.I):
        return {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}
    if re.search(r'\b(?:Funktionen?|Functions?|Aufgaben|Responsibilities)\s*:|software|algorithm|logik|processing|fusion|regelung|planung|kontrolle|zeitprogramme|schnittstell|interface|fronthaul|backhaul', text, re.I):
        return {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}
    # Actions describe behavior even when their objects contain hardware words.
    # Apply before lexical device detection, without treating noun declarations
    # such as "Motorcontroller (MC)" as capabilities.
    if not any(quantities(text).values()) and not document_device_aliases(text) and re.search(_DOCUMENT_ACTION, text, re.I):
        return {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}
    if re.search(r'\b(?:Sensorlinks?|sensor links?|Punkt-zu-Punkt-Links|point-to-point links?)\b', text, re.I):
        return {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}
    # Composite cells are physical groupings, not a single PLC/robot role.
    if re.fullmatch(r'\s*[\w/ -]*(?:zellen|cells)\s*\.?\s*', text, re.I):
        return {'kind': 'CATEGORY', 'role': 'OTHER', 'quantity': None}
    role = None
    if re.search(r'[\w-]*gateway\b', text, re.I):
        role = 'GATEWAY'
    elif re.search(r'[\w-]*(?:controller|computer|rechner|steuergerät|steuerung|server|workstation)\b|\b(?:SPS|DCS|SIS|PLC|CNC|ECU|HMI|BMS)\b', text, re.I):
        role = 'CONTROLLER'
    elif re.match(r'\s*(?:Greifer|Greifarm|Endeffektor|[\w-]*motor(?:en)?|[\w-]*(?:aktuator|aktor)(?:en)?)\b', text, re.I):
        role = 'ACTUATOR'  # Integrated feedback does not change the actuator's hardware role.
    elif re.search(r'sensor|sensorik|\b(?:LiDAR|Radar|Kameras?|IMU|Encoder|Scanner|Waagen?|Messtaster)\b', text, re.I):
        role = 'SENSOR'
    elif re.search(r'aktor|actuator|aktuator|motor|reaktionsräder|pumpenmechanik|greifer', text, re.I):
        role = 'ACTUATOR'
    if role is None:
        if re.search(r'[\w-]*(?:modul|mechanik|panel|wandler|akku|batterie|gehäuse|speicher|netzteil)\b|(?<![\w-])(?:chassis|räder)(?![\w-])', text, re.I):
            return {'kind': 'CATEGORY', 'role': 'OTHER', 'quantity': None}
        return None
    alternative = bool(re.search(r'\bz\.\s*B\.|\be\.\s*g\.|\b(?:oder|or)\b|\([^)]*[,/][^)]*\)', text, re.I))
    key = {'CONTROLLER': 'ecus', 'GATEWAY': 'gateways', 'SENSOR': 'sensors', 'ACTUATOR': 'actuators'}[role]
    count = quantities(text).get(key, 0)
    concrete = bool(document_device_aliases(text) or re.search(r'\b(?:Hauptrechner|main computer)\b', text, re.I)
                    or re.search(r'\b(?:ID|Kennung|Gerätename|device name)\s*[:=]', text, re.I))
    if alternative or re.search(r'\d+\s*[–—-]\s*\d+', text):
        return {'kind': 'CATEGORY', 'role': role, 'quantity': None}
    if concrete or count:
        return {'kind': 'INSTANCE', 'role': role, 'quantity': count or 1}
    return {'kind': 'CATEGORY', 'role': role, 'quantity': None}


def _document_context_heading(text: str) -> bool:
    """Numbered outlines are scopes; explicit quantity rows are not headings."""
    if not re.match(r'^\d+(?:\.\d+)*[.)]?\s+.+', text):
        return False
    if re.match(r'^\d+\s+', text):
        policy = document_component_policy(text)
        if policy and policy['kind'] == 'INSTANCE':
            return False
    return True


def document_source_contexts(source: str):
    """Bind Markdown and numeric headings to their original character offsets."""
    offsets, contexts, markdown_path, numbered_path = [0], [[]], [], []
    offset = 0
    for line in source.splitlines(keepends=True):
        text = line.strip()
        markdown = re.match(r'^(#{1,6})\s+(.+?)(?:\s+#+)?$', text)
        heading = re.match(r'^(\d+(?:\.\d+)*)[.)]?\s+(.+)', text)
        if markdown:
            level = len(markdown[1])
            markdown_path = [entry for entry in markdown_path if entry[0] < level]
            markdown_path.append((level, markdown[2]))
            numbered_path = []
        elif heading and _document_context_heading(text):
            identifier = heading[1]
            numbered_path = [entry for entry in numbered_path if identifier.startswith(entry[0] + '.')]
            numbered_path.append((identifier, text))
        else:
            offset += len(line)
            continue
        # Numeric headings may themselves declare a controller. Their context
        # starts on the heading row, rather than after its newline.
        offsets.append(offset)
        contexts.append([entry[1] for entry in [*markdown_path, *numbered_path]])
        offset += len(line)
    return offsets, contexts


def document_source_scope(context: list[str]) -> list[str]:
    """Remove only a semantic section caption, retaining named device scopes."""
    if not context:
        return []
    label = re.sub(r'^\d+(?:\.\d+)*[.)]?\s+', '', context[-1]).rstrip(':').strip()
    if re.fullmatch(r'(?:Architektur|Architecture|Hardware(?:komponenten| components)?|Systemfunktionen|Funktionsbeschreibung|Functional description|Funktionen|Functions|Aufgaben|Responsibilities|(?:Referenz[- ]?)?Anforderungen|(?:Reference )?Requirements|Schnittstellen|Interfaces|Anschlüsse|Connections|Übersicht|Overview|Systemübersicht|System overview)', label, re.I):
        return context[:-1]
    return context[:]


def document_component_sources(rows: list, *, scope_prefix=''):
    """Expose distinct literal clauses, retaining full lines separately on wire.

    Commas inside parentheses remain one type/alternative group. A mixed
    architecture list gets disjoint references; the original combined reference
    cannot be used to hide its separate roles in an OTHER category.
    """
    result = []
    function_section = None
    first_function_body = False
    excluded_section = None
    excluded_normative = False
    requirement_section = None
    requirement_lead = False
    architecture_section = None
    interface_section = None
    assurance_section = None
    platform_section = None
    markdown_path = []
    numbered_path = []
    heading_sequence = 0
    context_rows = [{**row, 'source_ref': 'CTX-' + row['source_ref']} for row in document_source_references(scope_prefix)]
    for row in [*context_rows, *rows]:
        text = row['text'].strip()
        row_policy = document_component_policy(text)
        normative_row = row_policy and row_policy['kind'] == 'REQUIREMENT'
        markdown = re.match(r'^(#{1,6})\s+(.+?)(?:\s+#+)?$', text)
        logical = markdown[2] if markdown else text
        heading = re.match(r'^(\d+(?:\.\d+)*)[.)]?\s+(.+)', logical)
        structural = heading[2] if heading else logical
        if markdown:
            level = len(markdown[1])
            markdown_path = [entry for entry in markdown_path if entry[0] < level]
            heading_sequence += 1
            markdown_path.append((level, logical, str(heading_sequence)))
            heading = {1: '.'.join(entry[2] for entry in markdown_path), 2: structural}
            numbered_path = []
        elif heading and _document_context_heading(logical):
            identifier = heading[1]
            numbered_path = [entry for entry in numbered_path if identifier.startswith(entry[0] + '.')]
            numbered_path.append((identifier, logical))
        if heading and architecture_section is not None and not heading[1].startswith(architecture_section + '.'):
            architecture_section = None
        if heading and re.fullmatch(r'(?:Architektur|Architecture|Hardware(?:komponenten| components)?)\s*:?\s*', structural, re.I):
            architecture_section = heading[1]
        if heading and interface_section is not None and not heading[1].startswith(interface_section + '.'):
            interface_section = None
        if (heading and re.match(r'^(?:Schnittstellen|Interfaces|Anschlüsse|Connections)\b', structural, re.I)) or re.match(r'^(?:Schnittstellen|Interfaces|Anschlüsse|Connections)\s*:', structural, re.I):
            interface_section = heading[1] if heading else ''
        elif re.match(r'^(?:Aufgaben|Tasks|Responsibilities|Funktionen|Functions|Systemfunktionen|Funktionsbeschreibung|Hardware|Architektur|Architecture|Plattform|Platform|Implementierung|Implementation|Sensorik|Aktorik|Anforderungen|Requirements)\s*(?::|\(|$)', structural, re.I) or re.match(r'^(?:Controller|Gateway|ECU)\s*:', structural, re.I):
            interface_section = None
        if heading and platform_section is not None and not heading[1].startswith(platform_section + '.'):
            platform_section = None
        if re.match(r'^(?:Plattform|Platform|Implementierung|Implementation)\s*(?::|$)', structural, re.I):
            platform_section = heading[1] if heading else ''
        elif re.match(r'^(?:Aufgaben|Tasks|Responsibilities|Funktionen|Functions|Systemfunktionen|Funktionsbeschreibung|Hardware|Architektur|Architecture|Sensorik|Aktorik|Schnittstellen|Interfaces|Anschlüsse|Anforderungen|Requirements)\s*(?::|\(|$)', structural, re.I):
            platform_section = None
        if heading and assurance_section is not None and not heading[1].startswith(assurance_section + '.'):
            assurance_section = None
        assurance_header = re.fullmatch(r'(?:Safety|Security|Sicherheit)(?:\s*(?:,|/|&|und|and)\s*(?:Safety|Security|Sicherheit|Qualität|Quality|Betrieb|Operations?))*\s*:?\s*', structural, re.I)
        if assurance_header:
            assurance_section = heading[1] if heading else ''
        if assurance_section is not None and not assurance_header:
            row_policy = {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}
            normative_row = True
        requirement_header = re.fullmatch(r'(?:(?:Referenz[- ]?)?Anforderungen|(?:Reference )?Requirements)\s*:?\s*', structural, re.I)
        if requirement_header:
            requirement_section = heading[1] if heading else ''
            requirement_lead = False
        elif heading and (requirement_section is not None or requirement_lead) and (not requirement_section or not heading[1].startswith(requirement_section + '.')):
            requirement_section = None
            requirement_lead = False
        elif re.fullmatch(r'(?:Hardware|Architektur|Architecture|Interfaces|Schnittstellen|Aufgaben|Responsibilities|Funktionen|Functions)\s*:', structural, re.I):
            requirement_section = None
            requirement_lead = False
        if re.fullmatch(r'(?:Das System|The system)\s+(?:muss|must|shall|soll|should)\s*:?\s*', text, re.I):
            requirement_lead = True
        if (requirement_section is not None or requirement_lead) and not requirement_header:
            row_policy = {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}
            normative_row = True
        if re.match(r'^(?:Index|Inhaltsverzeichnis|Contents|Table of contents|Testfälle|Test cases|Verifikation|Verification|Varianten|Variants|Erweiterungen|Erweiterungsmöglichkeiten|Extensions|Systemkontext|System context|Zweck|Purpose|Betriebsmodi|Operating modes|(?:Safety|Security|Sicherheit)(?=\s*:?\s*$)|Software[- ]?Schnittstellen|Software interfaces|ROS2 Topics|Services)\b', structural, re.I):
            excluded_section = heading[1] if heading else ''
            excluded_normative = bool(re.match(r'^(?:Index|Inhaltsverzeichnis|Contents|Table of contents|Testfälle|Test cases|Verifikation|Verification)\b', structural, re.I))
        elif heading and excluded_section is not None and (not excluded_section or not heading[1].startswith(excluded_section + '.')):
            excluded_section = None
        if (excluded_section is not None and (not normative_row or excluded_normative)) or text.startswith('/') or re.match(r'^\s*[-*]?\s*\*{0,2}TC[-_]', text, re.I):
            continue
        function_header = re.search(r'^(?:\d+(?:\.\d+)*[.)]?\s+)?(?:Systemfunktionen|Funktionsbeschreibung|Functional description|Funktionen|Functions|Aufgaben|Responsibilities)\s*:?\s*$', logical, re.I)
        if function_header:
            function_section = heading[1] if heading else ''
            first_function_body = True
        elif function_section is not None and re.match(r'^(?:Schnittstellen|Interfaces|Anschlüsse|Sensorik|Aktorik|Hardware|Anforderungen|Requirements|Kommunikation|Energieversorgung|Plattform|Platform|Implementierung|Implementation)\s*:', text, re.I):
            function_section = None
            first_function_body = False
        elif function_section is not None and heading:
            if function_section == '' and first_function_body and not (row_policy and row_policy['kind'] == 'INSTANCE'):
                function_section = heading[1].rsplit('.', 1)[0] if '.' in heading[1] else heading[1]
            elif not function_section or not heading[1].startswith(function_section + '.'):
                function_section = None
                first_function_body = False
        required_body = bool(first_function_body and not function_header)
        if required_body:
            first_function_body = False
        in_functions = function_section is not None and heading and '.' in heading[1]
        if row['source_ref'].startswith('CTX-'):
            continue
        if function_header:
            continue  # A structural function caption is not an executable duty.
        # Markdown headings and two-column numbered index rows navigate the
        # document; they do not declare additional installed hardware.
        if markdown or re.match(r'^\|\s*\d+\s*\|[^|]+\|\s*$', text):
            continue
        if platform_section is not None and not normative_row:
            continue  # Platform metadata stays literal source context, not an executable function.
        if not normative_row and re.match(r'^(?:Direkte?\s+|Direct\s+)?(?:Sensorlinks?|sensor links?|Punkt-zu-Punkt-Links|point-to-point links?)\b', text, re.I):
            continue
        if interface_section is not None and not normative_row:
            if re.search(r'\b(?:jede|each)\b', text, re.I):
                row_policy = {'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None}
                normative_row = True
            else:
                continue  # Transport declarations remain technology facts, not hardware.
        if not normative_row and re.match(r'^(?:Beispiel\s+\d+|Systembeschreibung\b|System description\b|Systemübersicht\s*:|System overview\s*:|Erweiterungen\s*:|Testfälle\s*:)', text, re.I):
            continue  # Context, future ideas and tests do not declare additional installed hardware.
        if not normative_row and re.match(r'^(?:Der|Die|Das|Es|The)\b', text, re.I) and re.search(r'\b(?:ist|sind|nutzt|beschreibt|besteht|uses|is|are)\b', text, re.I):
            continue
        if not normative_row and re.search(r'\b(?:für|for|über|via)\b', text, re.I):
            from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
            first = text.split()[0].translate(str.maketrans({char: '-' for char in '\u2010\u2011\u2012\u2013\u2014\u2212'}))
            first = re.sub(r'-Bus$', '', first, flags=re.I).split('/')[0]
            try:
                DEFAULT_TECHNOLOGY_REGISTRY.profile(first, fields=('id',))
            except KeyError:
                pass
            else:
                continue  # "CAN-Bus für Motoren" declares communication, not another motor.
        if requirement_header or re.match(r'^- (?:Aufgaben-Anlage|Architektur-Evidence):', text):
            continue
        if markdown_path and row_policy is None and architecture_section is None and function_section is None:
            continue  # Unclassified document prose is not a component declaration.
        if heading and not normative_row and function_section is None and (document_component_policy(text) is None or re.search(r'(?:design|architecture|architektur|übersicht|overview)\s*$', structural, re.I)):
            continue
        if re.search(r'→|\b(?:angebunden|angeschlossen|verbunden)\b', text, re.I) and function_section is None:
            continue  # Connection statements are technology evidence, not additional hardware declarations.
        prefix = re.match(r'^\s*(?:Architektur|Architecture|Hardwarekomponenten|Hardware components)\s*:\s*', text, re.I)
        body = text[prefix.end():] if prefix else text
        clauses, start, depth = [], 0, 0
        for index, char in enumerate(body):
            if char in '([{': depth += 1
            elif char in ')]}': depth = max(0, depth - 1)
            elif depth == 0 and (char in ',;' or (architecture_section is not None and char == '/' and index > 0 and index + 1 < len(body) and body[index - 1] != '-' and body[index + 1] != '-')):
                clauses.append(body[start:index].strip().rstrip('.'))
                start = index + 1
            elif depth == 0 and architecture_section is not None and not body[:index].rstrip().endswith('-') and re.match(r' (?:und|and) ', body[index:]):
                delimiter = re.match(r' (?:und|and) ', body[index:])[0]
                clauses.append(body[start:index].strip().rstrip('.'))
                start = index + len(delimiter)
        clauses.append(body[start:].strip().rstrip('.'))
        function_list = bool(function_section is not None and not normative_row and not heading
                             and len(clauses) > 1 and not re.search(r'\b(?:muss|soll|shall|must|wenn|falls|if|when)\b|[.!?]\s+\w', body, re.I))
        if function_list:
            last = re.split(r'\s+und\s+(?![^()]*\))', clauses[-1])
            if len(last) == 2 and all(last):
                clauses = [*clauses[:-1], *last]
            clauses = [re.sub(r'^[-*]\s+', '', clause).strip().rstrip('.') for clause in clauses]
        policies = [document_component_policy(clause) for clause in clauses]
        mixed_hardware = len({p['role'] for p in policies if p and p['kind'] in {'CATEGORY', 'INSTANCE'}}) > 1
        split = len(clauses) > 1 and not normative_row and (function_list or prefix or architecture_section is not None or (mixed_hardware and not re.search(r'Funktion|Function|Anforderung|REQ|Testf', text, re.I)))
        for index, clause in enumerate(clauses if split else [text]):
            policy = row_policy if normative_row else document_component_policy(clause)
            if architecture_section is not None and policy is None:
                policy = {'kind': 'CATEGORY', 'role': 'OTHER', 'quantity': None}
            if function_section is not None and not (policy and policy['kind'] == 'REQUIREMENT'):
                policy = {'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None}
            required = bool(architecture_section is not None or split or in_functions or required_body or re.match(r'^(?:Funktionen?|Functions?)\s*:', text, re.I)
                            or (policy and policy['kind'] in {'CATEGORY', 'INSTANCE', 'REQUIREMENT'})
                            or (policy and policy['kind'] == 'FUNCTION' and re.search(_DOCUMENT_ACTION, clause, re.I)))
            if function_section is not None and not function_header:
                required = True
            transport_controller = re.fullmatch(r'([\w-]+)-Controller', clause, re.I)
            if transport_controller and not split:
                from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
                try:
                    DEFAULT_TECHNOLOGY_REGISTRY.profile(transport_controller[1])
                except KeyError:
                    pass
                else:
                    required = False  # A transport implementation is not a project device declaration.
            result.append({'source_ref': row['source_ref'] + (f'.F{index + 1:02d}' if function_list else f'.C{index + 1:02d}' if split else ''),
                           'text': clause, **({'source_quote': text} if function_list else {}), 'policy': policy, 'required': required,
                           'source_context': [entry[1] for entry in [*markdown_path, *numbered_path]],
                           'function_scope': function_section is not None,
                           'function_heading': bool(function_section is not None and (heading or function_header))})
    # Adjacent normative rows form a bounded literal citation, rather than
    # competing for one output slot per sentence. Their original source rows
    # remain on wire and are never summarized or dropped.
    raw = {row['source_ref']: row['text'] for row in rows}
    order = {row['source_ref']: index for index, row in enumerate(rows)}
    grouped = []
    pending = []
    def flush():
        if not pending:
            return
        if len(pending) == 1:
            grouped.append(pending[0])
        else:
            refs = [u['source_ref'] for u in pending]
            suffix = '.G' if pending[0]['policy']['kind'] == 'REQUIREMENT' else '.F'
            grouped.append({**pending[0], 'source_ref': refs[0] + suffix,
                            'text': ''.join(raw[ref] for ref in refs).strip(), 'source_rows': refs,
                            'required': any(u['required'] for u in pending)})
        pending.clear()
    for unit in result:
        groupable = unit['policy'] and unit['source_ref'] in raw and (unit['policy']['kind'] == 'REQUIREMENT' or (unit['policy']['kind'] == 'FUNCTION' and unit['function_scope'] and (unit['function_heading'] or (pending and pending[0]['function_heading']))))
        if groupable:
            if pending and (order[unit['source_ref']] != order[pending[-1]['source_ref']] + 1 or unit['policy']['kind'] != pending[-1]['policy']['kind'] or unit['function_heading']):
                flush()
            proposed = ''.join(raw[u['source_ref']] for u in [*pending, unit]).strip()
            if len(proposed) > 1000:
                flush()
            pending.append(unit)
        else:
            flush()
            grouped.append(unit)
    flush()
    return grouped


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
            if re.match(_DOCUMENT_TRANSPORT_QUALIFIER, text[match.end():]):
                continue
            if not any(label in other and len(other) > len(label)
                       and any(outer.start() <= match.start() and outer.end() >= match.end()
                               for outer in re.finditer(r'(?<![\w])' + re.escape(other) + r'(?![\w])', text))
                       for other in other_aliases):
                return True
    return False


def document_qualified_transports(source: str, profiles):
    """Keep literal qualifications visible; a similar bus is not a confirmed port."""
    text = source.translate(str.maketrans({char: '-' for char in '\u2010\u2011\u2012\u2013\u2014\u2212'}))
    result = set()
    for profile in profiles:
        for alias in [profile['id'], *profile.get('aliases', [])]:
            for match in re.finditer(r'(?<![\w])' + re.escape(alias) + r'(?![\w])', text, re.I):
                qualifier = re.match(_DOCUMENT_TRANSPORT_QUALIFIER, text[match.end():], re.I)
                if qualifier:
                    result.add(source[match.start():match.end() + qualifier.end()])
    return sorted(result)


def document_declared_unknown_transports(rows: list, profiles, *, candidates=None, scope_prefix=''):
    """Literal unknown names from interface declarations, never from arbitrary prose."""
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    if candidates is None:
        candidates = document_transport_candidates(''.join(row['text'] for row in rows), profiles)
    result = {}
    in_section = False
    ignored = False
    aliases = {name.casefold() for name in document_device_aliases(scope_prefix + ''.join(row['text'] for row in rows))}
    context_rows = [{**row, 'source_ref': 'CTX-' + row['source_ref']} for row in document_source_references(scope_prefix)]
    for row in [*context_rows, *rows]:
        text = row['text'].strip()
        heading = re.match(r'^\d+(?:\.\d+)*[.)]?\s+(.+)', text)
        body = heading[1] if heading else text
        row_policy = document_component_policy(text)
        if row_policy and row_policy['kind'] == 'REQUIREMENT':
            continue
        if re.match(r'^(?:Testfälle|Test cases|Erweiterungen|Extensions|Software[- ]?Schnittstellen|Software interfaces|Funktionsbeschreibung|Systemfunktionen|Funktionen|Aufgaben|Responsibilities)\b', body, re.I):
            in_section = False
            ignored = True
            continue
        if heading or re.match(r'^(?:Architektur|Hardware|Anforderungen|Requirements|Energieversorgung)\s*:?\s*$', body, re.I):
            in_section = False
            ignored = False
        caption = re.match(r'^(?:(?:Unbekannte|Elektrische|Physische)\s+)?(?:Schnittstellen?|Anschlüsse|Anschluss|Interfaces?|Kommunikation|Kommunikationsnetzwerke|Connectivity|Diagnosezugänge)\s*(?::|\(|$)\s*(.*)', body, re.I)
        content = None
        if caption:
            ignored = False
            content = caption[1].rstrip(').')
            in_section = not content.strip()
        elif not ignored and '→' in text:
            left, right = text.split('→', 1)
            policy = document_component_policy(left)
            if in_section or (policy and policy['kind'] in {'CATEGORY', 'INSTANCE'}):
                content = right
        elif not ignored:
            assignment = re.match(r'^(\S+)\s+(?:für|for|über|via)\b', text, re.I)
            if in_section or (assignment and any(document_registered_transport_citation(p['id'], assignment[1], profiles=profiles) for p in candidates)):
                content = assignment[1] if assignment else text
        if not content:
            continue
        # A functional partner ("CDC (Lenk-/Bremsanforderungen)") is not a
        # physical interface. Keep ADC usable when explicitly named as a port.
        partner = re.fullmatch(r'([A-Z][A-Z0-9_-]{1,15})\s*\(([^)]+)\)\s*\.?', content)
        if partner and partner[1].casefold() in aliases:
            continue
        links = re.fullmatch(r'(?:Direkte?\s+|Direct\s+)?(?:Sensorlinks?|sensor links?|Anschlüsse|Interfaces)\s*\(([^)]+)\)\s*\.?', content, re.I)
        if links:
            content = links[1]
        if document_qualified_transports(content, profiles):
            content = re.sub(_DOCUMENT_TRANSPORT_QUALIFIER, '', content, flags=re.I)
        protected = set()
        for profile in candidates:
            for alias in profile.get('aliases', []):
                if '/' in alias:
                    for match in re.finditer(re.escape(alias), content, re.I):
                        protected.update(i for i in range(match.start(), match.end()) if content[i] == '/')
        pieces, start = [], 0
        for index, char in enumerate(content):
            if char in ',;' or (char == '/' and index not in protected):
                pieces.append(content[start:index]); start = index + 1
        pieces.append(content[start:])
        for piece in pieces:
            piece = piece.strip().rstrip('.')
            if not piece or any(document_registered_transport_citation(p['id'], piece, profiles=profiles) for p in profiles):
                continue
            match = re.match(r'[^\W\d][\w\u2010\u2011\u2012\u2013\u2014\u2212-]*', piece)
            if not match:
                continue
            name = match.group()
            # Unknown technology labels may have descriptive suffixes, but
            # ordinary connection prose does not introduce a new protocol.
            if name.casefold() in aliases or re.match(r'^(?:Verbindung(?:en)?|connections?)\s+(?:zum|zur|zu|mit|to|with)\b', piece, re.I):
                continue
            if re.fullmatch(r'[\w\u2010\u2011\u2012\u2013\u2014\u2212-]*(?:Signale|Nachrichten|Signals|Messages)\s*(?:\([^)]*\))?', piece, re.I):
                continue
            if len(name) > 80 or row['source_ref'].startswith('CTX-'):
                continue
            result.setdefault(name, set()).add(row['source_ref'])
    return {name: sorted(refs) for name, refs in result.items()}


def document_device_aliases(source: str):
    return {match[1] for match in re.finditer(r'\b' + _DOCUMENT_CONTROLLER_LABEL + r'\s*\(([A-Z][A-Z0-9_-]{1,15})\)', source, re.I)}


def document_technology_source(source: str, *, scope_prefix=''):
    """Mask test/index mentions without changing source character positions."""
    from bisect import bisect_right
    offsets, contexts = document_source_contexts(scope_prefix + source)
    result, offset = [], len(scope_prefix)
    for line in source.splitlines(keepends=True):
        context = contexts[bisect_right(offsets, offset) - 1]
        excluded = any(re.match(r'^(?:\d+(?:\.\d+)*[.)]?\s+)?(?:Index|Inhaltsverzeichnis|Contents|Table of contents|Verifikation|Verification|Testfälle|Test cases)\b', label, re.I) for label in context)
        excluded = excluded or bool(re.match(r'^\s*[-*]?\s*\*{0,2}TC[-_]', line, re.I))
        result.append(''.join(char if char in '\r\n' else ' ' for char in line) if excluded else line)
        offset += len(line)
    return ''.join(result)


def document_transport_candidates(source: str, profiles, *, context_aliases=None, candidates=None, scope_prefix=''):
    """Registry-owned mentions; controller aliases never prove physical ports."""
    source = document_technology_source(source, scope_prefix=scope_prefix)
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
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    choices = {'registered_transports': {}, 'device_aliases': {}, 'unresolved_transports': {}}
    if schema['properties']['technologies'].get('type') == 'object':
        for key, claim in schema['properties']['technologies']['properties'].items():
            kind, name = key.split(':', 1)
            target = {'TRANSPORT': 'registered_transports', 'DEVICE_ALIAS': 'device_aliases', 'UNRESOLVED': 'unresolved_transports'}[kind]
            choices[target][name] = claim['enum']
        return choices
    qualifier_profiles = DEFAULT_TECHNOLOGY_REGISTRY.profiles()
    for branch in schema['$defs']['DocumentTechnology'].get('oneOf', []):
        kind = branch['properties']['kind']['enum'][0]
        if kind == 'UNRESOLVED':
            names = [name for name in branch['properties']['name']['enum']
                     if re.search(_DOCUMENT_TRANSPORT_QUALIFIER, name, re.I)
                     and document_qualified_transports(name, qualifier_profiles)]
            for name in names:
                choices['unresolved_transports'].setdefault(name, set()).update(branch['properties']['source_ref']['enum'])
            continue
        target = choices['registered_transports' if kind == 'TRANSPORT' else 'device_aliases']
        for name in branch['properties']['name']['enum']:
            identity = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(name) if kind == 'TRANSPORT' else name
            target.setdefault(identity, set()).update(branch['properties']['source_ref']['enum'])
    for name, refs in schema.get('x-declared-unknown-transports', {}).items():
        choices['unresolved_transports'].setdefault(name, set()).update(refs)
    return {key: {name: sorted(refs) for name, refs in values.items()} for key, values in choices.items()}


def document_component_grounding(rows: list, *, scope_prefix=''):
    units = document_component_sources(rows, scope_prefix=scope_prefix)
    return {'component_sources': {u['source_ref']: {'source_rows': u['source_rows']} if 'source_rows' in u else u['text']
                                  for u in units if '.C' in u['source_ref'] or '.F' in u['source_ref'] or 'source_rows' in u},
            'required_components': [u['source_ref'] for u in units if u['required']]}


def document_model_output_schema(schema: dict, rows: list, *, scope_prefix=''):
    """Project the same claim constraints into unique model-output keys.

    The public proposal stays a list. Grammar-level keys prevent repetition
    loops without accepting duplicates or discarding repeated model claims.
    """
    from copy import deepcopy
    result = deepcopy(schema)
    properties = {}
    for branch in schema['$defs']['DocumentComponent'].get('oneOf', []):
        claim = deepcopy(branch)
        refs = claim['properties'].pop('source_ref')['enum']
        claim['required'] = [name for name in claim['required'] if name != 'source_ref']
        for reference in refs:
            properties[reference] = claim
    result['properties']['components'] = {'type': 'object', 'additionalProperties': False,
        'properties': properties, 'required': document_component_grounding(rows, scope_prefix=scope_prefix)['required_components'], 'maxProperties': 24}
    technologies = {}
    grounding = document_technology_grounding(schema)
    for kind, field in [('TRANSPORT', 'registered_transports'), ('DEVICE_ALIAS', 'device_aliases'), ('UNRESOLVED', 'unresolved_transports')]:
        for name, refs in grounding[field].items():
            technologies[kind + ':' + name] = {'type': 'string', 'enum': refs}
    result['properties']['technologies'] = {'type': 'object', 'properties': technologies, 'required': list(technologies), 'additionalProperties': False, 'maxProperties': 16}
    result.pop('x-declared-unknown-transports', None)
    result['required'] = list(dict.fromkeys([*result.get('required', []), 'components', 'technologies']))
    return result


def document_response_json(content: str):
    """Reject duplicate JSON keys instead of silently overwriting source claims."""
    import json
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Doppelter Schlüssel in der Qwen-Antwort: ' + key)
            result[key] = value
        return result
    return json.loads(content, object_pairs_hook=unique)


def document_output_schema(source: str, base_schema: dict, *, context_aliases=None, scope_prefix=''):
    """Use ASCII source identities, not two independently selected text fields."""
    from copy import deepcopy
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    schema = deepcopy(base_schema)
    rows = [row for row in document_source_references(source)
            if row['text'].strip() and len(row['text'].strip()) <= 1200]
    units = document_component_sources(rows, scope_prefix=scope_prefix)
    references = [row['source_ref'] for row in units]
    if not rows:
        # An uninterpretable window is still supplied in full. It cannot
        # contribute fabricated extracted facts or hide a failed later window.
        schema['properties']['components']['maxItems'] = 0
        schema['properties']['technologies']['maxItems'] = 0
        return schema
    profiles = DEFAULT_TECHNOLOGY_REGISTRY.profiles()
    source_aliases = document_device_aliases(source) if context_aliases is None else context_aliases
    available_profiles = document_transport_candidates(source, profiles, context_aliases=source_aliases, scope_prefix=scope_prefix)
    eligible_source = document_technology_source(source, scope_prefix=scope_prefix)
    declared_unknown = document_declared_unknown_transports(rows, profiles, candidates=available_profiles, scope_prefix=scope_prefix)
    schema['x-declared-unknown-transports'] = declared_unknown
    for definition in ('DocumentComponent',):
        item_schema = schema['$defs'][definition]
        removed = {'source_quote', 'name', 'source_context'} if definition == 'DocumentComponent' else {'source_quote'}
        for field in removed:
            item_schema['properties'].pop(field)
        item_schema['required'] = [field for field in item_schema['required'] if field not in removed] + ['source_ref']
        item_schema['properties']['source_ref'] = {'type': 'string', 'enum': references}
    component_base = schema['$defs']['DocumentComponent']
    component_branches = []
    import json
    policies = {}
    for unit in units:
        policies.setdefault(json.dumps(unit['policy'], sort_keys=True), []).append(unit['source_ref'])
    for encoded, selected in policies.items():
        policy = json.loads(encoded)
        branch = deepcopy(component_base)
        branch['properties']['source_ref']['enum'] = selected
        if policy:
            for key, value in policy.items():
                branch['properties'][key] = {'type': 'null'} if value is None else {'enum': [value], 'type': 'integer' if key == 'quantity' else 'string'}
        else:
            branch['properties']['kind'] = {'type': 'string', 'enum': ['CATEGORY', 'FUNCTION']}
            branch['properties']['role'] = {'type': 'string', 'enum': ['OTHER']}
            branch['properties']['quantity'] = {'type': 'null'}
        component_branches.append(branch)
    schema['$defs']['DocumentComponent'] = {'oneOf': component_branches} if component_branches else {'not': {}}
    if not component_branches:
        schema['properties']['components']['maxItems'] = 0
    # A name, semantic kind and original reference form one allowed tuple.
    # Independent enums allowed valid names to cite unrelated valid rows.
    branches = []
    punctuation = str.maketrans({char: '-' for char in '\u2010\u2011\u2012\u2013\u2014\u2212'})
    def normalize(text):
        return text.translate(punctuation).casefold()
    for row in rows:
        text = row['text']
        if text.strip() not in eligible_source:
            continue
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
        if not re.search(r'kommunikation|schnittstell|anschluss|interface|bus|connectivity|diagnosezug|telemetri|link|protokoll|protocol|→', text, re.I):
            unresolved = {label for label in unresolved if label.isupper() or len(labels) == 1}
        unresolved.update(document_qualified_transports(text, profiles))
        unresolved.update(name for name, refs in declared_unknown.items() if row['source_ref'] in refs)
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


def validate_document_interpretation(value, source: str, *, context_aliases=None, scope_prefix='', aggregate=False):
    """Reject invented source claims before displaying a local-model proposal."""
    model = DocumentProposalInterpretation if aggregate else DocumentInterpretation
    result = model.model_validate(value)
    from backend.nis.agent.tools.inventory_quantities import quantities
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY
    count_keys = {'SENSOR': 'sensors', 'ACTUATOR': 'actuators', 'CONTROLLER': 'ecus', 'GATEWAY': 'gateways'}
    punctuation = str.maketrans({char: '-' for char in '\u2010\u2011\u2012\u2013\u2014\u2212'})
    def normalized_label(text):
        return text.translate(punctuation).casefold()
    profiles = DEFAULT_TECHNOLOGY_REGISTRY.profiles()
    if context_aliases is None:
        context_aliases = document_device_aliases(source)
    def transport_citation(item):
        identity = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(normalized_label(item.name))
        target = [p for p in profiles if p['id'] == identity]
        return bool(document_transport_candidates(item.source_quote, profiles, context_aliases=context_aliases, candidates=target))
    eligible_source = document_technology_source(source, scope_prefix=scope_prefix)
    semantic_errors = []
    for technology in result.technologies:
        if technology.source_quote not in eligible_source:
            semantic_errors.append(f'{technology.name}: Test-/Indexzitat belegt keine Projektschnittstelle.')
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
    # Citation grouping may differ at a window boundary. Bind the context to
    # original character positions rather than to a particular grouping.
    from bisect import bisect_right
    context_offsets, context_values = document_source_contexts(scope_prefix + source)
    context_cache = {}
    for component in result.components:
        if component.source_quote not in context_cache:
            contexts = []
            position = source.find(component.source_quote)
            while position >= 0:
                contexts.append(context_values[bisect_right(context_offsets, len(scope_prefix) + position) - 1])
                position = source.find(component.source_quote, position + 1)
            context_cache[component.source_quote] = contexts
        contexts = context_cache[component.source_quote]
        unique_contexts = {tuple(context) for context in contexts}
        if not component.source_context and len(unique_contexts) == 1:
            component.source_context = list(next(iter(unique_contexts)))
        elif 'source_context' not in component.model_fields_set and len(unique_contexts) > 1:
            semantic_errors.append(f'{component.name}: Abschnittskontext fehlt bei mehrdeutiger Quellenangabe.')
        if component.source_context and component.source_context not in contexts:
            semantic_errors.append(f'{component.name}: unbelegter Abschnittskontext.')
        if any(contexts) and component.source_context not in contexts:
            semantic_errors.append(f'{component.name}: Abschnittskontext fehlt oder ist veraltet.')
        if component.kind in {'INSTANCE', 'CATEGORY'} and component.source_quote not in eligible_source:
            semantic_errors.append(f'{component.name}: Test-/Indexzitat belegt keine installierte Hardware.')
        policy = document_component_policy(component.source_quote)
        if policy is None and component.kind in {'INSTANCE', 'CATEGORY'} and component.role != 'OTHER':
            semantic_errors.append(f'{component.name}: unbelegte Geräterolle; OTHER und explizite Klärung erforderlich.')
        if component.kind == 'INSTANCE' and policy is None:
            semantic_errors.append(f'{component.name}: keine belegte individuelle Geräteidentität oder Stückzahl; keine INSTANCE bilden.')
        if policy and component.kind in {'INSTANCE', 'CATEGORY'}:
            if policy['kind'] in {'FUNCTION', 'REQUIREMENT'}:
                semantic_errors.append(f'{component.name}: logische Verarbeitung/Anforderung ist keine Hardware.')
            elif component.role != policy['role']:
                semantic_errors.append(f'{component.name}: role {policy["role"]} erforderlich.')
            elif component.kind == 'INSTANCE' and policy['kind'] == 'CATEGORY':
                semantic_errors.append(f'{component.name}: Geräteart, Alternative oder Mengenbereich bestätigt keine individuelle Instanz; CATEGORY und quantity null erforderlich.')
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
    missing_transports = [profile['id'] for profile in document_transport_candidates(source, profiles, context_aliases=context_aliases, scope_prefix=scope_prefix)
                          if not any(item.kind == 'TRANSPORT' and DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(normalized_label(item.name)) == profile['id']
                                     for item in result.technologies)]
    if missing_transports:
        semantic_errors.append('Alle eindeutig belegten registrierten Transportvarianten erfassen, ohne Duplikate als Ersatz: '
                               + ', '.join(missing_transports))
    for qualified in document_qualified_transports(eligible_source, profiles):
        if not any(item.kind == 'UNRESOLVED' and item.name.casefold() == qualified.casefold() for item in result.technologies):
            semantic_errors.append('Qualifizierte oder nur ähnliche Technologie als UNRESOLVED erhalten: ' + qualified)
    for name in document_declared_unknown_transports(document_source_references(source), profiles, scope_prefix=scope_prefix):
        if not any(item.kind == 'UNRESOLVED' and item.name.casefold() == name.casefold() for item in result.technologies):
            semantic_errors.append('Explizit genannte unbekannte Schnittstelle als UNRESOLVED erhalten: ' + name)
    combined_source = re.sub(r'\b(?:Controller|Computer|ECU)\s*\([^)]+\)', lambda match: ' ' * len(match.group()), eligible_source)
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
    for match in re.finditer(r'\b' + _DOCUMENT_CONTROLLER_LABEL + r'\s*\(([A-Z][A-Z0-9_-]{1,15})\)', eligible_source, re.I):
        if not any(item.kind == 'DEVICE_ALIAS' and item.name == match[1]
                   and match.group() in item.source_quote for item in result.technologies):
            missing_aliases.append(match[1])
    if missing_aliases:
        semantic_errors.append('Alle Gerätekürzel brauchen DEVICE_ALIAS mit vollständigem Controller-/Computerzitat: ' + ', '.join(missing_aliases))
    original_rows = document_source_references(source)
    original_text = {row['source_ref']: row['text'].strip() for row in original_rows}
    for unit in document_component_sources(original_rows, scope_prefix=scope_prefix):
        if unit['required']:
            pieces = [original_text[ref] for ref in unit.get('source_rows', [])] or [unit['text']]
            for piece in pieces:
                if not any(piece in item.source_quote and item.source_context == unit['source_context'] and (not unit.get('source_quote') or item.name == unit['text'][:120]) and (not unit['policy'] or (item.kind == unit['policy']['kind'] and item.role == unit['policy']['role'] and item.quantity == unit['policy']['quantity'])) for item in result.components):
                    semantic_errors.append('Wesentliche getrennte Quellenangabe fehlt: ' + piece[:150])
        if unit['policy']:
            for item in result.components:
                if item.source_context == unit['source_context'] and item.source_quote == unit.get('source_quote', unit['text']) and (item.kind != unit['policy']['kind'] or item.role != unit['policy']['role'] or item.quantity != unit['policy']['quantity']):
                    semantic_errors.append('Quellenangabe benötigt die belegte Einordnung ' + str(unit['policy']) + ': ' + unit['text'][:100])
    for line in eligible_source.splitlines():
        if document_device_aliases(line) and not re.search(r'^\s*REQ\b|\b(?:muss|müssen|must|shall)\b', line, re.I):
            if not any(item.kind == 'INSTANCE' and item.role in {'CONTROLLER', 'GATEWAY'} and line.strip() in item.source_quote
                       for item in result.components):
                semantic_errors.append('Konkret benannten Controller aus seiner eigenen Deklaration als INSTANCE erfassen: ' + line.strip())
    for component in result.components:
        if component.kind in {'INSTANCE', 'CATEGORY'} and re.search(r'\bcontroller\b', normalized_label(component.name)) and component.role not in {'CONTROLLER', 'GATEWAY'}:
            semantic_errors.append(f'{component.name}: ausdrücklich als Controller benannt; role CONTROLLER erforderlich.')
    for line in eligible_source.splitlines():
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


def document_fact_identity(fact: dict) -> str:
    """Cross-language identity of a literal typed source fact and its scope."""
    import json
    return json.dumps([fact['kind'], fact.get('source_context', []), fact['source_quote'], fact['name']],
                      ensure_ascii=False, separators=(',', ':'))


def reviewed_document_evidence(prompt: str):
    """Validate the reviewed source snapshot before ordinary model proposal use.

    The original source, typed facts and review answers share the existing
    document-equipment envelope. This performs no model writes or approvals.
    """
    import hashlib
    import json
    matches = list(re.finditer(r'^- Dokument-Geräte:\s*([^\r\n]+)$', prompt, re.M))
    if not matches:
        return None
    match = matches[-1]
    value = json.loads(match[1])
    if not isinstance(value, dict) or 'facts' not in value:
        return None  # Existing quantity-only review envelopes remain supported.
    source = value.get('source_text')
    if not isinstance(source, str) or not source or len(source) > DOCUMENT_SOURCE_MAX_CHARS:
        raise ValueError('Vollständige Dokumentquelle für die geprüften Befunde fehlt.')
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
    if value.get('source_sha256') != digest or value.get('source_chars') != len(source):
        raise ValueError('Geprüfte Dokumentbefunde gehören nicht zu dieser vollständigen Quelle.')
    outside = prompt[:match.start()] + prompt[match.end():]
    facts = value.get('facts')
    technologies = value.get('technologies')
    if not isinstance(facts, list) or not isinstance(technologies, list):
        raise ValueError('Strukturierte Dokumentbefunde sind unvollständig.')
    for item in [*facts, *technologies]:
        if not isinstance(item, dict) or not item.get('source_quote') or item['source_quote'] not in outside:
            raise ValueError('Ein Dokumentbefund ist nicht in der ursprünglichen Auftragsquelle belegt.')
    interpretation = validate_document_interpretation({
        'summary': 'Geprüfte quellengebundene Dokumentbefunde.',
        'components': facts, 'technologies': technologies,
        'proposed_task': 'Quellenbefunde im normalen Modellvorschlag prüfen; offene Zuordnungen und Mengen nicht ergänzen.',
        'assumptions': [], 'open_questions': ['Offene Angaben bleiben vor Modellfreigabe zu klären.'],
    }, source, aggregate=True)
    assignments = value.get('function_assignments', {})
    function_ids = {document_fact_identity(fact) for fact in interpretation['components'] if fact['kind'] == 'FUNCTION'}
    if (not isinstance(assignments, dict) or any(key not in function_ids or not isinstance(host, str)
            or not host.strip() for key, host in assignments.items())):
        raise ValueError('Unbelegte Funktionszuordnung in den Dokumentbefunden.')
    return {'source': 'reviewed_document', 'source_name': value.get('source_name'),
            'source_sha256': digest, 'source_chars': len(source),
            'components': interpretation['components'], 'technologies': interpretation['technologies'],
            'questions': value.get('questions', []), 'answers': value.get('answers', []),
            'excluded_questions': value.get('excluded_questions', []), 'function_assignments': assignments,
            'canonical_writes': False, 'approval_required': True}
