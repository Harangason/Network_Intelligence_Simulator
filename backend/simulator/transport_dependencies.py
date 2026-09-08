"""Explicit sampled-input function models over actually delivered trace events.

Input policies are opt-in model parameters, never inferred from signal names.
The pass runs in release-time order and exposes each consumed sample and loss.
"""
import heapq
import math
from model_based_simulation import FormulaEvaluator


def apply_transport_dependencies(events, engine):
    definitions = {s.id: s for s in engine.signals}
    models = {sid: s for sid, s in definitions.items() if s.parameters.get("transport_inputs")}
    if not models:
        return
    for signal in models.values():
        spec = signal.parameters["transport_inputs"]
        if not isinstance(spec, dict) or len(spec) > 32 or not signal.parameters.get("formula"):
            raise ValueError(f"{signal.id}: transport_inputs requires <=32 named inputs and an explicit formula")
        for name, policy in spec.items():
            if not name.isidentifier() or policy.get("signal_id") not in definitions:
                raise ValueError(f"{signal.id}: unknown transport input {name}")
            if policy.get("on_stale", "hold") not in {"hold", "fallback"}:
                raise ValueError("on_stale must be hold or fallback")
            if not math.isfinite(float(policy.get("max_age_ms", 100))) or float(policy.get("max_age_ms", 100)) < 0:
                raise ValueError("max_age_ms must be finite and nonnegative")
    inbox, attempts, nominal = {}, {}, {}
    pending = []
    rank = {s.id: i for i, s in enumerate(engine.derived.order(engine.signals))}
    ordered = sorted(events, key=lambda e: (float(e["scheduled_time_s"]), min((rank.get(s["signal_id"], 0) for s in e.get("signals", [])), default=0), e["route_id"]))
    serial = 0
    for event in ordered:
        now = float(event["scheduled_time_s"])
        while pending and pending[0][0] <= now:
            _, _, receiver, record = heapq.heappop(pending)
            key = (receiver, record["signal_id"])
            attempts[key] = record
            if record["status"] == "transmitted":
                inbox[key] = record
        changed = False
        for sample in event.get("signals", []):
            signal = models.get(sample["signal_id"])
            if signal:
                inputs, actual, golden = [], {}, {}
                for name, policy in signal.parameters["transport_inputs"].items():
                    sid = policy["signal_id"]
                    key = (event["sender_hardware"], sid)
                    received, attempted = inbox.get(key), attempts.get(key)
                    fallback = float(policy.get("fallback", 0))
                    age = (now - received["published_s"]) * 1000 if received else None
                    stale = received is None or age > float(policy.get("max_age_ms", 100))
                    value = received["value"] if received and (not stale or policy.get("on_stale", "hold") == "hold") else fallback
                    expected = nominal.get(sid, fallback)
                    actual[name], golden[name] = float(value), float(expected)
                    inputs.append({"name": name, "signal_id": sid, "value": value, "reference_value": expected,
                        "source_event_id": received["event_id"] if received else None,
                        "source_publish_s": received["published_s"] if received else None,
                        "source_receive_s": received["received_s"] if received else None,
                        "last_attempt_event_id": attempted["event_id"] if attempted else None,
                        "last_attempt_status": attempted["status"] if attempted else None,
                        "upstream_faults": (attempted or received or {}).get("faults", []),
                        "age_ms": age, "stale": stale, "policy": dict(policy)})
                formula = str(signal.parameters["formula"])
                actual_value = FormulaEvaluator.evaluate(formula, {"t": now, **actual})
                reference = FormulaEvaluator.evaluate(formula, {"t": now, **golden})
                actual_value = engine.behavior.apply_limits(signal, engine.behavior.apply_resolution(signal, actual_value))
                reference = engine.behavior.apply_limits(signal, engine.behavior.apply_resolution(signal, reference))
                value, faults = engine.faults.signal_value(signal, now, actual_value, engine.behavior)
                impaired = any(i["stale"] or i["upstream_faults"] for i in inputs)
                sample.update(value=value, actual_value=value, golden_value=reference,
                    quality="STALE_INPUT" if impaired else "GOOD", faults=faults,
                    source_dependencies=[i["signal_id"] for i in inputs],
                    dependency_valid=not impaired,
                    dependency_evidence={"model": "SAMPLED_TRANSPORT_INPUT_V1", "formula": formula,
                        "evaluation_s": now, "inputs": inputs, "unfaulted_output": actual_value,
                        "reference_output": reference, "input_effect_observed": impaired and actual_value != reference})
                changed = True
            nominal[sample["signal_id"]] = sample.get("golden_value", sample.get("value"))
        if changed:
            encoded = [(definitions[s["signal_id"]], s.get("value")) for s in event["signals"] if s["signal_id"] in definitions]
            event["payload_hex"] = engine.codec.encode(encoded, int(event["payload_bytes"]))
            for sample in event["signals"]:
                if sample["signal_id"] in definitions:
                    sample["received_value"] = engine.codec.decode(event["payload_hex"], definitions[sample["signal_id"]])
            event.update(value=event["signals"][0]["value"], signal_value=event["signals"][0]["value"], golden_value=event["signals"][0]["golden_value"])
            if event["status"] == "corrupted" and event["payload_hex"]:
                event["payload_hex"] = "FF" + event["payload_hex"][2:]
        for receiver in event["receiver_hardware"]:
            rx = next((p for p in event.get("rx_ports", []) if p["hardware_id"] == receiver), None)
            received_s = float(rx["end_s"] if rx else event["time_s"])
            status = rx["status"] if rx else event["status"]
            for sample in event.get("signals", []):
                if sample.get("value") is None:
                    continue
                serial += 1
                record = {"signal_id": sample["signal_id"], "value": sample.get("received_value", sample["value"]),
                    "published_s": now, "received_s": received_s, "event_id": event["event_id"],
                    "status": status, "faults": list(dict.fromkeys([*event.get("faults", []), *sample.get("faults", [])]))}
                if sample.get("quality") == "STALE_INPUT":
                    record["faults"].append("UPSTREAM_INPUT_DEGRADED")
                heapq.heappush(pending, (received_s, serial, receiver, record))
