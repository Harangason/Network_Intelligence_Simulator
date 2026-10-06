# Current Implementation Audit

| Responsibility | Current File | Current Function/Class | Runtime Caller | Status | Problem | Decision |
|---|---|---|---|---|---|---|
| Signal extraction | `frontend/src/lib/agent/engineering-specification.ts` | `extractEngineeringSpecification` | Engineering wizard / agent | IMPLEMENTED | Produced one raw chain per detected signal | ADAPT |
| Message packing | `frontend/src/lib/agent/engineering-specification.ts` | `packEngineeringChains` | Engineering wizard / agent before registration | IMPLEMENTED | Previously DLC was per signal only | REUSE |
| Backend packing service | `backend/engineering/message_packing.py` | `pack_signals` | Tests and backend integration point | IMPLEMENTED | Central deterministic Python service was missing | KEEP |
| CAN-FD DLC classes | `backend/engineering/message_packing.py` | `valid_payload_bytes` | Packing service | IMPLEMENTED | CAN-FD must use legal payload classes | KEEP |
| Frame load estimate | `backend/engineering/capacity/calculators.py` | `estimate_frame`, `utilization_percent` | Capacity and packing services | IMPLEMENTED | Must not be calculated by LLM | REUSE |
| Capacity workbench | `backend/engineering/capacity/service.py` | `CapacityTimingService` | `/studio/capacity` | IMPLEMENTED | Uses persisted messages/interfaces | KEEP |
| Signal payload validation | `backend/engineering/signal_audit.py` | payload checks | Intelligence / Capacity | IMPLEMENTED | Requires correct message DLC/start bits | KEEP |
| Chain registration | `frontend/src/lib/agent/engineering-agent.ts` | `registerEngineeringChain` | Engineering agent tools | IMPLEMENTED | Reuse depends on stable packed names | KEEP |
| Interface detail UI | `frontend/src/components/engineering-workbench.tsx` | `InterfaceMessageList` | Engineering workbench | IMPLEMENTED | Direct-only filter hid related messages | ADAPT |
| Lazy backend imports | `backend/engineering/__init__.py`, `backend/engineering/capacity/__init__.py` | `__getattr__` | Core tests | IMPLEMENTED | Core tests loaded DB dependencies unnecessarily | KEEP |

Observed behavior: some interfaces showed no or only one message because raw chain generation produced one message/interface name per chain, and the UI only displayed exact `interface_id` matches.

Expected behavior: multiple compatible signals may share a message, and multiple messages may share one interface until projected load reaches the configured threshold.

Root cause: packing and interface allocation were not applied before the wizard/agent registration step.

Regression risk: generated names change for new projects. Existing persisted projects are not migrated automatically; their UI now explains/directs related message display.
