"""Actual 9B counter for shared requirements without individual function facts."""
import asyncio
import importlib.util
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('stage_counter_support', HERE.parent / 'current-stage-context-repair/native_counter.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.HERE = HERE

def source_request():
    declarations = [f'Steuergerät ID: C{number}' for number in range(1, 5)]
    function = 'C1 verarbeitet die empfangenen Statusmeldungen.'
    requirement = ('Alle vier Steuergeraete C1, C2, C3 und C4 sind aktive Kommunikationspartner. '
        'Jedes erstellt fuenf bis zwanzig fachlich passende Statussignale und empfaengt die '
        'fuer seine Aufgabe erforderlichen Statusdaten anderer Steuergeraete. '
        'C1 koordiniert den Anlagenzustand, C2 den Energiezustand, C3 den Wartungszustand '
        'und C4 die Prozessfreigabe. Erstelle fuer jedes dieser vier Steuergeraete einen '
        'pruefpflichtigen physischen Kommunikationsentwurf auf dem gemeinsamen CAN-FD-Segment S. '
        'Es gibt keine weiteren Segmente, parallelen Verbindungen, Sensoren oder Aktoren. '
        'Signaldefinitionen und konkrete Nachrichtenrouten werden im nachfolgenden Planungsschritt ausgelegt. '
        'Die Rollen und der gemeinsame Kommunikationsbedarf gelten auch ohne eigene FUNCTION-FactID.')
    source = ('Industrie: allgemeine industrielle Statuskommunikation.\n' + '\n'.join(declarations)
        + '\nFunktion: ' + function + '\nREQ-001: ' + requirement
        + '\nTransport: can_fd\nSelbst verfasster Gegenbeispielfall ohne Hardwarequalifikation.')
    devices = [{'name': quote, 'role': 'CONTROLLER', 'quantity': 1, 'source_quote': quote,
                'source_context': [], 'minimum': False} for quote in declarations]
    facts = [{key: value for key, value in row.items() if key != 'minimum'} | {'kind': 'INSTANCE'} for row in devices]
    facts += [{'name': function, 'kind': 'FUNCTION', 'role': 'OTHER', 'quantity': None,
               'source_quote': 'Funktion: ' + function, 'source_context': []},
              {'name': 'REQ-001', 'kind': 'REQUIREMENT', 'role': 'OTHER', 'quantity': None,
               'source_quote': 'REQ-001: ' + requirement, 'source_context': []}]
    envelope = {'source_text': source, 'source_name': 'authored-shared-port-requirement.txt',
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'source_chars': len(source),
        'devices': devices, 'facts': facts, 'questions': [], 'answers': [], 'function_assignments': {},
        'technologies': [{'name': 'can_fd', 'kind': 'TRANSPORT', 'source_quote': 'Transport: can_fd'}]}
    return {'mode': 'EXAMPLE_PROJECT', 'prompt': source + '\n- Dokument-Geräte: ' + json.dumps(envelope, ensure_ascii=False),
            'reference_sources': []}

runner.source_request = source_request
if __name__ == '__main__':
    asyncio.run(runner.main())
