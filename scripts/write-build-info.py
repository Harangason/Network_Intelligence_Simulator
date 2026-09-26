"""Create the same content-addressed release identity for both app processes."""
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commit_identity(root):
    """Base Git revision; source_sha256 separately identifies uncommitted code."""
    supplied = os.environ.get("NIS_BUILD_COMMIT_ID", "").strip()
    if supplied:
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", supplied):
            raise ValueError("NIS_BUILD_COMMIT_ID must be a full Git object ID")
    if not (root / ".git").exists():
        return supplied or None
    try:
        value = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            text=True, stderr=subprocess.DEVNULL, timeout=10,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if supplied and supplied != value:
        raise ValueError("NIS_BUILD_COMMIT_ID differs from the checkout HEAD")
    return value if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) else None


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
    excluded = {".venv", "node_modules", "test-output", "tests", "__pycache__", "generated"}
    hashes = {}
    for path in sorted(paths):
        relative_parts = path.relative_to(root).parts
        if not path.is_file() or excluded.intersection(relative_parts) or relative_parts[:2] == ("backend", "runtime"):
            continue
        if path.suffix in {".pyc", ".tsbuildinfo"}:
            continue
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    source = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": 1, "build_id": source[:12], "source_sha256": source,
            "commit_id": commit_identity(root),
            "built_at": datetime.now(timezone.utc).isoformat(), "source_file_count": len(hashes)}


if __name__ == "__main__":
    manifest = build_manifest()
    for relative in ("backend/app/build-info.json", "frontend/public/build-info.json"):
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))
