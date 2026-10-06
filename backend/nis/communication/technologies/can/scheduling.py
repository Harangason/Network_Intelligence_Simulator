"""Preserved technology-specific scheduling bound; functional acceptance remains separate."""
from math import ceil, floor, lcm
from backend.nis.communication.core.scheduling import number, _constraints

def schedule(rows, policy, periods, result):
    if any(row.get("arbitration_id") is None for row in rows):
        return {**result, "status": "PROFILE_INCOMPLETE", "reasons": ["CAN-Identifier fehlt; Priorität ist nicht aus Namen ableitbar."]}
    # Standard frames only for this sufficient bound; mixed extended/standard
    # arbitration must not be approximated by sorting integer IDs.
    if any(number(row["arbitration_id"]) > 0x7ff for row in rows):
        return {**result, "status": "UNVERIFIED", "reasons": ["Erweiterte CAN-Identifier benötigen eine gesonderte Arbitrierungsanalyse."]}
    ordered = sorted(rows, key=lambda r: (r["arbitration_id"], r["stream_id"]))
    if len({row["arbitration_id"] for row in ordered}) != len(ordered):
        return {**result, "status": "MODEL_INCONSISTENT", "reasons": ["Mehrere physische Sender verwenden denselben CAN-Identifier."]}
    result["model"] = "CAN_SUFFICIENT_COMPLETION_BOUND_V1"
    result["assumptions"].append("Standard-Identifier; streng nach CAN-ID priorisierte Senderqueues; konservative Rahmendauer inklusive Stuffing und Intermission")
    for index, row in enumerate(ordered):
        def cost(item):
            return number(item.get("frame_time_bound_ms")) or number(item.get("segment_transmission_latency_ms"))
        own = cost(row)
        blocking = max((cost(r) for r in ordered[index + 1:]), default=0)
        bound = own + blocking
        period = periods[row["stream_id"]]
        for _ in range(1000):
            updated = own + blocking + sum(ceil((bound + number(r.get("release_jitter_ms")) + 1e-9) / periods[r["stream_id"]])
                                           * cost(r) for r in ordered[:index])
            if updated > period + 1e-7:
                bound = updated
                result["reasons"].append(f"{row.get('name')}: Antwortgrenze überschreitet den Sendeabstand.")
                break
            if abs(updated - bound) < 1e-8:
                bound = updated
                break
            bound = updated
        else:
            result["reasons"].append("Antwortzeitanalyse hat die Iterationsgrenze erreicht.")
        response = bound + number(row.get("release_jitter_ms"))
        result["responses"][row["stream_id"]] = response
        result["reasons"].extend(_constraints(row, period, response + number(row.get("fixed_path_delay_ms")),
                                              response - number(row.get("segment_transmission_latency_ms"))))
    return result
