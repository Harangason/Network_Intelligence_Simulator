"""Domain-independent spatial identity and evidence for generators and agents.

Location, functional ownership and transport are three independent dimensions.
No motor numbering, function name or communication peer defines a location.
"""
from copy import deepcopy
import json
import re

from backend.knowledge.semantic_vocabulary import engineering_tokens
from .models import EngineeringValidationError

VERSION = 'spatial-architecture-v2'
DERIVED_SOURCES = {VERSION, 'automotive-zones-v1'}
LOCAL_BUSES = {'lin', 'can', 'can_fd', 'can_xl', 'flexray'}
LABELS = {'FL': 'VL', 'FR': 'VR', 'RL': 'HL', 'RR': 'HR', 'F': 'Vorn',
          'R': 'Hinten', 'L': 'Links', 'RIGHT': 'Rechts', 'UPPER': 'Oben',
          'LOWER': 'Unten', 'CENTER': 'Mitte', 'UNKNOWN': 'Ort offen'}

REASONING_RULES = (
    'Raumcluster sind branchenübergreifend. Trenne Einbauort/Bezugsrahmen, funktionalen Owner und Busanbindung. '
    'Prüfe vor Zuordnung oder Generierung inspect_spatial_architecture. Nutze bestätigte Einbauorte zuerst, '
    'danach eindeutige vollständige Positionswörter; begründe die Entscheidung mit ihrer Quelle. '
    'Gemeinsame Funktion oder derselbe Controller beweisen keine räumliche Nähe. '
    'Motor 1–4 einer Drohne ergeben ohne Geometrie und Motorzuordnung keine vier bestimmten Ecken; '
    'auch Drehsinn, Nummern, Fahrwerk und Fahrerassistenz sind keine Einbauorte. '
    'Beachte Bezugssysteme und räumliche Hierarchien: Roboterarme, Rotorarme, Etagen/Räume und Fahrzeugzonen. '
    'Unbekannte oder widersprüchliche Orte bleiben offen; bei architekturrelevanten Lücken gezielt fragen. '
    'Lokale Zweige räumlich trennen, übergeordnete Backbones getrennt bewerten. '
    'Eine Raumaufteilung legt weder Bustyp noch Kanalzahl oder zulässiges Timing fest: '
    'Prüfe Hardwarebestand, Busgrenzen, Kapazität, Timing, Routen und Rückmeldungen. '
    'Frühere Projekte sind begründete Vorschläge, kein Beleg für den Einbauort im aktuellen Projekt.'
)


def architecture_from(parameters=None, prompt=''):
    """Read the same structured contract in saved projects and wizard requests."""
    raw = deepcopy((parameters or {}).get('spatial_architecture') or {})
    entries = re.findall(r'^- Raumarchitektur:[ \t]*([^\r\n]*)$', prompt, re.M)
    if len(entries) > 1:
        raise EngineeringValidationError('Raumarchitektur darf im Wizard nur einmal definiert sein.')
    if entries:
        try:
            requested = json.loads(entries[0])
        except ValueError as error:
            raise EngineeringValidationError('Raumarchitektur enthält ungültiges JSON.') from error
        if raw and architecture_from({'spatial_architecture': raw}) != architecture_from({'spatial_architecture': requested}):
            raise EngineeringValidationError('Wizard-Raumarchitektur widerspricht der gespeicherten Projektdefinition.')
        raw = requested
    if not isinstance(raw, dict):
        raise EngineeringValidationError('Raumarchitektur muss ein Objekt sein.')
    frame = raw.get('reference_frame', 'asset-relative')
    if not isinstance(frame, str) or not frame.strip():
        raise EngineeringValidationError('Raumarchitektur benötigt einen Bezugsrahmen.')
    zones = raw.get('zones') or []
    if not isinstance(zones, list):
        raise EngineeringValidationError('Raumcluster müssen als Liste angegeben werden.')
    declared = {}
    for zone in zones:
        if not isinstance(zone, dict):
            raise EngineeringValidationError('Raumcluster benötigt id und label.')
        key = zone.get('id', '')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]{0,119}', key) or key in declared or key in LABELS:
            raise EngineeringValidationError('Raumcluster-Kennung fehlt, ist doppelt oder reserviert.')
        if not isinstance(zone.get('label'), str) or not zone['label'].strip():
            raise EngineeringValidationError('Raumcluster benötigt einen Anzeigenamen.')
        declared[key] = zone
    if declared and not raw.get('reference_frame'):
        raise EngineeringValidationError('Benannte Raumcluster benötigen einen expliziten Bezugsrahmen.')
    for key, zone in declared.items():
        seen = {key}
        parent = zone.get('parent_id')
        while parent:
            if parent not in declared or parent in seen:
                raise EngineeringValidationError('Raumcluster-Hierarchie enthält einen fehlenden oder zyklischen Elternraum.')
            seen.add(parent)
            parent = declared[parent].get('parent_id')
    assignments = raw.get('assignments') or {}
    if not isinstance(assignments, dict) or any(not isinstance(k, str) or not isinstance(v, str) or v not in {*LABELS, *declared} for k, v in assignments.items()):
        raise EngineeringValidationError('Raumzuordnung verweist auf einen unbekannten Raumcluster.')
    # Names are case-insensitive throughout the generator. Reject ambiguity.
    if len({key.casefold() for key in assignments}) != len(assignments):
        raise EngineeringValidationError('Mehrdeutige Gerätenamen in Raumzuordnungen.')
    return {**raw, 'version': VERSION, 'reference_frame': frame, 'zones': zones, 'assignments': assignments}


