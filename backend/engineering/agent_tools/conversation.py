"""Durable conversation state, serialized with the existing project transaction.

UI history is presentation only. Decisions, questions and run ownership are
server-owned and cannot be replaced by stale browser history.
"""
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend.agent_core.api.agent_response import AgentInput, InteractiveQuestion
from ..db import get_connection, ConcurrentUpdateError
from ..project_context import current_project_id
from .model import model_revision
from copy import deepcopy


def read():
    with get_connection() as conn:
        conn.execute('INSERT INTO engineering_agent_conversations(project_id) VALUES (%s) ON CONFLICT DO NOTHING', (current_project_id(),))
        state = conn.execute('SELECT state FROM engineering_agent_conversations WHERE project_id=%s FOR UPDATE', (current_project_id(),)).fetchone()['state']
    return {'conversation_id': current_project_id(), 'current_question': None, 'answered_questions': {},
        'questions': {}, 'active_proposal': None, 'active_workload': None, 'pending_approvals': [],
        'selected_context': {}, 'decisions': {}, **state}


def write(state):
    with get_connection() as conn:
        conn.execute('UPDATE engineering_agent_conversations SET state=%s, modified_at=now() WHERE project_id=%s', (Jsonb(state), current_project_id()))
    return state


def inspect():
    state = read()
    revision = model_revision()
    for question in state['questions'].values():
        if question['status'] == 'OPEN' and question.get('model_revision') != revision:
            question['status'] = 'OUTDATED'
        elif question['status'] == 'OPEN' and question.get('expires_at', '') < datetime.now(timezone.utc).isoformat():
            question['status'] = 'EXPIRED'
    for decision in state['decisions'].values():
        if decision.get('review_on_change') and decision.get('model_revision') != revision:
            decision['status'] = 'NEEDS_REVIEW'
    if state['pending_approvals']:
        with get_connection() as conn:
            rows = conn.execute('SELECT proposal_id, engineering_contract FROM engineering_ai_proposals WHERE project_id=%s AND proposal_id::text = ANY(%s)',
                (current_project_id(), state['pending_approvals'])).fetchall()
        state['pending_approvals'] = [str(row['proposal_id']) for row in rows if row['engineering_contract'].get('status') not in {'APPLIED', 'REJECTED'}]
    return write(state)


def begin(prompt, context, raw_input=None):
    state = inspect()
    now = datetime.now(timezone.utc)
    if state.get('run_id') and state.get('lease_until', '') > now.isoformat():
        raise ConcurrentUpdateError('In diesem Gespräch läuft bereits ein Auftrag. Bitte dessen Antwort abwarten.')
    selected = {'active_view': context.active_view, 'selected_object_refs': context.selected_object_refs}
    if raw_input is not None and AgentInput.model_validate(raw_input).type == 'FINDING_ACTION':
        finding_id = AgentInput.model_validate(raw_input).finding_id
        finding = state.get('findings', {}).get(finding_id)
        if not finding:
            raise LookupError('Das Finding ist nicht mehr verfügbar.')
        prompt = 'Schlage eine fachlich begründete Maßnahme zu diesem Finding vor. Prüfe die betroffenen Objekte und erzeuge Änderungen ausschließlich als Review-Vorschlag. Finding: ' + finding.get('text', '')
        state.update(current_requirement=prompt, current_question=None, answered_questions={}, active_proposal=None, active_workload=None)
        for question in state['questions'].values():
            if question['status'] == 'OPEN':
                question['status'] = 'OUTDATED'
    elif raw_input is not None and AgentInput.model_validate(raw_input).type == 'RESUME':
        if not state.get('current_requirement') or state['current_question']:
            raise ValueError('Bitte zuerst die offene Frage beantworten oder eine Anforderung eingeben.')
        if state['selected_context'] != selected:
            raise ConcurrentUpdateError('Der Kontext hat sich geändert. Bitte die Anforderung erneut stellen.')
        prompt = state['current_requirement']
    elif raw_input is not None:
        answer = AgentInput.model_validate(raw_input)
        question = state['questions'].get(answer.question_id)
        if not question or question['status'] != 'OPEN' or state['current_question'] != answer.question_id:
            raise ConcurrentUpdateError('Diese Frage ist nicht mehr offen. Bitte den aktuellen Gesprächsstand laden.')
        if state['selected_context'] != selected:
            raise ConcurrentUpdateError('Der Auswahlkontext hat sich geändert. Bitte die Anforderung im neuen Kontext stellen.')
        options = {o['id']: o for o in question['options']}
        ids = answer.selected_options
        if answer.type == 'SKIP_QUESTION':
            if question['required']:
                raise ValueError('Diese Engineering-Entscheidung ist erforderlich.')
            question['status'] = 'SKIPPED'
        else:
            if not ids or len(ids) != len(set(ids)) or any(i not in options or options[i]['disabled'] for i in ids):
                raise ValueError('Bitte gültige verfügbare Optionen auswählen.')
            if question['selection_mode'] == 'SINGLE' and len(ids) != 1:
                raise ValueError('Genau eine Option ist erforderlich.')
            question['status'] = 'ANSWERED'
        question['selected_options'] = ids
        key = question.get('decision_key', answer.question_id)
        state['answered_questions'][key] = {'question_id': answer.question_id, 'selected_options': ids,
            'labels': [options[i]['label'] for i in ids], 'status': question['status']}
        state['current_question'] = None
        prompt = state.get('current_requirement', '')
    else:
        for question in state['questions'].values():
            if question['status'] == 'OPEN':
                question['status'] = 'OUTDATED'
        state['answered_questions'] = {}
        state['current_question'] = None
        state['current_requirement'] = prompt
        state['active_proposal'] = None
    state['selected_context'] = selected
    if ('Strukturierte Vorgaben fuer den Engineering-Agenten:' in prompt
            and 'per Wizard-Uebernehmen bestaetigt' in prompt):
        import re
        import hashlib
        from ..workflow.service import WorkflowStatusService
        canonical_prompt = re.sub(r'\nFortsetzung des bestätigten Wizard-Auftrags:[^\r\n]*', '', prompt).strip()
        request_contract = {'version': 1, 'prompt': canonical_prompt,
            'sha256': hashlib.sha256(canonical_prompt.encode('utf-8')).hexdigest()}
        workflow = WorkflowStatusService(current_project_id())
        saved = workflow.get(summary=True)
        if saved.get('context', {}).get('wizard_request') != request_contract:
            workflow.set_context({'wizard_request': request_contract}, summary=True)
    state['run_id'] = str(uuid4())
    state['lease_until'] = (now + timedelta(seconds=300)).isoformat()
    write(state)
    restored = context.model_copy(update={'current_requirement': prompt,
        'current_workload': state.get('active_workload') if raw_input else context.current_workload,
        'answered_questions': state['answered_questions'], 'active_proposal': state.get('active_proposal') if raw_input else None,
        'unresolved_findings': [{**finding, 'decision':state['decisions'].get(finding_id, {'status':'OPEN'})}
            for finding_id, finding in list(state.get('findings', {}).items())[-100:]]})
    return {'run_id': state['run_id'], 'prompt': prompt, 'context': restored.model_dump()}


