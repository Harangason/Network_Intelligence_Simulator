# Memory, Cache and Rendering Governance

This project treats large data as backend-owned data. Frontend views, React
state and hot caches receive bounded projections only.

Core rule:

- Full project models, traces, snapshots and histories live in the database or
  artifact store.
- API list endpoints return summaries and identifiers.
- Detail endpoints load one requested object or snapshot.
- Renderers receive only the visible window, selected detail and compact
  counters.

The executable policy is exposed by:

- `GET /api/engineering/performance/governance`
- `backend/engineering/performance_governance.py`

