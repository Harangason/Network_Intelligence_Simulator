"""Common class model for industry-specific technology generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


def legacy_profiles(technology_ids: Iterable[str]) -> dict[str, TechnologyProfile]:
    """Project historical export presets from their single technology owners.

    These retain the original export API and are not confirmed project settings.
    Actual validation/capacity continues to use the communication registry.
    """
    import json
    from pathlib import Path
    from importlib import import_module
    technologies = import_module("backend.nis.communication.technologies")
    root = Path(technologies.__file__).parent
    result = {}
    for key in technology_ids:
        data = json.loads((root / key / "legacy_export_preset.json").read_text(encoding="utf-8"))["profile"]
        data["native_formats"] = tuple(data["native_formats"])
        result[key] = TechnologyProfile(**data)
    return result


@dataclass(frozen=True)
class TechnologyProfile:
    """Serializable description of one bus or network technology."""

    family: str
    medium: str
    topology: str
    access: str
    addressing: str
    default_bitrate: int | None = None
    max_payload_bytes: int | None = None
    native_formats: tuple[str, ...] = field(default_factory=tuple)
    kind: str = "bus"
    timing_model: str | None = None
    error_model: str = "technology_specific"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["timing_model"] = self.timing_model or self.access
        result["native_formats"] = list(self.native_formats)
        return result


class BaseTechnologyGenerator(ABC):
    """Base class implemented by every industry technology catalog."""

    domain: str = "generic"

    @abstractmethod
    def generate(self) -> dict[str, TechnologyProfile]:
        """Return the technology profiles owned by this domain."""

    def profile(
        self,
        family: str,
        medium: str,
        topology: str,
        access: str,
        addressing: str,
        *,
        default_bitrate: int | None = None,
        max_payload_bytes: int | None = None,
        native_formats: Iterable[str] = (),
        kind: str = "bus",
    ) -> TechnologyProfile:
        return TechnologyProfile(
            family=family,
            medium=medium,
            topology=topology,
            access=access,
            addressing=addressing,
            default_bitrate=default_bitrate,
            max_payload_bytes=max_payload_bytes,
            native_formats=tuple(native_formats),
            kind=kind,
        )
