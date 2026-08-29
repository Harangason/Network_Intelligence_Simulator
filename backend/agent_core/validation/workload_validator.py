from __future__ import annotations

from typing import Any, Mapping, Sequence


class WorkloadValidator:
    def validate(self, workload: Mapping[str, Any], packages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        requested = int(workload.get("requested_total") or workload.get("target_total") or 0)
        package_total = sum(int(item.get("requested_count") or 0) for item in packages)
        if requested <= 0:
            findings.append({"code": "INVALID_TARGET", "severity": "ERROR"})
        if package_total != requested:
            findings.append(
                {
                    "code": "WORKLOAD_CONFIGURATION_ERROR",
                    "severity": "ERROR",
                    "expected": requested,
                    "actual": package_total,
                }
            )
        return findings
