"""Bounded trace and graph analysis shared by MCP consumers."""
from __future__ import annotations

from collections import defaultdict
import json
import math
from statistics import mean
from ..project_context import current_project_id
from ..repository import NotFoundError
from ..relations import list_relations
from .model import model


def trace_events(arguments: dict) -> list[dict]:
    if arguments.get("events") is not None:
        events = arguments["events"]
        if not isinstance(events, list) or len(events) > 100000:
            raise ValueError("events muss eine Liste mit höchstens 100000 Einträgen sein.")
        return events
    from .simulation_gateway import trace
    return trace(arguments["job_id"])


def window(arguments: dict) -> dict:
    from .simulation_gateway import iter_trace
    events = trace_events(arguments) if arguments.get("events") is not None else iter_trace(arguments["job_id"])
    start, end = float(arguments.get("start_s", 0)), float(arguments.get("end_s", 1e12))
    if start < 0 or end < start:
        raise ValueError("Ungültiges Zeitfenster.")
    limit = min(int(arguments.get("limit", 1000)), 10000)
    offset = int(arguments.get("offset", 0))
    selected, total = [], 0
    for event in events:
        if start <= float(event.get("time_s", 0)) <= end:
            if offset <= total < offset+limit:
                selected.append(event)
            total += 1
    return {"events": selected, "total": total, "next_offset": offset+limit if offset+limit < total else None}


def analyze(arguments: dict) -> dict:
    events = trace_events(arguments)
    if not events:
        return {"available": False, "event_count": 0, "findings": [{"severity": "WARNING", "code": "TRACE_EMPTY"}]}
    from backend.app.runtime_analysis import analyze_runtime_trace
    config = arguments.get("configuration") or {}
    result = analyze_runtime_trace({"model_simulation": {"frames": events}}, config)
    return {**result, "event_count": len(events), "evidence": [{"source": "trace", "sample_count": len(events)}]}


def root_cause(arguments: dict) -> dict:
    result = analyze(arguments)
    events = trace_events(arguments)
    faults = [event for event in events if event.get("fault") or event.get("error") or event.get("status") in {"ERROR", "FAILED"}]
    return {"analysis": result, "hypotheses": [{"reason": "Zeitlich zugeordneter Fehler im Trace",
             "event": item, "confidence": 0.6, "requires_review": True} for item in faults[:50]],
            "causality_proven": False, "evidence": [{"fault_event_count": len(faults)}]}


def correlate(arguments: dict) -> dict:
    """Match timestamps explicitly; never correlate unrelated sample positions."""
    events = trace_events(arguments)
    series: dict[str, dict[float, float]] = defaultdict(dict)
    for event in events:
        timestamp = float(event.get("time_s", 0))
        raw = event.get("signals") or event.get("signal_values") or {}
        items = raw.items() if isinstance(raw, dict) else ((s.get("name") or s.get("signal_id"), s.get("value")) for s in raw)
        for name, value in items:
            if isinstance(value, dict):
                value = value.get("physical_value", value.get("value"))
            if isinstance(value, (float, int)) and math.isfinite(value):
                series[str(name)][timestamp] = float(value)
    names = arguments.get("signal_names") or sorted(series)[:20]
    if len(names) > 50:
        raise ValueError("Höchstens 50 Signale gemeinsam korrelieren.")
    correlations = []
    for index, left in enumerate(names):
        for right in names[index+1:]:
            timestamps = sorted(series[left].keys() & series[right].keys())
            if len(timestamps) < 3:
                continue
            x, y = [series[left][t] for t in timestamps], [series[right][t] for t in timestamps]
            mx, my = mean(x), mean(y)
            denominator = math.sqrt(sum((v-mx)**2 for v in x) * sum((v-my)**2 for v in y))
            correlations.append({"left": left, "right": right, "samples": len(x),
                                 "pearson_r": sum((a-mx)*(b-my) for a,b in zip(x,y))/denominator if denominator else None})
    return {"correlations": correlations, "method": "PEARSON_ON_MATCHED_TIMESTAMPS", "causality_proven": False}


