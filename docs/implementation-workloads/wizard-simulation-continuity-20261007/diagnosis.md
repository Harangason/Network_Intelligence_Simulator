User requirement: saved simulation configuration must survive returning to the running wizard; missing actual device evidence must not block simulation.

Observed live state: existing run 1dfcae6a-a187-498f-b85b-c9cfb5245f92, step 5 status overview; proposal aa7c0504-1cf4-4d09-b2e8-6ce28f8a2b49 OUTDATED after parameter save. No canonical hardware objects applied.

Product causes: questionnaire rendered before asynchronous restoration, restoration failures silently ignored; review reload does not refresh OUTDATED findings; parameter artifact and preflight use actual-only proof validation; device-only capacity finding classified REVIEW and therefore blocks simulation; simulation snapshot transport uses actual-only ingress. Saved prompt rate precedence can overwrite later user edits.

Scope: operational simulation under stored assumptions; actual hardware capacity, measured timing and safety qualification remain unverified. Missing/invalid configuration, scope, provenance, native schedule and physical/model inconsistencies remain blocking. Existing tests extended, independent campaign state not altered.

The complete gate for source 608a20cd failed two cases after 21,654 passing tests.
The full wizard simulation exposed a product schema gap: CSV export rejected the
new timing_basis/hardware_evidence/functional_timing_accepted fields. The serializer
now includes these columns explicitly; existing native LIN/CAN-FD trace tests
verify CSV and JSONL preserve the scenario evidence without ignoring extra fields.

The mixed robotics parameter test still expected valid saved DDS assumptions to
require actual hardware qualification before configuration could complete. This
contradicts the user's explicit simulation-default and nonblocking-device-evidence
requirements. Its acceptance now checks native saved assumptions, no inherited
Ethernet bitrate or invented DDS registered source, false hardware qualification,
and rejection of forged cross-technology provenance. No model, native timing,
physical or provenance validation was relaxed. The failed receipt cannot authorize
deployment; the final version must pass a new complete gate.

The next complete gate (e9e540f4d7a2/951b0d517929) passed 21,656 backend tests
and 582 frontend tests, but failed four browser cases. The small restore test
removed a still-running delayed request handler; cleanup now waits for completion.
The I2C/Modbus cases asserted missing device references although the actual
blockers are native dependency errors. Assertions now retain these native
blockers, no generated device source, empty simulation stage and no simulation
job. These three corrected cases passed in the first isolated browser rerun.

A second rerun with additional frozen-configuration assertions lost readiness
after the disposable application's restart; its subsequent two navigation
failures were connection refusals. It is not a passing verification. The next
diagnostic runner preserves container state and logs before owned-stack cleanup.
The original full gate's large captured graph independently exceeded the unchanged
four-minute contiguous-stage watchdog at parameters (frontier 3/9).

Profiling the unchanged full captured 50/250/250 SQL test showed 615 seconds in
parameter generation. Spatial zoning already performs sizing and capacity;
generation then repeated sizing preview with no intervening edits. Grouping
also copied the entire profile for every message, costing 35.5 seconds across
three calls. Generation now reuses the completed zoning sizing plan; grouping
reads the detached medium-access attribute once per technology. Rate planning
reuses frame estimates only within a fixed native operating point and payload
size, while each message keeps its own release period. No watchdog extension,
validation bypass or reduced model/traffic fixture is allowed. The original
diagnostic test completed successfully in 27:21 including profiling overhead;
86 existing parameter/sizing/zoning and 40 rate planning tests pass after repair.

The next diagnostic browser pass completed all nine small-project stages but
failed the new frozen-value assertion: transport fields are stored in scoped
assumptions and physical network rows, not necessarily at the runtime parameter
root. The captured frozen network has data_bitrate=1000000,
can_fd_data_prescaler=2, _rate_evidenced=false and hardware_evidence=false.
The assertion now checks seed at the runtime root and the exact edited native
rate/prescaler on every frozen CAN-FD network. No expected value was removed.

