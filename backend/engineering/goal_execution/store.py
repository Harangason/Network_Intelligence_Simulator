"""Project-bound durable plans, authorization envelopes and canonical resources."""
from psycopg.types.json import Jsonb
from ..db import get_connection, mark_model_changed
from ..project_context import current_project_id
from ..agent_tools.model import json_safe
from .models import CommunicationCapability, CommunicationController, PhysicalPort, NetworkConnection

RESOURCE_MODELS = {model.__name__: model for model in (CommunicationCapability, CommunicationController, PhysicalPort, NetworkConnection)}


def resources():
    with get_connection() as conn:
        rows = conn.execute('SELECT kind, body FROM engineering_communication_resources WHERE project_id=%s ORDER BY kind, resource_id',
                            (current_project_id(),)).fetchall()
    result = {kind: [] for kind in RESOURCE_MODELS}
    for row in rows:
        result[row['kind']].append(row['body'])
    return result


def save_resource(kind, body):
    value = RESOURCE_MODELS[kind].model_validate(body).model_dump(mode='json')
    identifier = value.get('id') or value['connection_id']
    with get_connection() as conn:
        conn.execute('INSERT INTO engineering_communication_resources(project_id,kind,resource_id,body) VALUES (%s,%s,%s,%s) '
                     'ON CONFLICT(project_id,kind,resource_id) DO UPDATE SET body=EXCLUDED.body, version=engineering_communication_resources.version+1, modified_at=now()',
                     (current_project_id(), kind, identifier, Jsonb(value)))
    mark_model_changed()
    return value


def get_goal(workload_id):
    with get_connection() as conn:
        row = conn.execute('SELECT body FROM engineering_execution_goals WHERE project_id=%s AND workload_id=%s FOR UPDATE',
                           (current_project_id(), workload_id)).fetchone()
    if not row:
        raise LookupError('Ausführungsauftrag im aktiven Projekt nicht gefunden.')
    return row['body']


def save_goal(goal):
    body = json_safe(goal)
    with get_connection() as conn:
        conn.execute('INSERT INTO engineering_execution_goals(project_id,workload_id,body) VALUES (%s,%s,%s) '
                     'ON CONFLICT(project_id,workload_id) DO UPDATE SET body=EXCLUDED.body, modified_at=now()',
                     (current_project_id(), body['workload_id'], Jsonb(body)))
    return body
