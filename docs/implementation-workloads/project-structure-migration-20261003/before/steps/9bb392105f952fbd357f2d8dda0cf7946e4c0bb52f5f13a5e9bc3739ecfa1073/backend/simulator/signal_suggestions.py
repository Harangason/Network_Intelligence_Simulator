from __future__ import annotations

from typing import Any

from trace_realism import external_signal_records, signal_specs_for_message


def _payload_bits(bus_type: str) -> int:
    return 512 if str(bus_type).lower() in {"fd", "xl", "mixed"} else 64


def _signal_spans(signals: list[dict[str, Any]]) -> list[tuple[int, int, dict[str, Any]]]:
    spans: list[tuple[int, int, dict[str, Any]]] = []
    for signal in signals:
        start = int(signal["start_bit"])
        length = int(signal["length"])
        spans.append((start, start + length, signal))
    return sorted(spans, key=lambda item: (item[0], item[1]))


def _coverage_gaps(signals: list[dict[str, Any]], total_bits: int) -> list[dict[str, int]]:
    gaps: list[dict[str, int]] = []
    cursor = 0
    for start, end, _signal in _signal_spans(signals):
        if start > cursor:
            gaps.append({"start_bit": cursor, "length": start - cursor})
        cursor = max(cursor, end)
    if cursor < total_bits:
        gaps.append({"start_bit": cursor, "length": total_bits - cursor})
    return gaps


