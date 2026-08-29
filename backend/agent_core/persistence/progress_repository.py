from __future__ import annotations

from typing import Any, Protocol


class ProgressRepository(Protocol):
    def save_progress(self, workload_id: str, progress: dict[str, Any]) -> None: ...

    def get_progress(self, workload_id: str) -> dict[str, Any]: ...
