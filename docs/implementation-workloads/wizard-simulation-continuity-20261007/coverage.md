# Wizard continuity and simulation qualification

Current user requirements (2026-10-07, project `20261007041943709-40764014`):

| Requirement | Existing executable source extended | Evidence scope |
|---|---|---|
| Return to saved status step without an initial project questionnaire or new START | `frontend/e2e/wizard.spec.ts`, existing small complete wizard case | Real pending proposal, saved parameters, reload, delayed workflow restoration, topbar return, run identity and canonical object assertions |
| Refresh outdated findings without human approval/application | `frontend/src/features/agent/lib/proposal-client.test.mjs` | Outdated/current/applied/rejected variants, project headers, one validation POST, no approval/application calls |
| Preserve changed values over the initial prompt/defaults | Existing small wizard browser case and `backend/tests/test_simulation_parameter_defaults.py` | Exact persisted SI rate and coherent CAN-FD prescaler; seed and run identity; original prompt cannot overwrite later scalar or scoped saved assumptions |
| Missing device evidence is informational for usable simulation configuration | `frontend/e2e/technology-parameter-review.spec.ts`, `backend/tests/test_workflow.py` | Real save/reload/read-only review, INFO classification, no false rate highlighting; central resolver, model errors still BLOCKED |
| Complete simulation inputs reach native models without fabricated hardware proof | `backend/tests/test_simulation_parameter_defaults.py`, `backend/tests/test_technology_parameter_review.py` | LIN/CAN-FD/Ethernet parameter artifact; LIN/CAN-FD runtime traces; unchanged actual qualification and timing fields; invalid rate, scope and proof remain rejected |
| Configured primary bus cannot hide missing other bus configuration | `backend/tests/test_simulation_parameter_defaults.py` | Missing LIN/Ethernet groups are incomplete; registered defaults fill missing groups while retaining saved CAN-FD values; read-only validation does not write defaults |
| Production delivery | Existing mandatory release-and-deploy pipeline | Complete release receipt, exact running image and readiness, live saved project/run/parameter digest comparison and UI restoration |

The independent Tool-Checker campaign remains in its existing repair phase. This work
extends existing executable test sources; neither a targeted regression nor the release
gate is reported as a new PASS for that independent campaign.

The first full gate was deliberately stopped before a candidate build when the mixed-bus
completeness defect was found. Its FAIL receipt is preserved; it cannot authorize delivery.
Only the complete gate for the final source and test manifest can authorize deployment.

Final targeted verification additionally covers the real captured 50/250/250 wizard:
all nine stages, interrupted simulation recovery with the same job identity, 1,404
canonical signals, 1,169 observed signals and 235 explicit transport exclusions.
All four selected browser cases passed without retries. The small complete case
asserts the saved 1 Mbit/s CAN-FD rate and prescaler on every frozen CAN-FD network;
the random seed belongs to the runtime root. Native I2C and Modbus configuration
dependency failures remain blockers.

The performance repair reuses the zoning sizing plan, reads each native medium-access
profile once per grouping, and memoizes frame costs only within an operating point.
Existing sizing/zoning regressions passed (86), rate-planning tests passed (40), and
startup tests passed (42). Initial backend readiness and backend restart both allow
90 seconds for the complete catalog and persisted-job recovery. The original wizard
progress, browser and native calculation watchdogs remain unchanged.

Complete final gate and production verification are pending until their own receipt
and live proof are sealed. Targeted PASS does not authorize deployment.

