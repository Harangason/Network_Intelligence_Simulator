"""Adapter from the canonical PostgreSQL model to provider-neutral knowledge services."""

from __future__ import annotations

from typing import Any

from backend.knowledge import EngineeringContextBuilder, HybridRetrievalService, KnowledgeDocument

from .db import get_connection


class CanonicalKnowledgeService:
    ENTITY_TABLES = (
        ("HardwareNode", "engineering_hardware_nodes", ""),
        ("Function", "engineering_functions", ""),
        ("Interface", "engineering_interfaces", ", interface_type"),
        ("Message", "engineering_messages", ""),
        ("Signal", "engineering_signals", ""),
    )

    def build(self) -> HybridRetrievalService:
        service = HybridRetrievalService()
        indexed_ids: set[str] = set()
        with get_connection() as connection:
            for object_type, table, extra_columns in self.ENTITY_TABLES:
                rows = connection.execute(
                    f"SELECT id, name, description, domain, source, approval_state, version, created_at{extra_columns} "
                    f"FROM {table} ORDER BY modified_at DESC LIMIT 1000"
                ).fetchall()
                for row in rows:
                    object_id = str(row["id"])
                    technology = row.get("interface_type")
                    service.index(
                        KnowledgeDocument(
                            object_id=object_id,
                            object_type=object_type,
                            text=" ".join(
                                part
                                for part in (
                                    str(row.get("name") or ""),
                                    str(row.get("description") or ""),
                                    str(row.get("domain") or ""),
                                    str(technology or ""),
                                )
                                if part
                            ),
                            source_id=str(row.get("source") or "canonical_engineering_model"),
                            domain=row.get("domain"),
                            technology=technology,
                            version=str(row.get("version") or "v1"),
                            approval_state=str(row.get("approval_state") or "draft"),
                            created_at=str(row.get("created_at") or ""),
                            knowledge_level=(
                                "L4_APPROVED"
                                if str(row.get("approval_state") or "").lower() == "approved"
                                else "L3_VALIDATED"
                                if str(row.get("review_state") or "").lower() == "reviewed"
                                else "L2_NORMALIZED"
                            ),
                            source_quality=1.0 if str(row.get("source") or "").lower() == "manual" else 0.75,
                            evidence=({"table": table, "object_id": object_id, "version": row.get("version")},),
                        )
                    )
                    indexed_ids.add(object_id)
            relations = connection.execute(
                "SELECT id, source_id, target_id, relation_type, attributes AS properties "
                "FROM engineering_relations ORDER BY created_at DESC LIMIT 5000"
            ).fetchall()

        for relation in relations:
            source_id = str(relation["source_id"])
            target_id = str(relation["target_id"])
            if source_id not in indexed_ids or target_id not in indexed_ids:
                continue
            service.add_relation(
                source_id,
                target_id,
                str(relation["relation_type"]),
                properties=relation.get("properties") or {},
                relation_id=str(relation["id"]),
            )
        return service

    def search(
        self,
        query: str,
        *,
        selected_object_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        service = self.build()
        items = service.retrieve(
            query,
            selected_object_ids=selected_object_ids,
            filters=filters,
            graph_depth=3,
            limit=limit,
        )
        return {
            "query": query,
            "items": items,
            "count": len(items),
            "context": EngineeringContextBuilder().build(
                query,
                items,
                selected_object_ids=selected_object_ids,
            ),
            "pipeline": [
                "keyword",
                "vector",
                "metadata",
                "graph",
                "merge",
                "deduplicate",
                "rerank",
                "graph_expand",
                "context_build",
            ],
        }

    def subgraph(self, object_ids: list[str], *, depth: int = 2) -> dict[str, Any]:
        service = self.build()
        graph = service.graph.get_subgraph(object_ids, depth=depth)
        return {**graph, "root_ids": object_ids, "depth": depth}
