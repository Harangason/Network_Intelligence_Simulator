from copy import deepcopy
from contextlib import contextmanager

from backend.engineering.physical_segments import physical_port_networks
from backend.engineering.system_clusters import system_owners
from backend.engineering.intelligence.network_planning import plan_network_distribution
from backend.engineering.routing.network_sync import enrich_route_from_linked_topology
from backend.engineering.structure_rules import normalize_hardware_name
from backend.engineering.routing.config_builder import CommunicationConfigBuilder


def topology(shared=False):
    return {
        "nodes": [
            {"id": "gw", "engineeringId": "gateway", "ports": [{"id": "a", "bus": "lin", "engineeringId": "ia"}, {"id": "b", "bus": "lin", "engineeringId": "ib"}]},
            {"id": "one", "engineeringId": "one", "ports": [{"id": "c", "bus": "lin", "engineeringId": "ic"}]},
            {"id": "two", "engineeringId": "two", "ports": [{"id": "d", "bus": "lin", "engineeringId": "id"}]},
        ],
        "edges": [
            {"id": "e1", "source": "one", "sourcePort": "c", "target": "gw", "targetPort": "a", "bus": "lin", "routingEntryId": "r1"},
            {"id": "e2", "source": "two", "sourcePort": "d", "target": "gw", "targetPort": "a" if shared else "b", "bus": "lin", "routingEntryId": "r2"},
        ],
    }


def test_separate_gateway_ports_are_separate_segments_and_shared_ports_are_one_bus():
    separate = physical_port_networks(topology())
    assert separate["a"] == separate["c"]
    assert separate["b"] == separate["d"]
    assert separate["a"] != separate["b"]
    shared = physical_port_networks(topology(True))
    assert shared["a"] == shared["c"] == shared["d"]


def test_segment_identity_is_stable_across_layout_labels_and_order():
    source = topology()
    changed = deepcopy(source)
    changed["nodes"].reverse()
    changed["edges"].reverse()
    for node in changed["nodes"]:
        node.update(x=100, y=40, name="New name")
    assert physical_port_networks(source) == physical_port_networks(changed)


def test_visual_ports_for_the_same_hardware_interface_share_one_segment():
    source = {
        "nodes": [
            {
                "id": "gateway",
                "ports": [
                    {"id": "gateway-a", "bus": "can_fd", "hardwareInterfaceId": "gateway-can"},
                    {"id": "gateway-b", "bus": "can_fd", "hardwareInterfaceId": "gateway-can"},
                ],
            },
            {"id": "ecu-a", "ports": [{"id": "ecu-a-port", "bus": "can_fd", "hardwareInterfaceId": "ecu-a-can"}]},
            {"id": "ecu-b", "ports": [{"id": "ecu-b-port", "bus": "can_fd", "hardwareInterfaceId": "ecu-b-can"}]},
        ],
        "edges": [
            {"source": "gateway", "sourcePort": "gateway-a", "target": "ecu-a", "targetPort": "ecu-a-port", "bus": "can_fd"},
            {"source": "gateway", "sourcePort": "gateway-b", "target": "ecu-b", "targetPort": "ecu-b-port", "bus": "can_fd"},
        ],
    }

    segments = physical_port_networks(source)

    assert len(set(segments.values())) == 1


def test_routing_uses_the_physical_interface_and_segment():
    route = {"id": "r2", "source": {"node_id": "two", "protocol": "LIN"}, "destinations": [{"node_id": "gateway", "protocol": "LIN", "interface_id": "ia"}]}
    result = enrich_route_from_linked_topology(route, topology())
    assert result["destinations"][0]["interface_id"] == "ib"
    assert result["source"]["network_id"] == result["destinations"][0]["network_id"]
    assert route["destinations"][0]["interface_id"] == "ia"


