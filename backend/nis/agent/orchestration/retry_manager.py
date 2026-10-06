from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RetryState:
    max_attempts: int
    attempt_count: int = 0
    last_error: str | None = None
    retry_reason: str | None = None

    @property
    def exhausted(self) -> bool:
        return self.attempt_count >= self.max_attempts


class RetryManager:
    def __init__(self, max_attempts: int = 3) -> None:
        self.default_max_attempts = max_attempts
        self._states: dict[str, RetryState] = {}

    def state(self, key: str, *, max_attempts: int | None = None) -> RetryState:
        return self._states.setdefault(key, RetryState(max_attempts or self.default_max_attempts))

    def record_attempt(
        self,
        key: str,
        *,
        reason: str,
        error: Exception | str | None = None,
        max_attempts: int | None = None,
    ) -> RetryState:
        state = self.state(key, max_attempts=max_attempts)
        state.attempt_count += 1
        state.retry_reason = reason
        state.last_error = str(error) if error is not None else None
        return state

    @staticmethod
    def can_retry(attempt_count: int, max_attempts: int) -> bool:
        return attempt_count < max_attempts

    @staticmethod
    def terminal_status(*, blocked: bool) -> str:
        return "BLOCKED" if blocked else "INCOMPLETE"
