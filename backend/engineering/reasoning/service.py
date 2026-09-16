"""Application service over existing jobs, trace windows, snapshots and proposals."""
import hashlib
import json
from urllib.parse import quote, urlencode
from uuid import UUID
from psycopg.types.json import Jsonb

from ..agent_tools import simulation_gateway as gateway
from ..agent_tools.model import json_safe
from ..db import get_connection
from ..project_context import current_project_id
from ..repository import NotFoundError
from ..simulation import trace_metadata
from ..workflow.service import WorkflowStatusService, WorkflowConflictError
from .contracts import CAPABILITY_VERSION, ReasoningRequest, SimulationReasoningResult
from .correlation import FirstDivergenceAnalyzer, complete_window_counterparts, event_time, signal_samples, correlate_time, object_refs, event_id
from .engine import EngineeringReasoningEngine

SOURCE_STEPS = ("engineering_model", "routing", "network_editor", "parameters", "simulation")


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


def stimulus_signature(config):
    traffic = [{key: route.get(key) for key in ('id', 'message_ids', 'signal_ids', 'payload_bytes', 'cycle_ms', 'deadline_ms', 'phase_ms', 'jitter_ratio', 'fault_model')}
        for route in config.get('communications') or []]
    return signature({'traffic': sorted(traffic, key=lambda row: str(row.get('id'))),
        'overlays': {key: config.get(key) for key in ('dropout_probability', 'corruption_probability', 'duplicate_probability',
            'reordering_probability', 'retry_limit', 'retransmission_enabled', 'deadline_ms')}})


class TraceWindowResolver:
    """At most three existing trace-window requests, bounded in bytes and events."""
    def __init__(self, reader=None):
        self.reader = reader or gateway.request_json

    def stream(self, job_id):
        cursor = 0
        for _ in range(2001):
            parameters = urlencode({'start_s': 0, 'end_s': 1e15, 'cursor': cursor, 'limit': 500})
            page = self.reader(f'/simulations/{quote(job_id, safe="")}/trace-window?{parameters}')
            yield from page['events']
            following = page['next_cursor']
            if following is None:
                return
            if following <= cursor:
                raise ValueError('Trace-Cursor hat keinen Fortschritt gemacht.')
            cursor = following
        raise ValueError('GOLDEN_ALIGNMENT_INCOMPLETE: Gegenereignisse überschreiten das Seitenbudget.')

    def resolve(self, request: ReasoningRequest):
        start, end = request.start_s, request.end_s
        if request.focus_s is not None:
            start, end = max(start, request.focus_s-.1), min(end, request.focus_s+.1)
        if end < start:
            raise ValueError("Ungültiges Reasoning-Zeitfenster.")
        events, cursor, pages = [], request.cursor, 0
        for _ in range(3):
            parameters = urlencode({"start_s": start, "end_s": end, "cursor": cursor, "limit": 500})
            page = self.reader(f"/simulations/{quote(request.job_id, safe='')}/trace-window?{parameters}")
            events.extend(page["events"])
            pages += 1
            next_cursor = page["next_cursor"]
            if next_cursor is None:
                cursor = None
                break
            if next_cursor <= cursor:
                raise ValueError("Trace-Cursor hat keinen Fortschritt gemacht.")
            cursor = next_cursor
        focus = request.focus_s
        window = {"start_s": start, "end_s": end, "focus_s": focus, "next_cursor": cursor,
                  "pages_read": pages, "event_count": len(events), "scope": "BOUNDED_TRACE_WINDOW",
                  "pre_window": [start, focus] if focus is not None else None,
                  "event_window": [focus, focus] if focus is not None else [start, end],
                  "post_window": [focus, end] if focus is not None else None}
        return events, window


