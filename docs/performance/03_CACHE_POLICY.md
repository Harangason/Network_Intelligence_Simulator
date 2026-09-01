# Cache Policy

Every hot cache must define:

- Namespace
- Owner
- Maximum entries
- TTL when eviction is time based
- Maximum value size
- Eviction policy
- Key template

Program cache entries carry `updatedAt` and optional `expiresAt`. Expired
entries are ignored on read and deleted during prune.

