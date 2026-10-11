from __future__ import annotations

from typing import Any, Mapping, Sequence


class WorkloadProgressTracker:
    def calculate(
        self,
        workload: Mapping[str, Any],
        packages: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        requested = int(workload.get("requested_total") or workload.get("target_total") or 0)
        generated = sum(int(item.get("generated_count") or 0) for item in packages)
        valid = sum(int(item.get("valid_count") or 0) for item in packages)
        invalid = sum(int(item.get("invalid_count") or 0) for item in packages)
        duplicates = sum(int(item.get("duplicate_count") or 0) for item in packages)
        missing = sum(max(0, int(item.get("requested_count") or 0) - int(item.get("valid_count") or 0)) for item in packages)
        warnings = sum(
            1
            for item in packages
            for finding in item.get("findings") or []
            if str(finding.get("severity") or "").upper() == "WARNING"
        )
        return {
            "requested": requested,
            "generated": generated,
            "valid": valid,
            "invalid": invalid,
            "duplicates": duplicates,
            "missing": missing,
            "warnings": warnings,
            "errors": invalid + duplicates,
            "percent": 0.0 if requested <= 0 else round(min(valid, requested) * 100 / requested, 2),
            "work_packages": [
                {
                    **dict(item),
                    "missing_count": max(0, int(item.get("requested_count") or 0) - int(item.get("valid_count") or 0)),
                    "progress_percent": 0.0
                    if int(item.get("requested_count") or 0) <= 0
                    else round(min(int(item.get("valid_count") or 0), int(item.get("requested_count") or 0)) * 100 / int(item.get("requested_count") or 0), 2),
                }
                for item in packages
            ],
        }
