"""Feature schema versioning for ML tasks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FeatureSchema:
    task: str
    version: str
    feature_names: tuple[str, ...]

    def validate(self, features: dict[str, Any]) -> None:
        missing = [name for name in self.feature_names if name not in features]
        if missing:
            raise ValueError(f"Feature schema mismatch for {self.task}: missing {', '.join(missing[:5])}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


FEATURE_SCHEMA_VERSION = "ml-feature-schema-v1"
