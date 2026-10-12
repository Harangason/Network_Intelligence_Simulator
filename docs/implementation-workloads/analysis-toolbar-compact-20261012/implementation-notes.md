# Compact analysis controls and simulation presentation

The analysis workspace toolbar keeps its existing window actions and shared
cursor visible, with explanation, profiles and window lists in closed native
details. Toolbar spacing and buttons are reduced without changing workspace
state, context publication or coupling behavior.

Follow-up browser feedback exposed a styling mismatch: signal names became
selection buttons, while the original 11px name rule still targeted `strong`.
The inherited button font was larger. The name button now receives the original
11px font size in both layouts. Compact headers constrain their inner grid item
and truncate overflowing labels inside the name column; the 42px rows still fit
15 signal tracks in the 630px viewport. Selection behavior is preserved.

The fault editor uses closed native details by default. Its summary keeps the
active fault count visible. Expanding it reveals the existing controls, German
explanations, proposals action and removable fault chips; fault configuration and
engine semantics are unchanged.

The user explicitly granted future audited cleanup of unused, fully archived
failed release candidates without another question. This is recorded in
AGENTS.md and the authorization evidence. The exact b3017a762dc0 image was
removed after complete archive/hash/receipt and all-container usage verification.
Production and rollback images were protected. No bulk or forced image pruning.

The first storage-blocked receipt contained no executed checks. A subsequent
partial run was explicitly interrupted before image build to include the new
browser feedback; its disposable database was removed. Neither receipt proves
release acceptance. The combined source completed the canonical release-and-deploy
command with a full PASS: storage checks, TypeScript, frontend tests, 21,796
isolated backend tests (two skipped, 56 subtests passed), production build, all
116 browser cases and independent small/large HTTP acceptance.

The exact tested image `sha256:89885e8cbdb16eb96e09e00dfea97936d604f3f31abe83a3ce65ce464720a382`
is deployed. Local and LAN/VPN readiness and source identity match the receipt
at `backend/test-output/release-gates/delivery-3731ea4649a5/baff4e76f405/receipt.json`.
Actual production presentation verified: 109px closed desktop toolbar, all four
window actions and cursor visible, profiles expandable, fault editor closed by
default and expandable, 60 rendered signal-name buttons at the original 11px
size within their header bounds. At a 390px mobile viewport the controls wrap
without document overflow. The existing historical simulation job list is unchanged.
The manual verifier's initially ambiguous nested-summary locator was corrected
to the direct editor summary; no application source, release input or assertion
was weakened. Completion guard reports COMPLETED with no issues. This is a
completed implementation/release, not a full tool-checker campaign PASS.
