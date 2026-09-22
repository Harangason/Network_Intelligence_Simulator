from copy import deepcopy
from contextlib import contextmanager

from backend.engineering.physical_segments import physical_port_networks
from backend.engineering.system_clusters import system_owners
from backend.engineering.intelligence.network_planning import (
    communication_system_inventory,
    plan_network_distribution,
    split_topology_by_distribution,
)
from backend.engineering.routing.network_sync import enrich_route_from_linked_topology
from backend.engineering.structure_rules import normalize_hardware_name
from backend.engineering.routing.config_builder import CommunicationConfigBuilder
from backend.engineering import api as engineering_api


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


def test_network_route_sync_refreshes_the_workflow_source_status(monkeypatch):
    calls = []
    expected = {"counts": {"created": 0, "outdated": 0, "unchanged": 2}}

    class WorkflowProbe:
        def __init__(self, project_id):
            calls.append(("workflow", project_id))

        def refresh_source_status(self, step, *, actor=None, reason=None):
            calls.append(("refresh_source_status", step, reason, actor))

    monkeypatch.setattr(engineering_api, "WorkflowStatusService", WorkflowProbe)
    monkeypatch.setattr(
        engineering_api,
        "synchronize_network_routes",
        lambda project_id, topology, *, actor=None: expected,
    )

    result = engineering_api._synchronize_network_routes_with_workflow(
        "project-1",
        {"nodes": [], "edges": []},
        actor="network-editor",
    )

    assert result is expected
    assert calls == [
        ("workflow", "project-1"),
        (
            "refresh_source_status",
            "routing",
            "Routing-Tabelle wurde mit der physischen Netzwerktopologie synchronisiert.",
            "network-editor",
        ),
    ]


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


def test_explicit_semantic_bus_joins_disconnected_drops_without_merging_other_domains():
    source = {
        "nodes": [
            {"id": "gateway", "ports": [
                {"id": "gateway-drive", "bus": "can_fd", "hardwareInterfaceId": "gateway-can", "physicalNetworkId": "powertrain-can-fd-bus"},
                {"id": "gateway-chassis", "bus": "can_fd", "hardwareInterfaceId": "gateway-can", "physicalNetworkId": "chassis-can-fd-bus"},
            ]},
            {"id": "motor", "ports": [{"id": "motor-can", "bus": "can_fd", "physicalNetworkId": "powertrain-can-fd-bus"}]},
            {"id": "fuel", "ports": [{"id": "fuel-can", "bus": "can_fd", "physicalNetworkId": "powertrain-can-fd-bus"}]},
            {"id": "brake", "ports": [{"id": "brake-can", "bus": "can_fd", "physicalNetworkId": "chassis-can-fd-bus"}]},
        ],
        "edges": [
            {"source": "gateway", "sourcePort": "gateway-drive", "target": "motor", "targetPort": "motor-can", "bus": "can_fd", "physicalNetworkId": "powertrain-can-fd-bus"},
            {"source": "fuel", "sourcePort": "fuel-can", "target": "motor", "targetPort": "motor-can", "bus": "can_fd", "physicalNetworkId": "powertrain-can-fd-bus"},
            {"source": "gateway", "sourcePort": "gateway-chassis", "target": "brake", "targetPort": "brake-can", "bus": "can_fd", "physicalNetworkId": "chassis-can-fd-bus"},
        ],
    }

    segments = physical_port_networks(source)

    assert segments["gateway-drive"] == segments["motor-can"] == segments["fuel-can"] == "powertrain-can-fd-bus"
    assert segments["gateway-chassis"] == segments["brake-can"] == "chassis-can-fd-bus"
    assert segments["gateway-drive"] != segments["gateway-chassis"]


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


def test_gateway_is_an_explicit_system_owner_for_its_own_routes():
    owners = system_owners([
        {"id": "gateway", "name": "System", "device_type": "Gateway"},
    ], {})

    assert owners["gateway"] == {"id": "gateway", "name": "System", "basis": "explicit"}


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


