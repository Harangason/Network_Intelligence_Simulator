"""Conservative entity resolution for imported engineering knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any

from .transformers import LocalTransformerService, TransformerService, cosine


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


@dataclass(frozen=True)
class EntityResolutionResult:
    match_type: str
    candidate_id: str | None
    score: float
    reason: str
    auto_merge_allowed: bool


class EntityResolutionService:
    """Finds candidates but never auto-merges ambiguous semantic matches."""

    def __init__(
        self,
        transformer: TransformerService | None = None,
        *,
        aliases: dict[str, set[str]] | None = None,
    ) -> None:
        self.transformer = transformer or LocalTransformerService()
        self.aliases = {
            _normalize(canonical): {_normalize(alias) for alias in values}
            for canonical, values in (aliases or {}).items()
        }

    def resolve(self, name: str, candidates: list[dict[str, Any]]) -> EntityResolutionResult:
        normalized = _normalize(name)
        for candidate in candidates:
            candidate_name = str(candidate.get("name") or "")
            if normalized and normalized == _normalize(candidate_name):
                return EntityResolutionResult("EXACT_MATCH", str(candidate.get("id")), 1.0, "Normalized names match.", True)

        for candidate in candidates:
            candidate_name = str(candidate.get("name") or "")
            canonical = _normalize(candidate_name)
            known_aliases = self.aliases.get(canonical, set()) | {
                _normalize(value) for value in candidate.get("aliases", []) if value
            }
            if normalized in known_aliases:
                return EntityResolutionResult("ALIAS_MATCH", str(candidate.get("id")), 0.99, "A reviewed alias matches.", True)

        if not candidates:
            return EntityResolutionResult("NEW_ENTITY", None, 0.0, "No candidates exist.", False)

        query_vector = self.transformer.embed([name])[0]
        best: tuple[float, dict[str, Any]] | None = None
        for candidate in candidates:
            candidate_name = str(candidate.get("name") or "")
            semantic = cosine(query_vector, self.transformer.embed([candidate_name])[0])
            lexical = SequenceMatcher(None, normalized, _normalize(candidate_name)).ratio()
            score = max(semantic * 0.55 + lexical * 0.45, lexical * 0.8)
            if best is None or score > best[0]:
                best = (score, candidate)

        assert best is not None
        score, candidate = best
        if score >= 0.9:
            match_type = "SEMANTIC_MATCH"
        elif score >= 0.62:
            match_type = "POSSIBLE_MATCH"
        else:
            return EntityResolutionResult("NEW_ENTITY", None, round(score, 6), "No sufficiently similar entity found.", False)
        return EntityResolutionResult(
            match_type,
            str(candidate.get("id")),
            round(score, 6),
            "A human must confirm semantic identity before merge.",
            False,
        )
