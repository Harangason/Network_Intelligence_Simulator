# Authorized thirteen-point implementation

The user explicitly approved all thirteen deferred comments and production delivery.
No separate design/UI test suite was run. Existing mandatory release checks remain required.

1. Native simulation-scope details defaults closed; invalid scope warning stays visible.
2. Runtime analysis is below the summary columns, using the full workbench width. Networks filter before the existing pagination helper, at 50 rows per page; filter changes reset pagination.
3. Four chart cards use equal 520px heights and two equal columns. Each can expand inline to full page width and viewport height; the same button restores all cards. Hidden cards retain their state.
4. Snapshot sidebar has text/status filters and six rows per page. It ends before the full-width charts and tables.
5. The calculated simulation-load list is in the new Buslast tab between Übersicht and Netze, reusing existing 50-item capacity pagination.
6. Missing input/device/implementation/timing evidence is explained separately from nominal demand calculation, which does not need a real ECU.
7. Redundant Technologie/Parameter navigation is removed; technology and parameter sections remain addressable.
8. Common parameter inputs retain three desktop columns, with controls aligned at the bottom of equal-height field wrappers; narrower screens remain responsive.
9. Peak and reserve aggregate recorded verified or simulation-assumption metrics, never fabricated zero/reserve values. Incomplete values remain unknown; hardware and functional timing acceptance are unchanged.
10. Existing optimize endpoint calculates proposals with applied=false; the button now says Optimierungsvorschläge berechnen and explains explicit adoption.
11. Existing scenario endpoint recalculates only burst_factor with persist=false. The UI explains the unpersisted comparison and existing explicit Draft application.
12. Shared sequence viewport accommodates fifteen original 68px event rows plus header and scrollbar, preserving 200-item pagination.
13. Deterministic read-only search supports German/English boolean operators, NOT > AND > OR, quoted phrases and parentheses. Plain literal search is preserved. Invalid syntax reports an error; no dynamic evaluation. Actual-endpoint participant filtering still intersects search results for simulated and observed data.

Functional verification: 30 existing and new sequence/capacity unit tests passed, including provenance separation, incomplete/nonfinite metrics, immutable model, expression precedence, invalid syntax and participant-filter conjunction. TypeScript check exited 0. No new dependencies, APIs, model writes or EIP changes.
React review: derived search is memoized; no extra fetching or render-driven state updates; native keyboard controls, visible syntax feedback and aria-expanded/invalid states; hidden charts remain mounted. User selection and authoritative transaction/timing evidence are preserved.

Production delivery is completed with the full PASS receipt `backend/test-output/release-gates/delivery-e846375a3120/e474119485bd/receipt.json`: 611 frontend tests, 21,794 backend tests plus 56 subtests (two skipped), all 110 browser cases, and both complete-scope HTTP checks passed. The canonical release-and-deploy command deployed exactly `sha256:04d9a791b807799cbec822820db86f00ccd1554910f44cc1b01f3de5e59749c5`. Local and LAN/VPN readiness and build identity match. Real-production search narrowed 10,000 historical events to 135 matching the boolean expression, rejected incomplete syntax, and restored all 10,000 at the same paused time. Real network pagination displayed 50 and 46 rows for the 96 networks. The short post-deploy check initially sampled the autoplaying trace before playback finished; comparing at its final paused time preserved the original restoration expectation. No additional design test suite was run.

The first complete attempt after an interrupted gate finished with 109 browser cases passed and one `readProject` GET transport reset in the large routing-review case. The genuine trace records Node Socket.socketOnEnd before an HTTP response (4.791 ms); the same isolated endpoint subsequently returned the correct project on three consecutive reads. The verification helper now uses the pinned Playwright `maxRetries: 2` only on GET, within the existing 60s deadline. A real loopback TCP counterprobe confirms recovery of one reset, rejection of persistent resets, unchanged HTTP 500 and malformed JSON failures, and no retries on writes. `transport-read-repair/owned-changes.diff` and `assertion-preservation.json` prove all assertions and other test code remain unchanged. The failed receipt remains FAIL; a new complete exact-image gate is mandatory. No production application source changed for this verification repair.