def test_approved_wizard_bus_quantities_become_capacity_inventory():
    prompt = (
        '- Kommunikationssystem-Sollwerte: [{"id":"can_fd","count":10},'
        '{"id":"lin","count":25},{"id":"detected:ethernet","count":5}]\n'
    )

    assert communication_system_inventory(prompt) == {"CAN_FD": 10, "LIN": 25, "ETHERNET": 5}


def test_distribution_uses_free_same_protocol_segments_before_migration():
    result = plan_network_distribution(
        capacity(), hardware(), {}, available_protocol_counts={"LIN": 3, "CAN_FD": 1}
    )
    network = result["networks"][0]

    assert network["decision"] == "SPLIT_CURRENT_TECHNOLOGY"
    assert network["available_additional_segments"] == 2
    assert network["selected_protocol"] == "LIN"


def test_distribution_selects_capable_available_technology_when_bus_stock_is_exhausted():
    result = plan_network_distribution(
        capacity((120, 20, 20)), hardware(), {},
        parameters={"technology_defaults": {"can_fd": {"bitrate": 2_000_000, "data_bitrate": 2_000_000}}},
        available_protocol_counts={"LIN": 1, "CAN_FD": 2},
    )
    network = result["networks"][0]

    assert result["status"] == "PROPOSED"
    assert network["decision"] == "MIGRATE_TECHNOLOGY"
    assert network["selected_protocol"] == "CAN_FD"
    assert network["technology_candidates"][0]["fits_target"] is True


def test_binding_inventory_reports_existing_overprovisioning_even_without_overload():
    result = plan_network_distribution(
        capacity((10, 10, 10)), hardware(), {}, available_protocol_counts={"LIN": 0}
    )

    assert result["status"] == "RESIDUAL_CONSTRAINTS"
    assert result["networks"] == []
    assert result["inventory_constraints"] == [{
        "protocol": "LIN", "provisioned": 0, "used": 1, "free": 0, "excess": 1,
    }]


def test_unapplied_migration_does_not_free_segments_for_split_proposals():
    source = capacity((120, 20, 20))
    extra = deepcopy(capacity((40, 40))['results']['routes'])
    for row in extra:
        row.update(network_id='other-lin', route_id='other-' + row['route_id'])
    source['results']['routes'].extend(extra)
    result = plan_network_distribution(
        source, hardware(), {}, available_protocol_counts={'LIN': 2, 'CAN_FD': 1},
    )
    assert result['networks'][0]['decision'] == 'MIGRATE_TECHNOLOGY'
    assert result['remaining_protocol_inventory']['LIN'] == 0
    assert result['networks'][1]['decision'] == 'UNRESOLVED_CAPACITY_CONSTRAINT'


def test_multiple_overloaded_branches_cannot_reserve_the_same_free_segment():
    source = {
        "id": "capacity-scarce-stock",
        "results": {
            "overview": {"target_bus_load_percent": 60},
            "routes": [
                {
                    "route_id": f"{network}-r{index}", "producer": producer,
                    "protocol": "LIN", "network_id": network, "cycle_ms": 10,
                    "payload_bytes": 8, "average_load_percent": 30,
                    "peak_load_percent": 40, "burst_load_percent": 40,
                }
                for network in ("network-a", "network-b")
                for index, producer in enumerate(("ecu", "s"), start=1)
            ],
        },
    }

    result = plan_network_distribution(
        source, hardware(), {}, available_protocol_counts={"LIN": 3}
    )

    decisions = {item["network_id"]: item["decision"] for item in result["networks"]}
    assert decisions == {
        "network-a": "SPLIT_CURRENT_TECHNOLOGY",
        "network-b": "UNRESOLVED_CAPACITY_CONSTRAINT",
    }
    assert result["remaining_protocol_inventory"]["LIN"] == 0


