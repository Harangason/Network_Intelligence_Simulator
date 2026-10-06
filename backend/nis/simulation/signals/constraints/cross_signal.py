from __future__ import annotations

from typing import Any


def dependency_values(dependencies: list[str], values: dict[str, Any]) -> dict[str, float]:
    resolved: dict[str, float] = {}
    for ref in dependencies:
        value = values.get(ref) or values.get(ref.replace("-", "_"))
        if isinstance(value, (int, float)):
            resolved[ref] = float(value)
    return resolved
