# Current State Analysis

## Existing Components

| Area | Main Paths | Current State |
|---|---|---|
| Engineering API | `backend/engineering/api.py` | Large route layer. Mostly transport, but also orchestration and error handling. |
| Canonical vocabulary | `backend/engineering/models.py` | Existing enums and governance helpers. Keep as compatibility vocabulary while core models mature. |
| Capacity and timing | `backend/engineering/capacity/*` | Python implementation exists and is the preferred source for bus load, timing and warning origin. |
| Signal audit | `backend/engineering/signal_audit.py` | Python implementation exists, overlaps with TypeScript signal inspection. |
| Routing | `backend/engineering/routing/*` | Python generation, validation and repository logic exist; frontend still contains matrix and semantic helper logic. |
| Workflow | `backend/engineering/workflow/*` | Python workflow state exists; UI should only display and trigger. |
| Workloads | `backend/engineering/workloads/*`, `backend/agent_core/*` | Python agent/workload core already exists and should become the only orchestration authority. |
| Frontend agent | `frontend/src/lib/agent/*`, `frontend/src/components/agent-chat-core.tsx` | Contains parsing, generation, workflow and wizard logic that must move behind Python APIs step by step. |
| Frontend inspection | `frontend/src/lib/capacity-network-inspection.ts`, `frontend/src/lib/signal-architecture.ts` | Duplicates Python signal audit and bit requirement logic. Marked for migration to Python API. |

## Duplicate Logic

| Logic | Python Location | TypeScript Location | Problem |
|---|---|---|---|
| Signal semantic classification | `backend/engineering/signal_audit.py` | `frontend/src/lib/signal-architecture.ts` | Two sources classify legacy status/state signals. |
| Bit requirement | `backend/engineering/signal_audit.py` | `frontend/src/lib/signal-architecture.ts`, `frontend/src/lib/capacity-network-inspection.ts` | Capacity warnings can diverge from backend audit. |
| Network inspection | `backend/engineering/signal_audit.py` | `frontend/src/lib/capacity-network-inspection.ts` | UI can produce findings that backend cannot reproduce. |
| Routing semantics | `backend/engineering/routing/generation.py` | `frontend/src/lib/agent/semantic-routing.ts` | Route recommendations can diverge from persisted routing validation. |
| Equipment generation | `frontend/src/lib/agent/engineering-specification.ts` | Python workload/generator stack | Wizard still generates canonical data in TypeScript. |
| Technology aliases | `backend/engineering/scope_rules.py`, `backend/engineering/capacity/service.py`, routing validation | `frontend/src/lib/agent/engineering-agent.ts`, specification parser | SOME/IP, Ethernet and CAN-FD normalization has multiple partial maps. |

## Oversized Files

| Path | Lines At Baseline | Issue |
|---|---:|---|
| `frontend/src/lib/agent/engineering-agent.ts` | 3259 | Agent tools, parsing, deterministic logic and API calls mixed. |
| `frontend/src/components/agent-chat-core.tsx` | 3132 | Wizard, status UI, chat and workflow display mixed. |
| `frontend/src/components/engineering-workbench.tsx` | 2309 | Workbench UI and orchestration too tightly coupled. |
| `frontend/src/components/network-editor.tsx` | 2023 | UI, topology mapping and validation concerns mixed. |
| `frontend/src/components/routing-workbench.tsx` | 1857 | Matrix UI plus route interpretation logic. |
| `backend/engineering/api.py` | 1300 | API surface is too broad for one module. |
| `backend/engineering/capacity/service.py` | 1067 | Calculation, grouping, reporting and persistence mixed. |
| `backend/engineering/workloads/service.py` | 909 | Orchestration, persistence and object synchronization mixed. |
| `backend/engineering/workflow/service.py` | 900 | Workflow status, invalidation and analysis summaries mixed. |

## Known Defects From Review

- SOME/IP was treated as unsupported in scope rules even though routing and capacity support it through Ethernet.
- Gateway-direct generation could create a central-computer ECU next to the existing `System` gateway.
- Frontend signal checks duplicated Python audit logic and produced warning text users could not trace back.
- Next dev startup reused `.next`, which made local Windows lock issues break the tool start.
- Runtime logs and job registry could be blocked by local file permissions without fallback.

## Migration Risks

- Moving wizard generation first would be high risk because it touches project creation, API writes and the guided UI at once.
- Moving signal audit first is lower risk because Python already has most of the logic and frontend can become a thin API consumer.
- Routing matrix changes should wait until route-core DTOs are stable; otherwise the UI will continue to encode business rules.
