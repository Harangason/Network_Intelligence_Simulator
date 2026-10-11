"""Expose the existing ECU transfer planner through human-reviewed proposals."""
import hashlib
import json
from .. import structure_transfer as transfer
from ..proposals import get_proposal
from ..repository import BASE_COLUMNS, PARENT_LINKS, get_object, get_spec
from . import conversation, proposal_service


def plan(arguments):
    signature = hashlib.sha256(json.dumps({key: value for key, value in arguments.items() if not key.startswith('_')},
                                         sort_keys=True).encode()).hexdigest()
    state = conversation.read()
    operations = state.setdefault('structure_transfer_operations', {})
    if signature in operations:
        return proposal_service.latest(operations[signature])
    source_plan = get_proposal(arguments['transfer_proposal_id'])
    if source_plan.get('proposal_type') != 'STRUCTURE_REPLICATION':
        raise ValueError('Ein ECU-Strukturtransferplan ist erforderlich.')
    if source_plan.get('status') in {'APPROVED', 'REJECTED'}:
        raise ValueError('Dieser Transferplan ist abgeschlossen. Den aktuellen Quell- und Zielstand erneut analysieren.')
    target = source_plan.get('target_object') or {}
    source_hardware = get_object('HardwareNode', target['source_hardware_id'])
    target_hardware = get_object('HardwareNode', target['target_hardware_id'])
    source_id, target_id = str(source_hardware['id']), str(target_hardware['id'])
    if source_id == target_id or not transfer._is_ecu(source_hardware) or not transfer._is_ecu(target_hardware):
        raise ValueError('Unterschiedliche Quell- und Ziel-ECUs sind erforderlich.')
    resolved = {source_id: {'id': target_id, 'name': target_hardware['name'], 'source_name': source_hardware['name']}}
    changes, reused, skipped, origins = [], [], [], []
    items = sorted(transfer._merge_transfer_decisions(source_plan['proposed_objects'], arguments.get('decisions')),
                   key=lambda item: int(item.get('level') or 99))
    for index, item in enumerate(items):
        kind = item['object_type']
        if kind not in transfer.TRANSFER_TYPES[1:]:
            raise ValueError('Unbekannter Transfer-Objekttyp.')
        source = get_object(kind, str(item['source_id']))
        parent = resolved.get(str(item['source_parent_id']))
        if item['action'] == 'skip' or not parent:
            skipped.append(item['plan_key'])
            continue
        if item['action'] == 'reuse':
            existing = get_object(kind, str(item['target_id']))
            if str(existing.get(PARENT_LINKS[kind][0])) != parent['id'] or str(existing['id']) in reused:
                raise ValueError('Das gewählte Zielobjekt gehört nicht zum Transfer-Elternobjekt oder wird mehrfach verwendet.')
            identifier, name = str(existing['id']), existing['name']
            reused.append(identifier)
        else:
            payload = transfer._clone_payload(source, item, parent, target_id, resolved,
                                              arguments['transfer_proposal_id'], 'engineering-agent')
            # The UI clone helper assumes an immediate human apply. Its review,
            # approval and actor fields must never enter an agent proposal.
            editable = set(BASE_COLUMNS) | set(get_spec(kind).own_columns)
            payload = {key: value for key, value in payload.items() if key in editable}
            ref = f'transfer-{index}'
            changes.append({'object_type': kind, 'local_ref': ref, 'action': 'CREATE', 'data': payload})
            origins.append({'local_ref': ref, 'object_type': kind, 'source_object_id': str(source['id'])})
            identifier, name = '$' + ref, payload['name']
        resolved[str(source['id'])] = {'id': identifier, 'name': name, 'source_name': source['name']}
    if not changes:
        return {'agent_response': {'type': 'RESULT', 'status': 'ANSWERED',
                'text': f'Keine neuen Objekte vorgesehen: {len(reused)} vorhandene Objekte verwendet, {len(skipped)} Positionen übersprungen.',
                'metadata': {'canonical_ids': reused, 'skipped_plan_keys': skipped, 'model_changed': False}}}
    proposal = proposal_service.create('STRUCTURE_TRANSFER', changes, arguments['rationale'],
        evidence=[{'source': 'structure_transfer', 'transfer_proposal_id': arguments['transfer_proposal_id'],
                   'source_hardware_id': source_id, 'target_hardware_id': target_id,
                   'reused_ids': reused, 'skipped_plan_keys': skipped, 'object_origins': origins}])
    validated = proposal_service.validate(proposal['proposal_id'])
    operations[signature] = proposal['proposal_id']
    conversation.write(state)
    return validated
