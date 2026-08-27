from contextlib import nullcontext

from backend.engineering import project_bundle


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def transaction(self):
        return nullcontext()

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self


def test_reset_workspace_clears_project_scoped_data(monkeypatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(project_bundle, "get_connection", lambda: connection)
    monkeypatch.setattr(
        project_bundle.ProjectBundleService,
        "_refresh_sequences",
        staticmethod(lambda _connection: None),
    )
    monkeypatch.setattr(project_bundle.WorkflowStatusService, "get", lambda _self: {"active_step": 1})

    result = project_bundle.ProjectBundleService().reset_workspace("test-project")

    project_deletes = [
        (str(query), params)
        for query, params in connection.calls
        if params == ("test-project",) and "engineering_workflow_projects" not in str(query)
    ]
    assert len(project_deletes) == len(project_bundle.PROJECT_TABLES)
    assert all(("test-project",) == params for _, params in project_deletes)
    assert set(project_bundle.PROJECT_TABLES).issubset(result["cleared_tables"])
    assert set(project_bundle.WORKSPACE_RESET_TABLES).issubset(result["cleared_tables"])
    assert result["workflow"] == {"active_step": 1}
