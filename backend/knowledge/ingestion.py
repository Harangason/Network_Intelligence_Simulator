"""Engineering-aware chunking and indexing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from .retrieval import HybridRetrievalService, KnowledgeDocument


@dataclass(frozen=True)
class EngineeringChunk:
    chunk_id: str
    object_id: str
    object_type: str
    text: str
    source_id: str
    metadata: dict[str, Any]


class EngineeringChunker:
    """Chunks documents by section and structured data by engineering entity."""

    def __init__(self, max_characters: int = 1600) -> None:
        if max_characters < 200:
            raise ValueError("max_characters must be at least 200.")
        self.max_characters = max_characters

    def document_chunks(
        self,
        *,
        source_id: str,
        text: str,
        object_type: str = "Document",
        metadata: dict[str, Any] | None = None,
    ) -> list[EngineeringChunk]:
        sections = [part.strip() for part in re.split(r"\n(?=#{1,6}\s)|\n\s*\n", text) if part.strip()]
        chunks: list[EngineeringChunk] = []
        index = 0
        for section in sections:
            paragraphs = [section[offset : offset + self.max_characters] for offset in range(0, len(section), self.max_characters)]
            for paragraph in paragraphs:
                chunk_id = f"{source_id}:section:{index}"
                chunks.append(
                    EngineeringChunk(
                        chunk_id=chunk_id,
                        object_id=chunk_id,
                        object_type=object_type,
                        text=paragraph,
                        source_id=source_id,
                        metadata={**(metadata or {}), "chunk_kind": "section", "chunk_index": index},
                    )
                )
                index += 1
        return chunks

    def entity_chunks(
        self,
        entities: Iterable[dict[str, Any]],
        *,
        source_id: str,
        object_type: str,
    ) -> list[EngineeringChunk]:
        chunks = []
        for index, entity in enumerate(entities):
            object_id = str(entity.get("id") or entity.get("key") or f"{object_type}:{index}")
            text = " ".join(
                f"{key}: {value}"
                for key, value in entity.items()
                if value not in (None, "", [], {}) and key not in {"provenance", "raw"}
            )
            chunks.append(
                EngineeringChunk(
                    chunk_id=f"{source_id}:{object_type}:{object_id}",
                    object_id=object_id,
                    object_type=object_type,
                    text=text[: self.max_characters],
                    source_id=source_id,
                    metadata={"chunk_kind": "engineering_object", **dict(entity.get("metadata") or {})},
                )
            )
        return chunks

    def import_plan_chunks(self, plan: dict[str, Any]) -> list[EngineeringChunk]:
        mapping = {
            "hardware_nodes": "HardwareNode",
            "functions": "Function",
            "interfaces": "Interface",
            "messages": "Message",
            "signals": "Signal",
        }
        source_id = str(plan.get("import_id") or plan.get("file_name") or "engineering-import")
        return [
            chunk
            for key, object_type in mapping.items()
            for chunk in self.entity_chunks(plan.get(key) or [], source_id=source_id, object_type=object_type)
        ]


class KnowledgeIngestionPipeline:
    """Normalizes chunks into vector and graph indexes without changing the source model."""

    def __init__(self, retrieval: HybridRetrievalService) -> None:
        self.retrieval = retrieval

    def ingest(self, chunks: Iterable[EngineeringChunk]) -> list[dict[str, Any]]:
        indexed = []
        for chunk in chunks:
            metadata = chunk.metadata
            indexed.append(
                self.retrieval.index(
                    KnowledgeDocument(
                        object_id=chunk.object_id,
                        object_type=chunk.object_type,
                        text=chunk.text,
                        source_id=chunk.source_id,
                        domain=metadata.get("domain"),
                        technology=metadata.get("technology"),
                        version=str(metadata.get("version") or "v1"),
                        approval_state=str(metadata.get("approval_state") or "imported"),
                        language=str(metadata.get("language") or "de"),
                        knowledge_level=str(metadata.get("knowledge_level") or "L1_IMPORTED"),
                        source_quality=float(metadata.get("source_quality") or 0.55),
                        evidence=tuple(metadata.get("evidence") or ()),
                    )
                )
            )
        return indexed
