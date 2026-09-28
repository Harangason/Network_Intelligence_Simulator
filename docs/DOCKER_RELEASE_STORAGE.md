# Release image and build-cache retention

Release gates keep every candidate by default. Existing images, receipts and
checker archives are evidence: this policy does not delete them. The full
`.tool-checker` and legacy `tool-checker` directories are host checker sources,
snapshots, repair evidence and archives, not simulator runtime inputs. Host
dependency caches, diagnostic reports, presentation output and implementation
workloads are also excluded from Docker context. Runtime source, config,
frontend public files, docs and the build-manifest inputs remain included.

`run-release-gate.py` records the candidate tag before building, adds gate/source
labels to new images, and preserves immutable image/source/PASS checks. Failed,
prepared and interrupted candidates remain protected. It checks a fixed minimum
20 GiB free on the checkout volume and Windows system volume before expensive
verification/build. A relocated Docker data volume must additionally be supplied
with `--docker-storage-path`; remote engines require their own verified free-space
evidence. This is a minimum readiness floor, not a prediction of total build size.
Before adding another candidate it also refuses builds when the `networkis`
repository already contains 100 distinct immutable image IDs (tag aliases count
once). This bounds future gate accumulation by stopping it pending reviewed
cleanup; no existing historical image is removed to meet the budget.

`python scripts/release_storage.py <audit-snapshot.json> --now <unix-seconds>`
produces a **PLAN_ONLY** inventory. It has no deletion mode. The snapshot contains
`inventory_complete`, `receipt_inventory_complete`, `production_image_id`,
`rollback_image_id`, `container_image_ids` (all running and stopped containers),
`receipts` (all historical receipts) and `images`. Each image uses its full
`sha256:...` ID, `created_epoch`, `audit_disposition`, `audit_evidence_path` and
`audit_evidence_sha256`. The referenced JSON audit must bind `image_id`,
`accepted: true`, `disposition: SUPERSEDED_DELIVERED` and concrete
`feature_delivery_evidence`; its current hash must match. Missing inventory or verified rollback PASS blocks all
eligibility. `container_inventory_complete: true`, an explicit list of strict
immutable container image IDs and `container_inventory_evidence: {path, sha256}`
are mandatory. That referenced JSON uses schema `nis-container-inventory-v1`,
an engine ID, `captured_epoch` and every running/stopped container as
`{name, container_id, image_id}`. Container IDs are full 64-character hex IDs;
image IDs use `sha256:` plus 64 hex characters. The evidence must be captured
within five minutes of the supplied planning timestamp, its image set must
exactly match the snapshot list, and current production must appear. Planning
does not independently query Docker; accepted inventory evidence must come from
a fresh complete `docker ps -a` plus inspect on that named engine.

Timestamps are finite, nonboolean Unix numbers from zero through year 9999;
future creation timestamps and invalid audit timestamps block eligibility.

`feature_delivery_evidence` is exactly two file/hash reference objects with
roles `running_manifest` and `delivery_comparison`. The running manifest binds
the current production immutable `image_id` and 64-character `source_sha256`.
The comparison binds `candidate_image_id`, `candidate_source_sha256`,
`delivered_to_image_id`, matching `delivered_source_sha256`,
`coverage: FULL_CANDIDATE_FEATURES` and a nonempty list of concrete `feature_ids`.
The audit's delivered image must match current production. Both actual referenced
files must exist and retain their recorded SHA-256 hashes. These structural and
correlation checks cannot prove the semantic accuracy of a feature comparison;
that remains part of the explicitly accepted review, supported by actual source
and running-manifest evidence. Whitespace strings, partial comparisons, missing
files and stale/mismatched identities never constitute delivery evidence.

Missing inventory or verified rollback PASS blocks all
eligibility. Current production, rollback, any container reference,
RUNNING, PREPARED, unknown receipts and undelivered/unclassified feature audits
remain protected regardless of age. A FAIL image remains protected until an
accepted audit proves every feature delivered or recovered elsewhere; failure
alone never makes it disposable. Only an audited `SUPERSEDED_DELIVERED`
PASS/FAIL older than seven days can enter the review proposal; any PASS receipt
must be complete, and evidence
file hashes must still match. Feature delivery must be established from source
and actual running manifests, never from tag order or build age.

Before any separately authorized image cleanup, accept the concrete audit plan,
refresh every container/image/receipt inventory, rerun protection checks, and
remove exact immutable IDs without force. A changed audit or running state
invalidates the proposal. Never use `image prune -a`, `system prune`, or delete
receipts/archives to free space. This helper intentionally cannot execute cleanup.

The gate can use an **existing dedicated** `nis-*` buildx builder via `--builder`.
No builder is created, reconfigured or pruned automatically. For a reviewed
dedicated-builder cache proposal add `--dedicated-builder nis-release` to the
planner. The proposal retains seven days and targets 20 GB cache with 10 GB free
space using installed buildx size flags. Verify CLI support, exclusive ownership
and absence of active builds before executing that separate maintenance action.
Shared/default Docker Desktop cache needs an explicit reviewed ownership/settings
decision; this patch changes no global Docker settings. Size/age preferences are
not hard quotas and retained or in-use cache may exceed them.

The 48-hour host pytest runtime policy in `TEST_RUNTIME_RETENTION.md` continues
independently; it does not authorize Docker image/cache cleanup.

PASS receipts used for rollback or candidate protection must have full lowercase
64-character SHA-256 verification and matching initial/release source hashes.
Checks are a list of named objects, with unique nonblank identifier names and
strict integer zero exit codes for every recorded check; boolean/float zero,
duplicate success/failure rows and malformed entries cannot establish PASS.
All six historical required release checks remain mandatory. Every recorded
commit identity must be a full 40/64-character Git ID and paired initial/release
commits must match. Historical receipts with absent commit fields remain
supported explicitly; missing or invalid source/verification proof does not.
Malformed snapshot/receipt/image inventories return a structured BLOCKED plan
with no eligible images instead of exceptions or inferred empty inventories.
