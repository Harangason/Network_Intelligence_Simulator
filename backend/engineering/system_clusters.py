"""System ownership stays independent of gateway-direct physical routing."""

import re
from typing import Any

from .structure_rules import normalize_hardware_name


FAMILIES = (
    (("airbag", "crash", "impact", "seatbelt", "gurt"), ("airbag", "rueckhalt")),
    (("brake", "brems", "wheelspeed"), ("bremsregelung",)),
    (("damper", "daempfer"), ("daempferregelung",)),
    (("suspension", "wheelload", "verticalacceleration"), ("fahrwerk",)),
    (("steering", "wheelangle", "lenk"), ("lenkung",)),
    (("yaw", "pitch", "rollrate", "lateralacceleration", "longitudinalacceleration"), ("stabilitaetsregelung",)),
    (("cabintemperature", "ambienttemperature", "refrigerant", "innenraum", "klima"), ("klima", "klimatisierung")),
    (("battery", "batterie", "cellvoltage"), ("batteriemanagement",)),
    (("transmission", "clutch", "gearselector"), ("getriebesteuerung",)),
    (("exhaust", "egrvalve", "urea"), ("abgasnachbehandlung",)),
    (("motorspeed", "motorcurrent"), ("elektromotorsteuerung",)),
    (("engine", "boostpressure", "accelerator", "throttle", "turbo"), ("motorsteuerung",)),
    (("radar",), ("radarverarbeitung",)),
    (("camera", "kamera"), ("kameraverarbeitung",)),
    (("fuel", "kraftstoff"), ("kraftstoffsystem",)),
    (("tire", "reifen"), ("reifendruckkontrolle",)),
    (("wheelacceleration", "wheeltorque"), ("stabilitaetsregelung", "fahrdynamik")),
    (("inverter", "dclink"), ("invertersteuerung",)),
    (("alternator", "accessorycurrent", "lowvoltage"), ("energieversorgung",)),
    (("rain", "washerfluid"), ("wischersteuerung", "bodycontrol")),
    (("ambientlight",), ("aussenlicht", "bodycontrol")),
    (("coolant", "oiltemperature", "intakeairtemperature", "oillevel", "temperature", "temperatur"), ("thermal", "thermomanagement", "klimatisierung")),
)


def _key(value: str) -> str:
    value = normalize_hardware_name(value).lower()
    for source, target in (("\u00e4", "ae"), ("\u00f6", "oe"), ("\u00fc", "ue"), ("\u00df", "ss")):
        value = value.replace(source, target)
    return re.sub(r"[^a-z0-9]", "", value)


def system_owners(hardware: list[dict[str, Any]], topology: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Prefer explicit ownership; unresolved or ambiguous names stay separate."""
    by_id = {str(item["id"]): item for item in hardware}
    processors = {key: item for key, item in by_id.items() if item.get("device_type") == "ECU"}
    processor_keys: dict[str, list[str]] = {}
    for processor_id, processor in processors.items():
        processor_keys.setdefault(_key(str(processor.get("name") or "")), []).append(processor_id)
    processor_owner: dict[str, str] = {}
    for candidates in processor_keys.values():
        canonical = sorted(
            candidates,
            key=lambda item: (
                len(normalize_hardware_name(str(processors[item].get("name") or ""))),
                len(str(processors[item].get("name") or "")),
                item,
            ),
        )[0]
        for candidate in candidates:
            processor_owner[candidate] = canonical
    canonical_processors = {
        key: item
        for key, item in processors.items()
        if processor_owner.get(key, key) == key
    }
    nodes = {str(item.get("id")): item for item in topology.get("nodes", [])}
    explicit = {}
    for node in nodes.values():
        owner = str(node.get("systemOwnerId") or "")
        owner_id = str(nodes.get(owner, {}).get("engineeringId") or owner)
        owner_id = processor_owner.get(owner_id, owner_id)
        if owner_id in processors:
            explicit[str(node.get("engineeringId") or node["id"])] = (owner_id, node.get("systemOwnerSource") or "explicit")
    owners = {}
    for key, item in by_id.items():
        explicit_owner, basis = explicit.get(key, ("", "explicit"))
        owner = str((item.get("identity") or {}).get("system_owner_id") or explicit_owner)
        owner = processor_owner.get(owner, owner)
        if key in processors:
            owner = processor_owner.get(key, key)
            basis = "explicit" if owner == key else "inferred"
        elif owner not in processors:
            name = _key(str(item.get("name") or ""))
            candidates = []
            for processor_id, processor in canonical_processors.items():
                processor_name = _key(str(processor.get("name") or ""))
                score = len(processor_name) + 2000 if len(processor_name) > 3 and name.startswith(processor_name) else 0
                for index, (sources, targets) in enumerate(FAMILIES):
                    specificity = max((len(token) for token in sources if token in name), default=0)
                    if specificity:
                        for target_index, target in enumerate(targets):
                            if target in processor_name:
                                score = max(score, (1200 if target == processor_name else 800) + specificity * 20 - target_index * 80)
                if score:
                    candidates.append((score, processor_id))
            candidates.sort(reverse=True)
            owner = candidates[0][1] if candidates and (len(candidates) == 1 or candidates[0][0] > candidates[1][0]) else key
            basis = "inferred" if owner != key else "unassigned"
        owners[key] = {"id": owner, "name": normalize_hardware_name(str(by_id.get(owner, item).get("name") or owner)), "basis": basis}
    return owners
