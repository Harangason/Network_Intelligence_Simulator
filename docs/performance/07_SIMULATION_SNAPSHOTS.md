# Simulation Snapshots

Simulation snapshot lists return metadata by default. Full result payloads are
loaded through the explicit detail endpoint:

- `GET /api/engineering/workflow/simulation-snapshots/<snapshot_id>`

The workflow state and snapshot list endpoints must not include `result`,
`configuration` or `calculated_metrics` for every snapshot.

