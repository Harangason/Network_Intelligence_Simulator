"""Weighted multilingual vocabulary for local engineering embeddings."""

from __future__ import annotations

from dataclasses import dataclass
import re
from unicodedata import normalize


_GERMAN_TRANSLITERATION = str.maketrans({
    "\u00e4": "ae",
    "\u00f6": "oe",
    "\u00fc": "ue",
    "\u00df": "ss",
    "\u00c4": "ae",
    "\u00d6": "oe",
    "\u00dc": "ue",
})


def normalize_engineering_text(value: str) -> str:
    """Normalizes German text, identifiers and CamelCase into stable words."""

    text = str(value).translate(_GERMAN_TRANSLITERATION)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def engineering_tokens(value: str) -> list[str]:
    return [token for token in normalize_engineering_text(value).split() if len(token) > 1]


@dataclass(frozen=True)
class SemanticConcept:
    key: str
    aliases: tuple[str, ...]
    weight: float = 2.0


ENGINEERING_CONCEPTS = (
    SemanticConcept(
        "intent:relation_mutation",
        (
            "relation anlegen", "relation erstellen", "beziehung anlegen", "kante erzeugen",
            "verbinden", "verbinde", "verknuepfen", "verknuepfe", "zuordnen", "ordne zu",
            "connect", "link", "associate", "assign", "create relation",
        ),
        2.6,
    ),
    SemanticConcept(
        "intent:create",
        ("anlegen", "erzeugen", "erstellen", "generieren", "modellieren", "registrieren", "create", "generate"),
        2.2,
    ),
    SemanticConcept(
        "intent:inspect",
        ("finden", "gefunden", "suchen", "anzeigen", "auflisten", "pruefen", "inspect", "find", "list", "lookup"),
        1.8,
    ),
    SemanticConcept(
        "intent:validate",
        ("validieren", "pruefen", "technische pruefung", "validate", "verify", "check"),
        2.0,
    ),
    SemanticConcept(
        "intent:approve",
        ("freigeben", "genehmigen", "uebernehmen", "approve", "accept", "release"),
        2.0,
    ),
    SemanticConcept(
        "entity:hardware_node",
        ("hardware node", "hardwarenode", "hardware knoten", "ecu", "steuergeraet", "controller", "gateway", "sensor", "aktor"),
        2.4,
    ),
    SemanticConcept(
        "entity:function",
        ("function", "functions", "funktion", "funktionen", "capability", "service function"),
        2.3,
    ),
    SemanticConcept(
        "entity:interface",
        ("interface", "interfaces", "schnittstelle", "schnittstellen", "port", "connector", "bus interface"),
        2.4,
    ),
    SemanticConcept(
        "entity:message",
        ("message", "messages", "nachricht", "nachrichten", "frame", "telegramm", "payload"),
        2.3,
    ),
    SemanticConcept(
        "entity:signal",
        ("signal", "signals", "datenpunkt", "messwert", "signalwert"),
        2.3,
    ),
    SemanticConcept(
        "entity:relation",
        ("relation", "relations", "relationship", "beziehung", "kante", "edge", "relation type"),
        2.5,
    ),
    SemanticConcept(
        "relation:has_interface",
        ("has interface", "has_interface", "besitzt schnittstelle", "interface zuordnen"),
        2.8,
    ),
    SemanticConcept(
        "relation:has_function",
        ("has function", "has_function", "besitzt funktion", "funktion zuordnen"),
        2.8,
    ),
    SemanticConcept(
        "relation:contains_signal",
        ("contains signal", "contains_signal", "enthaelt signal", "signal zuordnen"),
        2.8,
    ),
    SemanticConcept(
        "relation:connected_to",
        ("connected to", "connected_to", "verbunden mit", "physisch verbunden"),
        2.7,
    ),
    SemanticConcept(
        "workflow:routing",
        ("routing", "route", "routing table", "routing tabelle", "kommunikationspfad", "route proposal"),
        2.4,
    ),
    SemanticConcept(
        "workflow:canonical_model",
        ("kanonisches modell", "canonical model", "engineering model", "objektmodell"),
        2.4,
    ),
    SemanticConcept(
        "status:discovered",
        ("gefunden", "erkannt", "discovered", "found"),
        1.7,
    ),
    SemanticConcept(
        "status:modelled",
        ("modelliert", "angelegt", "modelled", "modeled", "created"),
        1.7,
    ),
    SemanticConcept(
        "status:registered",
        ("registriert", "gespeichert", "registered", "persisted"),
        1.7,
    ),
    SemanticConcept(
        "api:canonical_reference",
        ("object id", "object_id", "object type", "object_type", "source id", "target id", "canonical id"),
        1.9,
    ),
    SemanticConcept(
        "api:relation_contract",
        ("relation type", "relation_type", "engineering relation", "relation payload", "json payload"),
        2.1,
    ),
    SemanticConcept(
        "safety:external_credentials",
        ("api token", "api_token", "your api token", "username", "authentication", "auth token"),
        1.8,
    ),
)


class EngineeringSemanticVocabulary:
    """Maps surface words to weighted, reusable engineering concept axes."""

    def __init__(self, concepts: tuple[SemanticConcept, ...] = ENGINEERING_CONCEPTS) -> None:
        self.concepts = concepts
        self._aliases = {
            concept.key: tuple(tuple(engineering_tokens(alias)) for alias in concept.aliases)
            for concept in concepts
        }

    @staticmethod
    def _contains(tokens: list[str], alias: tuple[str, ...]) -> bool:
        if not alias or len(alias) > len(tokens):
            return False
        width = len(alias)
        return any(tuple(tokens[index:index + width]) == alias for index in range(len(tokens) - width + 1))

    def concept_weights(self, value: str) -> dict[str, float]:
        tokens = engineering_tokens(value)
        weights = {
            concept.key: concept.weight
            for concept in self.concepts
            if any(self._contains(tokens, alias) for alias in self._aliases[concept.key])
        }

        relation_mutation = "intent:relation_mutation" in weights
        if relation_mutation and "entity:interface" in weights:
            weights["relation:has_interface"] = 2.8
        if relation_mutation and "entity:function" in weights:
            weights["relation:has_function"] = 2.8
        if relation_mutation and "entity:signal" in weights:
            weights["relation:contains_signal"] = 2.8
        if relation_mutation and "entity:hardware_node" in weights and len(weights) == 2:
            weights["relation:connected_to"] = 2.7
        return weights

    def lexical_features(self, value: str) -> set[str]:
        return {*engineering_tokens(value), *self.concept_weights(value)}

    def vector_features(self, value: str) -> list[tuple[str, float]]:
        tokens = engineering_tokens(value)
        features = [(f"token:{token}", 1.0) for token in tokens]
        features.extend((f"phrase:{left}_{right}", 1.15) for left, right in zip(tokens, tokens[1:]))
        features.extend((f"concept:{key}", weight) for key, weight in self.concept_weights(value).items())
        return features
