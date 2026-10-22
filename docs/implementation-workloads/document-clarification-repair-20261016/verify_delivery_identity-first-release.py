"""Read-only independent identity/health audit; no project or model writes."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
receipt_path = Path(sys.argv[1]).resolve()
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
assert receipt["status"] == "PASS", receipt["status"]
config = json.loads((ROOT / "config/networkis.resources.json").read_text(encoding="utf-8"))
docker = config["paths"]["docker_cli"]


def docker_read(*args):
    return subprocess.check_output([docker, *args], text=True, encoding="utf-8").strip()


image = docker_read("inspect", "NetworkIS", "--format", "{{.Image}}")
assert image == receipt["image_id"], (image, receipt["image_id"])
container = json.loads(docker_read("inspect", "NetworkIS"))[0]
assert container["State"]["Running"] is True
base = "http://127.0.0.1:13500"
with urlopen(base + "/api/ready", timeout=20) as response:
    ready = json.load(response)
with urlopen(base + "/api/build-info", timeout=20) as response:
    build = json.load(response)
assert ready["status"] == "ready", ready
assert build["source_sha256"] == receipt["release"]["source_sha256"]
modules = [
    "backend/nis/agent/orchestration/project_intake.py",
    "backend/nis/communication/registry.py",
    "backend/nis/agent/tools/wizard_generation.py",
    "backend/nis/engineering/communication/device_communication.py",
]
expected = {p: hashlib.sha256((OUT / "after" / p).read_bytes()).hexdigest() for p in modules}
code = "import hashlib,json,sys; from pathlib import Path; print(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in json.loads(sys.argv[1])}))"
actual = json.loads(docker_read("exec", "NetworkIS", "python", "-c", code, json.dumps(modules)))
assert actual == expected, {"expected": expected, "actual": actual}
assert docker_read("inspect", "NetworkIS", "--format", "{{.Image}}") == image
report = {
    "status": "PASSED",
    "at": datetime.now(timezone.utc).isoformat(),
    "scope": "Exact PASS image, running state, readiness, build source and four affected backend module hashes only; not native Wizard/vehicle simulation evidence.",
    "receipt": str(receipt_path),
    "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    "image_id": image,
    "source_sha256": build["source_sha256"],
    "ready": ready,
    "build": build,
    "container_started_at": container["State"]["StartedAt"],
    "module_hashes": actual,
    "project_id": "20261016122109077-dc3a1aeb",
    "canonical_writes": False,
}
(OUT / "production-identity-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"status": report["status"], "image_id": image, "source_sha256": build["source_sha256"]}), flush=True)
