"""Intent, family, and semantic resolution for requirement expansion."""

from __future__ import annotations

from .text_utils import match_any


DOMAIN_KEYWORDS = {
    "Automotive": (r"\bvehicle\b", r"\bcar\b", r"\bautomotive\b", r"\bfahrzeug\b", r"\badas\b", r"\becu\b"),
    "Industrial": (r"\bindustrial\b", r"\banlage\b", r"\bplc\b", r"\bmaschine\b", r"\brobot\b", r"\bros\b"),
    "Rail": (r"\brail\b", r"\bzug\b", r"\bbahn\b", r"\btrain\b"),
    "Aerospace": (r"\baerospace\b", r"\bflug\b", r"\buav\b", r"\bdrone\b", r"\bdrohne\b"),
    "Energy": (r"\benergy\b", r"\bgrid\b", r"\bpower\b", r"\bnetz\b", r"\bumrichter\b"),
}


def choose_domain(text: str, domain: str | None) -> str:
    hint = str(domain or "automotive").strip().lower()
    explicit_domains = {
        "energy": "Energy",
        "rail": "Rail",
        "aerospace": "Aerospace",
        "industrial": "Industrial",
        "robotics": "Industrial",
        "generic": "Generic",
        "automotive": "Automotive",
        "industrial_automation": "Industrial",
        "embedded_systems": "Generic",
        "aerospace_defense": "Aerospace",
        "robotics_ros": "Industrial",
        "generic_networking": "Generic",
    }
    if hint in explicit_domains:
        return explicit_domains[hint]

    for resolved_domain, patterns in DOMAIN_KEYWORDS.items():
        if match_any(text, *patterns):
            return resolved_domain

    if match_any(text, r"\bkameras?\b", r"\bcameras?\b", r"\bumfeld\b", r"\bsicht\b"):
        return "Automotive"
    if match_any(text, r"\btemperatur\b", r"\btemperature\b", r"\bdruck\b", r"\bpressure\b", r"\bmotor\b"):
        return "Automotive"
    if match_any(text, r"\bposition\b", r"\bros\b", r"\broboter\b"):
        return "Industrial"
    return "Generic"


def sensor_family(text: str) -> str:
    if match_any(text, r"\bkameras?\b", r"\bcameras?\b", r"\bvision\b"):
        return "camera"
    if match_any(text, r"\blidar\b", r"\blaser\b"):
        return "lidar"
    if match_any(text, r"\bradar\b"):
        return "radar"
    if match_any(text, r"\bultraschall\b", r"\bultrasonic\b", r"\bsonar\b"):
        return "ultrasonic"
    if match_any(text, r"\btemperatur\b", r"\btemperature\b", r"\bmotor\b"):
        return "temperature"
    if match_any(text, r"\bdruck\b", r"\bpressure\b"):
        return "pressure"
    if match_any(text, r"\bposition\b", r"\bros\b", r"\blokalisierung\b", r"\bgps\b", r"\btracking\b"):
        return "position"
    return "generic"


def resolve_safety_context(text: str, domain: str) -> dict[str, object]:
    """Resolve safety relevance without silently approving ambiguous cases."""
    safety_relevant = match_any(
        text,
        r"\bsafety\b",
        r"\bsicherheits",
        r"\basil\b",
        r"\bfail[- ]?safe\b",
        r"\bnotbrems",
        r"\bcollision\b",
        r"\bkollision\b",
    )
    explicitly_non_safety = match_any(text, r"\bnon[- ]?safety\b", r"\bnicht sicherheitsrelevant\b")
    if safety_relevant:
        level = "safety_relevant"
        status = "CONFIRMED"
    elif explicitly_non_safety:
        level = "non_safety"
        status = "CONFIRMED"
    elif domain in {"Automotive", "Aerospace", "Rail"}:
        level = "safety_unknown"
        status = "REQUIRED_REVIEW"
    else:
        level = "not_classified"
        status = "OPTIONAL"
    return {
        "level": level,
        "status": status,
        "requires_confirmation": status == "REQUIRED_REVIEW",
    }


def resolve_architecture(text: str) -> dict[str, object]:
    """Resolve likely network architecture from explicit cues."""
    if match_any(text, r"\beth(?:ernet)?\b", r"\bautomotive ethernet\b", r"\b100base", r"\b1000base"):
        technology = "ETHERNET"
        source = "explicit"
    elif match_any(text, r"\bcan[- ]?fd\b"):
        technology = "CAN_FD"
        source = "explicit"
    elif match_any(text, r"\bcan\b"):
        technology = "CAN"
        source = "explicit"
    else:
        technology = "AUTO_SELECT"
        source = "derived_from_capacity"
    return {"technology": technology, "source": source}
