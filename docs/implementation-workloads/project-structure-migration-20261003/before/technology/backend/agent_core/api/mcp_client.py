"""The agent's only engineering access: a genuine negotiated MCP client."""
from __future__ import annotations
import asyncio
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
        return [{"name":tool.name,"description":tool.description,"input_schema":tool.input_schema,
                 "output_schema":tool.output_schema, "metadata":tool.meta or {},
                 "annotations":tool.annotations.model_dump() if tool.annotations else {}}
                for tool in result.tools]

    async def call(self, name: str, arguments: dict | None = None) -> ToolResult:
        try:
            response = await self.client.call_tool(name, {"request":arguments or {}})
        except (TimeoutError, asyncio.TimeoutError):
            # A timed-out mutation may have committed. Do not retry blindly.
            return ToolResult(success=False, status="TOOL_TIMEOUT", findings=[{
                "code": "TOOL_TIMEOUT", "message": f"Zeitlimit für {name} überschritten. Gespeicherten Zustand vor Wiederholung prüfen.",
                "retryable": False}])
        if response.structured_content:
            return ToolResult.model_validate(response.structured_content)
        definition = next((item for item in await self.tools() if item['name'] == name), None) if response.is_error else None
        missing = response.is_error and definition is None
        if response.is_error and definition:
            from jsonschema import Draft202012Validator
            errors = list(Draft202012Validator(definition['input_schema']).iter_errors({'request': arguments or {}}))
            if errors:
                return ToolResult(success=False, status='INVALID_INPUT', findings=[{
                    'code': 'INVALID_INPUT', 'field': list(error.absolute_path),
                    'reason': error.validator, 'message': error.message,
                    'expected_schema': error.schema,
                } for error in errors])
        return ToolResult(success=False,status="TOOL_NOT_FOUND" if missing else "INVALID_INPUT" if response.is_error else "INTERNAL_ERROR",
                          findings=[{"message":block.text} for block in response.content if hasattr(block,"text")])
