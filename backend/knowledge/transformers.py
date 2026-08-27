"""Transformer-facing contract and deterministic local semantic implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from hashlib import sha256
from math import sqrt
from typing import Any

from .semantic_vocabulary import EngineeringSemanticVocabulary, engineering_tokens


def tokenize(value: str) -> list[str]:
    return engineering_tokens(value)


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    denominator = sqrt(sum(value * value for value in left)) * sqrt(sum(value * value for value in right))
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / denominator


class TransformerService(ABC):
    """Separates embedding, reranking and classification from persistence."""

    model_name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def rerank(self, query: str, candidates: list[dict[str, Any]], *, limit: int = 20) -> list[dict[str, Any]]: ...

    @abstractmethod
    def classify(self, text: str, labels: list[str]) -> dict[str, Any]: ...


class LocalTransformerService(TransformerService):
    """Offline semantic baseline with stable hashed token and phrase embeddings.

    It is intentionally small and deterministic. A provider-backed transformer can
    replace it through the same contract without changing knowledge or business code.
    """

    model_name = "local-hashed-engineering-embedding-v2"

    def __init__(
        self,
        dimensions: int = 256,
        vocabulary: EngineeringSemanticVocabulary | None = None,
    ) -> None:
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32.")
        self.dimensions = dimensions
        self.vocabulary = vocabulary or EngineeringSemanticVocabulary()

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for feature, weight in self.vocabulary.vector_features(text):
            digest = sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * weight
        norm = sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(str(text)) for text in texts]

    def rerank(self, query: str, candidates: list[dict[str, Any]], *, limit: int = 20) -> list[dict[str, Any]]:
        query_tokens = self.vocabulary.lexical_features(query)
        query_vector = self._embed_one(query)
        ranked = []
        for candidate in candidates:
            text = str(candidate.get("text") or candidate.get("name") or candidate.get("reason") or "")
            candidate_tokens = self.vocabulary.lexical_features(text)
            lexical = len(query_tokens & candidate_tokens) / max(1, len(query_tokens))
            semantic = cosine(query_vector, self._embed_one(text))
            prior = float(candidate.get("score") or 0.0)
            score = max(0.0, min(1.0, prior * 0.45 + semantic * 0.35 + lexical * 0.2))
            ranked.append({**candidate, "score": round(score, 8), "reranker_model": self.model_name})
        return sorted(ranked, key=lambda item: (-item["score"], str(item.get("object_id") or item.get("id") or "")))[:limit]

    def classify(self, text: str, labels: list[str]) -> dict[str, Any]:
        if not labels:
            raise ValueError("At least one label is required.")
        query_vector = self._embed_one(text)
        scored = [
            {"label": label, "score": max(0.0, cosine(query_vector, self._embed_one(label)))}
            for label in labels
        ]
        scored.sort(key=lambda item: (-item["score"], item["label"]))
        return {"label": scored[0]["label"], "score": round(scored[0]["score"], 8), "scores": scored}
