from __future__ import annotations

import os

import pytest

from backend.app import create_app
from backend.engineering.db import close_pool, get_connection


pytestmark = pytest.mark.skipif(
    not os.environ.get("ENGINEERING_TEST_DATABASE_URL"),
    reason="ENGINEERING_TEST_DATABASE_URL ist für Engineering-DB-Integrationstests nicht gesetzt.",
)


def _client():
    os.environ["DATABASE_URL"] = os.environ["ENGINEERING_TEST_DATABASE_URL"]
    close_pool()
    return create_app(testing=True).test_client()


def test_create_get_update_list_delete_hardware_node() -> None:
    client = _client()

    create_resp = client.post(
        "/api/engineering/hardware-nodes",
        json={
            "name": "ECU-Front-Left",
            "device_type": "ECU",
            "domain": "automotive",
            "identity": {"serial": "123"},
            "actor": "pytest",
        },
    )
    assert create_resp.status_code == 201
    node = create_resp.get_json()
    assert node["name"] == "ECU-Front-Left"
    assert node["version"] == 1
    assert node["lifecycle_state"] == "draft"
    assert node["approval_state"] == "pending"
    node_id = node["id"]

    get_resp = client.get(f"/api/engineering/hardware-nodes/{node_id}")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["id"] == node_id

    update_resp = client.patch(
        f"/api/engineering/hardware-nodes/{node_id}",
        json={"description": "Updated description", "actor": "pytest"},
    )
    assert update_resp.status_code == 200
    updated = update_resp.get_json()
    assert updated["description"] == "Updated description"
    assert updated["version"] == 2

    list_resp = client.get("/api/engineering/hardware-nodes")
    assert list_resp.status_code == 200
    listed = list_resp.get_json()
    assert listed["count"] >= 1
    assert any(item["id"] == node_id for item in listed["items"])

    versions_resp = client.get(f"/api/engineering/hardware-nodes/{node_id}/versions")
    assert versions_resp.status_code == 200
    versions = versions_resp.get_json()["items"]
    assert len(versions) == 2
    assert versions[0]["change_summary"] == "updated"
    assert versions[-1]["change_summary"] == "created"

    delete_resp = client.delete(f"/api/engineering/hardware-nodes/{node_id}")
    assert delete_resp.status_code == 204

    missing_resp = client.get(f"/api/engineering/hardware-nodes/{node_id}")
    assert missing_resp.status_code == 404


