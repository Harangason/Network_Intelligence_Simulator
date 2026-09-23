"""Evidence-bound end-to-end transactions shared by runtime and sequence views."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _limit(route: dict[str, Any], *names: str) -> float | None:
    for source in (route, route.get("timing"), route.get("receiver_acceptance_policy"), route.get("metadata")):
        if not isinstance(source, dict):
            continue
        for name in names:
            if name in source:
                value = _number(source[name])
                return value if value is not None and value >= 0 else None
    return None


@dataclass(frozen=True)
class E2EHopTiming:
    event_id: str | None
    segment_index: int
    network_id: str | None
    technology: str | None
    tx_start_s: float | None
    tx_end_s: float | None
    arrival_time_s: float | None
    queue_delay_ms: float | None
    status: str | None


@dataclass(frozen=True)
class E2ETransaction:
    transaction_id: str
    route_id: str
    source_release_time_s: float | None
    source_generation_time_s: float | None
    physical_arrival_time_s: float | None
    transport_latency_ms: float | None
    receiver_accept_time_s: float | None
    e2e_latency_ms: float | None
    data_age_at_accept_ms: float | None
    receiver_status: str
    transport_status: str
    deadline_ms: float | None
    max_data_age_ms: float | None
    timing_margin_ms: float | None
    data_age_margin_ms: float | None
    deadline_status: str
    freshness_status: str
    requirement_status: str
    protection_status: str
    evidence_event_ids: list[str]
    findings: list[str]
    hops: list[E2EHopTiming]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_e2e_transactions(
    events: list[dict[str, Any]], routes: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Correlate explicit trace IDs; never infer receiver acceptance from delivery."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if str(event.get("traffic_type") or "DATA").upper() != "DATA":
            continue
        transaction_id = event.get("transaction_id") or event.get("end_to_end_event_id")
        if transaction_id:
            grouped[str(transaction_id)].append(event)

    transactions: list[dict[str, Any]] = []
    for transaction_id, items in sorted(grouped.items()):
        transport = [item for item in items if str(item.get("event_type") or "").upper() not in
                     {"RECEIVER_ACCEPTANCE", "RECEIVER_REJECTION"}]
        hops = sorted(transport, key=lambda item: int(item.get("segment_index") or 0))
        if not hops:
            continue
        first = hops[0]
        route_id = str(first.get("end_to_end_route_id") or first.get("route_id") or "")
        route = (routes or {}).get(route_id, {})
        expected_count = max(int(item.get("segment_count") or 1) for item in hops)
        indices = {int(item.get("segment_index") or 0) for item in hops}
        final = next((item for item in reversed(hops)
                      if item.get("final_segment") is True or
                      int(item.get("segment_index") or 0) == expected_count - 1), None)
        complete = final is not None and indices == set(range(expected_count))
        delivered = complete and all(item.get("status") == "transmitted" for item in hops)
        release = _number(first.get("origin_release_time_s"))
        generation = _number(first.get("data_generation_time_s"))
        arrival = _number(final.get("time_s")) if delivered and final else None
        transport_latency = (round((arrival - release) * 1000, 6)
                             if arrival is not None and release is not None and arrival >= release else None)
        findings: list[str] = []
        if arrival is not None and release is not None and arrival < release:
            findings.append("ARRIVAL_PRECEDES_RELEASE")

        explicit = next((item for item in reversed(items) if
                         str(item.get("receiver_status") or "").upper() in {"ACCEPTED", "REJECTED"} or
                         str(item.get("receiver_action") or "").upper() in {"ACCEPT", "REJECT"} or
                         str(item.get("event_type") or "").upper() in {"RECEIVER_ACCEPTANCE", "RECEIVER_REJECTION"}), None)
        observed_status = str((explicit or {}).get("receiver_status") or "").upper()
        if observed_status not in {"ACCEPTED", "REJECTED"}:
            action = str((explicit or {}).get("receiver_action") or "").upper()
            kind = str((explicit or {}).get("event_type") or "").upper()
            observed_status = ("ACCEPTED" if action == "ACCEPT" or kind == "RECEIVER_ACCEPTANCE" else
                               "REJECTED" if action == "REJECT" or kind == "RECEIVER_REJECTION" else "NOT_OBSERVED")
        accept = None
        if observed_status == "ACCEPTED":
            accept = _number((explicit or {}).get("receiver_accept_time_s"))
            if accept is None and str((explicit or {}).get("event_type") or "").upper() == "RECEIVER_ACCEPTANCE":
                accept = _number((explicit or {}).get("time_s"))
            if accept is None or release is None or arrival is None or accept < max(release, arrival):
                findings.append("ACCEPTANCE_EVIDENCE_INVALID")
                accept = None
                observed_status = "UNVERIFIED"
        latency = round((accept - release) * 1000, 6) if accept is not None and release is not None else None
        age = round((accept - generation) * 1000, 6) if accept is not None and generation is not None and accept >= generation else None
        if accept is not None and generation is not None and accept < generation:
            findings.append("ACCEPTANCE_PRECEDES_GENERATION")
        deadline = _limit(route, "max_e2e_latency_ms", "maximum_latency_ms", "max_latency_ms", "deadline_ms")
        age_limit = _limit(route, "max_data_age_ms", "freshness_ms", "data_freshness_limit")
        timing_margin = round(deadline - latency, 6) if deadline is not None and latency is not None else None
        age_margin = round(age_limit - age, 6) if age_limit is not None and age is not None else None
        # A late physical arrival is already a lower-bound proof of a missed acceptance deadline.
        deadline_status = ("FAIL" if deadline is not None and
                           ((timing_margin is not None and timing_margin < -1e-7) or
                            (transport_latency is not None and transport_latency > deadline + 1e-7)) else
                           "PASS" if timing_margin is not None else "NOT_EVALUATED")
        freshness_status = ("FAIL" if age_margin is not None and age_margin < -1e-7 else
                            "PASS" if age_margin is not None else "NOT_EVALUATED")
        protection = str((explicit or final or {}).get("protection_status") or "UNVERIFIED").upper()
        transport_status = ("DELIVERED" if delivered else
                            "CORRUPTED" if any(item.get("status") == "corrupted" for item in hops) else "INCOMPLETE")
        if deadline_status == "FAIL":
            findings.append("E2E_DEADLINE_MISSED")
        if freshness_status == "FAIL":
            findings.append("E2E_DATA_STALE")
        if observed_status == "REJECTED":
            findings.append("RECEIVER_REJECTED")
        if protection in {"FAIL", "FAILED", "INVALID", "CORRUPT"}:
            findings.append("E2E_PROTECTION_FAILED")
        requirement_status = ("FAIL" if "FAIL" in (deadline_status, freshness_status) or observed_status == "REJECTED"
                              or protection in {"FAIL", "FAILED", "INVALID", "CORRUPT"} else
                              "PASS" if observed_status == "ACCEPTED" and transport_status == "DELIVERED" and
                              (deadline is not None or age_limit is not None) and
                              all(status == "PASS" for status, limit in ((deadline_status, deadline), (freshness_status, age_limit))
                                  if limit is not None) else "NOT_EVALUATED")
        transactions.append(E2ETransaction(
            transaction_id=transaction_id, route_id=route_id, source_release_time_s=release,
            source_generation_time_s=generation, physical_arrival_time_s=arrival,
            transport_latency_ms=transport_latency, receiver_accept_time_s=accept,
            e2e_latency_ms=latency, data_age_at_accept_ms=age, receiver_status=observed_status,
            transport_status=transport_status, deadline_ms=deadline, max_data_age_ms=age_limit,
            timing_margin_ms=timing_margin, data_age_margin_ms=age_margin,
            deadline_status=deadline_status, freshness_status=freshness_status,
            requirement_status=requirement_status, protection_status=protection,
            evidence_event_ids=[str(item["event_id"]) for item in items if item.get("event_id")],
            findings=findings,
            hops=[E2EHopTiming(
                event_id=str(item["event_id"]) if item.get("event_id") else None,
                segment_index=int(item.get("segment_index") or 0), network_id=item.get("network"),
                technology=item.get("technology"), tx_start_s=_number(item.get("tx_start_s")),
                tx_end_s=_number(item.get("tx_end_s")),
                arrival_time_s=_number(item.get("time_s")) if item.get("status") == "transmitted" else None,
                queue_delay_ms=_number(item.get("queue_delay_ms")), status=item.get("status"),
            ) for item in hops],
        ).to_dict())
    return transactions


def build_sequence_model(
    events: list[dict[str, Any]],
    routes: dict[str, dict[str, Any]] | None = None,
    *,
    source: str,
) -> dict[str, Any]:
    """Build the shared presentation contract from the canonical E2E model.

    Timing, correlation, completeness, and receiver acceptance are taken from
    ``build_e2e_transactions``. This function only adds the event fields the
    sequence renderer needs; it does not infer delivery from a nearby frame.
    """
    transactions = build_e2e_transactions(events, routes)
    by_id = {str(item["transaction_id"]): item for item in transactions}
    participants: set[str] = set()
    sequence_events: list[dict[str, Any]] = []
    correlated = 0
    for index, record in enumerate(events):
        if not isinstance(record, dict):
            continue
        transaction_id = record.get("transaction_id") or record.get("end_to_end_event_id")
        transaction_id = str(transaction_id) if transaction_id else None
        transaction = by_id.get(transaction_id or "")
        sender = record.get("source_name") or record.get("sender_hardware") or record.get("sender") or record.get("source") or "Unbekannt"
        receivers = record.get("destination_names") or record.get("receiver_hardware") or record.get("receivers") or record.get("destination") or []
        if not isinstance(receivers, list):
            receivers = [receivers]
        destination = ", ".join(str(item) for item in receivers if item) or "Unbekannt"
        participants.update((str(sender), destination))
        if transaction_id:
            correlated += 1
        kind = str(record.get("event_type") or "").upper()
        is_receiver = kind in {"RECEIVER_ACCEPTANCE", "RECEIVER_REJECTION"}
        time_value = record.get("time_s", record.get("timestamp"))
        try:
            time_s = float(time_value) if time_value is not None and not isinstance(time_value, bool) else None
        except (TypeError, ValueError):
            time_s = None
        time_status = str(record.get("time_status") or "").lower()
        if time_status in {"unavailable", "invalid", "unknown"}:
            time_s = None
        status = str(record.get("status") or "observed")
        receiver_status = transaction.get("receiver_status") if transaction else "NOT_OBSERVED"
        accept_time = transaction.get("receiver_accept_time_s") if transaction else None
        sequence_events.append({
            "id": str(record.get("event_id") or f"{source}:{index}"),
            "transactionId": transaction_id,
            "timeS": time_s,
            "source": str(sender),
            "destination": destination,
            "technology": str(record.get("technology") or record.get("bus") or record.get("channel") or "Unbekannt"),
            "route": str(record.get("route_name") or record.get("route_id") or record.get("message") or "Unbekannt"),
            "status": status,
            "segmentIndex": record.get("segment_index"),
            "segmentCount": record.get("segment_count"),
            "releaseTimeS": transaction.get("source_release_time_s") if transaction else record.get("origin_release_time_s"),
            "transportLatencyMs": transaction.get("transport_latency_ms") if transaction else None,
            "queueDelayMs": record.get("queue_delay_ms"),
            "payloadBytes": record.get("payload_bytes"),
            "eventKind": "RECEIVER" if is_receiver else "TRANSPORT",
            "receiverStatus": receiver_status if is_receiver else None,
            "receiverAcceptTimeS": accept_time if is_receiver else None,
            "e2eLatencyMs": transaction.get("e2e_latency_ms") if transaction else None,
            "dataAgeAtAcceptMs": transaction.get("data_age_at_accept_ms") if transaction else None,
        })
    sequence_events.sort(key=lambda item: item["timeS"] if item["timeS"] is not None else float("inf"))
    event_ids_by_transaction: dict[str, list[str]] = defaultdict(list)
    technologies_by_transaction: dict[str, set[str]] = defaultdict(set)
    for event in sequence_events:
        transaction_id = event["transactionId"]
        if not transaction_id:
            continue
        event_ids_by_transaction[transaction_id].append(event["id"])
        if event["eventKind"] == "TRANSPORT":
            technologies_by_transaction[transaction_id].add(event["technology"])
    sequence_transactions = [{
        "id": item["transaction_id"],
        "eventIds": event_ids_by_transaction.get(item["transaction_id"], []),
        "technologies": sorted(technologies_by_transaction.get(item["transaction_id"], set())),
        "complete": item["transport_status"] == "DELIVERED",
        "receiverStatus": item["receiver_status"],
        "e2eLatencyMs": item["e2e_latency_ms"],
        "dataAgeAtAcceptMs": item["data_age_at_accept_ms"],
        "deadlineStatus": item["deadline_status"],
        "freshnessStatus": item["freshness_status"],
        "requirementStatus": item["requirement_status"],
        "evidenceEventIds": item["evidence_event_ids"],
        "findings": item["findings"],
    } for item in transactions]
    return {
        "source": source,
        "participants": sorted(participants),
        "events": sequence_events,
        "transactions": sequence_transactions,
        "correlatedCount": correlated,
        "uncorrelatedCount": len(sequence_events) - correlated,
    }
