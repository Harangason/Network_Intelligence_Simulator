"""Spezialisierte Generatoren und Validatoren fuer Engineering-Workloads."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .registry import WorkloadHandler

SIGNAL_REQUIRED_FIELDS = (
    "id",
    "name",
    "display_name",
    "description",
    "category",
    "datatype",
    "unit",
    "minimum",
    "maximum",
    "resolution",
    "default_value",
    "invalid_value",
    "cycle_time",
    "producer",
    "consumers",
    "source",
    "generated_by",
    "confidence",
    "review_state",
)


def _signal(
    name: str,
    description: str,
    unit: str,
    minimum: float,
    maximum: float,
    resolution: float = 1.0,
    datatype: str = "unsigned",
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "unit": unit,
        "minimum": minimum,
        "maximum": maximum,
        "resolution": resolution,
        "datatype": datatype,
    }


THERMAL_SIGNAL_CATALOG = (
    _signal("ThermalIsttemperatur", "Gefilterte aktuelle Temperatur der Thermal-ECU.", "degC", -40, 180, 0.1, "signed"),
    _signal("ThermalSolltemperatur", "Aktiver Temperatursollwert der Thermal-Regelung.", "degC", -40, 180, 0.1, "signed"),
    _signal("Kuehlmitteltemperatur", "Temperatur des Kuehlmittelkreises.", "degC", -40, 180, 0.1, "signed"),
    _signal("Motortemperatur", "Thermischer Zustand des Motors.", "degC", -40, 220, 0.1, "signed"),
    _signal("Invertertemperatur", "Thermischer Zustand des Inverters.", "degC", -40, 180, 0.1, "signed"),
    _signal("Temperaturgradient", "Zeitliche Aenderung der gemessenen Temperatur.", "degC/s", -100, 100, 0.1, "signed"),
    _signal("Heizanforderung", "Normierte Anforderung an die Heizleistung.", "%", 0, 100, 0.1),
    _signal("Kuehlanforderung", "Normierte Anforderung an die Kuehlleistung.", "%", 0, 100, 0.1),
    _signal("ThermischerStatus", "Kodierter Betriebszustand der Thermal-Regelung.", "code", 0, 15),
    _signal("TemperaturSensorQualitaet", "Qualitaetswert der Temperaturerfassung.", "%", 0, 100, 0.1),
)

MOTION_SIGNAL_CATALOG = (
    _signal("MotionFahrzeuggeschwindigkeit", "Berechnete Fahrzeuggeschwindigkeit.", "km/h", 0, 300, 0.01),
    _signal("MotionMotordrehzahl", "Aktuelle Motordrehzahl der Motion-ECU.", "rpm", 0, 20000),
    _signal("RaddrehzahlVorneLinks", "Raddrehzahl vorne links.", "rpm", 0, 3000),
    _signal("RaddrehzahlVorneRechts", "Raddrehzahl vorne rechts.", "rpm", 0, 3000),
    _signal("RaddrehzahlHintenLinks", "Raddrehzahl hinten links.", "rpm", 0, 3000),
    _signal("RaddrehzahlHintenRechts", "Raddrehzahl hinten rechts.", "rpm", 0, 3000),
    _signal("Laengsbeschleunigung", "Laengsbeschleunigung des Fahrzeugs.", "m/s2", -30, 30, 0.01, "signed"),
    _signal("Querbeschleunigung", "Querbeschleunigung des Fahrzeugs.", "m/s2", -30, 30, 0.01, "signed"),
    _signal("Gierrate", "Drehgeschwindigkeit um die Hochachse.", "deg/s", -250, 250, 0.01, "signed"),
    _signal("Lenkwinkel", "Aktueller Lenkwinkel.", "deg", -720, 720, 0.1, "signed"),
    _signal("Fahrpedalstellung", "Normierte Fahrpedalstellung.", "%", 0, 100, 0.1),
    _signal("Bremsdruck", "Aktueller hydraulischer Bremsdruck.", "bar", 0, 250, 0.1),
    _signal("MotionSollmoment", "Angefordertes Antriebsmoment.", "Nm", -1000, 1000, 0.1, "signed"),
    _signal("MotionIstmoment", "Ermitteltes aktuelles Antriebsmoment.", "Nm", -1000, 1000, 0.1, "signed"),
    _signal("MotionMomentenlimit", "Aktives Momentenlimit.", "Nm", 0, 1000, 0.1),
    _signal("MotionMotorstrom", "Motorstrom im Motion-Regelkreis.", "A", -1000, 1000, 0.1, "signed"),
    _signal("Zwischenkreisspannung", "Spannung des elektrischen Zwischenkreises.", "V", 0, 1000, 0.1),
    _signal("MotionLeistungsaufnahme", "Elektrische Leistungsaufnahme des Antriebs.", "kW", -500, 500, 0.1, "signed"),
    _signal("MotionFahrmodus", "Kodierter aktiver Fahrmodus.", "code", 0, 15),
    _signal("Traktionsstatus", "Kodierter Zustand der Traktionsregelung.", "code", 0, 15),
    _signal("RadschlupfVorneLinks", "Berechneter Radschlupf vorne links.", "%", -100, 100, 0.01, "signed"),
    _signal("RadschlupfVorneRechts", "Berechneter Radschlupf vorne rechts.", "%", -100, 100, 0.01, "signed"),
    _signal("RadschlupfHintenLinks", "Berechneter Radschlupf hinten links.", "%", -100, 100, 0.01, "signed"),
    _signal("RadschlupfHintenRechts", "Berechneter Radschlupf hinten rechts.", "%", -100, 100, 0.01, "signed"),
    _signal("MotionFehlercode", "Aggregierter Diagnosecode der Motion-ECU.", "code", 0, 65535),
)

SIGNAL_CATALOGS = {
    "thermal": THERMAL_SIGNAL_CATALOG,
    "motion": MOTION_SIGNAL_CATALOG,
}

SIGNAL_ALIAS_GROUPS = (
    ("motordrehzahl", "enginespeed", "motorrpm", "rotationalspeed"),
    ("fahrzeuggeschwindigkeit", "vehiclespeed", "speed"),
    ("isttemperatur", "temperaturecurrent", "actualtemperature"),
    ("solltemperatur", "temperaturetarget", "targettemperature"),
    ("laengsbeschleunigung", "longitudinalacceleration"),
    ("querbeschleunigung", "lateralacceleration"),
)


def normalized_name(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "", text)


def semantic_alias_key(value: Any) -> str:
    key = normalized_name(value)
    for index, aliases in enumerate(SIGNAL_ALIAS_GROUPS):
        if any(alias in key for alias in aliases):
            return f"alias-group-{index}"
    return key


def _default_value(minimum: float, maximum: float) -> float:
    if minimum <= 0 <= maximum:
        return 0
    return minimum


def _semantic_type_for_signal(name: str, unit: str, minimum: float, maximum: float) -> str:
    key = f"{name} {unit}".lower()
    if minimum == 0 and maximum == 1 and any(token in key for token in ("status", "flag", "aktiv", "enable", "boolean")):
        return "BOOLEAN"
    if any(token in key for token in ("status", "state", "mode", "zustand", "diagnose", "fehler", "code")) or unit == "code":
        return "STATE"
    return "NUMERIC"


def _state_value_domain(name: str) -> dict[str, Any]:
    if "gateway" in name.lower():
        enum_values = {"OK": 0, "DEGRADED": 1, "ROUTING_LIMITED": 2, "ERROR": 3}
    else:
        enum_values = {"OK": 0, "WARNING": 1, "ERROR": 2, "NOT_AVAILABLE": 3}
    return {
        "enum_values": enum_values,
        "allowed_values": list(enum_values),
        "reserved_values": [4, 5, 6, 7],
        "invalid_values": [15],
        "default_value": "OK",
        "resolution": 1,
    }


def _canonical_signal_layers(
    *,
    name: str,
    description: str,
    category: str,
    datatype: str,
    unit: str,
    minimum: float,
    maximum: float,
    resolution: float,
    producer: str,
    consumers: list[str],
    cycle_time: float,
    length_bits: int,
    start_bit: int,
) -> dict[str, Any]:
    semantic_type = _semantic_type_for_signal(name, unit, minimum, maximum)
    if semantic_type == "BOOLEAN":
        value_domain = {
            "minimum": 0,
            "maximum": 1,
            "resolution": 1,
            "allowed_values": [False, True],
            "enum_values": {"FALSE": 0, "TRUE": 1},
            "invalid_values": [],
            "reserved_values": [],
            "default_value": False,
        }
    elif semantic_type == "STATE":
        value_domain = _state_value_domain(name)
    else:
        value_domain = {
            "minimum": minimum,
            "maximum": maximum,
            "resolution": resolution,
            "allowed_values": [],
            "enum_values": {},
            "invalid_values": [maximum + resolution],
            "reserved_values": [],
            "default_value": _default_value(minimum, maximum),
        }
    return {
        "semantic": {
            "semantic_type": semantic_type,
            "quantity": name,
            "category": category,
            "meaning": description,
            "unit": unit if semantic_type == "NUMERIC" else "not_applicable",
            "generated_by": "engineering-workload-signal-generator-v2",
            "assumptions": [] if semantic_type == "NUMERIC" else ["Diskretes Signal wurde als explizite Value-Domain modelliert."],
        },
        "data": value_domain,
        "configuration": {
            "raw_datatype": datatype,
            "bit_length": length_bits,
            "signed": datatype == "signed",
            "factor": resolution,
            "offset": 0,
            "endianness": "little_endian",
            "start_bit": start_bit,
            "encoding_type": "linear" if semantic_type == "NUMERIC" else "coded",
            "coding_rule": "MEANING_VALUE_DOMAIN_ENCODING_PACKING_TRANSPORT",
        },
        "communication": {
            "cycle_time_ms": cycle_time,
            "producer": producer,
            "consumers": consumers,
            "update_type": "cyclic_fast" if cycle_time <= 20 else "cyclic",
        },
        "quality": {
            "confidence": 0.95 if semantic_type == "NUMERIC" else 0.88,
            "semantic_complete": True,
            "value_domain_complete": True,
            "encoding_complete": True,
            "packing_complete": True,
            "validation_status": "proposal",
        },
        "protocol_bindings": [],
    }


def _signal_definition(
    workload: dict[str, Any],
    package: dict[str, Any],
    candidate: dict[str, Any],
    context: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    minimum = float(candidate["minimum"])
    maximum = float(candidate["maximum"])
    resolution = float(candidate["resolution"])
    message = context["message"]
    producer = str(context["node"].get("name") or package["category"])
    cycle_time = float(message.get("cycle_ms") or 10)
    identifier = f"{workload['workload_id']}:{normalized_name(candidate['name'])}"
    start_bit = index * 16
    layers = _canonical_signal_layers(
        name=str(candidate["name"]),
        description=str(candidate["description"]),
        category=str(package["category"]),
        datatype=str(candidate["datatype"]),
        unit=str(candidate["unit"]),
        minimum=minimum,
        maximum=maximum,
        resolution=resolution,
        producer=producer,
        consumers=list(context.get("consumers") or []),
        cycle_time=cycle_time,
        length_bits=16,
        start_bit=start_bit,
    )
    return {
        "id": identifier,
        "object_type": "Signal",
        "resource": "signals",
        "name": candidate["name"],
        "display_name": candidate["name"],
        "description": candidate["description"],
        "category": package["category"],
        "datatype": candidate["datatype"],
        "data_type": candidate["datatype"],
        "unit": candidate["unit"],
        "minimum": minimum,
        "min_value": minimum,
        "maximum": maximum,
        "max_value": maximum,
        "resolution": resolution,
        "factor": resolution,
        "offset_value": 0,
        "default_value": _default_value(minimum, maximum),
        "invalid_value": maximum + resolution,
        "cycle_time": cycle_time,
        "producer": producer,
        "consumers": list(context.get("consumers") or []),
        "source": "ai_generated",
        "generated_by": "engineering-workload-signal-generator-v2",
        "confidence": 0.95,
        "review_state": "unreviewed",
        "approval_state": "pending",
        "domain": str(workload.get("domain") or "automotive"),
        "message_id": str(message["id"]),
        "start_bit": start_bit,
        "length_bits": 16,
        "byte_order": "little_endian",
        **layers,
    }


def _existing_signal_definition(
    workload: dict[str, Any],
    package: dict[str, Any],
    candidate: dict[str, Any],
    existing: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    minimum = existing.get("min_value") if existing.get("min_value") is not None else candidate["minimum"]
    maximum = existing.get("max_value") if existing.get("max_value") is not None else candidate["maximum"]
    resolution = existing.get("factor") if existing.get("factor") not in (None, 0) else candidate["resolution"]
    communication = dict(existing.get("communication") or {})
    semantic = dict(existing.get("semantic") or {})
    producer = str(communication.get("producer") or semantic.get("owner") or context["node"].get("name") or package["category"])
    return {
        **_signal_definition(workload, package, candidate, context, 0),
        "id": str(existing["id"]),
        "name": str(existing.get("name") or candidate["name"]),
        "display_name": str(existing.get("display_name") or existing.get("name") or candidate["name"]),
        "description": str(existing.get("description") or candidate["description"]),
        "datatype": str(existing.get("data_type") or candidate["datatype"]),
        "data_type": str(existing.get("data_type") or candidate["datatype"]),
        "unit": existing.get("unit") or candidate["unit"] or "not_applicable",
        "minimum": float(minimum),
        "min_value": float(minimum),
        "maximum": float(maximum),
        "max_value": float(maximum),
        "resolution": float(resolution),
        "factor": float(resolution),
        "default_value": (existing.get("data") or {}).get("default_value", _default_value(float(minimum), float(maximum))),
        "invalid_value": (existing.get("data") or {}).get("invalid_value", float(maximum) + float(resolution)),
        "cycle_time": float(communication.get("cycle_time_ms") or context["message"].get("cycle_ms") or 10),
        "producer": producer,
        "consumers": list(communication.get("consumers") or []),
        "source": str(existing.get("source") or "manual"),
        "generated_by": str((existing.get("provenance") or {}).get("model") or "existing-engineering-model"),
        "confidence": float(existing.get("confidence") if existing.get("confidence") is not None else 1.0),
        "review_state": str(existing.get("review_state") or "reviewed"),
        "approval_state": str(existing.get("approval_state") or "approved"),
    }


def validate_signal_definition(definition: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for field in SIGNAL_REQUIRED_FIELDS:
        value = definition.get(field)
        if value is None or value == "" or (field == "consumers" and not isinstance(value, list)):
            findings.append({"code": "MISSING_FIELD", "field": field, "severity": "ERROR"})
    minimum = definition.get("minimum")
    maximum = definition.get("maximum")
    resolution = definition.get("resolution")
    if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)) and minimum > maximum:
        findings.append({"code": "INVALID_RANGE", "field": "minimum", "severity": "ERROR"})
    if not isinstance(resolution, (int, float)) or resolution <= 0:
        findings.append({"code": "INVALID_RESOLUTION", "field": "resolution", "severity": "ERROR"})
    default = definition.get("default_value")
    if (
        isinstance(default, (int, float))
        and isinstance(minimum, (int, float))
        and isinstance(maximum, (int, float))
        and not minimum <= default <= maximum
    ):
        findings.append({"code": "DEFAULT_OUT_OF_RANGE", "field": "default_value", "severity": "ERROR"})
    if definition.get("datatype") not in {"signed", "unsigned", "float", "boolean", "enum"}:
        findings.append({"code": "INVALID_DATATYPE", "field": "datatype", "severity": "ERROR"})
    confidence = definition.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        findings.append({"code": "INVALID_CONFIDENCE", "field": "confidence", "severity": "ERROR"})
    return findings


class SignalGenerationWorkloadHandler(WorkloadHandler):
    workload_type = "SIGNAL_GENERATION"

    def plan(self, orchestrator, workload: dict[str, Any], packages: list[dict[str, Any]]) -> None:
        for package in packages:
            orchestrator.unblock_package(package)
            category = str(package["category"]).lower()
            if category not in SIGNAL_CATALOGS:
                orchestrator.block_package(
                    package,
                    "UNSUPPORTED_SIGNAL_CATEGORY",
                    f"Fuer {category!r} ist kein fachlich belastbarer Signalgenerator registriert.",
                )
                continue
            if int(package["requested_count"]) > len(SIGNAL_CATALOGS[category]):
                orchestrator.block_package(
                    package,
                    "INSUFFICIENT_DOMAIN_KNOWLEDGE",
                    f"Der Katalog enthaelt {len(SIGNAL_CATALOGS[category])} belastbare Signale, angefordert sind {package['requested_count']}.",
                )
                continue
            context = orchestrator.build_context(workload, package)["engineering"]
            if not context.get("node") or not context.get("engineering_interface"):
                orchestrator.block_package(
                    package,
                    "MISSING_ENGINEERING_DEPENDENCY",
                    f"Fuer {category} fehlen ECU oder Kommunikationsinterface.",
                )
            elif not context.get("message"):
                orchestrator.ensure_message_dependency(workload, package, context)

    def execute(self, orchestrator, workload: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
        if str(package.get("status")) == "BLOCKED":
            return {"status": "SUCCESS", "requested": package["requested_count"], "generated": 0, "valid": 0, "invalid": 0, "objects": [], "validation_findings": package.get("findings") or [], "remaining": package["requested_count"]}
        category = str(package["category"]).lower()
        context = orchestrator.build_context(workload, package)["engineering"]
        if not context.get("message"):
            orchestrator.block_package(package, "MISSING_MESSAGE_DEPENDENCY", "Die benoetigte Container-Message ist noch nicht freigegeben.")
            return {"status": "SUCCESS", "requested": package["requested_count"], "generated": 0, "valid": 0, "invalid": 0, "objects": [], "validation_findings": [{"code": "MISSING_MESSAGE_DEPENDENCY"}], "remaining": package["requested_count"]}

        existing_signals = orchestrator.list_canonical_objects("Signal")
        workload_objects = orchestrator.list_workload_objects(str(workload["workload_id"]), str(package["work_package_id"]))
        generator = self.select_generator(orchestrator, package)
        generated = generator.generate(
            int(package["requested_count"]),
            workload=workload,
            package=package,
            context={**context, "workload_objects": workload_objects},
            existing=existing_signals,
        )
        proposals: list[dict[str, Any]] = []
        generated_keys: list[str] = []
        for item in generated.objects:
            key = str(item["object_key"])
            definition = dict(item["definition"])
            if item.get("canonical_id"):
                orchestrator.upsert_workload_object(
                    workload,
                    package,
                    key,
                    definition,
                    canonical_id=str(item["canonical_id"]),
                    approval_state=str(item.get("approval_state") or "APPROVED"),
                    review_state=str(item.get("review_state") or "REVIEWED"),
                )
            else:
                proposals.append(definition)
                generated_keys.append(key)

        if proposals:
            proposal = orchestrator.create_validated_proposal(workload, package, "Signal", proposals)
            for index, definition in enumerate(proposals):
                orchestrator.upsert_workload_object(
                    workload,
                    package,
                    generated_keys[index],
                    definition,
                    proposal_id=str(proposal["proposal_id"]),
                    proposal_index=index,
                    review_state="READY_FOR_REVIEW" if proposal.get("status") == "READY_FOR_REVIEW" else "DRAFT",
                )
        objects = orchestrator.list_workload_objects(str(workload["workload_id"]), str(package["work_package_id"]))
        return {
            "status": "SUCCESS",
            "requested": int(package["requested_count"]),
            "generated": len(objects),
            "valid": sum(bool(item.get("is_valid")) for item in objects),
            "invalid": sum(not bool(item.get("is_valid")) for item in objects),
            "objects": [str(item["workload_object_id"]) for item in objects],
            "validation_findings": [finding for item in objects for finding in item.get("validation_results") or []],
            "remaining": max(0, int(package["requested_count"]) - len(objects)),
            "generator": type(generator).__name__,
        }

    def validate(self, orchestrator, workload: dict[str, Any]) -> dict[str, Any]:
        objects = orchestrator.list_workload_objects(str(workload["workload_id"]))
        identifiers: dict[str, str] = {}
        names: dict[str, str] = {}
        concepts: dict[str, str] = {}
        for item in objects:
            definition = dict(item.get("definition") or {})
            findings = validate_signal_definition(definition)
            identifier_key = normalized_name(definition.get("id"))
            name_key = normalized_name(definition.get("name"))
            concept_key = semantic_alias_key((definition.get("semantic") or {}).get("concept") or name_key)
            duplicate_of = identifiers.get(identifier_key) or names.get(name_key) or concepts.get(concept_key)
            if identifier_key and identifier_key in identifiers:
                findings.append({"code": "DUPLICATE_ID", "severity": "ERROR", "duplicate_of": duplicate_of})
            elif name_key and name_key in names:
                findings.append({"code": "DUPLICATE_NAME", "severity": "ERROR", "duplicate_of": duplicate_of})
            elif duplicate_of:
                findings.append({"code": "POSSIBLE_DUPLICATE", "severity": "ERROR", "duplicate_of": duplicate_of})
            else:
                identifiers[identifier_key] = str(item["workload_object_id"])
                names[name_key] = str(item["workload_object_id"])
                concepts[concept_key] = str(item["workload_object_id"])
            orchestrator.update_workload_object_validation(
                item,
                definition,
                findings,
                duplicate_of=duplicate_of,
            )
        orchestrator.recount_packages(str(workload["workload_id"]))
        return {"status": "SUCCESS", "validated": len(objects)}

    def repair(self, orchestrator, workload: dict[str, Any]) -> dict[str, Any]:
        repaired = 0
        for item in orchestrator.list_workload_objects(str(workload["workload_id"])):
            findings = item.get("validation_results") or []
            if item.get("is_valid") or any(finding.get("code") == "POSSIBLE_DUPLICATE" for finding in findings if isinstance(finding, dict)):
                continue
            definition = deepcopy(item.get("definition") or {})
            minimum = definition.get("minimum")
            maximum = definition.get("maximum")
            if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)) and minimum > maximum:
                definition["minimum"], definition["maximum"] = maximum, minimum
                definition["min_value"], definition["max_value"] = maximum, minimum
            if not isinstance(definition.get("resolution"), (int, float)) or definition.get("resolution", 0) <= 0:
                definition["resolution"] = 1
                definition["factor"] = 1
            if definition.get("unit") in (None, ""):
                definition["unit"] = "not_applicable"
            if not isinstance(definition.get("consumers"), list):
                definition["consumers"] = []
            if definition.get("default_value") is None and isinstance(definition.get("minimum"), (int, float)) and isinstance(definition.get("maximum"), (int, float)):
                definition["default_value"] = _default_value(definition["minimum"], definition["maximum"])
            if definition.get("invalid_value") is None and isinstance(definition.get("maximum"), (int, float)):
                definition["invalid_value"] = definition["maximum"] + float(definition.get("resolution") or 1)
            if definition != item.get("definition"):
                orchestrator.replace_workload_object_definition(item, definition)
                repaired += 1
        if repaired:
            orchestrator.sync_workload_proposals(str(workload["workload_id"]))
        return {"status": "SUCCESS", "repaired": repaired}


class StructuredObjectWorkloadHandler(WorkloadHandler):
    """Generic counted handler for registry types with explicit candidates."""

    def __init__(self, workload_type: str) -> None:
        self.workload_type = workload_type

    def plan(self, orchestrator, workload: dict[str, Any], packages: list[dict[str, Any]]) -> None:
        for package in packages:
            candidates = (package.get("configuration") or {}).get("candidate_objects")
            if not isinstance(candidates, list) or len(candidates) < int(package["requested_count"]):
                orchestrator.block_package(
                    package,
                    "INSUFFICIENT_DOMAIN_KNOWLEDGE",
                    "Es liegen nicht genug fachlich begruendete candidate_objects vor; Quantitaet wird nicht halluziniert.",
                )

    def execute(self, orchestrator, workload: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
        candidates = list((package.get("configuration") or {}).get("candidate_objects") or [])[: int(package["requested_count"])]
        if str(package.get("status")) == "BLOCKED":
            return {"status": "SUCCESS", "requested": package["requested_count"], "generated": 0, "valid": 0, "invalid": 0, "objects": [], "validation_findings": package.get("findings") or [], "remaining": package["requested_count"]}
        proposal = None
        target = str(workload["target_object"])
        if target in {"HardwareNode", "Function", "Interface", "Message", "Signal"}:
            proposal = orchestrator.create_validated_proposal(workload, package, target, candidates)
        for index, candidate in enumerate(candidates):
            definition = dict(candidate)
            definition.setdefault("object_type", target)
            definition.setdefault("category", package["category"])
            definition.setdefault("id", f"{workload['workload_id']}:{package['package_code']}:{index + 1}")
            key = f"{target.lower()}:{package['category']}:{normalized_name(definition.get('name') or definition['id'])}"
            orchestrator.upsert_workload_object(
                workload,
                package,
                key,
                definition,
                proposal_id=str(proposal["proposal_id"]) if proposal else None,
                proposal_index=index if proposal else None,
                review_state="READY_FOR_REVIEW" if proposal and proposal.get("status") == "READY_FOR_REVIEW" else "DRAFT",
            )
        return {"status": "SUCCESS", "requested": package["requested_count"], "generated": len(candidates), "valid": 0, "invalid": 0, "objects": [], "validation_findings": [], "remaining": max(0, int(package["requested_count"]) - len(candidates))}

    def validate(self, orchestrator, workload: dict[str, Any]) -> dict[str, Any]:
        objects = orchestrator.list_workload_objects(str(workload["workload_id"]))
        names: dict[str, str] = {}
        for item in objects:
            definition = dict(item.get("definition") or {})
            findings = []
            if not definition.get("id"):
                findings.append({"code": "MISSING_FIELD", "field": "id", "severity": "ERROR"})
            if not definition.get("name") and workload["target_object"] not in {"Documentation", "TraceAnalysis", "NetworkAnalysis", "BusLoadAnalysis"}:
                findings.append({"code": "MISSING_FIELD", "field": "name", "severity": "ERROR"})
            key = normalized_name(definition.get("name") or definition.get("id"))
            duplicate_of = names.get(key)
            if duplicate_of:
                findings.append({"code": "POSSIBLE_DUPLICATE", "severity": "ERROR", "duplicate_of": duplicate_of})
            else:
                names[key] = str(item["workload_object_id"])
            orchestrator.update_workload_object_validation(item, definition, findings, duplicate_of=duplicate_of)
        orchestrator.recount_packages(str(workload["workload_id"]))
        return {"status": "SUCCESS", "validated": len(objects)}

    def repair(self, orchestrator, workload: dict[str, Any]) -> dict[str, Any]:
        return {"status": "SUCCESS", "repaired": 0, "note": "Unsichere fachliche Inhalte erfordern Review statt Halluzinationsreparatur."}
