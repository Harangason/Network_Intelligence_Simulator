"""Hybrid vector, keyword, metadata and multi-hop graph retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import re
from typing import Any

from .stores import GraphStore, LocalGraphStore, LocalVectorStore, VectorStore
from .transformers import LocalTransformerService, TransformerService


APPROVAL_WEIGHTS = {
    "released": 1.0,
    "approved": 0.95,
    "validated": 0.85,
    "reviewed": 0.8,
    "pending": 0.65,
    "draft": 0.55,
    "imported": 0.45,
    "raw": 0.35,
    "ai_generated": 0.3,
}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1}


@dataclass(frozen=True)
class KnowledgeDocument:
    object_id: str
    object_type: str
    text: str
    source_id: str
    domain: str | None = None
    technology: str | None = None
    version: str = "v1"
    approval_state: str = "draft"
    language: str = "de"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    knowledge_level: str = "L2_NORMALIZED"
    source_quality: float = 0.7
    evidence: tuple[dict[str, Any], ...] = ()
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def embedding_id(self) -> str:
        return f"{self.object_type}:{self.object_id}:{self.version}"

    def metadata(self, embedding_model: str) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("text")
        extra_metadata = payload.pop("extra_metadata")
        payload["embedding_id"] = self.embedding_id
        payload["embedding_model"] = embedding_model
        payload["evidence"] = [dict(item) for item in self.evidence]
        for key, value in extra_metadata.items():
            if key not in payload and key != "text":
                payload[key] = value
        return payload


class HybridRetrievalService:
    """Runs the mandatory hybrid pipeline and returns compact evidence records."""

    def __init__(
        self,
        *,
        graph_store: GraphStore | None = None,
        vector_store: VectorStore | None = None,
        transformer: TransformerService | None = None,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.graph = graph_store or LocalGraphStore()
        self.vectors = vector_store or LocalVectorStore()
        self.transformer = transformer or LocalTransformerService()
        self.weights = {
            "semantic": 0.36,
            "keyword": 0.2,
            "graph": 0.18,
            "approval": 0.1,
            "source_quality": 0.06,
            "domain": 0.04,
            "technology": 0.04,
            "version": 0.02,
            **(weights or {}),
        }

    def index(self, document: KnowledgeDocument) -> dict[str, Any]:
        metadata = document.metadata(self.transformer.model_name)
        vector = self.transformer.embed([document.text])[0]
        record = self.vectors.add(document.embedding_id, vector, document.text, metadata)
        properties = {**metadata, "text": document.text}
        self.graph.add_node(document.object_id, document.object_type, properties)
        return record

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        *,
        properties: dict[str, Any] | None = None,
        relation_id: str | None = None,
    ) -> dict[str, Any]:
        return self.graph.add_edge(
            source_id,
            target_id,
            relation_type,
            properties,
            edge_id=relation_id,
        )

    @staticmethod
    def _candidate(record: dict[str, Any], source: str, score: float, reason: str) -> dict[str, Any]:
        metadata = dict(record.get("metadata") or record.get("properties") or {})
        object_id = str(metadata.get("object_id") or record.get("id") or "")
        return {
            "object_id": object_id,
            "object_type": metadata.get("object_type") or record.get("type") or "Knowledge",
            "text": record.get("text") or metadata.get("text") or "",
            "metadata": metadata,
            "score_parts": {source: max(0.0, min(1.0, float(score)))},
            "retrieval_sources": [source],
            "reasons": [reason],
        }

    @staticmethod
    def _merge(target: dict[str, dict[str, Any]], candidate: dict[str, Any]) -> None:
        object_id = candidate["object_id"]
        if not object_id:
            return
        current = target.get(object_id)
        if current is None:
            target[object_id] = candidate
            return
        current["score_parts"].update(candidate["score_parts"])
        current["retrieval_sources"] = sorted(set(current["retrieval_sources"] + candidate["retrieval_sources"]))
        current["reasons"].extend(reason for reason in candidate["reasons"] if reason not in current["reasons"])
        if candidate.get("graph_path") and not current.get("graph_path"):
            current["graph_path"] = candidate["graph_path"]
            current["graph_edges"] = candidate.get("graph_edges", [])

    def retrieve(
        self,
        query: str,
        *,
        selected_object_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        graph_depth: int = 3,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query_tokens = _tokens(query)
        query_vector = self.transformer.embed([query])[0]
        merged: dict[str, dict[str, Any]] = {}

        for record in self.vectors.search(query_vector, limit=max(limit * 3, 30), filters=filters):
            self._merge(merged, self._candidate(record, "vector", record["score"], "Semantic vector similarity."))

        records = self.vectors.search_by_metadata({}, limit=2000)
        for record in records:
            text_tokens = _tokens(record["text"])
            lexical = len(query_tokens & text_tokens) / max(1, len(query_tokens))
            if lexical:
                self._merge(merged, self._candidate(record, "keyword", lexical, "Engineering keyword overlap."))

        if filters:
            for record in self.vectors.search_by_metadata(filters, limit=max(limit * 3, 30)):
                self._merge(merged, self._candidate(record, "metadata", 1.0, "Requested metadata filters match."))

        seeds = list(dict.fromkeys(selected_object_ids or []))
        seeds.extend(item["id"] for item in self.graph.search_entities(query, limit=10) if item["id"] not in seeds)
        for seed in seeds:
            node_matches = self.graph.get_subgraph([seed], depth=0)["nodes"]
            for node in node_matches:
                self._merge(merged, self._candidate(node, "graph", 1.0, "Explicitly selected graph object."))
            for item in self.graph.traverse(seed, max_depth=graph_depth):
                graph_score = 1.0 / (1.0 + float(item["distance"]))
                candidate = self._candidate(
                    item["node"],
                    "graph",
                    graph_score,
                    f"Multi-hop graph neighbor at distance {item['distance']} via {item['edge']['type']}.",
                )
                candidate["graph_path"] = item["path"]
                candidate["graph_edges"] = item["edge_path"]
                self._merge(merged, candidate)

        candidates = []
        for candidate in merged.values():
            metadata = candidate["metadata"]
            parts = candidate["score_parts"]
            approval = APPROVAL_WEIGHTS.get(str(metadata.get("approval_state") or "draft").lower(), 0.5)
            source_quality = max(0.0, min(1.0, float(metadata.get("source_quality") or 0.5)))
            domain = 1.0 if filters and filters.get("domain") == metadata.get("domain") else 0.0
            technology = 1.0 if filters and filters.get("technology") == metadata.get("technology") else 0.0
            version = 1.0 if metadata.get("version") else 0.0
            score = (
                parts.get("vector", 0.0) * self.weights["semantic"]
                + parts.get("keyword", 0.0) * self.weights["keyword"]
                + parts.get("graph", 0.0) * self.weights["graph"]
                + approval * self.weights["approval"]
                + source_quality * self.weights["source_quality"]
                + domain * self.weights["domain"]
                + technology * self.weights["technology"]
                + version * self.weights["version"]
            )
            candidates.append({**candidate, "score": round(score, 8)})

        reranked = self.transformer.rerank(query, candidates, limit=limit)
        return [
            {
                "object_id": item["object_id"],
                "object_type": item["object_type"],
                "score": item["score"],
                "retrieval_sources": item["retrieval_sources"],
                "source": item["metadata"].get("source_id"),
                "reason": " ".join(item["reasons"]),
                "evidence": item["metadata"].get("evidence") or [],
                "text": item["text"],
                "metadata": item["metadata"],
                **({"graph_path": item["graph_path"]} if item.get("graph_path") else {}),
            }
            for item in reranked
        ]


class EngineeringContextBuilder:
    """Builds a bounded, priority-ordered prompt context from retrieval evidence."""

    TYPE_PRIORITY = {
        "HardwareNode": 1,
        "hardware_node": 1,
        "Function": 2,
        "function": 2,
        "Interface": 3,
        "interface": 3,
        "Signal": 4,
        "signal": 4,
        "Requirement": 5,
        "Protocol": 6,
        "Document": 8,
        "SimulationRun": 9,
    }

    def build(
        self,
        query: str,
        retrieved: list[dict[str, Any]],
        *,
        selected_object_ids: list[str] | None = None,
        max_items: int = 16,
        max_characters: int = 12000,
    ) -> dict[str, Any]:
        selected = set(selected_object_ids or [])
        ranked = sorted(
            retrieved,
            key=lambda item: (
                0 if item.get("object_id") in selected else 1,
                self.TYPE_PRIORITY.get(str(item.get("object_type")), 7),
                -float(item.get("score") or 0),
            ),
        )
        items = []
        used = 0
        for item in ranked[:max_items]:
            compact = {
                "object_id": item.get("object_id"),
                "object_type": item.get("object_type"),
                "score": item.get("score"),
                "reason": item.get("reason"),
                "text": str(item.get("text") or "")[:1600],
                "evidence": item.get("evidence") or [],
            }
            length = len(str(compact))
            if items and used + length > max_characters:
                break
            items.append(compact)
            used += length
        return {
            "query": query,
            "selected_object_ids": list(selected),
            "items": items,
            "item_count": len(items),
            "truncated": len(items) < len(retrieved),
            "character_budget": max_characters,
        }