class ReasoningService:
    def __init__(self):
        self.project_id = current_project_id()
        self.workflow = WorkflowStatusService(self.project_id)

    def context(self, job_id):
        # Read metadata before opening a project transaction; no full trace response.
        job = gateway.request_json(f"/simulations/{quote(job_id, safe='')}?view=metadata")
        if job.get("project_id") != self.project_id:
            raise NotFoundError("Simulationslauf gehört nicht zum aktiven Projekt.")
        if job.get("status") not in {"completed", "failed"}:
            raise WorkflowConflictError("Der Simulationslauf ist noch nicht abgeschlossen.")
        snapshot_id = job.get("workflow_snapshot_id")
        snapshot = self.workflow.get_simulation_snapshot(snapshot_id) if snapshot_id else None
        config = (snapshot or {}).get("configuration") or {}
        state = self.workflow.get(summary=True)
        metadata = trace_metadata(job_id)
        metadata = metadata[0] if metadata else {}
        source_model = config.get("engineering_model") or {}
        dependencies = {}
        state_models = dict(config.get("state_models") or {})
        for signal in source_model.get("signals") or []:
            value = signal.get("source_dependencies") or (signal.get("behavior") or {}).get("source_dependencies")
            if value is not None:
                dependencies[str(signal["id"])] = value
        for behavior in source_model.get("behaviors") or []:
            parameters = behavior.get("parameters") or {}
            sid = str(behavior.get("signal_id") or "")
            explicit = parameters.get("source_dependencies") or parameters.get("dependencies")
            if isinstance(explicit, (list, dict)):
                dependencies[sid] = list(explicit)
            machine = parameters.get("state_machine") or parameters
            if isinstance(machine.get("transitions"), list):
                state_models[sid] = {"transitions": machine["transitions"]}
        lineage = {"simulation_snapshot": snapshot_id, "simulation_run": job_id,
            "trace_session": str(metadata.get("id") or job_id), "trace_revision": signature({k: job.get(k) for k in ("id", "updated_at", "status", "output_dir")}),
            "route_revision": {str(r.get("id")): r.get("version") for r in source_model.get("routes") or []},
            "technology_model_version": metadata.get("model_versions") or {}, "analysis_version": 1,
            "reasoning_capability_version": CAPABILITY_VERSION,
            "source_versions": {k: state["versions"].get(k) for k in SOURCE_STEPS},
            "snapshot_source_versions": (snapshot or {}).get("source_versions") or {},
            "snapshot_outdated": bool((snapshot or {}).get("is_outdated")),
            "scenario_signature": signature(config.get("scenario") or metadata.get("scenario_snapshot") or {}),
            "stimulus_signature": stimulus_signature(config),
            "seed": config.get("seed", metadata.get("seed")), "duration_s": config.get("duration_s", metadata.get("duration_s"))}
        return {"snapshot_available": snapshot is not None, "trusted_simulation": True,
            "trace_session_id": lineage["trace_session"], "configuration": config,
            "routes": source_model.get("routes") or [], "dependencies": dependencies, "state_models": state_models,
            "faults": (config.get("scenario") or {}).get("faults", metadata.get("faults") or []),
            "lineage": lineage, "job_status": job["status"], "job_error": job.get("error")}

    def analyze(self, payload):
        request = payload if isinstance(payload, ReasoningRequest) else ReasoningRequest.model_validate(payload)
        previous = self.get(request.previous_reasoning_id) if request.previous_reasoning_id else None
        if previous and (previous.simulation_run_id != request.job_id or previous.validation_status == "STALE"):
            raise WorkflowConflictError("Eine veraltete oder fremde Analyse kann nicht fortgesetzt werden.")
        if previous and (not previous.continuation or any(getattr(request, k) != previous.continuation[k] for k in ("cursor", "start_s", "end_s"))):
            raise WorkflowConflictError("Fortsetzung muss am gespeicherten Cursor im selben Zeitfenster erfolgen.")
        context = self.context(request.job_id)
        try:
            events, window = TraceWindowResolver().resolve(request)
        except NotFoundError:
            if context["job_status"] != "failed":
                raise
            events, window = [], {"start_s": request.start_s, "end_s": request.end_s, "next_cursor": None}
        comparison = None
        if request.golden_job_id:
            golden, golden_window = TraceWindowResolver().resolve(request.model_copy(update={"job_id": request.golden_job_id, "cursor": 0}))
            golden_context = self.context(request.golden_job_id)
            if golden:
                actual_comparison, golden_comparison = complete_window_counterparts(
                    events, golden, lambda: TraceWindowResolver().stream(request.job_id),
                    lambda: TraceWindowResolver().stream(request.golden_job_id))
                comparison = FirstDivergenceAnalyzer.analyze(actual_comparison, golden_comparison)
                comparison['alignment'] = 'WINDOW_WITH_STREAM_VERIFIED_COUNTERPARTS'
                comparison["golden_job_id"] = request.golden_job_id
                comparison["golden_lineage"] = golden_context["lineage"]
            if golden_window["next_cursor"] is not None or not golden or request.cursor:
                context.setdefault("data_gaps", []).append({"code": "INCOMPLETE_GOLDEN_WINDOW", "message": "Referenzvergleich nicht vollständig oder Fenster unterschiedlich paginiert. Zeitbereich eingrenzen."})
        result = EngineeringReasoningEngine().analyze(project_id=self.project_id, job_id=request.job_id, events=events,
            context=context, goal=request.goal, window=window, previous=previous, comparison=comparison)
        if context["job_status"] == "failed":
            result.data_gaps.append({"code": "SIMULATION_FAILED", "message": context.get("job_error") or "Lauf fehlgeschlagen; Trace möglicherweise unvollständig.", "blocking": True})
            result.completion_status = "INCOMPLETE"
            result.validation_status = "BLOCKED_BY_DATA_GAP"
            result.confirmed_causes = []
            result.conclusion = "ROOT_CAUSE_UNCONFIRMED: Fehlgeschlagener Simulationslauf; technische Fehlerdetails und Trace-Abdeckung prüfen."
        if context["lineage"]["snapshot_outdated"]:
            result.validation_status = "STALE"
        self._save(result, request)
        return result

    def _save(self, result, request):
        # Reuse analysis snapshots without advancing or invalidating engineering phases.
        with get_connection() as connection:
            connection.execute("INSERT INTO engineering_analysis_snapshots (id, project_id, analysis_type, source_versions, input_data, results, findings, provenance, status) VALUES (%s,%s,'reasoning',%s,%s,%s,%s,%s,%s)",
                (result.reasoning_id, self.project_id, Jsonb(result.lineage["source_versions"]), Jsonb(request.model_dump(mode="json")),
                 Jsonb(result.model_dump(mode="json")), Jsonb(result.findings), Jsonb(result.lineage), result.completion_status))

    def get(self, identifier):
        try:
            UUID(str(identifier))
        except ValueError as exc:
            raise NotFoundError("Reasoning-Ergebnis nicht gefunden.") from exc
        with get_connection() as connection:
            row = connection.execute("SELECT results FROM engineering_analysis_snapshots WHERE id=%s AND project_id=%s AND analysis_type='reasoning'", (identifier, self.project_id)).fetchone()
        if not row:
            raise NotFoundError("Reasoning-Ergebnis nicht gefunden.")
        result = SimulationReasoningResult.model_validate(row["results"])
        state = self.workflow.get(summary=True)
        if (result.lineage.get("snapshot_outdated") or result.lineage.get("reasoning_capability_version") != CAPABILITY_VERSION
                or result.lineage.get("source_versions") != {k: state["versions"].get(k) for k in SOURCE_STEPS}):
            result.validation_status = "STALE"
        try:
            job = gateway.request_json(f"/simulations/{quote(result.simulation_run_id, safe='')}?view=metadata")
            if result.lineage.get("trace_revision") != signature({k: job.get(k) for k in ("id", "updated_at", "status", "output_dir")}):
                result.validation_status = "STALE"
        except NotFoundError:
            result.validation_status = "STALE"
        return result

    def list(self, job_id=None):
        with get_connection() as connection:
            rows = connection.execute("SELECT id, status, created_at, results->>'simulation_run_id' AS job_id, results->>'conclusion' AS conclusion FROM engineering_analysis_snapshots WHERE project_id=%s AND analysis_type='reasoning' AND (%s::text IS NULL OR results->>'simulation_run_id'=%s) ORDER BY created_at DESC LIMIT 30", (self.project_id, job_id, job_id)).fetchall()
        return json_safe(rows)

    def continue_analysis(self, identifier):
        old = self.get(identifier)
        if old.validation_status == "STALE":
            raise WorkflowConflictError("Analyse ist veraltet; bitte neu starten.")
        if not old.continuation:
            raise WorkflowConflictError("Keine weitere Trace-Seite offen. Für weitere Evidenz ein neues Zeitfenster wählen.")
        if old.comparison:
            raise WorkflowConflictError("Für Golden-Vergleiche bitte das Zeitfenster eingrenzen; ungleich paginierte Läufe werden nicht zusammengeführt.")
        return self.analyze({"job_id": old.simulation_run_id, "goal": old.goal,
            **old.continuation, "previous_reasoning_id": identifier})

    def propose(self, identifier, action_id):
        from ..agent_tools import wizard_generation
        result = self.get(identifier)
        if result.validation_status != "CURRENT":
            raise WorkflowConflictError("Nur aktuelle, vollständige Evidenz darf einen Änderungsvorschlag begründen.")
        action = next((a for a in result.recommended_actions if a["id"] == action_id), None)
        if not action or not action.get("proposal_supported"):
            raise ValueError("Für diese Empfehlung ist noch eine fachliche Konkretisierung nötig; keine Modelländerung ausgeführt.")
        if action_id == "capacity-repair":
            from ..agent_tools import proposal_service
            proposal = wizard_generation.generate_capacity_network_repair({"prompt": f"Kapazitätsverbesserung auf Basis Reasoning {identifier}: {result.conclusion}"})
            # The wizard normally supplies this validation boundary. Direct
            # reasoning/UI callers must receive an equally reviewable proposal.
            return proposal_service.validate(proposal["proposal_id"])
        raise ValueError("Empfehlung besitzt keinen freigegebenen Proposal-Adapter.")

    def compare_runs(self, before_id, after_id):
        before, after = self.get(before_id), self.get(after_id)
        same_experiment = all(before.lineage.get(k) == after.lineage.get(k) and before.lineage.get(k) is not None for k in ("scenario_signature", "stimulus_signature", "seed", "duration_s"))
        complete_windows = not before.continuation and not after.continuation and all(before.time_range.get(k) == after.time_range.get(k) for k in ("start_s", "end_s"))
        def metrics(result):
            trace = next((e.details for e in result.evidence_refs if e.source_type == "TraceMetrics"), {})
            return {"network_load": max((float(n["peak_load_percent"]) for e in result.evidence_refs if e.source_type == "CapacityResult" for n in e.details.get("networks") or [] if n.get("peak_load_percent") is not None), default=None),
                "max_latency_ms": trace.get("max_latency_ms") if trace.get("latency_available") else None,
                "coverage": trace.get("transport_event_counts"), "signal_ids": trace.get("signal_ids"),
                "deadline_misses": sum(o.type == "DEADLINE_MISS" for o in result.observations),
                "signal_anomalies": sum(o.type == "SIGNAL_ANOMALY" for o in result.observations),
                "message_losses": sum(o.type == "MESSAGE_LOSS" for o in result.observations),
                "fault_effects": sum(h.status == "SUPPORTED" and h.id.startswith("fault:") for h in result.hypotheses),
                "findings": sorted({f["code"] for f in result.findings}), "root_cause": result.conclusion}
        a, b = metrics(before), metrics(after)
        numeric = ("network_load", "max_latency_ms", "deadline_misses", "signal_anomalies", "message_losses", "fault_effects")
        available = all(a[k] is not None and b[k] is not None for k in numeric)
        same_coverage = bool(a["coverage"]) and a["coverage"] == b["coverage"] and a["signal_ids"] == b["signal_ids"]
        reduced = available and any(b[k] < a[k] for k in numeric) and all(b[k] <= a[k] for k in numeric)
        # Measurement completeness and cause-explanation completeness are
        # separate contracts. A residual unexplained observation is not missing
        # measurement data and must not erase an independently measured gain.
        # Keep all actual data/model/window gaps blocking the comparison.
        comparison_gaps = [g for r in (before, after) for g in r.data_gaps
                           if g.get("blocking", True) and g.get("code") != "UNCONFIRMED_MECHANISM"]
        no_blocking_gaps = not comparison_gaps
        verified = same_experiment and same_coverage and complete_windows and no_blocking_gaps and reduced and before.simulation_run_id != after.simulation_run_id
        return {"before": a, "after": b, "before_reasoning_id": before_id, "after_reasoning_id": after_id,
                "comparable_scenario_seed_duration": same_experiment, "complete_matching_windows": complete_windows,
                "same_transport_and_signal_coverage": same_coverage, "all_metrics_available": available,
                "comparison_data_gaps": comparison_gaps,
                "cause_explanation_complete": {"before": before.completion_status == "COMPLETE", "after": after.completion_status in {"COMPLETE", "NO_ANOMALY_IN_WINDOW"}},
                "status": "IMPROVEMENT_VERIFIED_IN_WINDOW" if verified else "IMPROVEMENT_NOT_VERIFIED",
                "warning": "Belegt werden ausschließlich die verglichenen Messgrößen im geprüften Zeitfenster, keine vollständige Systemfehlerfreiheit. Ungeklärte Ursachen bleiben separat offen. Andere Faults/Seeds, unvollständige Fenster oder fehlende Messdaten verhindern den Nachweis."}

    def inspect(self, name, payload):
        request = ReasoningRequest.model_validate({k: v for k, v in payload.items() if k in ReasoningRequest.model_fields})
        events, window = TraceWindowResolver().resolve(request)
        validation = "PARTIAL" if window["next_cursor"] is not None else "VALIDATED"
        warnings = ["Begrenztes Zeitfenster; keine vollständige Laufanalyse."]
        refs = [{"id": f"{request.job_id}:TraceEvent:{event_id(e)}", "source_type": "TraceEvent", "timestamp": event_time(e)} for e in events[:50]]
        if name == "get_trace_events":
            data = {"events": events}
        elif name == "get_signal_series":
            data = {"samples": [{"time_s": event_time(e), **s} for e in events for s in signal_samples(e)
                if not payload.get("signal_id") or str(s.get("signal_id") or s.get("signal") or s.get("name")) == payload["signal_id"]][:2000]}
        elif name == "correlate_events":
            pairs = []
            for left, right in zip(events[:100], events[1:101]):
                shared = [r for r in object_refs(left) if r in object_refs(right)]
                pairs.append({"left": event_id(left), "right": event_id(right), "temporal_relation": correlate_time(event_time(left), event_time(right)),
                              "relation": "CORRELATED_ONLY", "shared_objects": shared, "causality_proven": False})
            data = {"pairs": pairs}
        elif name == "find_first_divergence":
            if not request.golden_job_id:
                raise ValueError("golden_job_id fehlt.")
            golden, gw = TraceWindowResolver().resolve(request.model_copy(update={"job_id": request.golden_job_id, "cursor": 0}))
            data = FirstDivergenceAnalyzer.analyze(events, golden)
            if gw["next_cursor"] is not None:
                window["next_cursor"] = window["next_cursor"] or 0
        else:
            context = self.context(request.job_id)
            result = EngineeringReasoningEngine().analyze(project_id=self.project_id, job_id=request.job_id, events=events, context=context, window=window)
            refs = [e.model_dump(mode="json") for e in result.evidence_refs]
            warnings.extend(g["message"] for g in result.data_gaps)
            if any(g.get("blocking", True) for g in result.data_gaps if g["code"] != "UNCONFIRMED_MECHANISM"):
                validation = "PARTIAL"
            if name == "get_fault_events":
                data = {"faults": context["faults"], "effects": [o.model_dump(mode="json") for o in result.observations if o.type in {"FAULT_ACTIVE", "MESSAGE_LOSS", "SIGNAL_ANOMALY"}]}
            elif name == "get_state_transitions":
                data = {"transitions": [o.model_dump(mode="json") for o in result.observations if o.type == "STATE_CHANGE"]}
            elif name in {"get_network_load", "get_timing_metrics", "get_route"}:
                source = {"get_network_load": "CapacityResult", "get_timing_metrics": "TimingResult", "get_route": "Route"}[name]
                data = {"items": [e.details for e in result.evidence_refs if e.source_type == source]}
            else:
                raise ValueError("Unbekanntes Reasoning-Werkzeug.")
        return {"data": data, "evidence_refs": refs, "time_range": window,
                "validation_status": "PARTIAL" if window["next_cursor"] is not None else validation,
                "affected_objects": [dict(pair) for pair in dict.fromkeys(tuple(sorted(obj.items())) for e in events for obj in object_refs(e))],
                "warnings": warnings}
