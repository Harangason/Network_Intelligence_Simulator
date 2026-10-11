"""Recoverable bounded continuation of explicitly authorized simulation goals.

The project transaction serializes claims across processes. External job I/O
continues to use the normal post-commit boundary and existing snapshot claim.
"""
from datetime import datetime, timedelta, timezone
import logging
import threading
from .store import get_goal, save_goal

PENDING = {'FOLLOWUP_PENDING', 'SIMULATION_RUNNING'}
TERMINAL = {'COMPLETE', 'INCOMPLETE', 'FAILED', 'PLAN_STALE', 'BACKGROUND_PAUSED'}
_thread = None
_start_lock = threading.Lock()
_stop = threading.Event()
logger = logging.getLogger(__name__)


def claim(workload_id, now=None):
    goal = get_goal(workload_id)
    if goal['status'] in TERMINAL and goal.get('background') and goal['background'].get('published_status') != goal['status']:
        return {'claimed': False, 'publish': True}
    if goal['status'] not in PENDING or not goal.get('followup_authorization'):
        return {'claimed': False}
    now = now or datetime.now(timezone.utc)
    state = goal.setdefault('background', {})
    if state.get('next_check_at', '') > now.isoformat():
        return {'claimed': False}
    if state.get('checks', 0) >= 720:
        goal['status'] = 'BACKGROUND_PAUSED'
        goal['findings'] = [{'code': 'FOLLOWUP_RETRY_LIMIT', 'severity': 'OPEN',
            'message': 'Der Lauf ist nach 720 Hintergrundprüfungen noch offen. Derselbe Auftrag kann gezielt fortgesetzt werden; es wurde kein weiterer Simulationsjob angelegt.'}]
        save_goal(goal)
        return {'claimed': False, 'publish': True}
    state.update(checks=state.get('checks', 0) + 1, last_check_at=now.isoformat(),
        next_check_at=(now + timedelta(seconds=10)).isoformat())
    save_goal(goal)
    return {'claimed': True}


def publish(workload_id):
    from ..agent_tools import conversation
    from .service import presentation
    from ..db import get_connection
    from ..project_context import current_project_id
    from psycopg.types.json import Jsonb
    goal = get_goal(workload_id)
    if goal['status'] not in TERMINAL or goal.get('background', {}).get('published_status') == goal['status']:
        return {'published': False}
    response = presentation(goal)
    response['id'] = f'{workload_id}-{goal["status"].lower()}'
    with get_connection() as connection:
        connection.execute('INSERT INTO engineering_agent_responses(project_id,response_id,body) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',
            (current_project_id(), response['id'], Jsonb(response)))
    # Preserve the current conversation/requirement, even when the user has
    # started another task. The completed workload remains addressable.
    conversation.history([{'id': response['id'], 'role': 'assistant', 'parts': [{'type': 'data-engineering', 'data': response}]}])
    goal.setdefault('background', {})['published_status'] = goal['status']
    save_goal(goal)
    return {'published': True, 'status': goal['status']}


def tick(project_id, workload_id, *, now=None):
    from ..agent_tools.runtime import ToolAuthority, execute
    from ..agent_tools.services import TOOLS
    from backend.agent_core.api.tool_contract import Permission
    authority = ToolAuthority(project_id, 'authorized-goal-continuation')
    claimed = execute(authority, 'claim_goal_followup', Permission.READ_MODEL, {}, lambda _: claim(workload_id, now))
    if not claimed.success: return claimed
    if not claimed.data.get('claimed'):
        if claimed.data.get('publish'):
            execute(authority, 'publish_goal_followup', Permission.READ_MODEL, {}, lambda _: publish(workload_id))
        return claimed
    definition = TOOLS['continue_engineering_goal']
    result = execute(authority, definition.name, definition.permission, {'workload_id': workload_id}, definition.handler)
    if result.success and result.data.get('status') in TERMINAL:
        execute(authority, 'publish_goal_followup', Permission.READ_MODEL, {}, lambda _: publish(workload_id))
    return result


def pending():
    from ..db import get_connection
    with get_connection() as connection:
        rows = connection.execute("SELECT project_id, workload_id FROM engineering_execution_goals "
            "WHERE (body->>'status' IN ('FOLLOWUP_PENDING','SIMULATION_RUNNING') "
            "AND jsonb_typeof(body->'followup_authorization')='object' "
            "AND COALESCE(body->'background'->>'next_check_at','') <= %s) OR "
            "(body->>'status' IN ('COMPLETE','INCOMPLETE','FAILED','PLAN_STALE','BACKGROUND_PAUSED') "
            "AND body->'background'->>'checks' IS NOT NULL "
            "AND COALESCE(body->'background'->>'published_status','') <> body->>'status') ORDER BY modified_at LIMIT 8",
            (datetime.now(timezone.utc).isoformat(),)).fetchall()
    return rows


def _run():
    failed = False
    while not _stop.wait(5 if not failed else 30):
        try:
            for row in pending():
                if _stop.is_set(): return
                result = tick(row['project_id'], row['workload_id'])
                if not result.success:
                    logger.warning('Goal follow-up remains retryable: %s / %s', row['workload_id'], result.status)
            failed = False
        except Exception:
            if not failed: logger.exception('Goal follow-up recovery is temporarily unavailable')
            failed = True


def start():
    global _thread
    with _start_lock:
        if _thread is None or not _thread.is_alive():
            _stop.clear()
            _thread = threading.Thread(target=_run, name='engineering-goal-followup', daemon=True)
            _thread.start()


def stop():
    _stop.set()