The subsequent I2C restart was terminated by the launcher at 21.66 seconds
(exit 1, no OOM, fixed host port), with no Python backend exception and the
backend still importing. A diagnostic container measured the required complete
import/catalog construction at 20.5 seconds with profiling. Backend startup and
automatic backend restart now use a bounded 90-second readiness allowance;
health must still match the launcher instance, and dead processes fail promptly.
Frontend/database readiness and all wizard/native/browser watchdog budgets are
unchanged. All 42 existing/new server startup cases and TypeScript checks pass.
Actual restart, large captured graph and the final complete gate remain required.

Final targeted browser verification on regular candidate ee8b5acd70fb (source
97f1125a9d02) passes all four existing cases without retries. The small wizard
passes all nine stages, delayed restore, same run/no START, save/reload, genuine
application restart and frozen 1 Mbit/s CAN-FD network rate with prescaler 2.
I2C and Modbus retain genuine native dependency blockers and start no simulation.
The exact captured 50/250/250 graph passes all nine stages, current watchdog
budgets, actual interrupted-job recovery, 1404 canonical signals, 1169 observed
signals, 235 explicit exclusions and complete scope/conformance checks. Its run
takes 16.3 minutes, the four-case suite 18.6 minutes. No test fixture, stage
budget, validation or signal-count assertion was reduced. Production still
requires the final complete release PASS and exact-image deployment.
# Concurrent verification input change during the final gate

The application identity remains `97f1125a9d02a7e31b9914a27cbaa52d98efae80013ef81f2bcf32eced8b0ce3`.
During gate `140e4854c416`, independent work extended `frontend/e2e/wizard.spec.ts`
and `frontend/e2e/support/native-transport-fixtures.ts` with repeated parameter
save/return cycles across LIN, CAN-FD and Ethernet. The verification fingerprint
therefore changed from `15e35f0a39aa28a73bc1ef4dc09882c15e34a5610cd7320006d88ad378b925b8`.
These concurrent changes are preserved. This in-flight gate cannot authorize
deployment against the changed test manifest; a complete gate must retest the
same immutable application image with the current verification inputs.

# Additional real repeated-return findings

The independently extended large case exposed a catalog rendering error:
`TypeError: e.domains is not iterable`. The shared API client converted any JSON
body read failure on HTTP 200 into `{}`. The catalog loader now rejects incomplete
JSON and invalid collection shapes, retries the native read once, and offers an
explicit retry preserving saved project data. Only the complete native catalog
read uses a bounded 60-second transfer budget; other API and native watchdog
budgets are unchanged. Eight API regressions and typechecking passed. The existing
native default browser case now injects broken READ responses while all writes
still use the real isolated API, and verifies saved values after explicit retry.

Image `06a468de4d33` then passed three selected wizard cases but the large repeated
return remained pending beyond the existing 60-second review readiness budget.
Its trace shows full proposal reads costing 5-9 seconds each before an unfinished
validation POST. Restore now reads status first and validates stale proposals
directly, avoiding a stale full-body transfer. Current complete content is retained
when compact metadata matches its identity/revision; incomplete replacement content
must still be read in full. All 18 proposal/API targeted tests and typechecking pass.
The 60-second review and 20-minute whole-case watchdogs are retained.

The diagnostic runner briefly shadowed its output prefix with a Docker-name prefix,
so the actual four-case report is preserved under `nis-e2e-runtime--browser*` and
is not reported as five cases. Its exact owned stack was removed; its image remains.
The runner variable is fixed. The next run must prove all five cases before sealing.

Gate `140e4854c416` completed 21,659 backend tests, 2 skips and 56 subtests without
test failures, but correctly failed source identity after these repairs. It cannot
authorize delivery. Candidate `505245c8dcfa` was also rejected after a late catalog
shape correction. Their FAIL receipts and the regular images remain preserved.


