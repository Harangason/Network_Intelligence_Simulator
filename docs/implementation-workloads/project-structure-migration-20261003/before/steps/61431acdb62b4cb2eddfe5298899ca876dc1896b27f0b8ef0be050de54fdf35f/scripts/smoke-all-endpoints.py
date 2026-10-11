#!/usr/bin/env python3
"""Exercise every registered Flask API method against a running simulator.

The smoke test deliberately uses an isolated project id and invalid/sentinel
object ids. Validation and not-found responses are acceptable; a 5xx response,
connection failure, or timeout is not. This verifies that every route can be
dispatched without turning the smoke run into a destructive data fixture.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app import create_app  # noqa: E402
from backend.engineering.api import RESOURCES  # noqa: E402


SENTINEL_ID = "00000000-0000-0000-0000-000000000000"
VARIABLE_RE = re.compile(r"<(?:(?P<converter>[^:>]+):)?(?P<name>[^>]+)>")


def route_paths(rule: str) -> Iterable[str]:
    resources = sorted(RESOURCES) if "<resource>" in rule else [None]
    for resource in resources:
        def replace(match: re.Match[str]) -> str:
            converter = match.group("converter")
            name = match.group("name")
            if name == "resource":
                return str(resource)
            if converter == "int":
                return "0"
            if converter == "path":
                return "smoke-missing.txt"
            if name == "address":
                return "0"
            if name == "tool_id":
                return "smoke-missing"
            return SENTINEL_ID

        yield VARIABLE_RE.sub(replace, rule)


def request_payload(path: str, project_id: str) -> dict[str, object]:
    # Never enqueue simulation work merely to prove that its HTTP route exists.
    if path in {"/api/simulations", "/api/simulations/validate"}:
        return {"project_id": f"{project_id}-mismatch", "workflow_managed": True}
    if path == "/api/simulation-campaigns":
        return {"project_id": project_id, "seeds": []}
    return {}


def registered_requests() -> list[tuple[str, str]]:
    app = create_app(testing=True)
    requests: list[tuple[str, str]] = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda item: item.rule):
        methods = sorted(rule.methods - {"HEAD", "OPTIONS"})
        for path in route_paths(rule.rule):
            for method in methods:
                requests.append((method, path))
    return requests


def frontend_requests() -> list[tuple[str, str]]:
    """Include every explicitly exported Next.js route handler."""
    root = REPOSITORY_ROOT / 'frontend' / 'src' / 'app'
    exports = re.compile(r'export\s+(?:async\s+function|const)\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b')
    requests = []
    for source in sorted((root / 'api').rglob('route.ts')):
        path = '/' + source.parent.relative_to(root).as_posix()
        path = re.sub(r'\[[^]]+\]', SENTINEL_ID, path)
        for method in exports.findall(source.read_text(encoding='utf-8')):
            requests.append((method, path))
    return requests


def exercise(
    base_url: str,
    project_id: str,
    requests: list[tuple[str, str]],
    timeout: float,
) -> tuple[Counter[int], list[dict[str, object]], float, list[dict[str, object]]]:
    statuses: Counter[int] = Counter()
    failures: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    started = time.perf_counter()
    for method, path in requests:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Project-ID": project_id,
        }
        body = None
        if method in {"POST", "PUT", "PATCH"}:
            body = json.dumps(request_payload(path, project_id)).encode("utf-8")
        suffix = f'?projectId={project_id}' if path == '/api/agent/history' else ''
        if path == '/api/agent/diagnostics' and method == 'GET':
            suffix = '?agentLog=status'
        request = Request(f"{base_url}{path}{suffix}", data=body, headers=headers, method=method)
        request_started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout) as response:
                status = response.status
                response.read(256)
        except HTTPError as error:
            status = error.code
            error.read(256)
        except (TimeoutError, URLError, OSError) as error:
            failure = {"method": method, "path": path, "error": str(error)}
            failures.append(failure)
            observations.append(failure)
            continue
        statuses[status] += 1
        observations.append({"method": method, "path": path, "status": status,
                             "milliseconds": round((time.perf_counter() - request_started) * 1000, 2)})
        if status >= 500 or status == 405:
            failures.append({"method": method, "path": path, "status": status})
    return statuses, failures, time.perf_counter() - started, observations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:15050")
    parser.add_argument("--project-id", default=f"endpoint-smoke-{uuid4().hex[:12]}")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--include-frontend", action="store_true")
    args = parser.parse_args()

    requests = registered_requests()
    backend_count = len(requests)
    frontend = frontend_requests() if args.include_frontend else []
    requests = list(dict.fromkeys(requests + frontend))
    report: dict[str, object] = {
        "base_url": args.base_url.rstrip("/"),
        "project_id": args.project_id,
        "registered_requests": len(requests),
        "backend_bindings": backend_count,
        "frontend_bindings": len(frontend),
        "scope": "Dispatch/availability smoke with invalid and sentinel inputs; 4xx may be expected, not proof of successful business operations.",
        "passes": [],
    }
    all_failures: list[dict[str, object]] = []
    for pass_number in range(1, args.repeats + 1):
        statuses, failures, elapsed, observations = exercise(
            args.base_url.rstrip("/"), args.project_id, requests, args.timeout
        )
        result = {
            "pass": pass_number,
            "elapsed_seconds": round(elapsed, 3),
            "statuses": dict(sorted(statuses.items())),
            "failures": failures,
            "observations": observations,
        }
        report["passes"].append(result)
        all_failures.extend(failures)
        print(json.dumps({key: value for key, value in result.items() if key != 'observations'}, ensure_ascii=False, sort_keys=True))

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        f"checked={len(requests) * args.repeats} "
        f"route_method_bindings={len(requests)} failures={len(all_failures)} "
        f"project_id={args.project_id}"
    )
    return 1 if all_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
