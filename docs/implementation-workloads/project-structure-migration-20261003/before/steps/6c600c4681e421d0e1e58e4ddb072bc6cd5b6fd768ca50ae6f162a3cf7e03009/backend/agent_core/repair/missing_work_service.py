from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class MissingWork:
    package_code: str
    category: str
    count: int


class MissingWorkService:
    def detect(self, packages: Sequence[Mapping[str, Any]]) -> list[MissingWork]:
        missing: list[MissingWork] = []
        for item in packages:
            count = max(0, int(item.get("requested_count") or 0) - int(item.get("valid_count") or 0))
            if count:
                missing.append(
                    MissingWork(
                        package_code=str(item.get("package_code") or item.get("work_package_id") or "WP"),
                        category=str(item.get("category") or "general"),
                        count=count,
                    )
                )
        return missing
