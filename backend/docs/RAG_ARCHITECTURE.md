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
