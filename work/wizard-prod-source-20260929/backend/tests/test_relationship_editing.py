"""Relationship edits must survive canonical channel materialization and reload."""
from copy import deepcopy
import os

import pytest

from backend.engineering.physical_ports import materialize_physical_ports


def test_generated_channel_name_is_independent_of_bus_name():
    hardware = [{"id": key} for key in ("a", "b")]
    channels = [{"id": key, "name": key + "_ETH", "source": "ai_generated", "hardware_node_id": key,
                 "technology": "Ethernet", "network_ref": "bus", "channel_index": 1,
                 "physical_port_ref": key + "-connector"} for key in ("a", "b")]
    topology = {"nodes": [{"id": key, "engineeringId": key, "ports": [{"id": key, "name": key + "_ETH",
                 "hardwareInterfaceId": key, "physicalNetworkId": "bus", "bus": "automotive_ethernet"}]} for key in ("a", "b")],
                "edges": [{"id": "ab", "source": "a", "target": "b", "sourcePort": "a", "targetPort": "b", "bus": "automotive_ethernet"}]}
    actual, changes = materialize_physical_ports(topology, hardware, channels,
        [{"id": "bus", "name": "Fahrerassistenz 01", "technology": "ETHERNET"}])
    assert not changes
    assert [n["ports"][0]["name"] for n in actual["nodes"]] == ["a_ETH", "b_ETH"]
    assert all(n["ports"][0]["physicalNetworkName"] == "Fahrerassistenz 01" for n in actual["nodes"])


@pytest.mark.skipif(not os.environ.get("ENGINEERING_TEST_DATABASE_URL"), reason="Separate SQL database required")
def test_interface_and_relationship_rename_reload_aliases_and_rollback(monkeypatch):
    from backend.tests.test_engineering_api import _client
    from backend.engineering.workflow.service import WorkflowStatusService
    from backend.engineering.models import EngineeringValidationError

    c = _client()
    nodes = []
    for key in ("owner", "camera", "radar"):
        hw = c.post("/api/engineering/hardware-nodes", json={"name": key, "domain": "robotics", "device_type": "ECU"}).get_json()
        nodes.append({"id": key, "name": key, "kind": "ecu", "engineeringId": hw["id"], "x": 0, "y": 0,
            "ports": [{"id": key, "name": key + " Ethernet", "bus": "automotive_ethernet", "side": "right", "offset": .5, "physicalNetworkId": "bus"}]})
    topology = {"nodes": nodes, "edges": [{"id": key, "source": "owner", "sourcePort": "owner", "target": key,
        "targetPort": key, "bus": "automotive_ethernet", "physicalNetworkId": "bus"} for key in ("camera", "radar")]}

    def save(t, state=None):
        return c.put("/api/engineering/workflow/topology", json={"topology": t,
            **({"expected_token": state["edit_tokens"]["topology"]} if state else {})})

    r = save(topology)
    assert r.status_code == 200, r.get_json()
    state = r.get_json()
    # Two canvas anchors of the same channel must remain the same named channel.
    t = deepcopy(state["topology"])
    t["nodes"][0]["ports"].append({**t["nodes"][0]["ports"][0], "id": "owner-alias", "offset": .8})
    t["edges"][1]["sourcePort"] = "owner-alias"
    r = save(t, state)
    assert r.status_code == 200, r.get_json()
    state = r.get_json()
    before = deepcopy(state["topology"])
    channels = {p["hardwareInterfaceId"]: c.get("/api/engineering/hardware-interfaces/" + p["hardwareInterfaceId"]).get_json()
                for n in before["nodes"] for p in n["ports"]}
    networks = deepcopy(state["parameters"]["networks"])
    t = deepcopy(before)
    for node in t["nodes"]:
        for port in node["ports"]:
            if node["id"] in ("owner", "camera"):
                port["name"] = "ETH_Master" if node["id"] == "owner" else "ETH_Kamera"
    for edge in t["edges"]:
        edge["sourceInterfaceName"] = "ETH_Master"
        if edge["id"] == "camera":
            edge.update(name="Kameralink", targetInterfaceName="ETH_Kamera", description="Benannter Anschluss")
    original = WorkflowStatusService.save_topology
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise EngineeringValidationError("Injected name persistence failure")
        patch.setattr(WorkflowStatusService, "save_topology", fail)
        r = save(t, state)
    assert r.status_code == 400, r.get_json()
    assert c.get("/api/engineering/workflow").get_json()["topology"] == before
    for identifier, channel in channels.items():
        assert c.get("/api/engineering/hardware-interfaces/" + identifier).get_json() == channel
    r = save(t, state)
    assert r.status_code == 200, r.get_json()
    assert save(t, state).status_code == 409
    state = c.get("/api/engineering/workflow").get_json()
    # An unchanged subsequent save must not restore generated names.
    r = save(state["topology"], state)
    assert r.status_code == 200, r.get_json()
    state = c.get("/api/engineering/workflow").get_json()
    after = state["topology"]
    assert state["parameters"]["networks"] == networks
    for node in after["nodes"]:
        for port in node["ports"]:
            old_port = next(p for n in before["nodes"] for p in n["ports"] if p["id"] == port["id"])
            for field in ("id", "engineeringId", "hardwareInterfaceId", "physicalNetworkId"):
                assert port[field] == old_port[field]
            channel = c.get("/api/engineering/hardware-interfaces/" + port["hardwareInterfaceId"]).get_json()
            for field in ("network_ref", "channel_index", "physical_port_ref"):
                assert channel[field] == channels[channel["id"]][field]
            expected = {"owner": "ETH_Master", "camera": "ETH_Kamera"}.get(node["id"], old_port["name"])
            assert port["name"] == channel["name"] == expected
    assert all(e["sourceInterfaceName"] == "ETH_Master" for e in after["edges"])
    camera = next(e for e in after["edges"] if e["id"] == "camera")
    assert (camera["name"], camera["targetInterfaceName"], camera["description"]) == ("Kameralink", "ETH_Kamera", "Benannter Anschluss")
    relation = c.get("/api/engineering/relations/" + camera["engineeringRelationId"]).get_json()
    assert relation["attributes"]["name"] == "Kameralink"
    # Inconsistent alias names are rejected atomically rather than last-writer-wins.
    conflict = deepcopy(after)
    conflict["nodes"][0]["ports"][1]["name"] = "Different"
    conflict["edges"][1]["sourceInterfaceName"] = "Different"
    r = save(conflict, state)
    assert r.status_code == 400, r.get_json()
    assert c.get("/api/engineering/workflow").get_json()["topology"] == after
