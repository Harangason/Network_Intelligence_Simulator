"""Record only this task's owned deltas and actual verification evidence."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent

def reference(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

def record(scope):
    path = HERE / f"{scope}-workload.json"
    work = json.loads(path.read_text(encoding="utf-8"))
    root = Path(work["repository"])
    after, changed, patch = [], [], []
    for relative in work["revision_before"]:
        actual = root / relative
        original = HERE / "before" / scope / relative
        target = HERE / "after" / scope / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = actual.read_bytes()
        target.write_bytes(content)
        after.append(reference(target))
        old = original.read_bytes() if original.is_file() else b""
        if content != old:
            changed.append(relative)
            patch.extend(difflib.unified_diff(old.decode("utf-8-sig").replace("\r\n", "\n").splitlines(True), content.decode("utf-8-sig").replace("\r\n", "\n").splitlines(True), fromfile="before/" + relative, tofile="after/" + relative))
    patch_path = HERE / f"{scope}-owned.diff"
    patch_path.write_text("".join(patch), encoding="utf-8")
    work.update(files_changed=changed, after=after, diff=[reference(patch_path)])
    path.write_text(json.dumps(work, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

if __name__ == "__main__":
    for scope in ("nis", "eip"):
        record(scope)
