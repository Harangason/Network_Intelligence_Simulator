from uuid import uuid4

from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools import project_draft
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.agent_tools.wizard_commands import WizardCommand, resolve_request
from backend.engineering.agent_tools.wizard_generation import extract_specification


def test_chat_and_wizard_share_inventory_and_stale_start_is_rejected():
    authority = ToolAuthority('shared-draft-' + uuid4().hex)
    def call(data, handler):
        return execute(authority, 'shared-draft-test', Permission.GENERATE_PROPOSAL, data, handler)
    created = call({'action': 'CREATE', 'operation_id': uuid4().hex,
                    'requirement': 'Raspberry Pi mit drei Temperatursensoren'}, project_draft.command)
    draft = created.data['draft']
    owner = next(d for d in draft['devices'] if d['role'] == 'CONTROLLER')
    resolved = call({'action': 'RESOLVE', 'operation_id': uuid4().hex, 'revision': 1,
                     'allow_simulation_defaults': True,
                     'devices': [{'device_id': d['id'], 'technology': 'ethernet',
                                  **({'owner_id': owner['id']} if d['role'] == 'SENSOR' else {})} for d in draft['devices']]}, project_draft.command)
    assert resolved.success, resolved.findings
    draft = resolved.data['draft']
    run = uuid4().hex
    arguments = {'draft_id': draft['draft_id'], 'revision': 2, 'run_id': run,
                 'scope_ids': ['engineering_model'], 'project_name': 'Temperaturregelung'}
    prepared = call(arguments, project_draft.workflow_request)
    assert prepared.success, prepared.findings
    payload = prepared.data
    direct = extract_specification(project_draft.planning_prompt(draft))
    wizard = extract_specification(payload['prompt'])
    assert wizard['targetCounts'] == direct['targetCounts']
    assert wizard['chains'] == direct['chains']
    command = WizardCommand(action='START', run_id=run, operation_id=uuid4().hex,
                            target=payload['target'], wizard_context=payload['context'])
    started = call({}, lambda _: resolve_request(command, payload['prompt'], {}, authority.project_id))
    assert started.success, started.findings
    forged = call({}, lambda _: resolve_request(command, payload['prompt'].replace('ethernet', 'CAN_FD'), {}, authority.project_id))
    assert not forged.success
    assert call({'action': 'AMEND', 'operation_id': uuid4().hex, 'revision': 2,
                 'requirement': 'Die Regelungsaufgabe wird noch präzisiert.'}, project_draft.command).success
    assert not call({}, lambda _: resolve_request(command, payload['prompt'], {}, authority.project_id)).success
