"""Lossless adapter for confirmed legacy wizard requests.

The full graph, port decisions, HMI choices and parameter evidence remain the
authoritative source. Never reparse this source through the small chat inventory
extractor: doing so would discard confirmed architecture.
"""
from copy import deepcopy
import hashlib
import json
import re
from uuid import uuid4

from ..db import ConcurrentUpdateError
from ..generation_rule_manager import resolve_generation_policy
from ..project_context import current_project_id


def capture(state, descriptor, wizard):
    if wizard.get('engineering_draft_ref'):
        return  # Already backed by the shared editable draft.
    previous = state.get('engineering_draft')
    same_run = previous and previous.get('structured_source', {}).get('run_id') == descriptor['run_id']
    if same_run and previous['structured_source']['request_revision'] == descriptor['revision']:
        wizard['structured_draft_ref'] = {'draft_id': previous['draft_id'], 'revision': previous['revision']}
        return
    if previous and not same_run:
        state.setdefault('engineering_draft_archive', {})[previous['draft_id']] = deepcopy(previous)
    prompt = descriptor['prompt']
    devices = {}
    assignments = wizard.get('system_cluster_assignments') or []
    if not assignments:
        graph_line = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', prompt, re.M)
        if graph_line:
            assignments = [{'tree': [{'name': branch['ecu'], 'deviceType': branch.get('device_type'),
                'sensors': [{'name': name} for name in branch.get('sensors') or []],
                'actuators': [{'name': name} for name in branch.get('actuators') or []]}
                for branch in cluster.get('controllers') or []]} for cluster in json.loads(graph_line[1])]
    for cluster in assignments:
        for branch in cluster.get('tree') or []:
            name = branch['name']
            role = 'GATEWAY' if branch.get('deviceType') == 'Gateway' else 'CONTROLLER'
            owner_id = hashlib.sha256((role + ':' + name.casefold()).encode()).hexdigest()[:20]
            devices[owner_id] = {'id': owner_id, 'name': name, 'role': role,
                'owner_id': None, 'technology': branch.get('interfaceType') or None,
                'source': 'CONFIRMED_WIZARD_GRAPH', 'known_kind': True}
            for key, role in [('sensors', 'SENSOR'), ('actuators', 'ACTUATOR')]:
                for leaf in branch.get(key) or []:
                    identity = hashlib.sha256((role + ':' + leaf['name'].casefold()).encode()).hexdigest()[:20]
                    devices[identity] = {'id': identity, 'name': leaf['name'], 'role': role,
                        'owner_id': owner_id, 'technology': leaf.get('interfaceType') or None,
                        'source': 'CONFIRMED_WIZARD_GRAPH', 'known_kind': True}
    industry = wizard.get('industry') or wizard.get('model_type')
    bus_types = [technology for device in devices.values()
                 for technology in (device.get('technologies') or [device.get('technology')]) if technology]
    bus_types.extend(wizard.get('technologies') or [])
    generation_policy = resolve_generation_policy(prompt, industry=industry, bus_types=bus_types)
    draft = {'schema_version': 2, 'source_format': 'WIZARD_V2',
        'draft_id': previous['draft_id'] if same_run else str(uuid4()),
        'revision': previous['revision'] + 1 if same_run else 1,
        'project_id': current_project_id(), 'mode': 'EXAMPLE_PROJECT' if re.search(r'^- Generierungsmodus:\s*EXAMPLE_PROJECT\s*$', prompt, re.M) else 'REAL_PROJECT',
        'industry': industry, 'generation_policy': generation_policy,
        'original_requirement': (previous.get('original_requirement') if same_run else None) or wizard.get('task') or prompt,
        'sources': [{'text': prompt, 'source': 'CONFIRMED_WIZARD'}],
        'devices': list(devices.values()), 'issues': [], 'removed_device_ids': [],
        'status': 'READY_TO_PLAN',
        'structured_source': {'version': 2, 'run_id': descriptor['run_id'],
            'request_revision': descriptor['revision'], 'prompt': prompt,
            'context': deepcopy(wizard), 'target': descriptor['target']}}
    state['engineering_draft'] = draft
    wizard['structured_draft_ref'] = {'draft_id': draft['draft_id'], 'revision': draft['revision']}


def assert_current(state, wizard):
    if wizard.get('engineering_draft_ref'):
        return  # Checked by the shared-draft workflow command resolver.
    reference = wizard.get('structured_draft_ref')
    if not reference:
        return
    draft = state.get('engineering_draft') or {}
    if draft.get('draft_id') != reference.get('draft_id') or draft.get('revision') != reference.get('revision'):
        raise ConcurrentUpdateError('Der gemeinsame Projektentwurf wurde geändert. Den aktuellen Entwurf laden und seine Revision ausdrücklich im Auftrag übernehmen.')


def amend(old, request):
    from backend.agent_core.context.limits import MAX_REQUIREMENT_LENGTH
    from .wizard_commands import amended_wizard_context, effective_wizard_prompt
    if request.action != 'AMEND' or request.devices or request.remove_device_ids or request.industry is not None or request.allow_simulation_defaults is not None:
        raise ValueError('Dieser Entwurf enthält bestätigte Wizard-Fachangaben. Änderungen als Auftragsergänzung übermitteln; Graph, Anschlüsse und HMI bleiben dabei erhalten.')
    draft = deepcopy(old)
    prompt = draft['structured_source']['prompt'] + '\n\nBestaetigte Ergaenzung des Nutzers:\n' + request.requirement
    if len(prompt) > MAX_REQUIREMENT_LENGTH:
        raise ValueError('Der vollständige strukturierte Auftrag überschreitet die zulässige Länge.')
    context = amended_wizard_context(draft['structured_source']['context'], prompt)
    draft['revision'] += 1
    draft['sources'].append({'text': request.requirement, 'source': 'USER', 'operation_id': request.operation_id})
    draft['structured_source'].update(prompt=effective_wizard_prompt(prompt), context=context)
    draft['generation_policy'] = resolve_generation_policy(
        prompt,
        industry=draft.get('industry'),
        bus_types=context.get('technologies') or (),
    )
    draft.pop('model_proposal_id', None)
    return draft


def workflow(draft, run_id, name, scopes):
    from .wizard_commands import effective_wizard_prompt
    prompt = effective_wizard_prompt(draft['structured_source']['prompt'])
    for key, value in [('Lauf-ID', run_id), ('Projektname', name), ('Workflowumfang', '; '.join(scopes))]:
        prompt = re.sub(r'^- ' + key + r':[^\n]*\n?', '', prompt, flags=re.M)
        prompt = prompt.replace('Strukturierte Vorgaben fuer den Engineering-Agenten:',
            'Strukturierte Vorgaben fuer den Engineering-Agenten:\n- ' + key + ': ' + value, 1)
    context = deepcopy(draft['structured_source']['context'])
    context.pop('structured_draft_ref', None)
    context.update(project_id=current_project_id(), run_id=run_id, project_name=name,
        scope=scopes, scope_ids=scopes, agent_prompt=prompt,
        engineering_draft_ref={'draft_id': draft['draft_id'], 'revision': draft['revision']})
    return {'prompt': prompt, 'context': context, 'target': scopes[-1]}
