"""Hybrid vector, keyword, metadata and GraphRAG context for route proposals."""

from __future__ import annotations

from typing import Any

from backend.knowledge import HybridRetrievalService, KnowledgeDocument

from ..db import get_connection


class HybridRoutingRetriever:
    """Rebuilds a bounded local index from canonical source-of-truth records."""

    ENTITY_TABLES = (
        ("hardware_node", "engineering_hardware_nodes"),
        ("function", "engineering_functions"),
        ("interface", "engineering_interfaces"),
        ("message", "engineering_messages"),
        ("signal", "engineering_signals"),
    )

    def retrieve(
        self,
        *,
        query: str,
        graph_paths: list[dict[str, Any]],
        target_ids: list[str],
        protocol: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        service = HybridRetrievalService()
        indexed_ids: set[str] = set()
        with get_connection() as connection:
            for object_type, table in self.ENTITY_TABLES:
                rows = connection.execute(
                    f"SELECT id, name, description, domain, source, approval_state, version, created_at FROM {table} "
                    "ORDER BY modified_at DESC LIMIT 500"
                ).fetchall()
                for row in rows:
                    object_id = str(row["id"])
                    service.index(
                        KnowledgeDocument(
                            object_id=object_id,
                            object_type=object_type,
                            text=" ".join(
                                value
                                for value in (
                                    str(row.get("name") or ""),
                                    str(row.get("description") or ""),
                                    str(row.get("domain") or ""),
                                )
                                if value
                            ),
                            source_id=str(row.get("source") or "canonical_engineering_model"),
                            domain=row.get("domain"),
                            technology=(row.get("interface_type") if object_type == "interface" else None),
                            version=str(row.get("version") or "v1"),
                            approval_state=str(row.get("approval_state") or "draft"),
                            created_at=str(row.get("created_at") or ""),
                            knowledge_level=(
                                "L4_APPROVED" if str(row.get("approval_state") or "").lower() == "approved" else "L2_NORMALIZED"
                            ),
                            source_quality=1.0 if str(row.get("source") or "").lower() == "manual" else 0.75,
                            evidence=({"table": table, "object_id": object_id},),
                        )
                    )
                    indexed_ids.add(object_id)

            relations = connection.execute(
                "SELECT id, source_id, target_id, relation_type, attributes AS properties FROM engineering_relations LIMIT 3000"
            ).fetchall()
            approved_routes = connection.execute(
                "SELECT id, route_code, name, source, payload, destinations, route, timing, created_at "
                "FROM engineering_routing_entries WHERE approval_state = 'APPROVED' "
                "ORDER BY approved_at DESC NULLS LAST LIMIT 50"
            ).fetchall()

        for relation in relations:
            source_id = str(relation["source_id"])
            target_id = str(relation["target_id"])
            if source_id in indexed_ids and target_id in indexed_ids:
                service.add_relation(
                    source_id,
                    target_id,
                    str(relation["relation_type"]),
                    properties=relation.get("properties") or {},
                    relation_id=str(relation["id"]),
                )

        for route in approved_routes:
            route_id = str(route["id"])
            service.index(
                KnowledgeDocument(
                    object_id=route_id,
                    object_type="RoutingEntry",
                    text=f"{route['route_code']} {route['name']} {route['source']} {route['payload']} {route['destinations']} {route['route']} {route['timing']}",
                    source_id="approved_route_history",
                    version="v1",
                    approval_state="approved",
                    created_at=str(route.get("created_at") or ""),
                    knowledge_level="L4_APPROVED",
                    source_quality=0.95,
                    evidence=({"route_id": route_id, "route_code": route["route_code"]},),
                )
            )

        retrieved = service.retrieve(
            query,
            selected_object_ids=[target for target in target_ids if target in indexed_ids],
            filters=None,
            graph_depth=3,
            limit=limit,
        )
        context: list[dict[str, Any]] = [
            {
                "source": "knowledge_graph",
                "retrieval_sources": ["graph"],
                "paths": graph_paths,
                "score": max((float(path.get("score", 0)) for path in graph_paths), default=0.0),
                "reason": "Candidate network paths from the canonical engineering graph.",
                "evidence": [],
            },
            {
                "source": "protocol_rules",
                "retrieval_sources": ["metadata"],
                "protocol": protocol or "CUSTOM",
                "rule": "Endpoints require compatible protocols or an explicit gateway transformation.",
                "score": 0.9,
                "reason": "Technology-specific routing guardrail.",
                "evidence": [],
            },
        ]
        context.extend(retrieved)
        return context
