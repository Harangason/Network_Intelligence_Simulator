"""Explicit PHY and medium-access models; missing hardware never becomes a default."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any


class MediumAccessModel(StrEnum):
    BITWISE_PRIORITY = "BITWISE_PRIORITY"
    MASTER_SCHEDULED = "MASTER_SCHEDULED"
    FULL_DUPLEX_SWITCHED = "FULL_DUPLEX_SWITCHED"
    MASTER_SLAVE = "MASTER_SLAVE"
    WIRED_AND_ARBITRATION = "WIRED_AND_ARBITRATION"
    POINT_TO_POINT = "POINT_TO_POINT"
    PLCA = "PLCA"
    TOKEN_PASSING = "TOKEN_PASSING"
    CENTRAL_SCHEDULED_FREQUENCY_HOPPING = "CENTRAL_SCHEDULED_FREQUENCY_HOPPING"
    VARIANT_DEPENDENT = 'VARIANT_DEPENDENT'
    CSMA_CD = 'CSMA_CD'


@dataclass(frozen=True)
class ArbitrationModel:
    id: str
    access: MediumAccessModel
    priority_source: str | None = None
    non_destructive: bool = False
    deterministic: bool = False
    worst_case_delay_model: str | None = None


@dataclass(frozen=True)
class PhysicalLayerProfile:
    id: str
    technology_id: str
    medium_type: str
    required_conductors: tuple[str, ...]
    pair_count: int | None
    differential: bool
    duplex_mode: str
    allowed_topologies: tuple[str, ...]
    termination_count: int | None
    access_model: MediumAccessModel
    arbitration: ArbitrationModel | None = None
    phy_variant: str | None = None


@dataclass(frozen=True)
class PhysicalRealization:
    id: str
    connection_id: str
    technology_id: str
    conductors: tuple[str, ...] | None
    pair_count: int | None
    topology: str | None
    termination_count: int | None
    phy_variant: str | None
    length_m: float | None
    chip_select_count: int | None
    slave_count: int | None
    available_channel_count: int | None
    used_channel_count: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhysicalRealization:
        def integer(name: str) -> int | None:
            value = data.get(name)
            return value if isinstance(value, int) and not isinstance(value, bool) else None

        conductors = data.get("conductors")
        return cls(
            id=str(data.get("id") or ""), connection_id=str(data.get("connection_id") or ""),
            technology_id=str(data.get("technology_id") or data.get("technology") or "").lower().replace("-", "_"),
            conductors=tuple(str(value).upper() for value in conductors) if isinstance(conductors, list) else None,
            pair_count=integer("pair_count"), topology=str(data["topology"]).upper() if data.get("topology") else None,
            termination_count=integer("termination_count"),
            phy_variant=str(data["phy_variant"]).upper() if data.get("phy_variant") else None,
            length_m=float(data["length_m"]) if isinstance(data.get("length_m"), (int, float)) and not isinstance(data["length_m"], bool) else None,
            chip_select_count=integer("chip_select_count"), slave_count=integer("slave_count"),
            available_channel_count=integer("available_channel_count"), used_channel_count=integer("used_channel_count"),
        )


from importlib import import_module
from backend.nis.communication.catalog import TECHNOLOGY_IDS

def _physical_owners():
    from json import loads
    from pathlib import Path
    result = {}
    for key in TECHNOLOGY_IDS:
        path = Path(__file__).parents[1] / 'technologies' / key / 'physical.json'
        if path.is_file():
            result[key] = loads(path.read_text(encoding='utf-8'))
    return result

def _physical_definition(value):
    value = dict(value)
    value['access_model'] = MediumAccessModel(value['access_model'])
    for key in ('required_conductors', 'allowed_topologies'):
        value[key] = tuple(value[key])
    if value.get('arbitration'):
        arbitration = dict(value['arbitration'])
        arbitration['access'] = MediumAccessModel(arbitration['access'])
        value['arbitration'] = ArbitrationModel(**arbitration)
    return PhysicalLayerProfile(**value)

_PHYSICAL_OWNERS = _physical_owners()
PHYSICAL_PROFILES = {key: _physical_definition(value['profile']) for key,value in _PHYSICAL_OWNERS.items()}
PROFILE_ALIASES = {alias: key for key,value in _PHYSICAL_OWNERS.items() for alias in value.get('aliases', [])}
PHY_PAIRS = _PHYSICAL_OWNERS['ethernet']['phy_pairs']
CAN_ARBITRATION = PHYSICAL_PROFILES['can'].arbitration

def _physical_implementation(profile):
    return import_module(f'backend.nis.communication.technologies.{profile.technology_id}.physical') if profile else None

def _resolve_profile(data, realization, profile):
    hook = getattr(_physical_implementation(profile), 'resolve_profile', None)
    return hook(data, realization, profile) if hook else (profile, False)

def _physical_rule(phase, data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus):
    hook = getattr(_physical_implementation(profile), phase, None)
    return hook(data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus) if hook else (profile, expected_pairs, resolved_access, unresolved_modbus)

def _allowed_topologies(realization, profile):
    hook = getattr(_physical_implementation(profile), 'allowed_topologies', None)
    return hook(realization, profile) if hook else profile.allowed_topologies


def physical_profile(technology_id: str) -> PhysicalLayerProfile | None:
    normalized = str(technology_id or "").lower().replace("-", "_")
    return PHYSICAL_PROFILES.get(PROFILE_ALIASES.get(normalized, normalized))


def validate_physical_realization(data: dict[str, Any]) -> dict[str, Any]:
    realization = PhysicalRealization.from_dict(data)
    profile = physical_profile(realization.technology_id)
    unresolved_modbus=False
    profile, unresolved_modbus = _resolve_profile(data, realization, profile)
    findings: list[dict[str, str]] = []
    resolved_access=profile.access_model.value if profile else None

    def finding(severity: str, code: str, message: str) -> None:
        findings.append({"severity": severity, "code": code, "message": message})

    expected_pairs = profile.pair_count if profile else None

    if profile is None:
        finding("REVIEW", "PHYSICAL_PROFILE_MISSING", "No registered physical profile for this technology.")
    else:
        profile, expected_pairs, resolved_access, unresolved_modbus = _physical_rule('validate_duplex', data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus)
        profile, expected_pairs, resolved_access, unresolved_modbus = _physical_rule('validate_variant', data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus)
        if profile.medium_type == 'RADIO' and realization.conductors:
            finding('BLOCKER','PHYSICAL_CONDUCTOR_MISMATCH','Radio links do not use wired bus conductors.')
        if realization.conductors is None and profile.required_conductors:
            finding("REVIEW", "PHYSICAL_CONDUCTORS_UNKNOWN", "Conductor assignment is not evidenced.")
        elif realization.conductors is not None:
            missing = set(profile.required_conductors) - set(realization.conductors)
            if missing:
                finding("BLOCKER", "PHYSICAL_CONDUCTOR_MISMATCH", f"Required conductors missing: {', '.join(sorted(missing))}.")
            if len(realization.conductors) != len(set(realization.conductors)):
                finding("BLOCKER", "PHYSICAL_CONDUCTOR_DUPLICATE", "Conductor names must be unique.")
        expected_pairs = profile.pair_count
        profile, expected_pairs, resolved_access, unresolved_modbus = _physical_rule('expected_pairs', data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus)
        profile, expected_pairs, resolved_access, unresolved_modbus = _physical_rule('validate_medium', data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus)
        profile, expected_pairs, resolved_access, unresolved_modbus = _physical_rule('validate_access', data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus)
        profile, expected_pairs, resolved_access, unresolved_modbus = _physical_rule('validate_phy_selection', data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus)
        if expected_pairs is not None:
            if realization.pair_count is None:
                finding("REVIEW", "PHYSICAL_PAIR_COUNT_UNKNOWN", "Physical pair count is not evidenced.")
            elif realization.pair_count != expected_pairs:
                finding("BLOCKER", "PHYSICAL_PAIR_COUNT_MISMATCH", "Pair count is incompatible with the physical profile.")
        allowed_topologies = _allowed_topologies(realization, profile)
        if realization.topology is None:
            finding("REVIEW", "PHYSICAL_TOPOLOGY_UNKNOWN", "Physical topology is not evidenced.")
        elif realization.topology not in allowed_topologies:
            finding("BLOCKER", "PHYSICAL_TOPOLOGY_INVALID", "Topology is incompatible with the physical profile.")
        if profile.termination_count is not None:
            if realization.termination_count is None:
                finding("REVIEW", "PHYSICAL_TERMINATION_UNKNOWN", "Termination count is not evidenced.")
            elif realization.termination_count != profile.termination_count:
                finding("BLOCKER", "PHYSICAL_TERMINATION_INVALID", "Termination count is incompatible with the bus profile.")
        profile, expected_pairs, resolved_access, unresolved_modbus = _physical_rule('validate_resources', data, realization, profile, finding, expected_pairs, resolved_access, unresolved_modbus)
    if realization.length_m is not None and (not isfinite(realization.length_m) or realization.length_m < 0):
        finding("BLOCKER", "PHYSICAL_LENGTH_INVALID", "Physical length must be a finite non-negative value.")
    if (realization.used_channel_count is not None and realization.available_channel_count is not None and
            realization.used_channel_count > realization.available_channel_count):
        finding("BLOCKER", "PHYSICAL_CHANNEL_LIMIT_EXCEEDED", "Used physical channels exceed hardware capability.")
    return {
        "realization_id": realization.id, "technology_id": realization.technology_id,
        "physical_layer_profile_id": profile.id if profile else None,
        "resolved_medium_access_model": resolved_access,
        "status": "INVALID" if any(item["severity"] == "BLOCKER" for item in findings) else
                  "REVIEW_REQUIRED" if findings else "VALID",
        "findings": findings,
    }
