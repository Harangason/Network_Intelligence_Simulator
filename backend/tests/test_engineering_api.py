from __future__ import annotations

from backend.app import create_app


def _client():
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


def test_relation_between_hardware_node_and_interface() -> None:
    client = _client()

    node = client.post(
        "/api/engineering/hardware-nodes",
        json={"name": "ECU-Relation-Test", "device_type": "ECU", "actor": "pytest"},
    ).get_json()

    interface = client.post(
        "/api/engineering/interfaces",
        json={
            "name": "CAN1",
            "interface_type": "CAN_FD",
            "hardware_node_id": node["id"],
            "actor": "pytest",
        },
    ).get_json()
    assert interface.get("hardware_node_id") == node["id"]

    relation_resp = client.post(
        "/api/engineering/relations",
        json={
            "relation_type": "HAS_INTERFACE",
            "source_type": "HardwareNode",
            "source_id": node["id"],
            "target_type": "Interface",
            "target_id": interface["id"],
            "actor": "pytest",
        },
    )
    assert relation_resp.status_code == 201

    relations_resp = client.get(
        "/api/engineering/relations",
        query_string={"object_type": "HardwareNode", "object_id": node["id"]},
    )
    assert relations_resp.status_code == 200
    relations = relations_resp.get_json()["items"]
    assert any(r["target_id"] == interface["id"] for r in relations)

    client.delete(f"/api/engineering/interfaces/{interface['id']}")
    client.delete(f"/api/engineering/hardware-nodes/{node['id']}")
