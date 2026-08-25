# Knowledge Graph

## Current State

Canonical relations are stored in `engineering_relations` with typed source and
target objects, provenance, confidence, review, and approval metadata. The API
supports create, read, list, filtering by object, and draft-safe deletion.

The simulator also has an older industry-local SQLite graph used for simulation
observations. It is not the canonical engineering graph and must not become a
second Engineering Model.

## Graph Abstraction

`backend.knowledge.GraphStore` defines node, edge, neighborhood,
traversal, path, entity-search, and subgraph operations. A local implementation
is the default; Neo4j and Memgraph adapters may be added without changing
the Engineering Core.

Graph nodes describe canonical object IDs. Graph data never replaces the
canonical object record. Simulation results enter as observations through
`SIMULATED_IN`, `FAILED_IN`, and `OBSERVED_IN`, not as approved truth.

## GraphRAG

Multi-hop expansion, path search, depth controls, graph-aware retrieval reasons
and evidence tests are implemented by `LocalGraphStore` and
`HybridRetrievalService`. `POST /api/engineering/knowledge/subgraph` returns a
bounded canonical subgraph; `knowledge/search` combines graph expansion with
keyword, vector and metadata evidence before reranking.