The additional native schema-role regression suite passes243 tests. Saved LIN,
CAN-FD and Ethernet resolve, calculate real native frames and report device
qualification as INFO even when UI default-generation is forbidden in the test.
Generated registry changes update detached role maps without stale metadata.
Captured native calculations match the immediately preceding built source exactly
(120 nominal groups,640 findings,120 plans). This diagnostic equivalence is
separate from the required real five-case browser and complete release gates.
The complete-request optimization passes 299 isolated native/proposal/workflow checks, including unchanged strict negative cases, scoped UPDATE/DELETE duplicate names, existing network IDs and heterogeneous payload/release loads. Native pure review output remains exactly identical for the captured 120 groups, 640 findings and 120 plans against validation source extracted from the preceding regular candidate; that diagnostic does not replace real browser or release verification.
The subsequent routing-return repair passes 195 isolated routing/proposal/periodic-acquisition tests. A complete selected canonical snapshot gives the same native output as SQL, remains detached during a review, and refreshes after a wire edit. Each route still reports its own invalid source/destination/payload/physical/duplicate/timing findings; prospective PERIODIC_ACQUISITION remains separate. Real large browser readiness and final delivery remain required.
The corrected topology SQL diagnostic preserves declared networks and returns VALIDATED (753 changes). It is intentionally stopped after profiling, so its pytest exit is not regression PASS. The observed parameter review costs 47.84s and topology validation 49.49s under profiling; scenario resolution repeats 1,304 times per request and copies LIN schema/constraints repeatedly.

After the topology performance repair, `topology-native-targeted.log` records **181 passing isolated SQL/native/API tests**, including different clocks, native provenance, nested capabilities, simulation assumption scopes, network identity, detached derivation output and updated generated profiles. `topology-native-equivalence.log` compares against validation and LIN timing code extracted from immutable regular candidate e6ef799ce239. Complete captured topology outputs match: 120 capacity groups, 640 findings and 120 bus-rate plans. Thirty LIN scenarios, including payloads 0–9, changed bitrates and explicit fixed layouts, retain identical derivations and frame estimates. No assertion or deadline was relaxed. Full browser/release verification is still pending.

The expanded large case subsequently reached its unchanged outer 20-minute test
deadline after successful individual returns. The existing full nine-stage case
now retains three real technology returns at each pending model, routing and
topology proposal. Three separate captured large review-only cases add nine
returns each at those phases. Total real return coverage increases from 27 to 36;
the full case retains all signal, ALL-scope, restart and nine-stage assertions.
Review-only evidence is explicitly labelled REVIEW_CONTINUITY_ONLY and cannot
prove workflow completion. The 20-minute case, 60-second return, 240-second
progress and 180-second manual-write budgets remain unchanged.

`review-suite-clock-targeted.log` records 51 passing watchdog/progress regressions.
`review-suite-case-list.json` collects eight cases against the new isolated stack;
collection alone is not browser PASS. The current eight-case browser execution
and complete release gate must pass before production delivery.

Native correctness follow-up: `native-consistency-regression.log` records 174
passing tests; `saved-current-graph-regression.log` records the strengthened
real MCP continuation with complete saved values (1 pass). Added checks cover
rate-only confirmation without hardware promotion, authoritative 100-Mbit PHY
selection, explicit incompatible PHY rejection, actual message MAC lengths,
conservative CAN-FD bounds and explicitly fixed 64-byte/CRC21 padding. The
captured isolated SQL diagnostic has zero remaining native schedule failures
after current-graph sizing; its deliberate diagnostic ERROR is not counted as
a passing test. No production database or user model approval was used.

The following run passed nine large parameter returns but failed the unchanged
240-second capacity watchdog. The continuation now invokes only native sizing
for complete saved parameters, with explicit incomplete-input rejection. Its
first regression run passed 174 tests. The later complete gate reported
21,687 backend passes and two failures (migration inventory and undeclared
padding in the stress fixture). Neither run authorizes delivery. The corrected
stress fixture retains the >100-channel threshold and complete graph/encoding
checks; it asserts simulation capacity separately from hardware qualification.
Current targeted tests, all eight browser cases and a complete final release
gate remain pending.

The large padded stress subsequently exposed a real downstream consumer bug:
distribution ignored valid `simulation_capacity` because hardware LOAD_KEYS are
null without qualification. The corrected consumer passes48 isolated planning
tests and the complete captured stress in the34-test targeted run. Native
assumption metrics drive the split without modifying source metrics or certifying
hardware; incomplete or invalid simulation metrics keep the whole bus unresolved.

