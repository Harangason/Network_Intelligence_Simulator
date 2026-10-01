"""Project the canonical transmission contracts into the executable snapshot."""
from copy import deepcopy
from .dimensioning import effective_period, transmission_contract


def apply_runtime_plan(config, messages):
    by_id = {str(item["id"]): item for item in messages}
    stored = (config.get("parameters") or {}).get("communication_schedule") or {}
    schedules = {item["network_id"]: item for item in stored.get("networks", [])}
    expanded = []
    for communication in config.get("communications", []):
        identifiers = [str(key) for key in communication.get("message_ids", []) if str(key) in by_id]
        if not identifiers:
            expanded.append(communication)
            continue
        for identifier in identifiers:
            item = deepcopy(communication)
            message = by_id[identifier]
            item["message_ids"] = [identifier]
            item["cycle_ms"] = effective_period(message, message.get("cycle_ms") or communication["cycle_ms"])
            payload_bytes = message.get("dlc")
            if payload_bytes is None:
                default_payload = (config.get("parameters") or {}).get("payload_bytes", 8)
                payload_bytes = communication.get("payload_bytes", default_payload) if len(identifiers) == 1 else default_payload
            item["payload_bytes"] = int(payload_bytes)
            item["transmission_contract"] = transmission_contract(message)
            item["signal_ids"] = [str(signal["id"]) for signal in (config.get("engineering_model") or {}).get("signals", []) if str(signal.get("message_id")) == identifier]
            try:
                raw_id = str(message.get("message_id_hex") or "")
                item["arbitration_id"] = int(raw_id, 16 if raw_id.lower().startswith("0x") else 10)
            except ValueError:
                item["arbitration_id"] = None
            if len(identifiers) > 1:
                item["id"] += ":message:" + identifier
                for segment in item.get("segments", []):
                    segment["id"] += ":message:" + identifier
            route_ids = set(item.get("routing_entry_ids") or []) | {item.get("routing_entry_id")}
            for endpoint in [item, *item.get("segments", [])]:
                schedule = schedules.get(endpoint.get("network_id"), {})
                slot = next((s for s in schedule.get("slots", []) if s.get("message_id") == identifier
                             and route_ids.intersection(s.get("route_ids", [])) and abs(s["period_ms"] - item["cycle_ms"]) < 1e-7), None)
                if slot:
                    endpoint["lin_slot"] = slot
                    endpoint["phase_ms"] = slot["offset_ms"]
            expanded.append(item)
    config["communications"] = expanded
    config["communication_plan_version"] = stored.get("version")
    return config
