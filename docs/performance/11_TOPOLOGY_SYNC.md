# Topology Sync

HTTP mutations run in one database transaction with a transaction-scoped
PostgreSQL advisory lock per project. This includes topology synchronization,
route synchronization and workflow invalidation, across browsers and backend
processes. A lock timeout returns a conflict instead of waiting indefinitely.

Direct in-process synchronization retains per-topology locks. The registry is
bounded to 256 locks; additional topology IDs reuse these locks. Held or awaited
locks are never evicted. HTTP synchronization uses the database lock without
also acquiring a process lock, avoiding an inverted lock order.

The sync code should store canonical nodes and relations in the engineering
model and avoid using process memory as a historical registry.
