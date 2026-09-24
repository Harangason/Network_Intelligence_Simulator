"""Prepare a standalone controller through canonical validation and review."""
from backend.agent_core.runtime.hardware_intent import simple_hardware_intent
from . import model as access, proposal_service as proposals
from ..proposals import list_proposals


def prepare_hardware_request(arguments):
    intent = simple_hardware_intent(arguments['prompt'])
    if intent is None:
        raise ValueError('Dieser Auftrag benötigt die vollständige Engineering-Planung.')
    if not intent['status_technology'] or intent['status_cycle_ms'] is None:
        return {'proposal': None, 'reused_objects': [], 'status': 'WAITING_FOR_ENGINEERING_DECISION',
                'findings': [{'code': 'CONTROLLER_STATUS_CONFIGURATION_REQUIRED', 'severity': 'OPEN',
                             'message': 'Für die ECU-/Controller-Anlage verlangt das Core-Modell eine Gerätefunktion und einen Betriebsstatus. '
                                        'Welchen Statusanschluss und welchen Statuszyklus in ms soll das Gerät verwenden? '
                                        'Bitte beispielsweise „Statusanschluss <Technologie>, Statuszyklus <Wert> ms“ angeben. '
                                        'Diese Werte betreffen den Betriebsstatus, nicht den Abfragezyklus der Datenerfassung.'}]}
    hardware = access.objects('HardwareNode')
    # An exact preserved requirement and device type identify our prior result.
    # Similar names alone must never silently select an unrelated controller.
    existing = [item for item in hardware if item.get('device_type') == intent['device_type']
                and item.get('description') == intent['description']]
    findings = ([{'code': 'ACQUISITION_CONFIGURATION_REQUIRED', 'severity': 'OPEN',
                 'message': 'Die Hardware kann angelegt werden. Für die ausführbare Datenerfassung fehlen noch '
                            'bestätigte Datenquellen, Erfassungsmodus beziehungsweise Zyklus und Anbindung.'}]
                if intent['acquisition_requested'] else [])
    if existing:
        return {'reused_objects': existing, 'findings': findings, 'proposal': None}
    findings.append({'code': 'STATUS_RECIPIENT_UNRESOLVED', 'severity': 'OPEN',
                     'message': 'Die Statusdefinition verwendet die bestehende Core-Vorlage und muss fachlich geprüft werden. '
                                'Status-Empfänger und Netzzuordnung sind noch offen; es wird keine Route erzeugt.'})
    offset = 0
    revision = access.model_revision()
    while True:
        page = list_proposals(limit=100, offset=offset)
        for row in page:
            contract = row.get('engineering_contract') or {}
            if (row.get('prompt') == arguments['prompt'] and contract.get('status') in {'VALIDATED', 'APPROVED'}
                    and any(item.get('source') == 'explicit_user_request' for item in row.get('evidence') or [])
                    and contract.get('base_model_revision') == revision):
                return {'proposal': proposals.get(str(row['proposal_id'])), 'findings': findings, 'reused_objects': []}
        if len(page) < 100:
            break
        offset += 100
    occupied = {item['name'].casefold() for item in hardware}
    name, index = intent['name'], 2
    while name.casefold() in occupied:
        name = f"{intent['name']}_{index:02d}"
        index += 1
    from ..device_classification import DeviceClassificationRegistry
    profile = DeviceClassificationRegistry().resolve_profile(name=name, device_type=intent['device_type'])
    changes = [{
        'object_type': 'HardwareNode', 'local_ref': 'requested-controller', 'action': 'CREATE',
        'data': {'name': name, 'device_type': intent['device_type'], 'device_class': profile.device_class,
                 'description': intent['description']},
    }, {'object_type': 'Function', 'local_ref': 'requested-function', 'action': 'CREATE',
        'data': {'name': name + '_Funktion',
                 'hardware_node_id': '$requested-controller', 'description': arguments['prompt']}}]
    from ..device_communication import complete_new_controller_status
    complete_new_controller_status(changes, status_technology=intent['status_technology'], status_cycle_ms=intent['status_cycle_ms'])
    proposal = proposals.create('MODEL_OBJECT_CREATION', changes, arguments['prompt'], assumptions=[item['message'] for item in findings],
        evidence=[{'source': 'explicit_user_request', 'request': arguments['prompt'],
                   'unresolved': findings}])
    proposal = proposals.validate(proposal['proposal_id'])
    return {'proposal': proposal, 'findings': findings, 'reused_objects': []}
