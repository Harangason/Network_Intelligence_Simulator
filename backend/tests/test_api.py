from __future__ import annotations

import time

from backend.app import create_app


def test_health_and_catalog() -> None:
    client = create_app(testing=True).test_client()

    assert client.get("/api/health").get_json()["status"] == "ok"
    catalog = client.get("/api/technologies").get_json()
    assert catalog["technology_count"] == 54
    assert len(catalog["domains"]) == 10


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
