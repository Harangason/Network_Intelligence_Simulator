"""Read-only independent identity/health audit; no project or model writes."""
import hashlib
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('receipt', type=Path)
parser.add_argument('--expected-freeze', type=Path)
parser.add_argument('--output-name', default='production-identity-verification.json')
args = parser.parse_args()
assert Path(args.output_name).name == args.output_name
receipt_path = args.receipt.resolve()
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
assert receipt["status"] == "PASS", receipt["status"]
freeze = json.loads(args.expected_freeze.read_text(encoding='utf-8')) if args.expected_freeze else None
if freeze:
    assert receipt['release']['source_sha256'] == freeze['source_sha256']
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
if freeze:
    expected.update({p: freeze['files'][p] for p in modules if p in freeze['files']})
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
    "expected_freeze": str(args.expected_freeze.resolve()) if args.expected_freeze else None,
    "expected_freeze_sha256": hashlib.sha256(args.expected_freeze.read_bytes()).hexdigest() if args.expected_freeze else None,
    "project_id": "20261016122109077-dc3a1aeb",
    "canonical_writes": False,
}
(OUT / args.output_name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"status": report["status"], "image_id": image, "source_sha256": build["source_sha256"]}), flush=True)
