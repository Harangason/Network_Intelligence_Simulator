# AI Audit Proposals

The engineering workload runner now turns detected model issues into reviewable proposals instead of stopping at a warning.

Supported proposal actions:

- `CREATE`: missing object or signal should be added.
- `UPDATE`: existing/proposed object should be corrected with suggested parameters.
- `DELETE`: duplicate or surplus canonical object should be removed when it is still `draft`.
- `DEPRECATE`: applied automatically instead of destructive deletion when the canonical object is already versioned beyond draft.

This keeps the workflow AI-supported but review-gated. The user still decides when a proposal is accepted.
