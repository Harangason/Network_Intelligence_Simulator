# Canonical Engineering Model

## Scope

The canonical model is the source of truth above the existing `CommunicationSimulator`.
Phase 1 currently covers `HardwareNode`, `Function`, `Interface`, `Message`,
`Signal`, typed relations, provenance fields, and immutable version snapshots.

All objects expose `id`, `object_type`, `name`, `description`, `domain`,
`version`, lifecycle, source, provenance, confidence, review and approval state,
plus creation and modification metadata. `HardwareNode` is industry-neutral;
`ECU` is one device type among several.

## Persistence

Postgres is accessed only through `engineering/repository.py`. The idempotent,
versioned schema is defined in `engineering/schema.py` and initialized under a
database advisory lock. The active schema version is exposed by
`GET /api/engineering/health`.

Every create and update writes a snapshot to `engineering_object_versions`.
Draft deletion also removes polymorphic relations, avoiding dangling graph edges.

## Containment Hierarchy

Engineering objects form one required containment chain:

`HardwareNode -> Function -> Interface -> Message -> Signal`

Creating a child requires its direct parent. The repository persists the typed
foreign key and the matching graph edge in the same transaction:
`HAS_FUNCTION`, `HAS_INTERFACE`, `HAS_MESSAGE`, or `CONTAINS_SIGNAL`.
An interface also retains its hardware lineage through `hardware_node_id`.

## Network Editor Synchronization

`POST /api/engineering/topology/sync` reconciles the visual Studio topology
with the canonical model. Network nodes map to `HardwareNode` objects, each
node receives a communication `Function`, ports map to `Interface` objects,
and wires map to `CONNECTED_TO` relations. Stable topology and port IDs make
the operation idempotent. Synchronization is serialized per topology so
concurrent browser tabs cannot create duplicate canonical objects.

## Governance Boundary

Generic CRUD never accepts `source=ai_generated` and never changes
`approval_state`. AI output must enter `engineering_ai_proposals`; a dedicated
Approval Service will later be the only path into the approved model.

## Open Model Work

Capability, PhysicalPort, Network, Protocol, DataType, Unit, Requirement,
Constraint, Evidence, ImportedSource, and SimulationArtifact remain Phase 1
extensions. They must extend this model rather than create a parallel source of truth.