def test_split_plan_rewrites_only_the_overloaded_branch_and_preserves_route_evidence():
    source = topology(shared=True)
    for index, edge in enumerate(source["edges"], start=1):
        route_id = f"r{index}"
        edge.update(
            physicalNetworkId="network-lin",
            physicalNetworkName="LIN branch",
            routingEntryId=route_id,
            routingEntryIds=[route_id],
            routingMetadata={route_id: {"routeId": route_id}},
        )
        for node in source["nodes"]:
            for port in node["ports"]:
                if port["id"] in {edge["sourcePort"], edge["targetPort"]}:
                    port.update(physicalNetworkId="network-lin", physicalNetworkName="LIN branch")
    unaffected = deepcopy(source["edges"][0])
    unaffected.update(
        id="edge-unaffected",
        physicalNetworkId="network-can-fd",
        physicalNetworkName="Powertrain CAN-FD",
        routingEntryId="r3",
        routingEntryIds=["r3"],
        routingMetadata={"r3": {"routeId": "r3"}},
    )
    source["edges"].append(unaffected)
    plan = {
        "networks": [{
            "network_id": "network-lin", "decision": "SPLIT_CURRENT_TECHNOLOGY",
            "segments": [
                {"name": "network-lin-CAP-S01", "route_ids": ["r1"]},
                {"name": "network-lin-CAP-S02", "route_ids": ["r2"]},
            ],
        }]
    }

    repaired, changed = split_topology_by_distribution(source, plan)

    assert changed == 2
    assert {edge["physicalNetworkId"] for edge in repaired["edges"]} == {
        "network-lin-CAP-S01", "network-lin-CAP-S02", "network-can-fd",
    }
    assert sorted(edge["routingEntryId"] for edge in repaired["edges"]) == ["r1", "r2", "r3"]
    assert next(edge for edge in repaired["edges"] if edge["id"] == "edge-unaffected") == unaffected


def test_single_route_overload_is_not_hidden_by_adding_buses():
    result = plan_network_distribution(capacity((120, 20, 20)), hardware(), {}, allowed_protocols=["LIN", "CAN_FD"])
    assert result["status"] == "PROPOSED"
    segment = next(item for item in result["networks"][0]["segments"] if item["load_check"] == "EXCEEDED")
    assert "20.0 ms" in segment["alternatives"][0]
    assert result["networks"][0]["decision"] == "MIGRATE_TECHNOLOGY"
    assert result["networks"][0]["selected_protocol"] == "CAN_FD"


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
            self.addressing = "engineering_hardware_interfaces" in query or "engineering_technology_address_bindings" in query
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


def test_simulator_export_updates_interface_technology_with_route_network(monkeypatch):
    class Connection:
        def execute(self, query, _values):
            self.hardware = "FROM engineering_hardware_nodes" in query
            self.addressing = "engineering_hardware_interfaces" in query or "engineering_technology_address_bindings" in query
            return self

        def fetchall(self):
            if self.addressing:
                return []
            if self.hardware:
                return [
                    {"id": "source", "name": "Source", "device_type": "ECU"},
                    {"id": "target", "name": "Target", "device_type": "ECU"},
                ]
            return [{
                "id": "target-interface",
                "name": "Target Ethernet",
                "hardware_node_id": "target",
                "interface_type": "ETHERNET",
                "configuration": {"network_id": "ethernet-old"},
            }]

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr("backend.engineering.routing.config_builder.get_connection", connection)
    route = {
        "id": "route-1",
        "route_code": "RT-1",
        "approval_state": "APPROVED",
        "source": {"node_id": "source", "network_id": "powertrain-can", "protocol": "CAN_FD"},
        "destinations": [{"node_id": "target", "interface_id": "target-interface"}],
        "timing": {"cycle_time_ms": 10},
    }

    config = CommunicationConfigBuilder().build([route])["config"]
    target = next(item for item in config["hardware"]["devices"] if item["id"] == "target")
    assert target["interfaces"] == [{
        "id": "target-interface",
        "name": "Target Ethernet",
        "technology": "can_fd",
        "network": "powertrain-can",
        "physical_port_ref": "target:target-interface",
    }]
