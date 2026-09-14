# Routing wizard: recipient lists and editable payload proposals

User decision: use three lists named **Empfohlen / Übrige / Ausgewählt**, rather than three lists by hardware type. Each list groups its contents into ECUs/Gateways, sensors, actuators and any other device types, with alphabetical ordering inside each group. Search filters the available lists but does not hide selected recipients. Checking or unchecking moves a recipient between the appropriate lists; it does not save a route.

Recommendations use explicit canonical consumer references (hardware, interface or unambiguous function allocation), released valid communication for the same source and payload, or an existing valid route proposal with a stored confidence strictly above 0.95. Declared or released partners have an evidence label, not an invented numerical probability. Missing, ambiguous, stale or rejected evidence stays outside the recommendation tier. Historical approval or confidence does not override a current local I/O recipient boundary.

“Payload vorschlagen” now creates an independent editable draft from existing sender messages and signal definitions that are eligible for the selected consumers. It initially chooses matching signals from the stated need, or offers existing state/health outputs as an explicitly provisional starting point. Receive-only traffic and messages without modeled signals are not generated as candidates. Missing information stays open and links to the message wizard in the same project.

The draft shows actual message size, cycle, frame ID, signal meanings, stored codes/ranges and bit placement. Users can change the data-need text, regenerate, add/remove messages and check/uncheck signals. Navigation preserves edits. Changing source/interface or recipients makes the draft ineligible for adoption until regenerated or restored to its original context. Discard preserves the previously chosen payload. Adoption replaces the local route payload; final save remains a separate explicit action in step 07. An unresolved draft blocks final save. No canonical signal encoding or message DLC is changed by selecting a subset of signals.

The viewport-sized shell and fixed navigation/footer remain in place. Payload suggestions use responsive cards. Recipient lists span the content width with endpoint/interface fields beneath, and stack on narrow viewports. Dense list scrolling is bounded; route details remain in the main scroll area.

## Verification

The Vercel React guidance was applied to component boundaries, derived state, indexed lookups, labels and independent checks. The verified story is routing UI → existing project model → derived recommendations/draft → explicit edited route payload → save/validation request.

- Eleven pure tests cover the strict confidence threshold, explicit partner evidence, ambiguous function ownership, stale/unrelated route evidence, local-recipient boundaries, signal-only route references, independent draft editing, exact existing encodings, empty results and receive-only messages.
- TypeScript and the production build passed.
- Browser checks cover all three lists, alphabetical grouping, search retaining selected recipients, selection transfers, generating a real draft from review, editing and discarding without changing the current payload, navigation retention, blocking stale/unadopted drafts, small-window access, explicit adoption and exactly one route update plus validation.
- The payload, explicit-save and viewport regression scripts provide additional coverage. The viewport suite checks all seven steps at seven sizes down to 640×384 and 390×844.
- Save requests are intercepted in browser tests; live project routes remain unchanged. The tests prove the request/response UI boundary using simulated saves, not a live database mutation. No backend schema or persistence service changed.

Evidence: `backend/runtime/routing-consumer-draft-unit.log`, `routing-consumer-draft-browser.json`, `routing-consumer-lists.png`, `routing-payload-draft-small.png`, `routing-consumer-draft-types.log`, `routing-consumer-draft-build.log`, `routing-wizard-sizing-browser.json`, `routing-payload-planner-browser.json`, and `routing-review-save-browser.json`.
