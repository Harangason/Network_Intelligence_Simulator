from backend.engineering.agent_tools.simulation_gateway import job_api_base


def test_job_dispatch_follows_this_backend_port(monkeypatch):
    monkeypatch.delenv("SIMULATOR_JOB_API_URL", raising=False)
    monkeypatch.setenv("FLASK_PORT", "15059")
    assert job_api_base() == "http://127.0.0.1:15059/api"


def test_explicit_shared_executor_takes_precedence(monkeypatch):
    monkeypatch.setenv("SIMULATOR_JOB_API_URL", "http://127.0.0.1:15100/api/")
    monkeypatch.setenv("FLASK_PORT", "15059")
    assert job_api_base() == "http://127.0.0.1:15100/api"
