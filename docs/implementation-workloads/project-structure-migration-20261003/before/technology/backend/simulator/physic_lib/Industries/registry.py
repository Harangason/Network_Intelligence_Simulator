"""Central class-based registry assembled from industry generators."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Sequence

from .Aerospace.generators import AerospaceTechnologyGenerator
from .Automotive.generators import AutomotiveTechnologyGenerator
from .BuildingAutomation.generators import BuildingTechnologyGenerator
from .EmbeddedSystems.generators import EmbeddedTechnologyGenerator
from .Energy.generators import EnergyTechnologyGenerator
from .Generic.generators import GenericNetworkTechnologyGenerator
from .IndustrialAutomation.generators import IndustrialTechnologyGenerator
from .Marine.generators import MarineTechnologyGenerator
from .Rail.generators import RailTechnologyGenerator
from .RoboticsROS.generators import RoboticsTechnologyGenerator
from .generator_base import BaseTechnologyGenerator


ALIASES = {
    "classic_can": "can",
    "can_classic": "can",
    "fd": "can_fd",
    "canfd": "can_fd",
    "xl": "can_xl",
    "canxl": "can_xl",
    "automotive ethernet": "automotive_ethernet",
    "100base_t1": "automotive_ethernet",
    "1000base_t1": "automotive_ethernet",
    "some/ip": "someip",
    "ethernet/ip": "ethernet_ip",
    "ethernetip": "ethernet_ip",
    "modbus": "modbus_rtu",
    "afdx": "arinc664_afdx",
    "arinc664": "arinc664_afdx",
    "mil1553": "mil_std_1553",
    "1553": "mil_std_1553",
    "i²c": "i2c",
    "1-wire": "one_wire",
    "nmea_0183": "nmea0183",
    "nmea_2000": "nmea2000",
    "bacnet": "bacnet_ip",
    "dds": "dds_rtps",
}


class TechnologyRegistry:
    """Build, extend and query the complete technology catalog."""

    DEFAULT_GENERATORS: tuple[type[BaseTechnologyGenerator], ...] = (
        AutomotiveTechnologyGenerator,
        IndustrialTechnologyGenerator,
        EmbeddedTechnologyGenerator,
        AerospaceTechnologyGenerator,
        RailTechnologyGenerator,
        MarineTechnologyGenerator,
        BuildingTechnologyGenerator,
        EnergyTechnologyGenerator,
        RoboticsTechnologyGenerator,
        GenericNetworkTechnologyGenerator,
    )

    def __init__(
        self,
        generators: Sequence[BaseTechnologyGenerator] | None = None,
    ) -> None:
        self.generators = list(generators or (generator() for generator in self.DEFAULT_GENERATORS))
        self._builtin = self._generate_builtin()

    @staticmethod
    def normalize_id(value: Any) -> str:
        token = str(value or "custom").strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
        while "__" in token:
            token = token.replace("__", "_")
        alias_key = str(value or "").strip().lower()
        return ALIASES.get(alias_key, ALIASES.get(token, token or "custom"))

    def _generate_builtin(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for generator in self.generators:
            for technology_id, profile in generator.generate().items():
                normalized = self.normalize_id(technology_id)
                if normalized in result:
                    raise ValueError(f"Duplicate technology profile: {normalized}")
                result[normalized] = profile.to_dict()
        return result

    @property
    def builtin(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._builtin)

    def build(self, custom_profiles: Iterable[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
        registry = self.builtin
        for raw in custom_profiles or []:
            if not isinstance(raw, dict):
                continue
            technology_id = self.normalize_id(raw.get("id") or raw.get("name"))
            profile = {
                "kind": str(raw.get("kind") or "bus"),
                "family": str(raw.get("family") or "custom"),
                "medium": str(raw.get("medium") or "custom"),
                "topology": str(raw.get("topology") or "custom"),
                "access": str(raw.get("access") or "custom"),
                "addressing": str(raw.get("addressing") or "custom"),
                "timing_model": str(raw.get("timing_model") or raw.get("access") or "custom"),
                "error_model": str(raw.get("error_model") or "custom"),
                "default_bitrate": raw.get("default_bitrate"),
                "max_payload_bytes": raw.get("max_payload_bytes"),
                "native_formats": list(raw.get("native_formats") or []),
                "custom": True,
            }
            profile.update({key: deepcopy(value) for key, value in raw.items() if key not in {"id", "name"}})
            registry[technology_id] = profile
        return registry

    def resolve(
        self,
        value: Any,
        registry: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        technology_id = self.normalize_id(value)
        selected = (registry or self._builtin).get(technology_id)
        if selected is None:
            return {
                "id": technology_id,
                "kind": "bus",
                "family": "custom",
                "medium": "custom",
                "topology": "custom",
                "access": "custom",
                "addressing": "custom",
                "timing_model": "custom",
                "error_model": "technology_specific",
                "default_bitrate": None,
                "max_payload_bytes": None,
                "native_formats": [],
                "custom": True,
                "requires_profile": True,
            }
        return {"id": technology_id, **deepcopy(selected)}

    def summary(self, registry: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        selected = registry or self._builtin
        return {
            "open_registry": True,
            "custom_technologies_supported": True,
            "technology_count": len(selected),
            "families": sorted({str(profile.get("family") or "other") for profile in selected.values()}),
            "technologies": sorted(selected),
            "generators": [
                {"domain": generator.domain, "class": type(generator).__name__}
                for generator in self.generators
            ],
            "support_model": {
                "universal": "all registered and custom technologies use the neutral event trace",
                "native": "native formats are provided by optional technology-specific writers",
            },
        }
