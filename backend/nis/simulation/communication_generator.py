#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Realistisches Communication Trace Tool

Erzeugt:
- CAN/CAN-FD/CAN-XL BLF Trace mit realen Sender-/Empfänger-Dialogen
- Ethernet PCAP/PCAPNG mit SOME/IP-ähnlicher Kommunikation
- zyklische Datenbotschaften plus passende Empfangsantworten
- je 25 Signalen logisch pro Botschaft
- Classic CAN, CAN-FD, CAN-XL-Profil und Ethernet-Unterstützung
- DBC-Datei passend zum Trace
- Rolling/Alive Counter
- CRC-8 über Nutzdaten mit Prüfung im Empfänger
- ACK/NACK Response, z.B. LIDAR_FRONT sendet Daten und ADAS_DOMAIN antwortet
- Gateway-Weiterleitung auf zweiten Kanal
- Fehler-/Störszenarien: Dropouts, Jitter, Timeout-Lücken, Bus-Off-Pause,
  DLC-Fehler, Counter-Fehler, CRC-Fehler, Timing-Violations
- Restbussimulation aus einer neutralen Standalone-JSON-Konfiguration

Installation:
    py -m pip install python-can

Beispiel:
    py generate_realistic_communication_tool.py --list-technologies
    py generate_realistic_communication_tool.py --technology arinc429 --duration 5 --nodes 3
    py generate_realistic_communication_tool.py --technology modbus_tcp --cycle-ms 20 --payload-bytes 64
    py generate_realistic_communication_tool.py --duration 60 --out realistic_can_trace.blf
    py generate_realistic_communication_tool.py --formats all --out-dir generated_trace_package
    py generate_realistic_communication_tool.py --simulation-mode restbus --formats blf,dbc,json --out-dir generated_restbus
    py generate_realistic_communication_tool.py --write-config-template simulation_config.json
    py generate_realistic_communication_tool.py --config simulation_config.json

Hinweis:
- BLF ist ein Vector-nahes Binärformat. python-can kann BLF schreiben/lesen.
- DBC enthält bei Classic CAN nur die ersten Signale, die in 8 Byte passen.
  Für 25 Signale pro Botschaft nutzt dieser Generator CAN-FD als realistischere Option.
