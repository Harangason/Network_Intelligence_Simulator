"""Deterministic communication sizing. History proposes; current constraints decide.

All time values are milliseconds. LIN slots reserve 1.4 times nominal frame
duration plus master jitter. CAN uses a sufficient non-preemptive completion
bound, including interference until completion (deliberately conservative).
Neither model certifies a vehicle function; results state their assumptions.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
from math import ceil, floor, isfinite, lcm

from .transmission import profile

VERSION = "communication-sizing-v2"
DEFAULT_POLICY = {
    "enabled": True, "minimum_interval_ms": 20.0,
    "maximum_generated_period_ms": 50.0,
    "candidate_periods_ms": [20, 25, 40, 50, 100, 200, 500, 1000],
    "target_load_percent": 60.0, "maximum_slot_load_percent": 90.0,
    "lin_timebase_ms": 5.0, "lin_master_jitter_ms": 0.0,
    "source": "automotive-development-profile",
}


def number(value, default=0.0):
    try:
        result = float(value)
        return result if isfinite(result) else default
    except (TypeError, ValueError):
        return default


def policy_for(parameters):
    explicit = parameters.get("communication_sizing") or {}
    automotive = str(parameters.get("industry") or "").lower() == "automotive"
    policy = {**DEFAULT_POLICY, "enabled": automotive, **explicit}
    for key in ("minimum_interval_ms", "maximum_generated_period_ms", "lin_timebase_ms"):
        if number(policy.get(key)) <= 0:
            raise ValueError(f"communication_sizing.{key} muss positiv sein.")
    if policy["maximum_generated_period_ms"] < policy["minimum_interval_ms"]:
        raise ValueError("Maximaler Zyklus liegt unter dem Mindest-Sendeabstand.")
    for key in ("target_load_percent", "maximum_slot_load_percent"):
        if not 0 < number(policy.get(key)) <= 100:
            raise ValueError(f"communication_sizing.{key} muss zwischen 0 und 100 liegen.")
    if number(policy.get("lin_master_jitter_ms"), -1) < 0:
        raise ValueError("LIN Master-Jitter darf nicht negativ sein.")
    candidates = sorted({number(v) for v in policy.get("candidate_periods_ms", [])})
    if not candidates or candidates[0] <= 0 or candidates[-1] > 60000:
        raise ValueError("Kandidatenzyklen müssen zwischen 0 und 60000 ms liegen.")
    policy["candidate_periods_ms"] = candidates
    return policy


def transmission_contract(message):
    return ((message.get("configuration") or {}).get("communication_contract") or {}).get("transmission") or {}


def effective_period(message, legacy_period):
    contract = transmission_contract(message)
    return profile(contract, legacy_period)["period_ms"] or number(legacy_period)


def stream_key(row):
    source = row.get("physical_source") or {}
    # Logical interface aliases must not cause extra physical broadcasts.
    port = source.get("hardware_interface_id") or source.get("physical_port_ref") or source.get("port_id") or source.get("interface_id")
    key = [str(row.get("network_id")), str(source.get("node_id") or row.get("producer")), str(port or ""),
           str(row.get("message_id") or row.get("route_id"))]
    if row.get("load_basis") == "BUSIEST_FULL_DUPLEX_PORT":
        target = row.get("physical_target") or {}
        key.extend([str(target.get("node_id")), str(target.get("port_id") or target.get("interface_id"))])
    return tuple(key)


def unique_streams(rows):
    unique = {}
    for row in rows:
        key = stream_key(row)
        route_ids = sorted(set(row.get("route_ids") or []) | {row["route_id"]})
        if key not in unique:
            unique[key] = {**deepcopy(row), "route_ids": route_ids}
            unique[key]["stream_id"] = sha256(json.dumps(key).encode()).hexdigest()[:20]
        else:
            entry = unique[key]
            entry["route_ids"] = sorted(set(entry["route_ids"] + route_ids))
            entry["consumers"] = sorted(set(entry.get("consumers", []) + row.get("consumers", [])))
            if any(entry.get(field) != row.get(field) for field in ("cycle_ms", "payload_bytes", "protocol", "bitrate")):
                entry["model_conflict"] = "Eine physische Nachricht hat widersprüchliche Übertragungsparameter."
            for field in ("max_latency_ms", "freshness_ms", "timeout_ms", "jitter_budget_ms"):
                values = [number(value) for value in (entry.get(field), row.get(field)) if number(value) > 0]
                entry[field] = min(values) if values else None
    return list(unique.values())


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


def bus_schedule(rows, policy):
    """Create a repeatable LIN poll table or sufficient CAN completion bounds."""
    if not rows:
        return {"status": "EMPTY", "slots": [], "responses": {}, "reasons": []}
    protocols = {str(row.get("protocol", "")).upper() for row in rows}
    if len(protocols) != 1 or any(row.get("model_conflict") or row.get("physical_path_resolved") is False for row in rows):
        return {"status": "MODEL_INCONSISTENT", "reasons": ["Physische Sendungen sind widersprüchlich."], "responses": {}}
    protocol = next(iter(protocols))
    limit = 8 if protocol in {"LIN", "CAN", "CAN_CLASSIC"} else 64 if protocol in {"CAN_FD", "CANFD"} else None
    if len({number(row.get("bitrate")) for row in rows}) > 1 or (limit and any(number(row.get("payload_bytes")) > limit for row in rows)):
        return {"status": "MODEL_INCONSISTENT", "responses": {}, "reasons": ["Bitrate oder Nutzlast passt nicht zum physischen Bus."]}
    periods = {row["stream_id"]: number(row.get("cycle_ms")) for row in rows}
    if min(periods.values()) <= 0:
        return {"status": "PROFILE_INCOMPLETE", "responses": {}, "reasons": ["Positiver Sendeabstand fehlt."]}
    if any(row.get("traffic_profile_incomplete") for row in rows):
        return {"status": "PROFILE_INCOMPLETE", "responses": {}, "reasons": ["Ereignis-/Anfrageprofil ist nicht vollständig begrenzt."]}
    nominal = sum(number(row.get("segment_transmission_latency_ms")) / periods[row["stream_id"]] * 100 for row in rows)
    result = {"status": "UNVERIFIED", "nominal_load_percent": round(nominal, 6), "responses": {}, "slots": [], "reasons": [],
              "assumptions": ["Vollständiger modellierter Verkehr", "Keine zusätzlichen Busfehler oder Retransmissions-Bursts", "Serialisierte Übertragungen"]}
    if nominal >= 100:
        return {**result, "status": "OVERLOAD", "reasons": ["Nominaler Bedarf erreicht oder überschreitet 100 %."]}
    if protocol == "LIN":
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
    elif protocol in {"CAN", "CAN_CLASSIC", "CAN_FD", "CANFD"}:
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
    else:
        evidence_gaps = {
            "PWM": (
                "PWM ist eine direkte Signalleitung und kein paketbasierter Bus. "
                "PWM-Frequenz sowie Aktualisierungs- und Erfassungsgrenzen fehlen für den Reaktionszeitnachweis."
            ),
            "GPIO": (
                "GPIO ist eine direkte Signalleitung und kein paketbasierter Bus. "
                "Abtast-, Entprell- und Flankenerkennungszeiten fehlen für den Reaktionszeitnachweis."
            ),
            "I2C": (
                "Für den I2C-Zeitnachweis fehlen Master-Zuordnung, Slave-Adresse und eine Grenze für Clock Stretching."
            ),
            "SPI": (
                "Für den SPI-Zeitnachweis fehlen Master-Zuordnung, Chip-Select-Zuordnung und eine bestätigte Takt-/Transfergrenze."
            ),
        }
        reason = evidence_gaps.get(
            protocol,
            f"Für {protocol or 'dieses Protokoll'} ist noch kein deterministisches Scheduling-Modell hinterlegt.",
        )
        return {**result, "status": "UNVERIFIED", "reasons": [reason]}
    result["status"] = "CONSTRAINT_VIOLATION" if result["reasons"] else "FEASIBLE_UNDER_ASSUMPTIONS"
    return result


def dimension_communications(rows, parameters, history=None):
    policy = policy_for(parameters)
    streams = unique_streams(rows)
    groups = defaultdict(list)
    for row in streams:
        groups[row["network_id"]].append(row)
    result = {"version": VERSION, "policy": policy, "networks": [], "changes": [], "history_matches": [],
              "status": "DISABLED" if not policy["enabled"] else "NO_CHANGES", "requires_functional_review": True}
    if not policy["enabled"]:
        return result
    proposals = {}
    for network_id, current in sorted(groups.items()):
        signature = [(r.get("message_name") or r.get("name") or "", r.get("payload_bytes"), r.get("protocol"), r.get("bitrate"),
                      r.get("max_latency_ms"), r.get("freshness_ms")) for r in current]
        fingerprint = sha256(json.dumps(sorted(signature, key=lambda item: json.dumps(item)), sort_keys=True).encode()).hexdigest()
        matches = [item for item in history or [] if item.get("fingerprint") == fingerprint and item.get("status") == "FEASIBLE_UNDER_ASSUMPTIONS"]
        attempts = []
        chosen = None
        floors = sorted(set([policy["minimum_interval_ms"], *policy["candidate_periods_ms"],
                             *[number(item.get("selected_floor_ms")) for item in matches]]))
        for period_floor in floors:
            if not policy["minimum_interval_ms"] <= period_floor <= policy["maximum_generated_period_ms"]:
                continue
            candidate = deepcopy(current)
            rejected = []
            for row in candidate:
                original = number(row["cycle_ms"])
                contract = row.get("transmission_contract") or {}
                locked = (str(contract.get("mode") or "CYCLIC").upper() != "CYCLIC"
                          or contract.get("period_locked") is True or row.get("period_origin") in {"user", "imported"})
                maximum = number(contract.get("maximum_period_ms")) or max(original, policy["maximum_generated_period_ms"])
                proposed = original if locked else max(original, period_floor)
                if proposed < policy["minimum_interval_ms"] or proposed > maximum:
                    rejected.append(f"{row.get('name')}: bestätigte Zyklusgrenze verhindert {proposed:g} ms.")
                row["cycle_ms"] = proposed
            check = bus_schedule(candidate, policy) if not rejected else {"status": "CONSTRAINT_VIOLATION", "reasons": rejected}
            fits = (check["status"] == "FEASIBLE_UNDER_ASSUMPTIONS"
                    and check["nominal_load_percent"] <= policy["target_load_percent"] + 1e-7
                    and check.get("slot_load_percent", 0) <= policy["maximum_slot_load_percent"] + 1e-7)
            reasons = list(check.get("reasons", []))
            if check.get("nominal_load_percent", 0) > policy["target_load_percent"]:
                reasons.append("Ziel-Buslast überschritten.")
            if check.get("slot_load_percent", 0) > policy["maximum_slot_load_percent"]:
                reasons.append("Reservierte LIN-Slots lassen zu wenig Reserve.")
            attempts.append({"floor_ms": period_floor, "status": check["status"], "fits": fits,
                             "load_percent": check.get("nominal_load_percent"), "slot_load_percent": check.get("slot_load_percent"), "reasons": reasons})
            if fits:
                chosen = (candidate, check, period_floor)
                break
        entry = {"network_id": network_id, "network_name": current[0].get("network_name") or network_id,
                 "protocol": current[0].get("protocol"), "fingerprint": fingerprint, "attempts": attempts,
                 "status": "UNRESOLVED", "explanation": "Kein zulässiger Zyklus gefunden; Packing, Bitrate, Busaufteilung oder Anforderungen prüfen."}
        if chosen:
            candidate, check, selected_floor = chosen
            entry.update(status=check["status"], schedule=check, selected_floor_ms=selected_floor,
                         explanation=f"Kleinster geprüfter Zyklus-Floor {selected_floor:g} ms: {check['nominal_load_percent']:.2f} % nominale Buslast; Fristen und Planungsreserve eingehalten.")
            for row in candidate:
                if row.get("message_id"):
                    proposals[row["message_id"]] = max(proposals.get(row["message_id"], 0), row["cycle_ms"])
        if matches:
            entry["history_evidence"] = [{"snapshot_id": item.get("snapshot_id"), "selected_floor_ms": item.get("selected_floor_ms")} for item in matches[:5]]
            result["history_matches"].append(network_id)
        result["networks"].append(entry)
    # The user's minimum interval is a model requirement, independent of a
    # transport timing proof. Migrate generated cyclic Ethernet traffic only
    # when its current traffic data are consistent; do not certify its timing.
    # A shared CAN/Ethernet message must retain one canonical period.
    for entry in result["networks"]:
        current = groups[entry["network_id"]]
        check = bus_schedule(current, policy)
        if entry["protocol"] != "ETHERNET" or check["status"] != "UNVERIFIED":
            continue
        entry["policy_only"] = True
        entry["schedule"] = check
        entry["explanation"] = "Mindestabstand für generierte zyklische Nachrichten übernehmen; Ethernet-Antwortzeiten sind damit nicht nachgewiesen."
        for row in current:
            contract = row.get("transmission_contract") or {}
            original = number(row["cycle_ms"])
            proposed = max(original, policy["minimum_interval_ms"], proposals.get(row.get("message_id"), 0))
            maximum = number(contract.get("maximum_period_ms")) or max(original, policy["maximum_generated_period_ms"])
            locked = str(contract.get("mode") or "CYCLIC").upper() != "CYCLIC" or contract.get("period_locked") or row.get("period_origin") in {"user", "imported"}
            if row.get("message_id") and not locked and proposed <= maximum and proposed > original:
                proposals[row["message_id"]] = proposed
    # A forwarded message has one application period. Recheck every affected
    # segment together, so a slower downstream choice cannot violate upstream freshness.
    for entry in result["networks"]:
        current = groups[entry["network_id"]]
        updated = [{**row, "cycle_ms": proposals.get(row.get("message_id"), row["cycle_ms"])} for row in current]
        check = bus_schedule(updated, policy)
        if entry["status"] == "FEASIBLE_UNDER_ASSUMPTIONS":
            entry["schedule"] = check
            if check["status"] != "FEASIBLE_UNDER_ASSUMPTIONS":
                entry.update(status="UNRESOLVED", explanation="Gemeinsame Nachrichtenperiode verletzt einen anderen physischen Pfad.")
    # Check full paths as well as individual buses. A LIN gateway may have to
    # wait until the next reserved downstream slot after its input arrives.
    paths = defaultdict(list)
    entries = {entry["network_id"]: entry for entry in result["networks"]}
    for row in streams:
        for route_id in row["route_ids"]:
            paths[(route_id, row.get("message_id"))].append(row)
    for related in paths.values():
        if not all(entries[row["network_id"]]["status"] == "FEASIBLE_UNDER_ASSUMPTIONS" for row in related):
            continue
        response = sum(entries[row["network_id"]]["schedule"]["responses"][row["stream_id"]]
                       + (proposals.get(row.get("message_id"), row["cycle_ms"]) if row.get("protocol") == "LIN" and row.get("route_segment_index", 1) > 1 else 0)
                       for row in related)
        response += max((number(row.get("fixed_path_delay_ms")) for row in related), default=0)
        jitter_bound = max(0, response - sum(number(row.get("segment_transmission_latency_ms")) for row in related))
        if any(_constraints(row, proposals.get(row.get("message_id"), row["cycle_ms"]), response, jitter_bound) for row in related):
            for row in related:
                entries[row["network_id"]].update(status="UNRESOLVED", explanation="Ende-zu-Ende-Frist über mehrere physische Busse nicht eingehalten.")
    # If one bus is unresolved, do not apply half a connected message change.
    # Propagate until every persisted schedule uses exactly the final periods.
    for _ in range(len(entries) + 1):
        blocked_messages = {row.get("message_id") for entry in result["networks"] if entry["status"] == "UNRESOLVED" and not entry.get("policy_only") for row in groups[entry["network_id"]]}
        changed = False
        for entry in result["networks"]:
            if entry["status"] == "UNRESOLVED":
                continue
            updated = [{**row, "cycle_ms": row["cycle_ms"] if row.get("message_id") in blocked_messages else proposals.get(row.get("message_id"), row["cycle_ms"])} for row in groups[entry["network_id"]]]
            check = bus_schedule(updated, policy)
            entry["schedule"] = check
            if check["status"] != "FEASIBLE_UNDER_ASSUMPTIONS" or check.get("nominal_load_percent", 0) > policy["target_load_percent"] or check.get("slot_load_percent", 0) > policy["maximum_slot_load_percent"]:
                entry.update(status="UNRESOLVED", explanation="Zugehörige Nachricht auf einem anderen Bus noch ungeklärt.")
                changed = True
        if not changed:
            break
    for message_id, period in sorted(proposals.items()):
        related = [row for row in streams if row.get("message_id") == message_id]
        if message_id in blocked_messages:
            continue
        old = min(number(row["cycle_ms"]) for row in related)
        if abs(old - period) > 1e-7 or any(not row.get("transmission_contract") for row in related):
            result["changes"].append({"message_id": message_id, "name": related[0].get("message_name") or related[0].get("name"),
                                      "evaluation": "POLICY_ONLY_UNVERIFIED" if any(entries[row["network_id"]].get("policy_only") for row in related) else "FEASIBLE_UNDER_ASSUMPTIONS",
                                      "before_ms": old, "after_ms": period, "route_ids": sorted({r for row in related for r in row["route_ids"]}),
                                      "network_ids": sorted({row["network_id"] for row in related})})
    final_periods = {change["message_id"]: change["after_ms"] for change in result["changes"]}
    for entry in result["networks"]:
        entry["effective_periods_ms"] = sorted({final_periods.get(row.get("message_id"), row["cycle_ms"]) for row in groups[entry["network_id"]]})
    result["status"] = "PARTIAL" if any(entry["status"] == "UNRESOLVED" for entry in result["networks"]) else "READY" if result["changes"] else "NO_CHANGES"
    return result
