"""python -m backend.nis.interfaces.mcp --project PROJECT [--transport streamable-http]."""
from __future__ import annotations

# Direct file entrypoints resolve the installed/source package independently of cwd.
import sys as _cli_sys
from pathlib import Path as _CliPath
_cli_backend = next(p for p in _CliPath(__file__).resolve().parents if p.name == "backend")
_cli_sys.path.insert(0, str(_cli_backend.parent))
import argparse
from backend.nis.agent.api.tool_contract import Permission
from backend.nis.agent.tools.runtime import ToolAuthority
from backend.nis.agent.tools.runtime import DEFAULT_PERMISSIONS
from backend.nis.interfaces.mcp.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Project-bound Simulator Engineering MCP server")
    parser.add_argument("--project", required=True)
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=15052)
    parser.add_argument("--allow-apply-approved", action="store_true", help="Allow apply only after human review in the Simulator UI")
    parser.add_argument("--allow-delete-proposals", action="store_true")
    args = parser.parse_args()
    permissions = set(DEFAULT_PERMISSIONS)
    if args.allow_apply_approved:
        permissions.add(Permission.APPLY_APPROVED_PROPOSAL)
    if args.allow_delete_proposals:
        permissions.add(Permission.DELETE_WITH_IMPACT_ANALYSIS)
    server = create_server(ToolAuthority(args.project, "external-mcp-client", frozenset(permissions)))
    try:
        if args.transport == "stdio":
            server.run("stdio")
        else:
            server.run("streamable-http", host="127.0.0.1", port=args.port)
    finally:
        from backend.nis.infrastructure.persistence.db import close_pool
        close_pool()


if __name__ == "__main__":
    main()
