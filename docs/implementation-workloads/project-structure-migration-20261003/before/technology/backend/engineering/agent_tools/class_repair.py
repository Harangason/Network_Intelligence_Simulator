"""Explicitly authorized, versioned correction of a faulty wizard proposal.

No deletion: reparent generated interfaces and supersede artificial functions.
The caller must own a project RequestUnit and provide explicit apply authority.
"""
from . import model, proposal_service
from ..repository import update_object


def repair(proposal_id: str, *, apply: bool = False, actor: str = 'user-authorized-class-repair'):
    proposal = proposal_service.get(proposal_id)
    if proposal['proposal_type'] != 'WIZARD_ENGINEERING_MODEL' or proposal['status'] != 'APPLIED':
        raise ValueError('Nur ein übernommener Wizard-Modellvorschlag kann korrigiert werden.')
    owned = {(item['object_type'], item['id']) for item in proposal['canonical_ids']}
    hardware = {row['id']: row for row in model.objects('HardwareNode')}
    functions = [row for row in model.objects('Function')
        if ('Function', row['id']) in owned and hardware[row['hardware_node_id']]['device_class'] < 3
        and row['lifecycle_state'] not in {'deprecated', 'superseded'}]
    by_function = {row['id']: row for row in functions}
    interfaces = [row for row in model.objects('Interface') if row.get('function_id') in by_function]
    if any(('Interface', row['id']) not in owned for row in interfaces):
        raise ValueError('Manuell ergänzte Interfaces gefunden; keine automatische Umhängung.')
    before = {kind: len(model.objects(kind)) for kind in ('HardwareNode', 'Message', 'Signal')}
    if apply:
        for row in interfaces:
            update_object('Interface', row['id'], {'function_id': None,
                'hardware_node_id': by_function[row['function_id']]['hardware_node_id'],
                'expected_version': row['version'], 'actor': actor,
                'change_summary': 'Klasse 0–2: Interface direkt an vorhandene Hardware gebunden.'})
        for row in functions:
            update_object('Function', row['id'], {'lifecycle_state': 'superseded',
                'expected_version': row['version'], 'actor': actor,
                'change_summary': 'Künstliche Wizard-Funktion der Klasse 0–2 ersetzt; Historie bleibt erhalten.'})
        if before != {kind: len(model.objects(kind)) for kind in before}:
            raise ValueError('Unerwartete Veränderung der Hardware-, Nachrichten- oder Signalanzahl.')
    return {'applied': apply, 'interfaces_reparented': len(interfaces), 'functions_superseded': len(functions),
            'preserved_counts': before, 'function_ids': [row['id'] for row in functions]}