def test_hardware_interface_ports_do_not_replace_logical_route_interfaces():
    source_hwi = "00000000-0000-0000-0000-000000000101"
    target_hwi = "00000000-0000-0000-0000-000000000102"
    physical = {
        "nodes": [
            {
                "id": "source",
                "engineeringId": "source-node",
                "ports": [{"id": "source-port", "bus": "can_fd", "hardwareInterfaceId": source_hwi}],
            },
            {
                "id": "target",
                "engineeringId": "target-node",
                "ports": [{"id": "target-port", "bus": "can_fd", "hardwareInterfaceId": target_hwi}],
            },
        ],
        "edges": [{
            "id": "edge",
            "source": "source",
            "sourcePort": "source-port",
            "target": "target",
            "targetPort": "target-port",
            "bus": "can_fd",
            "routingEntryId": "route",
        }],
    }
    route = {
        "id": "route",
        "source": {"node_id": "source-node", "interface_id": "logical-source", "protocol": "CAN_FD"},
        "destinations": [{"node_id": "target-node", "interface_id": "logical-target", "protocol": "CAN_FD"}],
    }

    result = enrich_route_from_linked_topology(route, physical)

    assert result["source"]["interface_id"] == "logical-source"
    assert result["source"]["port_id"] == source_hwi
    assert result["destinations"][0]["interface_id"] == "logical-target"
    assert result["destinations"][0]["port_id"] == target_hwi


def hardware():
    return [
        {"id": "ecu", "name": "Airbag-ECU", "device_type": "ECU"},
        {"id": "airbag-controller", "name": "Airbagsteuergerät", "device_type": "ECU"},
        {"id": "s", "name": "AirbagPressureSensor", "device_type": "SensorController"},
        {"id": "a", "name": "AirbagValveActuator", "device_type": "ActuatorController"},
        {"id": "climate", "name": "Klima", "device_type": "ECU"},
        {"id": "unknown", "name": "Unknown", "device_type": "SensorController"},
    ]


def capacity(loads=(25, 25, 25)):
    return {"id": "capacity-1", "results": {"overview": {"target_bus_load_percent": 60}, "routes": [
        {"route_id": f"r{index}", "producer": producer, "protocol": "LIN", "network_id": "network-lin", "cycle_ms": 10, "payload_bytes": 8,
         "average_load_percent": load / 1.5, "peak_load_percent": load, "burst_load_percent": load}
        for index, (producer, load) in enumerate(zip(("ecu", "s", "a"), loads))
    ]}}


def test_airbag_cluster_survives_gateway_direct_routing_and_unknowns_stay_unassigned():
    owners = system_owners(hardware(), {})
    assert {owners[key]["id"] for key in ("ecu", "airbag-controller", "s", "a")} == {"ecu"}
    assert owners["airbag-controller"]["basis"] == "inferred"
    assert owners["unknown"]["basis"] == "unassigned"


def test_direct_physical_parent_replaces_stale_inferred_owner():
    items = [
        {"id": "motor", "name": "Motorsteuerung", "device_type": "ECU"},
        {"id": "thermal", "name": "Thermomanagement", "device_type": "ECU"},
        {"id": "temperature", "name": "MotorTemperature", "device_type": "SensorController"},
    ]
    physical = {
        "nodes": [
            {"id": "n-motor", "engineeringId": "motor"},
            {"id": "n-thermal", "engineeringId": "thermal"},
            {
                "id": "n-temperature",
                "engineeringId": "temperature",
                "systemOwnerId": "thermal",
                "systemOwnerSource": "inferred",
            },
        ],
        "edges": [{"source": "n-temperature", "target": "n-motor"}],
    }

    owners = system_owners(items, physical)

    assert owners["temperature"] == {"id": "motor", "name": "Motorsteuerung", "basis": "physical"}


def test_explicit_owner_is_not_replaced_by_a_physical_hint():
    items = [
        {"id": "motor", "name": "Motorsteuerung", "device_type": "ECU"},
        {"id": "thermal", "name": "Thermomanagement", "device_type": "ECU"},
        {"id": "temperature", "name": "MotorTemperature", "device_type": "SensorController"},
    ]
    physical = {
        "nodes": [
            {"id": "n-motor", "engineeringId": "motor"},
            {"id": "n-thermal", "engineeringId": "thermal"},
            {
                "id": "n-temperature",
                "engineeringId": "temperature",
                "systemOwnerId": "thermal",
                "systemOwnerSource": "structure_tree",
            },
        ],
        "edges": [{"source": "n-temperature", "target": "n-motor"}],
    }

    owners = system_owners(items, physical)

    assert owners["temperature"] == {"id": "thermal", "name": "Thermomanagement", "basis": "structure_tree"}


