"""python -m backend.simulator_engineering_mcp --project PROJECT [--transport streamable-http]."""
from __future__ import annotations
import argparse
from backend.agent_core.api.tool_contract import Permission
from backend.engineering.agent_tools.runtime import ToolAuthority, DEFAULT_PERMISSIONS
from .server import create_server


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
        from backend.engineering.db import close_pool
        close_pool()


if __name__ == "__main__":
    main()
