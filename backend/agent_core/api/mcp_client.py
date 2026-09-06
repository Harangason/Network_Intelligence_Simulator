"""The agent's only engineering access: a genuine negotiated MCP client."""
from __future__ import annotations
from mcp import Client
from .tool_contract import ToolResult


class EngineeringMCPClient:
    def __init__(self, server):
        self.client = Client(server, read_timeout_seconds=240)

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self.client.__aexit__(*args)

    async def tools(self) -> list[dict]:
        result = await self.client.list_tools()
        return [{"name":tool.name,"description":tool.description,"input_schema":tool.input_schema} for tool in result.tools]

    async def call(self, name: str, arguments: dict | None = None) -> ToolResult:
        response = await self.client.call_tool(name, {"request":arguments or {}})
        if response.structured_content:
            return ToolResult.model_validate(response.structured_content)
        return ToolResult(success=False,status="INVALID_INPUT" if response.is_error else "INTERNAL_ERROR",
                          findings=[{"message":block.text} for block in response.content if hasattr(block,"text")])
