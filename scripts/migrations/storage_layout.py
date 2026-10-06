"""Copy approved durable storage with coherent SQLite snapshots and receipts.

Originals remain intact. Existing different destinations require reconciliation;
this tool never overwrites them. Unclassified trees stay at their current paths.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sqlite_contents(path: Path) -> dict:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        if integrity != [("ok",)]:
            raise ValueError(f"SQLite integrity failed: {path}: {integrity}")
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {"integrity": "ok", "tables": {
            name: connection.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
            for name in tables}}


def copy_verified(source: Path, target: Path) -> dict:
    if source.is_symlink() or target.is_symlink():
        raise ValueError("Linked storage needs explicit reconciliation")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nis-migration-", dir=target.parent) as temporary:
        snapshot = Path(temporary) / "snapshot"
        if source.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            # The backup API includes committed WAL changes consistently.
            with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as original:
                with closing(sqlite3.connect(snapshot)) as destination:
                    original.backup(destination)
            readability = sqlite_contents(snapshot)
        else:
            before = digest(source)
            shutil.copy2(source, snapshot)
            if digest(source) != before or digest(snapshot) != before:
                raise ValueError(f"Source changed during copy: {source}")
            readability = None
        sha = digest(snapshot)
        if target.exists():
            if digest(target) != sha:
                raise FileExistsError(f"Destination differs; original preserved: {target}")
        else:
            # Exclusive creation prevents overwriting another concurrent writer.
            with target.open("xb") as output, snapshot.open("rb") as input_stream:
                shutil.copyfileobj(input_stream, output)
        if digest(target) != sha:
            raise ValueError(f"Destination checksum mismatch: {target}")
        return {"source": str(source), "target": str(target), "sha256": sha,
                "readability": readability, "original_retained": source.exists()}


def approved_files(root: Path):
    legacy = root / "backend/simulator/physic_lib"
    yield legacy / "Config/simulation_config.db", root / "var/data/databases/simulation_config.db"
    for source in (legacy / "Industries").rglob("*.db"):
        relative = source.relative_to(legacy / "Industries")
        yield source, root / "var/data/learning/industries" / relative
    for old, new in [("SAVED", "projects"), ("backend/runtime/jobs", "jobs"),
                     ("backend/runtime/ml_registry", "ml_registry"),
                     ("backend/runtime/storage", "storage"),
                     ("backend/runtime/technology-license-evidence", "technology-license-evidence"),
                     ("technologies/generated", "technologies/generated")]:
        origin = root / old
        if origin.is_dir():
            for source in origin.rglob("*"):
                if source.is_file() and source.suffix not in {".lock", ".tmp"}:
                    yield source, root / "var/data" / new / source.relative_to(origin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    files = [(source, target) for source, target in approved_files(ROOT) if source.is_file()]
    records = [copy_verified(source, target) if args.apply else
               {"source": str(source), "target": str(target), "action": "snapshot-copy"}
               for source, target in files]
    receipt = {"schema_version": 1, "applied": args.apply,
               "recorded_at": datetime.now(timezone.utc).isoformat(), "files": records,
               "retained_unclassified": ["traces", "reports", "runtime", "backend/runtime"],
               "cutover": "Configuration and production volume migration still required"}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(records), "applied": args.apply, "receipt": str(args.receipt)}))


if __name__ == "__main__":
    main()
