"""Preserved technology-specific scheduling bound; functional acceptance remains separate."""
from math import ceil, floor, lcm
from backend.nis.communication.core.scheduling import number, _constraints

def schedule(rows, policy, periods, result):
    base = number(policy["lin_timebase_ms"])
    jitter = number(policy["lin_master_jitter_ms"])
    ticks = {key: round(value / base) for key, value in periods.items()}
    if any(ticks[key] < 1 or abs(ticks[key] * base - value) > 1e-7 for key, value in periods.items()):
        return {**result, "status": "NO_SCHEDULE", "reasons": ["Zyklen müssen Vielfache der LIN-Zeitbasis sein."]}
    horizon = 1
    for value in ticks.values():
        horizon = lcm(horizon, value)
        if horizon > 20000:
            return {**result, "status": "SEARCH_LIMIT", "reasons": ["Hyperperiode überschreitet die Planungsgrenze."]}
    widths = {row["stream_id"]: floor((1.4 * number(row.get("segment_transmission_latency_ms")) + jitter) / base + 1e-9) + 1 for row in rows}
    reserved = sum(widths[key] / ticks[key] * 100 for key in ticks)
    result.update(model="LIN_PERIODIC_MASTER_TABLE_V1", hyperperiod_ms=horizon * base,
                  slot_load_percent=round(reserved, 6), timebase_ms=base, master_jitter_ms=jitter)
    occupied = [False] * horizon
    for row in sorted(rows, key=lambda r: (ticks[r["stream_id"]], -widths[r["stream_id"]], r["stream_id"])):
        key = row["stream_id"]
        period, width = ticks[key], widths[key]
        phase = next((offset for offset in range(max(0, period - width + 1))
                      if all(not occupied[index] for start in range(offset, horizon, period) for index in range(start, start + width))), None)
        if phase is None:
            return {**result, "status": "NO_SCHEDULE", "reasons": ["Kein kollisionsfreier periodischer LIN-Plan für diese Zyklen gefunden."]}
        for start in range(phase, horizon, period):
            for index in range(start, start + width):
                occupied[index] = True
        response = 1.4 * number(row.get("segment_transmission_latency_ms")) + jitter
        if str((row.get("transmission_contract") or {}).get("mode") or "CYCLIC").upper() != "CYCLIC":
            response += periods[key]  # An event/request may just miss its reserved poll slot.
        result["slots"].append({"stream_id": key, "message_id": row.get("message_id"), "route_ids": row.get("route_ids", []),
                                "period_ms": periods[key], "offset_ms": phase * base, "duration_ms": width * base})
        result["responses"][key] = response
        result["reasons"].extend(_constraints(row, periods[key], response + number(row.get("fixed_path_delay_ms")),
                                              response - number(row.get("segment_transmission_latency_ms"))))
    result["assumptions"].append("Messwert-/Release-Phase folgt dem Master-Pollplan; 1,4-fache nominale LIN-Rahmendauer reserviert")
    return result


def forwarded_release_wait(row, period):
    return period if row.get('protocol') == 'LIN' and row.get('route_segment_index', 1) > 1 else 0

def validate_policy(policy):
    if number(policy.get('lin_timebase_ms')) <= 0:
        raise ValueError('communication_sizing.lin_timebase_ms muss positiv sein.')
    if number(policy.get('lin_master_jitter_ms'), -1) < 0:
        raise ValueError('LIN Master-Jitter darf nicht negativ sein.')

def reserve_reason():
    return 'Reservierte LIN-Slots lassen zu wenig Reserve.'
