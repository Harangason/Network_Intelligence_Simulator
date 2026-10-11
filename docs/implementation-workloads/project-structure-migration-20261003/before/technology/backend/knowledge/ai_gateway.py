"""Provider-neutral AI model routing for generation and small-model tasks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .transformers import LocalTransformerService, TransformerService


class AIProvider(ABC):
    provider_name: str

    @abstractmethod
    def generate(self, prompt: str, *, context: dict[str, Any] | None = None) -> str: ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def rerank(self, query: str, candidates: list[dict[str, Any]], *, limit: int = 20) -> list[dict[str, Any]]: ...

    @abstractmethod
    def classify(self, text: str, labels: list[str]) -> dict[str, Any]: ...


class LocalAIProvider(AIProvider):
    """Local provider for embeddings/ranking with an optional generation callback."""

    provider_name = "local"

    def __init__(
        self,
        transformer: TransformerService | None = None,
        generation_callback: Callable[[str, dict[str, Any] | None], str] | None = None,
    ) -> None:
        self.transformer = transformer or LocalTransformerService()
        self.generation_callback = generation_callback

    def generate(self, prompt: str, *, context: dict[str, Any] | None = None) -> str:
        if self.generation_callback is None:
            raise RuntimeError("No local generation model is configured.")
        return self.generation_callback(prompt, context)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.transformer.embed(texts)

    def rerank(self, query: str, candidates: list[dict[str, Any]], *, limit: int = 20) -> list[dict[str, Any]]:
        return self.transformer.rerank(query, candidates, limit=limit)

    def classify(self, text: str, labels: list[str]) -> dict[str, Any]:
        return self.transformer.classify(text, labels)


class AIModelGateway:
    """Routes model tasks without exposing provider clients to business services."""

    def __init__(self, default_provider: AIProvider, task_providers: dict[str, AIProvider] | None = None) -> None:
        self.default_provider = default_provider
        self.task_providers = dict(task_providers or {})

    def _provider(self, task: str) -> AIProvider:
        return self.task_providers.get(task, self.default_provider)

    def generate(self, prompt: str, *, context: dict[str, Any] | None = None) -> str:
        return self._provider("generation").generate(prompt, context=context)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._provider("embedding").embed(texts)

    def rerank(self, query: str, candidates: list[dict[str, Any]], *, limit: int = 20) -> list[dict[str, Any]]:
        return self._provider("reranking").rerank(query, candidates, limit=limit)

    def classify(self, text: str, labels: list[str]) -> dict[str, Any]:
        return self._provider("classification").classify(text, labels)