The parent wizard's repeated stale full-proposal transfers were separately
observed in the actual failing browser trace. Status-first parent restoration
and compact polling pass12 client tests and typecheck. The60-second return
budget and all original review/run/data-preservation assertions remain intact.
The complete final gate includes all eight relevant browser cases. Any selected
case evidence extracted from its real report must retain the gate receipt,
image/source identity, test results and attachment paths; it is not an additional
execution or an independent campaign PASS. Delivery and live verification remain
pending until the final receipt and post-deployment proof exist.

Gate999af6c2d1bb completed21702 backend and588 frontend tests successfully.
Its96 actual browser cases gave95PASS and one strict final conformance failure
after the large case completed all nine stages. All individual large parameter
returns and Raspberry Pi/native-default cases passed. The five unevaluated
jitter routes were traced to an untouched default duration promoted by bulk
save. The duration-intent repair has72 isolated backend tests,6 client tests,
typecheck and a detached766-route frozen transport replay passing. The replay
retains communications and event budget and does not certify the complete
signal scope or release. The initial two-case browser check passed the primary
CAN-FD explicit same-value case; its newly added secondary Ethernet assertion
was corrected to respect the fixture's mixed-project scoped persistence. The
failed report is retained and both actual UI cases are rerun on the same image.
The subsequent complete gate must independently pass all original strict
conformance, duration intent, budgets and complete workflow assertions before
exact-image delivery. No historical test result substitutes for that gate.


The two real duration-intent UI cases passed on image66df/source d7d; the later complete gate failed only at the large case's unchanged20-minute boundary. A new measured workflow-read performance repair has152 isolated regressionPASS and three byte-identical frozen status replays. New cases retain absent versus explicitnull/malformed transport semantics, allfour outdated authored ID links, and invalid nativeEVENT/ON_REQUEST/release timestamps. This targeted proof is not full release or independent campaignPASS. Final8-case and2-duration evidence will be selected from the actual completePASS browser report and bound to its exact receipt/source/image; prior focused evidence is retained as history. Allnine full-workflow and strict conformance assertions remain unchanged.


Final complete release bd97b35d951d isPASS:21726 backend tests (2skips,56subtests),589 frontend tests,96 browser cases (47.2minutes), small and large independentHTTP acceptance. The unchanged full50/250/250 browser case passes allnine stages and complete conformance in16.0minutes; independent model/routing/topology returns pass in4.6/7.1/8.8minutes. Exact production image sha256:d3e0832d2fb6e241da0f09112150203386edee5e3d937cbe8854e668e1a4a16e isDEPLOYED andready with source d982fac5e281cbd03df018259d611569ca3322d35b5fa0cf3697ded3bbc51b9a. Live human project20261007041943709-40764014 returns through the real button toStatusübersicht Schritt5von5; parameters areFreigegeben. Proposal aa7c0504-1cf4-4d09-b2e8-6ce28f8a2b49 is freshlyVALIDATED andstillnotapplied (canonical_count0); run1dfcae6a-a187-498f-b85b-c9cfb5245f92 and exact saved parameterSHA71e63bc6401a1cd75b726d7d9ecc97551ecac0187b751bb5a0b14f54f088fcb9 remainunchanged. All168 LIN device-proof findings areINFO with usable simulation parameters. Existing unconfirmedCAN-FD/Ethernet groups remain separate, and no human parameter save/approval/application was performed. Screenshots live-parameters.png/live-wizard.png and live-wizard-dom.txt record the actual product UI. The eight relevant and two duration cases were selected from the actual completePASS report, notrerun/invented; their exactreceipt/image/source bindings are retained. The independent Tool-Checker campaign remains REPAIR_1_ACTIVE and isnotclaimedPASS.
