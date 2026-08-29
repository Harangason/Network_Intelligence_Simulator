# Workload Orchestration

## Planner

`WorkloadPlanner` delegates request interpretation to an injected plan factory. Its output must contain exact packages and an execution order. The simulator injects its deterministic request parser; EIP may inject another parser without changing the Core.

## Dispatcher

`WorkloadDispatcher` resolves a handler, a category-specific generator and all registered validators. Selection is registry based. Adding a workload type must not add an `if/else` branch to the dispatcher.

## Execution Loop

`WorkloadExecutionLoop` repeatedly performs one persisted cycle:

```text
inspect -> check dependencies/retry limit -> execute package handlers
        -> validate -> repair -> recount -> evaluate completion
```

The loop receives callbacks and therefore has no domain or database dependency. It stops on terminal/review states, unsatisfied dependencies or exhausted attempts. Progress tokens prevent an unbounded no-progress loop.

## Retry Manager

`RetryManager` records `max_attempts`, `attempt_count`, `last_error` and `retry_reason`. Retry exhaustion produces `INCOMPLETE` or `BLOCKED` with a reason; it never silently loops.

## Progress Tracker

`WorkloadProgressTracker` derives all counts and percentages from packages. UI polling reads persisted state and cannot accidentally declare completion.

## Completion Flow

The handler returns generated objects and validation findings. `CompletionValidator` independently evaluates exact total, every sub-target, required fields, validation status, duplicates, dependencies and blockers. Passing technical checks yields `READY_FOR_REVIEW`; human approval is required for `COMPLETED`.
