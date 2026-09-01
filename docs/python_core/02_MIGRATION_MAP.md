# Migration Map

| Component | Current Path | Current Responsibility | Problem | Decision | Target Path | Risk |
|---|---|---|---|---|---|---|
| Engineering Core Models | `backend/engineering/models.py` | Vocabularies and validation helpers | Not enough canonical aggregate contracts | REFACTOR | `backend/engineering/core/models.py` | Low |
| Signal Architecture TS | `frontend/src/lib/signal-architecture.ts` | Semantic type and bit requirement | Duplicates Python audit | MOVE_TO_CORE | `backend/engineering/signals/*` or `backend/engineering/signal_audit.py` | Medium |
| Capacity Network Inspection TS | `frontend/src/lib/capacity-network-inspection.ts` | Signal/message/network inspection | Duplicates Python findings | MOVE_TO_CORE | `backend/engineering/analysis/network_inspection.py` | Medium |
| Engineering Specification TS | `frontend/src/lib/agent/engineering-specification.ts` | Text parsing and project generation | Frontend generates canonical engineering data | MOVE_TO_CORE | `backend/engineering/imports/specification.py`, `backend/engineering/generation/*` | High |
| Equipment Clustering TS | `frontend/src/lib/agent/equipment-clustering.ts` | Domain grouping and bus suggestions | Contains domain heuristics in UI | MOVE_TO_CORE | `backend/engineering/domain_profiles/*` | Medium |
| Semantic Routing TS | `frontend/src/lib/agent/semantic-routing.ts` | Route candidate heuristics | Duplicates routing generation | MOVE_TO_CORE | `backend/engineering/routing/generation.py` | Medium |
| Capacity Service | `backend/engineering/capacity/service.py` | Capacity, timing, grouping and persistence | Too many responsibilities | SPLIT | `backend/engineering/analysis/capacity/*` | Medium |
| Capacity Calculators | `backend/engineering/capacity/calculators.py` | Frame/load/timing helper functions | Good Python source, needs technology modules | REFACTOR | `backend/engineering/technologies/*` | Medium |
| Routing Validation | `backend/engineering/routing/validation.py` | Route and protocol validation | Good source but uses local protocol tables | REFACTOR | `backend/engineering/routing/validation.py` + technology registry | Low |
| Workload Service | `backend/engineering/workloads/service.py` | Workload orchestration, persistence and proposal sync | Monolithic service | SPLIT | `backend/agent_core/*` + thin engineering adapters | High |
| Semantic Intelligence | `backend/engineering/semantic_intelligence/*` | Ontology, alias resolution, proposal classification and confidence aggregation | New controlled base; parser and UI still need integration | INTEGRATE | Parser, workload generation, capacity audit and wizard API clients | Medium |
| Engineering API | `backend/engineering/api.py` | API routes for all engineering areas | Oversized route module | SPLIT | `backend/engineering/api/*` | Medium |
| Technology Catalog | `backend/simulator/physic_lib/Industries/registry.py` | Industry generator registry | Useful but not contract-complete for calculators | REFACTOR | `backend/engineering/technologies/registry.py` | Medium |
| Runtime Launcher | `generate_realistic_communication_tool.py` | CLI/web launch, Docker, health, process supervision | Large but operational | KEEP | Same, later split to launcher package | Low |
| Frontend Workbenches | `frontend/src/components/*workbench.tsx` | Rendering plus local interpretation | Some business logic leaks into UI | REFACTOR | UI-only components + API DTOs | Medium |

## Phase Status

| Phase | Status |
|---|---|
| 1. Architecture Inventory | Started |
| 2. Canonical Core | Started |
| 3. Signal Core | Pending |
| 4. Message Core | Pending |
| 5. Technology Registry | Pending |
| 6. Specialized Technology Modules | Pending |
| 7. Routing Core | Pending |
| 8. Network Core | Pending |
| 9. Analysis Core | Pending |
| 10. Simulation Core | Pending |
| 11. Trace Core | Pending |
| 12. Agent Core Integration | Pending |
| 13. API Boundaries | Pending |
| 14. Frontend Logic Removal | Pending |
| 15. Semantic Intelligence | Started |