def record_event(run_id, event):
    state = read()
    if state.get('run_id') != run_id:
        raise ConcurrentUpdateError('Dieser Agentenlauf ist abgelaufen.')
    with get_connection() as conn:
        conn.execute('INSERT INTO engineering_agent_responses(project_id, response_id, body) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',
            (current_project_id(), event['id'], Jsonb(event)))
    event = deepcopy(event)
    if len(event.get('text', '')) > 700 or event.get('metadata', {}).get('details') is not None:
        event['text'] = event.get('text', '')[:700]
        event.setdefault('metadata', {}).pop('details', None)
        event['metadata']['detail_id'] = event['id']
    if event.get('question'):
        question = InteractiveQuestion.model_validate(event['question']).model_dump()
        question.update(model_revision=model_revision(), decision_key=event.get('metadata', {}).get('decision_key', question['id']),
            expires_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
        state['questions'][question['id']] = question
        state['current_question'] = question['id']
        # Bound snapshots while preserving the currently open question.
        state['questions'] = dict(list(state['questions'].items())[-100:])
    if event.get('proposal'):
        state['active_proposal'] = event['proposal']['proposal_id']
        state['pending_approvals'] = list(dict.fromkeys([*state['pending_approvals'], state['active_proposal']]))[-100:]
    workload_id = (event.get('workload') or {}).get('workload_id')
    if isinstance(workload_id, str) and workload_id.strip():
        state['active_workload'] = workload_id
    if event['type'] == 'FINDING':
        state.setdefault('findings', {})[event['id']] = event
        state['findings'] = dict(list(state['findings'].items())[-100:])
    write(state)
    return event


def response_detail(response_id):
    with get_connection() as conn:
        row = conn.execute('SELECT body FROM engineering_agent_responses WHERE project_id=%s AND response_id=%s', (current_project_id(), response_id)).fetchone()
    if not row:
        raise LookupError('Die Antwort ist in diesem Projekt nicht vorhanden.')
    return row['body']


def finish(run_id):
    state = read()
    if state.get('run_id') == run_id:
        state['run_id'] = None
        write(state)


def renew(run_id, seconds=300):
    lease_until = (datetime.now(timezone.utc) + timedelta(seconds=max(60, int(seconds)))).isoformat()
    # Change only the lease field: replacing the complete JSON document from
    # the heartbeat could discard a simultaneously stored agent event.
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE engineering_agent_conversations
            SET state = jsonb_set(state, '{lease_until}', to_jsonb(%s::text), true),
                modified_at = now()
            WHERE project_id = %s AND state->>'run_id' = %s
            RETURNING project_id
            """,
            (lease_until, current_project_id(), run_id),
        ).fetchone()
    return row is not None


def decide(finding_id, decision, rationale, review_on_change):
    state = inspect()
    if finding_id not in state.get('findings', {}):
        raise LookupError('Finding ist in diesem Gespräch nicht vorhanden.')
    if decision not in {'MITIGATE', 'ACCEPTED_RISK', 'DEFERRED'}:
        raise ValueError('Unbekannte Entscheidung.')
    if decision == 'ACCEPTED_RISK' and (not isinstance(rationale, str) or len(rationale.strip()) < 10):
        raise ValueError('Bitte die Risikoübernahme mit mindestens 10 Zeichen begründen.')
    state['decisions'][finding_id] = {'status': decision, 'rationale': str(rationale)[:4000],
        'review_on_change': bool(review_on_change), 'model_revision': model_revision(),
        'created_at': datetime.now(timezone.utc).isoformat()}
    return write(state)['decisions'][finding_id]


def _history_proposal_references(messages):
    """A chat cache carries references, never partial human-review contents."""
    result = deepcopy(messages)
    for message in result:
        for part in message.get('parts', []):
            data = part.get('data') if isinstance(part, dict) else None
            proposal = data.get('proposal') if isinstance(data, dict) else None
            if not isinstance(proposal, dict) or not proposal.get('proposal_id'):
                continue
            data['proposal'] = {
                **{key: proposal[key] for key in ('proposal_id', 'proposal_type', 'revision', 'status', 'workload_id') if key in proposal},
                'rationale': str(proposal.get('rationale', ''))[:2000],
                'content_state': 'REFERENCE',
                'change_count': proposal.get('change_count', len(proposal.get('changes') or [])),
                'canonical_count': proposal.get('canonical_count', len(proposal.get('canonical_ids') or [])),
                'changes': [], 'canonical_ids': [], 'assumptions': [], 'validation_result': {},
            }
    return result


def history(messages=None, *, clear=False):
    state = read()
    if clear:
        state['ui_history'] = []
        state['ui_updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
        write(state)
    elif messages is not None:
        if not isinstance(messages, list) or len(messages) > 60:
            raise ValueError('Der UI-Verlauf ist auf 60 Nachrichten begrenzt.')
        existing = {m['id']: m for m in state.get('ui_history', [])}
        for message in messages:
            if not isinstance(message, dict) or not isinstance(message.get('id'), str) or message.get('role') not in {'user', 'assistant'} or not isinstance(message.get('parts'), list) or len(message['parts']) > 150:
                raise ValueError('Ungültige UI-Nachricht.')
            for part in message['parts']:
                if not isinstance(part, dict) or not isinstance(part.get('type'), str):
                    raise ValueError('Ungültiger Nachrichteninhalt.')
                if part['type'] == 'data-engineering':
                    data = part.get('data')
                    if not isinstance(data, dict):
                        raise ValueError('Ungültige Engineering-Antwort.')
                    if data.get('type') not in {'CONTEXT', 'HEARTBEAT'}:
                        from backend.agent_core.api.agent_response import validate_response
                        if 'run_id' in data:
                            data.setdefault('metadata', {})['run_id'] = data.pop('run_id')
                        if data.get('type') in {'QUESTION','SINGLE_SELECT','MULTI_SELECT'} and not data.get('question'):
                            data['question'] = {'id':data.pop('question_id', str(uuid4())), 'question':data.get('text',''),
                                'selection_mode':'MULTI' if data['type']=='MULTI_SELECT' else 'SINGLE',
                                'options':[{**{k:v for k,v in o.items() if k!='value'},'id':o.get('id') or o.get('value')} for o in data.pop('options',[])]}
                        part['data'] = validate_response(data)
            previous = existing.get(message['id'])
            # A stale browser cannot erase parts of an already completed response.
            if previous is None or len(message['parts']) > len(previous['parts']):
                existing[message['id']] = message
        complete_questions = {_question_id(part) for message in existing.values() if not message['id'].startswith('restored-question-') for part in message['parts']}
        state['ui_history'] = _history_proposal_references([message for message in existing.values() if not (message['id'].startswith('restored-question-') and message['id'].removeprefix('restored-question-') in complete_questions)][-60:])
        state['ui_updated_at'] = int(datetime.now(timezone.utc).timestamp() * 1000)
        write(state)
    result = _history_proposal_references(state.get('ui_history', []))
    question_id = state.get('current_question')
    if not clear and question_id and not any(_question_id(part) == question_id for message in result for part in message['parts']):
        question = state['questions'][question_id]
        clean = {key:value for key,value in question.items() if key in InteractiveQuestion.model_fields}
        from backend.agent_core.api.agent_response import AgentResponse
        response = AgentResponse(type='MULTI_SELECT' if question['selection_mode']=='MULTI' else 'SINGLE_SELECT', question=clean).model_dump(mode='json', exclude_none=True)
        result.append({'id':f'restored-question-{question_id}', 'role':'assistant', 'parts':[{'type':'data-engineering', 'data':response}]})
    return {'messages':result[-60:], 'updatedAt':state.get('ui_updated_at') or (int(datetime.now(timezone.utc).timestamp() * 1000) if result else None)}


def _question_id(part):
    data = part.get('data') if isinstance(part, dict) and part.get('type') == 'data-engineering' else None
    question = data.get('question') if isinstance(data, dict) else None
    return question.get('id') if isinstance(question, dict) else None
