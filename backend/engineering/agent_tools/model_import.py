"""Engineering file import uses the same parser and field mapping as the UI."""
import base64
import binascii
import json
from urllib.parse import urlencode

from .. import importer
from . import conversation, proposal_service


def export_project(arguments):
    from ..project_bundle import ProjectBundleService
    from ..project_context import current_project_id
    bundle = ProjectBundleService().export(current_project_id())
    result = {'format': bundle['format'], 'bundle_version': bundle['bundle_version'],
              'project_id': bundle['project_id'], 'generated_at': bundle['generated_at'],
              'counts': {key: len(rows) for key, rows in bundle['source_data'].items()},
              'download_url': '/api/engineering/projects/export?' + urlencode({'project': current_project_id()}),
              'download_semantics': 'Download liest den dann aktuellen Projektstand.'}
    if arguments.get('include_data'):
        if len(json.dumps(bundle, default=str).encode()) > 5 * 1024 * 1024:
            raise ValueError('Projektpaket größer als 5 MiB; den Projektexport-Download verwenden.')
        result['bundle'] = bundle
    return result


def preview(arguments):
    text, encoded = arguments.get('text'), arguments.get('content_base64')
    if (text is None) == (encoded is None):
        raise ValueError('Genau einen Dateiinhalt angeben: text oder content_base64.')
    try:
        content = text.encode('utf-8') if text is not None else base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError('Ungültiger Base64-Dateiinhalt.') from error
    if len(content) > 5 * 1024 * 1024:
        raise ValueError('Die Importdatei darf höchstens 5 MiB enthalten.')
    return importer.preview_import(arguments['filename'], content)


def plan(arguments):
    source = preview(arguments)
    state = conversation.read()
    operations = state.setdefault('model_import_operations', {})
    key = source['import_id'] + ':' + source['format']
    if key in operations:
        return proposal_service.latest(operations[key])
    ids, changes, origins, reused = {}, [], [], []
    for group, kind, parent_key, parent_field in importer.IMPORT_GROUPS:
        for item in source[group]:
            existing = importer._existing(kind, source['import_id'], item['key'])
            if existing:
                ids[item['key']] = str(existing['id'])
                reused.append({'object_type': kind, 'id': str(existing['id'])})
                continue
            data = importer.import_payload(kind, item, ids, parent_key, parent_field)
            ref = 'import-' + str(len(changes))
            changes.append({'local_ref': ref, 'object_type': kind, 'action': 'CREATE', 'data': data})
            origins.append({'local_ref': ref, 'object_type': kind, 'import_key': item['key']})
            ids[item['key']] = '$' + ref
    if not changes:
        return {'agent_response': {'type': 'RESULT', 'status': 'ANSWERED',
                'text': 'Der Dateiinhalt wurde bereits vollständig übernommen.',
                'metadata': {'canonical_ids': reused, 'model_changed': False, 'import_id': source['import_id']}}}
    proposal = proposal_service.create('MODEL_IMPORT', changes, arguments['rationale'],
        assumptions=source.get('warnings') or [], evidence=[{'source': 'engineering_import',
            'import_id': source['import_id'], 'file_name': source['file_name'], 'object_origins': origins,
            'reused_ids': reused}])
    operations[key] = proposal['proposal_id']
    conversation.write(state)
    return proposal_service.validate(proposal['proposal_id'])
