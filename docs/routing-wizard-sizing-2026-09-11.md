# Routing wizard: viewport-sized dialog

The wizard no longer stops growing at 820px height. Its shared shell uses the available dynamic viewport height with a small responsive margin and a maximum width of 1440px. All seven steps use the same shell dimensions. Content is not scaled down to fit a longer step.

Header, step navigation and footer remain outside a shared scrolling body. The planned gateway path, errors and editable step contents scroll together, so a long preview or review cannot consume all the space above the inputs. The gateway path still precedes the editable fields. Endpoint details use the shared body; the long consumer selection list retains its own bounded scroll area. Inputs use 14px text and supporting field labels use 12px text. Technical source identifiers wrap, and the governance summary uses fewer columns.

Narrow or short viewports use horizontal step navigation; changing steps brings the active step into view and resets the body to its beginning. Footer buttons keep their intrinsic widths, avoiding the global mobile full-width button rule. Background page scrolling is locked while the wizard is open and restored on close. Saving remains an explicit action in the review step.

## Verification

- TypeScript, production build and whitespace checks passed. The final build is running locally.
- `frontend/scripts/verify-routing-wizard-sizing.mjs` checked all seven steps at 1688×1272, 1366×768, 1024×600, 800×600, 640×480, 640×384 and 390×844. Dialog geometry and footer position stay stable; the dialog fits the viewport, editable content does not overflow horizontally, the active step and footer controls remain reachable, and scrolling at the boundary leaves the background in place. The production check uses the deployed stylesheet without style injection.
- Payload selection, navigation and simulated save/reopen passed with the shared scroll area. The fixture uses the route's selected message when multiple messages have the same display name.
- Gateway/interface selection and functional recipient scope passed. The path-order assertion now checks that the path precedes the editable fields rather than the fixed step navigation.
- Explicit-save regression passed: navigating to review, double-clicking Next and Enter do not save; explicit save produces one update and one validation request.
- Route saves were intercepted in save tests. Geometry tests made no route writes. Live project routes and topology remained unchanged.

Evidence: `backend/runtime/routing-wizard-sizing-browser.json`, `routing-wizard-sizing-1366x768.png`, `routing-wizard-sizing-640x480.png`, `routing-wizard-sizing-build.log`, `routing-payload-planner-browser.json`, `routing-functional-scope-browser.json`, and `routing-review-save-browser.json`.
