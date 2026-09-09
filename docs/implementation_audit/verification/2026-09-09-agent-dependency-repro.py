"""Read-only dependency inspection; no package install or removal.

Simulate only a missing external MCP import and call the real app factory.
"""
import importlib.abc
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import tomllib

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
lock = tomllib.loads((root / "backend/uv.lock").read_text())
packages = lock["package"]
by_name = {package["name"]: package for package in packages}
print(json.dumps({
    "check": "locked_dependencies",
    "lock_package_count": len(packages),
    "mcp_in_lock": "mcp" in by_name,
    "httpx_in_lock": "httpx" in by_name,
    "openai_dependencies": [item["name"] for item in by_name.get("openai", {}).get("dependencies", [])],
}))
for name in ("mcp", "httpx"):
    print(json.dumps({"module": name, "module_origin": importlib.util.find_spec(name).origin, "installed_version": importlib.metadata.version(name)}))

class MissingMCP(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mcp" or fullname.startswith("mcp."):
            raise ModuleNotFoundError("No module named 'mcp'", name="mcp")

sys.meta_path.insert(0, MissingMCP())
try:
    from backend.app import create_app
    create_app(testing=True)
    print(json.dumps({"check": "app_start_without_mcp", "unexpected_success": True}))
except ModuleNotFoundError as error:
    print(json.dumps({"check": "app_start_without_mcp", "exception": type(error).__name__, "message": str(error), "missing": error.name}))
