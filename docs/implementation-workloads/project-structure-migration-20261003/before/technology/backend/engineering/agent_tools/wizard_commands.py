"""Typed wizard commands and immutable request identity, independent of UI prose."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.agent_core.context.limits import MAX_REQUIREMENT_LENGTH
from ..db import ConcurrentUpdateError
from ..workflow.models import WORKFLOW_STEPS


class WizardCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['START', 'CONTINUE', 'AMEND']
    run_id: str = Field(min_length=8, max_length=120, pattern=r'^[A-Za-z0-9._-]+$')
    operation_id: str = Field(min_length=8, max_length=120, pattern=r'^[A-Za-z0-9._-]+$')
    request_revision: str | None = Field(default=None, max_length=128)
    target: str | None = None
    wizard_context: dict[str, Any] | None = None
    automatic: bool = False

    @model_validator(mode='after')
    def valid_target(self):
        if self.target is not None and self.target not in WORKFLOW_STEPS:
            raise ValueError('Unbekanntes Workflowziel.')
        if self.action == 'START' and (self.target is None or self.wizard_context is None):
            raise ValueError('Start benötigt Workflowziel und bestätigten Wizardkontext.')
        return self


def canonical_wizard_prompt(prompt: str) -> str:
    """Migrate historical continuation envelopes without changing confirmed input."""
    return re.split(r'\n\s*Fortsetzung des bestätigten Wizard-Auftrags:', str(prompt), maxsplit=1)[0].strip()


def effective_wizard_prompt(prompt: str) -> str:
    """Project explicitly amended fields into the generator's current header.

    The durable request remains an append-only record. Only an explicit typed
    AMEND envelope can replace a confirmed field; continuation prose cannot.
    The generator reads its header before the original task text, so keeping
    a second field at the end would silently ignore the user's amendment.
    """
    marker = '\n\nBestaetigte Ergaenzung des Nutzers:\n'
    if marker not in prompt:
        return prompt
    allowed = {'Hardware-Sollwerte', 'Systemcluster-Graph', 'Netzwerktechnologien',
               'Bus-Teilnehmergrenzen', 'Aktor-Befehle', 'Netzarchitektur-ID',
               'Netzarchitektur', 'Raumarchitektur', 'Geräteanschlüsse',
               'Bestätigte-Geräteanschlüsse', 'Geräte-Spezifikationen'}
    amended = {}
    for section in prompt.split(marker)[1:]:
        for line in section.splitlines():
            match = re.fullmatch(r'- ([^:\r\n]+):\s*(.*)', line)
            if match and match[1] in allowed:
                amended[match[1]] = line
    if not amended:
        return prompt
    lines = []
    for line in prompt.splitlines():
        match = re.fullmatch(r'- ([^:\r\n]+):\s*(.*)', line)
        if not match or match[1] not in amended:
            lines.append(line)
    return '\n'.join([*amended.values(), *lines])


def request_descriptor(prompt: str, run_id: str, target: str) -> dict:
    original = canonical_wizard_prompt(prompt)
    if (not original or len(original) > MAX_REQUIREMENT_LENGTH
            or 'Strukturierte Vorgaben fuer den Engineering-Agenten:' not in original
            or 'per Wizard-Uebernehmen bestaetigt' not in original):
        raise ValueError('Der vollständige bestätigte Wizardauftrag fehlt oder ist zu groß.')
    embedded_run = re.search(r'\bLauf-ID:\s*([A-Za-z0-9._-]{8,120})', original)
    if not embedded_run or embedded_run.group(1).rstrip('.') != run_id:
        raise ValueError('Die Lauf-ID im bestätigten Auftrag stimmt nicht mit dem Kommando überein.')
    if target not in WORKFLOW_STEPS:
        raise ValueError('Unbekanntes Workflowziel.')
    digest = hashlib.sha256(json.dumps({'run_id': run_id, 'prompt': original, 'target': target},
                                      ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {'version': 2, 'run_id': run_id, 'revision': digest, 'sha256': digest,
            'prompt': original, 'target': target}


def amended_wizard_context(wizard: dict, prompt: str) -> dict:
    """Keep the displayed confirmed scope aligned with the effective AMEND header."""
    wizard = dict(wizard)
    effective = effective_wizard_prompt(prompt)
    latest = prompt.rsplit('\n\nBestaetigte Ergaenzung des Nutzers:\n', 1)[-1]
    changed = set(re.findall(r'^- ([^:\r\n]+):', latest, re.M))
    counts_match = re.search(r'^- Hardware-Sollwerte:\s*(\{[^\r\n]+\})\s*$', effective, re.M)
    if counts_match and 'Hardware-Sollwerte' in changed:
        counts = json.loads(counts_match[1])
        if (not isinstance(counts, dict) or any(key not in {'gateways', 'ecus', 'sensors', 'actuators'}
                or type(value) is not int or not 0 <= value <= 1000 for key, value in counts.items())):
            raise ValueError('Die ergänzten Hardware-Sollwerte sind ungültig.')
        wizard['hardware_counts'] = {**wizard.get('hardware_counts', {}), **counts}
    graph_match = re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])\s*$', effective, re.M)
    if graph_match and 'Systemcluster-Graph' in changed:
        graph = json.loads(graph_match[1])
        if not isinstance(graph, list) or any(not isinstance(cluster, dict) for cluster in graph):
            raise ValueError('Der ergänzte Systemcluster-Graph ist ungültig.')
        old_clusters = {item.get('cluster_id'): item for item in wizard.get('system_cluster_assignments', [])}
        old_branches = {item['name']: item for cluster in old_clusters.values() for item in cluster.get('tree', [])}
        old_leaves = {item['name']: item for branch in old_branches.values()
                      for item in [*branch.get('sensors', []), *branch.get('actuators', [])]}
        assignments = []
        for cluster in graph:
            old = old_clusters.get(cluster.get('cluster_id'), {})
            branches = []
            for controller in cluster.get('controllers', []):
                name = controller.get('ecu')
                if not isinstance(name, str) or not name.strip():
                    raise ValueError('Ein Controller im ergänzten Graph hat keinen Namen.')
                branch = {**old_branches.get(name, {}), 'name': name}
                branch.setdefault('interfaceType', '')
                for key, role in [('sensors', 'SensorController'), ('actuators', 'ActuatorController')]:
                    names = controller.get(key, [])
                    if not isinstance(names, list) or any(not isinstance(item, str) or not item.strip() for item in names):
                        raise ValueError('Ein Teilnehmer im ergänzten Graph hat keinen Namen.')
                    branch[key] = [{**old_leaves.get(item, {}), 'name': item, 'deviceType': role,
                                    'interfaceType': old_leaves.get(item, {}).get('interfaceType', ''),
                                    'confidence': old_leaves.get(item, {}).get('confidence', 0),
                                    'reason': 'Vom Nutzer in der Auftragsergänzung diesem Controller zugeordnet.'} for item in names]
                branches.append(branch)
            counts = {'ECU': len(branches), 'SensorController': sum(len(item['sensors']) for item in branches),
                      'ActuatorController': sum(len(item['actuators']) for item in branches)}
            old_unassigned = {item['name']: item for item in old.get('unassigned', [])}
            unassigned = [{**old_unassigned.get(name, {}), 'name': name,
                           'deviceType': old_unassigned.get(name, {}).get('deviceType', 'Unknown'),
                           'interfaceType': old_unassigned.get(name, {}).get('interfaceType', ''),
                           'confidence': 0, 'reason': 'Noch ohne bestätigte Controller-Zuordnung.'}
                          for name in cluster.get('unassigned', [])]
            assignments.append({**old, **{key: cluster.get(key, old.get(key, '')) for key in
                ('cluster_id', 'label', 'network_id', 'network_label', 'bus_name')}, 'selected': True,
                'tree': branches, 'counts': counts, 'devices': sum(counts.values()) + len(unassigned), 'unassigned': unassigned,
                'evidence': ['Explizit bestätigte Auftragsergänzung.'], 'hmi_routes': cluster.get('hmi_routes', []),
                'validation': {'valid': False, 'warnings': ['Ergänzten Graph im Modellvorschlag prüfen.']}})
        wizard['system_cluster_assignments'] = assignments
        wizard['system_cluster_graph'] = graph
    return wizard


def resolve_request(command: WizardCommand, prompt: str, context: dict, project_id: str) -> tuple[dict, dict]:
    """Resolve one immutable request; callers hold the project transaction."""
    saved = context.get('wizard_request') or {}
    wizard = context.get('agent_wizard_status') or {}
    if command.action == 'START':
        wizard = dict(command.wizard_context or {})
        if wizard.get('project_id') != project_id or wizard.get('run_id') != command.run_id:
            raise ConcurrentUpdateError('Projekt oder Lauf des Wizardauftrags stimmt nicht überein.')
        scopes = wizard.get('scope_ids') or []
        requested = [step for step in WORKFLOW_STEPS if step in scopes]
        if not requested or command.target != requested[-1]:
            raise ValueError('Das Workflowziel muss dem bestätigten Auftragsumfang entsprechen.')
        if wizard.get('engineering_draft_ref'):
            from .project_draft import workflow_request
            source = wizard['engineering_draft_ref']
            prepared = workflow_request({**source, 'run_id': command.run_id,
                                         'scope_ids': scopes, 'project_name': wizard.get('project_name', '')})
            if canonical_wizard_prompt(prompt) != canonical_wizard_prompt(prepared['prompt']):
                raise ConcurrentUpdateError('Die bestätigten Entwurfsangaben stimmen nicht mit dem Workflowauftrag überein.')
            wizard = {**wizard, **prepared['context']}
        descriptor = request_descriptor(prompt, command.run_id, command.target)
        if saved.get('version') == 2 and saved.get('run_id') == command.run_id and saved.get('revision') != descriptor['revision']:
            raise ConcurrentUpdateError('Der bestätigte Auftrag ist unveränderlich. Änderungen benötigen einen neuen Auftrag.')
        wizard.update(agent_prompt=descriptor['prompt'], status='RUNNING', request_revision=descriptor['revision'])
        return descriptor, wizard
    if wizard.get('run_id') != command.run_id:
        raise ConcurrentUpdateError('Dieser Wizardauftrag ist nicht mehr der aktuelle Projektauftrag.')
    if wizard.get('engineering_draft_ref') and command.action != 'AMEND':
        from .project_draft import inspect as inspect_draft
        draft = inspect_draft()
        source = wizard['engineering_draft_ref']
        if not draft or draft['draft_id'] != source.get('draft_id') or draft['revision'] != source.get('revision'):
            raise ConcurrentUpdateError('Der zugrunde liegende Entwurf wurde geändert. Den aktualisierten Entwurf prüfen und einen neuen Auftrag starten.')
    if wizard.get('status') == 'CANCELED':
        raise ConcurrentUpdateError('Ein abgebrochener Auftrag kann nicht fortgesetzt werden.')
    if saved.get('version') != 2 or saved.get('run_id') != command.run_id:
        scopes = wizard.get('scope_ids') or []
        target = next((step for step in reversed(WORKFLOW_STEPS) if step in scopes), None)
        descriptor = request_descriptor(str(wizard.get('agent_prompt') or ''), command.run_id, target)
        if command.request_revision and command.request_revision != descriptor['revision']:
            raise ConcurrentUpdateError('Die Auftragsrevision hat sich geändert. Bitte aktuellen Stand laden.')
    else:
        descriptor = saved
        if command.request_revision != descriptor['revision']:
            raise ConcurrentUpdateError('Die Auftragsrevision hat sich geändert. Bitte aktuellen Stand laden.')
    if command.target is not None and command.target != descriptor['target']:
        raise ConcurrentUpdateError('Das Workflowziel gehört zum bestätigten Auftrag und kann nicht beim Fortsetzen geändert werden.')
    if command.action == 'AMEND':
        if wizard.get('engineering_draft_ref') or (wizard.get('structured_draft_ref') and (command.wizard_context or {}).get('engineering_draft_ref')):
            from .draft_workflow_revision import amend
            return amend(command, prompt, descriptor, {**wizard, 'engineering_draft_ref': wizard.get('engineering_draft_ref') or wizard['structured_draft_ref']})
        addition = prompt.strip()
        if not addition or len(addition) > 16000:
            raise ValueError('Eine Ergänzung benötigt 1 bis 16000 Zeichen.')
        parent = descriptor
        descriptor = request_descriptor(parent['prompt'] + '\n\nBestaetigte Ergaenzung des Nutzers:\n' + addition,
                                        command.run_id, parent['target'])
        descriptor.update(parent_revision=parent['revision'], base_prompt=parent.get('base_prompt', parent['prompt']),
                          amendments=[*(parent.get('amendments') or []), addition])
        wizard = amended_wizard_context(wizard, descriptor['prompt'])
        wizard['task'] = str(wizard.get('task') or '') + '\n\n' + addition
    wizard = {**wizard, 'agent_prompt': descriptor['prompt'], 'request_revision': descriptor['revision']}
    return descriptor, wizard


def receipt(command: WizardCommand, request: dict, *, duplicate: bool = False) -> dict:
    return {'accepted': True, 'duplicate': duplicate, 'run_id': command.run_id,
            'operation_id': command.operation_id, 'request_revision': request['revision'], 'target': request['target']}


def command_fingerprint(command: WizardCommand, prompt: str, raw_input: dict | None = None) -> str:
    from backend.agent_core.api.agent_response import AgentInput
    payload = {'command': command.model_dump(), 'prompt': prompt if command.action in {'START', 'AMEND'} else '',
               'input': AgentInput.model_validate(raw_input).model_dump() if raw_input is not None else None}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
