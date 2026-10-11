"""Adopt a reviewed shared-draft revision without abandoning its workflow run."""
from ..db import ConcurrentUpdateError


def amend(command, prompt, descriptor, wizard):
    from .project_draft import workflow_request
    from .wizard_commands import canonical_wizard_prompt, request_descriptor

    previous = wizard['engineering_draft_ref']
    requested = (command.wizard_context or {}).get('engineering_draft_ref')
    if not isinstance(requested, dict) or requested.get('draft_id') != previous.get('draft_id'):
        raise ConcurrentUpdateError('Den zugehörigen gemeinsamen Entwurf bearbeiten, speichern und im Auftrag übernehmen.')
    revision = requested.get('revision')
    if not isinstance(revision, int) or revision <= previous.get('revision', 0):
        raise ConcurrentUpdateError('Für diese Ergänzung ist eine neuere gespeicherte Entwurfsrevision erforderlich.')
    # Scope and project name remain bound to the original run. The caller cannot
    # broaden execution authority while adopting a newer inventory revision.
    prepared = workflow_request({**requested, 'run_id': command.run_id,
                                 'scope_ids': wizard['scope_ids'], 'project_name': wizard['project_name']})
    if canonical_wizard_prompt(prompt) != canonical_wizard_prompt(prepared['prompt']):
        raise ConcurrentUpdateError('Die bestätigte Ergänzung entspricht nicht dem gespeicherten Projektentwurf.')
    replacement = request_descriptor(prepared['prompt'], command.run_id, descriptor['target'])
    replacement.update(parent_revision=descriptor['revision'],
                       base_prompt=descriptor.get('base_prompt', descriptor['prompt']),
                       draft_revisions=[*(descriptor.get('draft_revisions') or [previous]), requested])
    return replacement, {**wizard, **prepared['context'], 'agent_prompt': replacement['prompt'],
                          'request_revision': replacement['revision']}
