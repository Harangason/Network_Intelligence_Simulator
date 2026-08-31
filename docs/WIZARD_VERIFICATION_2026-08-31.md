# Wizard verification: neu 9

Status: Data Science is populated with diagnostic findings and reviewable
proposals despite capacity failures. Simulation remains correctly blocked by
unresolved timing/load constraints. See the follow-up verification below.

## Evidence and fixes

- Input: `I:\PycharmProjects\neu 9.txt`, including the explicit 100 actuators.
- Frontend service logs showed an 8-second timeout during topology creation and
  repeated submission of the original specification for an existing run.
- The global assistant and wizard could both initiate continuation. Wizard-owned
  runs now exclude the global auto-continuation; concurrent builds of the same
  project are rejected, and polling requests no longer overlap.
- Expensive downstream operations use a 180-second timeout. The test topology
  plus parameter operation took about 20 seconds, exceeding the former limit.
- The complete run status is persisted across all nine workflow stages.
  Explicit retry resumes downstream work without recreating the model.
- Premature "Fertig stellen" previously cleared the saved wizard context.
  Completion now requires the selected stages to be complete; closing the dialog
  preserves its context.
- Actuator counts, synonyms, generated chains, enforcement rules and exact
  completeness checks now include ActuatorController. Legacy projects without
  an actuator limit remain unconstrained rather than receiving an implicit zero.
- Default architecture is gateway-direct, still requiring explicit approval.
- All eight wizard steps are visible. Step 7 reviews editable device quantities;
  step 8 shows status. Device categories and expandable name lists replace the
  combined hardware total.
- Capacity analysis now uses the appropriate protocol speed for mixed networks,
  retaining primary-technology and interface-specific overrides. CAN speed no
  longer leaks into Ethernet or LIN calculations.
- Blocking findings and the actual failing step are shown instead of marking
  the previously completed parameter step as failed.

## Live verification

Separate test project: `network-project-20260831050020542-596ac3f0`.
Run: `ec166863-6cda-4853-a227-fb2202f1dedd`.
Original project data was not replaced or cleared.

The full sample was entered through the wizard. Architecture approval was
explicitly exercised in this test project. Step 7 detected and submitted:

| Device category | Required | Persisted |
| --- | ---: | ---: |
| Gateways | 1 | 1 |
| ECUs | 50 | 50 |
| Sensors | 100 | 100 |
| Actuators | 100 | 100 |

Negative counts blocked submission. The first build created 251 canonical
chains and 250 valid draft routes, then waited at the human-review gate. After
test approval, 251 topology nodes and 250 edges were materialized, and parameters
were saved. Reloading and reopening restored step 8 and the same run ID. Explicit
retry retained the model and routing instead of rebuilding them. Completion is
disabled while capacity errors remain.

## Original blocker (before follow-up)

Topology synchronization originally assigned every connection of a protocol to
`network-lin`, `network-can_fd`, or `network-automotive_ethernet`, even when the
gateway has separate physical ports. With the correct technology speeds the
current generated sample produces:

| Network | Bitrate | Average load | Burst load |
| --- | ---: | ---: | ---: |
| LIN | 19,200 | 1125.16% | 1687.73% |
| CAN-FD | 2,000,000 | 69.28% | 103.92% |
| Ethernet | 100,000,000 | 1.38% | 2.07% |

Some generated fast LIN sensor defaults also violate latency constraints. These
are real findings, not a stalled animation. No error gate was bypassed and no
Data Science result was fabricated. Approval was requested before changing the
network segmentation semantics: separate physical gateway ports as separate
segments, shared bus ports as one segment. The user subsequently approved this
semantics; it is implemented and tested in the follow-up below.

## Initial tests

- TypeScript: `tsc --noEmit --incremental false` passed.
- Focused frontend suite: 27 tests passed, including deterministic 25-pass
  extraction checks, actuator count corrections and concurrent-build guards.
- Backend: 275 passed, 10 skipped. Skips require ENGINEERING_TEST_DATABASE_URL;
  the real database/UI checks above were performed separately.
- Browser: default selection, mandatory architecture approval, all eight steps,
  editable quantity validation, category lists, reload recovery, review gate,
  explicit retry and premature-completion guard checked.
- `git diff --check` passed.

The 25-pass checks are deterministic parser/routing tests, not 25 completed
live runs through Data Science. No commit, push or shutdown was performed.

## Follow-up: names, segments, diagnostic Intelligence

- Hardware type suffixes are removed from canonical device names and wizard
  extraction. Device type and stable IDs remain separate properties. Same names
  across different device types are no longer false duplicate candidates.
