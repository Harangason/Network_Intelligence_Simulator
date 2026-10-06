"""Snapshot a read-only mounted data volume before a production path cutover."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.migrations.storage_layout import copy_verified


def snapshot_tree(source: Path, destination: Path) -> dict:
    source, destination = source.resolve(), destination.resolve()
    if source == destination or destination.is_relative_to(source):
        raise ValueError("Snapshot must be outside the source volume")
    records = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Linked volume entry requires reconciliation: {path}")
        if not path.is_file() or path.name.endswith(("-wal", "-shm")) or path.suffix in {".lock", ".tmp"}:
            continue
        records.append(copy_verified(path, destination / path.relative_to(source)))
    receipt = {"schema_version": 1, "recorded_at": datetime.now(timezone.utc).isoformat(),
               "source": str(source), "destination": str(destination), "files": records,
               "source_read_only": True, "status": "SNAPSHOT_VERIFIED"}
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "snapshot-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    result = snapshot_tree(args.source, args.destination)
    print(json.dumps({"status": result["status"], "files": len(result["files"])}))
