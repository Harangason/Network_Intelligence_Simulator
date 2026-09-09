"""Rebuild and replay the exported 260-node project without database or HTTP access."""
from contextlib import contextmanager
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "backend/simulator")]
os.environ["DATABASE_URL"] = "postgresql://offline:offline@127.0.0.1:1/offline"
os.environ["ENGINEERING_TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
from backend.engineering.routing import config_builder
from backend.engineering.capacity import service as capacity
from backend.app.runtime_analysis import analyze_runtime_trace
from communication_simulator import run_simulation

bundle = json.loads((Path(__file__).parent / "2026-09-09-nis-project-bundle.json").read_text(encoding="utf-8-sig"))
original = bundle["project_data"]["engineering_simulation_snapshots"][0]["configuration"]
source = bundle["source_data"]

class Connection:
    def execute(self, query, _parameters):
        self.rows = next((rows for table, rows in source.items() if f"FROM {table} " in query), [])
        return self
    def fetchall(self):
        return deepcopy(self.rows)

@contextmanager
def connection():
    yield Connection()

model = original["engineering_model"]
with patch.object(config_builder, "get_connection", connection):
    transport = config_builder.CommunicationConfigBuilder().build(model["routes"],
        topology=original["topology"], parameters=original["parameters"])["config"]
config = {**original, **transport, "output_dir": str(ROOT / ".tmp/transport-fixed-real260"),
    "formats": ["universal-jsonl"]}
started = perf_counter()
result = run_simulation(config)
simulation_seconds = perf_counter() - started
started = perf_counter()
runtime = analyze_runtime_trace(result, config)
analysis_seconds = perf_counter() - started
object_tables = {"HardwareNode": "engineering_hardware_nodes", "HardwareNetworkInterface": "engineering_hardware_interfaces",
    "Interface": "engineering_interfaces", "Message": "engineering_messages", "Signal": "engineering_signals"}
def page(rows, kwargs):
    offset = kwargs.get("offset", 0)
    return deepcopy(rows[offset:offset + kwargs.get("limit", 250)])
with patch.object(capacity, "list_objects", lambda kind, **kwargs: page(source.get(object_tables.get(kind), []), kwargs)), \
     patch.object(capacity, "list_routes", lambda **kwargs: page(model["routes"], kwargs)):
    service = capacity.CapacityTimingService("offline-real260")
    with patch.object(service.workflow, "get", lambda: deepcopy(bundle["workflow"])), patch.object(service, "latest", lambda: None):
        started = perf_counter()
        capacity_result = service.calculate(persist=False)
        capacity_seconds = perf_counter() - started
        calculated = capacity_result["results"]
trace = next(Path(item) for item in result["artifacts"] if str(item).endswith("universal_trace.jsonl"))
events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
output_network = "Infotainment_08-S01"
summary = {
    "source": "Saved original 260-node project, no live/database writes. Existing missing-route data intentionally retained.",
    "wall_seconds": {"simulation_and_golden_export": round(simulation_seconds, 3),
        "runtime_analysis": round(analysis_seconds, 3), "capacity_analysis": round(capacity_seconds, 3)},
    "networks": len(transport["networks"]), "route_segments": sum(len(item["segments"]) for item in transport["communications"]),
    "logical_routes": len(transport["communications"]), "events": len(events),
    "observed_signals": len({signal["signal_id"] for event in events for signal in event.get("signals", [])}),
    "runtime_summary": runtime["summary"],
    "route_statuses": dict(Counter(item["status"] for item in runtime["routes"])),
    "routes_with_jitter_limit": sum(item["jitter_limit_ms"] is not None for item in runtime["routes"]),
    "false_jitter_passes": sum(item["status"] == "PASS" and item["jitter_limit_ms"] is not None
        and item["maximum_jitter_ms"] > item["jitter_limit_ms"] for item in runtime["routes"]),
    "gateway_output_events": sum(item["network"] == output_network for item in events),
    "gateway_output_technologies": sorted({item["technology"] for item in events if item["network"] == output_network}),
    "gateway_output_runtime": next(item for item in runtime["networks"] if item["network_id"] == output_network),
    "gateway_output_capacity": next(item for item in calculated["networks"] if item["network_id"] == output_network),
    "capacity_networks": len(calculated["networks"]), "capacity_findings_by_code": dict(Counter(item["code"] for item in capacity_result["findings"])),
    "golden_events": sum(1 for _ in next(Path(item) for item in result["artifacts"] if str(item).endswith("golden_trace.jsonl")).open(encoding="utf-8")),
}
output = Path(__file__).with_suffix(".json")
output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({key: value for key, value in summary.items() if key not in {"gateway_output_runtime", "gateway_output_capacity"}}, indent=2))
