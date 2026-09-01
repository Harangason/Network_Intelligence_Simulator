# Architecture Compliance

## Current Status

The project is not yet compliant with the Python-first target. The first safe steps have been created: a neutral Python core model package, an explicit migration map and a deterministic-first semantic intelligence layer.

## Compliance Checks

| Rule | Current Status | Evidence |
|---|---|---|
| Python owns engineering logic | Partial | Capacity, routing, workflow and signal audit exist in Python; wizard generation and signal inspection still exist in TypeScript. |
| Core owns truth | Started | `backend/engineering/core/models.py` exists as first neutral contract. |
| Semantics are explicit and reviewable | Started | `backend/engineering/semantic_intelligence` contains ontology, alias resolution, modular classifiers and proposal-only confidence aggregation. |
| Technology modules own protocol behavior | Partial | Capacity calculators and industry registry exist, but no unified technology contract yet. |
| Services own calculations | Partial | Capacity and signal audit services exist; frontend still calculates bit requirements. |
| Agents orchestrate services | Partial | `backend/agent_core` exists; frontend agent still has deterministic generation and parsing logic. |
| Frontend visualizes results | Not compliant | Several `frontend/src/lib` files still contain engineering decisions. |
| No duplicate data models | Not compliant | Python models and TypeScript signal/capacity models both express engineering truth. |
| Regression tests exist | Partial | Focused tests exist for startup, scope rules, signal architecture, clustering and core models. |

## Immediate Guardrail

New engineering calculations and semantic rules should not be added to `frontend/src/lib` or React components. Add them to Python services, expose them through the API and keep uncertain results as reviewable proposals.
