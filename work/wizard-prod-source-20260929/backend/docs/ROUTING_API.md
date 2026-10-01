# Routing API

Base path: `/api/engineering/routing`

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/routing` | list or create manual/imported drafts |
| GET/PATCH/DELETE | `/routing/{id}` | inspect, revise or delete a non-approved route |
| POST | `/routing/{id}/validate` | validate one route |
| POST | `/routing/{id}/approve` | human approval for a valid route |
| POST | `/routing/{id}/reject` | reject with reason |
| GET | `/routing/{id}/path` | hops, gateways, transformations, loops |
| GET | `/routing/{id}/evidence` | technical evidence and metrics |
| GET | `/routing/{id}/versions` | immutable revision history |
| POST | `/routing/validate` | validate the current table |
| GET | `/routing/paths` | graph path candidates |
| POST | `/routing/generate` | create an AI proposal |
| POST | `/routing/optimize` | proposal-only optimization hints |
| POST | `/routing/import` | import route drafts |
| GET | `/routing/approved/config` | simulator config from approved routes |
| GET/PATCH/DELETE | `/routing/proposals/{id}` | proposal lifecycle |
| POST | `/routing/proposals/{id}/accept` | create selected route drafts |
| POST | `/routing/approve-selected` | approve selected valid routes |
| POST | `/routing/approve-all-valid` | approve every pending valid route |
| POST | `/routing/reject-selected` | reject selected routes |
| GET/POST | `/routing/rules` | list/create conditional rules |
| GET/PATCH/DELETE | `/routing/rules/{id}` | manage a draft rule |
| GET | `/routing/audit` | route and proposal audit trail |

Errors use `{ "error": "..." }`. Invalid input returns 400, missing resources
404 and governance conflicts 409. JSON route payloads follow `ROUTING_MODEL.md`.
