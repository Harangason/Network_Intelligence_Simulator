"""Reconcile legacy names in the two explicitly renamed camera/radar networks."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

from backend.engineering.network_naming import rename_network

PROJECT = "network-project-20260910042736034-d11591d0"
NETWORKS = ("Fahrerassistenz_05-IO-kameraverarbeitung-automotive-ethernet-S01",
            "Fahrerassistenz_05-IO-radarverarbeitung-automotive-ethernet-S01")

def api(path, data=None):
    request = urllib.request.Request("http://127.0.0.1:15050/api/engineering" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"X-Project-ID": PROJECT, "Content-Type": "application/json"},
        method="PUT" if data is not None else "GET")
    return json.load(urllib.request.urlopen(request, timeout=90))

def reconcile():
    receipts = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for index, network_id in enumerate(NETWORKS):
        before = api("/workflow")
        network = next(n for n in before["parameters"]["networks"] if n["id"] == network_id)
        assert network.get("name_source") == "user"
        ports = [p for n in before["topology"]["nodes"] for p in n["ports"] if p.get("physicalNetworkId") == network_id]
        channels = {p["hardwareInterfaceId"]: api("/hardware-interfaces/" + p["hardwareInterfaceId"]) for p in ports}
        parameters, topology = rename_network(before, network_id, network["name"], channels=channels)
        assert parameters == before["parameters"]
        old_ports = {p["id"]: p for p in ports}
        changed = [{"node": n["name"], "port_id": p["id"], "from": old_ports[p["id"]]["name"], "to": p["name"]}
                   for n in topology["nodes"] for p in n["ports"] if p["id"] in old_ports and p["name"] != old_ports[p["id"]]["name"]]
        # Do not make metadata-only changes if the reported defect is already repaired.
        if not changed:
            receipts.append({"network": network_id, "status": "already consistent"})
            continue
        backup = Path(f"backend/runtime/bus-interface-names-{stamp}-{index}-before.json")
        backup.write_text(json.dumps({"state": before, "channels": channels}, ensure_ascii=False, indent=2), encoding="utf-8")
        saved = api("/workflow/bus-name", {"network_id": network_id, "name": network["name"],
            "expected_token": before["edit_tokens"]["topology"], "expected_parameters_token": before["edit_tokens"]["parameters"]})
        assert saved["topology"] == topology
        assert saved["parameters"] == before["parameters"]
        for key in ("versions", "statuses", "routing"):
            assert saved.get(key) == before.get(key), key
        for key, old in channels.items():
            new = api("/hardware-interfaces/" + key)
            assert new["name"] == network["name"]
            for field in ("id", "network_ref", "hardware_node_id", "technology", "channel_index", "physical_port_ref", "approval_state"):
                assert new[field] == old[field], field
        receipts.append({"network": network_id, "name": network["name"], "changes": changed, "backup": str(backup),
                         "topology_matches_plan": True, "parameters_routing_versions_statuses_preserved": True})
    result = Path("backend/runtime/bus-interface-names-reconciled.json")
    result.write_text(json.dumps({"project": PROJECT, "receipts": receipts}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"result": str(result), "receipts": receipts}, ensure_ascii=False))

if __name__ == "__main__":
    reconcile()
