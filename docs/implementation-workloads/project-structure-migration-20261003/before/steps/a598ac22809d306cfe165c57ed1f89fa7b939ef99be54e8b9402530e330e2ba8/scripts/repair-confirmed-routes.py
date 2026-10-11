"""Preview, or explicitly apply, only missing transports with canonical evidence."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.confirmed_routes import repair_confirmed_routes, refresh_confirmed_topology
from backend.engineering.db import close_pool


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--apply", action="store_true", help="Review and atomically apply technically valid missing routes")
    parser.add_argument("--output", type=Path, help="Write the full reviewable JSON report here")
    parser.add_argument("--refresh-topology", action="store_true", help="Also preserve/update physical topology and rerun capacity, preflight and intelligence")
    args = parser.parse_args()
    try:
        report = repair_confirmed_routes(args.project_id, apply=args.apply)
        if args.refresh_topology:
            report["topology_refresh"] = refresh_confirmed_topology(args.project_id, apply=args.apply)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps({key: report[key] for key in ("project_id", "applied", "existing_route_count", "new_route_count")}
            | {"invalid_count": len(report["invalid"]), "unconfirmed_message_count": len(report["unconfirmed_messages"]),
               "before_missing_messages": len(report["before"]["missing_message_ids"]),
               "after_missing_messages": len(report.get("after", report["projected_after"])["missing_message_ids"]),
               "topology_refreshed": report.get("topology_refresh", {}).get("applied", False),
               "preflight_status": report.get("topology_refresh", {}).get("preflight_status")}, ensure_ascii=False))
    finally:
        close_pool()


if __name__ == "__main__":
    main()
