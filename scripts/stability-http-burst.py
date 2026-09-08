#!/usr/bin/env python3
"""Run a concurrent health/page burst against the live NetworkIS services."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_TARGETS = (
    "http://127.0.0.1:15050/api/health",
    "http://127.0.0.1:15050/api/engineering/health",
    "http://127.0.0.1:13500/",
    "http://127.0.0.1:13500/api/ready",
    "http://127.0.0.1:13500/api/engineering/workflow?view=summary&project=20260908103453543-44dfbb43",
)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(round((len(ordered) - 1) * fraction), len(ordered) - 1)]


def fetch(index: int, targets: tuple[str, ...], timeout: float) -> dict[str, object]:
    url = targets[index % len(targets)]
    started = time.perf_counter()
    try:
        with urlopen(Request(url, headers={"Accept": "application/json", "X-Project-ID": "20260908103453543-44dfbb43"}), timeout=timeout) as response:
            body = response.read(2_097_153)
            if len(body) > 2_097_152:
                raise ValueError('Response exceeded the 2 MiB smoke budget.')
            if 'application/json' in response.headers.get('Content-Type', ''):
                json.loads(body)
            return {
                "url": url,
                "status": response.status,
                "elapsed_ms": (time.perf_counter() - started) * 1000,
            }
    except HTTPError as error:
        return {
            "url": url,
            "status": error.code,
            "elapsed_ms": (time.perf_counter() - started) * 1000,
        }
    except (TimeoutError, URLError, OSError, ValueError) as error:
        return {
            "url": url,
            "error": str(error),
            "elapsed_ms": (time.perf_counter() - started) * 1000,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(fetch, index, DEFAULT_TARGETS, args.timeout) for index in range(args.requests)]
        results = [future.result() for future in as_completed(futures)]

    failures = [item for item in results if item.get("status") != 200]
    latencies = [float(item["elapsed_ms"]) for item in results]
    report = {
        "requests": len(results),
        "workers": args.workers,
        "targets": list(DEFAULT_TARGETS),
        "wall_seconds": round(time.perf_counter() - started, 3),
        "statuses": dict(sorted(Counter(item.get("status", "error") for item in results).items(), key=lambda item: str(item[0]))),
        "latency_ms": {
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "max": round(max(latencies, default=0.0), 2),
        },
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
