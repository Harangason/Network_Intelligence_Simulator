"""Registry identity is enumerable; registration cannot stand in for evidence."""
from copy import deepcopy

import pytest

from backend.app import create_app
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as REGISTRY
from backend.communication.technologies.core.registry import TechnologyRegistry


def definition(label, **extra):
    return {"label": label, "layer": "DATA_LINK", "implementation_status": "PLANNED",
            "rate_model": {"fields": []}, **extra}


def test_every_profile_exposes_canonical_identity_aliases_and_honest_verification():
    profiles = REGISTRY.list_all()
    assert profiles == REGISTRY.profiles()
    assert len(profiles) == len({p["canonical_id"] for p in profiles})
    assert {p["id"] for p in profiles} == set(REGISTRY._profiles)
    for profile in profiles:
        assert profile["canonical_id"] == profile["id"] == REGISTRY.normalize_id(profile["id"])
        assert profile["display_name"] == profile["label"]
        assert profile["classification"]
        assert isinstance(profile["aliases"], list)
        assert profile["verification_status"] == "UNVERIFIED"
        assert profile["verification_scope"] == "REGISTRY_TEMPLATE"
        assert profile["fallback_allowed"] is False
        for alias in profile["aliases"]:
            assert REGISTRY.profile(alias)["canonical_id"] == profile["id"], (profile["id"], alias)
    assert set(REGISTRY._aliases.values()) <= {p["id"] for p in profiles}


def test_ros_aliases_are_exported_and_can_xl_never_becomes_can_fd():
    assert {"ROS2", "ROS_2", "ros-2"} <= set(REGISTRY.profile("ros2")["aliases"])
    for alias in ("ROS2", "ROS_2", "ros-2", "ROS 2"):
        assert REGISTRY.profile(alias)["id"] == "ros2"
    assert REGISTRY.profile("CANXL")["id"] == "can_xl"
    assert REGISTRY.profile("CANFD")["id"] == "can_fd"
    assert REGISTRY.profile("CANXL")["capacity_evidence"]["status"] == "MODEL_MISSING"
    # A device class must not be translated to a non-existent technology identity.
    assert REGISTRY.normalize_id("SPS") == "sps"
    assert REGISTRY.validate_parameters("SPS", {})["status"] == "UNKNOWN"


@pytest.mark.parametrize("alias", ["First Bus", "first_bus"])
def test_alias_cannot_hijack_an_existing_canonical_profile(alias):
    registry = TechnologyRegistry()
    registry.register_profile("first_bus", definition("First Bus"))
    before = registry.profiles(), deepcopy(registry._aliases)
    with pytest.raises(ValueError, match="alias"):
        registry.register_profile("second_bus", definition("Second Bus", aliases=[alias]))
    assert (registry.profiles(), registry._aliases) == before


def test_alias_cannot_hijack_a_reserved_builtin_identity():
    registry = TechnologyRegistry()
    with pytest.raises(ValueError, match="alias"):
        registry.register_profile("custom_bus", definition("Custom Bus", aliases=["CANFD"]))
    assert registry.profiles() == [] and registry._aliases == {}


def test_description_cannot_assert_project_verification_or_foreign_canonical_id():
    registry = TechnologyRegistry()
    registry.register_profile("custom_bus", definition("Custom Bus", canonical_id="can_fd",
        verification_status="VERIFIED", fallback_allowed=True))
    profile = registry.profile("custom_bus")
    assert profile["canonical_id"] == "custom_bus"
    assert profile["verification_status"] == "UNVERIFIED"
    assert profile["fallback_allowed"] is False
    profile["aliases"].append("mutated")
    assert "mutated" not in registry.profile("custom_bus")["aliases"]


def test_rejected_generated_profile_update_preserves_previous_registration():
    registry = TechnologyRegistry()
    profile = definition("Generated Bus", id="generated_bus", aliases=["GBUS"],
                         knowledge_origin="GENERATED_TECHNOLOGY_PACK")
    registry.register_generated_profile(profile)
    before = registry.profiles(), deepcopy(registry._aliases)
    with pytest.raises(ValueError, match="alias"):
        registry.register_generated_profile({**profile, "aliases": ["CANFD"]})
    assert (registry.profiles(), registry._aliases) == before
    assert registry.profile("GBUS")["id"] == "generated_bus"


def test_generated_profile_update_via_alias_preserves_canonical_identity():
    registry = TechnologyRegistry()
    profile = definition("Generated Bus", id="generated_bus", aliases=["GBUS"],
                         knowledge_origin="GENERATED_TECHNOLOGY_PACK")
    registry.register_generated_profile(profile)
    registry.register_generated_profile({**profile, "id": "GBUS", "aliases": ["SECOND"]})
    assert registry.profile("SECOND")["id"] == "generated_bus"
    assert registry.profile("generated_bus")["canonical_id"] == "generated_bus"
    assert len(registry.profiles()) == 1


def test_http_catalog_preserves_registry_identity_and_verification_metadata():
    response = create_app().test_client().get('/api/technologies')
    assert response.status_code == 200
    catalog = response.get_json()
    exported = {p['id']: p for domain in catalog['domains'] for p in domain['technologies']}
    assert set(exported) == {p['id'] for p in REGISTRY.list_all()}
    for tid, profile in exported.items():
        assert profile['canonical_id'] == tid
        assert profile['verification_status'] == 'UNVERIFIED'
        assert profile['aliases'] == REGISTRY.profile(tid)['aliases']
