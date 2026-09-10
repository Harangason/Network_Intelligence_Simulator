"""Single registry of callable Python capabilities and their MCP input schemas."""
from __future__ import annotations

from dataclasses import dataclass
from backend.agent_core.context.limits import MAX_REQUIREMENT_LENGTH
from typing import Any, Callable
from pydantic import BaseModel, ConfigDict, Field, create_model
from backend.agent_core.api.tool_contract import Permission


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    permission: Permission
    input_model: type[BaseModel]
    handler: Callable[[dict], Any]


TOOLS: dict[str, ToolDefinition] = {}


def register(tool_name: str, description: str, permission: Permission, handler: Callable, **fields) -> None:
    name = tool_name
    if name in TOOLS:
        raise RuntimeError(f"Doppeltes Engineering-Werkzeug: {name}")
    schema = create_model("".join(part.title() for part in name.split("_"))+"Input", __base__=StrictInput, **fields)
    TOOLS[name] = ToolDefinition(name, description, permission, schema, handler)


ID = (str, Field(min_length=1, max_length=200))
TEXT = (str, Field(min_length=1, max_length=30000))
PROMPT = (str, Field(min_length=1, max_length=MAX_REQUIREMENT_LENGTH))
OBJECT = (dict[str, Any], ...)
OPTIONAL_OBJECT = (dict[str, Any], Field(default_factory=dict))
ITEMS = (list[dict[str, Any]], Field(min_length=1, max_length=2000))
COUNT = (int, Field(default=1, ge=1, le=100))
LIMIT = (int, Field(default=100, ge=1, le=1000))
TECHNOLOGY = (str, "CAN_FD")
