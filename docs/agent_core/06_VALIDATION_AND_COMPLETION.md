# Validation and Completion

## Validation Layers

Validation is composed, not hidden in generator text:

- `WorkloadValidator`: positive targets and exact package totals.
- Domain validator: required engineering fields and domain rules.
- `DuplicateValidator`: IDs, names, semantic aliases and near duplicates.
- `DependencyValidator`: required workload states.
- `QualityValidator`: reusable required-field checks.
- `CompletionValidator`: final deterministic state decision.

## Completion Criteria

`CompletionValidator` exposes individual checks:

```text
evaluate_total_target
evaluate_sub_targets
evaluate_required_fields
evaluate_validation_status
evaluate_duplicates
evaluate_dependencies
evaluate_blocking_errors
```

The result contains `checks` and `reasons`, so an incomplete state is explainable through API and audit.

## Count Validation

For a request of 35 signals with 10 thermal and 25 motion:

```text
valid_total == 35
valid_thermal == 10
valid_motion == 25
```

Both total and every package target must match exactly. More generated candidates do not compensate for an incomplete category.

## Duplicate Validation

Exact duplicate IDs and names are errors. Semantic aliases such as `MotorRPM`, `EngineSpeed` and `RotationalSpeed` are `POSSIBLE_DUPLICATE`; similar spellings can be `NEAR_DUPLICATE`. Possible or near duplicates are retained for review and never automatically deleted.

## Quality Validation

Required fields are checked on structured definitions. A `MISSING_FIELD` error prevents readiness. Domain validators additionally check units, ranges, data types, resolution, references and other engineering constraints.

## Blocking Errors

An unsatisfied dependency or a package in `BLOCKED` prevents execution and completion. Retry exhaustion without an external blocker becomes `INCOMPLETE`. A repair that cannot be made confidently becomes `NEEDS_REVIEW`.

## READY_FOR_REVIEW Decision

All of the following must be true:

```text
total target met
all package targets met
required fields valid
invalid count == 0
duplicate count == 0
dependencies satisfied
blocking errors == 0
all valid objects persisted as draft/proposal/canonical object
```

Only then is status `READY_FOR_REVIEW`. `COMPLETED` additionally requires canonical IDs and `APPROVED` state for every required valid object. The LLM is not called by this decision.

## Generator Success Is Not Completion

A generator can return `SUCCESS` with fewer valid objects, warnings, invalid objects or remaining work. The handler persists and validates results; Completion Validator independently decides workload state from the persisted snapshot.
