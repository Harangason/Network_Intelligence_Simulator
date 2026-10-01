from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .retry_manager import RetryManager


class WorkloadExecutionLoop:
    """Bounded execution loop driven by persisted state callbacks."""

    STOP_STATUSES = frozenset({"READY_FOR_REVIEW", "COMPLETED", "BLOCKED", "PAUSED", "CANCELED", "FAILED", "INCOMPLETE"})

    def __init__(self, retry_manager: RetryManager | None = None) -> None:
        self.retry_manager = retry_manager or RetryManager()

    def run(
        self,
        *,
        inspect: Callable[[], dict[str, Any]],
        execute_cycle: Callable[[dict[str, Any]], None],
        evaluate: Callable[[], dict[str, Any]],
        progress_token: Callable[[dict[str, Any]], Any],
    ) -> dict[str, Any]:
        while True:
            state = inspect()
            status = str(state.get("status") or "RECEIVED").upper()
            if status in self.STOP_STATUSES:
                return evaluate()
            if any(not item.get("satisfied") for item in state.get("dependencies_resolved") or []):
                return evaluate()
            attempts = int(state.get("attempts") or 0)
            max_attempts = int(state.get("max_generation_attempts") or 3)
            if not self.retry_manager.can_retry(attempts, max_attempts):
                return evaluate()
            before = progress_token(state)
            execute_cycle(state)
            decision = evaluate()
            decision_status = str(decision.get("status") or decision.get("completion", {}).get("status") or "")
            if decision_status in self.STOP_STATUSES:
                return decision
            after_state = inspect()
            after = progress_token(after_state)
            if before == after and not self.retry_manager.can_retry(
                int(after_state.get("attempts") or 0), int(after_state.get("max_generation_attempts") or 3)
            ):
                return evaluate()
