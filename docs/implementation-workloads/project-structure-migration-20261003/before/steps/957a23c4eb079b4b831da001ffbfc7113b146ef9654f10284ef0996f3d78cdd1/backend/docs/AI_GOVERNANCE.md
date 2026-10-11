# AI Governance

## Separation

Knowledge, AI proposals, approved Engineering Objects, and Simulation are
separate persistence and lifecycle concerns. Vectors describe similarity;
graphs describe relationships; neither is the source of truth.

## Enforced Today

- AI-generated object and relation proposals use `engineering_ai_proposals`.
- Generic canonical CRUD rejects `source=ai_generated`.
- Generic canonical CRUD rejects direct approval changes.
- Approved state is not available to the agent tool set.
- Object revisions are recorded in `engineering_object_versions`.
- Human reviewers can edit, validate, approve selected proposal objects,
  approve all valid proposals, or reject a proposal.
- Approval materializes canonical objects with proposal, model, prompt,
  evidence, and approver provenance and writes the first version snapshot.

## Approval Boundary

The approval API is intentionally absent from the AI tool registry. Endpoints
under `/api/engineering/proposals/*/approve` are human-review actions. Bulk
approval processes only currently valid, not-yet-materialized proposal items.
Invalid, rejected, approved, and superseded state transitions are guarded by the
proposal service.

Released revisions remain immutable. Changes create a successor revision with
`REPLACES` or `VERSION_OF`; they never overwrite released history.
