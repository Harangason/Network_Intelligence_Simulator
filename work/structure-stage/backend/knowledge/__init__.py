"""Provider-neutral knowledge, retrieval and model abstractions."""

from backend.knowledge.ai_gateway import AIModelGateway, AIProvider, LocalAIProvider
from backend.knowledge.entity_resolution import EntityResolutionResult, EntityResolutionService
from backend.knowledge.ingestion import EngineeringChunk, EngineeringChunker, KnowledgeIngestionPipeline
from backend.knowledge.industry_rag import IndustryRAGOrchestrator, IndustrySignalRAGProfile
from backend.knowledge.retrieval import EngineeringContextBuilder, HybridRetrievalService, KnowledgeDocument
from backend.knowledge.sources import PostgresSourceAdapter, RawEntity, RestSourceAdapter, SignalListSourceAdapter, SourceAdapter, SourceAdapterRegistry, SourceIngestionService, SourceRequest, StagedEntity
from backend.knowledge.semantic_vocabulary import EngineeringSemanticVocabulary, SemanticConcept
from backend.knowledge.stores import GraphStore, LocalGraphStore, LocalVectorStore, VectorStore
from backend.knowledge.transformers import LocalTransformerService, TransformerService

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
