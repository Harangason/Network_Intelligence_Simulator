"""Use the application's single job executor across embedded, stdio and HTTP MCP.

Canonical model calculations stay local Python services. Long-running jobs are
owned by the existing application process, so every browser sees the same jobs.
"""
from __future__ import annotations
import json
import os
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from ..project_context import current_project_id
from ..repository import NotFoundError
from ..workflow.service import WorkflowConflictError


def job_api_base() -> str:
    explicit = os.environ.get("SIMULATOR_JOB_API_URL")
    if explicit:
        return explicit.rstrip("/")
    port = int(os.environ.get("FLASK_PORT", "15050"))
    if not 1 <= port <= 65535:
        raise ValueError("FLASK_PORT muss zwischen 1 und 65535 liegen.")
    return f"http://127.0.0.1:{port}/api"


def request_json(path: str, payload: dict | None = None):
    base = job_api_base()
    if urlparse(base).scheme not in {"http","https"}:
        raise ValueError("SIMULATOR_JOB_API_URL benötigt HTTP oder HTTPS.")
    request = Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"X-Project-ID":current_project_id(),"Content-Type":"application/json"})
    try:
        with urlopen(request,timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        detail = json.loads(error.read()).get("error",str(error))
        if error.code==404:
            raise NotFoundError(detail) from error
        if error.code==409:
            raise WorkflowConflictError(detail) from error
        raise ValueError(detail) from error


def job(job_id: str, *, metadata: bool = False):
    return request_json("/simulations/"+quote(job_id,safe="")+("?view=metadata" if metadata else ""))


def start(snapshot_id: str):
    return request_json("/simulations",{"workflow_snapshot_id":snapshot_id,"workflow_managed":True,"project_id":current_project_id()})


def stop(job_id: str):
    return request_json("/simulations/"+quote(job_id,safe="")+"/cancel",{})


def iter_trace(job_id: str):
    item = job(job_id)
    for artifact in item.get("artifact_downloads") or []:
        if artifact.get("name","").endswith("universal_trace.jsonl"):
            base=job_api_base()
            request=Request(base+f"/simulations/{quote(job_id,safe='')}/artifacts/{int(artifact['index'])}",headers={"X-Project-ID":current_project_id()})
            with urlopen(request,timeout=30) as response:
                for line in response:
                    if line.strip():
                        yield json.loads(line)
            return
    yield from ((item.get("result") or {}).get("model_simulation") or {}).get("frames") or []


def trace(job_id: str) -> list[dict]:
    events = []
    for event in iter_trace(job_id):
        if len(events) == 100000:
            raise ValueError("Für große Traces get_trace_window nutzen und das begrenzte Fenster analysieren.")
        events.append(event)
    return events
