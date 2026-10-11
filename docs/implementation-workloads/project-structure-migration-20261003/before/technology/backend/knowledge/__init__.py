"""Provider-neutral knowledge, retrieval and model abstractions."""

from .ai_gateway import AIModelGateway, AIProvider, LocalAIProvider
from .entity_resolution import EntityResolutionResult, EntityResolutionService
from .ingestion import EngineeringChunk, EngineeringChunker, KnowledgeIngestionPipeline
from .industry_rag import IndustryRAGOrchestrator, IndustrySignalRAGProfile
from .retrieval import EngineeringContextBuilder, HybridRetrievalService, KnowledgeDocument
from .sources import (
    PostgresSourceAdapter,
    RawEntity,
    RestSourceAdapter,
    SignalListSourceAdapter,
    SourceAdapter,
    SourceAdapterRegistry,
    SourceIngestionService,
    SourceRequest,
    StagedEntity,
)
from .semantic_vocabulary import EngineeringSemanticVocabulary, SemanticConcept
from .stores import GraphStore, LocalGraphStore, LocalVectorStore, VectorStore
from .transformers import LocalTransformerService, TransformerService

__all__ = [
    "AIModelGateway",
    "AIProvider",
    "EngineeringContextBuilder",
    "EngineeringSemanticVocabulary",
    "EngineeringChunk",
    "EngineeringChunker",
    "IndustryRAGOrchestrator",
    "IndustrySignalRAGProfile",
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
    "SignalListSourceAdapter",
    "SourceAdapter",
    "SourceAdapterRegistry",
    "SourceIngestionService",
    "SourceRequest",
    "StagedEntity",
    "SemanticConcept",
    "TransformerService",
    "VectorStore",
]
