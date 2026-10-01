"""Official SDK HTTP contract/discovery check against an explicit test server."""
import asyncio
import json
import os
import re
from pathlib import Path
from mcp import Client
from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.engineering.agent_tools.services import TOOLS


async def main():
    url = os.environ["SIMULATOR_TEST_MCP_URL"]
    project = os.environ["SIMULATOR_TEST_MCP_PROJECT"]
    source = Path("docs/SIMULATOR_ENGINEERING_AGENT_MCP_ARCHITECTURE_CODEX.md").read_text(encoding="utf-8")
    forbidden = {"delete_anything", "update_any_object"}
    names = sorted(set(re.findall(r"^([a-z][a-z0-9_]+)\(\)", source, re.M))-forbidden)
    assert not (set(names)-set(TOOLS)), sorted(set(names)-set(TOOLS))
    assert not (forbidden & set(TOOLS))
    async with EngineeringMCPClient(url) as client:
        tools = await client.tools()
        assert {tool["name"] for tool in tools} == set(TOOLS)
        load = await client.call("calculate_bus_load", {"technology": "CAN_FD", "payload_bytes": 64, "cycle_ms": 10})
        assert load.success, load
    resources = [f"simulator://project/{project}"+suffix for suffix in ["", "/model", "/hardware", "/functions", "/interfaces", "/hardware-interfaces", "/signals", "/messages", "/networks", "/routing", "/findings"]]
    resources += ["simulator://schemas/"+kind for kind in ["signal", "message", "function", "hardware-interface"]]
    resources += ["simulator://technologies/can-fd", "simulator://device-classes"]
    async with Client(url) as client:
        for resource in resources:
            response = await client.read_resource(resource)
            value = json.loads(response.contents[0].text)
            assert not isinstance(value, dict) or value.get("success", True), value
    report = {"transport": "streamable-http", "tool_count": len(tools), "specified_tool_names": names, "missing_tools": [], "forbidden_tools_absent": sorted(forbidden), "resources": resources, "bus_load_result": load.model_dump(mode="json")}
    Path("backend/test-output/mcp-http-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"tool_count": len(tools), "specified_tools": len(names), "resources": len(resources)}))


if __name__ == "__main__":
    asyncio.run(main())
