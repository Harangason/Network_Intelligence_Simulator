"""Pure, deterministic progress model. No model clients or network calls."""
from __future__ import annotations
import math
from tool_check import ident, now

PHASES = {"preflight":5, "browser_setup":5, "agent_start":10, "model_inspection":10,
          "engineering_execution":25, "routing_capacity":15, "timing_validation":15,
          "evidence":10, "completion":5}
MODES = {"SILENT", "PROGRESS", "VERBOSE"}
POLICIES = {"DISABLED", "ON_DEMAND", "REQUIRED_BY_TEST"}
TERMINAL = {"COMPLETE", "FAILED", "BLOCKED", "CANCELLED"}
KINDS = {"file", "json", "http", "adapter", "decision", "browser"}
AUTO = [
    {"step_id":"_preflight", "step_label":"Preflight", "phase":"preflight"},
    {"step_id":"_evidence", "step_label":"Evidence wird gespeichert", "phase":"evidence"},
    {"step_id":"_completion", "step_label":"Completion wird geprüft", "phase":"completion"},
]

def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0

def plan_for(case):
    source = case.get("execution_plan")
    if not isinstance(source, list) or not source:
        raise ValueError("Background execution requires a reviewed execution_plan")
    plan = [dict(AUTO[0])]
    for item in source:
        step = dict(item)
        ident(step.get("step_id"))
        if step["step_id"].startswith("_"):
            raise ValueError("Reserved step ID")
        if not isinstance(step.get("step_label"), str) or not step["step_label"].strip():
            raise ValueError("Step labels must come from the saved plan")
        if step.get("phase") not in PHASES:
            raise ValueError("Unknown phase")
        if step.get("kind") not in KINDS:
            raise ValueError("Unsupported deterministic step kind")
        step.setdefault("weight", 1)
        if not positive(step["weight"]):
            raise ValueError("Invalid step weight")
        if step["kind"] == "decision":
            if not isinstance(step.get("question"),str) or not step["question"].strip():
                raise ValueError("Decision requires a question")
            options = step.get("options")
            if not isinstance(options,list) or len(options)<2 or any(not isinstance(x,str) or not x for x in options) or len(set(options))!=len(options):
                raise ValueError("Decision requires distinct options")
        if step["kind"] in ("file","json") and not isinstance(step.get("path"),str):
            raise ValueError("File step needs path")
        if step["kind"] == "json" and "equals" not in step:
            raise ValueError("JSON assertion needs equals")
        if step["kind"] == "adapter" and not isinstance(step.get("adapter"),str):
            raise ValueError("Adapter step needs registered adapter")
        if step["kind"] == "browser":
            import sys
            from pathlib import Path
            sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"adapters"))
            from browser_runner import validate_step
            validate_step(step)
        plan.append(step)
    plan += [dict(x) for x in AUTO[1:]]
    ids = [x["step_id"] for x in plan]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate progress step IDs")
    weights = case.get("phase_weights", PHASES)
    if not isinstance(weights,dict) or set(weights) != set(PHASES) or any(not positive(x) for x in weights.values()):
        raise ValueError("phase_weights must define positive finite weights for every phase")
    return plan, weights

def percentage(plan, completed, phase_weights, weighted=True, complete=False):
    done = set(completed)
    if plan and {s["step_id"] for s in plan}.issubset(done):
        return 100.0
    if not weighted:
        value = len(done & {x["step_id"] for x in plan}) / len(plan) * 100
    else:
        phases = {x["phase"] for x in plan}
        denominator = sum(phase_weights[x] for x in phases)
        value = 0.0
        for phase in phases:
            steps = [s for s in plan if s["phase"] == phase]
            fraction = sum(s.get("weight",1) for s in steps if s["step_id"] in done) / sum(s.get("weight",1) for s in steps)
            value += phase_weights[phase] * fraction / denominator * 100
    return min(99.0, round(value, 1))

def event(job, kind, step=None):
    step = step or {}
    return {"event":kind, "run_id":job["run_id"], "test_id":job["test_id"],
            "phase":step.get("phase",job.get("phase","preflight")),
            "step_id":step.get("step_id",job.get("step_id","_preflight")),
            "step_label":step.get("step_label",job.get("current_step","Preflight")),
            "completed_steps":len(job["completed_step_ids"]), "total_steps":len(job["plan"]),
            "percentage":percentage(job["plan"],job["completed_step_ids"],job["phase_weights"],
                job["weighted"],job["status"]=="COMPLETE"),
            "status":job["status"], "timestamp":now()}

def public_job(job):
    keys = ("job_id","task_id","test_id","run_id","status","phase","percentage","current_step",
            "completed_steps","total_steps","started_at","updated_at","finished_at","result_ref",
            "output_mode","decision","batch_id","message","metrics","cancel_requested","test_weight")
    return {k:job.get(k) for k in keys}

def batch_progress(jobs):
    counts = {s:sum(j["status"]==s for j in jobs) for s in TERMINAL}
    total = len(jobs)
    finished = sum(counts.values())
    weights = sum(j.get("test_weight",1) for j in jobs)
    value = sum(j.get("test_weight",1)*j["percentage"] for j in jobs)/weights if weights else 0
    complete = bool(jobs) and all(j.get("percentage")==100 for j in jobs)
    status = "COMPLETE" if counts["COMPLETE"] == total and total else "FAILED" if finished==total and counts["FAILED"] else "BLOCKED" if finished==total and counts["BLOCKED"] else "CANCELLED" if finished==total else "RUNNING"
    return {"status":status, "percentage":100.0 if complete else min(99.0,round(value,1)),
            "completed_tests":finished,"total_tests":total,"counts":counts}
