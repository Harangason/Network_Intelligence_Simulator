"""Request-local project scope for canonical engineering data."""

from __future__ import annotations

from contextvars import ContextVar, Token
import re


DEFAULT_PROJECT_ID = "default"
NETWORK_PROJECT_PREFIX = "network-project-"
COMPACT_NETWORK_PROJECT_PATTERN = re.compile(r"^\d{14,17}-[A-Za-z0-9._-]+$")
_ACTIVE_PROJECT_ID: ContextVar[str] = ContextVar(
    "engineering_active_project_id",
    default=DEFAULT_PROJECT_ID,
)


def normalize_context_project_id(value: object) -> str:
    project_id = str(value or DEFAULT_PROJECT_ID).strip()
    if not project_id:
        return DEFAULT_PROJECT_ID
    if project_id == DEFAULT_PROJECT_ID or project_id.startswith(NETWORK_PROJECT_PREFIX):
        return project_id
    if COMPACT_NETWORK_PROJECT_PATTERN.fullmatch(project_id):
        return f"{NETWORK_PROJECT_PREFIX}{project_id}"
    return project_id


def current_project_id() -> str:
    return _ACTIVE_PROJECT_ID.get()


def compact_context_project_id(value: object) -> str:
    project_id = normalize_context_project_id(value)
    return (
        project_id[len(NETWORK_PROJECT_PREFIX):]
        if project_id.startswith(NETWORK_PROJECT_PREFIX)
        else project_id
    )


def activate_project(project_id: object) -> Token[str]:
    return _ACTIVE_PROJECT_ID.set(normalize_context_project_id(project_id))


def reset_project(token: Token[str]) -> None:
    _ACTIVE_PROJECT_ID.reset(token)
