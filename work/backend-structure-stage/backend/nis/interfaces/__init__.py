"""HTTP, MCP and command-line entry points."""

from backend.nis.models import Capability

CAPABILITY = Capability(
    "interfaces", "External interfaces",
    ("backend.nis.interfaces.http.simulation", "backend.nis.interfaces.http.engineering", "backend.nis.interfaces.mcp", "backend.nis.interfaces.cli.standalone"),
    "Stable HTTP, MCP and CLI boundaries around application services.",
)
__all__ = ["CAPABILITY"]
