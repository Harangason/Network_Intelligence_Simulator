"""Check a live project repair against its pre-migration export without mutations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:15050")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8-sig"))
    project_id = before["source_project_id"]
    request = Request(args.base_url.rstrip("/") + "/api/engineering/projects/export",
                      headers={"X-Project-ID": project_id})
    with urlopen(request, timeout=180) as response:
        after = json.load(response)
    args.after.write_text(json.dumps(after, ensure_ascii=False), encoding="utf-8")
    old, new = before["source_data"], after["source_data"]
    checks = []
    fixed_tables = ["engineering_hardware_nodes", "engineering_functions", "engineering_interfaces",
                    "engineering_messages", "engineering_signals"]
    for table in fixed_tables:
        assert {row["id"] for row in old[table]} == {row["id"] for row in new[table]}, table
    checks.append("Hardware, Funktionen, Kommunikationsschnittstellen, Nachrichten und Signal-IDs vollständig erhalten")
    for table, fields in {
        "engineering_hardware_nodes": ["name", "device_type", "device_class"],
        "engineering_messages": ["name", "interface_id", "cycle_ms", "dlc", "direction", "message_id_hex"],
        "engineering_signals": None,
        "engineering_routing_entries": ["timing", "payload"],
    }.items():
        current = {row["id"]: row for row in new[table]}
        for row in old[table]:
            assert row["id"] in current, (table, row["id"])
            for field in fields or list(row):
                assert row.get(field) == current[row["id"]].get(field), (table, row["id"], field)
    checks.append("Vorhandene Geräteidentitäten, Nachrichtendefinitionen, Signale und Routing-Grenzwerte unverändert")
    old_hwifs = {row["id"] for row in old["engineering_hardware_interfaces"]}
    assert old_hwifs <= {row["id"] for row in new["engineering_hardware_interfaces"]}
    checks.append("Alle bisherigen physischen Anschluss-IDs erhalten")
    def scope(bundle):
        return (bundle["workflow"].get("parameters") or {}).get("simulation_scope") or {"mode": "ALL"}
    assert scope(before).get("mode", "ALL") == scope(after).get("mode", "ALL") == "ALL"
    checks.append("Gesamtumfang ALL erhalten")
    old_nodes = {row["id"] for row in before["workflow"]["topology"]["nodes"]}
    new_nodes = {row["id"] for row in after["workflow"]["topology"]["nodes"]}
    assert old_nodes == new_nodes
    checks.append("Topologie enthält dieselben Hardwareknoten")
    report = {"project_id": project_id, "checks": checks,
              "counts_before": {table: len(old[table]) for table in fixed_tables + ["engineering_hardware_interfaces", "engineering_routing_entries"]},
              "counts_after": {table: len(new[table]) for table in fixed_tables + ["engineering_hardware_interfaces", "engineering_routing_entries"]},
              "explicit_system_owners": sum(bool((row.get("identity") or {}).get("system_owner_id")) for row in new["engineering_hardware_nodes"]),
              "workflow_statuses": after["workflow"]["statuses"], "scope": scope(after)}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
