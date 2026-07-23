"""Technology-open CLI models and interactive dialogs for the simulator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from bus_technologies import DEFAULT_TECHNOLOGY_REGISTRY
from communication_simulator import CommunicationSimulator


InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]


DOMAIN_LABELS = {
    "automotive": "Automotive",
    "industrial_automation": "Industrial Automation",
    "embedded_systems": "Embedded Systems",
    "aerospace": "Aerospace / Defense",
    "rail": "Rail",
    "marine": "Marine",
    "building_automation": "Building Automation",
    "energy": "Energy",
    "robotics_ros": "Robotics / ROS",
    "generic_networking": "Generic Networking",
}

SUPPORTED_STANDALONE_FORMATS = {
    "universal-jsonl",
    "universal-csv",
    "jsonl",
    "blf",
    "dbc",
    "asc",
    "trc",
    "csv",
    "json",
    "log",
    "txt",
    "xml",
    "yaml",
    "yml",
    "arxml",
    "fibex",
    "pcap",
    "pcapng",
    "mdf",
    "mf4",
}


def domain_for_technology(technology_id: str) -> str:
    normalized = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(technology_id)
    for generator in DEFAULT_TECHNOLOGY_REGISTRY.generators:
        if normalized in generator.generate():
            return generator.domain
    return "generic_networking"


@dataclass(frozen=True)
class StandaloneSimulationOptions:
    """Complete parameter set for a simple multi-node technology simulation."""

    technology: str
    industry: str
    output_dir: Path
    formats: tuple[str, ...] = ("universal-jsonl", "universal-csv")
    duration_s: float = 1.0
    seed: int = 42
    node_count: int = 2
    bitrate: int | None = None
    cycle_ms: float = 100.0
    payload_bytes: int = 8
    max_events: int = 100_000
    dropout_probability: float = 0.0
    corruption_probability: float = 0.0
    network_id: str | None = None

    def to_config(self) -> dict[str, Any]:
        technology = DEFAULT_TECHNOLOGY_REGISTRY.resolve(self.technology)
        network_id = self.network_id or f"{technology['id']}_network"
        network: dict[str, Any] = {
            "id": network_id,
            "technology": technology["id"],
            "fault_model": {
                "dropout_probability": self.dropout_probability,
                "corruption_probability": self.corruption_probability,
            },
        }
        selected_bitrate = self.bitrate or technology.get("default_bitrate")
        if selected_bitrate is not None:
            network["bitrate"] = int(selected_bitrate)

        hardware: list[dict[str, Any]] = []
        interface_ids: list[str] = []
        for index in range(1, self.node_count + 1):
            node_id = f"node_{index}"
            port_id = f"{node_id}_{technology['id']}_port"
            interface_id = f"{node_id}_{technology['id']}_if"
            interface_ids.append(interface_id)
            hardware.append(
                {
                    "id": node_id,
                    "type": "controller" if index == 1 else "device",
                    "ports": [
                        {
                            "id": port_id,
                            "physical_type": technology.get("medium") or "generic",
                            "network_interfaces": [
                                {
                                    "id": interface_id,
                                    "technology": technology["id"],
                                    "network": network_id,
                                }
                            ],
                        }
                    ],
                }
            )

        communication = {
            "id": f"{technology['id']}_communication",
            "sender_interface": interface_ids[0],
            "receivers": interface_ids[1:],
            "cycle_ms": self.cycle_ms,
            "payload_bytes": self.payload_bytes,
        }
        return {
            "schema": "communication-simulator.simulation-config.v1",
            "name": f"{technology['id']}_standalone_simulation",
            "industry": self.industry,
            "output_dir": str(self.output_dir),
            "formats": list(self.formats),
            "duration_s": self.duration_s,
            "seed": self.seed,
            "max_events": self.max_events,
            "networks": [network],
            "hardware": hardware,
            "communications": [communication],
        }


class TechnologyCatalogMenu:
    """Expose the registry in domain-oriented order for interactive selection."""

    def __init__(self) -> None:
        self.domains: list[tuple[str, str, list[str]]] = []
        for generator in DEFAULT_TECHNOLOGY_REGISTRY.generators:
            technologies = list(generator.generate())
            self.domains.append(
                (
                    generator.domain,
                    DOMAIN_LABELS.get(generator.domain, generator.domain),
                    technologies,
                )
            )

    def domain(self, index: int) -> tuple[str, str, list[str]]:
        return self.domains[index]


class InteractiveStandaloneCli:
    """Prompt for all universal simulation parameters."""

    def __init__(
        self,
        input_function: InputFunction = input,
        output_function: OutputFunction = print,
    ) -> None:
        self.input = input_function
        self.output = output_function
        self.catalog = TechnologyCatalogMenu()

    def _select(self, title: str, labels: list[str], default_index: int = 0) -> int:
        self.output(title)
        for index, label in enumerate(labels, start=1):
            suffix = " (Default)" if index - 1 == default_index else ""
            self.output(f"{index}. {label}{suffix}")
        while True:
            selected = self.input(
                f"Auswahl [1-{len(labels)}, Enter = {default_index + 1}]: "
            ).strip()
            if not selected:
                return default_index
            if selected.isdigit() and 1 <= int(selected) <= len(labels):
                return int(selected) - 1
            self.output("Ungültige Auswahl.")

    def _integer(self, title: str, default: int, minimum: int, maximum: int) -> int:
        while True:
            selected = self.input(
                f"{title} [{minimum}-{maximum}, Enter = {default}]: "
            ).strip()
            if not selected:
                return default
            try:
                value = int(selected)
            except ValueError:
                value = minimum - 1
            if minimum <= value <= maximum:
                return value
            self.output(f"Bitte einen Wert zwischen {minimum} und {maximum} eingeben.")

    def _number(
        self,
        title: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        while True:
            selected = self.input(
                f"{title} [{minimum:g}-{maximum:g}, Enter = {default:g}]: "
            ).strip()
            if not selected:
                return default
            try:
                value = float(selected.replace(",", "."))
            except ValueError:
                value = minimum - 1.0
            if minimum <= value <= maximum:
                return value
            self.output(f"Bitte einen Wert zwischen {minimum:g} und {maximum:g} eingeben.")

    def collect(self) -> StandaloneSimulationOptions:
        domain_index = self._select(
            "Branche / Technologiebereich:",
            [label for _, label, _ in self.catalog.domains],
            default_index=0,
        )
        domain, domain_label, technologies = self.catalog.domain(domain_index)
        technology_index = self._select(
            f"Technologie in {domain_label}:",
            technologies,
            default_index=0,
        )
        technology_id = technologies[technology_index]
        profile = DEFAULT_TECHNOLOGY_REGISTRY.resolve(technology_id)
        self.output(
            "Profil: "
            f"Typ={profile.get('kind')}, Medium={profile.get('medium')}, "
            f"Topologie={profile.get('topology')}, Zugriff={profile.get('access')}, "
            f"Adressierung={profile.get('addressing')}"
        )
        self.output(
            "Ausgabe: universeller JSONL/CSV-Trace"
            + (
                f"; native Adapter={','.join(profile.get('native_formats') or [])}"
                if profile.get("native_formats")
                else "; keine nativen Adapter"
            )
        )
        default_bitrate = int(profile.get("default_bitrate") or 1_000_000)
        bitrate = self._integer(
            "Bitrate in bit/s",
            default_bitrate,
            1,
            100_000_000_000,
        )
        node_count = self._integer("Anzahl Hardware-Knoten", 2, 2, 100)
        duration_s = self._number("Simulationsdauer in Sekunden", 1.0, 0.001, 86_400.0)
        cycle_ms = self._number("Kommunikationszyklus in Millisekunden", 100.0, 0.001, 3_600_000.0)
        payload_limit = int(profile.get("max_payload_bytes") or 65_535)
        payload_default = min(8, payload_limit)
        payload_bytes = self._integer(
            "Payload-Größe in Byte",
            payload_default,
            0,
            payload_limit,
        )
        seed = self._integer("Zufalls-Seed", 42, 0, 2_147_483_647)
        max_events = self._integer("Maximale Anzahl Trace-Events", 100_000, 1, 10_000_000)
        dropout = self._number("Dropout-Wahrscheinlichkeit", 0.0, 0.0, 1.0)
        corruption = self._number("Korruptionswahrscheinlichkeit", 0.0, 0.0, 1.0)
        while True:
            formats_raw = self.input(
                "Ausgabeformate [Enter = universal-jsonl,universal-csv]: "
            ).strip()
            formats = tuple(
                token.lower()
                for token in re.split(r"[\s,;]+", formats_raw)
                if token
            ) or ("universal-jsonl", "universal-csv")
            unknown_formats = sorted(set(formats) - SUPPORTED_STANDALONE_FORMATS)
            if not unknown_formats:
                break
            self.output(f"Unbekannte Ausgabeformate: {', '.join(unknown_formats)}")
        output_raw = self.input(
            f"Ausgabeordner [Enter = interactive_{technology_id}]: "
        ).strip()
        output_dir = Path(output_raw or f"interactive_{technology_id}")
        return StandaloneSimulationOptions(
            technology=technology_id,
            industry=domain,
            output_dir=output_dir,
            formats=formats,
            duration_s=duration_s,
            seed=seed,
            node_count=node_count,
            bitrate=bitrate,
            cycle_ms=cycle_ms,
            payload_bytes=payload_bytes,
            max_events=max_events,
            dropout_probability=dropout,
            corruption_probability=corruption,
        )


class StandaloneCliRunner:
    """Execute and report a universal simulation."""

    def __init__(self, simulator: CommunicationSimulator | None = None) -> None:
        self.simulator = simulator or CommunicationSimulator()

    def run(
        self,
        options: StandaloneSimulationOptions,
        *,
        validate_only: bool = False,
    ) -> dict[str, Any]:
        return self.simulator.run(options.to_config(), validate_only=validate_only)

    @staticmethod
    def print_result(result: dict[str, Any], output_function: OutputFunction = print) -> None:
        output_function(f"Status: {result['status']}")
        output_function(f"Ausgabe: {result['output_dir']}")
        output_function(f"Trace-Events: {result['trace']['events']}")
        output_function(f"Artefakte: {len(result['artifacts'])}")
        for artifact in result["artifacts"]:
            output_function(f"- {artifact}")
        for warning in result.get("warnings") or []:
            output_function(f"Warnung: {warning}")


def parse_format_tokens(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        raw = value
    else:
        raw = re.split(r"[\s,;]+", str(value or ""))
    return tuple(str(item).strip().lower() for item in raw if str(item).strip())


def options_from_namespace(args: Any) -> StandaloneSimulationOptions:
    technology = DEFAULT_TECHNOLOGY_REGISTRY.resolve(args.technology)
    formats = parse_format_tokens(args.formats)
    if not formats or formats == ("blf", "dbc"):
        formats = ("universal-jsonl", "universal-csv")
    unknown_formats = sorted(set(formats) - SUPPORTED_STANDALONE_FORMATS)
    if unknown_formats:
        raise ValueError(f"Unbekannte Ausgabeformate: {', '.join(unknown_formats)}")
    payload_limit = int(technology.get("max_payload_bytes") or 65_535)
    payload = int(args.payload_bytes if args.payload_bytes is not None else min(8, payload_limit))
    if payload < 0 or payload > payload_limit:
        raise ValueError(
            f"--payload-bytes muss für {technology['id']} zwischen 0 und {payload_limit} liegen"
        )
    bitrate = args.bitrate
    if bitrate is None:
        bitrate = technology.get("default_bitrate")
    return StandaloneSimulationOptions(
        technology=technology["id"],
        industry=str(args.industry or domain_for_technology(technology["id"])),
        output_dir=Path(args.out_dir or f"standalone_{technology['id']}"),
        formats=formats,
        duration_s=float(args.duration),
        seed=int(args.seed),
        node_count=int(args.nodes),
        bitrate=int(bitrate) if bitrate is not None else None,
        cycle_ms=float(args.cycle_ms),
        payload_bytes=payload,
        max_events=int(args.max_events or args.messages or 100_000),
        dropout_probability=float(args.dropout_probability),
        corruption_probability=float(args.corruption_probability),
        network_id=args.network_id,
    )
