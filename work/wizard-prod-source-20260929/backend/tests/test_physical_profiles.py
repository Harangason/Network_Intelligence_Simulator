"""Physical profile checks preserve missing evidence and reject impossible wiring."""

from pathlib import Path

import pytest

from backend.app.simulation_service import SimulationService
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.engineering.capacity import service as capacity_service
from backend.engineering.capacity.service import PreflightService
from backend.engineering.workflow.models import default_statuses, default_versions


def codes(result):
    return {item["code"] for item in result["findings"]}


def test_registered_technologies_link_to_explicit_phy_and_access_models():
    can_fd = registry.profile("can_fd")
    assert can_fd["physical_layer_profile_id"] == "CAN_DIFFERENTIAL_PAIR"
    assert can_fd["medium_access_model"] == "BITWISE_PRIORITY"
    assert can_fd["arbitration_model_id"] == "CAN_NON_DESTRUCTIVE"
    assert registry.profile("lin")["physical_layer_profile_id"] == "LIN_SINGLE_WIRE"
    assert registry.profile("ethercat")["medium_access_model"] == "FULL_DUPLEX_SWITCHED"


def test_can_pair_and_terminations_are_explicitly_validated():
    valid = {"id": "bus", "technology_id": "can_fd", "conductors": ["CAN_H", "CAN_L"],
             "pair_count": 1, "topology": "BUS", "termination_count": 2}
    assert registry.validate_physical_realization(valid)["status"] == "VALID"
    missing = registry.validate_physical_realization({"id": "bus", "technology_id": "can_fd"})
    assert missing["status"] == "REVIEW_REQUIRED"
    assert "PHYSICAL_CONDUCTORS_UNKNOWN" in codes(missing)
    wrong = registry.validate_physical_realization({**valid, "conductors": ["CAN_H"], "termination_count": 3})
    assert wrong["status"] == "INVALID"
    assert {"PHYSICAL_CONDUCTOR_MISMATCH", "PHYSICAL_TERMINATION_INVALID"} <= codes(wrong)


def test_lin_cannot_masquerade_as_can_and_spi_needs_chip_selects():
    lin = registry.validate_physical_realization({"technology_id": "lin", "conductors": ["CAN_H", "CAN_L"],
                                                  "pair_count": 0, "topology": "BUS"})
    assert "PHYSICAL_CONDUCTOR_MISMATCH" in codes(lin)
    spi = registry.validate_physical_realization({"technology_id": "spi", "conductors": ["SCLK", "MOSI", "MISO"],
                                                  "pair_count": 0, "topology": "STAR", "slave_count": 3,
                                                  "chip_select_count": 2})
    assert "SPI_CHIP_SELECT_EXHAUSTED" in codes(spi)


def test_ethernet_phy_variant_and_shared_topology_must_match():
    t1 = {"technology_id": "ethernet", "phy_variant": "100BASE_T1", "pair_count": 1,
          "topology": "POINT_TO_POINT"}
    assert registry.validate_physical_realization(t1)["status"] == "VALID"
    wrong = registry.validate_physical_realization({**t1, "pair_count": 4})
    assert "PHYSICAL_PAIR_COUNT_MISMATCH" in codes(wrong)
    shared = registry.validate_physical_realization({**t1, "phy_variant": "10BASE_T1S", "topology": "BUS"})
    assert shared["status"] == "VALID"
    assert shared["resolved_medium_access_model"] == "PLCA"
    assert "PHYSICAL_TOPOLOGY_INVALID" in codes(registry.validate_physical_realization({**t1,
        "phy_variant": "10BASE_T1S", "topology": "STAR"}))


def test_simulation_preparation_rejects_an_explicit_impossible_phy(tmp_path: Path):
    with pytest.raises(ValueError, match="PHYSICAL_PAIR_COUNT_MISMATCH"):
        SimulationService().prepare_config({"config": {
            "physical_realizations": [{"technology_id": "ethernet", "phy_variant": "100BASE_T1",
                "pair_count": 4, "topology": "POINT_TO_POINT"}],
        }}, tmp_path)


def test_preflight_exposes_phy_blocker_in_unified_result(monkeypatch):
    state = {"versions": default_versions(), "statuses": {key: "COMPLETE" for key in default_statuses()},
             "parameters": {"physical_realizations": [{"id": "physical-can", "technology_id": "can_fd",
                 "conductors": ["CAN_H", "CAN_L"], "pair_count": 1, "topology": "BUS",
                 "termination_count": 1}]}, "topology": {"nodes": [], "edges": []}}
    service = PreflightService("isolated-phy")
    monkeypatch.setattr(service.workflow, "get", lambda: state)
    monkeypatch.setattr(service.workflow, "latest_analysis", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service.workflow, "create_analysis_snapshot", lambda *_args, **_kwargs: {"id": "snapshot"})
    monkeypatch.setattr(capacity_service, "list_objects", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(capacity_service, "list_routes", lambda **_kwargs: [])
    result = service.run()
    assert "PHYSICAL_TERMINATION_INVALID" in {item["code"] for item in result["category_checks"]["physical"]}
    assert result["preflight_status"] == "BLOCKED"