def test_invalid_device_type_returns_400() -> None:
    client = _client()

    response = client.post(
        "/api/engineering/hardware-nodes",
        json={"name": "Bad Node", "device_type": "NotARealType"},
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_interface_requires_existing_hardware_node() -> None:
    client = _client()

    response = client.post(
        "/api/engineering/interfaces",
        json={
            "name": "CAN0",
            "interface_type": "CAN_FD",
            "hardware_node_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code in (400, 404)


def test_hierarchy_relations_are_created_automatically() -> None:
    client = _client()

    node = client.post(
        "/api/engineering/hardware-nodes",
        json={"name": "ECU-Relation-Test", "device_type": "ECU", "actor": "pytest"},
    ).get_json()

    function = client.post(
        "/api/engineering/functions",
        json={
            "name": "Gateway Routing",
            "hardware_node_id": node["id"],
            "actor": "pytest",
        },
    ).get_json()
    assert function["hardware_node_id"] == node["id"]

    interface = client.post(
        "/api/engineering/interfaces",
        json={
            "name": "CAN1",
            "interface_type": "CAN_FD",
            "hardware_node_id": node["id"],
            "function_id": function["id"],
            "actor": "pytest",
        },
    ).get_json()
    assert interface.get("hardware_node_id") == node["id"]
    assert interface["function_id"] == function["id"]

    message = client.post(
        "/api/engineering/messages",
        json={
            "name": "GatewayStatus",
            "interface_id": interface["id"],
            "actor": "pytest",
        },
    ).get_json()
    assert message["interface_id"] == interface["id"]

    signal = client.post(
        "/api/engineering/signals",
        json={
            "name": "GatewayReady",
            "message_id": message["id"],
            "actor": "pytest",
        },
    ).get_json()
    assert signal["message_id"] == message["id"]

    relations_resp = client.get(
        "/api/engineering/relations"
    )
    assert relations_resp.status_code == 200
    relations = relations_resp.get_json()["items"]
    expected = {
        ("HAS_FUNCTION", node["id"], function["id"]),
        ("HAS_INTERFACE", function["id"], interface["id"]),
        ("HAS_MESSAGE", interface["id"], message["id"]),
        ("CONTAINS_SIGNAL", message["id"], signal["id"]),
    }
    actual = {(r["relation_type"], r["source_id"], r["target_id"]) for r in relations}
    assert expected <= actual

    client.delete(f"/api/engineering/signals/{signal['id']}")
    client.delete(f"/api/engineering/messages/{message['id']}")
    client.delete(f"/api/engineering/interfaces/{interface['id']}")
    client.delete(f"/api/engineering/functions/{function['id']}")
    client.delete(f"/api/engineering/hardware-nodes/{node['id']}")


def test_network_topology_sync_is_idempotent() -> None:
    client = _client()
    topology_id = "pytest-network-sync"
    payload = {
        "topology_id": topology_id,
        "nodes": [
            {
                "id": "gateway",
                "name": "Test Gateway",
                "kind": "gateway",
                "ports": [{"id": "gateway-can", "name": "CAN FD", "bus": "can_fd"}],
            },
            {
                "id": "ecu",
                "name": "Test ECU",
                "kind": "ecu",
                "ports": [{"id": "ecu-can", "name": "CAN FD", "bus": "can_fd"}],
            },
        ],
        "edges": [
            {
                "id": "gateway-ecu",
                "source": "gateway",
                "sourcePort": "gateway-can",
                "target": "ecu",
                "targetPort": "ecu-can",
                "bus": "can_fd",
            }
        ],
    }

    first_response = client.post("/api/engineering/topology/sync", json=payload)
    assert first_response.status_code == 200
    first = first_response.get_json()
    assert first["counts"] == {"hardware_nodes": 2, "interfaces": 2, "connections": 1}

    second_response = client.post("/api/engineering/topology/sync", json=payload)
    assert second_response.status_code == 200
    second = second_response.get_json()
    assert [item["engineering_id"] for item in second["nodes"]] == [
        item["engineering_id"] for item in first["nodes"]
    ]
    assert second["edges"][0]["engineering_relation_id"] == first["edges"][0][
        "engineering_relation_id"
    ]

    for node in first["nodes"]:
        for interface in node["interfaces"]:
            client.delete(f"/api/engineering/interfaces/{interface['engineering_id']}")
    for node in first["nodes"]:
        client.delete(f"/api/engineering/functions/{node['function_id']}")
        client.delete(f"/api/engineering/hardware-nodes/{node['engineering_id']}")


def test_ai_proposal_is_stored_separately_from_engineering_objects() -> None:
    client = _client()
    response = client.post(
        "/api/engineering/proposals",
        json={
            "proposal_type": "OBJECT",
            "prompt": "Create BatteryStatusInterface",
            "proposed_objects": [{"object_type": "Interface", "name": "BatteryStatusInterface"}],
            "actor": "pytest",
        },
    )
    assert response.status_code == 201
    proposal = response.get_json()
    assert proposal["status"] == "AI_GENERATED"
    assert proposal["proposed_objects"][0]["name"] == "BatteryStatusInterface"

    with get_connection() as connection:
        connection.execute(
            "DELETE FROM engineering_ai_proposals WHERE proposal_id = %s",
            (proposal["proposal_id"],),
        )
        connection.commit()
