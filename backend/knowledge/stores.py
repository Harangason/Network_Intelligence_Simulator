"""Replaceable graph and vector-store contracts with local implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict, deque
from copy import deepcopy
from math import sqrt
from threading import RLock
from typing import Any
from uuid import uuid4


class GraphStore(ABC):
    """Database-neutral graph operations used by GraphRAG."""

    @abstractmethod
    def add_node(self, node_id: str, node_type: str, properties: dict[str, Any] | None = None) -> dict[str, Any]: ...

    @abstractmethod
    def update_node(self, node_id: str, properties: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def delete_node(self, node_id: str) -> bool: ...

    @abstractmethod
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
        *,
        edge_id: str | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def remove_edge(self, edge_id: str) -> bool: ...

    @abstractmethod
    def get_neighbors(
        self,
        node_id: str,
        *,
        direction: str = "both",
        edge_types: set[str] | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def traverse(
        self,
        start_id: str,
        *,
        max_depth: int = 2,
        edge_types: set[str] | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def find_path(self, source_id: str, target_id: str, *, max_depth: int = 8) -> dict[str, Any] | None: ...

    @abstractmethod
    def search_entities(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_subgraph(self, node_ids: list[str], *, depth: int = 1) -> dict[str, list[dict[str, Any]]]: ...


class LocalGraphStore(GraphStore):
    """Thread-safe in-memory graph suitable for local development and tests."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[str, dict[str, Any]] = {}
        self._outgoing: dict[str, set[str]] = defaultdict(set)
        self._incoming: dict[str, set[str]] = defaultdict(set)
        self._lock = RLock()

    def add_node(self, node_id: str, node_type: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            node = {"id": str(node_id), "type": str(node_type), "properties": deepcopy(properties or {})}
            self._nodes[node["id"]] = node
            return deepcopy(node)

    def update_node(self, node_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if node_id not in self._nodes:
                raise KeyError(node_id)
            self._nodes[node_id]["properties"].update(deepcopy(properties))
            return deepcopy(self._nodes[node_id])

    def delete_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False
            for edge_id in list(self._outgoing[node_id] | self._incoming[node_id]):
                self.remove_edge(edge_id)
            self._outgoing.pop(node_id, None)
            self._incoming.pop(node_id, None)
            del self._nodes[node_id]
            return True

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
        *,
        edge_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if source_id not in self._nodes or target_id not in self._nodes:
                raise KeyError("Both edge endpoints must exist before an edge is added.")
            edge = {
                "id": edge_id or str(uuid4()),
                "source_id": source_id,
                "target_id": target_id,
                "type": str(edge_type),
                "properties": deepcopy(properties or {}),
            }
            previous = self._edges.get(edge["id"])
            if previous:
                self._outgoing[previous["source_id"]].discard(edge["id"])
                self._incoming[previous["target_id"]].discard(edge["id"])
            self._edges[edge["id"]] = edge
            self._outgoing[source_id].add(edge["id"])
            self._incoming[target_id].add(edge["id"])
            return deepcopy(edge)

    def remove_edge(self, edge_id: str) -> bool:
        with self._lock:
            edge = self._edges.pop(edge_id, None)
            if edge is None:
                return False
            self._outgoing[edge["source_id"]].discard(edge_id)
            self._incoming[edge["target_id"]].discard(edge_id)
            return True

    def get_neighbors(
        self,
        node_id: str,
        *,
        direction: str = "both",
        edge_types: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if direction not in {"both", "out", "in"}:
            raise ValueError("direction must be 'both', 'out' or 'in'.")
        with self._lock:
            edge_ids: set[str] = set()
            if direction in {"both", "out"}:
                edge_ids.update(self._outgoing.get(node_id, set()))
            if direction in {"both", "in"}:
                edge_ids.update(self._incoming.get(node_id, set()))
            result = []
            for edge_id in sorted(edge_ids):
                edge = self._edges[edge_id]
                if edge_types and edge["type"] not in edge_types:
                    continue
                neighbor_id = edge["target_id"] if edge["source_id"] == node_id else edge["source_id"]
                result.append({"node": deepcopy(self._nodes[neighbor_id]), "edge": deepcopy(edge)})
            return result

    def traverse(
        self,
        start_id: str,
        *,
        max_depth: int = 2,
        edge_types: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        if start_id not in self._nodes:
            return []
        queue = deque([(start_id, 0, [start_id], [])])
        seen = {start_id}
        result = []
        while queue:
            node_id, depth, path, path_edges = queue.popleft()
            if depth >= max_depth:
                continue
            for item in self.get_neighbors(node_id, edge_types=edge_types):
                neighbor_id = item["node"]["id"]
                if neighbor_id in seen:
                    continue
                seen.add(neighbor_id)
                edge_id = item["edge"]["id"]
                entry = {
                    "node": item["node"],
                    "edge": item["edge"],
                    "distance": depth + 1,
                    "path": [*path, neighbor_id],
                    "edge_path": [*path_edges, edge_id],
                }
                result.append(entry)
                queue.append((neighbor_id, depth + 1, entry["path"], entry["edge_path"]))
        return result

    def find_path(self, source_id: str, target_id: str, *, max_depth: int = 8) -> dict[str, Any] | None:
        if source_id not in self._nodes or target_id not in self._nodes:
            return None
        if source_id == target_id:
            return {"nodes": [source_id], "edges": [], "hop_count": 0}
        queue = deque([(source_id, [source_id], [])])
        seen = {source_id}
        while queue:
            current, nodes, edges = queue.popleft()
            if len(edges) >= max_depth:
                continue
            for item in self.get_neighbors(current):
                neighbor_id = item["node"]["id"]
                if neighbor_id in seen:
                    continue
                next_nodes = [*nodes, neighbor_id]
                next_edges = [*edges, item["edge"]["id"]]
                if neighbor_id == target_id:
                    return {"nodes": next_nodes, "edges": next_edges, "hop_count": len(next_edges)}
                seen.add(neighbor_id)
                queue.append((neighbor_id, next_nodes, next_edges))
        return None

    def search_entities(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        terms = {term for term in query.lower().replace("_", " ").split() if term}
        matches = []
        with self._lock:
            for node in self._nodes.values():
                haystack = f"{node['type']} {' '.join(map(str, node['properties'].values()))}".lower()
                score = sum(term in haystack for term in terms) / max(1, len(terms))
                if score:
                    matches.append({**deepcopy(node), "score": round(score, 6)})
        return sorted(matches, key=lambda item: (-item["score"], item["id"]))[:limit]

    def get_subgraph(self, node_ids: list[str], *, depth: int = 1) -> dict[str, list[dict[str, Any]]]:
        selected = {node_id for node_id in node_ids if node_id in self._nodes}
        for node_id in list(selected):
            selected.update(item["node"]["id"] for item in self.traverse(node_id, max_depth=depth))
        with self._lock:
            nodes = [deepcopy(self._nodes[node_id]) for node_id in sorted(selected)]
            edges = [
                deepcopy(edge)
                for edge in self._edges.values()
                if edge["source_id"] in selected and edge["target_id"] in selected
            ]
        return {"nodes": nodes, "edges": edges}


class VectorStore(ABC):
    """Provider-neutral vector index contract."""

    @abstractmethod
    def add(self, embedding_id: str, vector: list[float], text: str, metadata: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def update(
        self,
        embedding_id: str,
        *,
        vector: list[float] | None = None,
        text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def delete(self, embedding_id: str) -> bool: ...

    @abstractmethod
    def search(
        self,
        vector: list[float],
        *,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def search_by_metadata(self, filters: dict[str, Any], *, limit: int = 100) -> list[dict[str, Any]]: ...


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    denominator = sqrt(sum(value * value for value in left)) * sqrt(sum(value * value for value in right))
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / denominator


class LocalVectorStore(VectorStore):
    """Thread-safe exact cosine index; adapters may replace it with pgvector/Qdrant/FAISS."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def add(self, embedding_id: str, vector: list[float], text: str, metadata: dict[str, Any]) -> dict[str, Any]:
        if not vector:
            raise ValueError("A non-empty vector is required.")
        record = {
            "embedding_id": str(embedding_id),
            "vector": [float(value) for value in vector],
            "text": str(text),
            "metadata": deepcopy(metadata),
        }
        with self._lock:
            self._records[record["embedding_id"]] = record
        return deepcopy(record)

    def update(
        self,
        embedding_id: str,
        *,
        vector: list[float] | None = None,
        text: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if embedding_id not in self._records:
                raise KeyError(embedding_id)
            record = self._records[embedding_id]
            if vector is not None:
                if not vector:
                    raise ValueError("A non-empty vector is required.")
                record["vector"] = [float(value) for value in vector]
            if text is not None:
                record["text"] = str(text)
            if metadata is not None:
                record["metadata"].update(deepcopy(metadata))
            return deepcopy(record)

    def delete(self, embedding_id: str) -> bool:
        with self._lock:
            return self._records.pop(embedding_id, None) is not None

    @staticmethod
    def _matches(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
        return all(metadata.get(key) == value for key, value in (filters or {}).items())

    def search(
        self,
        vector: list[float],
        *,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            matches = [
                {**deepcopy(record), "score": round(_cosine(vector, record["vector"]), 8)}
                for record in self._records.values()
                if self._matches(record["metadata"], filters)
            ]
        return sorted(matches, key=lambda item: (-item["score"], item["embedding_id"]))[:limit]

    def search_by_metadata(self, filters: dict[str, Any], *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            matches = [deepcopy(record) for record in self._records.values() if self._matches(record["metadata"], filters)]
        return sorted(matches, key=lambda item: item["embedding_id"])[:limit]