The first final-source candidate preparation was blocked by disk readiness at
16.7 GiB free on I:. No guard was weakened and no historical Docker image was
pruned. Fifteen completed historical trace.zip files (5,324,293,180 bytes) were
copied to the explicitly writable F: evidence archive, each SHA-256 verified
before removing its exact original file. Each original location retains a
trace.zip.relocated.json pointer; receipts/reports/backup dumps were untouched.
The plan and completion manifests are storage-relocation-*.json. I: then had
21.6 GiB free and regular candidate 252b0f82237a began with disk/image budgets PASS.

The first five-case browser run against source977fea passed native catalog read
recovery, small full workflow plus repeated returns/restart, and both native
I2C/Modbus negatives, but the large first LIN return remained pending after60s.
Its diagnostics are preserved under before-schema-roles-catalog-*; the concurrently
started full gate ffd68f3a0941 was explicitly stopped with FAIL and its owned
isolated database removed. No candidate from those runs authorizes delivery.

Captured-input profiling (4135 pending changes, empty canonical model) found
2290 UI parameter_fields calls inside saved-value review, costing36.6s under
profiling by regenerating constrained default proposals to look up schema roles.
A lightweight registry.parameter_roles now reads the same labeled native schema.
Saved scenario ingress and LIN reference classification use it; review metadata
is reused only within a single call and technology. LIN planning reads only the
registered schema and constraints. Native constraints/provenance and missing
operational facts still execute. 243 isolated targeted tests pass, including
saved native execution without any parameter_fields/default-generation calls.

The first diagnostic comparison accidentally used the task's initial before
snapshot, predating the deliberate device-hint changes, so findings comparison
failed. That diagnostic FAIL is preserved. The corrected comparison uses source
extracted from the actual previous regular image252b0f82237a and verifies exact
identity of120 capacity groups,640 findings and120 rate plans. See
schema-role-equivalence-current.log. Diagnostic replay uses only the captured
pending graph and native calculators; it is not a SQL/UI/E2E completion proof.

Full SQL validation profile: 73.3 s, 121 network reads/124 workflow reads, 3.59 million name comparisons, 653 complete message profile copies. The newest regular candidate still has four passing browser cases and a failing large return. No delivery. Repair targets repeated work while preserving strict semantics and existing readiness budgets.

Full SQL validation profile: 73.3 s, 121 network reads/124 workflow reads, 3.59 million name comparisons, 653 complete message profile copies. The newest regular candidate still has four passing browser cases and a failing large return. No delivery. Repair targets repeated work while preserving strict semantics and existing readiness budgets.

Regular candidate cec9d47d49b0: four browser cases pass; large successfully saves/reloads/returns nine times before model approval, then fails first routing return at the unchanged 60-second readiness budget. The isolated routing profile has 6,511 SQL executions/12,884 connection contexts for 766 routes. Complete current canonical snapshot is already supported by strict RoutingValidator and has SQL-equivalence/foreign-context/physical-removal tests. No deployment.
### Topology return diagnostic, 2026-10-07

Regular candidate e6ef799ce239 passes the four smaller browser cases and all nine model plus nine routing save/reload/return cycles. The large case fails its unchanged 60-second readiness assertion on the first topology return at 20.2 minutes. The trace records the parallel parameter review GET taking 51.219 seconds; topology POST validation remains pending until the assertion fails. Results and cleanup are retained under `before-topology-catalog-*`. No release gate PASS or delivery exists for this candidate.

The first two standalone topology measurement inputs were incomplete: their diagnostic `save_parameters` calls replaced the complete parameter document, removing declared networks. Their `PROPOSED` outcomes and missing-network findings are **diagnostic input errors, not established product defects**. These artifacts remain available for audit and must not support a claim about topology correctness. The corrected measurement preserves the complete current parameter document and explicitly asserts unchanged declared networks before examining the same native saved technology values. It exits with an intentional diagnostic failure after measurement; that exit is not a passing regression.

