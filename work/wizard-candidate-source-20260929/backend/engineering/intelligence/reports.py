"""CSV and JSON-ready report projections for Intelligence snapshots."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


class IntelligenceReportService:
    def json_report(self, snapshot: dict[str, Any]) -> str:
        return json.dumps(snapshot, ensure_ascii=False, indent=2, default=str)

    def csv_report(self, snapshot: dict[str, Any], section: str = "issues") -> str:
        results = snapshot.get("results") or {}
        if section == "maturity":
            rows = [
                {"dimension": key, "score": value}
                for key, value in (results.get("maturity") or {}).get("dimensions", {}).items()
            ]
        elif section == "data-quality":
            rows = [results.get("data_quality") or {}]
        elif section == "recommendations":
            rows = results.get("recommendations") or []
        else:
            rows = results.get("critical_issues") or []
        flattened = [
            {key: json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else value for key, value in row.items()}
            for row in rows
        ]
        columns = sorted({key for row in flattened for key in row})
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flattened)
        return output.getvalue()