- Fixed an additional migration defect: EGRValvePositionSensor was inferred as
  an actuator because of "Valve". Explicit assigned types now take precedence;
  name cleanup cannot change an existing device's type.
- Physical networks are connected components of ports, not whole gateway
  devices. Shared ports share a bus; separate gateway ports remain separate.
  Layout and label changes do not alter network identity. Routing interfaces,
  exported simulator networks and protocol speeds use the same segmentation.
- System ownership is independent of direct gateway routing. Explicit system
  owners are preserved; semantic ownership is marked as inferred. Ambiguous
  participants stay unassigned instead of being attached to the first ECU.
- Capacity ERROR automatically persists an Intelligence diagnostic snapshot.
  Missing simulation/preflight evidence remains visible. The workflow agent also
  attempts the diagnostic stage when earlier technical gates block execution.
- Distribution proposals pack coherent cluster portions using the maximum of
  average, peak and burst load. Oversized clusters may span buses without losing
  their system ownership. Proposals retain route/device IDs and residual risks.
- Individual routes exceeding the target are not falsely solved by adding buses.
  The UI shows conditional cycle and CAN-FD alternatives. These are bus-load
  estimates, not validated timing, safety or gateway-interface approvals.
- New generated defaults no longer assign fast sensors to LIN by list position;
  ECU LIN defaults use a suitable slower template cycle. Existing imported timing
  requirements are not silently changed.
- Review history is matched by category and affected objects, supplied to later
  recommendations and AI review, and never inherited as a fresh approval.
  This is versioned evidence/feedback reuse, not neural-model training.

### Live diagnostic loop

The same isolated 251-device sample was used. No original user project was reset.
After physical reconciliation there are 250 configured port segments and 250
routes. This reflects the existing independent-port topology, not a claim that
250 physical buses are an optimal final design.

All **25/25 live capacity -> automatic Intelligence loops passed**:

- Every pass persisted a new capacity and diagnostic snapshot.
- Every diagnostic referenced that pass's actual capacity snapshot.
- Every pass produced 40 findings, 37 recommendations and 12 load plans.
- All 251 node IDs and 250 edge IDs remained unchanged.
- Simulation and Results remained EMPTY; they were not fabricated as successful.

Final loop snapshots:

- Capacity: `50cac079-2890-48f2-b466-991dcbc258f7`
- Intelligence: `3f4e5cb0-16c8-417f-a3ea-16c685c9a9f3`

The corrected sample has 238 NORMAL, 10 CRITICAL and 2 OVERLOAD segments. The
maximum burst load is 178.125%, not the former protocol-wide aggregate of
1687.73%. Twelve legacy LIN routes still exceed the 60% target. For example,
the 10 ms door route has 89.0625% burst load; the calculated CAN-FD alternative
is about 1.29% at the same cycle, conditional on compatible hardware and review.
Eighteen sensor/actuator system assignments remain unresolved; they are not
arbitrarily assigned. The gateway itself is also outside a functional ECU owner.

### Additional AI integration defect

The first UI test of "KI pruefen lassen" wrongly classified the supplied device
evidence as a new specification, bypassing the LLM and creating two interfaces.
Only these timestamp-verified, unreferenced test interfaces were deleted; the
existing topology and approvals were reconciled without approving new routes.

Review intent now blocks specification creation and automatic workflow execution.
The review path reads current diagnostic evidence and runs a text-only model
evaluation with no mutation tools. A regression test covers device names in
review evidence. Model, routing, network and parameter versions were checked
unchanged across the corrected live review. Proposal persistence was tested
separately through "Vorschlag vormerken" (status PROPOSED, no application).

The local fast model initially emitted pseudo-tool JSON, then a generic review.
Technical reviews now select the configured deeper local model in hybrid-demand
mode and receive dedicated review instructions. Mathematical calculations stay
deterministic; AI interpretation is clearly separate from the numeric snapshot.

The final local deep review (`qwen3.8:27b`, read-only) completed successfully.
It rejected the unchanged one-bus proposal as insufficient and examined the
provided CAN-FD alternative. Its prose is advisory, not a validated engineering
result. The model generated about 3-4 tokens/second on this host. Versions of
engineering_model, routing, network_editor and parameters stayed unchanged.
Current populated Intelligence snapshot: `d526a305-282d-49a2-ab08-ed9ea282f43f`.

### Final checks and limits

