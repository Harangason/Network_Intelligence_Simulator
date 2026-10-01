from uuid import uuid4

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import project_draft
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools.wizard_commands import WizardCommand, resolve_request


def test_updated_shared_draft_preserves_run_and_scope_with_a_new_review_revision():
    authority = ToolAuthority('draft-amend-' + uuid4().hex)
    def call(data, handler):
        return execute(authority, 'draft-amend-test', Permission.GENERATE_PROPOSAL, data, handler)
    created = call({'action': 'CREATE', 'operation_id': uuid4().hex,
                    'requirement': 'Raspberry Pi mit drei Temperatursensoren'}, project_draft.command)
    draft = created.data['draft']
    owner = next(d for d in draft['devices'] if d['role'] == 'CONTROLLER')
    resolved = call({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 1,
                     'allow_simulation_defaults': True,
                     'devices': [{'device_id': d['id'], 'technology': 'ethernet',
                                  **({'owner_id': owner['id']} if d['role'] == 'SENSOR' else {})} for d in draft['devices']]}, project_draft.command)
    assert resolved.success, resolved.findings
    arguments = {'draft_id': draft['draft_id'], 'revision': 2, 'run_id': uuid4().hex,
                 'scope_ids': ['engineering_model'], 'project_name': 'Temperaturregelung'}
    prepared = call(arguments, project_draft.workflow_request).data
    start = WizardCommand(action='START', run_id=arguments['run_id'], operation_id=uuid4().hex,
                          target=prepared['target'], wizard_context=prepared['context'])
    started = call({}, lambda _: resolve_request(start, prepared['prompt'], {}, authority.project_id))
    assert started.success
    descriptor, wizard = started.data
    context = {'wizard_request': descriptor, 'agent_wizard_status': wizard}
    sensor = next(d for d in draft['devices'] if d['role'] == 'SENSOR')
    updated = call({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 2,
                    'devices': [{'device_id': sensor['id'], 'name': 'Einlasstemperatur'}]}, project_draft.command)
    assert updated.success, updated.findings
    prepared = call({**arguments, 'revision': 3}, project_draft.workflow_request).data
    continuation = WizardCommand(action='CONTINUE', run_id=start.run_id, operation_id=uuid4().hex,
                                 request_revision=descriptor['revision'])
    assert not call({}, lambda _: resolve_request(continuation, '', context, authority.project_id)).success
    amendment = continuation.model_copy(update={'action': 'AMEND', 'wizard_context': prepared['context']})
    assert not call({}, lambda _: resolve_request(amendment, prepared['prompt'].replace('ethernet', 'CAN_FD'), context, authority.project_id)).success
    amended = call({}, lambda _: resolve_request(amendment, prepared['prompt'], context, authority.project_id))
    assert amended.success, amended.findings
    new_descriptor, new_wizard = amended.data
    assert new_descriptor['run_id'] == descriptor['run_id']
    assert new_descriptor['parent_revision'] == descriptor['revision']
    assert new_descriptor['revision'] != descriptor['revision']
    assert new_descriptor['base_prompt'] == descriptor['prompt']
    assert new_wizard['scope_ids'] == ['engineering_model']
    assert new_wizard['engineering_draft_ref']['revision'] == 3
    assert 'Einlasstemperatur' in new_descriptor['prompt']
    newer_context = {'wizard_request': new_descriptor, 'agent_wizard_status': new_wizard}
    assert not call({}, lambda _: resolve_request(amendment, prepared['prompt'], newer_context, authority.project_id)).success
