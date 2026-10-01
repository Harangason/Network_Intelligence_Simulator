from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compute_policy_documents_the_active_cpu_gpu_contract() -> None:
    config = json.loads((ROOT / "config" / "networkis.resources.json").read_text(encoding="utf-8"))
    resources = config["resources"]
    policy = resources["compute_policy"]

    assert resources["numeric_accelerator"] == "auto"
    assert resources["numeric_accelerator_min_items"] > 0
    assert policy["numeric_selection"]["mode_from"] == "resources.numeric_accelerator"
    assert policy["numeric_selection"]["minimum_items_from"] == "resources.numeric_accelerator_min_items"
    assert policy["numeric_selection"]["fallback"] == "CPU"
    assert policy["numeric_selection"]["deterministic_results_required"] is True
    assert policy["numeric_selection"]["gpu_side_effects_allowed"] is False
    assert any("Datenbank" in task for task in policy["cpu_authoritative_tasks"])
    assert any("Trace" in task for task in policy["gpu_accelerated_tasks"])
    assert policy["ai_selection"]["semantic_fast_model_from"] == "ai.providers.ollama.fast_model"