### Browser scope partition, 2026-10-07

Candidate 27a216bd0002 (source d34420cf, image d1192019) passes the four
smaller browser cases and individual large model/routing/topology return checks,
then reaches the outer 1,200,000ms test timer during readProject. This is the
expanded test's aggregate deadline, not an individual 60-second readiness
failure. The complete failure artifacts remain under before-review-suite-catalog-*.

The contract's 20-minute full-case budget stays intact. Review detours are
partitioned into three explicitly review-only large cases, each exercising nine
real save/reload/return cycles. The full nine-stage case retains nine detours and
all original completion/restart/encoding assertions. This raises total return
coverage to 36 while keeping all deadlines and strict native checks unchanged.
The image is reused because only verification inputs changed. Eight-case
collection and 51 watchdog tests pass; execution and release delivery remain
pending and cannot be inferred from collection.

The first partitioned execution passes four smaller cases and the integrated
model returns, then fails the first routing edit expectation: the test reused
seed42 with otherwise identical values and received VALIDATED rather than
OUTDATED. This is an idempotent-save test setup error, not evidence of a product
reset. Its completed trace and failure log remain under before-idempotent-seed-*.
The remaining run was stopped explicitly through its verified Playwright process
tree; the runner removed only its four disposable resources, all exit0. No PASS
is claimed for that interrupted run. The full case now uses seeds41,43,42 at the
three phases, retaining every assertion, the final seed42, and all deadlines.

The corrected seed run passed all nine integrated model/routing/topology
returns, but the full workflow then failed native preflight: two LIN schedules
and eight Ethernet profiles. Captured disposable SQL reproduces those findings.
Confirmed rates previously short-circuited native simulation configuration;
after restoring configuration, dependent Ethernet PHY/MAC assumptions must
follow the authoritative rate. CAN-FD conservative timing must use the same
native per-message padding as nominal timing. Explicit PHY/layout choices
remain fixed and incompatible inputs remain blockers.

The unchanged large prompt explicitly requests Ethernet 100 Mbit/s. Filling
its former 1-Gbit profile seed with the identical value did not constitute a
user change. The return case now genuinely edits the seed to the prompt's
100 Mbit/s and retains strict saved-value/provenance checks.

The restored SQL diagnostic shows ten native schedule failures before repair,
two after native configuration/layout repair, and zero after the existing
communication sizing path runs on the split graph (102 generated message
period edits, no invalid routes). This is diagnostic evidence, deliberately
reported as an ERROR by its fixture, not a passing regression. Wizard capacity
continuations now rerun that sizing path for already complete saved parameters.
174 targeted native/SQL/wizard tests pass; a separate strengthened saved-current-
graph continuation test passes and preserves user seed and both saved value
groups. Browser execution, complete gate, and production delivery remain pending.

The subsequent full browser case passed all nine parameter returns, then exceeded
the unchanged 240-second capacity progress watchdog. The complete-parameter
continuation still invoked default generation and spatial zoning. It now uses
the registered tool's explicit `sizing_only` mode: require complete saved
parameters and topology, then preview/apply the existing native sizing service
against the current graph. No defaults, routing or spatial generation is run.
The unchanged 20-minute case and all inner watchdogs remain required.

The preceding complete gate failed, with 21,687 backend passes and two failures;
it is not a delivery receipt. The canonical migration inventory omitted the two
catalog-response files. The captured routing stress fixture also relied on
undeclared starter padding to create more than 100 channels. The inventory now
includes the actual files. The fixture declares native CAN-FD DLC15/64-byte/CRC21
transport padding before generation, retains the original graph and all route,
signal and frame-preservation assertions, and requires nominal simulation
capacity without falsely certifying device hardware. A separate focused sizing
mock explicitly enables the native sizing policy. These repairs require their
own targeted, browser and complete gate results before deployment.

