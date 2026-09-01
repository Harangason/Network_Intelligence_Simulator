# Invalidation

When canonical data changes, dependent projections are invalidated instead of
silently reusing stale full payloads.

Workflow snapshots keep source versions and outdated reasons. UI views should
show stale status from metadata and load details only when the user opens the
specific evidence.

