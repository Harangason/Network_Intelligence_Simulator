# Requirements Traceability

Stand: 2026-08-25

## Binding Workflow

| Step | Implementation | Verified behavior |
|---|---|---|
| 1 Engineering Model | Canonical PostgreSQL model, hierarchy, relations, import, review UI | Hardware -> Function -> Interface -> Message -> Signal is linked and editable |
| 2 Routing Table | Versioned routing repository, manual editor, AI proposals, graph paths, validation and approval | Producer, payload/signals, multiple consumers, gateways, conditions, fallback and evidence |
| 3 Network Editor | Project topology, model synchronization, movable/resizable nodes and ports | Approved model objects are selectable through add controls; labels remain bounded |
| 4 Parameters | Technology registry and dynamic physical, timing, QoS, reliability, synchronization and simulation fields | Parameter changes increment source versions and invalidate dependent results |
| 5 Capacity & Timing | Technology-specific calculators and persisted analysis snapshots | Average/Peak/Burst load, reserve, latency, jitter, queueing, gateways, reliability and synchronization |
| 6 Validation / Preflight | Cross-step validator and readiness score | ERROR blocks; WARNING remains visible and runnable; validation binds a version snapshot |
| 7 Simulation | Existing simulator kernel plus approved-routing configuration builder | Runs only from a validated snapshot and records immutable artifacts and runtime metrics |
| 8 Results / Analysis | Persisted prediction/runtime comparison and run comparison UI | Load, latency, jitter, queues, gateways, violations, bottlenecks and source references |

`WorkflowStatusService` applies the required dependency cascade. Earlier changes
mark later snapshots `OUTDATED`; no historical capacity, validation, simulation,
result, or artifact record is deleted.

## Engineering And Ingestion

- PostgreSQL is the canonical source of truth; local vector and graph stores are
  replaceable indexes, not a second Engineering model.
- Canonical objects carry source, provenance, confidence, lifecycle, review,
  approval, version, actor and timestamps.
- The visible import wizard handles DBC, CSV and XLSX without an application file
  size limit and preserves an industry-neutral domain (`generic` fallback).
- `SourceAdapterRegistry` covers CSV, JSON, YAML, XML, SQLite, PostgreSQL and REST.
- `RawEntity -> StagedEntity -> EngineeringChunk -> Knowledge index` preserves
  source provenance and keeps canonical commit under human review.
- Entity resolution distinguishes exact, alias, semantic, possible and new;
  semantic/possible matches never auto-merge.

## AI, RAG And Graph

- Provider boundaries: `AIProvider`, `AIModelGateway`, `TransformerService`,
  `VectorStore` and `GraphStore`.
- Retrieval pipeline: keyword, vector, metadata and graph retrieval, merge,
  deduplication, governance/source weighting, reranking, graph expansion and
  bounded context construction.
- GraphRAG supports neighbors, multi-hop traversal, path search and subgraphs.
- The global Engineering Agent receives active project, workflow step and
  selected object/route/network/signal/simulation context on every page.
- The agent can read, retrieve, validate and create proposals. It has no approval
  tool and cannot directly mutate approved Engineering data.
- Object and relation proposals stay separate. Human Review supports edit,
  validate, selected approval, bulk-valid approval and rejection. Materialized
  objects preserve prompt, model, evidence, proposal ID and approver provenance.

## Routing And Simulation Coupling

- Routing entries support unicast, multicast/broadcast, conditional, redundant
  and gateway paths, individual signal selection and multiple consumers.
- Validators cover missing endpoints, duplicates, loops, protocols and required
  conversion, gateways, payload, latency, jitter, conditions, fallback and
  estimated route load.
- Individual and bulk-valid approval, version history and audit events are
  persisted. Only approved routes enter the communication configuration.
- Runtime events retain route, network, message, gateway, queue, latency,
  corruption, drop and retransmission references. Results link back to the
  affected Engineering and routing objects.

## Verification Loop

1. Full backend regression: `93 passed, 6 skipped`; the six isolated-test-schema
   cases are skipped because `ENGINEERING_TEST_DATABASE_URL` is intentionally
   unset, while the same PostgreSQL paths are covered by the live API loop.
2. Python source compilation: all backend source modules compile.
3. TypeScript: `tsc --noEmit` passes.
4. Frontend production build: Next.js 16.3.2, all 19 pages generated.
5. Live services: `/studio/results` returns HTTP 200; `/api/health` returns `ok`.
6. Live eight-step project: model, routing, network, parameters, Capacity,
   Preflight, two simulations and Results comparison completed.
7. Change loop: bitrate modification recalculated Capacity and marked Validation,
   Simulation and Results `OUTDATED` while retaining both snapshots and artifacts.
8. Live RAG: vector, keyword, metadata and graph sources returned evidence and a
   multi-hop subgraph; route generation created a proposal without model mutation.
9. Live proposal governance: `DRAFT -> READY_FOR_REVIEW -> APPROVED`; canonical
   materialization and version creation occurred only after explicit approval.
10. Browser checks: desktop and 390 x 844 layouts have no page-level horizontal
    overflow; the fixed global agent remains collapsible and inside the viewport.

The resulting operational sequence is:

```text
Define -> Route -> Connect -> Configure -> Calculate
       -> Validate -> Simulate -> Analyze -> Improve
```
