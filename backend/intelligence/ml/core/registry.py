"""File-backed model registry for simulator ML artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ModelRegistryEntry:
    model_id: str
    model_type: str
    task: str
    version: str
    dataset_version: str
    feature_schema_version: str
    metrics: dict[str, Any]
    status: str
    artifact_location: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelRegistry:
    def __init__(self, root: Path | str = "backend/runtime/ml_registry") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "models.json"

    def list(self, task: str | None = None) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        items = json.loads(self.index_path.read_text(encoding="utf-8"))
        if task:
            return [item for item in items if item.get("task") == task]
        return items

    def save_model(self, model: Any, dataset_version: str, metrics: dict[str, Any], status: str = "CANDIDATE") -> ModelRegistryEntry:
        artifact = self.root / f"{model.model_id}.json"
        artifact.write_text(json.dumps(model.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        entry = ModelRegistryEntry(
            model_id=model.model_id,
            model_type=model.model_type,
            task=model.task,
            version=model.version,
            dataset_version=dataset_version,
            feature_schema_version=model.feature_schema_version,
            metrics=metrics,
            status=status,
            artifact_location=str(artifact),
        )
        items = [item for item in self.list() if item.get("model_id") != model.model_id]
        items.append(entry.to_dict())
        self.index_path.write_text(json.dumps(items, indent=2, sort_keys=True), encoding="utf-8")
        return entry

    def preferred(self, task: str) -> dict[str, Any] | None:
        candidates = [item for item in self.list(task) if item.get("status") in {"CANDIDATE", "APPROVED", "PRODUCTION"}]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (float((item.get("metrics") or {}).get("f1") or 0), item.get("model_type") == "GRADIENT_BOOSTING"), reverse=True)[0]
