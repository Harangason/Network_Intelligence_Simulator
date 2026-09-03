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


def test_direct_hardware_interface_proposal_creates_hardware_relation() -> None:
    client = _client()
    headers = {"X-Project-ID": "pytest-direct-interface-proposal"}
    node = client.post(
        "/api/engineering/hardware-nodes",
        headers=headers,
        json={"name": "TemperatureSensor", "device_type": "TemperatureSensor", "actor": "pytest"},
    ).get_json()
    proposal = client.post(
        "/api/engineering/proposals",
        headers=headers,
        json={
            "proposal_type": "OBJECT",
            "target_object": {"resource": "interfaces"},
            "prompt": "Create the direct sensor interface.",
            "model": "pytest",
            "proposed_objects": [
                {
                    "object_type": "Interface",
                    "resource": "interfaces",
                    "name": "TemperatureSensor_1",
                    "hardware_node_id": node["id"],
                    "interface_type": "LIN",
                    "domain": "automotive",
                }
            ],
        },
    ).get_json()

    validated = client.post(
        f"/api/engineering/proposals/{proposal['proposal_id']}/validate",
        headers=headers,
        json={"actor": "pytest"},
    )
    assert validated.status_code == 200
    approved = client.post(
        f"/api/engineering/proposals/{proposal['proposal_id']}/approve",
        headers=headers,
        json={"actor": "pytest"},
    )
    assert approved.status_code == 200
    interface_id = approved.get_json()["proposed_objects"][0]["canonical_id"]

    relations = client.get("/api/engineering/relations", headers=headers).get_json()["items"]
    assert ("HAS_INTERFACE", node["id"], interface_id) in {
        (item["relation_type"], item["source_id"], item["target_id"])
        for item in relations
    }


def test_approved_engineering_proposal_invalidates_workflow() -> None:
    client = _client()
    headers = {"X-Project-ID": "pytest-proposal-workflow-invalidation"}
    before = client.get("/api/engineering/workflow", headers=headers).get_json()

    proposal_response = client.post(
        "/api/engineering/proposals",
        headers=headers,
        json={
            "proposal_type": "OBJECT",
            "target_object": {"resource": "hardware-nodes"},
            "prompt": "Erzeuge einen Hardware-Knoten fuer den Mutationstest.",
            "model": "pytest",
            "proposed_objects": [
                {
                    "object_type": "HardwareNode",
                    "resource": "hardware-nodes",
                    "name": "Proposal-Workflow-Test-ECU",
                    "device_type": "ECU",
                    "domain": "automotive",
                }
            ],
            "created_by": "pytest",
        },
    )
    assert proposal_response.status_code == 201
    proposal_id = proposal_response.get_json()["proposal_id"]

    validation = client.post(
        f"/api/engineering/proposals/{proposal_id}/validate",
        headers=headers,
        json={"actor": "pytest"},
    )
    assert validation.status_code == 200
    unchanged = client.get("/api/engineering/workflow", headers=headers).get_json()
    assert unchanged["versions"]["engineering_model"] == before["versions"]["engineering_model"]

    approval = client.post(
        f"/api/engineering/proposals/{proposal_id}/approve",
        headers=headers,
        json={"actor": "pytest"},
    )
    assert approval.status_code == 200
    after = client.get("/api/engineering/workflow", headers=headers).get_json()
    assert after["versions"]["engineering_model"] == before["versions"]["engineering_model"] + 1
    assert after["active_step"] == "engineering_model"
    assert after["statuses"]["engineering_model"] == "IN_PROGRESS"

    repeated_approval = client.post(
        f"/api/engineering/proposals/{proposal_id}/approve",
        headers=headers,
        json={"actor": "pytest"},
    )
    assert repeated_approval.status_code == 200
    after_repeat = client.get("/api/engineering/workflow", headers=headers).get_json()
    assert after_repeat["versions"]["engineering_model"] == after["versions"]["engineering_model"]


