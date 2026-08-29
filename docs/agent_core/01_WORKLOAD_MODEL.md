# Workload Model

## EngineeringWorkload

An `EngineeringWorkload` is a persisted, measurable user outcome. Important fields are:

```text
workload_id, workload_type, title, target_total
work_packages[], dependencies[], completion_criteria[]
status, attempts, max_attempts
parent_workload_id, child_workload_ids[]
```

The sum of all package targets must equal `target_total`. A mismatch is a `WORKLOAD_CONFIGURATION_ERROR` and execution must not start.

## WorkPackage

Every package owns its target and counters:

```text
requested_count, generated_count, valid_count
invalid_count, duplicate_count, missing_count
attempts, max_attempts, status
```

`missing_count = max(0, requested_count - valid_count)`. Generated candidates are not equivalent to valid results.

## Status

Lifecycle states are `RECEIVED`, `PLANNING`, `IN_PROGRESS`, `VALIDATING`, `INCOMPLETE`, `READY_FOR_REVIEW`, `COMPLETED`, `FAILED`, `BLOCKED`, `NEEDS_REVIEW`, `PAUSED` and `CANCELED`.

- `READY_FOR_REVIEW`: all technical criteria pass, human approval is pending.
- `COMPLETED`: all required valid proposals have canonical approved objects.
- `INCOMPLETE`: retry limit reached without a blocking dependency.
- `BLOCKED`: a dependency or blocking package error prevents progress.

## Progress

Progress is calculated from persisted package counters. The API exposes total and package percentages plus generated, valid, invalid, duplicate, warning, error and missing counts.

## Targets and Completion Criteria

Targets are exact, not advisory. Completion criteria are structured metrics, for example total valid count, sub-targets, duplicate count, required fields, persistence and dependencies. The LLM cannot override them.

## Parent and Child Workloads

A parent can own mandatory child workloads. The parent is complete only when all mandatory children are `COMPLETED` and its own completion criteria pass. Optional children may finish independently. Parent/child links do not replace dependency edges; mandatory children are represented as dependencies as well.