def zone_label(zone, architecture=None):
    return next((z['label'] for z in (architecture or {}).get('zones', []) if z['id'] == zone), LABELS.get(zone, zone))


def location_decision(name, identity=None, driving_side=None, architecture=None, object_id=None):
    identity, architecture = identity or {}, architecture or architecture_from()
    frame = architecture['reference_frame']
    known = {*LABELS, *(z['id'] for z in architecture['zones'])}
    assignments = {k.casefold(): v for k, v in architecture['assignments'].items()}
    by_id, by_name = assignments.get(str(object_id).casefold()), assignments.get(str(name).casefold())
    if by_id and by_name and by_id != by_name:
        raise EngineeringValidationError(f'{name}: widersprüchliche Raumzuordnung nach ID und Name.')
    assigned = by_id or by_name
    explicit = identity.get('installation_zone') if identity.get('installation_zone_source') not in DERIVED_SOURCES else None
    if explicit and assigned and explicit != assigned:
        raise EngineeringValidationError(f'{name}: bestätigter Einbauort widerspricht der Raumarchitektur.')
    def result(zone, source, evidence):
        return {'zone_id': zone, 'label': zone_label(zone, architecture), 'reference_frame': frame,
                'status': 'UNRESOLVED' if zone == 'UNKNOWN' else 'CONFIRMED' if source in {'explicit_identity', 'project_assignment'} else 'DERIVED',
                'source': source, 'evidence': evidence, 'version': VERSION}
    if explicit or assigned:
        zone = explicit or assigned
        if zone not in known:
            raise EngineeringValidationError(f'{name}: unbekannter Einbauort {zone}.')
        identity_frame = identity.get('installation_reference_frame')
        if explicit and identity_frame and identity_frame != frame:
            raise EngineeringValidationError(f'{name}: Einbauort gehört zu einem anderen Bezugsrahmen.')
        return result(zone, 'explicit_identity' if explicit else 'project_assignment',
                      'Hardware-Identität' if explicit else 'Bestätigte Raumarchitektur')
    # Custom reference systems (rooms, cells, different vehicles) must not merge
    # every occurrence of "left" into one global left-side cluster.
    if architecture['zones']:
        return result('UNKNOWN', 'unresolved', 'Zuordnung zum benannten Raumcluster fehlt.')
    words = set(engineering_tokens(str(name)))
    front = bool(words & {'front', 'vorne', 'vorn'})
    rear = bool(words & {'rear', 'hinten', 'heck', 'fond', 'hinterachs'})
    left, right = bool(words & {'left', 'links'}), bool(words & {'right', 'rechts'})
    if words & {'sitz', 'tuer', 'tuere', 'seat', 'door'} and words & {'fahrer', 'beifahrer'}:
        if driving_side in {'LHD', 'RHD'}:
            passenger = 'beifahrer' in words
            left = left or ((driving_side == 'LHD') != passenger)
            right = right or ((driving_side == 'RHD') != passenger)
            front = front or not rear
    upper, lower = bool(words & {'upper', 'oben'}), bool(words & {'lower', 'unten'})
    center = bool(words & {'center', 'centre', 'mitte'})
    if (front and rear) or (left and right) or (upper and lower) or (center and (left or right)):
        raise EngineeringValidationError(f'{name}: widersprüchliche Positionsangaben; Einbauort explizit festlegen.')
    # Compound 3-D positions need a declared zone, rather than losing an axis.
    if (upper or lower) and (front or rear or left or right or center):
        return result('UNKNOWN', 'unresolved', 'Mehrdimensionale Position benötigt einen benannten Raumcluster.')
    zone = ('FL' if front and left else 'FR' if front and right else 'RL' if rear and left else 'RR' if rear and right
            else 'F' if front else 'R' if rear else 'L' if left else 'RIGHT' if right else 'UPPER' if upper
            else 'LOWER' if lower else 'CENTER' if center else 'UNKNOWN')
    return result(zone, 'name_tokens' if zone != 'UNKNOWN' else 'unresolved',
                  f'Positionswörter in {name}' + (f'; Lenkungsseite {driving_side}' if driving_side else '')
                  if zone != 'UNKNOWN' else 'Keine eindeutige räumliche Angabe; Nummer oder Funktion genügt nicht.')


def installation_zone(name, identity=None, driving_side=None, architecture=None, object_id=None):
    return location_decision(name, identity, driving_side, architecture, object_id)['zone_id']


def with_spatial_architecture(prompt, parameters):
    """Make confirmed project geometry available before generating any binding."""
    if not (parameters or {}).get('spatial_architecture'):
        architecture_from(prompt=prompt)  # Reject malformed explicit input early.
        return prompt
    architecture = architecture_from(parameters, prompt)
    if re.search(r'^- Raumarchitektur:', prompt, re.M):
        return prompt
    return prompt + '\n- Raumarchitektur: ' + json.dumps(architecture, ensure_ascii=False)
