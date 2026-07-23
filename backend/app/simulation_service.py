"""Adapter between HTTP payloads and the existing simulator API."""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

from .config import SIMULATOR_ROOT


if str(SIMULATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIMULATOR_ROOT))

from bus_technologies import DEFAULT_TECHNOLOGY_REGISTRY  # noqa: E402
from communication_simulator import CommunicationSimulator  # noqa: E402
from standalone_cli import (  # noqa: E402
    DOMAIN_LABELS,
    SUPPORTED_STANDALONE_FORMATS,
    StandaloneSimulationOptions,
    domain_for_technology,
)


class SimulationService:
    def __init__(self) -> None:
        self.simulator = CommunicationSimulator()

    def catalog(self) -> dict[str, Any]:
        domains: list[dict[str, Any]] = []
        for generator in DEFAULT_TECHNOLOGY_REGISTRY.generators:
            technologies = []
            for technology_id, profile in generator.generate().items():
                technologies.append({"id": technology_id, **profile.to_dict()})
            domains.append(
                {
                    "id": generator.domain,
                    "label": DOMAIN_LABELS.get(generator.domain, generator.domain),
                    "technologies": technologies,
                }
            )
        return {
            "technology_count": sum(len(item["technologies"]) for item in domains),
            "domains": domains,
            "formats": sorted(SUPPORTED_STANDALONE_FORMATS),
        }

    def prepare_config(self, payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("Die Simulationsanfrage muss ein JSON-Objekt sein.")
        if isinstance(payload.get("config"), dict):
            config = copy.deepcopy(payload["config"])
            config["output_dir"] = str(output_dir)
            return config

        technology_id = str(payload.get("technology") or "can_fd")
        technology = DEFAULT_TECHNOLOGY_REGISTRY.resolve(technology_id)
        if technology.get("requires_profile"):
            raise ValueError(f"Unbekannte Technologie: {technology_id}")

        formats_value = payload.get("formats") or ["universal-jsonl", "universal-csv"]
        if isinstance(formats_value, str):
            formats = tuple(
                token for token in re.split(r"[\s,;]+", formats_value.lower()) if token
            )
        else:
            formats = tuple(str(item).strip().lower() for item in formats_value if str(item).strip())
        unknown_formats = sorted(set(formats) - SUPPORTED_STANDALONE_FORMATS)
        if unknown_formats:
            raise ValueError(f"Unbekannte Ausgabeformate: {', '.join(unknown_formats)}")

        options = StandaloneSimulationOptions(
            technology=technology["id"],
            industry=str(payload.get("industry") or domain_for_technology(technology["id"])),
            output_dir=output_dir,
            formats=formats,
            duration_s=float(payload.get("duration_s", 1.0)),
            seed=int(payload.get("seed", 42)),
            node_count=int(payload.get("node_count", 2)),
            bitrate=int(payload["bitrate"]) if payload.get("bitrate") not in {None, ""} else None,
            cycle_ms=float(payload.get("cycle_ms", 100.0)),
            payload_bytes=int(payload.get("payload_bytes", min(8, int(technology.get("max_payload_bytes") or 8)))),
            max_events=int(payload.get("max_events", 100_000)),
            dropout_probability=float(payload.get("dropout_probability", 0.0)),
            corruption_probability=float(payload.get("corruption_probability", 0.0)),
            network_id=str(payload["network_id"]) if payload.get("network_id") else None,
        )
        self._validate_options(options, technology)
        return options.to_config()

    @staticmethod
    def _validate_options(
        options: StandaloneSimulationOptions,
        technology: dict[str, Any],
    ) -> None:
        if not 2 <= options.node_count <= 100:
            raise ValueError("node_count muss zwischen 2 und 100 liegen.")
        if options.duration_s <= 0 or options.cycle_ms <= 0:
            raise ValueError("Dauer und Zyklus müssen größer als 0 sein.")
        if not 1 <= options.max_events <= 10_000_000:
            raise ValueError("max_events muss zwischen 1 und 10.000.000 liegen.")
        if options.bitrate is not None and options.bitrate < 1:
            raise ValueError("Die Bitrate muss mindestens 1 bit/s betragen.")
        payload_limit = int(technology.get("max_payload_bytes") or 65_535)
        if not 0 <= options.payload_bytes <= payload_limit:
            raise ValueError(f"payload_bytes muss zwischen 0 und {payload_limit} liegen.")
        for label, value in (
            ("dropout_probability", options.dropout_probability),
            ("corruption_probability", options.corruption_probability),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{label} muss zwischen 0 und 1 liegen.")

    def run(
        self,
        payload: dict[str, Any],
        output_dir: Path,
        *,
        validate_only: bool = False,
    ) -> dict[str, Any]:
        config = self.prepare_config(payload, output_dir)
        return self.simulator.run(config, validate_only=validate_only)
