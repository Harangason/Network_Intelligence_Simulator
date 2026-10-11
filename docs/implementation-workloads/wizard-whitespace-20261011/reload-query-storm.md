# Release regression: duplicate background retrievals during typing

Owner: PROJECT_PRODUCT. First failing layer: frontend semantic query scheduling.

Evidence: release receipt delivery-0365fbec85ea/8d4503be8753 is FAIL. The preserved Playwright error-context and trace demonstrate successful individual Space/Enter assertions and failure only on reload. The wizard shows its existing explicit workflow-service unavailable state.

Trace analysis: 33 generation-experience/retrieve POST requests used exactly the same payload {industry: custom, bus_types: [], candidate_controllers: []}. A subsequent workflow summary GET was aborted after 10008.464 ms; later summary GET requests completed in 32.282 and 30.852 ms. No backend HTTP error response was recorded. Keystrokes recreate plannedEquipment.chains; the effect depends on that array identity although its query only needs controller names, industry and bus types. Browser cancellation does not cancel already dispatched server work.

Required repair: retain the exact editable draft, schedule retrieval only when its semantic request scope changes, and debounce rapid legitimate scope changes. Cancel pending timers and stale requests on scope/project changes. Retain explicit restore errors, current timeout limits and all persistence/reload assertions. Do not turn a failed release into PASS.

Acceptance: the same Space/Enter/reload regression passes with real backend and bounded duplicate semantic retrievals. Full release gate must be rerun after this application source change. The stopped run's partial browser scope is not complete E2E coverage. Its owned stack was cleaned by the canonical gate after the isolated failing browser process tree was stopped.
