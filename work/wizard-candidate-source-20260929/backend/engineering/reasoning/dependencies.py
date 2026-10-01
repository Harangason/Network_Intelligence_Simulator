"""Recompute explicit sampled-input effects from immutable model + trace evidence."""
import math


def validate_dependency_effect(sample, event, events_by_id, configuration):
    try:
        return _validate_dependency_effect(sample, event, events_by_id, configuration)
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        # Imported/malformed evidence cannot become a confirmed mechanism or
        # crash the entire analysis. It remains an unconfirmed candidate.
        return None


def _validate_dependency_effect(sample, event, events_by_id, configuration):
    from backend.simulator.model_based_simulation import FormulaEvaluator, SignalDefinition
    model = configuration.get("engineering_model") or {}
    raw = next((s for s in model.get("signals", []) if str(s.get("id")) == str(sample.get("signal_id"))), None)
    if not raw:
        return None
    behavior = next((b for b in model.get("behaviors", []) if str(b.get("signal_id")) == str(raw["id"])), None)
    definition = SignalDefinition.from_record({**raw, **({"behavior": behavior} if behavior else {})})
    policy = definition.parameters.get("transport_inputs")
    evidence = sample.get("dependency_evidence") or {}
    inputs = evidence.get("inputs") or []
    if not policy or len(inputs) != len(policy) or {i.get("name") for i in inputs} != set(policy):
        return None
    now = float(event["scheduled_time_s"])
    actual, nominal, source_events = {}, {}, []
    impaired = False
    for item in inputs:
        rule = policy[item["name"]]
        sid = rule["signal_id"]
        if sid != item.get("signal_id") or rule != item.get("policy"):
            return None
        source = events_by_id.get(item.get("source_event_id"))
        attempted = events_by_id.get(item.get("last_attempt_event_id"))
        fallback = float(rule.get("fallback", 0))
        if source:
            receiver = next((p for p in source.get("rx_ports", []) if p["hardware_id"] == event["sender_hardware"]), None)
            received_at = float(receiver["end_s"] if receiver else source["time_s"])
            status = receiver["status"] if receiver else source["status"]
            if status != "transmitted" or received_at > now + 1e-9 or event["sender_hardware"] not in source["receiver_hardware"]:
                return None
            upstream = next((s for s in source.get("signals", []) if s["signal_id"] == sid), None)
            if not upstream:
                return None
            age = (now - float(source["scheduled_time_s"])) * 1000
            stale = age > float(rule.get("max_age_ms", 100))
            value = float(upstream.get("received_value", upstream["value"])) if not stale or rule.get("on_stale", "hold") == "hold" else fallback
            impaired |= stale or bool(upstream.get("faults")) or upstream.get("quality") == "STALE_INPUT"
            source_events.append(source)
        else:
            # Missing history is not evidence that an input did not exist.
            if not attempted or attempted.get("status") not in {"dropped", "corrupted"}:
                return None
            value, stale = fallback, True
            impaired = True
        if attempted:
            if float(attempted["time_s"]) > now + 1e-9 or event["sender_hardware"] not in attempted["receiver_hardware"]:
                return None
            source_events.append(attempted)
        candidates = [(float(e["scheduled_time_s"]), s.get("golden_value")) for e in events_by_id.values()
            if float(e["scheduled_time_s"]) <= now for s in e.get("signals", []) if s["signal_id"] == sid]
        if not candidates:
            return None
        expected = max(candidates, key=lambda pair: pair[0])[1]
        if expected is None or not math.isclose(value, float(item["value"]), abs_tol=1e-9) or not math.isclose(float(expected), float(item["reference_value"]), abs_tol=1e-9):
            return None
        actual[item["name"]], nominal[item["name"]] = value, float(expected)
    formula = str(definition.parameters.get("formula"))
    def evaluate(values):
        value = FormulaEvaluator.evaluate(formula, {"t": now, **values})
        return max(definition.minimum, min(definition.maximum, round(value / definition.resolution) * definition.resolution))
    computed, reference = evaluate(actual), evaluate(nominal)
    if not impaired or math.isclose(computed, reference) or sample.get("faults") or not math.isclose(computed, float(sample["value"]), abs_tol=1e-9):
        return None
    return {"source_events": list({e["event_id"]: e for e in source_events}.values()),
        "source_signals": [i["signal_id"] for i in inputs], "destination_signal": sample["signal_id"],
        "evaluation_s": now, "formula": formula, "computed_output": computed, "reference_output": reference}
