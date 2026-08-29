# Repair and Retry

## Repair Strategies

`RepairService` maps a finding code to an explicit strategy. A strategy receives the candidate and structured context. It may return a corrected candidate or decline. Unknown or unsafe corrections are listed under `needs_review`.

Examples of safe repair are swapping an inverted numeric range, restoring a known unit from engineering context or adding a deterministic default. Semantic renames and ambiguous topology changes require review.

## Regeneration

`RegenerationService` calls the selected generator with only the missing count. Generated candidates are validated and recounted like the initial candidates; they never bypass proposals.

## Missing Work

`MissingWorkService` calculates package-level gaps from requested and valid counts. For 9/10 thermal signals it emits one `MissingWork` item for category `thermal`.

## Retry Limits

`RetryManager` records attempt count, reason and last error. Workloads and packages both have explicit maximum attempts. No retry path can create an endless loop.

## Failure States

- `INCOMPLETE`: attempts exhausted and measurable work remains.
- `BLOCKED`: dependency or blocking error prevents progress.
- `NEEDS_REVIEW`: a result is not safely repairable.
- `FAILED`: execution failed irrecoverably.

Every attempt, repair and retry is written to the workload audit.
