"""Evidence-only counterprobe against the exact preserved before source."""
from pathlib import Path
from types import ModuleType
import pytest
from backend.tests import test_reference_reasoner as regression


def test_preserved_before_source_exposes_stale_downstream_state(monkeypatch):
    path = Path(__file__).parent / "before/backend/nis/agent/orchestration/local_reasoner.py"
    before = ModuleType("nis_retry_before_counterprobe")
    before.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), before.__dict__)
    monkeypatch.setattr(regression.LocalEngineeringReasoner, "plan_reference_design",
                        before.LocalEngineeringReasoner.plan_reference_design)
    with pytest.raises(AssertionError) as caught:
        regression.test_reference_profile_replan_discards_stale_downstream_stage_outputs(monkeypatch)
    failure = caught.traceback[-1]
    assert failure.name == "test_reference_profile_replan_discards_stale_downstream_stage_outputs"
    assert "all(not rows" in str(failure.statement)
