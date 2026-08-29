# Extension Guide

A new workload type must be added without modifying Agent Core control flow.

## 1. Register the Workload Type

Create a `WorkloadTypeDefinition` with type, target object and description and register it during application composition.

## 2. Create a Handler

Implement `BaseWorkloadHandler`. Keep workflow knowledge in the handler and object construction out of it. Establish child workloads/dependencies in `plan` and use repository adapters for persistence.

## 3. Register Generators

Implement `BaseGenerator.generate` and return `GeneratorResult`. Register by workload type and optional category. Use `*` only as an intentional fallback.

## 4. Register Validators

Register domain validators in `ValidatorRegistry`. Reuse duplicate, dependency and quality validators where applicable. Validators return structured findings and never delete candidates silently.

## 5. Define Completion Criteria

Set exact total and package targets, required fields and blocking criteria. `CompletionValidator` remains unchanged and consumes persisted counters/results.

## 6. Add Context Providers

When domain knowledge is needed, provide engineering, RAG or graph adapters through `ContextBuilder`. Do not import domain stores into the Core.

## 7. Add Persistence/API Adapters

Implement repository protocols and expose the standard workload API through the host framework. Preserve proposals and human approval.

## 8. Add Tests

Test package planning, registry dispatch, generator contract, validation failures, duplicates, missing-work regeneration, retry exhaustion, progress, deterministic completion, proposal/approval and audit.

No edit to planner control flow, dispatcher branches, execution loop or Completion Validator should be necessary for a new workload type.