The padding hypothesis did not resolve the large fixture: its repeated run
still generated37 LIN-only channels. A pure ingress replay confirmed the saved
DLC15/64-byte/CRC21 values were retained. The captured native snapshot identifies
the actual consumer gap: CAN-FD hardware load fields are null without device
qualification, while `simulation_capacity` contains valid10/11.5/15-percent
average/peak/burst demand. Network distribution treated those null hardware
fields as zero. It now projects only validated finite native simulation demand
and per-segment frame duration into detached planning streams; an invalid stream
blocks the complete physical bus instead of validating its remaining subset.
Source capacity data, hardware qualification and functional acceptance stay
unchanged.48 planning regressions pass. The complete captured padded stress now
passes with its original >100-channel, all-route and signal/frame preservation
assertions; the combined targeted run reports34 passes.

The following browser failure was not slow native calculation alone. The real
trace shows the parent wizard repeatedly transferring stale full proposals
before and during its child's current validation. Two topology validationPOSTs
complete in28/29s; a third starts18s into the60s return window and is cancelled
at the deadline. Pure parameter review takes14s under profiling. Parent loading
now shares the existing status-first restoration client and compact polling:
OUTDATED validation returns the fresh body directly, and matching current
revisions retain their own full content.12 client tests and typecheck pass.
No return, progress, manual-write or outer test deadline was increased.

The final release-and-deploy pipeline is running. Its complete browser suite
contains the same eight targeted cases plus the remaining E2E coverage. Their
results may be extracted from that immutable complete gate as bound evidence,
avoiding an unnecessary second execution of already passing identical cases.
Only a complete PASS receipt and exact-image deployment/live proof close this
workload; historical targeted and failed browser runs never authorize delivery.

The completed `999af6c2d1bb` gate passed21702 backend tests,588 frontend tests
and95 of96 browser cases. All three large parameter-return cases passed and the
complete50/250/250 case completed all nine stages on the same run. Its final
strict conformance assertion failed withNOT_EVALUATED, not a timeout. Frozen
evidence has all766 routes observed,761PASS and five1000ms LIN routes with just
one receipt and unevaluated jitter. The unchanged native observation planner
requires1.071s, but an unrelated whole-form save had promoted the untouched
default1s to an explicit USER_PARAMETER. The duration intent boundary now keeps
trusted unchanged default origin while preserving explicitly edited durations,
including an identical1s value and legacy direct API requests. Profile defaults
are selected through the existing native registry; client provenance cannot
erase an explicit saved duration.72 isolated backend tests,6 API client tests
and typecheck pass. Detached replay of the exact frozen transport configuration
with the original default origin gives766PASS, no failed or unevaluated routes,
and two receipts for each previously incomplete route at1.071s. Routes, native
transport parameters, timing requirements and event budgets remain unchanged.
This detached replay is not complete release evidence.

The first two-case browser check passes the primary CAN-FD save/reload and
same-value explicit duration case. A new assertion in the separate mixed-project
native-rates case incorrectly expected global duration provenance after saving
the secondary Ethernet protocol. The fixture's CAN-FD primary has no saved
global duration; Ethernet correctly stores duration in its own scoped group.
The correction asserts unchanged global duration/provenance and scoped Ethernet
duration1, retaining all previous native persistence checks. Original failed
report and cleanup evidence are preserved inbefore-mixed-duration-test. This is
a correction of a newly added test expectation, not an application relaxation.
The application image is unchanged; the corrected browser tests are rerun on
that exact image before the complete immutable release gate.

Both corrected duration-intent UI cases pass on image66df226713c9/source d7d049e2b8d6.
The subsequent full gate860f9d4a7375 passes21713 backend tests (2SKIP,
56subtests) and589 frontend tests, then its large browser case exceeds the
unchanged1200000ms whole-case budget. This is a real timeout, unlike the earlier
999af6c2d1bb conformance failure. Read-only capture from the owned disposable
test database proves the engine now usesTECHNOLOGY_DEFAULT origin and a derived
1.071s window, with766 evaluated routes allPASS,1169 observed required signals,
no failed/unevaluated routes and no missing observations. The server's same-run
execution eventually completes all nine stages; that post-timeout state does
not turn the timed-out UI case intoPASS. Production remains unchanged.

