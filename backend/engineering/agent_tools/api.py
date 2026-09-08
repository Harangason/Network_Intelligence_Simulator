"""Human-facing agent/review API. Approval is intentionally absent from MCP."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hmac
import json
import os
from queue import Queue, Empty
import secrets
import threading
from urllib.parse import urlparse
from uuid import uuid4
from flask import Blueprint, Response, jsonify, request, stream_with_context
from pydantic import ValidationError
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.agent_core.api.tool_contract import Permission
from backend.agent_core.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.simulator_engineering_mcp.server import create_server
from ..project_context import normalize_context_project_id
from .runtime import ToolAuthority, DEFAULT_PERMISSIONS, execute
from .services import TOOLS
from . import proposal_service as proposals
from . import conversation
from .run_status import WizardExecutionTracker, extract_wizard_run_id, reconcile_model_apply, restore_wizard_continuation_prompt
from .cancellation import RunCancellation, request_cancel
from ..workflow.service import WorkflowStatusService
from datetime import datetime, timezone
from backend.agent_core.api.agent_response import validate_response

agent_api = Blueprint("engineering_agent_api", __name__)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="engineering-agent")
_slots = threading.BoundedSemaphore(4)
COOKIE = "engineering_review_csrf"
_PROPOSAL_STATUS_FIELDS = (
    "proposal_id", "proposal_type", "revision", "status", "validation_result", "canonical_ids", "workload_id",
)


def _project() -> str:
    return normalize_context_project_id(request.headers.get("X-Project-ID") or request.args.get("project") or "default")


@agent_api.get("/review-session")
def review_session():
    token = secrets.token_urlsafe(32)
    response = jsonify({"csrf_token": token})
    response.set_cookie(COOKIE,token,httponly=True,samesite="Strict",secure=request.is_secure,path="/api/engineering/agent",max_age=1800)
    response.headers["Cache-Control"] = "no-store"
    return response


def _human_intent() -> bool:
    cookie, supplied = request.cookies.get(COOKIE,""), request.headers.get("X-Review-CSRF", "")
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).hostname not in {"localhost", "127.0.0.1", "::1", request.host.split(":")[0]}:
        return False
    return bool(cookie and supplied and hmac.compare_digest(cookie,supplied)) and request.headers.get("X-Human-Review")=="confirmed"


def _proposal_status_payload(result) -> dict:
    """Keep polling and mutation responses small even for topology proposals."""
    payload = result.model_dump(mode="json")
    if isinstance(result.data, dict):
        payload["data"] = {key: result.data[key] for key in _PROPOSAL_STATUS_FIELDS if key in result.data}
    return payload


@agent_api.get("/proposals/<proposal_id>")
def proposal_get(proposal_id):
    authority = ToolAuthority(_project(),"review-ui")
    result = execute(authority,"inspect_proposal",Permission.READ_MODEL,{"proposal_id":proposal_id},lambda a:proposals.latest(a["proposal_id"]))
    payload = _proposal_status_payload(result) if request.args.get("view") == "status" else result.model_dump(mode="json")
    return jsonify(payload), 200 if result.success else 404


@agent_api.post("/proposals/<proposal_id>/review")
def proposal_review(proposal_id):
    if not _human_intent():
        return jsonify({"error":"Die bewusste Freigabe in der Review-Oberfläche ist erforderlich."}),403
    data = request.get_json(silent=True) or {}
    authority = ToolAuthority(_project(),"local-human")
    result = execute(authority,"human_review",Permission.READ_MODEL,{},lambda a:proposals.review(proposal_id,
        revision=str(data.get("revision") or ""),decision=str(data.get("decision") or ""),actor=authority.actor,trace_id=a["_trace_id"]))
    return jsonify(result.model_dump(mode="json")),200 if result.success else 409


@agent_api.post("/proposals/<proposal_id>/apply")
def proposal_apply(proposal_id):
    if not _human_intent():
        return jsonify({"error":"Die bewusste Übernahme in der Review-Oberfläche ist erforderlich."}),403
    authority = ToolAuthority(_project(),"local-human",DEFAULT_PERMISSIONS|{Permission.APPLY_APPROVED_PROPOSAL})
    def apply_and_reconcile(args):
        proposal = proposals.apply(args["proposal_id"], actor=authority.actor, trace_id=args["_trace_id"])
        # One transaction: an applied model must never leave the wizard at its
        # old review gate if updating the durable continuation state fails.
        reconcile_model_apply(authority.project_id, proposal)
        return proposal
    result = execute(authority,"apply_approved_proposal",Permission.APPLY_APPROVED_PROPOSAL,{"proposal_id":proposal_id},
                     apply_and_reconcile)
    payload = _proposal_status_payload(result) if request.args.get("view") == "status" else result.model_dump(mode="json")
    return jsonify(payload),200 if result.success else 409


@agent_api.post("/proposals/<proposal_id>/validate")
def proposal_validate(proposal_id):
    authority = ToolAuthority(_project(),"review-ui")
    result = execute(authority,"validate_proposal",Permission.VALIDATE,{"proposal_id":proposal_id},lambda a:proposals.validate(a["proposal_id"]))
    return jsonify(result.model_dump(mode="json")),200 if result.success else 409


@agent_api.post('/proposals/<proposal_id>/revise')
def proposal_revise(proposal_id):
    if not _human_intent():
        return jsonify({'error': 'Eine bewusste Bearbeitung in der Oberfläche ist erforderlich.'}), 403
    data = request.get_json(silent=True) or {}
    def revise(args):
        old = proposals.get(proposal_id)
        if old['status'] in {'APPLIED', 'REJECTED'} or old['revision'] != data.get('revision'):
            raise ValueError('Dieser Vorschlag kann in diesem Stand nicht bearbeitet werden.')
        names = data.get('names')
        if not isinstance(names, dict) or len(names) > len(old['changes']):
            raise ValueError('Ungültige Änderungsnamen.')
        if set(names) - {change['local_ref'] for change in old['changes'] if change['action'] in {'CREATE','UPDATE'} and (change.get('data') or {}).get('name')}:
            raise ValueError('Nur Namen vorhandener Anlege- oder Änderungsvorschläge sind editierbar.')
        for change in old['changes']:
            ref = change['local_ref']
            if ref in names:
                name = names[ref]
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
                    raise ValueError('Objektnamen benötigen 1 bis 200 Zeichen.')
                change.setdefault('data', {})['name'] = name.strip()
        rationale = data.get('rationale', old['rationale'])
        if not isinstance(rationale, str) or not 1 <= len(rationale.strip()) <= 30000:
            raise ValueError('Eine Beschreibung der Änderung ist erforderlich.')
        revised = proposals.create(old['proposal_type'], old['changes'], rationale, assumptions=old['assumptions'],
            evidence=[{'source':'human_revision','previous_proposal_id':proposal_id}])
        proposals.review(proposal_id, revision=old['revision'], decision='reject', actor='local-human', trace_id=args['_trace_id'])
        proposals.set_replacement(proposal_id, revised['proposal_id'])
        state = conversation.read()
        state['active_proposal'] = revised['proposal_id']
        state['pending_approvals'] = list(dict.fromkeys([*state['pending_approvals'], revised['proposal_id']]))[-100:]
        conversation.write(state)
        return proposals.validate(revised['proposal_id'])
    result = execute(ToolAuthority(_project(), 'local-human'), 'revise_proposal', Permission.GENERATE_PROPOSAL, {}, revise)
    return jsonify(result.model_dump(mode='json')), 200 if result.success else 409


@agent_api.post('/runs/<wizard_run_id>/cancel')
def cancel_wizard(wizard_run_id):
    if (request.get_json(silent=True) or {}).get('confirmed') is not True:
        return jsonify({'error': 'Bitte den Abbruch ausdrücklich bestätigen.'}), 400
    project_id = _project()
    def cancel(_):
        service = WorkflowStatusService(project_id)
        workflow = service.get(summary=True)
        context = workflow.get('context') or {}
        execution = context.get('agent_execution') or {}
        wizard = context.get('agent_wizard_status') or {}
        if wizard_run_id != (execution.get('run_id') or wizard.get('run_id')):
            raise ValueError('Dieser Auftrag ist nicht mehr der aktuelle Projektauftrag.')
        state = conversation.read()
        if state.get('run_id') and extract_wizard_run_id(state.get('current_requirement', '')) != wizard_run_id:
            raise ValueError('Ein anderer Auftrag läuft; dieser wird nicht abgebrochen.')
        running_here = request_cancel(project_id, wizard_run_id)
        if not running_here and state.get('run_id'):
            conversation.finish(state['run_id'])
        if state.get('active_workload') and extract_wizard_run_id(state.get('current_requirement', '')) == wizard_run_id:
            from ..workloads import EngineeringWorkloadOrchestrator
            workloads = EngineeringWorkloadOrchestrator(project_id)
            if workloads.get_workload(state['active_workload'])['status'] not in {'COMPLETED', 'CANCELED'}:
                workloads.cancel(state['active_workload'], actor='local-human')
        now = datetime.now(timezone.utc).isoformat()
        updated = {'agent_execution': {**execution, 'run_id': wizard_run_id, 'state': 'CANCELED',
            'step': execution.get('step') or workflow['active_step'],
            'completed': execution.get('completed', 0), 'total': execution.get('total', 0),
            'message': 'Auftrag abgebrochen. Bereits übernommene Modelldaten bleiben erhalten.', 'updated_at': now}}
        if wizard.get('run_id') == wizard_run_id:
            updated['agent_wizard_status'] = {**wizard, 'status': 'CANCELED', 'canceled_at': now}
        return service.set_context(updated, summary=True)
    result = execute(ToolAuthority(project_id, 'local-human'), 'cancel_wizard_run', Permission.READ_MODEL, {}, cancel)
    return jsonify(result.model_dump(mode='json')), 200 if result.success else 409


@agent_api.post("/chat")
def chat():
    payload = request.get_json(silent=True)
    if not isinstance(payload,dict) or (not payload.get('input') and (not isinstance(payload.get("prompt"),str) or not payload["prompt"].strip())):
        return jsonify({"error":"Eine Anforderung als prompt ist erforderlich."}),400
    payload.setdefault('prompt', '')
    history = payload.get("history") or []
    if not isinstance(history, list) or len(history) > 12 or any(not isinstance(item, dict) or item.get("role") not in {"user", "assistant"} or not isinstance(item.get("content"), str) or len(item["content"]) > 8000 for item in history):
        return jsonify({"error":"Ungültiger Gesprächskontext."}),400
    history = [{"role":item["role"], "content":item["content"]} for item in history]
    project_id = _project()
    workflow = WorkflowStatusService(project_id).get(summary=True)
    payload['prompt'] = restore_wizard_continuation_prompt(
        payload['prompt'],
        (workflow.get('context') or {}).get('agent_wizard_status'),
    )
    raw_context = payload.get("context") or {}
    if not isinstance(raw_context, dict) or not isinstance(payload['prompt'], str) or len(payload["prompt"]) > 30000:
        return jsonify({"error":"Ungültiger Kontext oder zu lange Anforderung."}),400
    if raw_context.get("active_project_id") and normalize_context_project_id(raw_context["active_project_id"]) != project_id:
        return jsonify({"error":"Projekt in Header und Kontext stimmt nicht überein."}),409
    try:
        context = AgentContext.model_validate({**raw_context,"active_project_id":project_id,
            "permissions":[p.value for p in DEFAULT_PERMISSIONS]})
    except ValidationError as error:
        return jsonify({"error":str(error)}),400
    if not _slots.acquire(blocking=False):
        return jsonify({"error":"Alle Agentenplätze sind belegt. Bitte gleich erneut versuchen."}),429
    authority = ToolAuthority(project_id, 'conversation-ui')
    started = execute(authority, 'begin_conversation_turn', Permission.READ_MODEL, {},
        lambda _: conversation.begin(payload['prompt'], context, payload.get('input')))
    if not started.success:
        _slots.release()
        return jsonify(started.model_dump(mode='json')), 409 if started.status.value == 'CONFLICT' else 400
    run_id = started.data['run_id']
    context = AgentContext.model_validate(started.data['context'])
    queue: Queue = Queue()
    wizard_run_id = extract_wizard_run_id(started.data['prompt'])
    tracker = WizardExecutionTracker(project_id, wizard_run_id) if wizard_run_id else None
    if tracker:
        try:
            tracker.started()
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Wizard execution status could not be started (%s)', wizard_run_id)
            execute(authority, 'finish_conversation_turn', Permission.READ_MODEL, {}, lambda _: conversation.finish(run_id))
            _slots.release()
            return jsonify({"error":"Der serverseitige Laufstatus konnte nicht angelegt werden."}),503
    cancellation = RunCancellation(project_id, wizard_run_id or run_id)
    def emit(event):
        cancellation.check()
        if event['type'] != 'CONTEXT':
            event = validate_response(event)
            saved = execute(authority, 'record_conversation_response', Permission.READ_MODEL, {},
                lambda _: conversation.record_event(run_id, event))
            if not saved.success:
                raise RuntimeError('Gesprächszustand konnte nicht gespeichert werden.')
            event = saved.data
            if tracker:
                tracker.event(event)
        queue.put(event)
    async def run():
        cancellation.bind()
        if tracker:
            current = WorkflowStatusService(project_id).get(summary=True).get('context', {}).get('agent_execution', {})
            if current.get('run_id') == wizard_run_id and current.get('state') == 'CANCELED':
                raise asyncio.CancelledError()
        reasoner = LocalEngineeringReasoner()
        try:
            async with EngineeringMCPClient(create_server(ToolAuthority(project_id))) as client:
                result = await EngineeringAgent(client,reasoner=reasoner).run(started.data['prompt'],context,emit=emit,history=history)
                emit({"type":"CONTEXT","context":result["context"],"status":result["status"]})
                return result
        finally:
            await reasoner.close()
    def worker():
        heartbeat_stop = threading.Event()
        def heartbeat():
            while not heartbeat_stop.wait(30):
                if cancellation.cancelled.is_set():
                    return
                try:
                    conversation.renew(run_id)
                    if tracker:
                        tracker.heartbeat()
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception('Agent heartbeat failed (%s)', run_id)
        heartbeat_thread = threading.Thread(target=heartbeat, name=f"agent-heartbeat-{run_id[:8]}", daemon=True)
        heartbeat_thread.start()
        try:
            result = asyncio.run(asyncio.wait_for(run(), timeout=max(300, min(int(os.environ.get('ENGINEERING_AGENT_RUN_TIMEOUT_SECONDS', '1800')), 7200))))
            if tracker:
                tracker.finished(result)
        except asyncio.CancelledError:
            queue.put(validate_response({'type': 'RESULT', 'status': 'CANCELED',
                'text': 'Auftrag abgebrochen. Bereits übernommene Modelldaten bleiben erhalten.'}))
        except Exception as error:
            import logging
            logging.getLogger(__name__).exception('Agent conversation failed (%s)', run_id)
            message = "Der Agentenlauf konnte nicht fortgesetzt werden. Projekt- und Modelldienste prüfen."
            if isinstance(error, asyncio.TimeoutError):
                message = "Das Zeitlimit des Hintergrundlaufs wurde erreicht. Der letzte Projektstand bleibt erhalten."
            if tracker:
                tracker.failed(message)
            queue.put(validate_response({"type":"ERROR","status":"BLOCKED","text":message,"metadata":{"run_id":run_id},"actions":[{"type":"RETRY","label":"Erneut versuchen"}]}))
        finally:
            cancellation.close()
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)
            execute(authority, 'finish_conversation_turn', Permission.READ_MODEL, {}, lambda _: conversation.finish(run_id))
            _slots.release()
            queue.put(None)
    _executor.submit(worker)
    @stream_with_context
    def stream():
        try:
            while True:
                try:
                    item = queue.get(timeout=15)
                except Empty:
                    yield json.dumps({"type":"HEARTBEAT"})+"\n"
                    continue
                if item is None:
                    break
                yield json.dumps(item,ensure_ascii=False,default=str)+"\n"
        finally:
            # The server-owned worker intentionally survives a browser or proxy
            # disconnect. Its durable status is read through the workflow API.
            pass
    return Response(stream(),mimetype="application/x-ndjson",headers={"Cache-Control":"no-store","X-Accel-Buffering":"no"})


@agent_api.get('/conversation')
def conversation_get():
    result = execute(ToolAuthority(_project(), 'conversation-ui'), 'inspect_conversation', Permission.READ_MODEL, {}, lambda _: conversation.inspect())
    if result.success:
        result.data.pop('ui_history', None)
    return jsonify(result.model_dump(mode='json')), 200 if result.success else 503


@agent_api.get('/responses/<response_id>')
def response_detail(response_id):
    result = execute(ToolAuthority(_project(), 'conversation-ui'), 'response_detail', Permission.READ_MODEL, {}, lambda _: conversation.response_detail(response_id))
    return jsonify(result.model_dump(mode='json')), 200 if result.success else 404


@agent_api.route('/history', methods=['GET', 'PUT', 'DELETE'])
def conversation_history():
    if request.content_length and request.content_length > 5_000_000:
        return jsonify({'error':'Der Verlauf ist zu groß.'}), 413
    data = request.get_json(silent=True) or {}
    if request.method == 'PUT' and not isinstance(data.get('messages'), list):
        return jsonify({'error':'Nachrichtenliste fehlt.'}), 400
    result = execute(ToolAuthority(_project(), 'conversation-ui'), 'conversation_history', Permission.READ_MODEL, {},
        lambda _: conversation.history(data.get('messages') if request.method == 'PUT' else None, clear=request.method == 'DELETE'))
    return jsonify(result.data if result.success else result.model_dump(mode='json')), 200 if result.success else 400


@agent_api.post('/findings/<finding_id>/decision')
def finding_decision(finding_id):
    if not _human_intent():
        return jsonify({'error': 'Eine bewusste Entscheidung in der Oberfläche ist erforderlich.'}), 403
    data = request.get_json(silent=True) or {}
    result = execute(ToolAuthority(_project(), 'local-human'), 'finding_decision', Permission.READ_MODEL, {},
        lambda _: conversation.decide(finding_id, data.get('decision'), data.get('rationale', ''), data.get('review_on_change', True)))
    return jsonify(result.model_dump(mode='json')), 200 if result.success else 400
