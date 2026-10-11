"""Real HTTP reasoning acceptance against an explicitly isolated wizard QA project.

Creates short baseline/fault/replay runs via canonical frozen snapshots. Never
changes a production project, fabricates traces or approves architecture changes.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wizard-report", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:13500")
    args = parser.parse_args()
    wizard = json.loads(args.wizard_report.read_text(encoding="utf-8"))
    project = wizard["project"]
    assert project.startswith("astra-e2e-"), "Writes are restricted to isolated QA projects"
    evidence = []

    def request(path, payload=None, expected=200, project_id=None):
        started = time.monotonic()
        req = Request(args.base_url + path, method="GET" if payload is None else "POST",
            headers={"X-Project-ID": project_id or project, "Content-Type": "application/json"},
            data=None if payload is None else json.dumps(payload).encode())
        try:
            response = urlopen(req, timeout=45)
        except HTTPError as error:
            response = error
        with response:
            data = json.load(response)
            evidence.append({"path": path, "method": req.method, "status": response.status, "seconds": round(time.monotonic()-started, 3)})
            assert response.status == expected, (path, response.status, data)
        return data

    initial = request("/api/simulations/" + wizard["job_id"])
    original = request("/api/engineering/workflow/simulation-snapshots/" + initial["workflow_snapshot_id"])
    configuration = deepcopy(original["configuration"])
    for key in ("output_dir", "job_id", "workflow_snapshot_id"):
        configuration.pop(key, None)
    configuration.update(duration_s=.1, seed=42)
    configuration["scenario"] = {"mode": "NORMAL", "faults": []}

    def simulate(config):
        preflight = request("/api/engineering/preflight", {})
        assert preflight["status"] in {"COMPLETE", "WARNING", "APPROVED"}, preflight
        snapshot = request("/api/engineering/workflow/simulation-snapshots", {"configuration": config}, expected=201)
        job = request("/api/simulations", {"workflow_snapshot_id": snapshot["id"], "workflow_managed": True, "project_id": project}, expected=202)
        job_id = job["id"]
        for _ in range(45):
            job = request("/api/simulations/" + job_id)
            if job["status"] in {"completed", "failed", "canceled"}:
                break
            time.sleep(1)
        assert job["status"] == "completed", job.get("error")
        return job_id

    golden_job = simulate(configuration)
    golden = request("/api/engineering/reasoning", {"job_id": golden_job}, expected=201)
    trace = request(f"/api/simulations/{golden_job}/trace-window?limit=5")
    target = trace["events"][0]["message_ids"][0]
    fault_configuration = deepcopy(configuration)
    fault_configuration["scenario"] = {"mode": "USER_DEFINED_FAULT", "faults": [{
        "type": "MESSAGE_LOSS", "scope": "MESSAGE", "target": {"id": target}, "start_s": .02, "end_s": .06}]}
    fault_job = simulate(fault_configuration)
    fault = request("/api/engineering/reasoning", {"job_id": fault_job, "golden_job_id": golden_job}, expected=201)
    assert fault["completion_status"] == "COMPLETE", {"gaps": fault["data_gaps"], "hypotheses": fault["hypotheses"]}
    assert fault["confirmed_causes"] and any(item["code"] == "FAULT_EFFECT_CHAIN" for item in fault["findings"])
    assert fault["comparison"]["first_credible_causal_deviation"], fault["comparison"]
    identifier = fault["reasoning_id"]
    assert request("/api/engineering/reasoning/" + identifier)["reasoning_id"] == identifier
    request("/api/engineering/reasoning/" + identifier, project_id="astra-e2e-other", expected=404)
    request("/api/engineering/reasoning/" + identifier + "/continue", {}, expected=409)
    request("/api/engineering/reasoning", {"job_id": fault_job, "cursor": -1}, expected=400)
    request("/api/engineering/reasoning/" + identifier + "/proposal", {"action_id": "measurement"}, expected=400)
    replay_job = simulate(configuration)
    replay = request("/api/engineering/reasoning", {"job_id": replay_job}, expected=201)
    stale = request("/api/engineering/reasoning/" + identifier)
    assert stale["validation_status"] == "STALE"
    request("/api/engineering/reasoning/" + identifier + "/proposal", {"action_id": "capacity-repair"}, expected=409)
    comparison = request("/api/engineering/reasoning/compare", {"before_reasoning_id": identifier, "after_reasoning_id": replay["reasoning_id"]})
    assert comparison["status"] == "IMPROVEMENT_NOT_VERIFIED" and not comparison["comparable_scenario_seed_duration"]
    # A repeat with identical input is not silently labelled an improvement either.
    unchanged = request("/api/engineering/reasoning/compare", {"before_reasoning_id": golden["reasoning_id"], "after_reasoning_id": replay["reasoning_id"]})
    assert unchanged["status"] == "IMPROVEMENT_NOT_VERIFIED"
    report = {"project": project, "golden_job": golden_job, "fault_job": fault_job, "replay_job": replay_job,
        "reasoning_id": identifier, "conclusion": fault["conclusion"], "completion": fault["completion_status"],
        "first_credible_causal_deviation": fault["comparison"]["first_credible_causal_deviation"],
        "false_repair_rejected": comparison, "http": evidence,
        "browser_url": args.base_url + f"/trace-analysis?project={project}&job={fault_job}&view=root-cause"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
