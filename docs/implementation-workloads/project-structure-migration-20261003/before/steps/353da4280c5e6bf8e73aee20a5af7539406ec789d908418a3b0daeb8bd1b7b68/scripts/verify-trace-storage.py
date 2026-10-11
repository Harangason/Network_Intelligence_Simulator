"""Live trace-storage acceptance. Uses only a dedicated QA project, no production model edits."""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--expected-path", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert args.project.startswith("astra-storage-"), "Only isolated storage QA projects are allowed."
    base = "http://127.0.0.1:13500"

    def request(path, payload=None, method=None):
        req = Request(base + path, method=method or ("GET" if payload is None else "POST"),
                      headers={"Content-Type": "application/json", "X-Project-ID": args.project,
                               "X-NetworkIS-Storage": "confirmed"},
                      data=None if payload is None else json.dumps(payload).encode())
        with urlopen(req, timeout=30) as response:
            return json.load(response)

    settings = request("/api/storage/settings")
    assert settings["resolved_path"] == args.expected_path, settings
    job = request("/api/simulations", {"project_id": args.project, "technology": "can_fd", "node_count": 2,
                  "duration_s": 0.02, "cycle_ms": 10, "formats": ["universal-jsonl", "universal-csv"]})
    for _ in range(120):
        job = request("/api/simulations/" + job["id"])
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.25)
    assert job["status"] == "completed", job
    assert job["output_dir"] == args.expected_path + "/" + job["id"], job["output_dir"]
    trace = request(f'/api/simulations/{job["id"]}/trace-window?limit=5')
    assert trace["count"] > 0, trace
    request("/api/storage/settings", {"path": None}, "PUT")
    after_reset = request(f'/api/simulations/{job["id"]}/trace-window?limit=5')
    assert after_reset["events"] == trace["events"]
    artifact = next(i for i, path in enumerate(job["result"]["artifacts"]) if path.endswith("universal_trace.jsonl"))
    req = Request(f'{base}/api/simulations/{job["id"]}/artifacts/{artifact}', headers={"X-Project-ID": args.project})
    with urlopen(req, timeout=30) as response:
        assert response.status == 200 and response.read(1)
    # Retain the tested choice in this QA project so the settings page demonstrates it.
    request("/api/storage/settings", {"path": args.expected_path}, "PUT")
    report = {"project": args.project, "job_id": job["id"], "output_dir": job["output_dir"],
              "artifacts": job["result"]["artifacts"], "trace_records_checked": trace["count"],
              "old_trace_and_download_after_reset": True, "status": "passed"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
