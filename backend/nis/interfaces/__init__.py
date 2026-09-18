"""HTTP, MCP and command-line entry points."""

from ..models import Capability

CAPABILITY = Capability(
    "interfaces", "External interfaces",
    ("backend.app.api", "backend.engineering.api", "backend.simulator_engineering_mcp", "backend.simulator.standalone_cli"),
    "Stable HTTP, MCP and CLI boundaries around application services.",
)
__all__ = ["CAPABILITY"]
