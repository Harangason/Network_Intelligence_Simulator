"""Provider-neutral knowledge, retrieval and model abstractions."""

from backend.nis.knowledge.ai_gateway import AIModelGateway
from backend.nis.knowledge.ai_gateway import AIProvider
from backend.nis.knowledge.ai_gateway import LocalAIProvider
from backend.nis.knowledge.entity_resolution import EntityResolutionResult
from backend.nis.knowledge.entity_resolution import EntityResolutionService
from backend.nis.knowledge.ingestion import EngineeringChunk
from backend.nis.knowledge.ingestion import EngineeringChunker
from backend.nis.knowledge.ingestion import KnowledgeIngestionPipeline
from backend.nis.knowledge.industry_rag import IndustryRAGOrchestrator
from backend.nis.knowledge.industry_rag import IndustrySignalRAGProfile
from backend.nis.knowledge.retrieval import EngineeringContextBuilder
from backend.nis.knowledge.retrieval import HybridRetrievalService
from backend.nis.knowledge.retrieval import KnowledgeDocument
from backend.nis.knowledge.sources import PostgresSourceAdapter
from backend.nis.knowledge.sources import RawEntity
from backend.nis.knowledge.sources import RestSourceAdapter
from backend.nis.knowledge.sources import SignalListSourceAdapter
from backend.nis.knowledge.sources import SourceAdapter
from backend.nis.knowledge.sources import SourceAdapterRegistry
from backend.nis.knowledge.sources import SourceIngestionService
from backend.nis.knowledge.sources import SourceRequest
from backend.nis.knowledge.sources import StagedEntity
from backend.nis.knowledge.semantic_vocabulary import EngineeringSemanticVocabulary
from backend.nis.knowledge.semantic_vocabulary import SemanticConcept
from backend.nis.knowledge.stores import GraphStore
from backend.nis.knowledge.stores import LocalGraphStore
from backend.nis.knowledge.stores import LocalVectorStore
from backend.nis.knowledge.stores import VectorStore
from backend.nis.knowledge.transformers import LocalTransformerService
from backend.nis.knowledge.transformers import TransformerService

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
