"""Controlled discovery and onboarding of network technology knowledge.

The core deliberately consumes structured source claims.  Fetching documents and
extracting claims is delegated to research providers; this module never executes
source content, installs packages, or turns an unverified value into a simulation
default.  Persisted packs are general NIS knowledge and do not mutate a project.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Protocol

from .core.models import Layer, PayloadElementType, TechnologyCapability, TransportUnitType
from .core.registry import TechnologyRegistry


PACK_SCHEMA_VERSION = 1
PACK_FILES = (
    "manifest.json", "vocabulary.json", "physical_layer.json", "topology.json",
    "nodes.json", "interfaces.json", "messages.json", "signals.json", "timing.json",
    "diagnostics.json", "error_model.json", "simulation.json", "generation_rules.json",
    "sources.json", "validation.json",
)

PRIMARY_SOURCE_TYPES = {
    "STANDARD", "OFFICIAL_ORGANIZATION", "MANUFACTURER_DATASHEET",
}
SECONDARY_SOURCE_TYPES = {"APPLICATION_NOTE", "RESEARCH_INSTITUTE", "UNIVERSITY"}
UNTRUSTED_SOURCE_TYPES = {"COMMUNITY", "FORUM", "BLOG", "UNKNOWN"}

PARAMETER_FILES = {
    "standard": "manifest.json", "revision": "manifest.json",
    "physical_medium": "physical_layer.json", "physical_layer": "physical_layer.json",
    "nominal_data_rate": "physical_layer.json", "maximum_data_rate": "physical_layer.json",
    "duplex": "physical_layer.json", "termination": "physical_layer.json",
    "cable_properties": "physical_layer.json", "connector_constraints": "physical_layer.json",
    "distance_constraints": "physical_layer.json", "topology": "topology.json",
    "maximum_nodes": "topology.json", "addressing": "topology.json",
    "arbitration": "messages.json", "access_method": "messages.json",
    "frame_structure": "messages.json", "payload_size": "messages.json",
    "frame_overhead": "messages.json", "encoding": "signals.json",
    "signal_definition": "signals.json", "cycle_time": "timing.json",
    "period": "timing.json", "deadline": "timing.json", "latency": "timing.json",
    "jitter": "timing.json", "transmission_time": "timing.json",
    "propagation_time": "timing.json", "processing_time": "timing.json",
    "synchronization": "timing.json", "error_detection": "error_model.json",
    "error_recovery": "error_model.json", "diagnostics": "diagnostics.json",
    "redundancy": "simulation.json", "security": "simulation.json",
    "wake_up": "simulation.json", "power_modes": "simulation.json",
    "simulation_constraints": "simulation.json",
}

READINESS_DEFAULTS = {
    "topology": ("physical_medium", "topology"),
    "message_generation": ("frame_structure", "payload_size", "encoding"),
    "timing_simulation": ("nominal_data_rate", "timing"),
    "busload": ("nominal_data_rate", "frame_overhead", "payload_size", "access_method"),
    "error_simulation": ("error_detection", "error_recovery"),
    "diagnostics": ("diagnostics",),
}

TRIGGER_CATEGORIES = {
    "unknown_protocol": tuple(PARAMETER_FILES),
    "unknown_interface": ("physical_medium", "physical_layer", "duplex", "connector_constraints"),
    "unknown_message_format": ("frame_structure", "payload_size", "frame_overhead", "access_method"),
    "unknown_signal_encoding": ("encoding", "signal_definition"),
    "unknown_physical_layer": ("physical_medium", "physical_layer", "termination", "cable_properties", "distance_constraints"),
    "unknown_bus_speed": ("nominal_data_rate", "maximum_data_rate"),
    "unknown_timing_model": ("cycle_time", "deadline", "latency", "jitter", "synchronization"),
    "unknown_topology": ("topology", "maximum_nodes", "addressing"),
}

PROFILE_FIELDS = {
    "label", "domain", "layer", "transport_unit", "payload_element_types",
    "hardware_interface", "default_stack", "capabilities", "deterministic",
}
REQUIRED_PROFILE_FIELDS = {
    "label", "domain", "layer", "transport_unit", "payload_element_types", "hardware_interface",
}

_UNIT_KIND = {
    "nominal_data_rate": "rate", "maximum_data_rate": "rate",
    "payload_size": "bytes", "frame_overhead": "bytes",
    "cycle_time": "time", "period": "time", "deadline": "time", "latency": "time",
    "jitter": "time", "transmission_time": "time", "propagation_time": "time",
    "processing_time": "time", "distance_constraints": "distance",
}
_UNIT_FACTORS = {
    "rate": {"bit/s": (1.0, "bit/s"), "kbit/s": (1_000.0, "bit/s"), "mbit/s": (1_000_000.0, "bit/s"), "gbit/s": (1_000_000_000.0, "bit/s")},
    "bytes": {"byte": (1.0, "byte"), "bytes": (1.0, "byte"), "b": (1.0, "byte")},
    "time": {"ns": (0.000001, "ms"), "us": (0.001, "ms"), "µs": (0.001, "ms"), "ms": (1.0, "ms"), "s": (1_000.0, "ms")},
    "distance": {"mm": (0.001, "m"), "cm": (0.01, "m"), "m": (1.0, "m"), "km": (1_000.0, "m")},
}

_SUSPICIOUS = re.compile(
    r"ignore\s+(?:all\s+)?previous|system\s+prompt|developer\s+message|<script|"
    r"(?:rm\s+-rf|powershell\s+-command|cmd\.exe|curl\s+[^\n|]+\||wget\s+[^\n|]+\||"
    r"subprocess\.|os\.system\(|eval\(|exec\(|javascript:)",
    re.IGNORECASE,
)


class TechnologyResearchProvider(Protocol):
    """Provider boundary for standards/datasheet discovery and extraction."""

    provider_name: str

    def research(self, plan: dict[str, Any]) -> list[dict[str, Any]]: ...


def default_pack_root() -> Path:
    configured = os.environ.get("NIS_TECHNOLOGY_PACK_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[3] / "technologies" / "generated"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _safe_id(value: Any) -> str:
    token = str(value or "").strip().lower().replace("/", "_").replace("-", "_").replace(" ", "_")
    token = re.sub(r"[^a-z0-9_.]+", "_", token)
    return re.sub(r"_+", "_", token).strip("_.")


def _source_rank(source_type: str) -> int:
    if source_type in PRIMARY_SOURCE_TYPES:
        return 3
    if source_type in SECONDARY_SOURCE_TYPES:
        return 2
    return 1


def _normalize_unit(parameter: str, value: Any, unit: Any) -> tuple[Any, str | None, str | None]:
    kind = _UNIT_KIND.get(parameter)
    if not kind:
        return value, str(unit).strip() if unit not in {None, ""} else None, None
    normalized_unit = str(unit or "").strip().lower().replace("bps", "bit/s")
    normalized_unit = normalized_unit.replace("kb/s", "kbit/s").replace("mb/s", "mbit/s").replace("gb/s", "gbit/s")
    option = _UNIT_FACTORS[kind].get(normalized_unit)
    if option is None:
        return value, str(unit or "") or None, f"unit {unit!r} is invalid for {parameter}"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value, option[1], f"numeric value required for {parameter}"
    converted = value * option[0]
    if converted < 0 or (parameter in {"nominal_data_rate", "maximum_data_rate"} and converted == 0):
        return value, option[1], f"positive value required for {parameter}"
    if float(converted).is_integer():
        converted = int(converted)
    return converted, option[1], None


class TechnologyOnboardingService:
    def __init__(
        self,
        registry: TechnologyRegistry,
        pack_root: Path | str | None = None,
        *,
        providers: Iterable[TechnologyResearchProvider] = (),
    ) -> None:
        self.registry = registry
        self.pack_root = Path(pack_root) if pack_root is not None else default_pack_root()
        self.providers = tuple(providers)
        self.audit_events: list[dict[str, Any]] = []

    def _audit(self, event: str, technology_id: str, **details: Any) -> None:
        self.audit_events.append({"event": event, "technology_id": technology_id, "at": _now(), **details})

    def resolve(self, value: Any, *, requested_revision: str | None = None) -> dict[str, Any]:
        technology_id = self.registry.normalize_id(value)
        try:
            profile = self.registry.profile(technology_id)
        except KeyError:
            profile = None
        if profile is not None:
            registered_revision = str(profile.get("technology_revision") or "")
            status = "OUTDATED_REVISION" if requested_revision and registered_revision and requested_revision != registered_revision else "KNOWN"
            return {"status": status, "query": str(value), "technology_id": technology_id, "profile": profile, "matched_by": "registry"}

        query = _safe_id(value)
        scored = sorted(
            (
                (SequenceMatcher(None, query, item["id"]).ratio(), item["id"], item.get("label"))
                for item in self.registry.profiles()
            ),
            reverse=True,
        )
        similar = [
            {"technology_id": item_id, "label": label, "similarity": round(score, 3)}
            for score, item_id, label in scored[:5] if score >= 0.72
        ]
        status = "PARTIALLY_KNOWN" if similar else "UNKNOWN"
        self._audit("NIS_TECH_UNKNOWN", technology_id, resolution_status=status)
        return {
            "status": status,
            "query": str(value),
            "technology_id": technology_id,
            "matched_by": "similarity" if similar else None,
            "candidates": similar,
            "discovery_trigger": "unknown_protocol",
        }

    def research_plan(
        self,
        value: Any,
        *,
        triggers: Iterable[str] = ("unknown_protocol",),
        requested_revision: str | None = None,
    ) -> dict[str, Any]:
        resolution = self.resolve(value, requested_revision=requested_revision)
        selected_triggers = list(dict.fromkeys(str(item) for item in triggers)) or ["unknown_protocol"]
        categories: list[str] = []
        unknown_triggers: list[str] = []
        for trigger in selected_triggers:
            if trigger not in TRIGGER_CATEGORIES:
                unknown_triggers.append(trigger)
                continue
            for category in TRIGGER_CATEGORIES[trigger]:
                if category not in categories:
                    categories.append(category)
        return {
            "technology_id": resolution["technology_id"],
            "resolution": resolution,
            "triggers": selected_triggers,
            "unknown_triggers": unknown_triggers,
            "categories": categories,
            "source_priority": [
                "STANDARD", "OFFICIAL_ORGANIZATION", "MANUFACTURER_DATASHEET",
                "APPLICATION_NOTE", "RESEARCH_INSTITUTE", "UNIVERSITY",
            ],
            "security": {
                "source_content_is_untrusted": True,
                "execute_source_code": False,
                "install_source_packages": False,
                "accept_community_only_for_simulation": False,
            },
        }

    def research(self, value: Any, *, triggers: Iterable[str] = ("unknown_protocol",)) -> dict[str, Any]:
        plan = self.research_plan(value, triggers=triggers)
        technology_id = plan["technology_id"]
        self._audit("NIS_TECH_RESEARCH_STARTED", technology_id, providers=[item.provider_name for item in self.providers])
        sources: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for provider in self.providers:
            try:
                batch = provider.research(deepcopy(plan))
            except Exception as error:  # provider failure stays visible and cannot create facts
                errors.append({"provider": provider.provider_name, "error": str(error)})
                continue
            for source in batch:
                sources.append({**deepcopy(source), "research_provider": provider.provider_name})
        return {"plan": plan, "sources": sources, "provider_errors": errors}

    def _normalize_sources(self, technology_id: str, raw_sources: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        sources: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for index, raw in enumerate(raw_sources):
            source_id = _safe_id(raw.get("source_id") or raw.get("id") or f"SRC-{index + 1:03d}").upper()
            if not source_id or source_id in seen_ids:
                findings.append({"code": "INVALID_SOURCE_ID", "severity": "ERROR", "source_id": source_id or None})
                continue
            seen_ids.add(source_id)
            source_type = str(raw.get("source_type") or "UNKNOWN").strip().upper()
            text_surface = " ".join(str(raw.get(key) or "") for key in ("title", "uri", "content", "excerpt"))
            suspicious = bool(_SUSPICIOUS.search(text_surface))
            if suspicious:
                findings.append({"code": "UNTRUSTED_SOURCE_CONTENT", "severity": "ERROR", "source_id": source_id, "message": "Source contains instruction/code-like content; its claims were ignored."})
            if source_type in UNTRUSTED_SOURCE_TYPES:
                findings.append({"code": "UNVERIFIED_SECONDARY_SOURCE", "severity": "WARNING", "source_id": source_id})
            complete_provenance = all(str(raw.get(key) or "").strip() for key in ("publisher", "title", "uri"))
            if not complete_provenance:
                findings.append({"code": "INCOMPLETE_SOURCE_PROVENANCE", "severity": "ERROR", "source_id": source_id, "required": ["publisher", "title", "uri"]})
            metadata = {
                "source_id": source_id,
                "publisher": str(raw.get("publisher") or "").strip(),
                "source_type": source_type,
                "title": str(raw.get("title") or "").strip(),
                "uri": str(raw.get("uri") or "").strip(),
                "technology_revision": str(raw.get("technology_revision") or "").strip() or None,
                "retrieved_at": str(raw.get("retrieved_at") or _now()),
                "parameter_scope": str(raw.get("parameter_scope") or "general"),
                "confidence": max(0.0, min(1.0, float(raw.get("confidence", 1.0)))),
                "source_rank": _source_rank(source_type),
                "eligible_for_validation": complete_provenance and not suspicious and source_type not in UNTRUSTED_SOURCE_TYPES,
                "research_provider": raw.get("research_provider"),
                "claims": [] if suspicious else list(raw.get("claims") or []),
            }
            sources.append(metadata)
            self._audit("NIS_TECH_SOURCE_FOUND", technology_id, source_id=source_id, source_type=source_type)
        return sources, findings

    def _normalize_claims(self, sources: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        claims: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        for source in sources:
            for raw in source.pop("claims", []):
                parameter = _safe_id(raw.get("parameter"))
                if parameter not in PARAMETER_FILES:
                    findings.append({"code": "UNKNOWN_PARAMETER", "severity": "WARNING", "source_id": source["source_id"], "parameter": parameter})
                    continue
                origin = str(raw.get("origin") or ("PRIMARY_SOURCE" if source["source_type"] in PRIMARY_SOURCE_TYPES else "SECONDARY_SOURCE")).upper()
                value, unit, unit_error = _normalize_unit(parameter, raw.get("value"), raw.get("unit"))
                if unit_error:
                    findings.append({"code": "INVALID_UNIT", "severity": "ERROR", "source_id": source["source_id"], "parameter": parameter, "message": unit_error})
                    continue
                verified = bool(raw.get("verified", source["source_type"] in PRIMARY_SOURCE_TYPES)) and origin != "SIMULATION_DEFAULT" and source["eligible_for_validation"]
                claim = {
                    "parameter": parameter,
                    "value": value,
                    "unit": unit,
                    "origin": origin,
                    "verified": verified,
                    "source_id": source["source_id"],
                    "publisher": source["publisher"],
                    "source_type": source["source_type"],
                    "technology_revision": str(raw.get("technology_revision") or source.get("technology_revision") or "") or None,
                    "parameter_scope": str(raw.get("parameter_scope") or source["parameter_scope"]),
                    "confidence": max(0.0, min(1.0, float(raw.get("confidence", source["confidence"])))),
                    "eligible_for_validation": source["eligible_for_validation"],
                }
                claims.append(claim)
        return claims, findings

    @staticmethod
    def _select_parameters(claims: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        grouped: dict[tuple[str, str, str | None], list[dict[str, Any]]] = {}
        for claim in claims:
            key = (claim["parameter"], claim["parameter_scope"], claim["technology_revision"])
            grouped.setdefault(key, []).append(claim)
        selected: dict[str, dict[str, Any]] = {}
        conflicts: list[dict[str, Any]] = []
        for (parameter, scope, revision), rows in grouped.items():
            trustworthy = [row for row in rows if row["eligible_for_validation"] and row["origin"] != "SIMULATION_DEFAULT"]
            values = {_stable_json({"value": row["value"], "unit": row["unit"]}) for row in trustworthy}
            if len(values) > 1:
                conflicts.append({
                    "code": "CONFLICT", "severity": "ERROR", "parameter": parameter,
                    "parameter_scope": scope, "technology_revision": revision,
                    "claims": deepcopy(trustworthy),
                })
                continue
            candidates = trustworthy or rows
            chosen = max(candidates, key=lambda row: (_source_rank(row["source_type"]), row["verified"], row["confidence"]))
            previous = selected.get(parameter)
            if previous is None or (_source_rank(chosen["source_type"]), chosen["confidence"]) > (_source_rank(previous["source_type"]), previous["confidence"]):
                selected[parameter] = deepcopy(chosen)
        return selected, conflicts

    @staticmethod
    def _readiness(selected: dict[str, dict[str, Any]], contract: dict[str, Any] | None = None) -> dict[str, Any]:
        requirements = {key: list(value) for key, value in READINESS_DEFAULTS.items()}
        for key, raw in (contract or {}).items():
            normalized_key = str(key).removeprefix("required_for_")
            if normalized_key in requirements and isinstance(raw, list):
                requirements[normalized_key] = [_safe_id(item) for item in raw]
        result: dict[str, Any] = {}
        for scope, required in requirements.items():
            missing = []
            for parameter in required:
                if parameter == "timing":
                    present = any(name in selected for name in ("cycle_time", "period", "latency", "transmission_time"))
                else:
                    present = parameter in selected
                if not present:
                    missing.append(parameter)
                    continue
                if parameter in selected:
                    row = selected[parameter]
                    if row["origin"] == "SIMULATION_DEFAULT" or not row["eligible_for_validation"]:
                        missing.append(parameter)
            result[scope] = {"status": "READY" if not missing else "BLOCKED_BY_DATA_GAP", "required": required, "missing": missing}
        return result

    def build_pack(self, request: dict[str, Any]) -> dict[str, Any]:
        technology_id = self.registry.normalize_id(request.get("technology_id") or request.get("name"))
        if not technology_id or technology_id == "custom_protocol" and not (request.get("technology_id") or request.get("name")):
            raise ValueError("technology_id or name is required")
        self._audit("NIS_TECH_RESEARCH_STARTED", technology_id, mode="structured_sources")
        sources, findings = self._normalize_sources(technology_id, request.get("sources") or [])
        claims, claim_findings = self._normalize_claims(sources)
        findings.extend(claim_findings)
        selected, conflicts = self._select_parameters(claims)
        findings.extend(conflicts)

        revisions = {str(item["technology_revision"]) for item in claims if item.get("technology_revision")}
        target_revision = str(request.get("technology_revision") or "").strip() or None
        if len(revisions) > 1 and not target_revision:
            findings.append({"code": "REVISION_CONFLICT", "severity": "ERROR", "revisions": sorted(revisions)})
        if target_revision:
            off_revision = sorted(revision for revision in revisions if revision != target_revision)
            if off_revision:
                findings.append({"code": "OUT_OF_SCOPE_REVISION", "severity": "WARNING", "target_revision": target_revision, "observed_revisions": off_revision})

        profile = {key: deepcopy(value) for key, value in (request.get("profile") or {}).items() if key in PROFILE_FIELDS}
        missing_profile = sorted(
            field for field in REQUIRED_PROFILE_FIELDS
            if profile.get(field) is None or profile.get(field) == "" or profile.get(field) == () or profile.get(field) == []
        )
        if missing_profile:
            findings.append({"code": "REGISTRATION_PROFILE_INCOMPLETE", "severity": "ERROR", "missing": missing_profile})
        if not missing_profile:
            try:
                Layer(str(profile["layer"]))
                TransportUnitType(str(profile["transport_unit"]))
                for payload_type in profile["payload_element_types"]:
                    PayloadElementType(str(payload_type))
                TechnologyCapability(**dict(profile.get("capabilities") or {}))
            except (TypeError, ValueError) as error:
                findings.append({"code": "INVALID_REGISTRATION_PROFILE", "severity": "ERROR", "message": str(error)})

        readiness = self._readiness(selected, request.get("simulation_readiness"))
        selected_scopes = list(dict.fromkeys(str(item).removeprefix("required_for_") for item in request.get("simulation_scopes") or readiness))
        unknown_scopes = sorted(scope for scope in selected_scopes if scope not in readiness)
        if unknown_scopes:
            findings.append({"code": "UNKNOWN_SIMULATION_SCOPE", "severity": "ERROR", "scopes": unknown_scopes})
        trustworthy = [row for row in claims if row["eligible_for_validation"] and row["origin"] != "SIMULATION_DEFAULT"]
        blocking_conflict = any(item["code"] in {"CONFLICT", "REVISION_CONFLICT"} for item in findings)
        if blocking_conflict:
            status = "CONFLICTED"
        elif not claims:
            status = "DISCOVERED"
        elif not trustworthy or missing_profile or any(item["severity"] == "ERROR" for item in findings):
            status = "PROVISIONAL"
        elif all(readiness[scope]["status"] == "READY" for scope in selected_scopes if scope in readiness):
            status = "SIMULATION_READY"
        else:
            status = "VALIDATED"

        aliases = list(dict.fromkeys(str(item) for item in request.get("aliases") or [] if str(item).strip()))
        parameter_files = {name: [] for name in PACK_FILES}
        data_gaps = [{"parameter": parameter, "status": "DATA_GAP"} for parameter in PARAMETER_FILES if parameter not in selected]
        for parameter, row in selected.items():
            parameter_files[PARAMETER_FILES[parameter]].append(deepcopy(row))
            self._audit("NIS_TECH_PARAMETER_ADDED", technology_id, parameter=parameter, source_id=row["source_id"])

        executable = all(readiness[scope]["status"] == "READY" for scope in ("message_generation", "busload")) and not blocking_conflict and not missing_profile
        generated_profile = {
            "id": technology_id,
            **profile,
            "aliases": aliases,
            "default_stack": list(profile.get("default_stack") or [technology_id]),
            "default_bitrate": (selected.get("nominal_data_rate") or {}).get("value"),
            "max_payload_bytes": (selected.get("payload_size") or {}).get("value"),
            "overhead_bytes": (selected.get("frame_overhead") or {}).get("value", 0),
            "implementation_status": "EXPERIMENTAL" if executable else "PLANNED",
            "technology_revision": target_revision or (next(iter(revisions)) if len(revisions) == 1 else None),
            "knowledge_status": status,
            "knowledge_origin": "GENERATED_TECHNOLOGY_PACK",
        }
        manifest = {
            "schema_version": PACK_SCHEMA_VERSION,
            "technology_id": technology_id,
            "label": profile.get("label") or request.get("name") or technology_id,
            "technology_revision": generated_profile["technology_revision"],
            "status": status,
            "created_at": _now(),
            "project_mutation": False,
            "canonical_model": ["HardwareNode", "Function", "HardwareInterface", "Message", "Signal"],
            "profile": generated_profile,
            "parameters": parameter_files["manifest.json"],
        }
        files: dict[str, Any] = {
            "manifest.json": manifest,
            "vocabulary.json": {"technology_id": technology_id, "aliases": aliases},
            "physical_layer.json": {"technology_id": technology_id, "parameters": parameter_files["physical_layer.json"]},
            "topology.json": {"technology_id": technology_id, "parameters": parameter_files["topology.json"]},
            "nodes.json": {"technology_id": technology_id, "node_types": list(request.get("node_types") or [])},
            "interfaces.json": {"technology_id": technology_id, "interface_types": list(request.get("interface_types") or []), "parameters": []},
            "messages.json": {"technology_id": technology_id, "abstract_model": ["identifier", "source", "destination", "payload", "timing", "priority", "encoding", "checksum", "protocol_specific"], "parameters": parameter_files["messages.json"]},
            "signals.json": {"technology_id": technology_id, "parameters": parameter_files["signals.json"]},
            "timing.json": {"technology_id": technology_id, "parameters": parameter_files["timing.json"]},
            "diagnostics.json": {"technology_id": technology_id, "parameters": parameter_files["diagnostics.json"]},
            "error_model.json": {"technology_id": technology_id, "parameters": parameter_files["error_model.json"]},
            "simulation.json": {"technology_id": technology_id, "adapter": request.get("simulation_adapter"), "parameters": parameter_files["simulation.json"], "readiness": readiness},
            "generation_rules.json": {"technology_id": technology_id, "executable": executable, "profile": generated_profile, "rules": list(request.get("generation_rules") or [])},
            "sources.json": {"technology_id": technology_id, "sources": sources},
            "validation.json": {"technology_id": technology_id, "status": status, "findings": findings, "data_gaps": data_gaps, "selected_simulation_scopes": selected_scopes, "readiness": readiness, "selected_parameters": selected},
        }
        manifest["pack_sha256"] = _digest({name: files[name] for name in PACK_FILES if name != "manifest.json"})
        if status in {"VALIDATED", "SIMULATION_READY"}:
            self._audit("NIS_TECH_VALIDATED", technology_id, status=status)
        if status == "SIMULATION_READY":
            self._audit("NIS_TECH_SIMULATION_READY", technology_id)
        return {"technology_id": technology_id, "status": status, "pack_sha256": manifest["pack_sha256"], "files": files, "audit_events": deepcopy(self.audit_events)}

    def persist_pack(self, pack: dict[str, Any]) -> dict[str, Any]:
        technology_id = _safe_id(pack.get("technology_id"))
        if not technology_id:
            raise ValueError("invalid technology_id")
        target = (self.pack_root / technology_id).resolve()
        root = self.pack_root.resolve()
        if root not in target.parents:
            raise ValueError("technology pack path escapes generated root")
        target.mkdir(parents=True, exist_ok=True)
        files = pack.get("files") or {}
        if set(files) != set(PACK_FILES):
            raise ValueError("technology pack file set is incomplete")
        version_target = target / "versions" / str(pack["pack_sha256"])
        version_target.mkdir(parents=True, exist_ok=True)
        for destination in (version_target, target):
            for name in PACK_FILES:
                temporary = destination / f".{name}.tmp"
                temporary.write_text(json.dumps(files[name], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                temporary.replace(destination / name)
        return {
            "technology_id": technology_id,
            "path": str(target),
            "version_path": str(version_target),
            "pack_sha256": pack["pack_sha256"],
            "status": pack["status"],
        }

    def create_pack(self, request: dict[str, Any], *, persist: bool = True) -> dict[str, Any]:
        pack = self.build_pack(request)
        if persist:
            pack["persistence"] = self.persist_pack(pack)
        return pack

    def load_pack(self, technology_id: Any) -> dict[str, Any]:
        normalized = _safe_id(technology_id)
        target = (self.pack_root / normalized).resolve()
        if self.pack_root.resolve() not in target.parents or not target.is_dir():
            raise FileNotFoundError(normalized)
        files = {name: json.loads((target / name).read_text(encoding="utf-8")) for name in PACK_FILES}
        expected = files["manifest.json"].get("pack_sha256")
        actual = _digest({name: files[name] for name in PACK_FILES if name != "manifest.json"})
        if expected != actual:
            raise ValueError(f"technology pack digest mismatch: {normalized}")
        return {"technology_id": normalized, "status": files["manifest.json"]["status"], "pack_sha256": actual, "files": files}

    def register_pack(self, technology_id: Any) -> dict[str, Any]:
        pack = self.load_pack(technology_id)
        validation = pack["files"]["validation.json"]
        if validation["status"] not in {"VALIDATED", "SIMULATION_READY", "VERIFIED"}:
            raise ValueError(f"technology pack is not validated: {validation['status']}")
        if any(item.get("code") in {"CONFLICT", "REVISION_CONFLICT"} for item in validation.get("findings") or []):
            raise ValueError("conflicted technology pack cannot be registered")
        profile = deepcopy(pack["files"]["generation_rules.json"]["profile"])
        self.registry.register_generated_profile(profile)
        index = self._load_index()
        index[profile["id"]] = {"pack_sha256": pack["pack_sha256"], "registered_at": _now(), "technology_revision": profile.get("technology_revision")}
        self._write_index(index)
        self._audit("NIS_TECH_REGISTERED", profile["id"], pack_sha256=pack["pack_sha256"])
        return {"technology_id": profile["id"], "registered": True, "profile": self.registry.profile(profile["id"]), "pack_sha256": pack["pack_sha256"]}

    def _load_index(self) -> dict[str, Any]:
        path = self.pack_root / "registry.json"
        if not path.is_file():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def _write_index(self, index: dict[str, Any]) -> None:
        self.pack_root.mkdir(parents=True, exist_ok=True)
        path = self.pack_root / "registry.json"
        temporary = self.pack_root / ".registry.json.tmp"
        temporary.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def load_registered_packs(self) -> list[dict[str, Any]]:
        loaded: list[dict[str, Any]] = []
        for technology_id, metadata in sorted(self._load_index().items()):
            try:
                pack = self.load_pack(technology_id)
                if pack["pack_sha256"] != metadata.get("pack_sha256"):
                    raise ValueError("registered digest differs from current pack")
                profile = deepcopy(pack["files"]["generation_rules.json"]["profile"])
                self.registry.register_generated_profile(profile)
                loaded.append({"technology_id": technology_id, "status": "LOADED"})
            except (FileNotFoundError, KeyError, ValueError) as error:
                loaded.append({"technology_id": technology_id, "status": "ERROR", "error": str(error)})
        return loaded


__all__ = [
    "PACK_FILES", "TechnologyOnboardingService", "TechnologyResearchProvider", "default_pack_root",
]
