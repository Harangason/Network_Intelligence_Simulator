"""Feature extraction for architecture quality classification."""

from __future__ import annotations

from typing import Any


def architecture_features(snapshot: dict[str, Any]) -> dict[str, Any]:
    counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), dict) else {}
    metrics = snapshot.get("metrics") if isinstance(snapshot.get("metrics"), dict) else {}
    return {
        "orphan_signals": _number(counts.get("orphan_signals") or snapshot.get("orphan_signals"), 0),
        "unmapped_functions": _number(counts.get("unmapped_functions") or snapshot.get("unmapped_functions"), 0),
        "routing_gaps": _number(counts.get("routing_gaps") or snapshot.get("routing_gaps"), 0),
        "timing_violations": _number(counts.get("timing_violations") or snapshot.get("timing_violations"), 0),
        "busload_margin": _number(metrics.get("busload_margin") or snapshot.get("busload_margin"), 100),
        "unknown_semantics": _number(counts.get("unknown_semantics") or snapshot.get("unknown_semantics"), 0),
        "spof_count": _number(counts.get("spof_count") or snapshot.get("spof_count"), 0),
        "traceability_gaps": _number(counts.get("traceability_gaps") or snapshot.get("traceability_gaps"), 0),
    }


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
