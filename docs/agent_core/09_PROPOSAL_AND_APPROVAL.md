# Proposal and Approval

## Proposal Lifecycle

```text
DRAFT -> validation -> READY_FOR_REVIEW
      -> human APPROVED | REJECTED | NEEDS_REVISION
```

## AI Generated Objects

Every generated object is marked as generated/draft and persisted in a proposal or an equivalent review state. It is not inserted as an approved canonical object by the generator.

## Review

The Workload UI shows category, fields, findings, duplicate status and proposal state. Users can review all results or select a subset of valid proposal objects.

## Approval

`ApprovalBoundary.require_human` rejects empty and automated actors. Only `READY_FOR_REVIEW` proposals may be approved. The simulator API additionally requires an explicit actor and uses its existing proposal service to create canonical objects.

## Rejection and Revision

Human rejection preserves proposal and audit history. A revision returns to draft/validation; it never mutates an already approved historical proposal invisibly.

## Human in the Loop

The Agent Core may generate, validate, repair and prepare proposals. It cannot approve them. Workload `COMPLETED` is derived only after approved canonical IDs are visible in persisted workload objects.
