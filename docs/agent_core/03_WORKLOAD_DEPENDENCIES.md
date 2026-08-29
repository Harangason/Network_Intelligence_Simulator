# Workload Dependencies

## Dependency Graph

`WorkloadDependencyGraph` stores directed edges from a workload to the workloads it requires. The graph validates cycles and produces a topological execution order with dependencies first.

## Blocking Rules

Each edge includes a required status. A dependency is satisfied when actual and required status match; `COMPLETED` also satisfies `READY_FOR_REVIEW`. `FAILED`, `CANCELED`, `BLOCKED` and `INCOMPLETE` dependencies block their dependent workload.

## Readiness

- `READY`: every dependency satisfies its required status.
- `WAITING`: at least one dependency is still active or awaiting review.
- `BLOCKED`: at least one dependency ended in a blocking state.

The readiness result lists both `waiting_for` and `blocked_by` IDs for API and audit use.

## Parent/Child Dependencies

Mandatory child workloads are dependency edges from parent to child with required status `COMPLETED`. Parent completion also checks all mandatory children explicitly. This supports a large communication-system workload composed of hardware, functions, interfaces, signals, messages, routing, parameters, validation and simulation.

## Workflow Dependencies

Typical domain order is:

```text
Hardware -> Functions -> Interfaces -> Signals -> Messages
         -> Routing -> Parameters -> Validation -> Simulation
```

The Core stores only graph relationships and statuses. Handlers decide which domain dependency is required and may create child workloads through the repository adapter.
