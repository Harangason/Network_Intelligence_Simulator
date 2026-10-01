"""Small approved seed ontology for industry-neutral engineering semantics."""

from __future__ import annotations

import re
from typing import Iterable

from .models import SemanticConcept, TypicalRange


def normalize_key(value: str) -> str:
    text = value.lower().replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "", text)


class ConceptOntology:
    """Resolve aliases, hierarchy and relations without model-side authority."""

    def __init__(self, concepts: Iterable[SemanticConcept] | None = None) -> None:
        seeded = list(concepts or _seed_concepts())
        self._concepts = {concept.id: concept for concept in seeded}
        self._aliases: dict[str, str] = {}
        for concept in seeded:
            for alias in (concept.id, concept.canonical_name, concept.display_name, *concept.aliases):
                key = normalize_key(alias)
                if key:
                    self._aliases.setdefault(key, concept.id)

    def concepts(self) -> list[SemanticConcept]:
        return sorted(self._concepts.values(), key=lambda item: item.canonical_name)

    def get(self, concept_id: str) -> SemanticConcept | None:
        return self._concepts.get(concept_id) or self.resolve_alias(concept_id)

    def resolve_alias(self, value: str) -> SemanticConcept | None:
        concept_id = self._aliases.get(normalize_key(value))
        return self._concepts.get(concept_id) if concept_id else None

    def resolve_parent(self, concept_id: str) -> SemanticConcept | None:
        concept = self.get(concept_id)
        return self._concepts.get(concept.parent_concept_id) if concept and concept.parent_concept_id else None

    def resolve_child(self, parent_concept_id: str, child: str) -> SemanticConcept | None:
        parent = self.get(parent_concept_id)
        candidate = self.get(child)
        if not parent or not candidate:
            return None
        return candidate if candidate.id in parent.child_concept_ids else None

    def find_related_concepts(self, concept_id: str) -> list[SemanticConcept]:
        concept = self.get(concept_id)
        if not concept:
            return []
        ids = {item for item in concept.related_concepts if item in self._concepts}
        ids.update(item for item in concept.child_concept_ids if item in self._concepts)
        if concept.parent_concept_id in self._concepts:
            ids.add(str(concept.parent_concept_id))
        return sorted((self._concepts[item] for item in ids), key=lambda item: item.canonical_name)

    def validate_concept_relation(self, source_concept_id: str, target_concept_id: str) -> bool:
        source = self.get(source_concept_id)
        target = self.get(target_concept_id)
        if not source or not target:
            return False
        if target.id in source.related_concepts or source.id in target.related_concepts:
            return True
        return self.find_common_ancestor(source.id, target.id) is not None

    def find_common_ancestor(self, left_concept_id: str, right_concept_id: str) -> SemanticConcept | None:
        left = self.get(left_concept_id)
        right = self.get(right_concept_id)
        if not left or not right:
            return None
        left_ancestors = _ancestor_ids(left, self._concepts)
        for concept_id in _ancestor_ids(right, self._concepts):
            if concept_id in left_ancestors:
                return self._concepts[concept_id]
        return None


def _ancestor_ids(concept: SemanticConcept, concepts: dict[str, SemanticConcept]) -> list[str]:
    result = [concept.id]
    current = concept
    while current.parent_concept_id and current.parent_concept_id in concepts:
        result.append(current.parent_concept_id)
        current = concepts[current.parent_concept_id]
    return result


def _concept(
    concept_id: str,
    canonical_name: str,
    display_name: str,
    description: str,
    *,
    parent: str | None = None,
    children: tuple[str, ...] = (),
    semantic_type: str = "UNKNOWN",
    aliases: tuple[str, ...] = (),
    units: tuple[str, ...] = (),
    datatypes: tuple[str, ...] = (),
    related: tuple[str, ...] = (),
    ranges: tuple[TypicalRange, ...] = (),
) -> SemanticConcept:
    return SemanticConcept(
        id=concept_id,
        canonical_name=canonical_name,
        display_name=display_name,
        description=description,
        aliases=aliases,
        parent_concept_id=parent,
        child_concept_ids=children,
        semantic_type=semantic_type,
        expected_units=units,
        typical_ranges=ranges,
        typical_datatypes=datatypes,
        domain_tags=("engineering",),
        industry_tags=("industry_neutral",),
        related_concepts=related,
        provenance={"source": "SEMANTIC_INTELLIGENCE_ML_DL_LLM_TRAINING_ARCHITECTURE", "type": "approved_seed"},
    )


