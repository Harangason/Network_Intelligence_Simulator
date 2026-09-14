# Routing wizard: clarify and select the required payload

The payload step now asks which information the selected consumer needs from the producer. A text field and information categories (operating state, health/quality, measurements, commands) filter existing canonical messages and signals. The review step's payload action opens these questions without selecting or saving a message automatically.

Each suggestion shows every modeled signal, its meaning, stored enum codes or range, bit length and start bit, plus the message size and cycle. Matching signals are highlighted; additional contents of the same frame remain visible. Messages covering only some selected categories are identified as partial suggestions. These are search hints from model metadata, not newly generated signals or proof that the consumer requires them.

Adoption is explicit. The chosen signals can subsequently be adjusted, and the selected payload remains visible when the search changes. A missing result explains that the information has not been found and links to the actual message-creation wizard in the same project, in a separate tab so the route draft remains available.

The data request is retained across wizard steps and included in `payload.data_requirements` when the route is saved. Reopening reads that field; editing through the manual route editor preserves it. Existing source/consumer scope checks still exclude local I/O intended for another recipient. Selecting fewer signals does not silently reduce the physical frame size or bus load: a smaller transmitted payload requires its own modeled message.

## Verification

- Nine unit tests passed (payload needs and interface search), including stored enum values, physical measurements named Status, empty results, legacy requirements and partial coverage across messages.
- TypeScript and the production build passed; the updated local container was started successfully.
- Pure backend route normalization preserved the requirements on create and update without connecting to a database.
- `frontend/scripts/verify-routing-payload-planner.mjs` passed against the running application: the cooling-control route exposes all five existing signals; “an, aus und Fehler” selects Status and Health explicitly; “Temperatur” shows missing content; the real message wizard opens in the same project; navigation retains the request; and the 800px layout remains usable.
- The browser test intercepts route writes. It verifies the save request and reopening from the simulated saved response; it does not claim a live database write. Live project routes remained unchanged.
- Gateway/interface and functional-scope regression checks passed, as did the explicit-save regression (single/double navigation click, Enter, direct review navigation, explicit save exactly once).

Local evidence: `backend/runtime/routing-payload-planner-browser.json`, `routing-payload-planner-desktop.png`, `routing-payload-planner-unit.log`, `routing-payload-planner-build.log`, `routing-functional-scope-browser.log`, and `routing-review-save-browser.log`.
