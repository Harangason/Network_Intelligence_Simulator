# Wizard verification and release

The product stack on ports 13500/15050 is never a test target. Run SQL tests with
`backend/.venv/Scripts/python.exe scripts/run-isolated-tests.py -- backend/tests -q`
(use the corresponding virtual-environment Python on Linux). The launcher owns a
random PostgreSQL container, database and loopback port and removes that container
after pytest, including on failure. Test collection rejects product DSNs before
test imports. Each test also receives an independent project context and runtime.

## Production candidate

Install frontend dependencies with `npm ci --prefix frontend`, install Chromium
with `npx playwright install --with-deps chromium` from `frontend`, then run:

```text
python scripts/run-release-gate.py
```

The gate runs TypeScript, frontend tests and the full isolated backend suite. It
builds a production image once, records its immutable image ID and source
manifest, and starts that image with a disposable database and runtime. It runs:

- A new small request entered into the real six-page browser wizard, with real
  proposal approval, nine workflow stages, reload and application restart.
- The captured 50-controller / 250-sensor / 250-actuator request, submitted through
  the normal START API and continued through the real wizard review UI. Its exact
  specification and original project/run provenance live in `frontend/e2e/fixtures`.
  A semantic manifest compares all 1404 original signal definitions and encodings.
  A real running simulation is killed through an isolated application restart;
  the same persisted job must resume and complete with full scope evidence.
- AMEND transport failures, an accepted operation whose response is lost, and
  a competing client's real revision conflict. Input survives rejection and the
  retry uses the correct operation/revision identity. These fault tests never
  fabricate a successful write response.
- An amendment after real model approval adds an explicitly owned sensor through
  a new review and apply, preserves the existing network identities and completes
  the remaining workflow with actual ALL-scope simulation evidence.
- Independent HTTP acceptance for small and large requests, including physical
  topology/scene identity, real persisted simulation jobs, trace events and
  complete ALL-scope route/network/signal evidence.

Browser and HTTP acceptance insert no generated model rows directly, and no
successful write response is mocked.
Warnings are not automatically functional success: simulation acceptance requires
PASS conformance, zero failed routes and no missing scope evidence. Failure
preserves logs, Playwright trace/screenshot/video and a FAIL receipt. A source
change during the run invalidates release. The source identity is captured before
unit tests and must match both the immutable image and the final working tree.
CI runs the same command.

Local acceptance and CI use the Chromium revision pinned by Playwright. Browser
profiles are created inside the gate's disposable output directory; a system
Chrome override is ignored by the release gate. This keeps browser behavior and
failure-artifact cleanup reproducible across diagnostic and acceptance runs.
The image build also compares every installed Python package with the exact
runtime lock; adding an unpinned transitive dependency fails the build.

Browser continuation permits 240 seconds without a new contiguous completed
workflow stage for the same project, run and request revision. Advancing that
completion frontier starts the next section; a heartbeat, retry, restart, label
change or repeated completion cannot extend it. A distinct successful manual
approval starts a new continuation section, with its separate 180-second write
limit. The whole browser case remains limited to 20 minutes. Clock regressions
verify these boundaries. A workflow HTTP 413 or the underlying engineering API
error page fails acceptance even when the wizard overlay remains functional.

## Coverage levels

These are test definitions, not a claim that a particular candidate has passed.
The candidate's receipt and reports supply execution evidence.

| Failure or contract | Verification level |
| --- | --- |
| Real new small request, all nine stages, finish | Browser, real backend/MCP/PostgreSQL |
| Exact confirmed large specification and all original signal encodings | API start, browser review/apply, canonical semantic manifest |
| Reload after model commit, restart after routing commit | Browser with persistent isolated runtime |
| Crash during a running simulation, same job identity and full traces | Browser plus real isolated container kill/restart |
| Generation worker restart/lease recovery | Service/SQL regression with old process identity; not a real browser-time kill |
| Approval/apply failure and lost response | SQL transaction rollback and client reconciliation regressions; not a kill inside a commit |
| Duplicate START/CONTINUE and repeated apply | Durable command/SQL idempotency tests and HTTP acceptance |
| Project isolation and stale responses | API/SQL authority and frontend client tests; no full browser project-switch scenario |
| Amendment after apply, existing identities retained | Browser with real canonical delta and continued simulation |
| HMI output/local I/O ownership, original encoding and complete scope | Domain/service tests plus large semantic golden and browser/HTTP ALL evidence |

The gate deliberately does not describe service-level fault injection as browser
E2E. Tests for exact process-kill timing during generation and apply remain a
separate coverage limitation from the real simulation-crash scenario.

The gate emits `backend/test-output/release-gates/<id>/receipt.json`. Only PASS
receipts containing every required check can be deployed:

```text
python scripts/deploy-verified-release.py <receipt.json>
```

On Windows, `start-networkis.ps1 -ReleaseReceipt <receipt.json>` preserves the
configured GPU/AI/runtime settings while deploying the verified image. A plain
`start-networkis.ps1` restarts the currently installed immutable image; it does
not rebuild edited source. Initial installation needs a verified receipt.

## Isolated development

`python scripts/run-release-gate.py --prepare` retains a disposable stack for
interactive diagnosis and returns its isolated URL in a PREPARED receipt.
`--development-base <existing-image>` can reuse installed dependencies only with
`--prepare`; the image is labeled as development and cannot pass a release gate.
Production images must be built using the Dockerfile and locked dependency files.
Never pass a development receipt to deployment and never point browser/HTTP tests
at the product URL. To inspect a failed gate's stack, use `--keep`; remove only
the exact container/network names recorded in that receipt afterward.

The workflow file is a repository check. Hosting-side required-check/branch
protection must also require `Wizard release gate / full-stack` before merging;
the repository cannot configure that remote policy by itself.
