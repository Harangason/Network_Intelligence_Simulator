"""Provider-neutral semantic intelligence data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class TypicalRange:
    minimum: float | None = None
    maximum: float | None = None
    unit: str = ""
    note: str = ""


@dataclass(frozen=True)
class SemanticConcept:
    id: str
    canonical_name: str
    display_name: str
    description: str
    aliases: tuple[str, ...] = ()
    parent_concept_id: str | None = None
    child_concept_ids: tuple[str, ...] = ()
    semantic_type: str = "UNKNOWN"
    expected_units: tuple[str, ...] = ()
    typical_ranges: tuple[TypicalRange, ...] = ()
    typical_datatypes: tuple[str, ...] = ()
    domain_tags: tuple[str, ...] = ()
    industry_tags: tuple[str, ...] = ()
    related_concepts: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    status: str = "APPROVED_SEED"
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClassificationInput:
    object_type: str
    name: str
    unit: str = ""
    data_type: str = ""
    minimum: float | None = None
    maximum: float | None = None
    bit_length: int | None = None
    allowed_values: tuple[Any, ...] = ()
    enum_values: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ClassificationInput":
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        semantic = payload.get("semantic") if isinstance(payload.get("semantic"), dict) else {}
        configuration = payload.get("configuration") if isinstance(payload.get("configuration"), dict) else {}
        return cls(
            object_type=str(payload.get("object_type") or payload.get("type") or "Signal"),
            name=str(payload.get("display_name") or payload.get("name") or payload.get("id") or ""),
            unit=str(payload.get("unit") or semantic.get("unit") or data.get("unit") or ""),
            data_type=str(payload.get("data_type") or configuration.get("raw_datatype") or ""),
            minimum=_number(payload.get("min_value", payload.get("minimum", data.get("minimum")))),
            maximum=_number(payload.get("max_value", payload.get("maximum", data.get("maximum")))),
            bit_length=_int_or_none(payload.get("length_bits", configuration.get("bit_length"))),
            allowed_values=tuple(data.get("allowed_values") or configuration.get("allowed_values") or ()),
            enum_values=dict(data.get("enum_values") or configuration.get("enum_values") or {}),
            description=str(payload.get("description") or semantic.get("meaning") or ""),
            context=dict(payload.get("context") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticCandidate:
    concept_id: str
    canonical_name: str
    display_name: str
    semantic_type: str
    confidence: float
    sources: tuple[str, ...]
    explanation: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClassificationProposal:
    proposal_id: str
    input: ClassificationInput
    candidates: tuple[SemanticCandidate, ...]
    selected_concept_id: str | None
    semantic_type: str
    confidence: float
    decision_state: str
    requires_review: bool
    pipeline: tuple[str, ...]
    model_states: dict[str, str]
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def build(
        cls,
        *,
        input_data: ClassificationInput,
        candidates: list[SemanticCandidate],
        decision_state: str,
        pipeline: tuple[str, ...],
        model_states: dict[str, str],
    ) -> "ClassificationProposal":
        ordered = tuple(sorted(candidates, key=lambda item: item.confidence, reverse=True))
        selected = ordered[0] if ordered else None
        return cls(
            proposal_id=f"semantic-proposal-{uuid4().hex[:12]}",
            input=input_data,
            candidates=ordered,
            selected_concept_id=selected.concept_id if selected else None,
            semantic_type=selected.semantic_type if selected else "UNKNOWN",
            confidence=round(selected.confidence, 4) if selected else 0.0,
            decision_state=decision_state,
            requires_review=decision_state not in {"CONFIRMED", "HIGH_CONFIDENCE"},
            pipeline=pipeline,
            model_states=model_states,
        )


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and result not in {float("inf"), float("-inf")} else None


def _int_or_none(value: Any) -> int | None:
    number = _number(value)
    if number is None or int(number) != number:
        return None
    return int(number)
