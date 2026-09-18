# NIS source map

The project is organized by responsibility without changing its programming
languages or runtime contracts. Python remains the backend implementation
language and TypeScript/React remains the browser implementation.

## Primary entry points

- `backend/nis/`: complete navigable architecture and provenance catalog.
- `backend/workflow/`: canonical identity and ownership of the nine workflow stages.
- `backend/specializations/industries/`: industry vocabulary and template ownership.
- `backend/specializations/technologies/`: independent transport technology ownership.
- `frontend/src/features/workflow/`: browser entry point for each workflow stage.

Existing modules remain available through their established import paths. A
feature entry point may therefore delegate to an existing implementation while
consumers migrate. This compatibility boundary prevents a folder move from
changing API behaviour, persistence or engineering semantics.

## Workflow provenance

| Stage | Backend structure | Frontend feature |
| --- | --- | --- |
| 01 Engineering model | `backend/workflow/stages/stage_01_engineering_model` | `frontend/src/features/workflow/stage_01_engineering_model` |
| 02 Routing | `backend/workflow/stages/stage_02_routing` | `frontend/src/features/workflow/stage_02_routing` |
| 03 Network editor | `backend/workflow/stages/stage_03_network_editor` | `frontend/src/features/workflow/stage_03_network_editor` |
| 04 Parameters | `backend/workflow/stages/stage_04_parameters` | `frontend/src/features/workflow/stage_04_parameters` |
| 05 Capacity and timing | `backend/workflow/stages/stage_05_capacity_timing` | `frontend/src/features/workflow/stage_05_capacity_timing` |
| 06 Validation | `backend/workflow/stages/stage_06_validation` | `frontend/src/features/workflow/stage_06_validation` |
| 07 Simulation | `backend/workflow/stages/stage_07_simulation` | `frontend/src/features/workflow/stage_07_simulation` |
| 08 Results and analysis | `backend/workflow/stages/stage_08_results_analysis` | `frontend/src/features/workflow/stage_08_results_analysis` |
| 09 Intelligence | `backend/workflow/stages/stage_09_intelligence` | `frontend/src/features/workflow/stage_09_intelligence` |

`backend.nis.architecture_catalog()` exposes the same map to Python tooling.
It includes source modules, inputs and outputs without importing or replacing
the implementation behind those modules.

## Dependency boundary

Industry selection supplies vocabulary, device classes and optional templates.
Technology selection independently supplies transport, topology, timing,
capacity and validation. Workflow stages orchestrate these services and merge
their output only at the canonical engineering-model boundary.

Runtime output, caches and test evidence are not source packages. They remain
outside the architecture namespaces and must not become import dependencies.
