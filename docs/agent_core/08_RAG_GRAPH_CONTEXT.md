# RAG and Graph Context

## Engineering Context

Engineering context can contain selected project, existing objects, functions, interfaces, signals, messages, routing, networks, parameters, requirements and validation results. The simulator provider resolves the canonical ECU/interface/message context required by a signal generator.

## Vector RAG Context

`RAGContext` can contain similar approved objects, historical solutions, technical documents and imported data. Retrieval results are evidence, not approval and not completion facts.

## Graph Context

`GraphContext` can contain neighbors, paths, dependencies, producer/consumer relations and hardware/function/routing mappings.

## Context Builder

`ContextBuilder` owns three optional provider adapters and returns a `WorkloadContext` with separate `engineering`, `rag`, `graph` and `execution` sections. The Core does not import a vector store or graph database.

## Retrieval Boundaries

- Providers receive only workload and optional package scope.
- Context is structured and auditable.
- Retrieval must prefer approved project/domain evidence.
- RAG or graph absence must not be disguised as evidence.
- Context may guide generators and repair, but cannot set `COMPLETED` or `APPROVED`.
