"""Provider-neutral knowledge, retrieval and model abstractions."""

from .ai_gateway import AIModelGateway, AIProvider, LocalAIProvider
from .entity_resolution import EntityResolutionResult, EntityResolutionService
from .ingestion import EngineeringChunk, EngineeringChunker, KnowledgeIngestionPipeline
from .retrieval import EngineeringContextBuilder, HybridRetrievalService, KnowledgeDocument
from .sources import (
    PostgresSourceAdapter,
    RawEntity,
    RestSourceAdapter,
    SourceAdapter,
    SourceAdapterRegistry,
    SourceIngestionService,
    SourceRequest,
    StagedEntity,
)
from .stores import GraphStore, LocalGraphStore, LocalVectorStore, VectorStore
from .transformers import LocalTransformerService, TransformerService

__all__ = [
    "AIModelGateway",
    "AIProvider",
    "EngineeringContextBuilder",
    "EngineeringChunk",
    "EngineeringChunker",
    "EntityResolutionResult",
    "EntityResolutionService",
    "GraphStore",
    "HybridRetrievalService",
    "KnowledgeDocument",
    "KnowledgeIngestionPipeline",
    "LocalAIProvider",
    "LocalGraphStore",
    "LocalTransformerService",
    "LocalVectorStore",
    "PostgresSourceAdapter",
    "RawEntity",
    "RestSourceAdapter",
    "SourceAdapter",
    "SourceAdapterRegistry",
    "SourceIngestionService",
    "SourceRequest",
    "StagedEntity",
    "TransformerService",
    "VectorStore",
]
