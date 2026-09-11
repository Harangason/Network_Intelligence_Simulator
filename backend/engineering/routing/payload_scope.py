"""Recipient boundaries for local I/O, shared device data and function outputs.

Only explicit communication contracts establish scope. Bus technology, names and
physical reachability never make local measurements/commands a function output.
"""
from ..pagination import all_pages
from ..repository import list_objects


def message_scope(message):
    config = message.get("configuration") or {}
    contract = config.get("communication_contract") or {}
    transport = config.get("transport_unit") or {}
    declared = contract.get("scope")
    command = (transport.get("provenance") or {}).get("generator") == "wizard-local-actuator-command"
    local = declared == "LOCAL_IO" or (not declared and (command or contract.get("role") in {"MEASUREMENT", "FEEDBACK", "COMMAND"}))
    scope = "LOCAL_IO" if local else declared or ("FUNCTION_OUTPUT" if contract.get("role") == "DEVICE_STATUS" else "DEVICE_IO")
    receivers = contract.get("consumer_refs", transport.get("consumer_refs", [])) or []
    return {"scope": scope, "restricted": local,
            "consumer_refs": sorted(set(map(str, receivers))),
            "reason": "Lokale Messung, Stellbefehl oder Rückmeldung: nur für die zugeordneten Empfänger."
            if local else "Funktionsausgang oder direkt nutzbare Gerätedaten; Empfänger gezielt festlegen."}


def scope_allows(scope, destination, interfaces=None):
    if not scope["restricted"]:
        return True
    interface = (interfaces or {}).get(str(destination.get("interface_id") or ""), {})
    identities = {str(destination.get("node_id") or ""), str(destination.get("interface_id") or ""),
                  str(interface.get("function_id") or "")}
    return bool(identities.intersection(scope["consumer_refs"]))


def payload_scope_issues(route, messages, signals=None, interfaces=None):
    payload = route.get("payload") or {}
    ids = {str(mid) for mid in payload.get("message_ids") or []}
    if payload.get("message_id"):
        ids.add(str(payload["message_id"]))
    ids.update(str((signals or {}).get(str(sid), {}).get("message_id") or "") for sid in payload.get("signal_ids") or [])
    issues = []
    for mid in sorted(ids):
        message = messages.get(mid)
        if not message:
            continue  # Reference validation reports missing objects separately.
        scope = message_scope(message)
        for destination in route.get("destinations") or []:
            if scope_allows(scope, destination, interfaces):
                continue
            issues.append({"code": "LOCAL_IO_RECIPIENT_MISMATCH", "severity": "ERROR",
                "message_id": mid, "destination_node_id": str(destination.get("node_id") or ""),
                "message": f"{message.get('name', mid)} ist lokale Sensor-/Aktorkommunikation. "
                    "Für diesen Empfänger einen benötigten Funktionsausgang wählen; lokale Rohdaten werden nicht automatisch weitergeleitet."})
    return issues


def load_payload_context():
    return tuple({str(item["id"]): item for item in all_pages(list_objects, kind)}
                 for kind in ("Message", "Signal", "Interface"))
