"""Industry- and technology-aware routing for engineering generation.

The manager deliberately keeps two decisions independent:

* the industry selects vocabulary, device and function templates;
* each confirmed bus selects its own transport, topology, timing and capacity
  path through the technology registry.

It does not generate canonical model objects and it does not approve a
proposal.  Its result is an explainable policy decision that generators can
persist as evidence and use to avoid leaking one industry's defaults into
another industry.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable

from backend.communication.technologies import (
    DEFAULT_TECHNOLOGY_ONBOARDING,
    DEFAULT_TECHNOLOGY_REGISTRY,
    MODEL_TYPES,
)


POLICY_VERSION = "generation-rules.v1"


_INDUSTRY_ALIASES = {
    "automotive": "automotive",
    "vehicle": "automotive",
    "fahrzeug": "automotive",
    "industrial": "industrial_automation",
    "industrial_automation": "industrial_automation",
    "industrieautomation": "industrial_automation",
    "robotics": "robotics_ros",
    "robotics_ros": "robotics_ros",
    "robotik": "robotics_ros",
    "aerospace": "aerospace",
    "aerospace_defense": "aerospace",
    "aviation": "aerospace",
    "rail": "rail",
    "railway": "rail",
    "marine": "marine",
    "building": "building_automation",
    "building_automation": "building_automation",
    "energy": "energy",
    "process": "process_industry",
    "process_industry": "process_industry",
    "embedded": "embedded_systems",
    "embedded_systems": "embedded_systems",
    "iot": "iot_wireless",
    "iot_wireless": "iot_wireless",
    "generic": "generic_networking",
    "generic_networking": "generic_networking",
    "custom": "custom",
}

_INDUSTRY_PATTERNS: dict[str, tuple[str, ...]] = {
    "building_automation": (
        r"\bgeb(?:ä|ae)ude(?:automation|technik)?\b", r"\bbuilding\s+automation\b",
    ),
    "process_industry": (
        r"\bprozessindustrie\b", r"\bprocess\s+industr(?:y|ies)\b", r"\bdcs\b",
    ),
    "industrial_automation": (
        r"\bindustrieautomation\b", r"\bindustrial\s+automation\b", r"\bindustrieanlage\w*\b", r"\bfabrik\w*\b", r"\bplc\b", r"\bsps\b",
    ),
    "robotics_ros": (
        r"\brobotik\b", r"\brobotics\b", r"\broboter\w*\b", r"\brobots?\b",
    ),
    "automotive": (
        r"\bautomotive\b", r"\bfahrzeug\w*\b", r"\bvehicle\b", r"\bcar\b", r"\bauto(?:mobil)?\b", r"\badas\b",
    ),
    "aerospace": (
        r"\bluftfahrt\b", r"\baerospace\b", r"\bavionik\b", r"\bavionics\b", r"\buav\b", r"\bdrohn\w*\b", r"\bdrone\b",
    ),
    "rail": (r"\bbahn\b", r"\bschienenfahrzeug\w*\b", r"\brail(?:way)?\b", r"\btrain\b"),
    "marine": (r"\bmarine\b", r"\bschiff\w*\b", r"\bmaritim\w*\b"),
    "energy": (r"\benergietechnik\b", r"\benergieversorgung\b", r"\bsmart\s+grid\b", r"\bpower\s+grid\b", r"\bstromnetz\b"),
    "embedded_systems": (r"\bembedded\s+systems?\b", r"\beingebettete\s+systeme\b", r"\bmikrocontroller\w*\b"),
    "iot_wireless": (r"\biot\b", r"\binternet\s+of\s+things\b", r"\bwireless\s+sensor\w*\b"),
}

_TECHNOLOGY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("can_fd", r"\bcan\s*[-_ ]?fd\b"),
    ("can_xl", r"\bcan\s*[-_ ]?xl\b"),
    ("flexray", r"\bflexray\b"),
    ("lin", r"\blin(?:\s*[- ]?bus)?\b"),
    ("someip", r"\bsome\s*/?\s*ip\b"),
    ("doip", r"\bdoip\b"),
    ("ethercat", r"\bethercat\b"),
    ("profinet", r"\bprofi\s*net\b"),
    ("profibus_dp", r"\bprofibus\s*[-_ ]?dp\b"),
    ("profibus_pa", r"\bprofibus\s*[-_ ]?pa\b"),
    ("modbus_tcp", r"\bmodbus\s*[-_ /]?tcp\b"),
    ("modbus_rtu", r"\bmodbus\s*[-_ /]?rtu\b"),
    ("io_link", r"\bio\s*[-_ ]?link\b"),
    ("opc_ua", r"\bopc\s*[-_ ]?ua\b"),
    ("ros2", r"\bros\s*2\b"),
    ("dds", r"\bdds(?:\s*/\s*rtps)?\b"),
    ("bacnet_ip", r"\bbacnet\s*[-_ /]?ip\b"),
    ("arinc429", r"\barinc\s*[-_ ]?429\b"),
    ("mil_std_1553", r"\bmil\s*[-_ ]?std\s*[-_ ]?1553\b|\bmil\s*[-_ ]?1553\b"),
    ("nmea2000", r"\bnmea\s*[-_ ]?2000\b"),
    ("nmea0183", r"\bnmea\s*[-_ ]?0183\b"),
    ("i2c", r"\bi\s*[²2]\s*c\b"),
    ("spi", r"\bspi\b"),
    ("uart", r"\buart\b"),
    ("rs485", r"\brs\s*[-_ ]?485\b"),
    ("usb", r"\busb\b"),
    ("ethernet", r"\b(?:automotive\s+|industrial\s+)?ethernet\b|\b(?:100|1000)base\s*[-_ ]?t1\b"),
    # Plain CAN is evaluated last so CAN-FD/CAN-XL do not become CAN too.
    ("can", r"\bcan(?:\s*[- ]?bus)?\b"),
)

_PERIPHERAL_BUSES = {"i2c", "spi", "uart", "usb", "gpio", "pwm", "adc", "dac", "one_wire"}
_SCHEDULED_BUSES = {"lin", "flexray"}
_INDUSTRIAL_REALTIME = {"profinet", "ethercat", "ethernet_ip", "powerlink", "sercos_iii", "cc_link"}
_PUBSUB = {"dds", "ros2", "opc_ua", "opc_ua_pubsub", "mqtt", "sparkplug_b"}
_SERIAL_FIELD = {"modbus_rtu", "modbus_ascii", "profibus_dp", "profibus_pa", "generic_serial", "rs485", "hart", "foundation_fieldbus_h1"}
_AVIONICS = {"arinc429", "mil_std_1553", "arinc664_afdx"}
_RAIL = {"mvb", "wtb", "etb", "trdp"}
_MARINE = {"nmea0183", "nmea2000", "iec61162"}


def _slug(value: Any) -> str:
    token = str(value or "").strip().lower().replace("/", "_").replace("-", "_").replace(" ", "_")
    return re.sub(r"_+", "_", token).strip("_")


def normalize_industry(value: Any) -> str | None:
    token = _slug(value)
    if not token:
        return None
    if token in _INDUSTRY_ALIASES:
        return _INDUSTRY_ALIASES[token]
    for model_type in MODEL_TYPES:
        if token == model_type["id"] or token == _slug(model_type.get("label")):
            return str(model_type["id"])
    return None


def _negated(text: str, match: re.Match[str]) -> bool:
    clause = re.split(r"[.!?;,\n]|\b(?:sondern|but|instead|und|and)\b", text[:match.start()], flags=re.I)[-1]
    if re.search(r"\b(?:kein\w*|nicht|ohne|no|not|non)\b", " ".join(clause.split()[-4:]), re.I):
        return True
    suffix = text[match.end():match.end() + 48]
    return bool(re.match(r"\s+(?:(?:ist|is)\s+)?(?:ausgeschlossen|unerwünscht|nicht\s+gewünscht|excluded)\b", suffix, re.I))


def industry_candidates(text: str) -> set[str]:
    found: set[str] = set()
    for industry, patterns in _INDUSTRY_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                if not _negated(text, match):
                    found.add(industry)
    return found


def _structured_industries(text: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    for label, raw in re.findall(r"^-\s*(Projekt-Modelltyp|Industrie):\s*([^\r\n]+)$", text, re.I | re.M):
        resolved = normalize_industry(raw)
        if resolved:
            results.append((resolved, f"structured:{label.lower()}"))
    return results


def _registered_technology(value: Any) -> tuple[str, dict[str, Any] | None]:
    technology_id = DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(value)
    # The product UI historically calls Ethernet T1 "automotive_ethernet";
    # execution uses the registered Ethernet data-link binding.
    if technology_id == "automotive_ethernet":
        technology_id = "ethernet"
    try:
        return technology_id, DEFAULT_TECHNOLOGY_REGISTRY.profile(technology_id)
    except KeyError:
        return technology_id, None


def technology_ids_from_task(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    occupied: list[tuple[int, int]] = []
    for technology_id, pattern in _TECHNOLOGY_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            if _negated(text, match):
                continue
            if technology_id == "can" and "CAN" not in match.group(0) and not re.search(r"can\s*[- ]?bus", match.group(0), re.I):
                # Do not interpret the English modal verb "can" as a bus.
                continue
            if technology_id == "can" and any(start <= match.start() < end for start, end in occupied):
                continue
            resolved, _ = _registered_technology(technology_id)
            if not any(item["id"] == resolved for item in found):
                found.append({"id": resolved, "source": "task_text", "evidence": match.group(0)})
            if technology_id in {"can_fd", "can_xl"}:
                occupied.append(match.span())
    structured = re.search(r"^- Netzwerktechnologien:\s*([^\r\n]+)$", text, re.I | re.M)
    if structured:
        for raw in re.findall(r"\(([a-zA-Z0-9_.:-]+)\)", structured.group(1)):
            resolved, _ = _registered_technology(raw.removeprefix("detected:"))
            if resolved and not any(item["id"] == resolved for item in found):
                found.append({"id": resolved, "source": "structured:network_technologies", "evidence": raw})
    for profile in DEFAULT_TECHNOLOGY_REGISTRY.profiles():
        if profile.get("knowledge_origin") != "GENERATED_TECHNOLOGY_PACK":
            continue
        for candidate in [profile["id"], profile.get("label"), *(profile.get("aliases") or [])]:
            label = str(candidate or "").strip()
            if len(label) < 4:
                continue
            match = re.search(rf"(?<![A-Za-z0-9]){re.escape(label)}(?![A-Za-z0-9])", text, re.I)
            if match and not _negated(text, match) and not any(item["id"] == profile["id"] for item in found):
                found.append({"id": profile["id"], "source": "generated_technology_alias", "evidence": match.group(0)})
    for match in re.finditer(r"\b(?:ein|a)\s+([A-Za-z][A-Za-z0-9./_-]*(?:\s*[- ]?\d+)?)\s+(?:netzwerk|network|bus)\b", text, re.I):
        candidate = match.group(1).strip()
        if candidate.lower() in {"neues", "new", "lokales", "local", "sicheres", "secure"}:
            continue
        resolved, profile = _registered_technology(candidate)
        if profile is None and not any(item["id"] == resolved for item in found):
            found.append({"id": resolved, "source": "unknown_technology_phrase", "evidence": candidate})
    return found


def _bus_path(technology_id: str, profile: dict[str, Any] | None) -> str:
    stack = {str(item) for item in (profile or {}).get("default_stack") or []}
    hardware = str((profile or {}).get("hardware_interface") or "")
    if technology_id in _PERIPHERAL_BUSES or hardware in {"i2c_controller", "spi_controller", "uart_port", "gpio_pin", "pwm_channel", "adc_channel", "dac_channel", "usb_port"}:
        return "peripheral_io"
    if technology_id in _SCHEDULED_BUSES:
        return "scheduled_frame_bus"
    if technology_id in {"can", "can_fd", "can_xl", "generic_can", "canopen", "j1939", "isobus"} or "can" in stack:
        return "arbitrated_can_bus"
    if technology_id in _INDUSTRIAL_REALTIME:
        return "industrial_realtime_ethernet"
    if technology_id in _PUBSUB:
        return "publish_subscribe_middleware"
    if technology_id in _SERIAL_FIELD or "rs485_port" == hardware:
        return "serial_field_bus"
    if technology_id in _AVIONICS:
        return "avionics_bus"
    if technology_id in _RAIL:
        return "rail_transport"
    if technology_id in _MARINE:
        return "marine_transport"
    if technology_id in {"ethernet", "someip", "doip", "ip", "udp", "tcp", "modbus_tcp", "bacnet_ip"} or "ethernet" in stack or hardware == "ethernet_port":
        return "switched_packet_network"
    if technology_id in {"wifi", "ble", "zigbee", "thread", "lorawan", "5g", "lte"}:
        return "wireless_network"
    return "registry_transport" if profile else "custom_transport_review"


def _recommended_for(industry: str | None) -> set[str]:
    row = next((item for item in MODEL_TYPES if item["id"] == industry), None)
    return {DEFAULT_TECHNOLOGY_REGISTRY.normalize_id(item) for item in (row or {}).get("recommended_technologies") or []}


def resolve_generation_policy(
    task: str,
    *,
    industry: str | None = None,
    bus_types: Iterable[Any] = (),
) -> dict[str, Any]:
    """Return a deterministic, explainable generation routing decision."""
    text = str(task or "")
    findings: list[dict[str, Any]] = []
    structured = _structured_industries(text)
    selected = normalize_industry(industry)
    selected_source = "explicit_argument" if selected else None
    if industry and not selected:
        findings.append({
            "code": "UNKNOWN_INDUSTRY",
            "severity": "WARNING",
            "message": f"Unbekanntes Branchenprofil: {industry}",
        })
    structured_ids = list(dict.fromkeys(item[0] for item in structured))
    if not selected and len(structured_ids) == 1:
        selected, selected_source = structured_ids[0], structured[0][1]
    candidates = sorted(industry_candidates(text))
    if not selected and len(candidates) == 1:
        selected, selected_source = candidates[0], "task_inference"
    if selected_source == "explicit_argument" and structured_ids and any(item != selected for item in structured_ids):
        findings.append({
            "code": "INDUSTRY_CONTEXT_CONFLICT",
            "severity": "ERROR",
            "message": "Expliziter Projektkontext und strukturierte Aufgabenbranche widersprechen sich.",
            "selected": selected,
            "structured": structured_ids,
        })
    if len(structured_ids) > 1 or (not selected and len(candidates) > 1):
        findings.append({
            "code": "AMBIGUOUS_INDUSTRY",
            "severity": "ERROR",
            "message": "Mehrere Branchen sind belegt; das Projektprofil muss explizit gewählt werden.",
            "candidates": structured_ids or candidates,
        })
    elif selected and candidates and selected not in candidates:
        findings.append({
            "code": "INDUSTRY_CONTEXT_DIFFERENCE",
            "severity": "INFO",
            "message": "Das explizite Projektprofil hat Vorrang vor beiläufigen Branchenbegriffen.",
            "selected": selected,
            "observed": candidates,
        })
    if not selected:
        findings.append({
            "code": "INDUSTRY_REQUIRED",
            "severity": "ERROR",
            "message": "Kein eindeutiges Branchenprofil erkannt; branchenspezifische Vorlagen bleiben gesperrt.",
        })

    technology_evidence: list[dict[str, str]] = []
    for raw in bus_types:
        technology_id, _ = _registered_technology(raw)
        if technology_id and not any(item["id"] == technology_id for item in technology_evidence):
            technology_evidence.append({"id": technology_id, "source": "explicit_bus_type", "evidence": str(raw)})
    for item in technology_ids_from_task(text):
        if not any(existing["id"] == item["id"] for existing in technology_evidence):
            technology_evidence.append(item)

    recommended = _recommended_for(selected)
    buses: list[dict[str, Any]] = []
    for item in technology_evidence:
        technology_id, profile = _registered_technology(item["id"])
        if profile is None:
            onboarding = DEFAULT_TECHNOLOGY_ONBOARDING.resolve(technology_id)
            findings.append({
                "code": "UNREGISTERED_BUS_TYPE",
                "severity": "ERROR",
                "message": f"Bustyp {technology_id} besitzt keinen registrierten Erzeugungsvertrag.",
                "technology_id": technology_id,
                "knowledge_status": onboarding["status"],
                "onboarding_trigger": onboarding["discovery_trigger"],
                "similar_technologies": onboarding.get("candidates") or [],
            })
            buses.append({
                **item,
                "id": technology_id,
                "path": "technology_discovery",
                "registered": False,
                "executable": False,
                "knowledge_status": onboarding["status"],
                "onboarding_trigger": onboarding["discovery_trigger"],
            })
            continue
        status = str(profile.get("implementation_status") or "NOT_SUPPORTED")
        executable = status in {"IMPLEMENTED", "PARTIAL", "EXPERIMENTAL", "LEGACY"}
        if not executable:
            findings.append({
                "code": "BUS_GENERATOR_NOT_EXECUTABLE",
                "severity": "ERROR",
                "message": f"Bustyp {technology_id} ist nur geplant und besitzt keinen ausführbaren Generator.",
                "technology_id": technology_id,
                "implementation_status": status,
            })
        profile_domain = str(profile.get("domain") or "generic_networking")
        if selected and profile_domain not in {selected, "generic_networking", "custom"} and technology_id not in recommended:
            findings.append({
                "code": "CROSS_INDUSTRY_BUS_REVIEW",
                "severity": "WARNING",
                "message": f"{technology_id} stammt aus dem Profil {profile_domain}; Nutzung in {selected} benötigt eine explizite technische Begründung.",
                "technology_id": technology_id,
                "profile_domain": profile_domain,
                "selected_industry": selected,
            })
        buses.append({
            **item,
            "id": technology_id,
            "path": _bus_path(technology_id, profile),
            "registered": True,
            "executable": executable,
            "implementation_status": status,
            "profile_domain": profile_domain,
            "hardware_interface": profile.get("hardware_interface"),
            "technology_stack": list(profile.get("default_stack") or [technology_id]),
            "generator": type(DEFAULT_TECHNOLOGY_REGISTRY.resolve_generator(profile.get("default_stack") or [technology_id])).__name__ if executable else None,
        })
    if not buses:
        findings.append({
            "code": "BUS_TYPE_REQUIRED",
            "severity": "ERROR",
            "message": "Kein bestätigter Bustyp erkannt; transportspezifische Erzeugung bleibt offen.",
        })

    blocked = any(item["severity"] == "ERROR" for item in findings)
    paths = list(dict.fromkeys(item["path"] for item in buses))
    decision = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "status": "NEEDS_INPUT" if blocked else "READY",
        "industry": {
            "id": selected,
            "source": selected_source or "unresolved",
            "candidates": candidates,
            "template_path": f"industry_template:{selected}" if selected else "industry_template:blocked",
        },
        "bus_types": buses,
        "generation_path": {
            "industry_path": f"industry_template:{selected}" if selected else None,
            "transport_paths": paths,
            "steps": [
                "resolve_industry_template",
                "resolve_each_bus_in_technology_registry",
                "generate_semantic_payloads",
                "generate_transport_per_bus_path",
                "validate_routing_capacity_timing_per_bus",
                "merge_only_at_canonical_model_boundary",
            ],
            "fallback": "generic templates are allowed only when generic_networking/custom is explicit; unresolved industry or bus remains open",
        },
        "guardrails": {
            "industry_does_not_define_bus": True,
            "bus_does_not_define_industry": True,
            "mixed_bus_paths_are_independent": True,
            "cross_industry_defaults_are_forbidden": True,
            "explicit_project_context_precedes_keyword_inference": True,
        },
        "findings": findings,
    }
    canonical = json.dumps(decision, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    decision["decision_sha256"] = sha256(canonical.encode("utf-8")).hexdigest()
    return decision


def inspect_generation_rules(arguments: dict[str, Any]) -> dict[str, Any]:
    return resolve_generation_policy(
        str(arguments.get("prompt") or ""),
        industry=arguments.get("industry"),
        bus_types=arguments.get("bus_types") or (),
    )