def test_overload_proposes_additional_buses_without_splitting_system_ownership():
    result = plan_network_distribution(capacity(), hardware(), {})
    network = result["networks"][0]
    assert network["proposed_segments"] == 2
    assert network["additional_segments"] == 1
    assert network["projected_max_load_percent"] == 50
    assert all(segment["cluster_id"] == "ecu" for segment in network["segments"])
    assert sorted(route for segment in network["segments"] for route in segment["route_ids"]) == ["r0", "r1", "r2"]
    assert result["automatic_changes"] is False


def test_single_route_overload_is_not_hidden_by_adding_buses():
    result = plan_network_distribution(capacity((120, 20, 20)), hardware(), {}, allowed_protocols=["LIN", "CAN_FD"])
    assert result["status"] == "RESIDUAL_CONSTRAINTS"
    segment = next(item for item in result["networks"][0]["segments"] if item["load_check"] == "EXCEEDED")
    assert "20.0 ms" in segment["alternatives"][0]
    assert "CAN-FD-Alternative" in segment["alternatives"][1]


def test_stale_and_missing_capacity_never_yield_a_validated_plan():
    assert plan_network_distribution({}, hardware(), {})["status"] == "NO_CAPACITY_DATA"
    assert plan_network_distribution({**capacity(), "is_outdated": True}, hardware(), {})["status"] == "STALE_CAPACITY_DATA"


def test_whole_clusters_share_buses_instead_of_allocating_a_bus_per_device():
    source = capacity((30, 20, 20))
    source["results"]["routes"][0]["producer"] = "climate"
    result = plan_network_distribution(source, hardware(), {})
    segments = result["networks"][0]["segments"]
    assert len(segments) == 2
    airbag = next(item for item in segments if "ecu" in item["cluster_ids"])
    assert airbag["route_ids"] == ["r1", "r2"]
    assert airbag["projected_load_percent"] == 40


def test_distribution_is_reproducible_over_25_passes_without_mutation():
    source = capacity()
    before = deepcopy(source)
    expected = plan_network_distribution(source, hardware(), {})
    for _ in range(25):
        assert plan_network_distribution(source, hardware(), {}) == expected
    assert source == before


def test_device_role_cleanup_keeps_instance_numbers():
    assert normalize_hardware_name("Airbag-ECU-2") == "Airbag-2"
    assert normalize_hardware_name("Airbagsteuergerät") == "Airbag"
    assert normalize_hardware_name("BremsAktuator") == "Brems"
    assert normalize_hardware_name("AcceleratorPositionSensor") == "AcceleratorPosition"


def test_simulator_export_preserves_physical_segments_and_protocol_speed(monkeypatch):
    class Connection:
        def execute(self, query, _values):
            self.hardware = "FROM engineering_hardware_nodes" in query
            return self

        def fetchall(self):
            return [{"id": "one", "name": "One", "device_type": "ECU"}, {"id": "gateway", "name": "Central", "device_type": "Gateway"}] if self.hardware else []

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr("backend.engineering.routing.config_builder.get_connection", connection)
    routes = [
        {"id": str(index), "route_code": f"RT-{index}", "approval_state": "APPROVED",
         "source": {"node_id": "one", "network_id": network, "protocol": "LIN"},
         "destinations": [{"node_id": "gateway"}], "timing": {"cycle_time_ms": 100}}
        for index, network in enumerate(("lin-port-a", "lin-port-b", "lin-port-a"))
    ]
    config = CommunicationConfigBuilder().build(routes)["config"]
    assert {item["id"] for item in config["networks"]} == {"lin-port-a", "lin-port-b"}
    assert all(item["bitrate"] == 19_200 for item in config["networks"])
    assert {item["network_id"] for item in config["communications"]} == {"lin-port-a", "lin-port-b"}