"""

from __future__ import annotations

# Direct file entrypoints resolve the installed/source package independently of cwd.
import sys as _cli_sys
from pathlib import Path as _CliPath
_cli_backend = next(p for p in _CliPath(__file__).resolve().parents if p.name == "backend")
_cli_sys.path.insert(0, str(_cli_backend.parent))

import argparse
import csv
import json
import math
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from backend.nis.communication.services.export_options import example_bitrate_choices
from backend.nis.communication.technologies.can.formats.native_example import DEFAULT_ROUTING_ROWS
from backend.nis.communication.technologies.can.formats.trace_model import ROUTE_INFO_START_BYTE, ROUTE_INFO_LENGTH

from backend.nis.simulation.bus_technologies import DEFAULT_TECHNOLOGY_REGISTRY
from backend.nis.simulation.filter_system import create_filter_bank
from backend.nis.simulation.filter_system import profile_from_request
from backend.nis.simulation.filter_system import summarize_filter_banks
from backend.nis.simulation.hardware_profile import hardware_profile_summary
from backend.nis.simulation.hardware_profile import normalize_hardware_config
from backend.nis.simulation.hardware_profile import validate_hardware_profile
from backend.nis.simulation.signal_suggestions import suggest_signal_gaps
from backend.nis.interfaces.cli.standalone import InteractiveStandaloneCli
from backend.nis.interfaces.cli.standalone import StandaloneCliRunner
from backend.nis.interfaces.cli.standalone import options_from_namespace
from backend.nis.traces.trace_realism import contains_external_signal_records
from backend.nis.traces.trace_realism import external_signal_records
from backend.nis.traces.trace_realism import physical_raw_value
from backend.nis.traces.trace_realism import signal_specs_for_message
from backend.nis.traces.trace_realism import trace_quality_summary

from backend.nis.infrastructure.paths import DATA_ROOT, TRACE_ROOT, EXPORT_ROOT
LIB_ROOT = DATA_ROOT / "library"



class ProgressBar:
    def __init__(self, enabled: bool = True, width: int = 32) -> None:
        self.enabled = enabled
        self.width = width
        self.last_len = 0

    def update(self, percent: int, message: str) -> None:
        if not self.enabled:
            return
        percent = max(0, min(100, int(percent)))
        filled = round(self.width * percent / 100)
        bar = "#" * filled + "-" * (self.width - filled)
        text = f"\r[{bar}] {message} {percent}%"
        padding = " " * max(0, self.last_len - len(text))
        print(text + padding, end="", flush=True)
        self.last_len = len(text)
        if percent >= 100:
            print()
            self.last_len = 0

    def line(self) -> None:
        if self.enabled and self.last_len:
            print()
            self.last_len = 0


# -----------------------------
# Datenmodell
# -----------------------------

from backend.nis.communication.technologies.can.formats.native_example import SignalDef, MessageDef, add_data_signals, add_response_signals, build_messages, encode_message_payload, encode_response_payload, iter_scheduled_events, generate_blf, write_dbc, validate_blf, CanMessage, BLFReader, BLFWriter
from backend.nis.communication.technologies.can.encoding import crc8_autosar, get_unsigned_le, verify_payload_crc, set_unsigned_le_strict as set_unsigned_le






from backend.nis.communication.technologies.can.formats.restbus_example import (RestbusParticipant, build_restbus_routing_rows, clamp_channel, default_restbus_participants, normalize_restbus_participant, normalize_service_names, participant_service_pairs, restbus_interface_summary, restbus_participants_from_request, route_cycle_ms, DEFAULT_RESTBUS_PARTICIPANTS, ROLE_CYCLE_FALLBACK_MS)

COMMON_NOMINAL_BITRATES = example_bitrate_choices('can')
CAN_FD_DATA_BITRATES = example_bitrate_choices('can_fd')
CAN_XL_DATA_BITRATES = example_bitrate_choices('can_xl')
ETHERNET_BITRATES = example_bitrate_choices('ethernet')





# -----------------------------
# CRC / Packing
# -----------------------------









def route_label(sender: str, receiver: str) -> str:
    return f"{sender} -> {receiver}"


def triangle_wave(t_s: float, period_s: float, minimum: int, maximum: int) -> int:
    if period_s <= 0:
        return minimum
    phase = (t_s % period_s) / period_s
    if phase < 0.5:
        y = phase * 2.0
    else:
        y = (1.0 - phase) * 2.0
    return int(minimum + y * (maximum - minimum))


def safe_identifier(value: str, fallback: str = "NODE") -> str:
    cleaned = re.sub(r"\W+", "_", str(value).strip()).strip("_").upper()
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"{fallback}_{cleaned}"
    return cleaned


def parse_optional_int(value: object, default: int | None = None) -> int | None:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return int(text, 0)




from backend.nis.communication.technologies.can.formats.routing import normalized_routing_row, load_routing_table, write_routing_template















def load_simulation_config(path: Path) -> Dict[str, Any]:
    path = resolve_library_request_path(path)
    request = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(request, dict):
        raise ValueError(f"Simulation configuration must be a JSON object: {path}")
    return request


def resolve_library_request_path(path: Path) -> Path:
    path = Path(path)
    if path.exists():
        return path
    if path.is_absolute() or path.parent != Path("."):
        return path
    library_root = LIB_ROOT
    if not library_root.exists():
        return path
    matches = [
        item
        for item in library_root.rglob(path.name)
        if item.is_file() and item.name == path.name
    ]
    if len(matches) == 1:
        return matches[0]
    return path


def write_simulation_config_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = {
        "schema": "communication-simulator.simulation-config.v1",
        "simulation_mode": "restbus",
        "output_dir": "generated_restbus_simulation",
        "formats": "blf,dbc,json,csv",
        "duration_s": 10.0,
        "bus_type": "fd",
        "channels": 4,
        "messages": None,
        "nominal_bitrate": 500000,
        "data_bitrate": 2000000,
        "seed": 42,
        "participants": DEFAULT_RESTBUS_PARTICIPANTS,
    }
    path.write_text(json.dumps(request, indent=2), encoding="utf-8")










def apply_simulation_config_to_args(args: argparse.Namespace, request: Dict[str, Any]) -> None:
    mapping = {
        "output_dir": "out_dir",
        "out_dir": "out_dir",
        "formats": "formats",
        "duration_s": "duration",
        "duration": "duration",
        "messages": "messages",
        "seed": "seed",
        "channels": "channels",
        "bus_type": "bus",
        "bus": "bus",
        "nominal_bitrate": "nominal_bitrate",
        "fd_bitrate": "fd_bitrate",
        "data_bitrate": "fd_bitrate",
        "xl_data_bitrate": "xl_data_bitrate",
        "eth_bitrate": "eth_bitrate",
        "eth_bitrates": "eth_bitrates",
        "eth_messages": "eth_messages",
        "simulation_mode": "simulation_mode",
        "interface_out": "interface_out",
    }
    for source, target in mapping.items():
        if source in request and request[source] is not None:
            setattr(args, target, request[source])
    if isinstance(request.get("scenario"), dict):
        args.scenario = request["scenario"]
    args.filter_system = profile_from_request(request)
    args.hardware = normalize_hardware_config(request)
    args.hardware_summary = hardware_profile_summary(args.hardware)
    args.hardware_validation = validate_hardware_profile(args.hardware)
    for attr in ["messages", "seed", "channels", "nominal_bitrate", "fd_bitrate", "xl_data_bitrate", "eth_bitrate", "eth_messages"]:
        value = getattr(args, attr, None)
        if value is not None:
            setattr(args, attr, int(value))
    if getattr(args, "duration", None) is not None:
        args.duration = float(args.duration)
    if getattr(args, "interface_out", None) is not None and not isinstance(args.interface_out, Path):
        args.interface_out = Path(str(args.interface_out))


def write_simulation_interface(
    path: Path,
    *,
    simulation_mode: str,
    written: List[Path],
    warnings: List[str],
    duration_s: float,
    bus_type: str,
    channel_count: int,
    nominal_bitrate: int,
    data_bitrate: int | None,
    routing_rows: List[Dict[str, object]] | None,
    restbus_summary: Dict[str, object] | None,
    filter_summary: Dict[str, object] | None = None,
    signal_suggestions: Dict[str, object] | None = None,
    hardware_summary: Dict[str, object] | None = None,
    hardware_validation: Dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "communication-simulator.native-result.v1",
        "simulation_mode": simulation_mode,
        "created_utc": format_utc_timestamp(datetime.now(timezone.utc).timestamp()),
        "duration_s": duration_s,
        "bus_type": bus_type,
        "channels": channel_count,
        "nominal_bitrate": nominal_bitrate,
        "data_bitrate": data_bitrate,
        "artifacts": [str(item) for item in written],
        "warnings": warnings,
        "routing_rows": routing_rows,
        "restbus": restbus_summary,
        "filter_system": filter_summary or {"enabled": False},
        "trace_quality": trace_quality_summary(),
        "signal_suggestions": signal_suggestions or suggest_signal_gaps(routing_rows, bus_type),
        "hardware_profile": hardware_summary or {"enabled": False},
        "hardware_validation": hardware_validation or {
            "valid": True,
            "mode": "non_invasive_validation",
            "findings": [],
        },
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def run_simulation(request: Dict[str, Any]) -> Dict[str, Any]:
    """Run the native CAN/Ethernet generator from a standalone configuration."""
    args = argparse.Namespace(
        out="realistic_can_trace.blf",
        dbc="realistic_can_network.dbc",
        out_dir="generated_native_simulation",
        formats="blf,dbc,json,csv",
        duration=10.0,
        messages=None,
        seed=42,
        routing_table=None,
        channels=4,
        bus="fd",
        classic_can=False,
        nominal_bitrate=500_000,
        fd_bitrate=2_000_000,
        xl_data_bitrate=None,
        eth_bitrate=1_000_000_000,
        eth_bitrates=None,
        eth_messages=None,
        simulation_mode="restbus",
        interface_out=None,
        config=None,
        scenario={},
        filter_system=None,
        filter_summary=None,
        hardware=None,
        hardware_summary=None,
        hardware_validation=None,
    )
    apply_simulation_config_to_args(args, request)

    bus_type = "classic" if args.classic_can else args.bus
    if bus_type == "classic":
        data_bitrate = None
    elif bus_type == "fd":
        data_bitrate = args.fd_bitrate or 2_000_000
    else:
        data_bitrate = args.xl_data_bitrate or CAN_XL_DATA_BITRATES["e"]
    channel_count = max(1, min(16, int(args.channels)))

    routing_rows: List[Dict[str, object]] | None = None
    restbus_summary: Dict[str, object] | None = None
    if args.routing_table:
        routing_rows = load_routing_table(Path(args.routing_table), channel_count)
    elif args.simulation_mode == "restbus":
        participants = restbus_participants_from_request(request, channel_count)
        routing_rows = build_restbus_routing_rows(participants, channel_count, max_routes=args.messages)
        restbus_summary = restbus_interface_summary(participants, routing_rows)

    num_messages = int(args.messages) if args.messages is not None else (len(routing_rows) if routing_rows is not None else 100)
    selected_formats = parse_formats(args.formats)
    args.eth_bitrates = parse_ethernet_bitrates(args.eth_bitrates)
    written, warnings = generate_format_package(
        formats=selected_formats,
        args=args,
        bus_type=bus_type,
        nominal_bitrate=int(args.nominal_bitrate),
        data_bitrate=data_bitrate,
        channel_count=channel_count,
        routing_rows=routing_rows,
        num_messages=num_messages,
    )
    interface_path = args.interface_out or Path(args.out_dir).resolve() / "simulation_interface.json"
    write_simulation_interface(
        Path(interface_path).resolve(),
        simulation_mode=args.simulation_mode,
        written=written,
        warnings=warnings,
        duration_s=float(args.duration),
        bus_type=bus_type,
        channel_count=channel_count,
        nominal_bitrate=int(args.nominal_bitrate),
        data_bitrate=data_bitrate,
        routing_rows=routing_rows,
        restbus_summary=restbus_summary,
        filter_summary=getattr(args, "filter_summary", None),
        signal_suggestions=getattr(args, "signal_suggestions", None),
        hardware_summary=getattr(args, "hardware_summary", None),
        hardware_validation=getattr(args, "hardware_validation", None),
    )
    return json.loads(Path(interface_path).read_text(encoding="utf-8"))


# -----------------------------
# Netzwerkdefinition
# -----------------------------







# -----------------------------
# Nutzdaten erzeugen
# -----------------------------





# -----------------------------
# BLF Trace erzeugen
# -----------------------------





# -----------------------------
# DBC schreiben
# -----------------------------



# -----------------------------
# ASC optional als Debug
# -----------------------------


def format_bitrate(value: int) -> str:
    if value >= 1_000_000:
        mbps = value / 1_000_000
        return f"{mbps:g} Mbit/s"
    return f"{value // 1000:g} kbit/s"


def format_utc_timestamp(timestamp_s: float) -> str:
    return datetime.fromtimestamp(timestamp_s, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def choose_bitrate(title: str, options: Dict[str, int], default_value: int) -> int:
    numbered_options = list(options.values())
    if default_value not in numbered_options:
        raise ValueError(f"Default-Bitrate {default_value} ist keine erlaubte Option.")

    print(title)
    for index, value in enumerate(numbered_options, start=1):
        default_suffix = " (Default)" if value == default_value else ""
        print(f"{index}. {format_bitrate(value)}{default_suffix}")

    allowed = "/".join(str(index) for index in range(1, len(numbered_options) + 1))
    selected = input(f"Geben Sie Ihre Auswahl ein [{allowed}], Enter = {format_bitrate(default_value)}: ").strip()
    if selected == "":
        return default_value
    while not selected.isdigit() or not 1 <= int(selected) <= len(numbered_options):
        print(f"Ungültige Eingabe. Bitte geben Sie eine Zahl von 1 bis {len(numbered_options)} ein oder drücken Sie Enter.")
        selected = input(f"Geben Sie Ihre Auswahl ein [{allowed}], Enter = {format_bitrate(default_value)}: ").strip()
        if selected == "":
            return default_value
    return numbered_options[int(selected) - 1]


def choose_channel_count(default_value: int = 2) -> int:
    selected = input(f"Wie viele CAN-Kanäle sollen im Trace sein? [1-16, Enter = {default_value}, erzeugt CAN0 bis CAN15]: ").strip()
    if selected == "":
        return default_value
    while not selected.isdigit() or not 1 <= int(selected) <= 16:
        print("Ungültige Eingabe. Bitte geben Sie eine Zahl von 1 bis 16 ein oder drücken Sie Enter.")
        selected = input(f"Wie viele CAN-Kanäle sollen im Trace sein? [1-16, Enter = {default_value}]: ").strip()
        if selected == "":
            return default_value
    return int(selected)


def choose_positive_int(title: str, default_value: int, minimum: int = 1, maximum: int = 500) -> int:
    selected = input(f"{title} [{minimum}-{maximum}, Enter = {default_value}]: ").strip()
    if selected == "":
        return default_value
    while not selected.isdigit() or not minimum <= int(selected) <= maximum:
        print(f"Ungültige Eingabe. Bitte geben Sie eine Zahl von {minimum} bis {maximum} ein oder drücken Sie Enter.")
        selected = input(f"{title} [{minimum}-{maximum}, Enter = {default_value}]: ").strip()
        if selected == "":
            return default_value
    return int(selected)


def choose_mode(title: str, modes: Dict[str, str], default_value: str | None = None) -> str:
    if title:
        print(title)
    for key, label in modes.items():
        default_suffix = " (Default)" if key == default_value else ""
        print(f"{key}. {label}{default_suffix}")

    prompt_default = f", Enter = {default_value}" if default_value is not None else ""
    selected = input(f"Geben Sie Ihre Auswahl ein [{'/'.join(modes)}{prompt_default}]: ").strip()
    if selected == "" and default_value is not None:
        return default_value
    while selected not in modes:
        print(f"Ungültige Eingabe. Bitte geben Sie {', '.join(modes)} ein.")
        selected = input(f"Geben Sie Ihre Auswahl ein [{'/'.join(modes)}{prompt_default}]: ").strip()
        if selected == "" and default_value is not None:
            return default_value
    return selected


def choose_multi_mode(title: str, modes: Dict[str, str], default_values: List[str]) -> List[str]:
    if title:
        print(title)
    for key, label in modes.items():
        default_suffix = " (Default)" if key in default_values else ""
        print(f"{key}. {label}{default_suffix}")

    allowed = "/".join(modes)
    default_text = ",".join(default_values)
    prompt = f"Geben Sie eine oder mehrere Auswahlen ein [{allowed}], z.B. 1,2, Enter = {default_text}: "
    selected = input(prompt).strip()
    if selected == "":
        return default_values

    while True:
        if selected.lower() in {"all", "alle", "a"}:
            return list(modes)
        parts = [part for part in re.split(r"[\s,;/]+", selected) if part]
        if parts and all(part in modes for part in parts):
            result: List[str] = []
            for part in parts:
                if part not in result:
                    result.append(part)
            return result
        print(f"Ungültige Eingabe. Bitte geben Sie eine oder mehrere Zahlen aus {', '.join(modes)} ein.")
        selected = input(prompt).strip()
        if selected == "":
            return default_values


def choose_can_profile(title: str, default_value: str = "fd") -> Tuple[str, int, int | None]:
    mode_choice = choose_mode(
        title,
        {
            "1": "Classic CAN",
            "2": "CAN-FD",
            "3": "CAN-XL Profil (BLF wird CAN-FD-kompatibel gespeichert)",
        },
        default_value={"classic": "1", "fd": "2", "xl": "3"}[default_value],
    )
    bus_type = {"1": "classic", "2": "fd", "3": "xl"}[mode_choice]
    nominal_bitrate = choose_bitrate("Nominale/arbitration Datenrate:", COMMON_NOMINAL_BITRATES, 500_000)
    data_bitrate: int | None = None
    if bus_type == "fd":
        data_bitrate = choose_bitrate("CAN-FD Datenphase:", CAN_FD_DATA_BITRATES, 2_000_000)
    elif bus_type == "xl":
        data_bitrate = choose_bitrate("CAN-XL Datenphase:", CAN_XL_DATA_BITRATES, 10_000_000)
    return bus_type, nominal_bitrate, data_bitrate


def choose_ethernet_formats() -> List[str]:
    selected = choose_multi_mode(
        "Ethernet-Ausgabearten:",
        {
            "1": "PCAP",
            "2": "PCAPNG",
        },
        default_values=["1", "2"],
    )
    return [{"1": "pcap", "2": "pcapng"}[item] for item in selected]


def choose_ethernet_bitrates() -> List[int]:
    bitrates = list(ETHERNET_BITRATES.values())
    modes = {str(index): format_bitrate(value) for index, value in enumerate(bitrates, start=1)}
    selected = choose_multi_mode("Ethernet-Geschwindigkeiten:", modes, default_values=["3"])
    return [bitrates[int(item) - 1] for item in selected]


def choice() -> Dict[str, object]:
    print("Wählen Sie den Modus:")
    mode_choice = choose_mode(
        "",
        {
            "1": "Realistischer CAN Trace (Classic CAN)",
            "2": "Realistischer CAN-FD Trace",
            "3": "Logisches CAN-XL Profil",
            "4": "Ethernet Trace (PCAP/PCAPNG)",
            "5": "Mixed Trace (CAN + Ethernet)",
        },
        default_value="2",
    )

    nominal_bitrate = 500_000
    data_bitrate: int | None = None
    channel_count = 0
    bus_type = "fd"
    formats = "blf,dbc"
    out_dir: str | None = None
    eth_bitrates: List[int] = []
    eth_messages: int | None = None

    if mode_choice in {"1", "2", "3"}:
        bus_type = {"1": "classic", "2": "fd", "3": "xl"}[mode_choice]
        nominal_bitrate = choose_bitrate("Nominale/arbitration Datenrate:", COMMON_NOMINAL_BITRATES, 500_000)
        if bus_type == "fd":
            data_bitrate = choose_bitrate("CAN-FD Datenphase:", CAN_FD_DATA_BITRATES, 2_000_000)
        elif bus_type == "xl":
            data_bitrate = choose_bitrate("CAN-XL Datenphase:", CAN_XL_DATA_BITRATES, 10_000_000)
        channel_count = choose_channel_count(default_value=2)
    elif mode_choice == "4":
        formats = ",".join(choose_ethernet_formats())
        out_dir = "generated_ethernet_trace"
    else:
        bus_type, nominal_bitrate, data_bitrate = choose_can_profile("CAN-Anteil im Mixed-Modus:", default_value="fd")
        channel_count = choose_channel_count(default_value=2)
        formats = ",".join(["can-all", *choose_ethernet_formats()])
        out_dir = "generated_mixed_trace"
        print("Mixed-Modus: erzeugt CAN-Dateien, Ethernet-Dateien und eine gemeinsame mixed_trace.json.")

    if mode_choice in {"4", "5"}:
        eth_bitrates = choose_ethernet_bitrates()
        eth_messages = choose_positive_int("Wie viele Ethernet-Kommunikationsströme sollen erzeugt werden?", default_value=4)

    return {
        "mode_choice": mode_choice,
        "bus_type": bus_type,
        "nominal_bitrate": nominal_bitrate,
        "data_bitrate": data_bitrate,
        "channel_count": channel_count,
        "eth_bitrate": eth_bitrates[0] if eth_bitrates else None,
        "eth_bitrates": eth_bitrates,
        "eth_messages": eth_messages,
        "formats": formats,
        "out_dir": out_dir,
    }


FORMAT_GROUPS = {
    "can-all": {"blf", "dbc", "asc", "trc", "csv", "json", "log", "txt", "xml", "yaml", "yml", "arxml", "fibex"},
    "eth-all": {"pcap", "pcapng"},
    "optional-all": {"mdf", "mf4"},
}
FORMAT_GROUPS["all"] = FORMAT_GROUPS["can-all"] | FORMAT_GROUPS["eth-all"]
SUPPORTED_FORMATS = FORMAT_GROUPS["all"] | FORMAT_GROUPS["optional-all"]
DATABASE_FORMATS = {"dbc", "arxml", "fibex"}


def parse_formats(value: str) -> List[str]:
    requested = [part.strip().lower() for part in value.split(",") if part.strip()]
    formats: List[str] = []
    for item in requested:
        expanded = FORMAT_GROUPS.get(item, {item})
        for fmt in sorted(expanded):
            if fmt not in SUPPORTED_FORMATS:
                allowed = ", ".join(sorted(SUPPORTED_FORMATS | set(FORMAT_GROUPS)))
                raise ValueError(f"Unbekanntes Format '{item}'. Erlaubt: {allowed}")
            if fmt not in formats:
                formats.append(fmt)
    return formats


def add_format_generators_to_path() -> None:
    """Retained API; canonical format modules need no sys.path modification."""
    pass


def package_output_path(out_dir: Path, fmt: str) -> Path:
    names = {
        "blf": "trace.blf",
        "dbc": "network.dbc",
        "asc": "trace.asc",
        "trc": "trace.trc",
        "csv": "trace.csv",
        "json": "trace.json",
        "log": "trace.log",
        "txt": "trace.txt",
        "xml": "trace.xml",
        "yaml": "trace.yaml",
        "yml": "trace.yml",
        "arxml": "system.arxml",
        "fibex": "system.fibex.xml",
        "pcap": "someip.pcap",
        "pcapng": "someip.pcapng",
        "mdf": "summary.mdf",
        "mf4": "summary.mf4",
    }
    subdir = "datenbasen" if fmt in DATABASE_FORMATS else "traces"
    path = out_dir / subdir / names[fmt]
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def bitrate_filename_slug(value: int) -> str:
    if value >= 1_000_000:
        return f"{value // 1_000_000}mbit"
    return f"{value // 1000}kbit"


def ethernet_output_path(out_dir: Path, fmt: str, bitrate: int, include_bitrate: bool) -> Path:
    if not include_bitrate:
        return package_output_path(out_dir, fmt)
    stem = "someip"
    path = out_dir / "traces" / f"{stem}_{bitrate_filename_slug(bitrate)}.{fmt}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def parse_ethernet_bitrates(value: object) -> List[int]:
    if value is None:
        return []
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
    else:
        parts = [part.strip() for part in str(value).split(",") if part.strip()]
    bitrates: List[int] = []
    allowed = set(ETHERNET_BITRATES.values())
    for part in parts:
        bitrate = int(part, 0)
        if bitrate not in allowed:
            allowed_text = ", ".join(str(item) for item in sorted(allowed))
            raise ValueError(f"Unbekannte Ethernet-Geschwindigkeit '{part}'. Erlaubt: {allowed_text}")
        if bitrate not in bitrates:
            bitrates.append(bitrate)
    return bitrates


def write_manifest(path: Path, metadata: Dict[str, object]) -> None:
    path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")


def archive_trace_package_to_library(out_dir: Path, package_type: str) -> Path | None:
    """Return the generated package path without creating runtime copies."""
    source = Path(out_dir).resolve()
    if not source.exists() or not source.is_dir():
        return None
    return source


def archive_generated_files_to_library(paths: Iterable[Path], category: str) -> Path | None:
    """Runtime artifacts are never copied into the source/profile library."""
    return None


def package_type_from_formats(formats: List[str]) -> str:
    has_can_output = any(fmt in FORMAT_GROUPS["can-all"] or fmt in FORMAT_GROUPS["optional-all"] for fmt in formats)
    has_eth_output = any(fmt in FORMAT_GROUPS["eth-all"] for fmt in formats)
    return "mixed" if has_can_output and has_eth_output else "ethernet" if has_eth_output else "can"


def route_generated_out_dir_to_library(args: argparse.Namespace, formats: List[str]) -> None:
    out_dir_value = args.out_dir or str(EXPORT_ROOT / "generated_trace_package")
    if not args.out_dir:
        args.out_dir = out_dir_value
    out_dir = Path(str(out_dir_value))
    if out_dir.is_absolute():
        return
    try:
        out_dir.relative_to(TRACE_ROOT)
        return
    except ValueError:
        pass
    if not out_dir.name.startswith("generated_"):
        return
    args.out_dir = str(TRACE_ROOT / out_dir.name)


def write_mixed_trace(
    path: Path,
    can_frames: List[object],
    eth_frames: List[object],
    metadata: Dict[str, object],
    trace_start_utc: float,
) -> None:
    entries: List[Dict[str, object]] = []
    for frame in can_frames:
        entries.append(
            {
                "timestamp": frame.timestamp,
                "timestamp_utc": format_utc_timestamp(frame.timestamp),
                "trace_time_s": frame.timestamp - trace_start_utc,
                "rel_time": frame.rel_time,
                "protocol": "CAN",
                "channel": f"CAN{frame.channel}",
                "id": f"0x{frame.arbitration_id:X}",
                "name": frame.name,
                "sender": frame.sender,
                "receiver": frame.receiver,
                "direction": frame.direction,
                "bus_type": frame.bus_type,
                "dlc": frame.dlc,
                "payload_hex": frame.data.hex(" ").upper(),
                "message_kind": frame.message_kind,
            }
        )
    for frame in eth_frames:
        entries.append(
            {
                "timestamp": frame.timestamp,
                "timestamp_utc": format_utc_timestamp(frame.timestamp),
                "trace_time_s": frame.timestamp - trace_start_utc,
                "rel_time": frame.rel_time,
                "protocol": "ETH",
                "src_node": frame.src_node,
                "dst_node": frame.dst_node,
                "src_mac": frame.src_mac,
                "dst_mac": frame.dst_mac,
                "src_ip": frame.src_ip,
                "dst_ip": frame.dst_ip,
                "src_port": frame.src_port,
                "dst_port": frame.dst_port,
                "service_id": f"0x{frame.service_id:04X}",
                "method_id": f"0x{frame.method_id:04X}",
                "message_type": f"0x{frame.message_type:02X}",
                "payload_hex": frame.payload.hex(" ").upper(),
            }
        )

    entries.sort(key=lambda item: (float(item["timestamp"]), str(item["protocol"])))
    path.write_text(
        json.dumps(
            {
                "trace_type": "mixed",
                "metadata": metadata,
                "frames": entries,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def generate_format_package(
    formats: List[str],
    args: argparse.Namespace,
    bus_type: str,
    nominal_bitrate: int,
    data_bitrate: int | None,
    channel_count: int,
    routing_rows: List[Dict[str, object]] | None,
    num_messages: int,
    progress: ProgressBar | None = None,
) -> Tuple[List[Path], List[str]]:
    if progress:
        progress.update(5, "Bereite Dateipaket vor")
    add_format_generators_to_path()
    from backend.nis.communication.technologies.can.formats.can_format_writers import (
        write_arxml as suite_write_arxml,
        write_asc,
        write_csv_trace,
        write_dbc as suite_write_dbc,
        write_fibex as suite_write_fibex,
        write_json_trace,
        write_log,
        write_trc,
        write_txt,
        write_xml_trace,
        write_yaml_trace,
    )
    from backend.nis.communication.technologies.can.formats.trace_model import build_can_trace
    from backend.nis.communication.technologies.ethernet.formats.trace_model import build_ethernet_trace
    from backend.nis.communication.technologies.ethernet.formats.eth_format_writers import write_pcap, write_pcapng

    out_dir = Path(args.out_dir or EXPORT_ROOT / "generated_trace_package").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_start_utc = datetime.now(timezone.utc).timestamp()

    written: List[Path] = []
    warnings: List[str] = []
    can_formats = [fmt for fmt in formats if fmt in FORMAT_GROUPS["can-all"] or fmt in FORMAT_GROUPS["optional-all"]]
    eth_formats = [fmt for fmt in formats if fmt in FORMAT_GROUPS["eth-all"]]
    mixed_enabled = bool(can_formats and eth_formats)
    eth_bitrates = parse_ethernet_bitrates(getattr(args, "eth_bitrates", None))
    if not eth_bitrates and eth_formats:
        eth_bitrates = [int(getattr(args, "eth_bitrate", 1_000_000_000))]
    eth_message_count = int(getattr(args, "eth_messages", None) or num_messages)
    suite_messages = None
    suite_frames = None
    eth_frames = None
    scenario = getattr(args, "scenario", {}) if isinstance(getattr(args, "scenario", {}), dict) else {}
    filter_banks = []

    def new_filter_bank():
        bank = create_filter_bank(getattr(args, "filter_system", None), scenario)
        if bank is not None:
            filter_banks.append(bank)
        return bank

    root_messages: List[MessageDef] | None = None
    if "blf" in formats:
        if progress:
            progress.update(15, "Erzeuge BLF Trace")
        blf_filter_bank = new_filter_bank()
        blf_path = package_output_path(out_dir, "blf")
        root_messages = generate_blf(
            out_blf=blf_path,
            duration_s=args.duration,
            bus_type=bus_type,
            seed=args.seed,
            num_messages=num_messages,
            nominal_bitrate=nominal_bitrate,
            data_bitrate=data_bitrate,
            channel_count=channel_count,
            routing_rows=routing_rows,
            start_utc=trace_start_utc,
            filter_bank=blf_filter_bank,
        )
        written.append(blf_path)

    if "dbc" in formats:
        if progress:
            progress.update(28, "Schreibe DBC Datenbank")
        dbc_path = package_output_path(out_dir, "dbc")
        if root_messages is None:
            root_messages = build_messages(
                num_messages=num_messages,
                bus_type=bus_type,
                seed=args.seed,
                channel_count=channel_count,
                routing_rows=routing_rows,
            )
        write_dbc(dbc_path, root_messages, nominal_bitrate=nominal_bitrate, data_bitrate=data_bitrate)
        written.append(dbc_path)

    if any(fmt in formats for fmt in {"asc", "trc", "csv", "json", "log", "txt", "xml", "yaml", "yml", "arxml", "fibex"}):
        if progress:
            progress.update(42, "Erzeuge CAN Zusatzformate")
        suite_filter_bank = new_filter_bank()
        suite_messages, suite_frames = build_can_trace(
            duration=args.duration,
            messages=num_messages,
            channels=channel_count,
            bus_type=bus_type,
            seed=args.seed,
            start_utc=trace_start_utc,
            routing_rows=routing_rows,
            filter_bank=suite_filter_bank,
        )
        writer_map = {
            "asc": lambda p: write_asc(p, suite_frames, trace_start_utc=trace_start_utc),
            "trc": lambda p: write_trc(p, suite_frames, trace_start_utc=trace_start_utc),
            "csv": lambda p: write_csv_trace(p, suite_frames),
            "json": lambda p: write_json_trace(p, suite_frames),
            "log": lambda p: write_log(p, suite_frames),
            "txt": lambda p: write_txt(p, suite_frames),
            "xml": lambda p: write_xml_trace(p, suite_frames),
            "yaml": lambda p: write_yaml_trace(p, suite_frames),
            "yml": lambda p: write_yaml_trace(p, suite_frames),
            "arxml": lambda p: suite_write_arxml(p, suite_messages),
            "fibex": lambda p: suite_write_fibex(p, suite_messages),
        }
        for fmt, writer in writer_map.items():
            if fmt in formats:
                if progress:
                    progress.update(45 + min(15, len(written)), f"Schreibe {fmt.upper()}")
                path = package_output_path(out_dir, fmt)
                writer(path)
                written.append(path)

    if eth_formats:
        if progress:
            progress.update(66, "Erzeuge Ethernet Frames")
        eth_frames = build_ethernet_trace(duration=args.duration, messages=eth_message_count, seed=args.seed, start_utc=trace_start_utc)
        include_bitrate_in_name = len(eth_bitrates) > 1
        for eth_bitrate in eth_bitrates:
            if "pcap" in formats:
                if progress:
                    progress.update(72, "Schreibe PCAP")
                path = ethernet_output_path(out_dir, "pcap", eth_bitrate, include_bitrate_in_name)
                write_pcap(path, eth_frames)
                written.append(path)
            if "pcapng" in formats:
                if progress:
                    progress.update(76, "Schreibe PCAPNG")
                path = ethernet_output_path(out_dir, "pcapng", eth_bitrate, include_bitrate_in_name)
                write_pcapng(path, eth_frames)
                written.append(path)

    for fmt, version in (("mdf", "3.30"), ("mf4", "4.10")):
        if fmt not in formats:
            continue
        path = package_output_path(out_dir, fmt)
        try:
            if progress:
                progress.update(82, f"Schreibe {fmt.upper()}")
            from backend.nis.communication.technologies.can.formats.mdf_writer import write_mdf

            write_mdf(path, version, args.duration, num_messages, channel_count, bus_type, args.seed, routing_rows=routing_rows)
            written.append(path)
        except SystemExit as exc:
            warnings.append(f"{fmt.upper()} nicht erzeugt: {exc}")

    if mixed_enabled:
        if progress:
            progress.update(88, "Schreibe Mixed Trace")
        if suite_frames is None:
            suite_filter_bank = new_filter_bank()
            suite_messages, suite_frames = build_can_trace(
                duration=args.duration,
                messages=num_messages,
                channels=channel_count,
                bus_type=bus_type,
                seed=args.seed,
                start_utc=trace_start_utc,
                routing_rows=routing_rows,
                filter_bank=suite_filter_bank,
            )
        if eth_frames is None:
            eth_frames = build_ethernet_trace(duration=args.duration, messages=eth_message_count, seed=args.seed, start_utc=trace_start_utc)
        mixed_path = out_dir / "traces" / "mixed_trace.json"
        mixed_path.parent.mkdir(parents=True, exist_ok=True)
        write_mixed_trace(
            mixed_path,
            suite_frames,
            eth_frames,
            {
                "duration_s": args.duration,
                "trace_start_utc": format_utc_timestamp(trace_start_utc),
                "trace_start_unix": trace_start_utc,
                "messages": num_messages,
                "ethernet_messages": eth_message_count,
                "can_frames": len(suite_frames),
                "ethernet_frames": len(eth_frames),
                "bus_type": bus_type,
                "nominal_bitrate": nominal_bitrate,
                "data_bitrate": data_bitrate,
                "ethernet_bitrates": eth_bitrates,
            },
            trace_start_utc=trace_start_utc,
        )
        written.append(mixed_path)

    if progress:
        progress.update(94, "Schreibe Manifest")
    can_frame_count = len(suite_frames) if suite_frames is not None else None
    ethernet_frame_count = len(eth_frames) if eth_frames is not None else None
    filter_summary = summarize_filter_banks(filter_banks, getattr(args, "filter_system", None), scenario)
    args.filter_summary = filter_summary
    signal_suggestions = suggest_signal_gaps(routing_rows, bus_type)
    args.signal_suggestions = signal_suggestions
    write_manifest(
        out_dir / "generation_manifest.json",
        {
            "package_type": "mixed" if mixed_enabled else "ethernet" if eth_formats else "can",
            "folders": {
                "traces": "traces",
                "databases": "datenbasen",
            },
            "formats": formats,
            "written": [str(path) for path in written],
            "warnings": warnings,
            "duration_s": args.duration,
            "trace_start_utc": format_utc_timestamp(trace_start_utc),
            "trace_start_unix": trace_start_utc,
            "messages": num_messages,
            "ethernet_messages": eth_message_count if eth_formats else None,
            "can_frames": can_frame_count,
            "ethernet_frames": ethernet_frame_count,
            "can_enabled": bool(can_formats),
            "ethernet_enabled": bool(eth_formats),
            "mixed_enabled": mixed_enabled,
            "channels": channel_count if can_formats else 0,
            "bus_type": bus_type if can_formats else None,
            "nominal_bitrate": nominal_bitrate if can_formats else None,
            "data_bitrate": data_bitrate if can_formats else None,
            "ethernet_bitrate": eth_bitrates[0] if eth_formats and eth_bitrates else None,
            "ethernet_bitrates": eth_bitrates if eth_formats else None,
            "routing_table": str(args.routing_table.resolve()) if args.routing_table else None,
            "filter_system": filter_summary,
            "trace_quality": trace_quality_summary(),
            "signal_suggestions": signal_suggestions,
            "hardware_profile": getattr(args, "hardware_summary", None) or {"enabled": False},
            "hardware_validation": getattr(args, "hardware_validation", None) or {
                "valid": True,
                "mode": "non_invasive_validation",
                "findings": [],
            },
        },
    )
    written.append(out_dir / "generation_manifest.json")
    return written, warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Technologieoffener Communication Simulator mit optionalen nativen CAN/Ethernet-Writern"
    )
    parser.add_argument("--out", default="realistic_can_trace.blf", help="Ausgabe-BLF")
    parser.add_argument("--dbc", default="realistic_can_network.dbc", help="Ausgabe-DBC")
    parser.add_argument("--out-dir", default=None, help="Zielordner für Multi-Format-Ausgabe")
    parser.add_argument(
        "--formats",
        default="blf,dbc",
        help="Kommagetrennt: universal-jsonl,universal-csv sowie native Formate wie blf,dbc,pcapng",
    )
    parser.add_argument("--duration", type=float, default=60.0, help="Trace-Laufzeit in Sekunden")
    parser.add_argument("--messages", type=int, default=None, help="Anzahl Datenbotschaften; ohne Wert nimmt --routing-table die CSV-Zeilenzahl")
    parser.add_argument("--seed", type=int, default=42, help="Zufalls-Seed")
    parser.add_argument("--routing-table", type=Path, default=None, help="CSV-Routingtabelle mit sender,receiver,cycle_ms,channel,gateway_to_channel,frame_id,name")
    parser.add_argument("--write-routing-template", type=Path, default=None, help="Schreibt eine Beispiel-Routing-CSV und beendet das Programm")
    parser.add_argument("--config", type=Path, default=None, help="Standalone JSON-Simulationskonfiguration")
    parser.add_argument("--write-config-template", type=Path, default=None, help="Schreibt eine Standalone-Konfigurationsvorlage und beendet das Programm")
    parser.add_argument("--interface-out", type=Path, default=None, help="Schreibt eine JSON-Ergebnisdatei")
    parser.add_argument(
        "--simulation-mode",
        choices=["existing", "restbus"],
        default="existing",
        help="existing nutzt Routing-Tabelle/Default-Logik; restbus erzeugt Routen aus Teilnehmern",
    )
    parser.add_argument(
        "--channels",
        type=int,
        choices=range(1, 17),
        default=2,
        metavar="1-16",
        help="Anzahl CAN-Kanäle im Trace; 16 erzeugt CAN0 bis CAN15",
    )
    parser.add_argument("--bus", choices=["classic", "fd", "xl"], default="fd", help="Busprofil: classic, fd oder xl")
    parser.add_argument("--classic-can", action="store_true", help="Classic CAN statt CAN-FD erzeugen")
    parser.add_argument(
        "--nominal-bitrate",
        type=int,
        choices=sorted(COMMON_NOMINAL_BITRATES.values()),
        default=500_000,
        help="Nominale/arbitration Datenrate in bit/s",
    )
    parser.add_argument(
        "--fd-bitrate",
        type=int,
        choices=sorted(CAN_FD_DATA_BITRATES.values()),
        default=None,
        help="CAN-FD Datenphase in bit/s",
    )
    parser.add_argument(
        "--xl-data-bitrate",
        type=int,
        choices=sorted(CAN_XL_DATA_BITRATES.values()),
        default=None,
        help="CAN-XL Datenphase in bit/s",
    )
    parser.add_argument(
        "--eth-bitrate",
        type=int,
        choices=sorted(ETHERNET_BITRATES.values()),
        default=1_000_000_000,
        help="Ethernet Datenrate in bit/s für Manifest/Metadaten",
    )
    parser.add_argument(
        "--eth-bitrates",
        default=None,
        help="Kommagetrennte Ethernet-Datenraten in bit/s, z.B. 100000000,1000000000",
    )
    parser.add_argument(
        "--eth-messages",
        type=int,
        default=None,
        help="Anzahl Ethernet-Kommunikationsströme; ohne Wert wird --messages verwendet",
    )
    parser.add_argument(
        "--technology",
        choices=sorted(DEFAULT_TECHNOLOGY_REGISTRY.builtin),
        default=None,
        help="Bus- oder Protokolltechnologie für die universelle Standalone-Simulation",
    )
    parser.add_argument(
        "--list-technologies",
        action="store_true",
        help="Zeigt alle registrierten Technologien nach Branche gruppiert an",
    )
    parser.add_argument("--industry", default=None, help="Optionale Branchenzuordnung")
    parser.add_argument(
        "--bitrate",
        type=int,
        default=None,
        help="Explizite Technologie-Bitrate in bit/s; für CAN-FD zusätzlich --fd-bitrate angeben",
    )
    parser.add_argument("--nodes", type=int, default=2, help="Anzahl Hardware-Knoten, mindestens 2")
    parser.add_argument(
        "--cycle-ms",
        type=float,
        default=100.0,
        help="Kommunikationszyklus der universellen Route in Millisekunden",
    )
    parser.add_argument(
        "--payload-bytes",
        type=int,
        default=None,
        help="Payload-Größe; wird gegen die Technologiegrenze geprüft",
    )
    parser.add_argument("--max-events", type=int, default=None, help="Maximale Anzahl neutraler Trace-Events")
    parser.add_argument(
        "--dropout-probability",
        type=float,
        default=0.0,
        help="Dropout-Wahrscheinlichkeit von 0.0 bis 1.0",
    )
    parser.add_argument(
        "--corruption-probability",
        type=float,
        default=0.0,
        help="Korruptionswahrscheinlichkeit von 0.0 bis 1.0",
    )
    parser.add_argument("--network-id", default=None, help="Optionale ID des simulierten Netzwerks")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validiert Hardware und Topologie ohne Trace-Erzeugung",
    )
    parser.add_argument(
        "--native-cli",
        action="store_true",
        help="Erzwingt den bisherigen nativen CAN/Ethernet-CLI-Pfad",
    )
    args = parser.parse_args()

    if args.list_technologies:
        print(f"Registrierte Technologien: {len(DEFAULT_TECHNOLOGY_REGISTRY.builtin)}")
        for generator in DEFAULT_TECHNOLOGY_REGISTRY.generators:
            print(f"\n{generator.domain}:")
            for technology_id, profile in generator.generate().items():
                bitrate = profile.default_bitrate
                bitrate_label = f", {format_bitrate(bitrate)}" if bitrate else ""
                print(f"- {technology_id} ({profile.kind}{bitrate_label})")
        return

    if args.write_config_template is not None:
        from backend.nis.simulation.communication_simulator import write_config_template

        write_config_template(args.write_config_template)
        print(f"Konfigurationsvorlage geschrieben: {args.write_config_template.resolve()}")
        return

    interactive_native = False
    if len(sys.argv) == 1:
        cli_mode = choose_mode(
            "Simulationsart:",
            {
                "1": "Technologieoffene Standalone-Simulation (alle registrierten Technologien)",
                "2": "Native CAN/CAN-FD/CAN-XL/Ethernet-Dateiformate",
            },
            default_value="1",
        )
        if cli_mode == "1":
            options = InteractiveStandaloneCli().collect()
            runner = StandaloneCliRunner()
            result = runner.run(options)
            runner.print_result(result)
            return
        interactive_native = True

    if args.technology is not None and not args.native_cli:
        if not 2 <= args.nodes <= 100:
            parser.error("--nodes muss zwischen 2 und 100 liegen")
        if args.duration <= 0:
            parser.error("--duration muss größer als 0 sein")
        if args.cycle_ms <= 0:
            parser.error("--cycle-ms muss größer als 0 sein")
        if args.bitrate is not None and args.bitrate < 1:
            parser.error("--bitrate muss mindestens 1 bit/s sein")
        if args.max_events is not None and args.max_events < 1:
            parser.error("--max-events muss mindestens 1 sein")
        if args.max_events is None and args.messages is not None and args.messages < 1:
            parser.error("--messages muss mindestens 1 sein")
        for name in ("dropout_probability", "corruption_probability"):
            if not 0.0 <= float(getattr(args, name)) <= 1.0:
                parser.error(f"--{name.replace('_', '-')} muss zwischen 0.0 und 1.0 liegen")
        try:
            options = options_from_namespace(args)
            runner = StandaloneCliRunner()
            result = runner.run(options, validate_only=args.validate_only)
        except (OSError, TypeError, ValueError) as exc:
            parser.error(str(exc))
        runner.print_result(result)
        return

    if args.config is not None and not args.native_cli:
        runner = StandaloneCliRunner()
        try:
            result = runner.simulator.run(
                runner.simulator.load_config(args.config),
                validate_only=args.validate_only,
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            parser.error(f"Simulationskonfiguration konnte nicht verarbeitet werden: {exc}")
        runner.print_result(result)
        return

    simulation_config: Dict[str, Any] | None = None
    if args.config is not None:
        try:
            simulation_config = load_simulation_config(args.config)
            apply_simulation_config_to_args(args, simulation_config)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(f"Simulationskonfiguration konnte nicht gelesen werden: {exc}")

    if args.write_routing_template is not None:
        write_routing_template(args.write_routing_template)
        print(f"Routing-Template geschrieben: {args.write_routing_template.resolve()}")
        return

    if args.simulation_mode not in {"existing", "restbus"}:
        parser.error("--simulation-mode muss existing oder restbus sein")
    if args.bus not in {"classic", "fd", "xl"}:
        parser.error("--bus muss classic, fd oder xl sein")
    if not 1 <= int(args.channels) <= 16:
        parser.error("--channels muss zwischen 1 und 16 liegen")

    if interactive_native:
        selected_profile = choice()
        bus_type = str(selected_profile["bus_type"])
        nominal_bitrate = int(selected_profile["nominal_bitrate"])
        data_bitrate_value = selected_profile["data_bitrate"]
        data_bitrate = int(data_bitrate_value) if data_bitrate_value is not None else None
        channel_count = int(selected_profile["channel_count"])
        args.eth_bitrate = selected_profile["eth_bitrate"]
        args.eth_bitrates = selected_profile["eth_bitrates"]
        args.eth_messages = selected_profile["eth_messages"]
        args.formats = str(selected_profile["formats"])
        if selected_profile["out_dir"] is not None:
            args.out_dir = str(selected_profile["out_dir"])
    else:
        bus_type = "classic" if args.classic_can else args.bus
        nominal_bitrate = args.nominal_bitrate
        channel_count = args.channels
        if bus_type == "classic":
            data_bitrate = None
        elif bus_type == "fd":
            data_bitrate = args.fd_bitrate
            if data_bitrate is None:
                data_bitrate = 2_000_000
        else:
            data_bitrate = args.xl_data_bitrate
            if data_bitrate is None:
                data_bitrate = CAN_XL_DATA_BITRATES["e"]
        if bus_type == "fd" and data_bitrate is None:
            data_bitrate = 2_000_000

    restbus_participants: List[RestbusParticipant] | None = None
    restbus_summary: Dict[str, object] | None = None
    if args.routing_table:
        routing_rows = load_routing_table(args.routing_table, channel_count)
    elif args.simulation_mode == "restbus":
        try:
            restbus_participants = restbus_participants_from_request(simulation_config or {}, channel_count)
            requested_routes = int(args.messages) if args.messages is not None else None
            routing_rows = build_restbus_routing_rows(restbus_participants, channel_count, max_routes=requested_routes)
            restbus_summary = restbus_interface_summary(restbus_participants, routing_rows)
        except ValueError as exc:
            parser.error(str(exc))
    else:
        routing_rows = None
    num_messages = args.messages
    if num_messages is None:
        num_messages = len(routing_rows) if routing_rows is not None else 100

    try:
        selected_formats = parse_formats(args.formats)
        args.eth_bitrates = parse_ethernet_bitrates(args.eth_bitrates)
    except ValueError as exc:
        parser.error(str(exc))
    if args.eth_messages is not None and args.eth_messages < 1:
        parser.error("--eth-messages muss mindestens 1 sein")

    legacy_single_output = (
        args.out_dir is None
        and selected_formats == ["blf", "dbc"]
    )

    if not legacy_single_output:
        route_generated_out_dir_to_library(args, selected_formats)
        package_type = package_type_from_formats(selected_formats)
        progress = ProgressBar()
        written, warnings = generate_format_package(
            formats=selected_formats,
            args=args,
            bus_type=bus_type,
            nominal_bitrate=nominal_bitrate,
            data_bitrate=data_bitrate,
            channel_count=channel_count,
            routing_rows=routing_rows,
            num_messages=num_messages,
            progress=progress,
        )
        interface_path = args.interface_out
        if interface_path is None and (args.simulation_mode == "restbus" or args.config is not None):
            interface_path = Path(args.out_dir or EXPORT_ROOT / "generated_trace_package").resolve() / "simulation_interface.json"
        if interface_path is not None:
            progress.update(97, "Schreibe Simulations-Interface")
            write_simulation_interface(
                interface_path.resolve(),
                simulation_mode=args.simulation_mode,
                written=written,
                warnings=warnings,
                duration_s=args.duration,
                bus_type=bus_type,
                channel_count=channel_count,
                nominal_bitrate=nominal_bitrate,
                data_bitrate=data_bitrate,
                routing_rows=routing_rows,
                restbus_summary=restbus_summary,
                filter_summary=getattr(args, "filter_summary", None),
                signal_suggestions=getattr(args, "signal_suggestions", None),
                hardware_summary=getattr(args, "hardware_summary", None),
                hardware_validation=getattr(args, "hardware_validation", None),
            )
            written.append(interface_path.resolve())
        progress.update(99, "Finalisiere Trace-Ordner")
        trace_package_path = archive_trace_package_to_library(Path(args.out_dir or EXPORT_ROOT / "generated_trace_package").resolve(), package_type)
        progress.update(100, "Erstellung fertig")
        print("Fertig.")
        print(f"Pakettyp: {package_type.capitalize() if package_type != 'can' else 'CAN'}")
        print(f"Simulation: {args.simulation_mode}")
        print(f"Formate: {', '.join(selected_formats)}")
        if package_type in {"ethernet", "mixed"}:
            selected_eth_bitrates = args.eth_bitrates or [args.eth_bitrate]
            print(f"Ethernet-Geschwindigkeiten: {', '.join(format_bitrate(int(value)) for value in selected_eth_bitrates)}")
            print(f"Ethernet-Kommunikationsströme: {args.eth_messages or num_messages}")
        print(f"Dateien: {len(written)}")
        for path in written:
            print(f"- {path}")
        if args.routing_table:
            print(f"Routing-Tabelle: {args.routing_table.resolve()} ({len(routing_rows)} Routen)")
        elif args.simulation_mode == "restbus":
            print(f"Restbus: {len(restbus_participants or [])} Teilnehmer, {len(routing_rows or [])} Routen")
        if trace_package_path is not None:
            print(f"Trace folder: {trace_package_path}")
        if warnings:
            print("Warnungen:")
            for warning in warnings:
                print(f"- {warning}")
        return

    out_blf = Path(args.out).resolve()
    out_dbc = Path(args.dbc).resolve()

    progress = ProgressBar()
    progress.update(15, "Erzeuge BLF Trace")
    messages = generate_blf(
        out_blf=out_blf,
        duration_s=args.duration,
        bus_type=bus_type,
        seed=args.seed,
        num_messages=num_messages,
        nominal_bitrate=nominal_bitrate,
        data_bitrate=data_bitrate,
        channel_count=channel_count,
        routing_rows=routing_rows,
    )
    progress.update(72, "Schreibe DBC Datenbank")
    write_dbc(out_dbc, messages, nominal_bitrate=nominal_bitrate, data_bitrate=data_bitrate)

    progress.update(85, "Validiere BLF")
    count, first, last = validate_blf(out_blf)
    written = [out_blf, out_dbc]
    interface_path = args.interface_out
    if interface_path is None and (args.simulation_mode == "restbus" or args.config is not None):
        interface_path = out_blf.parent / "simulation_interface.json"
    if interface_path is not None:
        progress.update(95, "Schreibe Simulations-Interface")
        write_simulation_interface(
            interface_path.resolve(),
            simulation_mode=args.simulation_mode,
            written=written,
            warnings=[],
            duration_s=args.duration,
            bus_type=bus_type,
            channel_count=channel_count,
            nominal_bitrate=nominal_bitrate,
            data_bitrate=data_bitrate,
            routing_rows=routing_rows,
            restbus_summary=restbus_summary,
            filter_summary=getattr(args, "filter_summary", None),
            signal_suggestions=getattr(args, "signal_suggestions", None),
            hardware_summary=getattr(args, "hardware_summary", None),
            hardware_validation=getattr(args, "hardware_validation", None),
        )
        written.append(interface_path.resolve())

    progress.update(99, "Aktualisiere Library")
    library_path = archive_generated_files_to_library(written, "can")
    progress.update(100, "Erstellung fertig")
    print("Fertig.")
    print(f"BLF: {out_blf}")
    print(f"DBC: {out_dbc}")
    if interface_path is not None:
        print(f"Simulationsergebnis: {interface_path.resolve()}")
    if library_path is not None:
        print(f"Library: {library_path}")
    print(f"Frames: {count}")
    print(f"UTC-Zeitbereich: {format_utc_timestamp(first)} bis {format_utc_timestamp(last)}")
    print(f"Trace-Dauer: {last - first:.6f}s")
    mode_label = {"classic": "Classic CAN", "fd": "CAN-FD", "xl": "CAN-XL"}[bus_type]
    print(f"Modus: {mode_label}")
    print(f"Nominale Datenrate: {format_bitrate(nominal_bitrate)}")
    if bus_type in {"fd", "xl"}:
        print(f"Datenphase: {format_bitrate(data_bitrate)}")
    if bus_type == "xl":
        print("CAN-XL Hinweis: natives CAN-XL wird von dieser python-can/BLF-Version nicht unterstützt; BLF ist CAN-FD-kompatibel gespeichert.")
    active_channels = sorted({m.channel for m in messages} | {m.gateway_to_channel for m in messages if m.gateway_to_channel is not None})
    print(f"CAN-Kanäle: {channel_count} konfiguriert ({', '.join(f'CAN{ch}' for ch in range(channel_count))})")
    print(f"Aktive Kanäle im Nachrichtenmodell: {', '.join(f'CAN{ch}' for ch in active_channels)}")
    print(f"Simulation: {args.simulation_mode}")
    if args.routing_table:
        print(f"Routing-Tabelle: {args.routing_table.resolve()} ({len(routing_rows)} Routen)")
    elif args.simulation_mode == "restbus":
        print(f"Restbus: {len(restbus_participants or [])} Teilnehmer, {len(routing_rows or [])} Routen")
    print(f"Kommunikation: {len([m for m in messages if m.kind == 'data'])} Datenbotschaften + "
          f"{len([m for m in messages if m.kind == 'response'])} Empfangsantworten")
    print("Hinweis: Jede Datenbotschaft hat eine passende ACK/NACK Response mit CRC-, DLC- und Counter-Prüfung.")


if __name__ == "__main__":
    main()
