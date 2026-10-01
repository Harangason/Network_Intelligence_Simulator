"""Recipient boundaries for local I/O, shared device data and function outputs.

Only explicit communication contracts establish scope. Bus technology, names and
physical reachability never make local measurements/commands a function output.
"""
from ..pagination import all_pages
from ..repository import list_objects


def external_routing_enabled(item):
    """Missing flags preserve legacy intent; explicit OFF limits forwarding."""
    return ((item.get("configuration") or {}).get("routing") or {}).get("enabled") is not False


def message_scope(message, signals=None):
    config = message.get("configuration") or {}
    contract = config.get("communication_contract") or {}
    transport = config.get("transport_unit") or {}
    declared = contract.get("scope")
    command = (transport.get("provenance") or {}).get("generator") == "wizard-local-actuator-command"
    local = declared == "LOCAL_IO" or (not declared and (command or contract.get("role") in {"MEASUREMENT", "FEEDBACK", "COMMAND"}))
    scope = "LOCAL_IO" if local else declared or ("FUNCTION_OUTPUT" if contract.get("role") == "DEVICE_STATUS" else "DEVICE_IO")
    receivers = contract.get("consumer_refs", transport.get("consumer_refs", [])) or []
    enabled = external_routing_enabled(message)
    blocked = [str(signal['id']) for signal in (signals or {}).values()
               if str(signal.get('message_id')) == str(message.get('id'))
               and signal.get('id') and not external_routing_enabled(signal)]
    forwarding_enabled = enabled and not blocked
    reason = ("Geroutet ist ausgeschaltet" if not enabled else "Die Nachricht enthält nicht geroutete Signale") \
        + "; bestätigte lokale I/O bleibt aktiv. Für externe Daten eine eigene explizite Nachricht verwenden."
    return {"scope": scope, "restricted": local or not forwarding_enabled,
            "routing_enabled": enabled, "forwarding_enabled": forwarding_enabled,
            "blocked_signal_ids": sorted(blocked), "local": local,
            "consumer_refs": sorted(set(map(str, receivers))) if forwarding_enabled or local else [],
            "reason": reason if not forwarding_enabled else
            "Lokale Messung, Stellbefehl oder Rückmeldung: nur für die zugeordneten Empfänger."
            if local else "Funktionsausgang oder direkt nutzbare Gerätedaten; Empfänger gezielt festlegen."}


def scope_allows(scope, destination, interfaces=None):
    if not scope["restricted"]:
        return True
    interface = (interfaces or {}).get(str(destination.get("interface_id") or ""), {})
    if interface.get("hardware_node_id") and str(interface["hardware_node_id"]) != str(destination.get("node_id") or ""):
        interface = {}
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
        # A route's signal subset is an observation selection, not a new frame.
        # Inspect every canonical signal in this physical message, including
        # excluded fields the caller did not select. Never shrink its DLC.
        disabled_signals = [signal for signal in (signals or {}).values()
                            if str(signal.get("message_id")) == mid and not external_routing_enabled(signal)]
        for destination in route.get("destinations") or []:
            local_allowed = scope["local"] and scope_allows(scope, destination, interfaces)
            if not local_allowed and (not scope["routing_enabled"] or disabled_signals):
                signal_names = ", ".join(str(signal.get("name") or signal.get("id")) for signal in disabled_signals)
                issues.append({"code": "MESSAGE_ROUTING_DISABLED" if not scope["routing_enabled"] else "SIGNAL_ROUTING_DISABLED",
                    "severity": "ERROR", "message_id": mid,
                    "signal_ids": [str(signal["id"]) for signal in disabled_signals if signal.get("id")],
                    "destination_node_id": str(destination.get("node_id") or ""),
                    "message": f"{message.get('name', mid)}: Geroutet ist ausgeschaltet"
                        + (f" für {signal_names}" if scope["routing_enabled"] else " für die Nachricht")
                        + ". Nur bestätigte lokale I/O-Empfänger bleiben zulässig. "
                        "Für externe Weitergabe eine eigene Nachricht mit expliziter Kodierung anlegen; "
                        "eine Signalunterauswahl verändert den physischen Frame nicht."})
                continue
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
