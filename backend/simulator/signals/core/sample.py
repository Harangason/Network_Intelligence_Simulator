from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SignalSample:
    signal_ref: str
    timestamp: float
    semantic_type: str
    physical_value: float | None
    display_value: float | str | bool | None
    quantized_value: float | None
    raw_value: int | None
    unit: str
    quality: str
    model_type: str
    behavior_model: str
    state: str | None = None
    source: str = "simulation"
    fault_state: list[str] = field(default_factory=list)
    golden_value: float | None = None
    source_dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
