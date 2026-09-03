"""Random Forest baseline trainer.

Uses sklearn when installed; otherwise falls back to a deterministic token
ensemble with Random-Forest-compatible registry metadata.
"""

from __future__ import annotations

from typing import Any

from ..core.feature_schema import FEATURE_SCHEMA_VERSION
from ..core.model import train_token_ensemble


class RandomForestTrainer:
    model_type = "RANDOM_FOREST"

    def train(self, task: str, rows: list[dict[str, Any]]) -> Any:
        return train_token_ensemble(rows, task=task, model_type=self.model_type, feature_schema_version=FEATURE_SCHEMA_VERSION)
