"""Deterministic-first semantic classification with modular model adapters."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .models import ClassificationInput, ClassificationProposal, SemanticCandidate
from .ontology import ConceptOntology, normalize_key


def _tokens(*values: Any) -> set[str]:
    text = " ".join(str(value or "") for value in values)
    normalized = text.replace("_", " ").replace("-", " ").replace("/", " ")
    normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    return {token.lower() for token in re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", normalized) if token}


class HeuristicClassifier:
    def __init__(self, ontology: ConceptOntology) -> None:
        self.ontology = ontology

    def classify(self, item: ClassificationInput) -> list[SemanticCandidate]:
        candidates: list[SemanticCandidate] = []
        unit = item.unit.strip()
        words = _tokens(item.name, item.description, unit)
        unit_alias = self.ontology.resolve_alias(unit)
        if unit_alias and unit_alias.id != "STATUS":
            candidates.append(_candidate(unit_alias, 0.86, "heuristic", f"Einheit {unit!r} passt zum Konzept."))

        token_map = {
            "TEMPERATURE": {"temperature", "temp", "thermal", "temperatur", "coolant", "refrigerant"},
            "PRESSURE": {"pressure", "druck", "press"},
            "VOLTAGE": {"voltage", "volt", "spannung"},
            "CURRENT": {"current", "ampere", "strom"},
            "POSITION": {"position", "pos", "angle", "winkel", "level"},
            "VELOCITY": {"velocity", "speed", "geschwindigkeit"},
            "ROTATIONAL_SPEED": {"rpm", "drehzahl", "rotationalspeed", "rotational", "revolutions"},
            "DIAGNOSTIC": {"diagnostic", "diagnose", "dtc"},
            "WARNING": {"warning", "warnung", "warn"},
            "ERROR": {"error", "fehler", "fault", "invalid"},
        }
        for concept_id, hints in token_map.items():
            if words & hints:
                concept = self.ontology.get(concept_id)
                if concept:
                    candidates.append(_candidate(concept, 0.74, "heuristic", "Name, Beschreibung oder Einheit enthaelt passende Semantikhinweise."))

        if _looks_discrete_state(item, words):
            concept = self.ontology.get("OPERATING_STATE") or self.ontology.get("STATUS")
            if concept:
                confidence = 0.82 if item.allowed_values or item.enum_values else 0.68
                candidates.append(_candidate(concept, confidence, "heuristic", "Diskrete Value-Domain oder Statusbegriff erkannt."))

        return candidates


class OntologyResolver:
    def __init__(self, ontology: ConceptOntology) -> None:
        self.ontology = ontology

    def classify(self, item: ClassificationInput) -> list[SemanticCandidate]:
        candidates = []
        for value in (item.name, item.unit, item.description):
            concept = self.ontology.resolve_alias(str(value or ""))
            if concept:
                candidates.append(_candidate(concept, 0.78, "ontology", "Alias direkt in der freigegebenen Ontologie gefunden."))
        return candidates


class EmbeddingClassifier:
    """Lightweight local similarity placeholder until a vector backend is registered."""

    def __init__(self, ontology: ConceptOntology) -> None:
        self.ontology = ontology

    def classify(self, item: ClassificationInput) -> list[SemanticCandidate]:
        input_tokens = _tokens(item.name, item.description, item.unit, item.data_type)
        if not input_tokens:
            return []
        candidates = []
        for concept in self.ontology.concepts():
            concept_tokens = _tokens(concept.canonical_name, concept.display_name, concept.description, " ".join(concept.aliases), " ".join(concept.expected_units))
            overlap = input_tokens & concept_tokens
            union = input_tokens | concept_tokens
            score = len(overlap) / len(union) if union else 0.0
            if score >= 0.12:
                candidates.append(_candidate(concept, min(0.70, 0.45 + score), "embedding_similarity", "Lokale Token-Aehnlichkeit als Embedding-Ersatz bewertet.", {"overlap": sorted(overlap)}))
        return candidates


class DisabledModelClassifier:
    def __init__(self, source_name: str) -> None:
        self.source_name = source_name

    def classify(self, item: ClassificationInput) -> list[SemanticCandidate]:
        return []


class ConfidenceAggregator:
    WEIGHTS = {
        "heuristic": 1.0,
        "ontology": 1.0,
        "embedding_similarity": 0.55,
        "ml": 0.0,
        "dl": 0.0,
        "llm": 0.0,
    }

    def aggregate(self, candidates: list[SemanticCandidate]) -> tuple[list[SemanticCandidate], str]:
        grouped: dict[str, list[SemanticCandidate]] = defaultdict(list)
        for candidate in candidates:
            grouped[candidate.concept_id].append(candidate)

        merged: list[SemanticCandidate] = []
        for concept_id, items in grouped.items():
            best = max(items, key=lambda item: item.confidence)
            weighted = sum(item.confidence * max(self.WEIGHTS.get(source, 0.35) for source in item.sources) for item in items)
            weight_total = sum(max(self.WEIGHTS.get(source, 0.35) for source in item.sources) for item in items) or 1.0
            source_bonus = min(0.12, 0.04 * len({source for item in items for source in item.sources}))
            confidence = min(0.99, weighted / weight_total + source_bonus)
            merged.append(
                SemanticCandidate(
                    concept_id=concept_id,
                    canonical_name=best.canonical_name,
                    display_name=best.display_name,
                    semantic_type=best.semantic_type,
                    confidence=round(confidence, 4),
                    sources=tuple(sorted({source for item in items for source in item.sources})),
                    explanation=" | ".join(dict.fromkeys(item.explanation for item in items)),
                    evidence={"contributors": [item.to_dict() for item in items]},
                )
            )

        merged.sort(key=lambda item: item.confidence, reverse=True)
        if not merged:
            return [], "UNKNOWN"
        if len(merged) > 1 and merged[0].confidence - merged[1].confidence < 0.08:
            return merged, "AMBIGUOUS"
        top = merged[0].confidence
        if top >= 0.88:
            return merged, "CONFIRMED"
        if top >= 0.72:
            return merged, "HIGH_CONFIDENCE"
        if top >= 0.50:
            return merged, "POSSIBLE"
        return merged, "UNKNOWN"


class SemanticClassificationService:
    def __init__(self, ontology: ConceptOntology | None = None) -> None:
        self.ontology = ontology or ConceptOntology()
        self.classifiers = (
            HeuristicClassifier(self.ontology),
            OntologyResolver(self.ontology),
            EmbeddingClassifier(self.ontology),
            DisabledModelClassifier("ml"),
            DisabledModelClassifier("dl"),
            DisabledModelClassifier("llm"),
        )
        self.aggregator = ConfidenceAggregator()

    def classify(self, payload: dict[str, Any] | ClassificationInput) -> dict[str, Any]:
        item = payload if isinstance(payload, ClassificationInput) else ClassificationInput.from_payload(payload)
        raw_candidates: list[SemanticCandidate] = []
        for classifier in self.classifiers:
            raw_candidates.extend(classifier.classify(item))
        candidates, decision_state = self.aggregator.aggregate(raw_candidates)
        return ClassificationProposal.build(
            input_data=item,
            candidates=candidates,
            decision_state=decision_state,
            pipeline=("heuristic", "ontology", "embedding_similarity", "confidence_aggregation", "human_review_gate"),
            model_states={
                "heuristic": "ACTIVE",
                "ontology": "ACTIVE",
                "embedding": "LOCAL_SIMILARITY_PLACEHOLDER",
                "ml": "NOT_REGISTERED",
                "dl": "NOT_REGISTERED",
                "llm": "PROPOSAL_ONLY_NOT_CALLED",
            },
        ).to_dict()

    def concepts(self) -> dict[str, Any]:
        items = [concept.to_dict() for concept in self.ontology.concepts()]
        return {"items": items, "count": len(items)}

    def concept(self, concept_id: str) -> dict[str, Any] | None:
        concept = self.ontology.get(concept_id)
        return concept.to_dict() if concept else None


def _candidate(concept: Any, confidence: float, source: str, explanation: str, evidence: dict[str, Any] | None = None) -> SemanticCandidate:
    return SemanticCandidate(
        concept_id=concept.id,
        canonical_name=concept.canonical_name,
        display_name=concept.display_name,
        semantic_type=concept.semantic_type,
        confidence=confidence,
        sources=(source,),
        explanation=explanation,
        evidence=evidence or {},
    )


def _looks_discrete_state(item: ClassificationInput, words: set[str]) -> bool:
    if words & {"status", "state", "mode", "zustand", "health", "quality", "availability"}:
        return True
    if item.allowed_values or item.enum_values:
        return not item.unit or normalize_key(item.unit) in {"code", "na", "notapplicable"}
    return False
