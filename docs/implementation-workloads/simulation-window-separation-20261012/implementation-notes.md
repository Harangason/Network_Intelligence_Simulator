# Simulation controls and window separation — 2026-10-12

Desktop command form now places scenario, duration, playback speed, seed, trace
formats and execution controls in one row, with reduced panel padding. Responsive
layouts wrap on narrower screens to preserve field readability and controls.

Workspace tools visibly separate Simulation and Trace-Analyse into two columns.
The existing WindowDescriptor.board_id is authoritative for shared view names
such as signals/sequence/load. Previously every non-simulation view was routed
to trace-analysis and presets/profile restore navigated the current page. Now
simulation child windows retain /studio/simulation and trace actions explicitly
request /trace-analysis. Popup blocking offers destination-labelled new-tab links.
Presets and restore open additional windows and never replace the current page.
Simulation initialization also reads the validated view query. The simulation
page formerly rendered TraceAnalysisWorkbench for every secondary window even
on /studio/simulation. It now reuses ModelSimulationRunner with readOnly=true:
simulation tabs/playback remain available but command form, scenario/fault
editing and preflight scope changes are absent. Only the primary publishes view
changes; linked time/source context continues through the existing store.
Actual secondary sequence tabs and restored historical job were verified.

Profiles retain optional primary_board/secondary_boards metadata, validated in
the existing v1 profile contract. Legacy profiles remain readable with their
previous trace destination semantics for shared view names. Source identity,
project, exact times and linkage mode still use the existing context/store.
No new analysis engine, shared-state authority or backend/data-model change.

Nine focused tests, TypeScript, frontend compilation and actual browser popup /
responsive checks passed. A verifier first compared a compact project alias to
the canonical network-project- prefixed ID; the read-only check was corrected to
compare the existing equivalent IDs. No application behavior was changed for that
fixture mismatch. The secondary-page rendering failure was reproduced from the
actual popup body, corrected at its page owner and rerun in production.
Only temporary local browser profile metadata was created and
removed; no new simulation, backend test database or full campaign was used.

User-authorized direct frontend delivery: patch b0d5da95feed.
Artifact a42c3f4f13d05c56d6ca5ad9cd07053565a0676550c86ee94d112de5905b5508; base image unchanged sha256:afffad957644b4f77b3ba831f61a62d8139a6f7b07cd3779917b812a92c3a179.
Rollback /app/.frontend-ui-rollback-b0d5da95feed; archive F:\CodexOrdner\visualizations\2026\10\09\01a11f88-d6c9-7b63-bec3-26450a86e52c\frontend-ui-b0d5da95feed.tar.
No image or full release gate; base-image PASS does not cover this overlay.
It survives restart of this container. Container recreation requires archive
restoration or release of canonical updated source. EIP remains untouched.
