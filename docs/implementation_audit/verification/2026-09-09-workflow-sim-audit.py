"""Read-only live audit plus isolated, local simulator reproductions.

Run with backend/.venv/Scripts/python.exe from the canonical repository.
No database calls, HTTP writes, or changes to the live project are performed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "backend/simulator")]
os.environ["DATABASE_URL"] = "postgresql://nis_audit_readonly:unavailable@127.0.0.1:1/nis_audit"
os.environ["ENGINEERING_TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
PROJECT = "network-project-20260909082213746-780a13ef"
SNAPSHOT = "8d0766df-0a7a-490a-95ea-13b2b27b2a17"


def get(path: str):
    request = urllib.request.Request(
        "http://127.0.0.1:15050/api/engineering/" + path,
        headers={"X-Project-ID": PROJECT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def live_evidence():
    snapshot = get("workflow/simulation-snapshots/" + SNAPSHOT)
    config = snapshot["configuration"]
    result = snapshot["result"]
    model = config["engineering_model"]
    communications = {item["id"]: item for item in config["communications"]}
    routes = {item["id"]: item for item in model["routes"]}
    metrics = result["runtime_metrics"]["routes"]
    covered_messages = {key for item in communications.values() for key in item.get("message_ids", [])}
    covered_signals = {key for item in communications.values() for key in item.get("signal_ids", [])}
    covered_signals |= {item["id"] for item in model["signals"] if item["message_id"] in covered_messages}
    calculated_networks = {item["network_id"]: item for item in snapshot["calculated_metrics"]["networks"]}
    executable_networks = {item["id"] for item in config["networks"]}
    runtime_networks = {item["network_id"] for item in result["runtime_metrics"]["networks"]}
    false_pass = []
    for metric in metrics:
        route = routes[communications[metric["route_id"]]["routing_entry_id"]]
        limit = route.get("timing", {}).get("jitter_limit_ms")
        if limit is not None and metric["maximum_jitter_ms"] > limit and metric["status"] == "PASS":
            false_pass.append({
                "name": route["name"], "canonical_route_id": route["id"],
                "runtime_route_id": metric["route_id"], "maximum_jitter_ms": metric["maximum_jitter_ms"],
                "canonical_jitter_limit_ms": limit, "runtime_jitter_limit_ms": metric["jitter_limit_ms"],
                "runtime_jitter_violations": metric["jitter_violations"], "runtime_status": metric["status"],
            })
    return {
        "project_id": PROJECT, "snapshot_id": SNAPSHOT, "job_id": snapshot["job_id"],
        "source_versions": snapshot["source_versions"], "model_counts": model["counts"],
        "duration_s": config["duration_s"], "runtime_summary": result["runtime_metrics"]["summary"],
        "runtime_route_statuses": dict(Counter(item["status"] for item in metrics)),
        "gateway_segment_coverage": {
            "calculated_network_count": len(calculated_networks),
            "executable_network_count": len(executable_networks), "runtime_network_count": len(runtime_networks),
            "calculated_networks_missing_from_simulation": [calculated_networks[key]
                for key in calculated_networks.keys() - executable_networks],
            "gateway_routes": [{"id": item["id"], "name": item["name"], "source": item["source"],
                "destinations": item["destinations"], "path": item["route"]}
                for item in routes.values() if item.get("route", {}).get("gateways")],
        },
        "canonical_timing_field_counts": {field: sum(item.get("timing", {}).get(field) is not None for item in routes.values())
            for field in ("jitter_limit_ms", "max_latency_ms", "timeout_ms", "deadline_ms")},
        "runtime_limit_field_counts": {field: sum(item.get(field) is not None for item in metrics)
            for field in ("jitter_limit_ms", "maximum_latency_limit_ms", "freshness_limit_ms")},
        "false_pass_jitter_route_count": len(false_pass), "false_pass_jitter_routes": false_pass,
        "transport_coverage": {
            "covered_messages": len(covered_messages), "covered_signals": len(covered_signals),
            "missing_messages": [{"id": item["id"], "name": item["name"]} for item in model["messages"] if item["id"] not in covered_messages],
            "missing_signals": [{"id": item["id"], "name": item["name"]} for item in model["signals"] if item["id"] not in covered_signals],
        },
        "signal_emulation_validation": config["signal_emulation_validation"],
        "actual_signal_summary": result["model_simulation"]["signal_summary"],
        "storage": result["model_simulation"]["storage"], "warnings": result["warnings"],
    }


def isolated_evidence():
    from backend.app.runtime_analysis import analyze_runtime_trace
    from backend.tests.test_model_based_simulation import simulation_config
    from communication_simulator import run_simulation

    frames = [{"route_id": "route-1", "network": "can-main", "time_s": time_s,
        "status": "dropped", "configured_cycle_ms": 10, "end_to_end_latency_ms": 0,
        "queue_delay_ms": 0, "transmission_latency_ms": 0} for time_s in (0, .1)]
    dropped = analyze_runtime_trace({"model_simulation": {"frames": frames}}, {
        "duration_s": .1, "communications": [{"id": "route-1", "timeout_ms": 20,
        "maximum_latency_ms": 10, "jitter_limit_ms": 5}],
    })
    out = ROOT / ".tmp/workflow-sim-golden-audit-20260909"
    fault = {"scope": "SIGNAL", "type": "SIGNAL_OFFSET", "target": {"id": "sig-temperature"},
        "start_s": .02, "end_s": .06, "magnitude": 20}
    result = run_simulation(simulation_config(out, faults=[fault]))

    def read(name):
        path = next(Path(value) for value in result["artifacts"] if str(value).endswith(name))
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    actual, golden = read("fault_trace.jsonl"), read("golden_trace.jsonl")
    index = next(i for i, event in enumerate(actual) if event["signals"][0]["value"] != event["signals"][0]["golden_value"])
    actual_event, golden_event = actual[index], golden[index]
    golden_decoded = int.from_bytes(bytes.fromhex(golden_event["payload_hex"])[0:2], "little") * .1 - 40
    return {
        "all_frames_dropped": {"summary": dropped["summary"], "routes": dropped["routes"]},
        "golden_payload_mismatch": {
            "actual_payload_hex": actual_event["payload_hex"], "golden_payload_hex": golden_event["payload_hex"],
            "actual_signal": actual_event["signals"][0], "golden_signal": golden_event["signals"][0],
            "decoded_golden_payload_degc": golden_decoded,
            "declared_golden_signal_degc": golden_event["signals"][0]["value"],
        },
    }


if __name__ == "__main__":
    evidence = {"captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "live": live_evidence(), "isolated_workspace": isolated_evidence()}
    target = Path(__file__).with_suffix(".json")
    target.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"evidence": str(target),
        "false_pass_jitter_routes": evidence["live"]["false_pass_jitter_route_count"],
        "actual_signal_count": evidence["live"]["actual_signal_summary"]["signal_count"],
        "model_signal_count": evidence["live"]["model_counts"]["signals"],
        "dropped_route_status": evidence["isolated_workspace"]["all_frames_dropped"]["routes"][0]["status"],
        "golden_declared_degc": evidence["isolated_workspace"]["golden_payload_mismatch"]["declared_golden_signal_degc"],
        "golden_decoded_degc": evidence["isolated_workspace"]["golden_payload_mismatch"]["decoded_golden_payload_degc"]}, indent=2))
