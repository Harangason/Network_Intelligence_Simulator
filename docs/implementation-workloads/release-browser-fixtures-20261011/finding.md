# Release browser verification repair

The complete gate delivery-dde7985139ee/cbeea5a4f97b found two verification defects.
Application source remains unchanged by this repair. The requested behavior remains
the structured Safety editor, canonical native formats and no initial JSON fallback.

1. `safety-assurance.spec.ts` uses exact `getByLabel('Norm')` for a wrapping label
   containing a select and all option texts. Its actual accessible snapshot exposes
   `combobox "Norm"`, just as the existing Function selector does. Use the semantic
   combobox role and exact accessible name for Norm and Anwendbarkeit. All save,
   persisted configuration, version, pending approval and absence-of-JSON assertions
   must remain. Owner: TOOL_CHECKER (browser selector).
2. The signal/sequence display fixture in `studio-export-controls.spec.ts` supplies
   an empty technology catalog and empty parameters, yet requires Start enabled.
   The product correctly keeps Start disabled until native formats resolve. Provide
   explicit Ethernet scope and the actual registered catalog from the isolated API.
   Hold its response initially to assert Start disabled and the loading indicator;
   then release it and retain the original Start-enabled and all display assertions.
   Real CAN, Ethernet and mixed native-format cases already pass in this failed run.
   Owner: TEST_DATA (incomplete registered-format fixture).

No timeout increase, assertion removal, product fallback or release bypass is allowed.
Counterprobes retain rejection before the catalog is available and enabled Start only
after canonical formats resolve. Safety must still persist unchanged explicit criteria
and remain unapproved. Retest the existing exact image through the canonical complete
release gate after verification inputs change; do not build a new application image.

Original failure artifacts are under
`backend/test-output/release-gates/delivery-dde7985139ee/cbeea5a4f97b/browser/`.
