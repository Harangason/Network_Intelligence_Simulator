"""Verify normal live API captures against immutable release and UI save/reload."""
import json
from pathlib import Path
import sys
import subprocess
from urllib.request import urlopen
out = Path(__file__).parent
receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert receipt["status"] == "PASS"
def read(label, name):
    return json.loads((out / label / (name + ".json")).read_text(encoding="utf-8"))
def saved_rates(parameters):
    return {technology: {key: value for key, value in group.get("values", {}).items() if "bitrate" in key}
            for technology, group in parameters.get("simulation_parameter_assumptions", {}).items()}
def nominal_checks(review):
    keys = ("network_id", "technology", "port_id", "message_count", "status", "rates", "load_percent", "target_load_percent")
    return sorted(({key: row.get(key) for key in keys} for row in review["simulation_capacity"]),
                  key=lambda row: (row["network_id"], row["technology"], row["port_id"] or ""))
before_parameters = read("before-save-live", "parameters")["parameters"]
after_parameters = read("after-reload-live", "parameters")["parameters"]
before_review = read("before-save-live", "review")
after_review = read("after-reload-live", "review")
build = read("after-reload-live", "build")
assert build["source_sha256"] == receipt["release"]["source_sha256"]
assert saved_rates(before_parameters) == saved_rates(after_parameters)
assert nominal_checks(before_review) == nominal_checks(after_review)
false_missing = [row for row in after_review["findings"]
                 if row["code"] == "CAPACITY_UNVERIFIED" and any("bitrate" in field for field in row.get("missing_fields", []))]
assert not false_missing
checks = nominal_checks(after_review)
assert checks and all(row["status"] == "FEASIBLE_UNDER_ASSUMPTIONS" for row in checks)
assert all(row.get("hardware_evidence") is False and row.get("functional_timing_accepted") is False
           for row in after_review["simulation_capacity"])
with urlopen("http://localhost:13500/api/ready", timeout=30) as response:
    ready = json.load(response)
assert ready["status"] == "ready"
running_image = subprocess.check_output(["C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe", "inspect", "NetworkIS", "--format", "{{.Image}}"], text=True).strip()
assert running_image == receipt["image_id"]
proof = {"status": "PASSED", "project_id": after_review["project_id"], "image_id": running_image,
         "source_sha256": build["source_sha256"], "ready": ready, "saved_rates_unchanged": True,
         "saved_rates": saved_rates(after_parameters), "save_reload_stable": True,
         "false_missing_rate_findings": len(false_missing), "nominal_network_checks": len(checks),
         "device_qualification_findings": sum(row["code"] == "CAPACITY_DEVICE_EVIDENCE_MISSING" for row in after_review["findings"]),
         "loads": checks, "screenshot": str((out / "live-save-reload.png").resolve()),
         "scope": "Normal live API and UI save/reload on pending user proposal; no assertion of user-project nine-stage completion."}
assert (out / "live-save-reload.png").is_file()
(out / "functional-proof.json").write_text(json.dumps(proof, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({key: value for key, value in proof.items() if key not in ("loads", "ready")}, ensure_ascii=False))