The actual trace records543 summary workflow reads,27 parameter reviews and
eight agent continuations; several agent writes take63–146s. Request totals are
overlapping durations, not whole-case elapsed time. During diagnosis, additional
read-only live status probes were made against the test stack; subsequent timing
rounds must use only existing log/trace evidence so that observer overhead does
not affect the budget. Further measurement must distinguish native calculation,
SQL artifact checks, serialization and polling before choosing a repair. The
complete frozen test project (resource rows, workflow state and analyses) and
its project-local user-defined values are captured for isolated profiling after
this full round finishes. No application/test edits or enlarged budgets are
allowed during the current full round. Independent model-return case92 passes.


The completed860f9d4a7375 gate has21713 backend,589 frontend and95/96 browserPASS. The unchanged large case reached its1200000ms limit while polling the workflow. Its eventual stored server assessment has766/766PASS,1169observed required signals, no missing routes/networks and the derived1.071s observation window; this does not constitute a browserPASS. Frozen SQL profiling identifies repeated fullJSON reads and route-by-signal scans in source-artifact reconciliation. No release budgets or assertions were changed.

The source repair projects complete consumed native contracts and channel fields, preserving non-object types, explicitnull transport_unit and every authored current/outdated transport reference. The shared coverage uses one message-child index; registry key enumeration is hoisted within the same authoritative validation call. All152 isolated workflow/coverage regressions pass, including13 new strict negative/absence/reference cases. Three frozen after reads remain byte-identical to the original full workflow stateSHA d3adb4cb8f9fbbb92668c368c41549307c6eeae726ab7edfab2a82944474cc88. Median measured status read improves0.7359s to0.5323s (27.7percent); timings are diagnostic, not release assertions. No second resultcache/registry or new acceptance logic was introduced. The full release-and-deploy command is now running; production still has the prior image until completePASS and exact-image delivery. Progress during this timing-sensitive full round is inspected from existing logs only.


Final complete release bd97b35d951d isPASS:21726 backend tests (2skips,56subtests),589 frontend tests,96 browser cases (47.2minutes), small and large independentHTTP acceptance. The unchanged full50/250/250 browser case passes allnine stages and complete conformance in16.0minutes; independent model/routing/topology returns pass in4.6/7.1/8.8minutes. Exact production image sha256:d3e0832d2fb6e241da0f09112150203386edee5e3d937cbe8854e668e1a4a16e isDEPLOYED andready with source d982fac5e281cbd03df018259d611569ca3322d35b5fa0cf3697ded3bbc51b9a. Live human project20261007041943709-40764014 returns through the real button toStatusübersicht Schritt5von5; parameters areFreigegeben. Proposal aa7c0504-1cf4-4d09-b2e8-6ce28f8a2b49 is freshlyVALIDATED andstillnotapplied (canonical_count0); run1dfcae6a-a187-498f-b85b-c9cfb5245f92 and exact saved parameterSHA71e63bc6401a1cd75b726d7d9ecc97551ecac0187b751bb5a0b14f54f088fcb9 remainunchanged. All168 LIN device-proof findings areINFO with usable simulation parameters. Existing unconfirmedCAN-FD/Ethernet groups remain separate, and no human parameter save/approval/application was performed. Screenshots live-parameters.png/live-wizard.png and live-wizard-dom.txt record the actual product UI. The eight relevant and two duration cases were selected from the actual completePASS report, notrerun/invented; their exactreceipt/image/source bindings are retained. The independent Tool-Checker campaign remains REPAIR_1_ACTIVE and isnotclaimedPASS.
