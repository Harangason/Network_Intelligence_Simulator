"""Technology-neutral schedule constraints and numeric normalization."""
from math import isfinite

def number(value, default=0.0):
    try:
        result = float(value)
        return result if isfinite(result) else default
    except (TypeError, ValueError):
        return default

def _constraints(row, period, response, jitter_bound=None):
    reasons = []
    for field in ("max_latency_ms", "timeout_ms"):
        if number(row.get(field)) > 0 and response > number(row[field]) + 1e-7:
            reasons.append(f"{field}: {response:.3f} > {row[field]} ms")
    if number(row.get("freshness_ms")) > 0 and period + response > number(row["freshness_ms"]) + 1e-7:
        reasons.append(f"Datenalter {period + response:.3f} > {row['freshness_ms']} ms")
    if jitter_bound is not None and number(row.get("jitter_budget_ms")) > 0 and jitter_bound > number(row["jitter_budget_ms"]) + 1e-7:
        reasons.append(f"Jittergrenze {jitter_bound:.3f} > {row['jitter_budget_ms']} ms")
    return reasons

