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
    if arguments.get("events") is None:
        from urllib.parse import quote, urlencode
        from .simulation_gateway import request_json
        if arguments.get("offset", 0):
            raise ValueError("Job-Traces verwenden Byte-Cursor: next_cursor als cursor übergeben; offset gilt nur für Inline-Ereignisse.")
        query = urlencode({"start_s": arguments.get("start_s", 0), "end_s": arguments.get("end_s", 1e12),
            "cursor": arguments.get("cursor", 0), "limit": min(int(arguments.get("limit", 500)), 1000)})
        page = request_json(f"/simulations/{quote(arguments['job_id'], safe='')}/trace-window?{query}")
        return {**page, "total": None, "next_offset": None, "pagination": "BYTE_CURSOR",
                "validation_status": "PARTIAL" if page["next_cursor"] is not None else "VALIDATED"}
    events = trace_events(arguments)
    start, end = float(arguments.get("start_s", 0)), float(arguments.get("end_s", 1e12))
    if start < 0 or end < start:
        raise ValueError("Ungültiges Zeitfenster.")
    limit = min(int(arguments.get("limit", 1000)), 10000)
    offset = int(arguments.get("offset", 0))
    selected, total = [], 0
    for event in events:
        from ..reasoning.correlation import event_time
        # Missing time is not t=0. A time-window operation needs a valid
        # timestamp; callers must supply the missing evidence explicitly.
        timestamp = event_time(event)
        if start <= timestamp <= end:
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
    from ..reasoning.engine import EngineeringReasoningEngine
    from ..reasoning.service import ReasoningService
    if arguments.get("events") is None:
        result = ReasoningService().analyze({k: arguments[k] for k in ("job_id", "start_s", "end_s") if k in arguments})
    else:
        result = EngineeringReasoningEngine().analyze(project_id=current_project_id(), job_id="inline-trace",
            events=trace_events(arguments), context={"snapshot_available": False, "trusted_simulation": False,
                "configuration": arguments.get("configuration") or {}, "faults": []})
    data = result.model_dump(mode="json")
    # Preserve the old affected_objects lookup while all conclusions come from one core.
    refs = {e.id: e for e in result.evidence_refs}
    for item in data["hypotheses"]:
        item["affected_objects"] = next(({k: refs[r].details[k] for k in ("route_id", "network", "gateway_ids", "message_ids") if k in refs[r].details}
            for r in item["evidence_refs"] if r in refs and refs[r].source_type == "TraceEvent"), {})
    return {**data, "causality_proven": bool(result.confirmed_causes) and result.validation_status == "CURRENT"}


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
    if arguments.get("events") is None and arguments.get("job_id") and arguments.get("golden_job_id"):
        from ..reasoning.service import ReasoningService
        return ReasoningService().inspect("find_first_divergence", arguments)["data"]
    actual = trace_events(arguments)
    golden = trace_events({"job_id": arguments["golden_job_id"]}) if arguments.get("golden_job_id") else arguments.get("golden_events", [])
    if not golden:
        raise ValueError("Ein Golden Trace ist erforderlich.")
    if not isinstance(golden, list) or len(golden) > 100000:
        raise ValueError('Golden Trace benötigt höchstens 100000 Ereignisse; größere Traces fensterweise vergleichen.')
    def identity(event):
        # Arrival time is an observation, not identity: a delayed frame is still
        # the same frame and its signal values must remain comparable.
        sequence = event.get('sequence', event.get('sequence_number'))
        return (str(event.get('route_id') or event.get('message_id') or 'unknown'),
                str(sequence) if sequence is not None else str(float(event.get('time_s', 0))))
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
                    result[str(name)][identity(event)] = float(value)
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
    actual_events = {identity(item): item for item in actual}
    golden_events = {identity(item): item for item in golden}
    deviations = []
    for key in sorted(actual_events.keys() | golden_events.keys()):
        left, right = actual_events.get(key), golden_events.get(key)
        difference = {'route_id': key[0], 'sequence': key[1]}
        if left is None or right is None:
            difference['type'] = 'MISSING_EVENT' if left is None else 'ADDITIONAL_EVENT'
        else:
            delta = float(left.get('time_s', 0)) - float(right.get('time_s', 0))
            if abs(delta) > 1e-9:
                difference['timing_delta_s'] = delta
            for field in ('status', 'network', 'faults'):
                if left.get(field) != right.get(field):
                    difference[field] = {'actual': left.get(field), 'golden': right.get(field)}
            if len(difference) == 2:
                continue
            difference['type'] = 'EVENT_DEVIATION'
        deviations.append(difference)
    findings = [{'code': 'GOLDEN_TRACE_DEVIATION', 'severity': 'WARNING', 'evidence': item}
                for item in deviations[:200]]
    findings.extend({'code': 'SIGNAL_DEVIATION', 'severity': 'WARNING', 'evidence': item}
                    for item in values if (item['max_absolute_error'] or 0) > 0)
    return {"event_count_delta": len(actual)-len(golden), "routes": [
        {"id": key, "actual": a[key], "golden": g[key], "delta": a[key]-g[key]} for key in sorted(a.keys() | g.keys())],
        "method": "MESSAGE_FREQUENCY_AND_ALIGNED_VALUE_COMPARISON", "value_comparison": values,
        "alignment": "ROUTE_SEQUENCE_OR_TIMESTAMP", "deviation_count": len(deviations),
        "event_deviations": deviations[:200], "findings": findings}


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
