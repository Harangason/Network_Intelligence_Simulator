"""Identity of the built source, frozen into simulation evidence."""
import json
from pathlib import Path


def build_info() -> dict:
    try:
        return json.loads(Path(__file__).with_name("build-info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema_version": 1, "build_id": "development", "source_sha256": None, "built_at": None}
