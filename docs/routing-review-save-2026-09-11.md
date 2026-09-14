# Routing wizard: explicit save after review

The reported early closing of “07 Prüfen” was reproduced in Chrome. A single click on the final “Weiter” changed the same DOM button from navigation to submit during the click; the browser then submitted the form. The baseline produced both a route PATCH and validation POST without a separate save action.

Navigation now retains its own button, which is disabled on the final step. Saving has a separate button and explicit handler that requires the review step and complete required fields. Implicit form submission does not save. A synchronous in-flight guard prevents duplicate requests. The saved route still undergoes validation through the existing save flow.

Verification: TypeScript and production build passed. `frontend/scripts/verify-routing-review-save.mjs` reproduced the baseline failure, then passed on the corrected local build: single/double navigation click, Enter in timing, direct review-tab selection and explicit double-click on save. Only the explicit save emitted one PATCH and one validation POST. Those two requests were intercepted in the test browser; the live project's routes remained unchanged. No browser errors; local health returned HTTP 200, `ok`.

Evidence: `backend/runtime/routing-review-save-baseline.log`, `routing-review-save-browser.json`, `routing-review-save.png`.
