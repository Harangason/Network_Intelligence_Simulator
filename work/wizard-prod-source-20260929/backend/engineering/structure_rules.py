"""Deterministic structure suggestions shared by API and repository updates."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


SEMANTIC_ALIASES = {
    "adas": "driver_assistance",
    "actuator": "actuator",
    "aktor": "actuator",
    "capture": "acquisition",
    "erfassung": "acquisition",
    "fahrerassistenz": "driver_assistance",
    "front": "front",
    "driverassistance": "driver_assistance",
    "vorne": "front",
    "hinten": "rear",
    "left": "left",
    "links": "left",
    "communication": "communication",
    "kommunikation": "communication",
    "control": "control",
    "controller": "control",
    "regelung": "control",
    "steuerung": "control",
    "pressure": "pressure",
    "druck": "pressure",
    "rear": "rear",
    "rechts": "right",
    "right": "right",
    "sensor": "sensor",
    "temperature": "temperature",
    "temperatur": "temperature",
    "thermal": "temperature",
    "tire": "tire",
    "tyre": "tire",
    "reifen": "tire",
    "wheel": "wheel",
    "rad": "wheel",
}

SEMANTIC_NOISE = {
    "data",
    "ecu",
    "function",
    "funktion",
    "interface",
    "message",
    "nachricht",
    "signal",
}

SYSTEM_NAME_DUPLICATE_THRESHOLD = 0.86
INDUSTRY_SYSTEM_ALIASES = {
    "automotive": {
        "motion": "motorsteuerung",
        "antrieb": "motorsteuerung",
        "antriebs": "motorsteuerung",
        "motionantriebs": "motorsteuerung",
        "motor": "motorsteuerung",
        "motorsteuerung": "motorsteuerung",
        "getriebe": "getriebesteuerung",
        "getriebesteuerung": "getriebesteuerung",
        "lenkungs": "lenkung",
        "lenkung": "lenkung",
        "klima": "klimatisierung",
        "klimatisierung": "klimatisierung",
        "thermal": "thermomanagement",
        "thermomanagement": "thermomanagement",
    },
}
SYSTEM_NAME_PLACEHOLDERS = {
    "ecu",
    "ecus",
    "function",
    "functions",
    "funktion",
    "funktionen",
    "funktions",
    "funktions ecu",
    "funktions ecus",
}
HARDWARE_NAME_SUFFIX = re.compile(
    r"(?:[-_ ]?(?:ECU|Gateway|Sensor|Aktor|Aktuator|Actuator|Controller|Steuerger(?:ä|ae|a|�)t))+(?P<instance>[-_ ]\d+)?$",
    flags=re.IGNORECASE,
)


def normalize_hardware_name(value: Any) -> str:
    """Keep the hardware role in ``device_type`` instead of duplicating it in the name."""

    original = str(value or "").strip()
    normalized = HARDWARE_NAME_SUFFIX.sub(lambda match: match.group("instance") or "", original).strip("-_ ")
    return normalized or original


def is_placeholder_system_name(value: Any) -> bool:
    normalized = normalize_hardware_name(value).strip().casefold().replace("_", "-")
    normalized = re.sub(r"\s*-\s*", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized in SYSTEM_NAME_PLACEHOLDERS


def _name_tokens(value: Any) -> list[str]:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-ZÄÖÜ])", " ", str(value or ""))
    expanded = expanded.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    expanded = re.sub(r"\bdriver[\s_-]+assistance\b", "driverassistance", expanded)
    expanded = re.sub(r"\bfahrer[\s_-]+assistenz\b", "fahrerassistenz", expanded)
    result: list[str] = []
    for token in re.split(r"[^a-z0-9]+", expanded):
        if len(token) <= 2 or token in SEMANTIC_NOISE:
            continue
        if token in SEMANTIC_ALIASES:
            result.append(SEMANTIC_ALIASES[token])
            continue
        compound_parts = {
            canonical
            for source, canonical in SEMANTIC_ALIASES.items()
            if len(source) >= 4 and source in token
        }
        result.extend(sorted(compound_parts) if len(compound_parts) >= 2 else [token])
    return result


def _tokens(value: Any) -> set[str]:
    return set(_name_tokens(value))


def semantic_name_signature(value: Any, *, context: Any = None) -> tuple[str, ...]:
    """Return a stable semantic signature while removing the parent ECU context."""

    tokens = _name_tokens(value)
    context_tokens = set(_name_tokens(context))
    remaining = [token for token in tokens if token not in context_tokens]
    return tuple(sorted(set(remaining or tokens)))


def semantic_name_similarity(
    left: Any,
    right: Any,
    *,
    left_context: Any = None,
    right_context: Any = None,
) -> float:
    """Compare technical names after language, parent-name and casing normalization."""

    left_signature = semantic_name_signature(left, context=left_context)
    right_signature = semantic_name_signature(right, context=right_context)
    if left_signature == right_signature and left_signature:
        return 1.0
    left_set = set(left_signature)
    right_set = set(right_signature)
    if not left_set or not right_set:
        return 0.0
    overlap = len(left_set & right_set) / len(left_set | right_set)
    sequence = SequenceMatcher(None, " ".join(left_signature), " ".join(right_signature)).ratio()
    subset_bonus = 0.08 if left_set <= right_set or right_set <= left_set else 0.0
    return round(min(1.0, overlap * 0.68 + sequence * 0.24 + subset_bonus), 2)


def system_name_similarity(left: Any, right: Any) -> float:
    """Compare top-level system names, including controlled technical aliases."""

    left_name = str(left or "").strip().casefold()
    right_name = str(right or "").strip().casefold()
    if left_name and left_name == right_name:
        return 1.0
    return semantic_name_similarity(left, right)


def _industry_system_name(value: Any, domain: Any = None) -> str:
    normalized = normalize_hardware_name(value).lower()
    normalized = normalized.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    profile = re.sub(r"[^a-z0-9_]+", "", str(domain or "").strip().lower())
    return INDUSTRY_SYSTEM_ALIASES.get(profile, {}).get(compact, compact)


def is_canonical_system_name(value: Any, domain: Any = None) -> bool:
    """Return whether a controlled industry alias already uses its canonical spelling."""

    normalized = normalize_hardware_name(value).lower()
    normalized = normalized.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    profile = re.sub(r"[^a-z0-9_]+", "", str(domain or "").strip().lower())
    aliases = INDUSTRY_SYSTEM_ALIASES.get(profile, {})
    return bool(compact) and aliases.get(compact, compact) == compact


def equivalent_system_names(left: Any, right: Any, *, domain: Any = None) -> tuple[bool, float]:
    """Return whether two names denote the same system with conservative confidence."""

    left_industry_name = _industry_system_name(left, domain)
    right_industry_name = _industry_system_name(right, domain)
    if left_industry_name and left_industry_name == right_industry_name:
        return True, 1.0
    similarity = system_name_similarity(left, right)
    return similarity >= SYSTEM_NAME_DUPLICATE_THRESHOLD, similarity


def adapt_structure_name(source_name: str, source_parent_name: str, target_parent_name: str) -> str:
    """Adapt a copied object name to its target parent without inventing new semantics."""

    if source_parent_name:
        exact = re.compile(re.escape(source_parent_name), flags=re.IGNORECASE)
        if exact.search(source_name):
            return exact.sub(target_parent_name, source_name, count=1)
    source_stem = re.sub(r"(?:[-_ ]?(?:ECU|Gateway|Funktion|Function))+$", "", source_parent_name, flags=re.IGNORECASE).strip("-_ ")
    target_stem = re.sub(r"(?:[-_ ]?(?:ECU|Gateway|Funktion|Function))+$", "", target_parent_name, flags=re.IGNORECASE).strip("-_ ")
    if source_stem and target_stem:
        stem = re.compile(re.escape(source_stem), flags=re.IGNORECASE)
        if stem.search(source_name):
            return stem.sub(target_stem, source_name, count=1)
    return source_name


def infer_device_type(name: str, current: str | None = None) -> str:
    """Infer a canonical device type without replacing a stronger known type."""

    if current and current not in {"GenericDevice", "CustomDevice"}:
        return current
    value = name.lower()
    if "gateway" in value:
        return "Gateway"
    if "sensor" in value:
        return "SensorController"
    if any(token in value for token in ("aktor", "aktuator", "actuator", "ventil", "valve")):
        return "ActuatorController"
    if any(token in value for token in ("sensor", "geber", "mess")):
        return "SensorController"
    if "ecu" in value or "steuergeraet" in value or "steuergerät" in value:
        return "ECU"
    return current or "GenericDevice"


def recommend_structure_name(
    child_type: str,
    child: dict[str, Any],
    parent: dict[str, Any],
) -> str:
    """Return a conservative editable name recommendation for one hierarchy edge."""

    current = str(child.get("name") or "").strip()
    parent_name = str(parent.get("name") or "").strip()
    stem = re.sub(
        r"(?:[-_ ]?(?:ECU|Gateway|Funktion|Function|Interface|Data|Message))+$",
        "",
        parent_name,
        flags=re.IGNORECASE,
    ).strip("-_ ") or parent_name
    if child_type == "Function":
        return f"{stem} Funktion"
    if child_type == "Interface":
        interface_type = str(child.get("interface_type") or "Interface").upper().replace(" ", "_")
        return f"{stem}_{interface_type}"
    if child_type == "Message":
        return f"{stem}Data"
    if child_type == "Signal":
        return str(child.get("display_name") or current or f"{stem}Signal")
    return current


def score_structure_parent(
    child: dict[str, Any],
    parent: dict[str, Any],
    *,
    current_parent_id: str | None = None,
    accepted_examples: int = 0,
    rejected_examples: int = 0,
) -> tuple[float, list[str]]:
    """Score a parent candidate using model context plus reviewed examples."""

    reasons: list[str] = []
    score = 0.42
    child_tokens = _tokens(child.get("name")) | _tokens(child.get("description"))
    parent_tokens = _tokens(parent.get("name")) | _tokens(parent.get("description"))
    overlap = child_tokens & parent_tokens
    if overlap:
        score += min(0.28, len(overlap) * 0.09)
        reasons.append(f"Namenskontext: {', '.join(sorted(overlap)[:3])}")
    if child.get("domain") and child.get("domain") == parent.get("domain"):
        score += 0.08
        reasons.append("gleiche Domäne")
    if current_parent_id and str(parent.get("id")) == current_parent_id:
        score += 0.12
        reasons.append("bestehende Zuordnung")
    if accepted_examples:
        score += min(0.16, accepted_examples * 0.04)
        reasons.append(f"{accepted_examples} bestätigte Lernbeispiele")
    if rejected_examples:
        score -= min(0.20, rejected_examples * 0.05)
        reasons.append(f"{rejected_examples} abgelehnte Lernbeispiele")
    if not reasons:
        reasons.append("technisch zulässige Hierarchiestufe")
    return round(max(0.05, min(0.98, score)), 2), reasons
