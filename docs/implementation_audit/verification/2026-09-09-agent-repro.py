"""Read-only, isolated repros for the 2026-09-09 Agent audit.

Run from repository root with backend/.venv/Scripts/python.exe.
No live database access, inference, or canonical model mutation.
"""
import asyncio
import json
from pathlib import Path
import sys
import threading
from contextlib import contextmanager
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.agent_core.core.engineering_agent import EngineeringAgent
from backend.agent_core.api.tool_contract import ToolResult
from backend.agent_core.context.agent_context import AgentContext
from backend.engineering.agent_tools import conversation
from backend.engineering.project_context import activate_project, reset_project, current_project_id

scopes = []
token = activate_project("audit-actual-project")
thread = threading.Thread(target=lambda: scopes.append(current_project_id()))
thread.start()
thread.join()
reset_project(token)
print(json.dumps({"check": "heartbeat_thread_project_scope", "worker_project": scopes[0], "expected_project": "audit-actual-project"}))

state = {"run_id": "audit-run", "active_workload": "workload-existing", "questions": {}, "pending_approvals": []}

class Connection:
    def execute(self, *args):
        pass

@contextmanager
def database():
    yield Connection()

with patch.object(conversation, "read", lambda: state), patch.object(conversation, "write", lambda value: value), patch.object(conversation, "get_connection", database):
    conversation.record_event("audit-run", {"id": "progress", "type": "PROGRESS", "workload": {"completed": 1, "total": 12}})
print(json.dumps({"check": "progress_preserves_active_workload", "actual": state["active_workload"], "expected": "workload-existing"}))

class FakeClient:
    async def call(self, name, arguments=None):
        return ToolResult(data={"active_step": "engineering_model", "context": {}})

    async def tools(self):
        return []

class HallucinatingReasoner:
    async def next(self, messages, context, tools):
        return {"text": "Das Gateway wurde erfolgreich angelegt.", "calls": [], "assistant_message": {}}

result = asyncio.run(EngineeringAgent(FakeClient(), reasoner=HallucinatingReasoner()).run("Lege ein Gateway an.", AgentContext(active_project_id="audit-local")))
print(json.dumps({"check": "free_form_creation_without_tool", "status": result["status"], "text": result["text"], "tools": [item["tool"] for item in result["trace"]], "proposal_count": len(result["proposals"])}, ensure_ascii=False))
