"""Attach verified evidence to the rate proposal implementation workload."""
import hashlib
import json
from pathlib import Path

root = Path(r"I:\PycharmProjects\My_first_Network_Simulator")
folder = root / "work/technology-fuzzy-search-20260930"
workload_file = folder / "rate-minimum-workload.json"
receipt_file = Path(r"F:\CodexOrdner\worktrees\wizard-repair\My_first_Network_Simulator\backend\test-output\release-gates\rate-minimum-final-20260930\9b7d7b543a9a\receipt.json")
evidence_folder = folder / "rate-minimum-evidence"
work = json.loads(workload_file.read_text(encoding="utf-8-sig"))
captured = json.loads((evidence_folder / "index.json").read_text(encoding="utf-8-sig"))
receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
live = json.loads((evidence_folder / "live-evidence.json").read_text(encoding="utf-8-sig"))
deployment = json.loads((evidence_folder / "deployment-evidence.json").read_text(encoding="utf-8-sig"))
assert receipt["status"] == "PASS"
assert all(check["exit_code"] == 0 for check in receipt["checks"])
assert deployment["image_id"] == receipt["image_id"]
assert deployment["source_sha256"] == receipt["release"]["source_sha256"]
assert deployment["ready"]["status"] == "ready"
assert live["technology"] == "i2c" and live["clock"] == "100000"
assert live["proposal_visible"] and live["saved_clock"] is None

def ref(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

receipt_ref = ref(receipt_file)
live_ref = ref(evidence_folder / "live-evidence.json")
deployment_ref = ref(evidence_folder / "deployment-evidence.json")
work.update(captured)
work["files_changed"] = list(work["revision_before"])
work["outcomes"] = {
    "known_mode_minimum_proposed": {"status": "PASSED", "evidence": [live_ref, receipt_ref]},
    "explicit_values_preserved": {"status": "PASSED", "evidence": [receipt_ref]},
    "proposal_unverified": {"status": "PASSED", "evidence": [live_ref]},
    "production_delivery": {"status": "PASSED", "evidence": [receipt_ref, deployment_ref]},
}
work["validations"] = {name: {"status": "PASSED", "evidence": [receipt_ref]}
                       for name in ("unit_tests", "browser_tests", "release_gate")}
work["validations"]["live_verification"] = {"status": "PASSED", "evidence": [live_ref, deployment_ref]}
work["delivery"] = {
    "decision": "YES",
    "authorization": "Standing production authorization in AGENTS.md",
    "target": "NetworkIS production port 13500",
    "tested_version": receipt["image_id"],
    "running_version": deployment["image_id"],
    "checks": {
        "release": {"status": "PASSED", "evidence": [receipt_ref]},
        "deployment": {"status": "PASSED", "evidence": [deployment_ref]},
        "health": {"status": "PASSED", "evidence": [deployment_ref]},
        "functional": {"status": "PASSED", "evidence": [live_ref]},
    },
}
work["remaining_findings"] = []
work["completion_status"] = "COMPLETED"
workload_file.write_text(json.dumps(work, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(workload_file)
