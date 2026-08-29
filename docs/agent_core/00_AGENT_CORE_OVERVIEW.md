# Agent Core Overview

## Purpose

`backend/agent_core` is the reusable execution kernel for measurable engineering work. It converts a request into packages, resolves dependencies, dispatches registered extensions, tracks progress and determines completion from persisted facts. It never invents domain objects and never approves a proposal.

## Architecture

```text
Request -> Planner -> Workload/Packages -> Dependency Graph
        -> Dispatcher -> Handler -> Generator -> Validator
        -> Repair/Regeneration -> Progress -> Completion
        -> Proposal -> Human Review
```

The separation is binding:

- Core: lifecycle, counts, dependencies, progress and completion.
- Handler: domain workflow for one workload type.
- Generator: concrete candidate objects.
- Validator: validity and quality findings.
- Repair: bounded correction or regeneration.
- Context Builder: adapter for engineering, RAG and graph context.
- Human: approval or rejection.

## Main Components

| Area | Components |
| --- | --- |
| Core | `EngineeringWorkload`, `WorkPackage`, `WorkloadDependencyGraph` |
| Orchestration | `WorkloadPlanner`, `WorkloadDispatcher`, `WorkloadExecutionLoop`, `RetryManager`, `WorkloadProgressTracker` |
| Registries | workload types, handlers, generators, validators and tools |
| Validation | workload, completion, duplicate, dependency and quality validators |
| Repair | `MissingWorkService`, `RegenerationService`, `RepairService` |
| Context | engineering, RAG, graph and execution context |
| Review | proposals, proposal store and `ApprovalBoundary` |
| Persistence | repository protocols plus simulator PostgreSQL adapters |

## Execution Flow

1. The request is planned into exact package targets.
2. Dependencies are checked before execution.
3. The dispatcher resolves a handler, generator and validators from registries.
4. The generator returns the standard `GeneratorResult` contract.
5. Validation and duplicate checks update structured state.
6. Missing or repairable work is retried within an explicit limit.
7. `CompletionValidator` calculates `READY_FOR_REVIEW` or an incomplete state.
8. A proposal remains separate from the canonical engineering model until human approval.

## Engineering Model Relationship

The simulator keeps PostgreSQL persistence and engineering proposal adapters in `backend/engineering`. Its workload service is an adapter that composes Agent Core services. Domain catalogues and signal construction remain in `backend/engineering/workloads`.

## AI, RAG and Graph Relationship

An LLM may help interpret a request or generate a candidate. It cannot set completion or approval. RAG and graph systems are optional providers behind `ContextBuilder`; the Core only receives structured context.

## Approval Boundary

Generated objects are drafts/proposals. Deterministic validation may move them to `READY_FOR_REVIEW`. Only a human actor can call approval and create or update canonical engineering objects.

## EIP Reuse

EIP can reuse the complete `agent_core` package and provide different repositories, context providers, handlers, generators and validators. Signal, routing, simulation and trace implementations stay simulator-specific.
