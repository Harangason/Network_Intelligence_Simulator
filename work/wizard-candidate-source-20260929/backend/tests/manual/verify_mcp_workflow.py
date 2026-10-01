"""Verify MCP -> shared application executor -> trace, on an isolated prepared project."""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from backend.agent_core.api.mcp_client import EngineeringMCPClient
from backend.engineering.agent_tools.runtime import ToolAuthority
from backend.simulator_engineering_mcp.server import create_server
from backend.engineering.db import close_pool

ROOT=Path(__file__).resolve().parents[2]/"test-output"


async def main():
    if not os.environ.get("SIMULATOR_JOB_API_URL") or not os.environ.get("ENGINEERING_TEST_DATABASE_URL"):
        raise RuntimeError("Explicit isolated job API and test database are required.")
    os.environ["DATABASE_URL"]=os.environ["ENGINEERING_TEST_DATABASE_URL"]
    project=json.loads((ROOT/"audit-flow-state.json").read_text(encoding="utf-8"))["project"]
    report={"project":project,"steps":[]}
    async with EngineeringMCPClient(create_server(ToolAuthority(project))) as client:
        async def call(name,args=None):
            result=await client.call(name,args)
            assert result.success,result.model_dump()
            report["steps"].append({"tool":name,"trace_id":result.trace_id,"status":result.status.value})
            return result.data
        await call("calculate_capacity")
        preflight=await call("validate_simulation_preflight")
        assert preflight["ready_for_simulation"]
        snapshot=await call("create_simulation_snapshot",{"configuration":{"duration_s":0.1,"max_events":100}})
        job=await call("start_simulation",{"snapshot_id":snapshot["id"]})
        duplicate=await client.call("start_simulation",{"snapshot_id":snapshot["id"]})
        assert duplicate.status=="CONFLICT",duplicate.model_dump()
        for _ in range(60):
            status=await call("get_simulation_status",{"job_id":job["id"]})
            if status["status"] not in {"queued","running"}:
                break
            await asyncio.sleep(0.5)
        assert status["status"]=="completed",status
        trace=await call("load_trace",{"job_id":job["id"]})
        assert trace["total"]>0,trace
        report["trace_events"]=trace["total"]
        await call("analyze_trace",{"job_id":job["id"],"configuration":{"duration_s":0.1}})
        (ROOT/"mcp-simulation-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report))


if __name__=="__main__":
    try:
        asyncio.run(main())
    finally:
        close_pool()