def test_new_project_proposal_reuses_semantic_hardware_synonym() -> None:
    client = _client()
    headers = {"X-Project-ID": "pytest-new-project-system-canonicalization"}
    existing = client.post(
        "/api/engineering/hardware-nodes",
        headers=headers,
        json={
            "name": "ADAS",
            "device_type": "ECU",
            "domain": "automotive",
            "actor": "pytest",
        },
    ).get_json()
    workflow_before = client.get("/api/engineering/workflow", headers=headers).get_json()
    proposal = client.post(
        "/api/engineering/proposals",
        headers=headers,
        json={
            "proposal_type": "OBJECT",
            "target_object": {"resource": "hardware-nodes"},
            "prompt": "Lege Fahrerassistenz aus dem Projektbrief an.",
            "model": "pytest-new-project-agent",
            "proposed_objects": [
                {
                    "object_type": "HardwareNode",
                    "resource": "hardware-nodes",
                    "name": "Fahrerassistenz-ECU",
                    "device_type": "ECU",
                    "domain": "automotive",
                }
            ],
            "created_by": "engineering-chat-agent",
        },
    ).get_json()

    response = client.post(
        f"/api/engineering/proposals/{proposal['proposal_id']}/approve",
        headers=headers,
        json={"actor": "engineering-chat-agent"},
    )

    assert response.status_code == 200
    approved = response.get_json()
    approved_item = approved["proposed_objects"][0]
    assert approved_item["canonical_id"] == existing["id"]
    assert approved_item["canonical_resolution"]["strategy"] == "semantic_hardware_reuse"
    hardware = client.get("/api/engineering/hardware-nodes?limit=20", headers=headers).get_json()["items"]
    assert [item["id"] for item in hardware] == [existing["id"]]
    workflow_after = client.get("/api/engineering/workflow", headers=headers).get_json()
    assert workflow_after["versions"]["engineering_model"] == workflow_before["versions"]["engineering_model"]

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM engineering_ai_proposals WHERE proposal_id = %s",
            (proposal["proposal_id"],),
        )
        conn.commit()
    client.delete(f"/api/engineering/hardware-nodes/{existing['id']}", headers=headers)


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
                "name": "Gateway zu Test ECU",
                "relationType": "CONNECTED_VIA",
                "description": "Manuell definierte CAN-FD-Verbindung",
                "direction": "BIDIRECTIONAL",
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

    payload["edges"][0].update(
        {
            "name": "Gateway kommuniziert mit Test ECU",
            "relationType": "COMMUNICATES_WITH",
            "description": "Aktualisierte gerichtete CAN-FD-Verbindung",
            "direction": "SOURCE_TO_TARGET",
        }
    )
    update_response = client.post("/api/engineering/topology/sync", json=payload)
    assert update_response.status_code == 200
    updated = update_response.get_json()
    assert updated["edges"][0]["engineering_relation_id"] == first["edges"][0][
        "engineering_relation_id"
    ]

    relation_response = client.get(
        "/api/engineering/relations?relation_type=COMMUNICATES_WITH"
    )
    assert relation_response.status_code == 200
    relation = next(
        item
        for item in relation_response.get_json()["items"]
        if item["id"] == first["edges"][0]["engineering_relation_id"]
    )
    assert relation["attributes"]["name"] == "Gateway kommuniziert mit Test ECU"
    assert relation["attributes"]["description"] == "Aktualisierte gerichtete CAN-FD-Verbindung"
    assert relation["attributes"]["direction"] == "SOURCE_TO_TARGET"

    for node in first["nodes"]:
        for interface in node["interfaces"]:
            client.delete(f"/api/engineering/interfaces/{interface['engineering_id']}")
    for node in first["nodes"]:
        client.delete(f"/api/engineering/functions/{node['function_id']}")
        client.delete(f"/api/engineering/hardware-nodes/{node['engineering_id']}")


