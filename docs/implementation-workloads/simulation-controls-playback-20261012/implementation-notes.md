# Simulation controls and playback — 2026-10-12

The controls formerly occupying several panels above the graph are now grouped
behind a default-closed Steuerung button beside the view tabs. The existing
workspace tools, fields, scenario actions, scope and fault editor remain mounted;
closing the controls does not reset their state. Validation, scope, restore and
execution errors stay visible outside the folded controls. The separate outdated
banner is removed; canonical snapshot staleness is unchanged, and the stored-run
label marks a loaded outdated snapshot as Veraltet.

The timeline now has Wiedergabe/Pause and Stopp. Playback reuses the existing
playing state and playhead publication, including the shared simulation-relative
workspace cursor. Starting at the end replays from zero. Stopp pauses playback
and returns the cursor to zero. The backend job cancellation action remains in
the folded form as Lauf stoppen and is independent of historical playback.

The user explicitly changed the delivery rule for these UI changes: small final
checks, no new image or large release test, direct production. AGENTS.md records
this scoped exception. TypeScript checking and frontend production compilation
passed, followed by a focused production browser check of an existing job.
Initial verifier attempts assumed an immediately rendered snapshot label for a
job-only browser session and then waited for snapshot metadata; those attempts
failed. The final check verifies actual playback on the existing job and unchanged
canonical historical snapshot staleness separately through its project API.
It does not claim a complete workflow or campaign PASS.

Production frontend patch: f8ba25ca672c.
Frontend artifact SHA-256: 6807c6414d19e0cae82a731c1a315c29c6fa2973e4e839b20d67141ecc08d000.
The container and base image remain unchanged: sha256:afffad957644b4f77b3ba831f61a62d8139a6f7b07cd3779917b812a92c3a179.
The frontend manifest separately records the patch and its source hashes; the
engine indicator identifies the UI patch rather than claiming an image release.
Local and LAN readiness and frontend artifact identity were verified.

The original image-layer directory could not be renamed (Docker overlayfs
EXDEV). Production stayed unchanged on that failed attempt. The corrected path
copies the old compiled bundle and affected files to
`/app/.frontend-ui-rollback-f8ba25ca672c`, replaces only the compiled bundle and scoped
frontend files, and restarts the existing container. Original dependencies and
backend remain untouched. The artifact is also archived at
`F:\CodexOrdner\visualizations\2026\10\09\01a11f88-d6c9-7b63-bec3-26450a86e52c\frontend-ui-f8ba25ca672c.tar` with a verified archive SHA-256.
This is an explicit frontend overlay: it survives restart of this container.
A future container recreation from the unchanged image requires restoring this
artifact or a normal source-based release; the base image alone lacks the patch.

No backend/model/database test data or new simulation run was created. The small
browser check preserved existing job identities/statuses. EIP was not modified.
