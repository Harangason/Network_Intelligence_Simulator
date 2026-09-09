"""Read-only comparison of audit-relevant workspace and running container code."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
DOCKER = r"C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"
FILES = [
    "backend/engineering/workflow/service.py",
    "backend/engineering/agent_tools/api.py",
    "backend/engineering/agent_tools/wizard_generation.py",
    "backend/engineering/routing/config_builder.py",
    "backend/app/runtime_analysis.py",
    "backend/simulator/communication_simulator.py",
    "frontend/src/components/agent-chat-core.tsx",
    "frontend/src/components/engineering-workbench.tsx",
    "frontend/src/components/structure-tree-workbench.tsx",
    "frontend/src/lib/agent/proposal-client.ts",
]
script = (
    "from pathlib import Path; import hashlib,json; "
    f"files={FILES!r}; "
    "print(json.dumps({f:hashlib.sha256(Path(f).read_text(encoding='utf-8').encode()).hexdigest() "
    "if Path(f).exists() else None for f in files}))"
)
runtime = json.loads(subprocess.check_output(
    [DOCKER, "exec", "-w", "/app", "NetworkIS", "python", "-c", script], text=True
))
container = json.loads(subprocess.check_output([
    DOCKER, "inspect", "NetworkIS", "--format",
    '{"image":{{json .Image}},"started_at":{{json .State.StartedAt}},"mounts":{{json .Mounts}}}',
], text=True))
rows = []
for file in FILES:
    path = ROOT / file
    local = hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest() if path.exists() else None
    rows.append({"file": file, "workspace_sha256": local, "runtime_sha256": runtime[file], "equal": local == runtime[file]})
result = {"normalization": "UTF-8 text, universal newline conversion", "container": container, "files": rows}
output = Path(__file__).with_suffix(".json")
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"output": str(output), "equal": sum(r["equal"] for r in rows), "different": [r["file"] for r in rows if not r["equal"]]}))
