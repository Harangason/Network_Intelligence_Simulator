"""Existing LIN slot reserve and timing-budget findings."""

def reserve_findings(network, sizing_policy, schedule):
    findings = []
    slot_load = schedule.get('slot_load_percent')
    if slot_load is not None and slot_load > sizing_policy['maximum_slot_load_percent']:
        findings.append({'severity': 'ERROR' if sizing_policy.get('reserve_requirement') == 'HARD' else 'WARNING',
            'code': 'LIN_SCHEDULE_RESERVE_UNMET', 'object_type': 'Network', 'object_id': network['network_id'],
            'message': f"{network['network_name']}: {slot_load:g} % der LIN-Slots reserviert; "
                       f"Reserveziel {sizing_policy['maximum_slot_load_percent']:g} %. "
                       'Bei 100 % bleibt kein freier Slot. Dies ist getrennt von Nominallast und Funktionsfreigabe zu bewerten.',
            'recommendation': 'Verbleibende Schedule-Reserve ausdrücklich prüfen; bestätigte Zyklen und Kodierungen bleiben unverändert.'})
    return findings


def budget_findings(network):
    findings = []
    schedule = network.get("lin_schedule") or {}
    if schedule.get("status") == "FAIL":
        findings.append({"severity": "ERROR", "code": "LIN_SCHEDULE_BUDGET_EXCEEDED",
            "object_type": "Network", "object_id": network["network_id"],
            "message": f"{network['network_id']}: Gleichzeitige LIN-Frames belegen {schedule['synchronous_batch_ms']:g} ms; das Timing-Budget betraegt {schedule['budget_ms']:g} ms.",
            "recommendation": "Lokale Busaufteilung anhand der Timing-Anforderungen planen oder einen expliziten Pollplan spezifizieren."})
    return findings
