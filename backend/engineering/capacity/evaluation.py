"""Keep wire capacity, stress scenarios and functional acceptance distinct."""
from .dimensioning import number


def network_evaluation(network, streams, signal_checks):
    message_ids = {row.get("message_id") for row in streams}
    signals = [signal for signal in signal_checks if signal.get("message_id") in message_ids]
    payload_errors = sum(signal["status"] == "ERROR" for signal in signals)
    payload_open = sum(signal["status"] == "OPEN" for signal in signals)
    schedule = network["communication_schedule"]
    functional = []
    for row in streams:
        contract = row.get("transmission_contract") or {}
        requirement = contract.get("functional_requirements") or {}
        confirmed = requirement.get("confirmed") is True
        deadline = number(requirement.get("maximum_event_to_response_ms"))
        delays_known = all(requirement.get(key) is not None and number(requirement[key], -1) >= 0
                           for key in ("sampling_delay_ms", "actuation_delay_ms"))
        response = schedule.get("responses", {}).get(row["stream_id"])
        # Arbitrary event can wait for the next release/poll. The wire bound
        # alone does not prove reaction of a brake, actuator or controller.
        bound = (row["cycle_ms"] + response + number(row.get("fixed_path_delay_ms"))
                 + number(requirement.get("sampling_delay_ms")) + number(requirement.get("actuation_delay_ms"))) if response is not None and delays_known else None
        verified = confirmed and deadline > 0 and bound is not None and row.get("route_segment_count", 1) == 1
        functional.append({"message_id": row.get("message_id"), "name": row.get("message_name") or row.get("name"),
            "status": ("PASS" if bound <= deadline else "FAIL") if verified else "UNVERIFIED",
            "event_to_response_bound_ms": bound if verified else None, "requirement_ms": deadline or None})
    status = "FAIL" if any(item["status"] == "FAIL" for item in functional) else (
        "PASS" if functional and all(item["status"] == "PASS" for item in functional) else "UNVERIFIED")
    return {"payload": {"status": "FAIL" if payload_errors else "UNVERIFIED" if payload_open or not signals else "PASS",
                        "signal_count": len(signals), "errors": payload_errors, "open": payload_open},
        "capacity": {"status": "OVERLOAD" if network["average_load_percent"] >= 100 else "PASS",
                     "load_percent": network["average_load_percent"],
                     "basis": "BOUNDED_EVENT_DEMAND" if any(row.get("traffic_load_basis") == "BOUNDED_EVENT_DEMAND" for row in streams) else "PERIODIC_DEMAND"},
        "schedule": {"status": schedule["status"], "slot_load_percent": schedule.get("slot_load_percent")},
        "stress": {"status": "EXCEEDED" if max(network["peak_load_percent"], network["burst_load_percent"]) > network["target_bus_load_percent"] else "PASS",
                   "peak_percent": network["peak_load_percent"], "burst_percent": network["burst_load_percent"]},
        "functional": {"status": status, "messages": functional,
            "explanation": "Funktionsfrist, Abtastung und Aktuation sind getrennt von der Bus-Antwortgrenze nachzuweisen."}}
