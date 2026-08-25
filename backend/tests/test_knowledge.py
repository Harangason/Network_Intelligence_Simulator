from __future__ import annotations

from backend.knowledge import (
    AIModelGateway,
    EngineeringChunker,
    EngineeringContextBuilder,
    EntityResolutionService,
    HybridRetrievalService,
    KnowledgeDocument,
    KnowledgeIngestionPipeline,
    LocalAIProvider,
    LocalGraphStore,
    LocalTransformerService,
    LocalVectorStore,
)


def test_local_graph_store_supports_traversal_paths_and_subgraphs():
    graph = LocalGraphStore()
    graph.add_node("powertrain", "HardwareNode", {"name": "Powertrain"})
    graph.add_node("battery", "Function", {"name": "Battery Monitoring"})
    graph.add_node("soc", "Signal", {"name": "State of Charge"})
    graph.add_edge("powertrain", "battery", "HAS_FUNCTION", edge_id="e1")
    graph.add_edge("battery", "soc", "PROVIDES", edge_id="e2")

    traversed = graph.traverse("powertrain", max_depth=3)
    assert [(item["node"]["id"], item["distance"]) for item in traversed] == [("battery", 1), ("soc", 2)]
    assert graph.find_path("powertrain", "soc") == {
        "nodes": ["powertrain", "battery", "soc"],
        "edges": ["e1", "e2"],
        "hop_count": 2,
    }
    subgraph = graph.get_subgraph(["powertrain"], depth=2)
    assert {item["id"] for item in subgraph["nodes"]} == {"powertrain", "battery", "soc"}
    assert {item["type"] for item in subgraph["edges"]} == {"HAS_FUNCTION", "PROVIDES"}


def test_local_vector_store_filters_updates_and_deletes():
    store = LocalVectorStore()
    store.add("a", [1, 0], "CAN FD battery status", {"domain": "mobility", "approval_state": "approved"})
    store.add("b", [0, 1], "Ethernet camera", {"domain": "mobility", "approval_state": "draft"})

    result = store.search([1, 0], filters={"approval_state": "approved"})
    assert result[0]["embedding_id"] == "a"
    assert result[0]["score"] == 1.0
    assert store.search_by_metadata({"domain": "mobility"}, limit=10)[1]["embedding_id"] == "b"
    assert store.update("b", metadata={"approval_state": "approved"})["metadata"]["approval_state"] == "approved"
    assert store.delete("a") is True
    assert store.delete("a") is False


def test_local_transformer_is_deterministic_and_reranks_relevant_text():
    transformer = LocalTransformerService(dimensions=64)
    assert transformer.embed(["Battery status"])[0] == transformer.embed(["Battery status"])[0]
    ranked = transformer.rerank(
        "battery status",
        [
            {"object_id": "camera", "text": "front camera stream", "score": 0.2},
            {"object_id": "battery", "text": "battery status and state of charge", "score": 0.2},
        ],
    )
    assert ranked[0]["object_id"] == "battery"
    assert transformer.classify("CAN FD frame", ["Ethernet", "CAN FD"])["label"] == "CAN FD"


