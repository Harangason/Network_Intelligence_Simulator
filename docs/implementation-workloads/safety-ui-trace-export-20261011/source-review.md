# Safety UI / trace export — 2026-10-11

## Implemented source changes

1. Scoped CSS module gives the safety panel padding, four responsive metric columns, readable fieldsets, wrapped text and table spacing. No global style rewrite.
2. The JSON textarea is replaced by labeled controls for norm/edition/applicability, hazard/goal references, optional integrity, route bindings, timing bounds, protection mechanisms, fault cases and optional original EIP source revisions. Existing canonical configuration and expected_version CAS are retained. An open editor is bound to its original active project.
3. The safety read endpoint reuses network_scene.confirmed_groups on the current canonical topology and original wizard cluster graph. Canonical hardware corrections retain priority. The browser groups routes by stable cluster and system-owner IDs and displays sender/receiver names with search and cross-cluster destination labels. This is a read-only display projection, not a model reassignment.
4. Canonical CAN/CAN-FD exports write one can_network.dbc containing every message and signal in the selected run's CAN scope. Same canonical messages on multiple buses are deduplicated; receivers and network provenance are retained. Wire identifiers, scalar encodings, signedness, Motorola alignment and FD/extended-frame flags are preserved. Ambiguous IDs with different canonical definitions or publishers fail before producing native artifacts. BLF-only export retains independently reused IDs and channels. Ethernet and LIN definitions are not represented as fictitious CAN messages.
5. The simulation trace-format state starts empty/loading. Registered project profiles determine its initial selection; there is no speculative JSONL/CSV default. Project switches clear manual override and stale picker state; Start and Save wait for format resolution. Explicit user format choices within the loaded project remain respected.

## Review and validation boundary

Manual source review only, using the before/after files and owned diff. Reviewed API shape, project scoping, CAS, native profiles, source identities, optional values, controlled multiline inputs, EIP duplicate-reference feedback, and aggregate ID conflicts. Regression specifications were updated for one DBC, original decoder values, collision rejection without model mutation, and BLF-only channel separation; none were executed.

No unit tests, frontend/browser tests, typecheck, lint, simulation run, production data mutation, build or release gate was started. Runtime/UI functionality remains unverified for this source revision. No claim of a test PASS or campaign PASS.

## Production delivery

User requests no tests. AGENTS.md requires a complete current-source PASS and scripts/release-and-deploy.py; the launcher has no shortened/no-test delivery mode. Previous PASS/build 578b113c9473 does not cover these application changes. Deployment is therefore pending the user decision on the conflicting test requirement. The existing production stack and all archived images are retained. EIP production remains excluded.
