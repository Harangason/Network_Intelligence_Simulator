"""Create the same content-addressed release identity for both app processes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_manifest(root=ROOT):
    paths = (set(root.joinpath("backend").rglob("*.py"))
             | set(root.joinpath("frontend/src").rglob("*"))
             | set(root.joinpath("frontend/scripts").rglob("*"))
             | set(root.joinpath("config").rglob("*.json")))
    paths.update(root.joinpath("frontend").glob("*config*"))
    paths.update(root / name for name in (
        "Dockerfile", ".dockerignore", "generate_realistic_communication_tool.py", "scripts/write-build-info.py",
        "scripts/verify-runtime-lock.py",
        "backend/requirements.txt", "backend/requirements.lock", "backend/pyproject.toml", "backend/uv.lock",
        "frontend/package.json", "frontend/package-lock.json",
    ))
    excluded = {".venv", "node_modules", "runtime", "test-output", "tests", "__pycache__", "generated"}
    hashes = {}
    for path in sorted(paths):
        if not path.is_file() or excluded.intersection(path.relative_to(root).parts):
            continue
        if path.suffix in {".pyc", ".tsbuildinfo"}:
            continue
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    source = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": 1, "build_id": source[:12], "source_sha256": source,
            "built_at": datetime.now(timezone.utc).isoformat(), "source_file_count": len(hashes)}


if __name__ == "__main__":
    manifest = build_manifest()
    for relative in ("backend/app/build-info.json", "frontend/public/build-info.json"):
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))
