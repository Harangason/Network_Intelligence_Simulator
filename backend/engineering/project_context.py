"""Request-local project scope for canonical engineering data."""

from __future__ import annotations

from contextvars import ContextVar, Token


DEFAULT_PROJECT_ID = "default"
_ACTIVE_PROJECT_ID: ContextVar[str] = ContextVar(
    "engineering_active_project_id",
    default=DEFAULT_PROJECT_ID,
)


def normalize_context_project_id(value: object) -> str:
    project_id = str(value or DEFAULT_PROJECT_ID).strip()
    return project_id or DEFAULT_PROJECT_ID


def current_project_id() -> str:
    return _ACTIVE_PROJECT_ID.get()


def activate_project(project_id: object) -> Token[str]:
    return _ACTIVE_PROJECT_ID.set(normalize_context_project_id(project_id))


def reset_project(token: Token[str]) -> None:
    _ACTIVE_PROJECT_ID.reset(token)