def _overlaps(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    overlaps: list[dict[str, Any]] = []
    spans = _signal_spans(signals)
    for index in range(1, len(spans)):
        previous_start, previous_end, previous = spans[index - 1]
        start, end, current = spans[index]
        if start < previous_end:
            overlaps.append(
                {
                    "signals": [previous["name"], current["name"]],
                    "overlap_start_bit": start,
                    "overlap_length": min(previous_end, end) - start,
                    "previous_span": [previous_start, previous_end],
                    "current_span": [start, end],
                }
            )
    return overlaps


def _out_of_bounds(signals: list[dict[str, Any]], total_bits: int) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for start, end, signal in _signal_spans(signals):
        if start < 0 or end > total_bits:
            findings.append(
                {
                    "signal": signal["name"],
                    "span": [start, end],
                    "payload_bits": total_bits,
                }
            )
    return findings


def _name_text(route: dict[str, Any], signals: list[dict[str, Any]]) -> str:
    signal_names = " ".join(str(signal.get("name", "")) for signal in signals)
    return " ".join(
        [
            str(route.get("name", "")),
            str(route.get("sender", "")),
            str(route.get("receiver", "")),
            signal_names,
        ]
    ).lower()


def _missing_semantics(route: dict[str, Any], signals: list[dict[str, Any]]) -> list[str]:
    text = _name_text(route, signals)
    names = " ".join(str(signal.get("name", "")).lower() for signal in signals)
    required: list[tuple[str, tuple[str, ...]]] = []
    if any(token in text for token in ["lidar", "radar", "camera", "object", "lane"]):
        required.extend(
            [
                ("object_distance", ("distance", "range")),
                ("object_relative_speed", ("relspeed", "rel_speed", "relative_speed")),
                ("signal_quality", ("quality", "confidence")),
            ]
        )
    if any(token in text for token in ["brake", "esc", "abs", "wheel"]):
        required.extend(
            [
                ("wheel_or_ego_speed", ("wheelspeed", "wheel_speed", "egospeed", "ego_speed")),
                ("brake_pressure", ("brakepressure", "brake_pressure", "pressure")),
            ]
        )
    if any(token in text for token in ["steer", "trajectory", "lane_change"]):
        required.extend(
            [
                ("steering_angle", ("steeringangle", "steering_angle")),
                ("yaw_rate", ("yawrate", "yaw_rate")),
            ]
        )
    if any(token in text for token in ["engine", "powertrain", "torque", "motor", "inverter"]):
        required.extend(
            [
                ("speed_or_rpm", ("rpm", "speed")),
                ("torque", ("torque",)),
            ]
        )

    required.extend(
        [
            ("alive_or_sequence_counter", ("counter", "sequence", "alive")),
            ("status_or_quality", ("status", "quality", "valid", "health")),
        ]
    )
    missing = [semantic for semantic, tokens in required if not any(token in names for token in tokens)]
    deduped: list[str] = []
    for item in missing:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _proposal_name_matches_semantic(name: str, semantic: str) -> bool:
    lname = name.lower()
    if semantic == "object_distance":
        return "distance" in lname or "range" in lname
    if semantic == "object_relative_speed":
        return "relspeed" in lname or "rel_speed" in lname
    if semantic == "signal_quality":
        return "quality" in lname or "confidence" in lname
    if semantic == "wheel_or_ego_speed":
        return "speed" in lname
    if semantic == "brake_pressure":
        return "brakepressure" in lname or "pressure" in lname
    if semantic == "steering_angle":
        return "steeringangle" in lname
    if semantic == "yaw_rate":
        return "yawrate" in lname
    if semantic == "speed_or_rpm":
        return "rpm" in lname or "speed" in lname
    if semantic == "torque":
        return "torque" in lname
    if semantic == "alive_or_sequence_counter":
        return "counter" in lname
    if semantic == "status_or_quality":
        return any(token in lname for token in ["status", "quality", "valid", "health"])
    return False


def _propose_signals(
    route: dict[str, Any],
    semantics: list[str],
    gaps: list[dict[str, int]],
    bus_type: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not semantics or not gaps:
        return []
    bit_length = 12 if str(bus_type).lower() in {"fd", "xl", "mixed"} else 8
    catalog = signal_specs_for_message(
        str(route.get("sender") or ""),
        str(route.get("receiver") or ""),
        str(route.get("name") or ""),
        signal_count=16,
        bit_length=bit_length,
    )
    proposals: list[dict[str, Any]] = []
    used_names: set[str] = set()
    gap_index = 0
    for semantic in semantics:
        spec = next((candidate for candidate in catalog if _proposal_name_matches_semantic(candidate.name, semantic)), None)
        if spec is None or spec.name in used_names:
            continue
        while gap_index < len(gaps) and gaps[gap_index]["length"] < bit_length:
            gap_index += 1
        if gap_index >= len(gaps):
            break
        gap = gaps[gap_index]
        proposals.append(
            {
                "name": spec.name,
                "start_bit": gap["start_bit"],
                "length": bit_length,
                "factor": spec.factor,
                "offset": spec.offset,
                "minimum": spec.minimum,
                "maximum": spec.maximum,
                "unit": spec.unit,
                "semantic_gap": semantic,
                "rationale": "fills a missing logical signal in an unused payload gap",
            }
        )
        used_names.add(spec.name)
        gap["start_bit"] += bit_length
        gap["length"] -= bit_length
        if len(proposals) >= limit:
            break
    return proposals


def suggest_signal_gaps(
    routing_rows: list[dict[str, Any]] | None,
    bus_type: str,
    *,
    max_routes: int = 25,
    max_proposals_per_route: int = 8,
) -> dict[str, Any]:
    rows = list(routing_rows or [])
    total_bits = _payload_bits(bus_type)
    suggestions: list[dict[str, Any]] = []
    for route in rows[:max_routes]:
        signals = external_signal_records(route.get("signals"))
        route_id = {
            "name": route.get("name"),
            "sender": route.get("sender"),
            "receiver": route.get("receiver"),
            "frame_id": f"0x{int(route.get('frame_id', 0)):X}" if route.get("frame_id") is not None else None,
        }
        if not signals:
            fallback_specs = signal_specs_for_message(
                str(route.get("sender") or ""),
                str(route.get("receiver") or ""),
                str(route.get("name") or ""),
                signal_count=max_proposals_per_route,
                bit_length=12 if total_bits > 64 else 8,
            )
            suggestions.append(
                {
                    "route": route_id,
                    "issue": "missing_external_signal_vector",
                    "severity": "info",
                    "message": "No external signal vector was supplied; built-in physical baseline signals will be used as fallback.",
                    "proposed_signals": [
                        {
                            "name": spec.name,
                            "factor": spec.factor,
                            "offset": spec.offset,
                            "minimum": spec.minimum,
                            "maximum": spec.maximum,
                            "unit": spec.unit,
                            "kind": spec.kind,
                        }
                        for spec in fallback_specs
                    ],
                    "source_policy": "suggestion_only",
                }
            )
            continue

        overlaps = _overlaps(signals)
        if overlaps:
            suggestions.append(
                {
                    "route": route_id,
                    "issue": "overlapping_external_signals",
                    "severity": "error",
                    "message": "External signal bit ranges overlap. The simulator preserves them, but the source vector should be reviewed.",
                    "overlaps": overlaps,
                    "source_policy": "preserve_external_definition",
                }
            )

        out_of_bounds = _out_of_bounds(signals, total_bits)
        if out_of_bounds:
            suggestions.append(
                {
                    "route": route_id,
                    "issue": "external_signal_out_of_payload",
                    "severity": "error",
                    "message": "External signal spans exceed the selected bus payload size.",
                    "signals": out_of_bounds,
                    "source_policy": "preserve_external_definition",
                }
            )

        gaps = _coverage_gaps(signals, total_bits)
        relevant_gaps = [gap for gap in gaps if gap["length"] >= 8]
        missing = _missing_semantics(route, signals)
        proposals = _propose_signals(
            route,
            missing,
            [dict(gap) for gap in relevant_gaps],
            bus_type,
            max_proposals_per_route,
        )
        if missing or proposals:
            suggestions.append(
                {
                    "route": route_id,
                    "issue": "logical_signal_gaps",
                    "severity": "warning" if proposals else "info",
                    "message": "External signal vector is preserved; the following logical additions may improve trace completeness.",
                    "missing_semantics": missing,
                    "available_payload_gaps": relevant_gaps[:8],
                    "proposed_signals": proposals,
                    "source_policy": "suggestion_only",
                }
            )

    return {
        "enabled": True,
        "mode": "non_invasive_suggestions",
        "source_policy": "external definitions are never modified automatically",
        "payload_bits": total_bits,
        "routes_analyzed": min(len(rows), max_routes),
        "suggestions": suggestions,
    }