def _seed_concepts() -> tuple[SemanticConcept, ...]:
    physical_children = ("TEMPERATURE", "PRESSURE", "VOLTAGE", "CURRENT", "POSITION", "VELOCITY", "ROTATIONAL_SPEED")
    state_children = ("OPERATING_STATE", "HEALTH_STATE", "SAFETY_STATE", "COMMUNICATION_STATE")
    return (
        _concept("ENGINEERING_CONCEPT", "engineering_concept", "Engineering Concept", "Root concept for engineering semantics.", children=("PHYSICAL_QUANTITY", "STATUS", "COMMAND", "REQUEST", "DIAGNOSTIC")),
        _concept("PHYSICAL_QUANTITY", "physical_quantity", "Physical Quantity", "Measured or calculated physical value.", parent="ENGINEERING_CONCEPT", children=physical_children, semantic_type="NUMERIC"),
        _concept("TEMPERATURE", "temperature", "Temperature", "Thermal state expressed as a physical quantity.", parent="PHYSICAL_QUANTITY", semantic_type="NUMERIC", aliases=("temp", "actual_temperature", "target_temperature", "isttemperatur", "solltemperatur"), units=("degC", "C", "K", "°C"), datatypes=("signed", "float", "double"), ranges=(TypicalRange(-273.15, 2000, "degC", "physical lower bound plus broad engineering range"),)),
        _concept("PRESSURE", "pressure", "Pressure", "Force per area or normalized pressure measurement.", parent="PHYSICAL_QUANTITY", semantic_type="NUMERIC", aliases=("press", "bar", "pascal"), units=("Pa", "kPa", "bar", "mbar"), datatypes=("unsigned", "signed", "float", "double")),
        _concept("VOLTAGE", "voltage", "Voltage", "Electrical potential difference.", parent="PHYSICAL_QUANTITY", semantic_type="NUMERIC", aliases=("volt", "battery_voltage", "u"), units=("V", "mV", "kV"), datatypes=("unsigned", "signed", "float", "double")),
        _concept("CURRENT", "current", "Current", "Electrical current.", parent="PHYSICAL_QUANTITY", semantic_type="NUMERIC", aliases=("ampere", "amps", "i"), units=("A", "mA"), datatypes=("unsigned", "signed", "float", "double")),
        _concept("POSITION", "position", "Position", "Linear, angular or logical position value.", parent="PHYSICAL_QUANTITY", semantic_type="NUMERIC", aliases=("pos", "angle", "winkel", "level"), units=("deg", "rad", "mm", "m", "%"), datatypes=("unsigned", "signed", "float", "double")),
        _concept("VELOCITY", "velocity", "Velocity", "Linear speed or rate of change.", parent="PHYSICAL_QUANTITY", semantic_type="NUMERIC", aliases=("speed", "velocity", "geschwindigkeit"), units=("m/s", "km/h", "mph"), datatypes=("unsigned", "signed", "float", "double")),
        _concept("ROTATIONAL_SPEED", "rotational_speed", "Rotational Speed", "Angular velocity measured as revolutions per time.", parent="PHYSICAL_QUANTITY", semantic_type="NUMERIC", aliases=("rpm", "1/min", "rev_per_min", "rotationspeed", "rotationalspeed", "drehzahl"), units=("rpm", "1/min"), datatypes=("unsigned", "signed", "float", "double")),
        _concept("STATUS", "status", "Status", "Discrete state or condition value.", parent="ENGINEERING_CONCEPT", children=state_children, semantic_type="STATE", aliases=("state", "mode", "zustand", "statuscode"), datatypes=("unsigned", "enum", "string"), related=("WARNING", "ERROR")),
        _concept("OPERATING_STATE", "operating_state", "Operating State", "Discrete operating mode or availability condition.", parent="STATUS", semantic_type="STATE", aliases=("mode", "operation_state", "betrieb", "betriebszustand"), datatypes=("unsigned", "enum", "string"), related=("HEALTH_STATE",)),
        _concept("HEALTH_STATE", "health_state", "Health State", "Discrete condition describing health or availability.", parent="STATUS", semantic_type="STATE", aliases=("health", "quality", "availability"), datatypes=("unsigned", "enum", "string"), related=("ERROR", "WARNING")),
        _concept("SAFETY_STATE", "safety_state", "Safety State", "Discrete safety-relevant state.", parent="STATUS", semantic_type="STATE", aliases=("safe_state", "safety_status", "sicherheitszustand"), datatypes=("unsigned", "enum", "string"), related=("ERROR", "WARNING")),
        _concept("COMMUNICATION_STATE", "communication_state", "Communication State", "Discrete communication or transport state.", parent="STATUS", semantic_type="STATE", aliases=("communication_status", "network_state", "bus_state"), datatypes=("unsigned", "enum", "string"), related=("ERROR", "WARNING")),
        _concept("COMMAND", "command", "Command", "Requested action issued to another engineering object.", parent="ENGINEERING_CONCEPT", semantic_type="COMMAND", aliases=("cmd", "request_command", "setpoint_command"), datatypes=("unsigned", "enum", "string"), related=("REQUEST", "STATUS")),
        _concept("REQUEST", "request", "Request", "Requested service, data or state change.", parent="ENGINEERING_CONCEPT", semantic_type="REQUEST", aliases=("req", "service_request"), datatypes=("unsigned", "enum", "string"), related=("COMMAND", "STATUS")),
        _concept("WARNING", "warning", "Warning", "Non-fatal abnormal condition requiring attention.", parent="DIAGNOSTIC", semantic_type="DIAGNOSTIC", aliases=("warn", "warnung", "degraded"), datatypes=("unsigned", "enum", "string"), related=("STATUS", "ERROR")),
        _concept("ERROR", "error", "Error", "Fault or invalid condition.", parent="DIAGNOSTIC", semantic_type="DIAGNOSTIC", aliases=("fault", "fehler", "invalid"), datatypes=("unsigned", "enum", "string"), related=("STATUS", "WARNING")),
        _concept("DIAGNOSTIC", "diagnostic", "Diagnostic", "Information used for diagnosis or analysis.", parent="ENGINEERING_CONCEPT", children=("WARNING", "ERROR"), semantic_type="DIAGNOSTIC", aliases=("diagnose", "diagnosis", "dtc"), datatypes=("unsigned", "enum", "string"), related=("STATUS",)),
    )
