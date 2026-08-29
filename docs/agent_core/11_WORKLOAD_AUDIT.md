# Workload Audit

## Audit Events

The simulator persists workload receipt/creation, planning, package creation/start/completion, handler selection, generator execution, generated objects, validation, repair, retry, progress update, completion evaluation, ready-for-review and approval events.

## Stored Metadata

Each database event stores project, workload, optional package, event type, actor, agent, model, structured details and timestamp. The generic `AuditEvent` additionally defines generator, validator and before/after fields for EIP adapters.

## Agent and Model

Agent/model identifiers describe who produced or interpreted a candidate. They do not grant approval and are preserved for reproducibility.

## Generator and Validator

Generator class/name, requested/generated counts and validation findings are recorded in structured details. Completion audit includes every boolean check and failed reason.

## Before and After

Repair and approval adapters should store the relevant before/after object state. Large binary artifacts are referenced rather than copied into event rows.

## Approval

Approval events include the human actor and affected proposal IDs/indexes. Rejection and revision must likewise remain append-only. `GET /workloads/{id}/audit` exposes the persisted trail.
