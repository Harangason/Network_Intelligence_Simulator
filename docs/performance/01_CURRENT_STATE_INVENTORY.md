# Current State Inventory

Tracked layers:

- Browser: visible viewport and interaction state only.
- React State: bounded summaries, selected ids and small forms.
- Frontend Query Cache: ttl and byte-limited cached projections.
- Global Frontend Store: preferences and workflow markers, not source data.
- WebSocket Buffer: recent deltas, not complete traces.
- Canvas/Graph Renderer: viewport nodes and visible labels.
- Backend Process RAM: hot jobs, active locks and bounded summaries.
- Python Cache: active run scratch data.
- Redis: optional distributed hot cache with ttl.
- Database: canonical engineering model and versions.
- Artifact Store: large traces, exports, reports and evidence bundles.

