from __future__ import annotations

import time

from backend.app import create_app


def test_health_and_catalog() -> None:
    client = create_app(testing=True).test_client()

    assert client.get("/api/health").get_json()["status"] == "ok"
    catalog = client.get("/api/technologies").get_json()
    assert catalog["technology_count"] == 54
    assert len(catalog["domains"]) == 10
    can_fd = next(
        technology
        for domain in catalog["domains"]
        for technology in domain["technologies"]
        if technology["id"] == "can_fd"
    )
    categories = {field["category"] for field in can_fd["parameter_schema"]}
    assert categories == {
        "physical", "timing", "capacity", "qos", "reliability",
        "synchronization", "gateway", "simulation",
    }
    assert all("simulation_relevant" in field for field in can_fd["parameter_schema"])


def test_local_studio_origin_is_allowed() -> None:
    client = create_app(testing=True).test_client()

    response = client.options(
        "/api/engineering/imports/commit",
        headers={"Origin": "http://127.0.0.1:13500"},
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:13500"
    assert "X-Project-ID" in response.headers["Access-Control-Allow-Headers"]


def test_knowledge_search_endpoint_returns_hybrid_context(monkeypatch) -> None:
    class FakeKnowledgeService:
        def search(self, query, *, selected_object_ids, filters, limit):
            return {
                "query": query,
                "items": [{"object_id": "signal-1", "retrieval_sources": ["vector", "graph"]}],
                "count": 1,
                "context": {"item_count": 1},
                "pipeline": ["keyword", "vector", "metadata", "graph", "rerank"],
                "input": {
                    "selected_object_ids": selected_object_ids,
                    "filters": filters,
                    "limit": limit,
                },
            }

    monkeypatch.setattr("backend.engineering.api.CanonicalKnowledgeService", FakeKnowledgeService)
    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/engineering/knowledge/search",
        json={
            "query": "battery status",
            "selected_object_ids": ["powertrain"],
            "filters": {"domain": "mobility"},
            "limit": 8,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["items"][0]["retrieval_sources"] == ["vector", "graph"]
    assert payload["input"] == {
        "selected_object_ids": ["powertrain"],
        "filters": {"domain": "mobility"},
        "limit": 8,
    }


def test_validation_job_completes() -> None:
    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/simulations/validate",
        json={"technology": "arinc429", "node_count": 2, "duration_s": 0.01},
    )
    assert response.status_code == 202
    job_id = response.get_json()["id"]

    job = None
    for _ in range(100):
        job = client.get(f"/api/simulations/{job_id}").get_json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.01)

    assert job is not None
    assert job["status"] == "completed"
    assert job["result"]["status"] == "validated"


def test_simulation_job_publishes_runtime_metrics() -> None:
    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/simulations",
        json={
            "technology": "can_fd",
            "node_count": 2,
            "duration_s": 0.02,
            "cycle_ms": 10,
            "formats": ["universal-jsonl", "universal-csv"],
        },
    )
    assert response.status_code == 202
    job_id = response.get_json()["id"]

    job = None
    for _ in range(100):
        job = client.get(f"/api/simulations/{job_id}").get_json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.01)

    assert job is not None
    assert job["status"] == "completed"
    runtime = job["result"]["runtime_metrics"]
    assert runtime["available"] is True
    assert runtime["networks"]
    assert runtime["routes"]
    assert runtime["jitter_definition"] == "abs(actual_interval - expected_interval)"


def test_topology_config_drives_explicit_route_retries_and_gateway_metrics() -> None:
    client = create_app(testing=True).test_client()
    config = {
        "name": "topology-runtime-contract",
        "duration_s": 0.02,
        "formats": ["universal-jsonl", "universal-csv"],
        "dropout_probability": 1.0,
        "retransmission_enabled": True,
        "retry_limit": 2,
        "gateway_delay_ms": 0.4,
        "gateway_maximum_throughput": 1_000_000,
        "networks": [{"id": "network-can_fd", "technology": "can_fd", "bitrate": 500_000}],
        "hardware": {
            "nodes": [
                {
                    "id": "gateway-a",
                    "name": "Gateway A",
                    "type": "gateway",
                    "ports": [{"id": "gw-port", "interfaces": [{"id": "gw-if", "technology": "can_fd", "network_id": "network-can_fd"}]}],
                },
                {
                    "id": "ecu-b",
                    "name": "ECU B",
                    "type": "ecu",
                    "ports": [{"id": "ecu-port", "interfaces": [{"id": "ecu-if", "technology": "can_fd", "network_id": "network-can_fd"}]}],
                },
            ]
        },
        "communications": [{
            "id": "route-explicit",
            "name": "Gateway to ECU",
            "sender_interface": "gw-if",
            "receiver_interfaces": ["ecu-if"],
            "network": "network-can_fd",
            "technology": "can_fd",
            "cycle_ms": 10,
            "payload_bytes": 8,
        }],
    }

    response = client.post("/api/simulations", json={"config": config})
    assert response.status_code == 202
    job_id = response.get_json()["id"]
    job = None
    for _ in range(100):
        job = client.get(f"/api/simulations/{job_id}").get_json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.01)

    assert job is not None and job["status"] == "completed"
    assert job["result"]["trace"]["routes"] == 1
    runtime = job["result"]["runtime_metrics"]
    assert runtime["routes"][0]["route_id"] == "route-explicit"
    assert runtime["reliability"]["retransmissions"] > 0
    assert runtime["gateways"][0]["gateway_id"] == "gateway-a"
