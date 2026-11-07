"""Execute the new regression against the immutable pre-repair class in memory."""
import importlib.util
from pathlib import Path
from backend.tests import test_reference_reasoner as cases

def test_saved_baseline_replan_keeps_stale_downstream_outputs(monkeypatch):
    path = Path(__file__).parent / "before/backend/nis/agent/orchestration/local_reasoner.py"
    spec = importlib.util.spec_from_file_location("saved_replan_baseline", path)
    saved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(saved)
    monkeypatch.setattr(cases, "LocalEngineeringReasoner", saved.LocalEngineeringReasoner)
    cases.test_reference_profile_replan_discards_stale_downstream_stage_outputs(monkeypatch)
