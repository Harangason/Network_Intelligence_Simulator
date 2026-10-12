# Simulation command fields

The previous desktop layout forced duration, speed and seed into 72px columns alongside a 390px action group. The speed caption wrapped while fields looked disproportionately narrow.

The existing command bar now uses five field columns. Its three numeric columns have identical fractions and a 140px minimum. Scenario and trace-format columns retain more space. The existing run actions span their own row, with a 12px field gap. Existing three-column and mobile single-column layouts remain; controls, labels, values, limits and callbacks are unchanged. Only CSS was edited.

TypeScript validation passed. No additional design test suite was added. The mandatory complete canonical release-and-deploy passed all eight checks and deployed the exact tested image `networkis:candidate-44fdae5dc2e1`, immutable ID `sha256:afffad957644b4f77b3ba831f61a62d8139a6f7b07cd3779917b812a92c3a179`, source `b3a5de5ff4cf97560eaf749f6e03c92dc81c67aa71002fcc8200d08184b6ed04`. Receipt: `backend/test-output/release-gates/delivery-3a8411e928fe/44fdae5dc2e1/receipt.json`.

The backend result was 21,796 passed, 2 skipped, 56 subtests passed and one existing warning. All 116 browser cases passed. The main small and large wizard cases exercise the actual full workflow; the three parameter-return cases cover their stated review stages only. Both HTTP cases passed their full-scope assessment checks with the existing virtual-profile fixtures. This is the release scope, not a Tool Checker campaign PASS.

Actual production identity, build source and readiness passed on local and LAN/VPN endpoints. Actual field presentation was checked at 1506, 1319, 954 and 390 pixels: equal numeric field widths and aligned captions on desktop, readable fields and no document overflow at all checked widths. Values remain 2, 1 and 42; run controls remain visible; the default collapsed fault editor is preserved. The existing historical simulation job is unchanged, with no simulation start or engineering-model edit.

The first presentation capture was taken before project formats resolved. Its evidence and images are retained with `initial-loading` filenames. The verifier now waits for the existing trace-format button to become enabled, and the final proof and images show the fully loaded form. No application or release input was changed for this capture correction.

One unused FAIL-only candidate, `networkis:candidate-999af6c2d1bb`, was archived with all 23 verified OCI components and archive/receipt hashes, checked against all container references and protected production/rollback images, then removed with `docker image rm --no-prune` under the standing authorization recorded in AGENTS.md. See its storage review. No force or bulk pruning was used.
