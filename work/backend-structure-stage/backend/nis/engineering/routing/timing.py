"""Reviewable initial timing budgets; existing route requirements are never changed."""


def generated_timing(cycle_ms, message=None, explicit=None):
    requirements = (message or {}).get("configuration") or {}
    explicit = explicit or {}
    cycle = float(explicit.get("cycle_time_ms") or cycle_ms or 100)
    defaults = {"cycle_time_ms": cycle, "timeout_ms": max(500, 3 * cycle),
        "freshness_ms": max(500, 3 * cycle), "max_latency_ms": 20, "jitter_limit_ms": 5}
    aliases = {"timeout_ms": ("timeout_ms", "timeout"), "freshness_ms": ("freshness_ms", "data_freshness_limit"),
        "max_latency_ms": ("max_latency_ms", "maximum_latency_ms", "deadline_ms"),
        "jitter_limit_ms": ("jitter_limit_ms", "maximum_jitter_ms"), "cycle_time_ms": ("cycle_time_ms",)}
    timing, provenance = {}, {}
    for field, fallback in defaults.items():
        candidates = [(float(source[key]), origin, key) for origin, source in (("message.configuration", requirements), ("explicit", explicit))
            for key in aliases[field] if source.get(key) is not None and float(source[key]) > 0]
        if candidates:
            value, origin, key = min(candidates)
            timing[field], provenance[field] = value, {"source": origin, "field": key, "unit": "ms"}
        else:
            timing[field] = fallback
            provenance[field] = {"source": "generated-default", "unit": "ms",
                "assumption": "max(500 ms, 3 × message cycle)" if field in {"timeout_ms", "freshness_ms"} else "Initial reviewable timing budget"}
    timing["provenance"] = provenance
    return timing
