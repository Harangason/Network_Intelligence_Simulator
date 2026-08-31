from __future__ import annotations

from engineering.tool_registry import get_engineering_tool, list_engineering_tools


def test_engineering_tool_registry_exposes_approval_boundaries_and_formats() -> None:
    tools = list_engineering_tools()

    assert len(tools) >= 10
    assert any(tool["id"] == "import.intelligent" for tool in tools)
    assert any(tool["id"] == "suggest.network_distribution" and tool["requires_approval"] for tool in tools)
    importer = get_engineering_tool("import.intelligent")
    assert {"arxml", "axml", "blf", "asc"}.issubset(set(importer["supported_formats"]))


def test_engineering_tool_registry_filters_for_agent_planning() -> None:
    approval_tools = list_engineering_tools(approval_required=True)
    automotive_imports = list_engineering_tools(category="import", industry="automotive")
    capacity_tools = list_engineering_tools(workflow_step="capacity_timing")

    assert approval_tools
    assert all(tool["requires_approval"] is True for tool in approval_tools)
    assert [tool["id"] for tool in automotive_imports] == ["import.intelligent"]
    assert {tool["id"] for tool in capacity_tools} >= {"analyze.capacity_timing", "validate.signal_sizing"}