def test_hybrid_retrieval_combines_vector_keyword_metadata_and_multihop_graph():
    service = HybridRetrievalService(transformer=LocalTransformerService(dimensions=96))
    service.index(
        KnowledgeDocument(
            object_id="powertrain",
            object_type="HardwareNode",
            text="Powertrain controller",
            source_id="manual-model",
            domain="mobility",
            approval_state="approved",
            source_quality=1.0,
        )
    )
    service.index(
        KnowledgeDocument(
            object_id="battery-function",
            object_type="Function",
            text="Battery monitoring and energy management",
            source_id="approved-library",
            domain="mobility",
            approval_state="approved",
            source_quality=0.95,
        )
    )
    service.index(
        KnowledgeDocument(
            object_id="battery-soc",
            object_type="Signal",
            text="Battery state of charge status signal",
            source_id="dbc-import",
            domain="mobility",
            technology="CAN_FD",
            approval_state="validated",
            evidence=({"source": "battery.dbc", "line": 41},),
        )
    )
    service.add_relation("powertrain", "battery-function", "HAS_FUNCTION", relation_id="r1")
    service.add_relation("battery-function", "battery-soc", "PROVIDES", relation_id="r2")

    results = service.retrieve(
        "battery status signal",
        selected_object_ids=["powertrain"],
        filters={"domain": "mobility"},
        graph_depth=3,
    )
    signal = next(item for item in results if item["object_id"] == "battery-soc")
    assert {"vector", "keyword", "metadata", "graph"}.issubset(signal["retrieval_sources"])
    assert signal["graph_path"] == ["powertrain", "battery-function", "battery-soc"]
    assert signal["evidence"] == [{"source": "battery.dbc", "line": 41}]
    assert signal["metadata"]["embedding_model"] == "local-hashed-engineering-embedding-v1"


def test_context_builder_prioritizes_selected_objects_and_respects_budget():
    context = EngineeringContextBuilder().build(
        "status",
        [
            {"object_id": "history", "object_type": "SimulationRun", "score": 0.99, "text": "x" * 2000},
            {"object_id": "selected", "object_type": "HardwareNode", "score": 0.4, "text": "selected node"},
        ],
        selected_object_ids=["selected"],
        max_characters=500,
    )
    assert context["items"][0]["object_id"] == "selected"
    assert context["truncated"] is True


def test_entity_resolution_never_auto_merges_semantic_or_possible_matches():
    resolver = EntityResolutionService(aliases={"PowertrainController": {"PT_ECU"}})
    candidates = [{"id": "p1", "name": "PowertrainController"}]
    assert resolver.resolve("Powertrain Controller", candidates).match_type == "EXACT_MATCH"
    assert resolver.resolve("PT_ECU", candidates).match_type == "ALIAS_MATCH"
    semantic = resolver.resolve("Powertrain control", candidates)
    assert semantic.match_type in {"SEMANTIC_MATCH", "POSSIBLE_MATCH"}
    assert semantic.auto_merge_allowed is False
    assert resolver.resolve("Weather Station", candidates).match_type == "NEW_ENTITY"


def test_ai_model_gateway_routes_small_model_tasks_without_provider_coupling():
    provider = LocalAIProvider(
        LocalTransformerService(dimensions=64),
        generation_callback=lambda prompt, context: f"proposal:{prompt}:{context['project']}",
    )
    gateway = AIModelGateway(provider)
    assert gateway.generate("route", context={"project": "demo"}) == "proposal:route:demo"
    assert len(gateway.embed(["signal"])[0]) == 64
    assert gateway.classify("CAN frame", ["CAN", "Ethernet"])["label"] == "CAN"


def test_ingestion_chunks_documents_and_imports_per_engineering_object():
    chunker = EngineeringChunker(max_characters=240)
    documents = chunker.document_chunks(
        source_id="requirements.md",
        text="# Battery\n\nBattery status requirements.\n\n# Display\n\nDisplay consumer requirements.",
    )
    plan_chunks = chunker.import_plan_chunks(
        {
            "import_id": "import-1",
            "hardware_nodes": [{"key": "node-1", "name": "Powertrain"}],
            "messages": [{"key": "message-1", "name": "BatteryStatus"}],
            "signals": [{"key": "signal-1", "name": "StateOfCharge"}],
        }
    )
    assert len(documents) == 4
    assert {item.object_type for item in plan_chunks} == {"HardwareNode", "Message", "Signal"}

    retrieval = HybridRetrievalService(transformer=LocalTransformerService(dimensions=64))
    indexed = KnowledgeIngestionPipeline(retrieval).ingest(plan_chunks)
    assert len(indexed) == 3
    assert retrieval.retrieve("state of charge")[0]["object_id"] == "signal-1"
