"""Evidence evaluation, independent of HTTP, databases, industries, and LLMs."""
from collections import defaultdict

from .contracts import (SimulationReasoningResult, EvidenceRef, Observation, Hypothesis,
                        CausalLink, ReasoningCompletionEvaluator)
from .correlation import number, event_time, event_id, object_refs, signal_samples, route_context, correlate_time

MAX_OBSERVATIONS = 1999


class EngineeringReasoningEngine:
    def analyze(self, *, project_id, job_id, events, context, goal="Ursache untersuchen", window=None, previous=None, comparison=None):
        if len(events) > 2000:
            raise ValueError("Reasoning verarbeitet höchstens 2000 Trace-Ereignisse pro Fenster.")
        result = SimulationReasoningResult(project_id=project_id, simulation_run_id=job_id,
            trace_session_id=context.get("trace_session_id") or job_id, goal=goal,
            lineage=context.get("lineage") or {}, time_range=window or {}, comparison=comparison)
        if previous:
            result.observations = list(previous.observations)
            result.evidence_refs = list(previous.evidence_refs)
            result.data_gaps = [g for g in previous.data_gaps if g["code"] not in {"INCOMPLETE_TRACE_WINDOW", "TRACE_EMPTY"}]
        observed = {o.id for o in result.observations}
        evidence = {e.id for e in result.evidence_refs}
        routes = context.get("routes") or []
        config = context.get("configuration") or {}
        route_configs = {str(r.get("id") or r.get("route_id")): r for r in config.get("communications") or config.get("routes") or []}
        gaps = {g["code"] for g in result.data_gaps}

        def gap(code, text, *, blocking=True):
            if code not in gaps:
                result.data_gaps.append({"code": code, "message": text, "blocking": blocking,
                    "next_measurement": "Trace-/Snapshot-Daten ergänzen und Analyse fortsetzen."})
                gaps.add(code)

        def ref(source, source_id, timestamp, objects=None, details=None):
            identifier = f"{job_id}:{source}:{source_id}"
            if identifier not in evidence and len(evidence) >= 1999:
                gap("EVIDENCE_BUDGET", "Evidenzlimit erreicht; Zeitfenster eingrenzen, bevor eine Ursache bestätigt werden kann.")
                identifier = f"{job_id}:DataGap:evidence-budget"
                source, source_id, objects, details = "DataGap", "evidence-budget", [], {"code": "EVIDENCE_BUDGET"}
            if identifier not in evidence:
                result.evidence_refs.append(EvidenceRef(id=identifier, source_type=source, source_id=str(source_id),
                    simulation_run_id=job_id, timestamp=timestamp, object_refs=objects or [], details=details or {}))
                evidence.add(identifier)
            return identifier

        def observe(kind, timestamp, text, refs, objects=None, metrics=None, suffix="", classification="OBSERVED_EFFECT"):
            identifier = f"{refs[0]}:{kind}:{suffix}"
            if identifier in observed:
                return next(o for o in result.observations if o.id == identifier)
            if len(result.observations) >= MAX_OBSERVATIONS:
                gap("OBSERVATION_BUDGET", f"Mehr als {MAX_OBSERVATIONS} Befunde: ein engeres Zeitfenster ist erforderlich.")
                return None
            observation = Observation(id=identifier, type=kind, timestamp=timestamp, description=text,
                evidence_refs=refs, affected_objects=objects or [], metrics=metrics or {}, classification=classification)
            observed.add(identifier)
            result.observations.append(observation)
            return observation

        ordered = sorted(events, key=event_time)
        signals = defaultdict(list)
        route_evidence = []
        inspected = {"route_inspected": bool(events) or bool(previous and previous.completion_checks.get("route_inspected")),
                     "timing_inspected": bool(events) or bool(previous and previous.completion_checks.get("timing_inspected")),
                     "capacity_inspected": bool(events) or bool(previous and previous.completion_checks.get("capacity_inspected")),
                     "faults_inspected": "faults" in context, "upstream_dependencies_inspected": True,
                     "downstream_effects_inspected": True, "snapshot_available": bool(context.get("snapshot_available"))}
        if not context.get("snapshot_available"):
            gap("MISSING_SIMULATION_SNAPSHOT", "Kein unveränderlicher Simulations-/Modell-Snapshot verfügbar.")
        if not events and not result.observations:
            gap("TRACE_EMPTY", "Im untersuchten Abschnitt wurden keine Trace-Ereignisse gefunden.")
        if context.get("data_gaps"):
            for item in context["data_gaps"]:
                gap(item["code"], item["message"], blocking=item.get("blocking", True))
        ref("SimulationRun", job_id, None, details={"status": context.get("job_status"), "scope": "BOUNDED_TRACE_WINDOW"})
        if context.get("snapshot_available"):
            ref("SimulationSnapshot", result.lineage.get("simulation_snapshot") or "provided-snapshot", None, details=result.lineage)

        prior_paths = {}
        for event in ordered:
            timestamp = event_time(event)
            objects = object_refs(event)
            eid = event_id(event)
            metrics = {key: event[key] for key in ("route_id", "route_ref", "network", "sequence", "scheduled_time_s",
                "queue_delay_ms", "queue_depth_estimate", "end_to_end_latency_ms", "transmission_latency_ms",
                "configured_latency_ms", "configured_cycle_ms", "injected_jitter_ms", "gateway_delay_ms", "status", "faults", "gateway_ids", "message_ids") if key in event}
            metrics["event_id"] = eid
            r = ref("TraceEvent", eid, timestamp, objects, metrics)
            if event.get("faults"):
                observe("FAULT_ACTIVE", timestamp, "Angewandte Fault-Marker im Ereignis; Ursache wird separat geprüft.", [r], objects, metrics, suffix="marker")
            path = route_context(event, routes)
            # A message traverses multiple physical segments. Compare the same
            # segment across transmissions, not successive gateway hops.
            transport_key = (event.get("route_id"), event.get("segment_id", event.get("segment_index")),
                             tuple(sorted(event.get("message_ids") or [])))
            path_key = (path["source_interface"], path["network"], tuple(sorted(path["destination_interfaces"])))
            if event.get("route_id") is not None and transport_key in prior_paths and prior_paths[transport_key][0] != path_key:
                observe("ROUTE_CHANGE", timestamp, "Physischer Pfad desselben Transports hat sich geändert.", [prior_paths[transport_key][1], r], objects, metrics)
            prior_paths[transport_key] = (path_key, r)
            if path not in route_evidence:
                route_evidence.append(path)
                ref("Route", str(path["route_id"]), timestamp, objects, path)
            if not path["complete"]:
                gap("MISSING_ROUTE_DATA", "Quell-/Zielknoten, physische Interfaces oder Netzreferenz fehlen im Trace.")
                inspected["route_inspected"] = False
            if path["logical_address"] is None:
                gap("MISSING_LOGICAL_ADDRESS", "Keine logische Quelladresse im betrachteten Lauf dokumentiert.", blocking=False)
            rc = route_configs.get(str(event.get("route_id")), {})
            timing = rc.get("timing") or {}
            deadline = number(event.get("deadline_ms"), number(timing.get("deadline_ms"), number(rc.get("deadline_ms"))))
            latency = number(event.get("end_to_end_latency_ms"))
            if deadline is not None:
                metrics["deadline_ms"] = deadline
            if latency is not None and deadline is not None and latency > deadline:
                observe("DEADLINE_MISS", timestamp, f"Latenz {latency:g} ms überschreitet Deadline {deadline:g} ms.", [r], objects, metrics)
            if latency is None or deadline is None:
                gap("MISSING_TIMING_MODEL", "Deadline oder gemessene Ende-zu-Ende-Latenz fehlen für mindestens eine Route.", blocking=False)
            if number(event.get("queue_delay_ms"), 0) > 0 or number(event.get("queue_depth_estimate"), 0) > 0:
                observe("QUEUE_GROWTH", timestamp, "Warteschlangenbeitrag im Trace gemessen.", [r], objects, metrics)
            if number(event.get("configured_latency_ms"), 0) > 0:
                observe("MESSAGE_DELAY", timestamp, "Zusätzlicher Latenzbeitrag im Simulationslauf.", [r], objects, metrics)
            if number(event.get("gateway_delay_ms"), 0) > 0 or "GATEWAY_DELAY" in (event.get("faults") or []):
                observe("GATEWAY_DELAY", timestamp, "Gateway-Verzögerung im Trace belegt.", [r], objects, metrics)
            if number(event.get("injected_jitter_ms"), 0) > 0 or number(event.get("jitter_ms"), 0) > number(timing.get("jitter_ms"), float("inf")):
                observe("TIMING_JITTER", timestamp, "Jitter-Injektion oder Überschreitung des Jitter-Budgets.", [r], objects, metrics)
            status = str(event.get("status") or "").lower()
            if status in {"dropped", "lost", "timeout"}:
                observe("MESSAGE_LOSS", timestamp, "Nachricht wurde nicht zugestellt.", [r], objects, metrics)
            if status in {"corrupted", "invalid_payload"}:
                observe("PAYLOAD_ERROR", timestamp, "Ungültige oder korrumpierte Nutzlast.", [r], objects, metrics)
            if status in {"offline", "bus_off"} or any(f in {"BUS_OFF", "LINK_DOWN", "GATEWAY_DROP"} for f in event.get("faults") or []):
                observe("NODE_OFFLINE", timestamp, "Kommunikationsausfall am betroffenen Pfad.", [r], objects, metrics)
            for sample in signal_samples(event):
                sid = str(sample.get("signal_id") or sample.get("signal") or sample.get("name") or "unknown")
                value = number(sample.get("actual_value", sample.get("value")))
                golden = number(sample.get("golden_value"))
                sample_metrics = {key: sample[key] for key in ("signal_id", "signal", "value", "actual_value", "golden_value", "minimum", "maximum", "state", "quality", "faults", "source_dependencies") if key in sample}
                sample_metrics.update(event_id=eid, route_id=event.get("route_id"), network=event.get("network"), subtype="")
                sr = ref("SignalSeries", f"{eid}:{sid}", timestamp, [{"object_type": "Signal", "id": sid}], sample_metrics)
                samples = signals[sid]
                reasons = []
                if value is None:
                    reasons.append("DROPOUT")
                if value is not None and (value < number(sample.get("minimum"), -float("inf")) or value > number(sample.get("maximum"), float("inf"))):
                    reasons.append("OUT_OF_RANGE")
                quality = str(sample.get("quality") or "").upper()
                if quality and quality not in {"GOOD", "VALID", "OK", "NORMAL", "NOMINAL"}:
                    reasons.append("INVALID_QUALITY")
                if sample.get("dependency_valid") is False:
                    reasons.append("DEPENDENCY_MISMATCH")
                if sample.get("state_valid") is False:
                    reasons.append("UNEXPECTED_STATE")
                if value is not None and golden is not None and abs(value-golden) > number(sample.get("noise_limit"), float("inf")):
                    reasons.append("NOISE_BURST")
                if samples:
                    before_t, before, before_ref = samples[-1]
                    before_value = number(before.get("actual_value", before.get("value")))
                    if value is not None and before_value is not None and timestamp > before_t and abs(value-before_value)/(timestamp-before_t) > number(sample.get("max_rate_per_s"), float("inf")):
                        reasons.append("RATE_OF_CHANGE")
                    if sample.get("state") != before.get("state") and sample.get("state") is not None:
                        transitions = (context.get("state_models") or {}).get(sid, {}).get("transitions")
                        valid = None if transitions is None else any(t.get("from") == before.get("state") and t.get("to") == sample.get("state") for t in transitions)
                        observe("STATE_CHANGE", timestamp, f"Zustand {before.get('state')} → {sample.get('state')}", [before_ref, sr], [{"object_type": "Signal", "id": sid}, *objects],
                                {**sample_metrics, "transition_valid": valid}, suffix=sid)
                        if valid is False:
                            reasons.append("UNEXPECTED_STATE")
                        elif valid is None:
                            gap("MISSING_STATE_MODEL", "Beobachteter Zustandswechsel ohne prüfbares Übergangsmodell.", blocking=False)
                if len(samples) >= 2 and value is not None and golden is not None:
                    previous_values = [number(s[1].get("actual_value", s[1].get("value"))) for s in samples[-2:]]
                    if all(v == value for v in previous_values) and any(number(s[1].get("golden_value")) != golden for s in samples[-2:]):
                        reasons.append("STUCK_VALUE")
                for reason in reasons:
                    observe("SIGNAL_ANOMALY", timestamp, f"{sid}: {reason}", [sr, r], [{"object_type": "Signal", "id": sid}, *objects],
                            {**sample_metrics, "subtype": reason}, suffix=f"{sid}:{reason}")
                samples.append((timestamp, sample, sr))

        # Reuse the canonical runtime calculator, constrained to this window.
        if ordered:
            from ..agent_tools.analysis import analyze
            window_start = number(result.time_range.get("start_s"), 0)
            configured_end = number(config.get("duration_s"), max(.01, event_time(ordered[-1])))
            window_end = min(number(result.time_range.get("end_s"), configured_end), configured_end)
            metric_config = {**config, "duration_s": max(.001, window_end-window_start, event_time(ordered[-1])-window_start)}
            normalized = [{**e, "time_s": event_time(e)-window_start} for e in ordered]
            runtime = analyze({"events": normalized, "configuration": metric_config})
            coverage = defaultdict(int)
            for event in ordered:
                for transport in event.get("message_ids") or [event.get("route_id") or "unknown"]:
                    coverage[str(transport)] += 1
            ref("TraceMetrics", "window", event_time(ordered[-1]), details={
                "transport_event_counts": dict(coverage), "event_count": len(ordered),
                "max_latency_ms": max((number(e.get("end_to_end_latency_ms"), 0) for e in ordered), default=0),
                "latency_available": all(number(e.get("end_to_end_latency_ms")) is not None for e in ordered),
                "signal_ids": sorted(signals), "page_only": bool(previous)})
            page_key = event_id(ordered[0]) + ":" + event_id(ordered[-1])
            cr = ref("CapacityResult", page_key, event_time(ordered[-1]), details={"scope": "WINDOW_PAGE_ONLY", "networks": runtime.get("networks") or [], "event_count": len(ordered)})
            ref("TimingResult", page_key, event_time(ordered[-1]), details={"scope": "WINDOW_PAGE_ONLY", "routes": (runtime.get("routes") or [])[:100]})
            if previous:
                gap("PAGINATED_AGGREGATION", "Netzlast- und Signalverlauf über Seitengrenzen sind nicht vollständig aggregiert. Für Ursachenbestätigung ein engeres, vollständig lesbares Zeitfenster wählen.")
            for network in runtime.get("networks") or []:
                load = number(network.get("peak_load_percent"), number(network.get("average_load_percent"), 0))
                if load > number(config.get("warning_threshold"), 60):
                    observe("BUS_LOAD_CHANGE", event_time(ordered[-1]), f"Netzlast im beobachteten Fenster: {load:g} %.", [cr],
                        [{"object_type": "Network", "id": str(network["network_id"])}], {"network": network["network_id"], "load_percent": load}, suffix=str(network["network_id"]))
            interface_runtime = analyze({"events": [{**e, "network": e.get("sender_interface") or "unknown-interface"} for e in normalized], "configuration": metric_config})
            for interface in interface_runtime.get("networks") or []:
                load = number(interface.get("peak_load_percent"), 0)
                ir = ref("HardwareInterface", interface["network_id"], event_time(ordered[-1]), details={**interface, "scope": "WINDOW_ONLY"})
                if load > number(config.get("warning_threshold"), 60):
                    observe("INTERFACE_LOAD_CHANGE", event_time(ordered[-1]), f"Quellinterface-Last im Fenster: {load:g} %.", [ir],
                            [{"object_type": "HardwareInterface", "id": interface["network_id"]}], {"load_percent": load}, suffix=interface["network_id"])

        # Ground truth is configured injection + matching time/target + applied marker + observed effect.
        effects = [o for o in result.observations if o.type not in {"FAULT_ACTIVE", "BUS_LOAD_CHANGE", "INTERFACE_LOAD_CHANGE"}]
        fault_effect_types = {
            "GATEWAY_DROP": {"NODE_OFFLINE", "MESSAGE_LOSS"}, "BUS_OFF": {"NODE_OFFLINE", "MESSAGE_LOSS"},
            "LINK_DOWN": {"NODE_OFFLINE", "MESSAGE_LOSS"}, "TEMPORARY_DISCONNECT": {"NODE_OFFLINE", "MESSAGE_LOSS"},
            "MESSAGE_LOSS": {"MESSAGE_LOSS"}, "MESSAGE_TIMEOUT": {"MESSAGE_LOSS"}, "ROUTING_FAILURE": {"MESSAGE_LOSS"},
            "MESSAGE_CORRUPTION": {"PAYLOAD_ERROR", "SIGNAL_ANOMALY"}, "FRAME_ERROR": {"PAYLOAD_ERROR", "MESSAGE_LOSS"},
            "MESSAGE_DELAY": {"MESSAGE_DELAY", "DEADLINE_MISS"}, "GATEWAY_DELAY": {"GATEWAY_DELAY", "DEADLINE_MISS"},
            "MESSAGE_JITTER": {"TIMING_JITTER", "DEADLINE_MISS"}, "MESSAGE_WRONG_CYCLE": {"TIMING_JITTER", "DEADLINE_MISS"},
            "NETWORK_OVERLOAD": {"QUEUE_GROWTH", "DEADLINE_MISS"}, "CONGESTION": {"QUEUE_GROWTH", "DEADLINE_MISS"},
            "QUEUE_OVERFLOW": {"QUEUE_GROWTH", "MESSAGE_LOSS"}, "BURST_TRAFFIC": {"QUEUE_GROWTH", "DEADLINE_MISS"},
        }
        for index, fault in enumerate(context.get("faults") or []):
            if not fault.get("enabled", True):
                continue
            kind = str(fault.get("type") or "")
            start, end = number(fault.get("start_s"), 0), number(fault.get("end_s"), float("inf"))
            target = fault.get("target") or {}
            target_id = str(target.get("id") or target.get("signal_id") or target.get("name") or "")
            fr = ref("FaultEvent", str(fault.get("id") or index), start, details={"type": kind, "target": target,
                "start_s": start, "end_s": end if end != float("inf") else None, "source": "SIMULATION_SCENARIO"})
            matches, contradictions = [], []
            for effect in effects:
                compatible = {"SIGNAL_ANOMALY"} if kind.startswith("SIGNAL_") else fault_effect_types.get(kind, set())
                if effect.type not in compatible:
                    continue
                refs = {r["id"] for r in effect.affected_objects}
                refs.update(str(effect.metrics.get(k) or "") for k in ("signal", "signal_id", "route_id", "network"))
                if target_id and target_id not in refs:
                    continue
                observed_time = number(effect.metrics.get("scheduled_time_s"), effect.timestamp)
                markers = effect.metrics.get("faults") or []
                if kind in markers and start <= observed_time <= end:
                    matches.append(effect)
                elif not start <= observed_time <= end:
                    contradictions.extend(effect.evidence_refs)
            hid = f"fault:{index}:{kind}"
            supported = bool(matches) and context.get("trusted_simulation", False)
            result.hypotheses.append(Hypothesis(id=hid, description=f"Injizierter Fehler {kind} verursacht die beobachtete Wirkung.",
                status="SUPPORTED" if supported else "REJECTED" if contradictions else "BLOCKED_BY_DATA_GAP",
                evidence_refs=[fr, *dict.fromkeys(r for e in matches for r in e.evidence_refs)], contradicting_evidence=list(dict.fromkeys(contradictions)),
                reason="Aktives Injektionsfenster, Zielobjekt, angewandter Fault-Marker und Wirkung stimmen überein." if supported else "Kein passender angewandter Fault mit Wirkung im aktiven Zeit-/Objektkontext nachgewiesen.", confidence=.98 if supported else 0))
            if supported:
                result.confirmed_causes.append(hid)
                cause = observe("FAULT_ACTIVE", start, f"Bekannte Injektion: {kind}", [fr], metrics={"fault_type": kind}, suffix=str(index), classification="INJECTED_CAUSE")
                for effect in matches[:30]:
                    if cause and effect.timestamp >= start:
                        result.causal_chain.append(CausalLink(cause=cause.id, relation="INJECTED_CAUSE", effect=effect.id,
                            timestamp=effect.timestamp, evidence_refs=[fr, *effect.evidence_refs], confidence=.98))
                result.findings.append({"code": "FAULT_EFFECT_CHAIN", "evidence_refs": [fr], "hypothesis_id": hid})

        for effect in [o for o in result.observations if o.type == "DEADLINE_MISS"][:100]:
            latency, deadline = number(effect.metrics.get("end_to_end_latency_ms")), number(effect.metrics.get("deadline_ms"))
            queue = number(effect.metrics.get("queue_delay_ms"))
            known = latency is not None and deadline is not None and queue is not None
            supported = known and 0 < queue <= latency and latency-queue <= deadline
            status = "SUPPORTED" if supported else "REJECTED" if known and queue == 0 else "PARTIALLY_SUPPORTED" if known else "BLOCKED_BY_DATA_GAP"
            hid = "queue:" + effect.id
            result.hypotheses.append(Hypothesis(id=hid, description="Warteschlangenverzögerung ist ausschlaggebend für die Deadline-Verletzung.", status=status,
                evidence_refs=effect.evidence_refs, contradicting_evidence=effect.evidence_refs if status == "REJECTED" else [],
                reason="Gemessene Latenz ohne Queue-Anteil läge innerhalb der Deadline." if supported else "Queue-Anteil fehlt, ist null oder erklärt die Überschreitung nicht allein.", confidence=.9 if supported else .3 if known else 0))
            if supported:
                result.confirmed_causes.append(hid)
                queue_observation = next((o for o in result.observations if o.type == "QUEUE_GROWTH" and o.metrics.get("event_id") == effect.metrics.get("event_id")), None)
                if queue_observation:
                    result.causal_chain.append(CausalLink(cause=queue_observation.id, relation="VALIDATED_LATENCY_COMPONENT", effect=effect.id,
                        timestamp=effect.timestamp, evidence_refs=effect.evidence_refs, confidence=.9))
                result.findings.append({"code": "TIMING_CAUSAL_CHAIN", "evidence_refs": effect.evidence_refs})
            loads = [o for o in result.observations if o.type == "BUS_LOAD_CHANGE" and o.metrics.get("network") == effect.metrics.get("network")]
            if loads:
                result.hypotheses.append(Hypothesis(id="load:"+effect.id, description="Hohe Netzlast erklärt den Queue-Anstieg.",
                    status="PARTIALLY_SUPPORTED", evidence_refs=[*loads[0].evidence_refs, *effect.evidence_refs],
                    reason="Gemeinsamer physischer Pfad; aggregierte Last belegt noch keine zeitlich gerichtete Verursachung.", confidence=.4))
                result.causal_chain.append(CausalLink(cause=loads[0].id, relation="CORRELATED_ONLY", effect=effect.id,
                    timestamp=effect.timestamp, evidence_refs=[*loads[0].evidence_refs, *effect.evidence_refs], confidence=.4))

        # Independently recompute transport-input models against source packets
        # and the frozen model; trace annotations alone never prove a cascade.
        from .dependencies import validate_dependency_effect
        events_by_id = {event_id(e): e for e in ordered}
        validated_dependencies = []
        if context.get("snapshot_available") and context.get("trusted_simulation"):
            for event in ordered:
                for sample in signal_samples(event):
                    if not sample.get("dependency_evidence"):
                        continue
                    checked = validate_dependency_effect(sample, event, events_by_id, config)
                    if not checked:
                        continue
                    sid = str(sample["signal_id"])
                    matches = [o for o in result.observations if o.type == "SIGNAL_ANOMALY" and o.metrics.get("event_id") == event_id(event) and o.metrics.get("signal_id") == sid]
                    if not matches:
                        continue
                    effect = matches[0]
                    refs = [ref("TraceEvent", event_id(e), event_time(e), object_refs(e), {"status": e["status"], "route_id": e["route_id"], "signals": e.get("signals", [])}) for e in checked["source_events"]]
                    dr = ref("DependencyModel", f"{event_id(event)}:{sid}", event_time(event), [{"object_type": "Signal", "id": sid}], {k: v for k, v in checked.items() if k != "source_events"})
                    evidence_refs = list(dict.fromkeys([*refs, dr, *effect.evidence_refs]))
                    hid = f"dependency:{event_id(event)}:{sid}"
                    result.hypotheses.append(Hypothesis(id=hid, description="Zugestellte bzw. veraltete Eingangswerte verursachen die berechnete Folgeabweichung.", status="SUPPORTED", evidence_refs=evidence_refs, reason="Sample-Herkunft, Empfang vor Auswertung, Eingangsregel und Formel wurden gegen den Snapshot nachgerechnet.", confidence=.95))
                    result.confirmed_causes.append(hid)
                    result.causal_chain.append(CausalLink(cause=refs[0], relation="VALIDATED_TRANSPORT_DEPENDENCY", effect=effect.id, timestamp=effect.timestamp, evidence_refs=evidence_refs, confidence=.95))
                    dependency = {"source_signals": checked["source_signals"], "destination_signal": sid, "timestamp": effect.timestamp, "classification": "VALIDATED_SECONDARY_EFFECT", "causality_proven": True, "evidence_refs": evidence_refs}
                    result.downstream_effects.append(dependency)
                    validated_dependencies.append(dependency)
            if validated_dependencies:
                result.findings.append({"code": "VALIDATED_DEPENDENCY_CHAIN", "count": len(validated_dependencies)})
            if any(left["destination_signal"] in right["source_signals"] and left["timestamp"] <= right["timestamp"] for left in validated_dependencies for right in validated_dependencies):
                result.findings.append({"code": "CASCADE_FAILURE", "basis": "CONNECTED_RECOMPUTED_TRANSPORT_DEPENDENCIES"})

        # Unvalidated explicit dependencies remain candidates.
        for sid, samples in signals.items():
            for timestamp, sample, sr in samples:
                dependencies = sample.get("source_dependencies") or (context.get("dependencies") or {}).get(sid) or []
                for dependency in dependencies:
                    source = str(dependency.get("signal_id") or dependency.get("source") or "") if isinstance(dependency, dict) else str(dependency)
                    upstream = [o for o in result.observations if o.type == "SIGNAL_ANOMALY" and any(r["id"] == source for r in o.affected_objects) and o.timestamp <= timestamp]
                    downstream = [o for o in result.observations if o.type in {"SIGNAL_ANOMALY", "STATE_CHANGE"} and any(r["id"] == sid for r in o.affected_objects) and o.timestamp == timestamp]
                    if upstream and downstream:
                        result.downstream_effects.append({"source_signal": source, "destination_signal": sid, "timestamp": timestamp,
                            "classification": "SECONDARY_EFFECT_CANDIDATE", "evidence_refs": [*upstream[0].evidence_refs, sr],
                            "relation": "EXPLICIT_DEPENDENCY", "causality_proven": False})
        result.downstream_effects = result.downstream_effects[:100]
        if comparison and comparison.get("first_divergence"):
            first = comparison["first_divergence"]
            gr = ref("GoldenTraceComparison", "first-divergence", first["timestamp"], details=first)
            observe("GOLDEN_TRACE_DEVIATION", first["timestamp"], "Erste zugeordnete Abweichung vom Referenzlauf.", [gr])
            result.findings.append({"code": "GOLDEN_TRACE_ROOT_DEVIATION", "evidence_refs": [gr], "root_cause_confirmed": False})
        if not result.hypotheses and result.observations:
            result.hypotheses.append(Hypothesis(id="unconfirmed", description="Ursache der beobachteten Abweichung.", status="BLOCKED_BY_DATA_GAP",
                evidence_refs=result.observations[0].evidence_refs, reason="Kein validierter Wirkmechanismus belegt; gezielte weitere Messung nötig.", confidence=0))
        result.tested_hypotheses = [h.id for h in result.hypotheses if h.status not in {"OPEN", "TESTING"}]
        result.rejected_hypotheses = [h.id for h in result.hypotheses if h.status == "REJECTED"]
        result.alternatives = [h.id for h in result.hypotheses if h.id not in result.confirmed_causes]
        if result.time_range.get("next_cursor") is not None:
            result.continuation = {"cursor": result.time_range["next_cursor"], "start_s": result.time_range.get("start_s", 0), "end_s": result.time_range.get("end_s", 1e15)}
            gap("INCOMPLETE_TRACE_WINDOW", "Das Trace-Zeitfenster ist noch nicht vollständig gelesen; weitere begrenzte Abfrage erforderlich.")
        if result.observations and not result.confirmed_causes:
            gap("UNCONFIRMED_MECHANISM", "Zeitliche Nähe und Auffälligkeiten reichen für eine Ursachenbestätigung nicht aus.")
        elif result.confirmed_causes:
            result.data_gaps = [g for g in result.data_gaps if g["code"] != "UNCONFIRMED_MECHANISM"]
        result.evidence_plan = [{"tool": tool, "status": "CHECKED" if inspected[key] else "DATA_GAP"} for tool, key in (
            ("get_route", "route_inspected"), ("get_timing_metrics", "timing_inspected"), ("get_network_load", "capacity_inspected"),
            ("get_fault_events", "faults_inspected"), ("get_signal_series", "upstream_dependencies_inspected"), ("get_state_transitions", "downstream_effects_inspected"))]
        result = ReasoningCompletionEvaluator.evaluate(result, inspected)
        confirmed = result.completion_status == "COMPLETE"
        if confirmed and result.comparison:
            for deviation in result.comparison.get("ordered_divergences") or []:
                related = [o for o in result.observations if o.metrics.get("event_id") == deviation.get("actual_event_id")]
                links = [link for link in result.causal_chain if link.relation in {"INJECTED_CAUSE", "VALIDATED_LATENCY_COMPONENT"} and any(o.id == link.effect for o in related)]
                if links:
                    result.comparison["first_credible_causal_deviation"] = {**deviation, "causality_proven": True,
                        "evidence_refs": list(dict.fromkeys(r for link in links for r in link.evidence_refs)),
                        "basis": "INDEPENDENTLY_VALIDATED_MECHANISM_NOT_DIVERGENCE_ALONE"}
                    break
        result.conclusion = ("ROOT_CAUSE_IDENTIFIED: " + "; ".join(h.description for h in result.hypotheses if h.id in result.confirmed_causes)) if confirmed else "ROOT_CAUSE_UNCONFIRMED: " + ("Keine Anomalie im untersuchten Fenster." if not result.observations else "Die Analyse benötigt weitere Evidenz; siehe Datenlücken und Hypothesen.")
        if not confirmed:
            result.confirmed_causes = []
        result.findings.insert(0, {"code": "ROOT_CAUSE_IDENTIFIED" if confirmed else "ROOT_CAUSE_UNCONFIRMED",
            "severity": "WARNING" if result.observations else "INFO", "reasoning_id": result.reasoning_id,
            "evidence_refs": list(dict.fromkeys(r for h in result.hypotheses for r in h.evidence_refs))[:50]})
        if any(o.type == "BUS_LOAD_CHANGE" for o in result.observations):
            result.recommended_actions.append({"id": "capacity-repair", "type": "ADD_CHANNEL", "description": "Physische Netzverteilung mit dem vorhandenen Kapazitätsplaner prüfen.", "requires_review": True, "proposal_supported": True})
        result.recommended_actions.append({"id": "measurement", "type": "NEXT_MEASUREMENT", "description": "Fehlende Daten ergänzen; dasselbe Zeitfenster unter vergleichbaren Bedingungen erneut prüfen.", "requires_review": False, "proposal_supported": False})
        if any(o.type == "FAULT_ACTIVE" for o in result.observations):
            result.recommended_actions.append({"id": "fault-handling", "type": "CHANGE_FAULT_HANDLING", "description": "Fehlerbehandlung/Redundanz im betroffenen Pfad prüfen. Das Abschalten der Injektion allein ist kein Reparaturnachweis.", "requires_review": True, "proposal_supported": False})
        # Keep bounded evidence only; no raw event arrays or model text are persisted.
        referenced = {r for o in result.observations for r in o.evidence_refs} | {r for h in result.hypotheses for r in h.evidence_refs}
        referenced.update(r for link in result.causal_chain for r in link.evidence_refs)
        referenced.update(r for hypothesis in result.hypotheses for r in hypothesis.contradicting_evidence)
        referenced.update(r for effect in result.downstream_effects for r in effect["evidence_refs"])
        result.evidence_refs = [e for e in result.evidence_refs if e.id in referenced or e.source_type in {"Route", "CapacityResult", "TimingResult", "TraceMetrics", "SimulationRun", "SimulationSnapshot"}]
        result.observations.sort(key=lambda o: (o.timestamp, o.id))
        return result
