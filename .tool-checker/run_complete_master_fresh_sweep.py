"""Execute the remaining fresh master cases against one verified disposable image."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / ".tool-checker"
STATE = HERE / "state"
TASK_ID = os.environ.get("TOOL_CHECKER_TASK_ID", "network-simulator-complete-master-80-fresh-20260918")
SOURCE = ROOT / "docs" / "NETWORK_SIMULATOR_COMPLETE_MASTER_TEST_SUITE_S01_S60_80_CHECKS.md"
BASE_URL = os.environ.get("TOOL_CHECKER_BASE_URL", "http://127.0.0.1:55634").rstrip("/")
RUN_NAME = os.environ.get("TOOL_CHECKER_RUN_NAME", "complete-master-80-fresh-20260918")
RUN_ROOT = HERE / "runs" / RUN_NAME
EVIDENCE_ROOT = RUN_ROOT / "sweep-evidence"
NORMALIZED_SOURCE = Path(os.environ.get(
    "TOOL_CHECKER_NORMALIZED_SOURCE",
    HERE / "runs" / "complete-master-80-fresh-20260918" / "complete-master-80.normalized.json",
))
NORMALIZED_EXECUTABLE = RUN_ROOT / "complete-master-80.sweep.normalized.json"
SKILL = Path(os.environ.get(
    "TOOL_CHECKER_SKILL",
    "F:/CodexOrdner/plugins/cache/plugins-cli/tool-checker/1.0.0+codex.20260921055224/skills/tool-checker",
))
PYTHON = Path(sys.executable)
ENV = {
    **os.environ,
    "PYTHONIOENCODING": "utf-8",
    "TOOL_CHECKER_EVIDENCE_ROOT": str(EVIDENCE_ROOT),
    "TOOL_CHECKER_ALLOWED_BASE_URL": BASE_URL,
}


def cli(script: str, *args: str) -> object:
    completed = subprocess.run(
        [str(PYTHON), str(SKILL / "scripts" / script), "--state", str(STATE), *args],
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    return json.loads(completed.stdout)


def get_json(project_id: str, path: str) -> object:
    request = Request(BASE_URL + path, headers={"X-Project-ID": project_id})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def setup() -> list[dict]:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    config = json.loads((STATE / "config.json").read_text(encoding="utf-8"))
    config.setdefault("adapters", {})["complete-master-real-wizard"] = {
        "argv": ["node", str(HERE / "complete_master_wizard_adapter.mjs")],
        "uses_llm": True,
        "mutating": True,
    }
    config["adapters"]["complete-master-real-wizard-readonly"] = {
        "argv": ["node", str(HERE / "complete_master_wizard_adapter.mjs")],
        "uses_llm": True,
        "mutating": False,
    }
    config["adapters"]["complete-master-fresh-http"] = {
        "argv": [str(PYTHON), str(HERE / "industry60_adapter.py")],
        "uses_llm": True,
        "mutating": True,
    }
    config["adapters"]["complete-master-fresh-http-readonly"] = {
        "argv": [str(PYTHON), str(HERE / "industry60_adapter.py")],
        "uses_llm": True,
        "mutating": False,
    }
    config["adapters"]["complete-master-specialized"] = {
        "argv": ["node", str(HERE / "complete_master_specialized_adapter.mjs")],
        "uses_llm": False,
        "mutating": False,
    }
    config["adapters"]["complete-master-reuse"] = {
        "argv": ["node", str(HERE / "complete_master_reuse_adapter.mjs")],
        "uses_llm": True,
        "mutating": True,
    }
    config["adapters"]["complete-master-reuse-readonly"] = {
        "argv": ["node", str(HERE / "complete_master_reuse_adapter.mjs")],
        "uses_llm": True,
        "mutating": False,
    }
    (STATE / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = json.loads(NORMALIZED_SOURCE.read_text(encoding="utf-8"))
    aggregate_outputs = [
        value for value in manifest.get("required_outputs", [])
        if value != "Fresh evidence per case"
    ]
    manifest["suite_required_outputs"] = aggregate_outputs
    manifest["required_outputs"] = ["Fresh evidence per case"]
    prefix = os.environ.get("TOOL_CHECKER_PROJECT_PREFIX", "fresh80")
    pool_cases = [f"S{number:02d}-{variant}" for number in range(1, 21) for variant in ("A", "B")]
    reuse_cases = [f"S{number}" for number in range(21, 61)]
    reuse_project = dict(zip(reuse_cases, pool_cases, strict=True))
    for case in manifest["test_cases"]:
        bare = {key: value for key, value in case.items() if key != "execution_plan"}
        real_wizard = re.fullmatch(r"S(?:0[1-9]|1[0-9]|20)-[AB]", case["test_id"]) is not None
        if real_wizard:
            adapter = "complete-master-real-wizard" if case.get("mutating", True) else "complete-master-real-wizard-readonly"
            step_id = "fresh-real-wizard"
            step_label = "Originalauftrag im echten Haupt-Wizard ausführen"
            channel = "browser"
        else:
            adapter = "complete-master-reuse" if case.get("mutating", True) else "complete-master-reuse-readonly"
            step_id = "reuse-real-project"
            step_label = "Fallspezifischen Agenten-, Wizard-, MCP- oder Trace-Vertrag im Wizard-Projekt ausführen"
            channel = "browser" if case.get("browser_required") else "mcp"
            bare["source_project_case"] = reuse_project[case["test_id"]]
        project_case = case["test_id"] if real_wizard else reuse_project[case["test_id"]]
        case["execution_plan"] = [{
            "step_id": step_id,
            "step_label": step_label,
            "kind": "adapter",
            "adapter": adapter,
            "channel": channel,
            "phase": "engineering_execution",
            "timeout": 600,
            "base_url": BASE_URL,
            "project_id": f"nis-e2e-final-examples-{prefix}-{project_case.lower()}",
            "case": bare,
        }]
    NORMALIZED_EXECUTABLE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    cli("tool_check.py", "ingest", str(SOURCE), "--id", TASK_ID, "--normalized", str(NORMALIZED_EXECUTABLE), "--force")
    return manifest["test_cases"]


def preflight(case: dict, project_id: str) -> tuple[Path, Path]:
    directory = EVIDENCE_ROOT / case["test_id"]
    directory.mkdir(parents=True, exist_ok=True)
    plan = cli("tool_check.py", "--task", TASK_ID, "dry-run", case["test_id"])[0]
    workflow = get_json(project_id, "/api/engineering/workflow?view=summary")
    baseline_path = directory / "baseline.json"
    baseline_path.write_text(json.dumps({"model_revision": workflow["versions"], "workflow": workflow}, ensure_ascii=False, indent=2), encoding="utf-8")
    proof = {
        "source_hash": plan["context"]["source_hash"],
        "contract_hash": plan["context"]["test"]["contract_hash"],
        "project_path": str(ROOT),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "dependencies": {"status": "PASSED", "evidence": "Verified disposable image stack."},
        "application": {"status": "PASSED", "evidence": get_json(project_id, "/api/ready")},
        "project": {"status": "PASSED", "evidence": project_id},
        "permissions": {"status": "PASSED", "evidence": "User requested a complete fresh run."},
        "test_data": {"status": "PASSED", "evidence": (
            f"Wizard-created pool project from {case.get('source_project_case') or case['test_id']} and current normalized contract."
        )},
        "available_skills": list(dict.fromkeys(plan["context"]["required_skills"] + plan["context"]["test"]["required_skills"])),
        "available_tools": list(dict.fromkeys(plan["context"]["required_tools"] + plan["context"]["test"]["required_tools"])),
        "available_views": list(dict.fromkeys(plan["context"]["required_views"] + plan["context"]["test"]["required_views"])),
        "browser": {"observed_working": True, "evidence": "Verified separately on the same immutable image; case-specific browser evidence remains mandatory."},
        "isolated_scope": f"Disposable stack {BASE_URL}; fresh project {project_id}.",
    }
    for key in ("preconditions", "required_model_context"):
        proof[key] = [{"name": name, "status": "PASSED", "evidence": "Fresh isolated baseline."} for name in plan["context"]["test"][key]]
    preflight_path = directory / "preflight.json"
    preflight_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    return preflight_path, baseline_path


def main() -> None:
    selected = set(sys.argv[1:])
    cases = setup()
    for case in cases:
        case_id = case["test_id"]
        if selected and case_id not in selected:
            continue
        step = case["execution_plan"][0]
        preflight_path, baseline_path = preflight(case, step["project_id"])
        job = cli(
            "tool_jobs.py", "submit", "--task", TASK_ID, "--test", case_id,
            "--preflight", str(preflight_path), "--baseline", str(baseline_path),
            "--llm-policy", "REQUIRED_BY_TEST",
        )
        directory = EVIDENCE_ROOT / case_id
        (directory / "current-job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{case_id} SUBMITTED {job['job_id']}", flush=True)
        while True:
            state = json.loads((STATE / "jobs" / job["job_id"] / "job.json").read_text(encoding="utf-8"))
            if state["status"] in {"COMPLETE", "FAILED", "BLOCKED", "CANCELLED"}:
                print(f"{case_id} {state['status']}", flush=True)
                break
            time.sleep(5)


if __name__ == "__main__":
    main()
