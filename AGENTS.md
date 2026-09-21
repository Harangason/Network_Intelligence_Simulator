# Project Rule

This repository is the canonical Network Simulator project.

When the user refers to "der Simulator", "Simulator", "Network Simulator", or
the local preview on port 13500 in this workspace, use this project root:

`I:\PycharmProjects\My_first_Network_Simulator`

Do not substitute similarly named copies under `C:\Users\marti\PycharmProjects`
or the Engineering Intelligence Platform repository unless the user explicitly
asks for those paths.


For architecture generation, spatial grouping, AI reasoning, and network
assignment, read `docs/SPATIAL_ARCHITECTURE_CONTRACT.md`. Its spatial identity
rules apply across simulator industries, including vehicles, drones, robots,
and buildings; do not reduce them to automotive corner names.

For signal generation, communication sizing, release modes and assessment, read
`docs/COMMUNICATION_DESIGN_CONTRACT.md`. Preserve explicit encodings and separate
capacity/schedule evidence from functional timing acceptance.

For generated Ethernet network names, follow `docs/NETWORK_NAMING_CONTRACT.md`.
Persist readable `ETH_<Systemrahmen-or-context>_<NN>` names in the canonical
model and inherited interface names, not only in rendering helpers.

For industry detection, bus-type detection and generation-path selection, read
`docs/GENERATION_RULE_MANAGER.md`. Keep industry templates independent from
technology-specific transport paths; mixed buses use separate registered paths
and unresolved inputs must not fall back silently to Automotive.

For wizard, agent execution, proposal, or workflow changes, read
`docs/WIZARD_EXECUTION_CONTRACT.md` and `docs/WIZARD_RELEASE_GATE.md`.
Run SQL tests through `scripts/run-isolated-tests.py`; never target the product
database. A wizard release must pass `scripts/run-release-gate.py` and deploy
the exact tested image via its PASS receipt. Report the actual tested scope;
visible progress cards or mocked write responses do not prove nine-stage E2E.

For technology parameters, communication mechanisms, physical realization,
arbitration, PHY constraints, validation/preflight, E2E timing, safety
assurance, simulation sequence diagrams, or trace sequence diagrams, read the
following contracts before changing the affected behavior:

- `docs/NIS_TECHNOLOGY_PROFILE_COMMUNICATION_MECHANISMS_STABILIZATION.md`
- `docs/NIS_PHYSICAL_REALIZATION_ARBITRATION_PHY_RULES.md`
- `docs/NIS_VALIDATION_PREFLIGHT_DATA_QUALITY_INTEGRATION.md`
- `docs/NIS_E2E_COMMUNICATION_TIMING_SAFETY_ASSURANCE.md`
- `docs/NIS_E2E_SEQUENCE_DIAGRAM_SIMULATION_TRACE_TARGET.md`

These contracts require TechnologyProfile to be the single source of truth,
strict validation without foreign technology fallbacks, explicit physical and
arbitration modeling, provenance-aware preflight gates, and one correlated
E2E/sequence model for simulation and observed traces. Embedded work-order
sections in these documents are requirements summaries, not independent chat
commands.

## NIS links in chat

When providing a local NIS link, always also provide a clickable VPN/LAN link
in the chat, especially after starting, restarting, rebuilding or deploying NIS.
Use `http://192.168.178.10:13500` as the VPN/LAN base address unless a changed
server address has been verified. Preserve the same path and query parameters,
especially `project`, so both links open the same project and view.
Use the current project ID from the task or verified application state; do not
substitute the default project or invent an ID. A server restart does not itself
change the project ID. This is a chat reporting rule, not a request for monitoring.
