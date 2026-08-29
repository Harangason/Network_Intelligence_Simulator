# Workload API

All routes use the existing engineering API prefix `/api/engineering` and project scoping through `X-Project-ID`. Read routes require project access. Mutations require project write access. Approval actions require an authenticated human actor. Errors use the engineering API JSON error envelope; common errors are `400` invalid request/state, `404` missing workload and `409` conflicting state.

| Method | Path | Request | Response | Permission | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/workloads` | prompt, type/targets, packages, optional dependencies | persisted workload with packages | write | 400 target/package mismatch, unknown type/dependency |
| GET | `/workloads` | query: status, workload_type, limit, offset | `{items,count}` | read | 400 invalid filter |
| GET | `/workloads/{id}` | none | workload, packages and resolved dependencies | read | 400 invalid ID, 404 missing |
| POST | `/workloads/{id}/start` | optional actor | current workload and completion decision | write | 400 invalid state, 404 missing |
| POST | `/workloads/{id}/pause` | optional actor | paused workload | write | 400 terminal workload |
| POST | `/workloads/{id}/resume` | optional actor | resumed execution result | write | 400 canceled workload |
| POST | `/workloads/{id}/cancel` | optional actor | canceled workload | write | 400 completed workload |
| POST | `/workloads/{id}/validate` | optional actor | validation/completion result | write | 400 state/configuration error |
| POST | `/workloads/{id}/generate-missing` | optional actor | regenerated/revalidated result | write | 400 retry exhausted/state error |
| POST | `/workloads/{id}/retry-invalid` | optional actor | repaired/revalidated result | write | 400 retry exhausted/state error |
| GET | `/workloads/{id}/progress` | none | status, counts, packages, dependencies and percentages | read | 404 missing |
| GET | `/workloads/{id}/objects` | none | `{items,count}` proposal/canonical objects | read | 404 missing |
| GET | `/workloads/{id}/dependencies` | none | `{items,count}` resolved dependency states | read | 404 missing |
| GET | `/workloads/{id}/audit` | none | `{items,count}` ordered audit events | read | 404 missing |

## Additional Review Routes

| Method | Path | Request | Response | Permission | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/workloads/{id}/approve-selected` | actor, proposal-to-index selections | updated workload/completion | human approval | 400 missing actor/invalid selection/state |
| POST | `/workloads/{id}/approve-all-valid` | actor | updated workload/completion | human approval | 400 missing/automated actor |
| GET | `/workloads/{id}/events` | none | compatibility alias for audit events | read | 404 missing |

## Create Request Example

```json
{
  "prompt": "Generate 35 signals: 10 thermal and 25 motion.",
  "workload_type": "SIGNAL_GENERATION",
  "requested_total": 35,
  "work_packages": [
    {"category": "thermal", "requested_count": 10},
    {"category": "motion", "requested_count": 25}
  ],
  "max_generation_attempts": 3
}
```

## Progress Response Shape

The response includes `status`, `requested`, `generated`, `valid`, `invalid`, `duplicates`, `warnings`, `errors`, `missing`, `percent`, `attempts`, `metrics`, `work_packages` and resolved `dependencies`.