def compare(arguments: dict) -> dict:
    actual = trace_events(arguments)
    golden = trace_events({"job_id": arguments["golden_job_id"]}) if arguments.get("golden_job_id") else arguments.get("golden_events", [])
    if not golden:
        raise ValueError("Ein Golden Trace ist erforderlich.")
    def summarize(events):
        counts = defaultdict(int)
        for event in events:
            counts[str(event.get("route_id") or event.get("message_id") or "unknown")] += 1
        return counts
    def samples(events):
        result = defaultdict(dict)
        for event in events:
            values = event.get("signals") or event.get("signal_values") or {}
            items = values.items() if isinstance(values, dict) else ((item.get("name") or item.get("signal_id"), item.get("value")) for item in values)
            for name, value in items:
                if isinstance(value, dict):
                    value = value.get("physical_value", value.get("value"))
                if isinstance(value, (int, float)) and math.isfinite(value):
                    result[str(name)][float(event.get("time_s", 0))] = float(value)
        return result
    actual_samples, golden_samples = samples(actual), samples(golden)
    values = []
    for name in sorted(actual_samples.keys() | golden_samples.keys()):
        left, right = actual_samples[name], golden_samples[name]
        common = left.keys() & right.keys()
        deltas = [left[t]-right[t] for t in common]
        values.append({"signal": name, "matched_samples": len(common), "unmatched_samples": len(left.keys() ^ right.keys()),
                       "rmse": math.sqrt(mean(delta*delta for delta in deltas)) if deltas else None,
                       "max_absolute_error": max(map(abs, deltas)) if deltas else None})
    a, g = summarize(actual), summarize(golden)
    return {"event_count_delta": len(actual)-len(golden), "routes": [
        {"id": key, "actual": a[key], "golden": g[key], "delta": a[key]-g[key]} for key in sorted(a.keys() | g.keys())],
        "method": "MESSAGE_FREQUENCY_AND_ALIGNED_VALUE_COMPARISON", "value_comparison": values}


def graph_analysis() -> dict:
    snapshot = model()
    adjacency: dict[str, set[str]] = {str(node["id"]): set() for node in snapshot["hardware"]}
    routes = [route for route in snapshot["routing"] if str(route.get("approval_state") or "").upper() == "APPROVED" and str(route.get("status") or "").upper() not in {"REJECTED","SUPERSEDED","DEPRECATED","OUTDATED"}]
    for route in routes:
        source = str((route.get("source") or {}).get("node_id") or "")
        hops = [str(hop.get("node_id") or "") if isinstance(hop, dict) else str(hop) for hop in (route.get("route") or {}).get("hops", [])]
        for destination in route.get("destinations") or []:
            path = [source, *hops, str(destination.get("node_id") or "")]
            path = [node for index, node in enumerate(path) if node in adjacency and (index == 0 or node != path[index-1])]
            for left, right in zip(path, path[1:]):
                adjacency[left].add(right)
                adjacency[right].add(left)
    def components(excluded=None):
        remaining = set(adjacency) - {excluded}
        count = 0
        while remaining:
            queue = [remaining.pop()]
            count += 1
            while queue:
                for peer in adjacency[queue.pop()] & remaining:
                    remaining.remove(peer)
                    queue.append(peer)
        return count
    baseline = components()
    spof = [node for node in adjacency if components(node) > baseline]
    hardware_ids = set(adjacency)
    gaps = [{"code": "UNMAPPED_FUNCTION", "id": function["id"]} for function in snapshot["functions"]
            if str(function.get("hardware_node_id")) not in hardware_ids]
    gaps.extend({"code": "ISOLATED_HARDWARE", "id": node} for node, peers in adjacency.items() if not peers)
    return {"gaps": gaps, "single_points_of_failure": spof, "connected_components": baseline,
            "graph_source": "canonical_routes", "node_count": len(adjacency)}
