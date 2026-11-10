"""Verify existing fixture failures against immutable pre-repair source."""
import importlib.util
from pathlib import Path
import pytest
_spec=importlib.util.spec_from_file_location('original_cache_tests',Path(__file__).parent/'before/test_reference_cache_output.py')
tests=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(tests)

def baseline():
    p=Path(__file__).parent/'before/local_reasoner.py'
    spec=importlib.util.spec_from_file_location('pre_current_stage_reasoner',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_original_anchor_fixture_changes_wire_envelope_before_prefix_assertion(monkeypatch):
    monkeypatch.setattr(tests,'reasoner',baseline())
    with pytest.raises(AssertionError):
        tests.test_overflow_snapshot_preserves_more_current_prefix_than_a_fitting_old_anchor()

def test_original_mock_builder_missing_existing_capacity_callback(monkeypatch):
    from backend.nis.agent.orchestration import local_reasoner
    previous=baseline()
    monkeypatch.setattr(local_reasoner,'_reference_context_messages',previous._reference_context_messages)
    with pytest.raises(TypeError,match='capacity_check'):
        tests.test_planner_retains_bounded_original_and_recent_actual_native_anchors(monkeypatch)
