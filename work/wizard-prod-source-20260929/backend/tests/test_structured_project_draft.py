"""Actual durable wizard/draft migration and same-run adoption, isolated SQL."""
import json
from copy import deepcopy
from uuid import uuid4

from backend.agent_core.api.tool_contract import Permission
from backend.agent_core.context.agent_context import AgentContext
from backend.engineering.agent_tools import conversation, project_draft
from backend.engineering.agent_tools.runtime import ToolAuthority, execute
from backend.engineering.workflow.service import WorkflowStatusService


def test_native_wizard_draft_preserves_complete_source_and_adopts_chat_revision():
    authority = ToolAuthority('structured-draft-' + uuid4().hex)
    run = uuid4().hex
    graph = [{'cluster_id': 'room-1', 'label': 'Raum', 'network_id': 'ethernet',
        'controllers': [{'ecu': 'Regler', 'sensors': ['Temperatur'], 'actuators': []}],
        'hmi_routes': [{'source': 'Regler', 'target': 'Anzeige', 'enabled': False}]}]
    prompt = ('Strukturierte Vorgaben fuer den Engineering-Agenten:\n'
        f'- Lauf-ID: {run}\n- Generierungsmodus: REAL_PROJECT\n'
        '- Projekt-Modelltyp: building_automation\n- Hardware-Sollwerte: {"ecus":1,"sensors":1}\n'
        '- Systemcluster-Graph: ' + json.dumps(graph) + '\n'
        '- Aktor-Befehle: {}\n- Bus-Teilnehmergrenzen: {"ethernet":8}\n'
        'Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:\n'
        'Regler und Temperatur. Lokal auswerten, nicht an Anzeige weiterleiten.')
    wizard = {'project_id': authority.project_id, 'run_id': run,
        'project_name': 'Raumregelung', 'scope_ids': ['engineering_model'], 'industry': 'building_automation',
        'task': 'Regler und Temperatur.', 'port_decisions': {'Regler': {'ports': ['ETH1', 'ETH2']}},
        'system_cluster_assignments': [{'cluster_id': 'room-1', 'tree': [
            {'name': 'Regler', 'interfaceType': 'Ethernet',
             'sensors': [{'name': 'Temperatur', 'interfaceType': 'Ethernet'}], 'actuators': []}]}]}
    context = AgentContext(active_project_id=authority.project_id, active_view='engineering')
    def call(handler, data=None):
        return execute(authority, 'structured-draft-test', Permission.GENERATE_PROPOSAL, data or {}, handler)
    command = {'action': 'START', 'run_id': run, 'operation_id': uuid4().hex,
        'target': 'engineering_model', 'wizard_context': wizard}
    started = call(lambda _: conversation.begin(prompt, context, wizard_command=command))
    assert started.success, started.findings
    assert call(lambda _: conversation.finish(started.data['run_id'])).success
    draft = call(project_draft.inspect).data
    assert draft['source_format'] == 'WIZARD_V2'
    assert draft['structured_source']['prompt'] == prompt
    assert draft['structured_source']['context']['port_decisions'] == wizard['port_decisions']
    assert len(draft['devices']) == 2
    assert call(lambda _: project_draft.planning_prompt(draft)).data == prompt
    previous = deepcopy(draft)
    amended = call(project_draft.command, {'action': 'AMEND', 'operation_id': uuid4().hex,
        'revision': 1, 'requirement': 'Temperatur alle 500 ms erfassen. HMI bleibt deaktiviert.'})
    assert amended.success, amended.findings
    draft = amended.data['draft']
    assert draft['revision'] == 2 and draft['draft_id'] == previous['draft_id']
    assert draft['devices'] == previous['devices']
    assert draft['structured_source']['context']['port_decisions'] == wizard['port_decisions']
    assert json.dumps(graph) in draft['structured_source']['prompt']
    revision = started.data['wizard_receipt']['request_revision']
    stale = call(lambda _: conversation.begin('', context, wizard_command={
        'action': 'CONTINUE', 'run_id': run, 'operation_id': uuid4().hex, 'request_revision': revision}))
    assert not stale.success and stale.status.value == 'CONFLICT'
    prepared = call(project_draft.workflow_request, {'draft_id': draft['draft_id'], 'revision': 2,
        'run_id': run, 'project_name': 'Raumregelung', 'scope_ids': ['engineering_model']})
    assert prepared.success, prepared.findings
    adopted = call(lambda _: conversation.begin(prepared.data['prompt'], context, wizard_command={
        'action': 'AMEND', 'run_id': run, 'operation_id': uuid4().hex, 'request_revision': revision,
        'wizard_context': prepared.data['context']}))
    assert adopted.success, adopted.findings
    saved = call(lambda _: WorkflowStatusService(authority.project_id).get(summary=True)).data['context']
    assert saved['agent_wizard_status']['run_id'] == run
    assert saved['agent_wizard_status']['engineering_draft_ref']['revision'] == 2
    assert '500 ms' in saved['wizard_request']['prompt']
    assert saved['agent_wizard_status']['port_decisions'] == wizard['port_decisions']
    assert call(lambda _: conversation.finish(adopted.data['run_id'])).success
    continuation = call(lambda _: conversation.begin('', context, wizard_command={
        'action': 'CONTINUE', 'run_id': run, 'operation_id': uuid4().hex,
        'request_revision': adopted.data['wizard_receipt']['request_revision']}))
    assert continuation.success, continuation.findings
