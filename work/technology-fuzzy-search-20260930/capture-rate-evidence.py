"""Capture the four scoped before/after files and diff for the implementation guard."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(r"I:\PycharmProjects\My_first_Network_Simulator")
target = root / "work/technology-fuzzy-search-20260930/rate-minimum-evidence"
target.mkdir(parents=True, exist_ok=True)
files = (
    "frontend/src/lib/types.ts",
    "frontend/src/lib/technology-parameters.ts",
    "frontend/src/lib/technology-parameters.test.mjs",
    "frontend/e2e/technology-parameter-review.spec.ts",
)

def reference(path: Path, data: bytes) -> dict[str, str]:
    path.write_bytes(data)
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}

before = []
after = []
for relative in files:
    label = relative.replace("/", "-")
    baseline = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=root)
    before.append(reference(target / f"before-{label}", baseline))
    after.append(reference(target / f"after-{label}", (root / relative).read_bytes()))
change = subprocess.check_output(["git", "diff", "--", *files], cwd=root)
diff = [reference(target / "change.diff", change)]
print(json.dumps({"before": before, "after": after, "diff": diff}, indent=2))
