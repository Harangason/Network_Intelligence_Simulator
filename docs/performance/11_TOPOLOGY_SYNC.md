# Topology Sync

Topology synchronization keeps per-topology locks to avoid overlapping syncs.
The lock registry is bounded to 256 topology ids.

The sync code should store canonical nodes and relations in the engineering
model and avoid using process memory as a historical registry.

