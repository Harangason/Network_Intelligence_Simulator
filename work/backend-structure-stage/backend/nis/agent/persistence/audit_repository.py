from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AuditEvent:
    workload_id: str
    event_type: str
    actor: str | None = None
    agent: str | None = None
    model: str | None = None
    generator: str | None = None
    validator: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> None: ...

    def list(self, workload_id: str) -> list[AuditEvent]: ...


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    def list(self, workload_id: str) -> list[AuditEvent]:
        return [event for event in self.events if event.workload_id == workload_id]
