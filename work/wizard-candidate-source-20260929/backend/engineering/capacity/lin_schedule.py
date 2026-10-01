"""Conservative batch bound for the simulator's non-preemptive LIN polling.

Participant count and average utilization alone do not bound the delay of a
simultaneous release. This check reserves the full batch before the strictest
deadline or the next fast poll's jitter window. No user deadline is relaxed.
"""
from math import isfinite


def lin_schedule_check(rows: list[dict]) -> dict:
    def number(value):
        try:
            parsed = float(value or 0)
            return parsed if isfinite(parsed) and parsed > 0 else 0
        except (ValueError, TypeError):
            return 0
    lin = [row for row in rows if str(row.get('protocol') or '').upper() == 'LIN']
    if not lin:
        return {'status': 'NOT_APPLICABLE'}
    batch = sum(number(row.get('segment_transmission_latency_ms', row.get('transmission_latency_ms'))) for row in lin)
    budgets = []
    for row in lin:
        breakdown = row.get('breakdown') or {}
        overhead = sum(number(breakdown.get(key)) for key in ('source_processing_ms', 'target_processing_ms', 'gateway_processing_ms', 'propagation_ms'))
        for key in ('max_latency_ms', 'timeout_ms'):
            value = number(row.get(key))
            if value:
                budgets.append(max(0, value - overhead))
        period, jitter = number(row.get('cycle_ms')), number(row.get('jitter_budget_ms'))
        if period and jitter:
            budgets.append(period + jitter - overhead)
    budget = min(budgets) if budgets else None
    return {'status': 'FAIL' if budget is not None and batch > budget + .00001 else 'PASS',
            'synchronous_batch_ms': round(batch, 6), 'budget_ms': round(budget, 6) if budget is not None else None,
            'model': 'LIN_NON_PREEMPTIVE_BATCH_BOUND_V1'}
