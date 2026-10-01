from __future__ import annotations

import pytest

from backend.engineering.performance_governance import (
    CACHE_POLICIES,
    INVENTORY,
    LARGE_OBJECT_THRESHOLD_BYTES,
    MEMORY_BUDGETS,
    assert_within_budget,
    performance_governance_summary,
)


def test_performance_governance_inventory_covers_required_layers() -> None:
    layers = {entry.layer for entry in INVENTORY}
    assert {
        "Browser",
        "React State",
        "Frontend Query Cache",
        "Global Frontend Store",
        "WebSocket Buffer",
        "Canvas/Graph Renderer",
        "Backend Process RAM",
        "Python Cache",
        "Redis",
        "Database",
        "Artifact Store",
    }.issubset(layers)


def test_cache_policies_are_bounded() -> None:
    assert CACHE_POLICIES
    for policy in CACHE_POLICIES:
        assert policy.max_entries > 0
        assert policy.max_value_bytes > 0
        assert policy.eviction_policy
        assert policy.key_template
        if "ttl" in policy.eviction_policy:
            assert policy.ttl_seconds > 0


def test_memory_budgets_have_actionable_limits() -> None:
    assert LARGE_OBJECT_THRESHOLD_BYTES == 1_000_000
    for budget in MEMORY_BUDGETS:
        assert budget.soft_limit_bytes > 0
        assert budget.hard_limit_bytes >= budget.soft_limit_bytes
        assert budget.enforcement
        assert budget.remediation


def test_budget_assertion_rejects_oversized_payload() -> None:
    budget = next(item for item in MEMORY_BUDGETS if item.name == "workflow_state_response")
    with pytest.raises(ValueError, match="workflow_state_response"):
        assert_within_budget("workflow_state_response", budget.hard_limit_bytes + 1)


def test_governance_summary_is_api_ready() -> None:
    summary = performance_governance_summary()
    assert summary["principle"]
    assert summary["memory_budgets"]
    assert summary["cache_policies"]
    assert summary["inventory"]
    assert summary["projection_limits"]["matrix_visible_rows"]["soft"] == 50
