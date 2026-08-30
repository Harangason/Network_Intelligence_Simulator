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
    assert len(project_deletes) == len(project_bundle.PROJECT_TABLES) + len(project_bundle.WORKSPACE_RESET_TABLES)
    assert all(("test-project",) == params for _, params in project_deletes)
    assert set(project_bundle.PROJECT_TABLES).issubset(result["cleared_tables"])
    assert set(project_bundle.WORKSPACE_RESET_TABLES).issubset(result["cleared_tables"])
    assert result["workflow"] == {"active_step": 1}


def test_clone_source_data_remaps_cross_table_identifiers() -> None:
    node_id = "11111111-1111-1111-1111-111111111111"
    interface_id = "22222222-2222-2222-2222-222222222222"
    route_id = "33333333-3333-3333-3333-333333333333"
    source_data = {table: [] for table in project_bundle.SOURCE_TABLES}
    source_data["engineering_hardware_nodes"] = [{"id": node_id, "project_id": "source", "name": "ECU"}]
    source_data["engineering_interfaces"] = [{
        "id": interface_id,
        "project_id": "source",
        "name": "CAN",
        "hardware_node_id": node_id,
    }]
    source_data["engineering_routing_entries"] = [{
        "id": route_id,
        "project_id": "source",
        "route_code": "RT-1",
        "source": {"node_id": node_id, "interface_id": interface_id},
    }]

    cloned, identifiers = project_bundle._clone_source_data(source_data, "target")

    cloned_node = cloned["engineering_hardware_nodes"][0]
    cloned_interface = cloned["engineering_interfaces"][0]
    cloned_route = cloned["engineering_routing_entries"][0]
    assert cloned_node["id"] != node_id
    assert cloned_interface["hardware_node_id"] == cloned_node["id"]
    assert cloned_route["source"] == {
        "node_id": cloned_node["id"],
        "interface_id": cloned_interface["id"],
    }
    assert cloned_route["id"] == identifiers[route_id]
    assert all(row["project_id"] == "target" for rows in cloned.values() for row in rows)


def test_clone_project_data_preserves_child_table_contracts() -> None:
    workload_id = "11111111-1111-1111-1111-111111111111"
    package_id = "22222222-2222-2222-2222-222222222222"
    project_data = {table: [] for table in project_bundle.PROJECT_TABLES}
    project_data["engineering_workloads"] = [{
        "workload_id": workload_id,
        "project_id": "source",
        "title": "Generate signals",
    }]
    project_data["engineering_work_packages"] = [{
        "work_package_id": package_id,
        "workload_id": workload_id,
        "package_code": "WP-1",
    }]
    project_data["engineering_workload_objects"] = [{
        "workload_object_id": "33333333-3333-3333-3333-333333333333",
        "workload_id": workload_id,
        "work_package_id": package_id,
        "object_key": "signal-1",
    }]
    project_data["engineering_workload_events"] = [{
        "event_id": 99,
        "project_id": "source",
        "workload_id": workload_id,
        "event_type": "COMPLETED",
    }]

    cloned, identifiers = project_bundle._clone_project_data(project_data, "target", {})

    cloned_workload = cloned["engineering_workloads"][0]
    cloned_package = cloned["engineering_work_packages"][0]
    cloned_object = cloned["engineering_workload_objects"][0]
    cloned_event = cloned["engineering_workload_events"][0]
    assert cloned_workload["project_id"] == "target"
    assert cloned_package["workload_id"] == identifiers[workload_id]
    assert cloned_object["work_package_id"] == identifiers[package_id]
    assert "project_id" not in cloned_package
    assert "project_id" not in cloned_object
    assert "event_id" not in cloned_event
    assert cloned_event["project_id"] == "target"
