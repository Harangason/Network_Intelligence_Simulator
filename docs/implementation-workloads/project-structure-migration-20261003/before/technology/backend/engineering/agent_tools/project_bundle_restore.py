"""Reviewed project-bundle restoration into a new, explicitly named project."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from ..db import get_connection
from ..project_context import current_project_id, activate_project, reset_project
from ..project_bundle import BUNDLE_VERSION, ProjectBundleService, normalize_project_id
from . import conversation, proposal_service


def validate_bundle(bundle):
    if not isinstance(bundle, dict) or bundle.get('format') != 'network-intelligence-project':
        raise ValueError('Kein Network-Intelligence-Projektpaket.')
    version = bundle.get('bundle_version')
    if type(version) is not int or not 1 <= version <= BUNDLE_VERSION:
        raise ValueError('Nicht unterstützte Projektpaketversion.')
    normalize_project_id(bundle.get('project_id'))
    for key in ('workflow', 'source_data', 'project_data'):
        if not isinstance(bundle.get(key), dict):
            raise ValueError(f'{key} fehlt im Projektpaket.')
    for group in ('source_data', 'project_data'):
        if any(not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
               for rows in bundle[group].values()):
            raise ValueError('Projektpakettabellen müssen Listen von Datensätzen enthalten.')


def plan(arguments):
    bundle = arguments['bundle']
    validate_bundle(bundle)
    encoded = json.dumps(bundle, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if len(encoded.encode()) > 5 * 1024 * 1024:
        raise ValueError('Projektpaket größer als 5 MiB; den Projektdatei-Import verwenden.')
    name = arguments['name'].strip()
    if not name:
        raise ValueError('Name des neuen Projekts fehlt.')
    signature = hashlib.sha256((name + '\n' + encoded).encode()).hexdigest()
    state = conversation.read()
    restores = state.setdefault('project_bundle_restores', {})
    if signature in restores:
        return proposal_service.latest(restores[signature]['proposal_id'])
    target = 'network-project-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[:17] + '-' + uuid4().hex[:8]
    restores[signature] = {'bundle': deepcopy(bundle), 'target_project_id': target, 'name': name}
    conversation.write(state)
    proposal = proposal_service.create('PROJECT_BUNDLE_RESTORE', [{
        'action': 'CREATE', 'object_type': 'ProjectBundleRestore',
        'data': {'name': name, 'target_project_id': target, 'bundle_sha256': signature}}],
        arguments['rationale'], assumptions=[
            'Wiederherstellung in ein neues Projekt; vorhandene Projekte bleiben unverändert.',
            'Gespeicherte Analysebelege bleiben Historie. Technische Freigabe und Ausführungsberechtigungen werden nicht aus einer Datei übernommen.'],
        evidence=[{'source': 'project_bundle', 'project_id': bundle['project_id'], 'bundle_version': bundle['bundle_version'],
            'counts': {key: len(rows) for key, rows in bundle['source_data'].items()}, 'bundle_sha256': signature}])
    restores[signature]['proposal_id'] = proposal['proposal_id']
    conversation.write(state)
    return proposal_service.validate(proposal['proposal_id'])


def source(data):
    item = conversation.read().get('project_bundle_restores', {}).get(data.get('bundle_sha256'))
    if not item or item['target_project_id'] != data.get('target_project_id') or item['name'] != data.get('name'):
        raise ValueError('Die gespeicherte Projektpaketquelle stimmt nicht mit dem Vorschlag überein.')
    encoded = json.dumps(item['bundle'], ensure_ascii=False, sort_keys=True, allow_nan=False)
    if hashlib.sha256((item['name'] + '\n' + encoded).encode()).hexdigest() != data['bundle_sha256']:
        raise ValueError('Das Projektpaket wurde nach der Planung geändert.')
    validate_bundle(item['bundle'])
    with get_connection() as connection:
        if connection.execute('SELECT 1 FROM engineering_workflow_projects WHERE project_id=%s', (item['target_project_id'],)).fetchone():
            raise ValueError('Das Zielprojekt existiert bereits. Vorhandene Projekte werden nicht überschrieben.')
    if item['target_project_id'] == current_project_id():
        raise ValueError('Wiederherstellung benötigt ein neues Zielprojekt.')
    return item


def restore(data, *, actor):
    item = source(data)
    bundle = deepcopy(item['bundle'])
    workflow = bundle['workflow']
    original_context = workflow.get('context') or {}
    workflow['context'] = {'project_name': item['name'], 'imported_context': original_context,
        'project_bundle_import': {'source_project_id': bundle['project_id'], 'actor': actor,
                                 'requires_revalidation': True}}
    workflow['statuses'] = {key: 'OUTDATED' for key in workflow.get('statuses') or {}}
    workflow['stale_reasons'] = {key: 'Projektpaket in neues Projekt übernommen; aktuellen Stand prüfen.' for key in workflow['statuses']}
    for table in ('engineering_analysis_snapshots', 'engineering_simulation_snapshots'):
        for snapshot in bundle['project_data'].get(table) or []:
            snapshot.update(is_outdated=True, outdated_reason='Importierter historischer Beleg; im Zielprojekt neu prüfen.')
    for table in ('engineering_workloads', 'engineering_work_packages'):
        for workload in bundle['project_data'].get(table) or []:
            if workload.get('status') not in {'COMPLETED', 'CANCELED'}:
                workload['status'] = 'NEEDS_REVIEW'
    for proposal in bundle['source_data'].get('engineering_ai_proposals') or []:
        contract = proposal.get('engineering_contract') or {}
        if contract.get('status') != 'APPLIED':
            for field in ('approved_by', 'approved_at', 'validation_result', 'base_model_revision'):
                contract.pop(field, None)
            if contract:
                contract.update(status='PROPOSED', revision=str(uuid4()))
            proposal.update(engineering_contract=contract, status='DRAFT')
    for scenario in bundle['project_data'].get('engineering_simulation_scenarios') or []:
        scenario.update(approval_state='pending', review_state='draft')
        for fault in scenario.get('faults') or []:
            fault['approved'] = False
    # WorkflowStatusService activates its project in the request context. Keep
    # the importing proposal and its receipt bound to the original project.
    token = activate_project(item['target_project_id'])
    try:
        with get_connection() as connection:
            connection.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (item['target_project_id'],))
            if connection.execute('SELECT 1 FROM engineering_workflow_projects WHERE project_id=%s', (item['target_project_id'],)).fetchone():
                raise ValueError('Das Zielprojekt existiert bereits. Keine Wiederherstellung über ein vorhandenes Projekt.')
        result = ProjectBundleService().import_bundle(bundle, target_project_id=item['target_project_id'])
    finally:
        reset_project(token)
    return {'id': result['project_id'], 'name': item['name'], 'import_report': result}
