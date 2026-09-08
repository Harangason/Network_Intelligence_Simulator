"""Time and identity joins. Chronology alone is never a causal mechanism."""
import hashlib
import json
import math
from collections import defaultdict


def number(value, default=None):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (ValueError, TypeError):
        return default


def event_time(event):
    value = number(event.get("time_s", event.get("timestamp_s")))
    if value is None or value < 0:
        raise ValueError("Trace-Ereignis ohne gültige Simulationszeit.")
    return value


def event_id(event):
    explicit = event.get("event_id")
    if explicit:
        return str(explicit)
    compact = {k: event.get(k) for k in ("route_id", "sequence", "time_s", "status", "sender_interface", "network", "signals", "faults")}
    return hashlib.sha256(json.dumps(compact, sort_keys=True, default=str).encode()).hexdigest()[:24]


def object_refs(event):
    pairs = [("Route", event.get("route_ref") or event.get("route_id")), ("Network", event.get("network")),
             ("HardwareNode", event.get("sender_hardware")), ("HardwareInterface", event.get("sender_interface"))]
    for kind, key in (("HardwareNode", "receiver_hardware"), ("HardwareNode", "gateway_ids"),
                      ("HardwareInterface", "receiver_interfaces"), ("TransportUnit", "message_ids")):
        values = event.get(key) or []
        if not isinstance(values, list):
            values = [values]
        pairs.extend((kind, value) for value in values)
    return [{"object_type": kind, "id": str(value)} for kind, value in pairs if value is not None and str(value)]


def correlate_time(left, right, *, mechanism_validated=False):
    if left > right + 1e-9:
        return "AFTER"
    if abs(left - right) <= 1e-9:
        return "SIMULTANEOUS"
    return "CAUSE_PRECEDES_EFFECT" if mechanism_validated else "BEFORE"


def route_context(event, routes):
    route = next((r for r in routes if str(r.get("id")) in {str(event.get("route_ref")), str(event.get("route_id"))}), None)
    source = (route or {}).get("source") or {}
    path = {"route_id": event.get("route_ref") or event.get("route_id"),
            "source_node": event.get("sender_hardware") or source.get("node_id"),
            "logical_address": event.get("source_logical_address") or source.get("logical_address"),
            "source_interface": event.get("sender_interface") or source.get("hardware_interface_id"),
            "network": event.get("network") or source.get("network_id"),
            "gateway_hops": event.get("gateway_ids") or [h.get("node_id") for h in ((route or {}).get("route") or {}).get("hops", []) if isinstance(h, dict)],
            "destination_interfaces": event.get("receiver_interfaces") or [],
            "destination_nodes": event.get("receiver_hardware") or [d.get("node_id") for d in (route or {}).get("destinations") or []],
            "revision": (route or {}).get("version"), "snapshot_route_found": route is not None}
    path["complete"] = all(path.get(k) for k in ("route_id", "source_node", "source_interface", "network", "destination_interfaces", "destination_nodes"))
    return path


def signal_samples(event):
    raw = event.get("signals") or event.get("signal_values") or []
    if isinstance(raw, dict):
        return [{"signal_id": str(k), **(v if isinstance(v, dict) else {"value": v})} for k, v in raw.items()]
    return [v for v in raw if isinstance(v, dict)]


class FirstDivergenceAnalyzer:
    @staticmethod
    def analyze(actual, golden):
        # Existing comparator remains the shared source of frequency/value metrics.
        from ..agent_tools.analysis import compare
        summary = compare({"events": actual, "golden_events": golden})
        def key(e):
            identity = e.get("message_ids") or e.get("message_id") or e.get("route_id")
            return json.dumps(identity, sort_keys=True), str(e.get("sequence", e.get("time_s")))
        a, b = defaultdict(list), defaultdict(list)
        for e in actual:
            a[key(e)].append(e)
        for e in golden:
            b[key(e)].append(e)
        deviations = []
        for identity in a.keys() | b.keys():
            for index in range(max(len(a[identity]), len(b[identity]))):
                left = a[identity][index] if index < len(a[identity]) else None
                right = b[identity][index] if index < len(b[identity]) else None
                kinds = []
                if left is None or right is None:
                    kinds.append("MISSING_EVENT" if left is None else "ADDITIONAL_EVENT")
                else:
                    if abs(event_time(left) - event_time(right)) > 1e-9:
                        kinds.append("TIMING_DEVIATION")
                    for field, kind in (("route_id", "ROUTE_DEVIATION"), ("network", "ROUTE_DEVIATION"), ("status", "STATE_DEVIATION"), ("faults", "FAULT_DEVIATION")):
                        if left.get(field) != right.get(field):
                            kinds.append(kind)
                    def values(e):
                        return {str(s.get("signal_id") or s.get("name") or s.get("signal")): (s.get("value"), s.get("state"), s.get("quality")) for s in signal_samples(e)}
                    if values(left) != values(right):
                        kinds.append("SIGNAL_DEVIATION")
                if kinds:
                    deviations.append({"timestamp": min(event_time(e) for e in (left, right) if e is not None),
                        "types": sorted(set(kinds)), "actual_event_id": event_id(left) if left else None,
                        "golden_event_id": event_id(right) if right else None,
                        "route_id": (left or right).get("route_id"), "causality_proven": False})
        deviations.sort(key=lambda d: (d["timestamp"], str(d["actual_event_id"])))
        return {**summary, "first_divergence": deviations[0] if deviations else None,
                "ordered_divergences": deviations[:100], "first_credible_causal_deviation": None,
                "causality_proven": False, "scope": "BOUNDED_TRACE_WINDOW"}
