"""Existing switched Ethernet timing-evidence finding."""

def timing_gap_findings(route, _number):
    findings = []
    if route.get("e2e_timing_gap") and any(_number(route.get(key), 0) > 0 for key in ("max_latency_ms", "timeout_ms", "freshness_ms", "jitter_budget_ms")):
        findings.append({"severity": "WARNING", "code": "ETHERNET_SWITCH_DELAY_UNVERIFIED",
            "object_type": "RoutingEntry", "object_id": route["route_id"],
            "message": route["e2e_timing_gap"],
            "recommendation": "Eine bestätigte switching_delay_ms-Grenze am Switch-Hardwareprofil hinterlegen und Capacity/Preflight erneut ausführen."})
    return findings