- Backend: 289 passed, 10 skipped (database fixture skips as noted above).
- Focused frontend: 29 passed; TypeScript no-emit check passed.
- Desktop browser: populated diagnosis, missing-evidence warning, load plans,
  conditional alternatives, proposal persistence and read-only AI review checked.
  Screenshot checked at 1280 px; no document-wide horizontal overflow. No mobile
  viewport verification was performed in this follow-up.
- The final backend wording improvement for unsplittable routes still requires
  a service reload. Automatic approval rejected that last restart because the
  active process could not be unambiguously associated with its port. Explicit
  user approval was requested. Functional diagnostic/segmentation/review-history
  changes are already running; the service was not stopped after the rejection.
- These are 25 diagnostic passes, not 25 successful end-to-end simulations or
  25 independent fresh project creations. No commit, push or shutdown performed.

## Intelligence refresh stability

The Intelligence workbench unmounted its content on every 10-second poll,
focus event and workflow notification. This also reset table pagination. Any
failed snapshot read triggered a new assessment, and a failed proposal read
prevented a successfully fetched snapshot from being displayed.

- Background reads now retain the current snapshot and mounted view.
- Poll/focus/workflow requests share one in-flight read per project; explicit
  reassessment is serialized behind an existing read.
- Only HTTP 404 triggers initial assessment. Network, authorization and server
  errors are displayed without silently starting a new assessment.
- Snapshot publication no longer depends on the proposal list succeeding.
- Reads use a captured project ID. Old project responses and responses after
  unmount are ignored.

Verification: 10 loader regression tests passed, including 25 background
refreshes, overlapping events, failures and project changes; all 29 existing
focused frontend tests passed. TypeScript passed with `--noEmit --incremental
false` (the existing incremental cache was not writable). Browser verification
retained issue page 2/2 and the populated Analytics view over multiple polling
intervals, without a loading placeholder or service error. No backend restart,
project rebuild, commit, push or shutdown was needed for this fix.

## Capacity lists and inline drilldown

- Network details expand in a full-width table row immediately below the selected
  network; the same button closes them. Paging and sorting close the selection.
- Capacity lists use 50 entries per page, including networks, messages, routes,
  timing, critical routes, gateways, recommendations and drilldown route lists.
- Snapshot refreshes preserve the current page. Shrinking result sets clamp it
  to the available range; sorting starts the network list at page one.
- Four pagination regression tests and the ten Intelligence loader regressions
  passed. TypeScript and `git diff --check` passed.
- Browser: five network pages contained exactly 250 unique networks, 50 per
  page. The 251 messages ended with one entry on page six. Route and timing
  views showed 50 entries; critical routes and recommendations showed their
  complete shorter lists. Inline expand/collapse and page-change collapse were
  verified, with no document-wide horizontal overflow at the desktop viewport.

## Capacity network signal inspection

- The expanded network detail now loads current Engineering sources and shows
  Sender, participants, interfaces and system frame assignment for the selected
  network.
- Signal checks display message assignment, data type, start bit, byte order,
  min/max, factor, offset, configured bit length and computed minimum bit need.
- Oversized, too-small, overlapping, out-of-payload and incomplete signal
  configurations are shown as explicit findings. The check is advisory and does
  not mutate approved messages or signals.
- Message occupancy stays separate from signal width, so an 8-byte message can
  still contain a correctly configured 16-bit signal.
- Browser verification for `network-lin-e18819ce3a38` showed two participants,
  one inferred system frame, one message and one signal. `Rollrate` remained
  PASSEND with 16 configured bits and 16 computed bits for -300..300 deg/s at
  factor 0.01.
- Nineteen focused capacity tests passed. TypeScript and `git diff --check`
  passed.

## Generation signal stability

- New-project template generation no longer assigns every generated signal a
  fixed 16-bit width. The wizard generator computes signal bit length from
  min/max, factor, offset and signedness, then chooses the smallest matching
  message DLC.
- Backend Capacity now persists a generation signal audit in `signal_quality`.
  It records sender, participants, system frames, message count, signal count,
  computed bit need, configured signal width and message occupancy.
- Capacity findings now expose oversized, too-small, overflowing, overlapping
  or incomplete generated/imported signals. These findings are advisory and do
  not mutate approved engineering data.
- Intelligence includes the same `signal_quality` block so the KI path can use
  deterministic signal evidence for proposals instead of relying on sparse bus
  load numbers alone.
- Regression checks covered 64-bit-to-8-bit detection, Rollrate remaining 16
  bits at 0.01 resolution, sender/participant/system-frame reporting, and
  new-project DLC sizing.
