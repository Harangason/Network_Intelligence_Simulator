"""Preserved technology-specific scheduling bound; functional acceptance remains separate."""
from math import ceil, floor, lcm
from backend.nis.communication.core.scheduling import number, _constraints

def schedule(rows, policy, periods, result):
    protocol = 'SPI'
    from .timing import confirmed_serial_evidence
    from backend.nis.engineering.capacity.dimensioning import local_evidence_proposal
    evidence = [confirmed_serial_evidence(protocol, {"local_timing_evidence": row.get("local_timing_evidence")},
                                          int(number(row.get("payload_bytes")))) for row in rows]
    masters = {str(item.get("master_node_id")) for item in evidence if item}
    if (any(item is None for item in evidence) or len(masters) != 1
            or any(number(row.get("segment_transmission_latency_ms")) <= 0 for row in rows)):
        reason = (
            "Für den I2C-Zeitnachweis fehlen oder widersprechen Master-Zuordnung, Slave-Adresse, "
            "Clock Stretching und bestätigte Transfer-/Taktgrenzen."
            if protocol == "I2C" else
            "Für den SPI-Zeitnachweis fehlen oder widersprechen Master-Zuordnung, "
            "Chip-Select-Zuordnung, Transfergrenze und bestätigter Takt."
        )
        return {**result, "status": "UNVERIFIED", "nominal_load_percent": None,
                "reasons": [reason],
                "hardware_review_proposal": local_evidence_proposal(protocol, rows)}
    durations = {row["stream_id"]: number(row["segment_transmission_latency_ms"]) for row in rows}
    for row in rows:
        identifier = row["stream_id"]
        blocking = max((duration for key, duration in durations.items() if key != identifier), default=0.0)
        response = blocking + durations[identifier]
        for _ in range(1000):
            updated = blocking + durations[identifier] + sum(
                ceil(response / periods[other["stream_id"]]) * durations[other["stream_id"]]
                for other in rows if other["stream_id"] != identifier)
            if abs(updated - response) < 1e-9:
                break
            if updated > 1_000_000:
                return {**result, "status": "UNVERIFIED", "responses": {},
                        "reasons": ["Serialisierter Master-Zeitplan konvergiert nicht innerhalb der Analysegrenze."]}
            response = updated
        else:
            return {**result, "status": "UNVERIFIED", "responses": {},
                    "reasons": ["Serialisierter Master-Zeitplan erreichte die Iterationsgrenze."]}
        result["responses"][identifier] = response
        if response > periods[identifier]:
            result["reasons"].append(f"{identifier}: Antwortgrenze {response:.3f} ms übersteigt den Zyklus {periods[identifier]:.3f} ms.")
        result["reasons"].extend(_constraints(row, periods[identifier],
                                              response + number(row.get("fixed_path_delay_ms"))))
    result["assumptions"].append("Ein bestätigter Master und nicht unterbrechbare Transaktionen")
    return result
