"""Durable audit for tools and the proposal approval boundary."""
from __future__ import annotations
from psycopg.types.json import Jsonb
from ..db import get_connection
from ..project_context import current_project_id
from .model import json_safe


def record(trace_id: str, actor: str, event_type: str, tool_name: str, status: str, details: dict) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO engineering_agent_audit (project_id, trace_id, actor, event_type, tool_name, status, details) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (current_project_id(), trace_id, actor, event_type, tool_name, status, Jsonb(json_safe(details))),
        )


def events(limit: int = 100) -> list[dict]:
    with get_connection() as connection:
        return json_safe(connection.execute(
            "SELECT * FROM engineering_agent_audit WHERE project_id=%s ORDER BY event_id DESC LIMIT %s",
            (current_project_id(), min(max(limit, 1), 500)),
        ).fetchall())
