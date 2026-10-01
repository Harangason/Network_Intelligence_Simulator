from backend.engineering.generation_rule_manager import (
    industry_candidates,
    resolve_generation_policy,
    technology_ids_from_task,
)
from backend.engineering.requirement_expansion_modules.engine import expand_requirement


def test_explicit_industry_controls_only_the_template_path():
    decision = resolve_generation_policy(
        "Gebäudeautomation mit BACnet/IP; Automotive ist ausgeschlossen.",
        industry="building_automation",
        bus_types=["bacnet_ip"],
    )

    assert decision["status"] == "READY"
    assert decision["industry"]["id"] == "building_automation"
    assert decision["industry"]["template_path"] == "industry_template:building_automation"
    assert decision["bus_types"][0]["path"] == "switched_packet_network"
    assert decision["guardrails"]["industry_does_not_define_bus"] is True


def test_industry_detection_covers_non_automotive_spatial_domains():
    assert industry_candidates("Drohne mit vier Rotorarmen") == {"aerospace"}
    assert industry_candidates("Roboterzelle einer Fabrik") == {"industrial_automation", "robotics_ros"}
    assert industry_candidates("Etagen einer Gebäudeautomation") == {"building_automation"}
    assert industry_candidates("Schienenfahrzeug im Bahnbetrieb") == {"rail"}


def test_mixed_bus_task_gets_independent_transport_paths():
    decision = resolve_generation_policy(
        "Industrieanlage mit CAN-FD, EtherCAT und Modbus RTU",
        industry="industrial_automation",
    )

    assert decision["status"] == "READY"
    assert [item["id"] for item in decision["bus_types"]] == ["can_fd", "ethercat", "modbus_rtu"]
    assert decision["generation_path"]["transport_paths"] == [
        "arbitrated_can_bus",
        "industrial_realtime_ethernet",
        "serial_field_bus",
    ]
    assert all(item["generator"] == "TechnologyTransportGenerator" for item in decision["bus_types"])
    assert decision["industry"]["source_modules"]
    assert all(item["source"]["source_modules"] for item in decision["bus_types"])
    assert decision["provenance"]["policy_source"] == "backend.engineering.generation_rule_manager"
    assert decision["guardrails"]["reviewed_history_is_advisory_only"] is True


def test_can_fd_does_not_also_select_classic_can():
    assert [item["id"] for item in technology_ids_from_task("CAN-FD mit 2 Mbit/s")] == ["can_fd"]
    assert technology_ids_from_task("The controller can communicate with the gateway") == []


def test_bus_never_silently_selects_an_industry():
    decision = resolve_generation_policy("CAN-FD und Ethernet verbinden")

    assert decision["industry"]["id"] is None
    assert decision["industry"]["template_path"] == "industry_template:blocked"
    assert {item["id"] for item in decision["bus_types"]} == {"can_fd", "ethernet"}
    assert any(item["code"] == "INDUSTRY_REQUIRED" for item in decision["findings"])
    assert industry_candidates("BACnet/IP, NMEA 2000 und WirelessHART") == set()


def test_ambiguous_industry_blocks_only_the_industry_path():
    decision = resolve_generation_policy("Automotive oder Industrial Automation mit Ethernet")

    assert decision["status"] == "NEEDS_INPUT"
    assert decision["industry"]["id"] is None
    assert any(item["code"] == "AMBIGUOUS_INDUSTRY" for item in decision["findings"])
    assert decision["bus_types"][0]["path"] == "switched_packet_network"


def test_structured_industry_conflict_is_visible_instead_of_overwritten():
    decision = resolve_generation_policy(
        "- Projekt-Modelltyp: automotive\n- Netzwerktechnologien: CAN-FD (can_fd)",
        industry="rail",
        bus_types=["can_fd"],
    )

    assert decision["status"] == "NEEDS_INPUT"
    assert any(item["code"] == "INDUSTRY_CONTEXT_CONFLICT" for item in decision["findings"])


def test_decision_hash_is_stable_and_changes_with_bus_path():
    first = resolve_generation_policy("Fahrzeug", industry="automotive", bus_types=["lin"])
    repeated = resolve_generation_policy("Fahrzeug", industry="automotive", bus_types=["lin"])
    changed = resolve_generation_policy("Fahrzeug", industry="automotive", bus_types=["can_fd"])

    assert first["decision_sha256"] == repeated["decision_sha256"]
    assert first["decision_sha256"] != changed["decision_sha256"]


def test_requirement_expansion_uses_industry_specific_camera_assumptions():
    automotive = expand_requirement(
        "Kamera im Fahrzeug mit Ethernet",
        domain="automotive",
    )
    building = expand_requirement(
        "Kamera in der Gebäudeautomation mit Ethernet",
        domain="building_automation",
    )
    automotive_assumptions = {item["concept"]: item["proposed_value"] for item in automotive["assumptions"]}
    building_assumptions = {item["concept"]: item["proposed_value"] for item in building["assumptions"]}

    assert automotive_assumptions["camera_operating_frame"] == "VehicleReferenceFrame"
    assert building_assumptions["camera_operating_frame"] == "BuildingReferenceFrame"
    assert automotive_assumptions["image_transport_policy"] != building_assumptions["image_transport_policy"]
    assert building["interpretation"]["generation_policy"]["industry"]["id"] == "building_automation"