def test_network_topology_sync_reuses_existing_compatible_interface() -> None:
    client = _client()
    node = client.post(
        "/api/engineering/hardware-nodes",
        json={"name": "Reuse Gateway", "device_type": "Gateway", "actor": "pytest"},
    ).get_json()
    function = client.post(
        "/api/engineering/functions",
        json={
            "name": "Reuse Gateway Communication",
            "hardware_node_id": node["id"],
            "actor": "pytest",
        },
    ).get_json()
    interface = client.post(
        "/api/engineering/interfaces",
        json={
            "name": "CAN FD",
            "interface_type": "CAN_FD",
            "hardware_node_id": node["id"],
            "function_id": function["id"],
            "actor": "pytest",
        },
    ).get_json()
    payload = {
        "topology_id": "pytest-interface-reuse",
        "nodes": [
            {
                "id": "reuse-gateway",
                "engineeringId": node["id"],
                "name": "Reuse Gateway",
                "kind": "gateway",
                "ports": [
                    {"id": "visual-can-port", "name": "CAN FD", "bus": "can_fd"}
                ],
            },
            {
                "id": "reuse-ecu",
                "name": "Reuse ECU",
                "kind": "ecu",
                "ports": [{"id": "ecu-can-port", "name": "CAN FD", "bus": "can_fd"}],
            },
        ],
        "edges": [
            {
                "id": "reuse-edge",
                "source": "reuse-gateway",
                "sourcePort": "visual-can-port",
                "target": "reuse-ecu",
                "targetPort": "ecu-can-port",
                "bus": "can_fd",
                "sourceInterfaceName": "ReuseGateway_CAN_FD",
                "targetInterfaceName": "ReuseECU_CAN_FD",
            }
        ],
    }

    response = client.post("/api/engineering/topology/sync", json=payload)
    assert response.status_code == 200
    result = response.get_json()
    gateway_sync = next(
        item for item in result["nodes"] if item["topology_node_id"] == "reuse-gateway"
    )
    assert gateway_sync["interfaces"][0]["engineering_id"] == interface["id"]
    assert gateway_sync["interfaces"][0]["engineering_name"] == "ReuseGateway_CAN_FD"

    listed = client.get("/api/engineering/interfaces").get_json()["items"]
    gateway_interfaces = [
        item for item in listed if item.get("hardware_node_id") == node["id"]
    ]
    assert [item["id"] for item in gateway_interfaces] == [interface["id"]]
    assert gateway_interfaces[0]["name"] == "ReuseGateway_CAN_FD"

    ecu_sync = next(
        item for item in result["nodes"] if item["topology_node_id"] == "reuse-ecu"
    )
    client.delete(
        f"/api/engineering/interfaces/{ecu_sync['interfaces'][0]['engineering_id']}"
    )
    client.delete(f"/api/engineering/interfaces/{interface['id']}")
    client.delete(f"/api/engineering/functions/{ecu_sync['function_id']}")
    client.delete(f"/api/engineering/hardware-nodes/{ecu_sync['engineering_id']}")
    client.delete(f"/api/engineering/functions/{function['id']}")
    client.delete(f"/api/engineering/hardware-nodes/{node['id']}")


def test_network_topology_sync_keeps_one_interface_per_port() -> None:
    client = _client()
    topology_id = "pytest-multi-lin-interface"
    payload = {
        "topology_id": topology_id,
        "persist_workflow": False,
        "nodes": [
            {
                "id": "gateway",
                "name": "Gateway",
                "kind": "gateway",
                "ports": [
                    {"id": "gateway-lin-1", "name": "Gateway_LIN", "bus": "lin"},
                    {"id": "gateway-lin-2", "name": "Gateway_LIN", "bus": "lin"},
                ],
            },
            {
                "id": "actor-1",
                "name": "Actor 1",
                "kind": "actuator",
                "ports": [{"id": "actor-1-lin", "name": "Actor1_LIN", "bus": "lin"}],
            },
            {
                "id": "actor-2",
                "name": "Actor 2",
                "kind": "actuator",
                "ports": [{"id": "actor-2-lin", "name": "Actor2_LIN", "bus": "lin"}],
            },
        ],
        "edges": [
            {
                "id": "gateway-actor-1",
                "source": "gateway",
                "sourcePort": "gateway-lin-1",
                "sourceInterfaceName": "Gateway_LIN",
                "target": "actor-1",
                "targetPort": "actor-1-lin",
                "targetInterfaceName": "Actor1_LIN",
                "bus": "lin",
            },
            {
                "id": "gateway-actor-2",
                "source": "gateway",
                "sourcePort": "gateway-lin-2",
                "sourceInterfaceName": "Gateway_LIN",
                "target": "actor-2",
                "targetPort": "actor-2-lin",
                "targetInterfaceName": "Actor2_LIN",
                "bus": "lin",
            },
        ],
    }

    first = client.post("/api/engineering/topology/sync", json=payload)
    assert first.status_code == 200
    first_result = first.get_json()
    gateway = next(item for item in first_result["nodes"] if item["topology_node_id"] == "gateway")
    assert first_result["counts"] == {"hardware_nodes": 3, "interfaces": 4, "connections": 2}
    assert [item["engineering_name"] for item in gateway["interfaces"]] == [
        "Gateway_LIN",
        "Gateway_LIN_2",
    ]
    assert len({item["engineering_id"] for item in gateway["interfaces"]}) == 2

    second = client.post("/api/engineering/topology/sync", json=payload)
    assert second.status_code == 200
    second_gateway = next(
        item for item in second.get_json()["nodes"] if item["topology_node_id"] == "gateway"
    )
    assert second_gateway["interfaces"] == gateway["interfaces"]

    for node in first_result["nodes"]:
        for interface in node["interfaces"]:
            client.delete(f"/api/engineering/interfaces/{interface['engineering_id']}")
    for node in first_result["nodes"]:
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
