"""Declared parameter presence is distinct from complete technology assurance."""
from copy import deepcopy

import pytest

from backend.app import create_app
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as REGISTRY
from backend.communication.technologies.core.registry import TechnologyRegistry


def profile(identifier="test_bus", **extra):
    return {"id": identifier, "label": identifier, "layer": "DATA_LINK",
            "implementation_status": "PLANNED", "rate_model": {"fields": []}, **extra}


def test_all_profiles_export_declared_requirements_without_claiming_completeness():
    for row in REGISTRY.list_all():
        assert set(row["rate_model"].get("fields", [])) <= set(row["required_parameters"])
        assert row["required_parameter_completeness"] == "UNVERIFIED"
        assert row["required_parameter_scope"] == "DECLARED_PROFILE_FIELDS"
    assert REGISTRY.profile("CANFD")["required_parameters"] == ["data_bitrate_bps", "nominal_bitrate_bps"]
    assert REGISTRY.profile("gpio")["required_parameters"] == []


@pytest.mark.parametrize("parameters", [{}, {"station_name": None}, {"station_name": "  "}])
def test_missing_non_rate_requirement_blocks_even_without_executable_model(parameters):
    registry = TechnologyRegistry()
    registry.register_defaults([profile(required_parameters=["station_name"])])
    original = deepcopy(parameters)
    result = registry.validate_parameters("test_bus", parameters)
    assert result["status"] == "UNVERIFIED"
    assert result["findings"][0]["parameter"] == "station_name"
    assert result["findings"][0]["code"] == "TECHNOLOGY_PARAMETER_MISSING"
    assert parameters == original


def test_required_schema_flag_is_checked_without_applying_schema_default():
    registry = TechnologyRegistry()
    registry.register_profile("test_bus", profile(parameter_schema={
        "mode": {"required": True, "default": "example"}, "optional": {"required": False}}))
    parameters = {}
    result = registry.validate_parameters("test_bus", parameters)
    assert result["required_parameters"] == ["mode"]
    assert result["status"] == "UNVERIFIED" and parameters == {}
    assert registry.validate_parameters("test_bus", {"mode": "explicit"})["status"] == "VALID"


@pytest.mark.parametrize("value", [False, 0])
def test_present_false_or_zero_values_are_not_confused_with_missing(value):
    registry = TechnologyRegistry()
    registry.register_profile("test_bus", profile(required_parameters=["parameter"]))
    result = registry.validate_parameters("test_bus", {"parameter": value})
    assert result["status"] == "VALID"
    assert result["validation_scope"] == "DECLARED_PROFILE_PARAMETERS"
    assert result["required_parameter_completeness"] == "UNVERIFIED"


def test_lower_layer_requirements_are_not_lost_and_values_are_not_invented():
    registry = TechnologyRegistry()
    registry.register_profile("lower", profile("lower", required_parameters=["physical_mode"]))
    registry.register_profile("upper", profile("upper", layer="APPLICATION",
        default_stack=["lower", "upper"], required_parameters=["endpoint"]))
    result = registry.validate_parameters("upper", {"endpoint": "test"})
    assert result["required_parameters"] == ["endpoint", "physical_mode"]
    assert result["status"] == "UNVERIFIED"
    assert [x["parameter"] for x in result["findings"]] == ["physical_mode"]


@pytest.mark.parametrize("declaration", [None, "mode", {}, [""], [" mode"], [4]])
def test_malformed_declarations_reject_registration_atomically(declaration):
    registry = TechnologyRegistry()
    with pytest.raises(ValueError, match="required_parameters"):
        registry.register_profile("test_bus", profile(required_parameters=declaration))
    assert registry.profiles() == [] and registry._aliases == {}


def test_exported_declarations_are_copied_and_http_visible():
    row = REGISTRY.profile("lin")
    row["required_parameters"].append("foreign")
    assert REGISTRY.profile("lin")["required_parameters"] == ["bitrate_bps"]
    response = create_app(testing=True).test_client().get('/api/technologies')
    assert response.status_code == 200
    profiles = {p["id"]: p for domain in response.get_json()["domains"] for p in domain["technologies"]}
    assert profiles["lin"]["required_parameters"] == ["bitrate_bps"]
    assert profiles["lin"]["required_parameter_completeness"] == "UNVERIFIED"
