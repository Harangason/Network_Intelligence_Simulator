# RAG Architecture

## Pipeline

```text
query -> intent -> keyword/vector/metadata/graph retrieval
      -> merge -> deduplicate -> rerank -> graph expansion
      -> EngineeringContextBuilder -> generation
```

Retrieval results must carry object ID and type, score, retrieval sources,
reason, source, and evidence. The context builder prioritizes the current model,
the selected object, direct graph neighbors, approved signals, requirements,
technical rules, approved analogues, imported documents, and simulation history.

## Scoring

Weights for semantic similarity, graph distance, approval level, source quality,
domain, technology, and version are configurable in `HybridRetrievalService`.
Released, approved, and validated knowledge receives more weight than raw,
imported, or AI-generated material.

## Industry Partitions

Signal-generation evidence is routed through `IndustryRAGOrchestrator`.
Industry-neutral semantic tags remain separate from profile-specific
`industry_tags`. Signal-list imports do not persist raw signal names; they
produce aggregate `SignalCorpusProfile` objects with counts, tag distributions,
and namespace patterns only. Profiles carry a `rag_partition` such as
`signal-generation:generic`, `signal-generation:automotive`,
`signal-generation:industrial_automation`, `signal-generation:aerospace`,
`signal-generation:rail`, `signal-generation:marine`, `signal-generation:energy`,
`signal-generation:building_automation`, `signal-generation:embedded_systems`,
`signal-generation:robotics_ros` or `signal-generation:generic_networking`.

Generators may combine the selected industry partition with
`signal-generation:generic` fallback evidence. RAG evidence remains advisory and
cannot approve or complete generated engineering objects.

## Current State

`backend/knowledge` contains provider-neutral graph, vector and transformer
contracts plus deterministic local implementations. `CanonicalKnowledgeService`
indexes canonical PostgreSQL objects by entity, loads typed relations, executes
hybrid retrieval and builds a bounded context. Routing proposals use the same
hybrid principles. `POST /api/engineering/knowledge/search` exposes the read-only
pipeline to the Engineering Agent.

The local exact vector index and hashed semantic baseline are development
implementations. The v2 local embedding enriches normalized German and English
surface words with weighted engineering concept axes for canonical object types,
relations, workflow actions, status terms, routing, and API contracts. This keeps
phrases such as `Schnittstelle zuordnen` and `HAS_INTERFACE` in the same local
vector region without auto-merging entities. pgvector, Qdrant, FAISS or a hosted
embedding/reranking model can replace it without changing Engineering persistence
or governance.
