# Results chart tools — 2026-10-12

Communication sizing removed only from Intelligence, preserved in Capacity.
Standalone historical Results banner removed; canonical staleness, snapshot list
status, source versions, preflight and stale-run handling are unchanged.

Expanded peak charts show all filtered networks, with a viewport-sized scroll area
and more useful label/plot proportions. Expanded route donut scales up and includes
saved runtime network counts by bus technology, route counts by network and by
sender/receiver pair. Multicast route involvement does not imply extra wire traffic.

Trend tools support up to six networks across different technologies, line/step/
point/bar representation, automatic or 0–100 percent scale, zoom, pan and reset.
The SVG adapts to available width while keeping readable typography. Each series
retains its original timestamps and window size. Extrema sampling plots real points,
not fabricated averages; all selected-window values remain in a paginated table.

Partner jitter uses saved aggregate route metrics, not invented time-series data.
The metric is absolute actual reception interval minus expected cycle in ms.
At least two received events and a positive expected cycle are required to assess it.
Explicit zero limits are valid. Missing limits are open, never silently passing.
The saved aggregates cover the entire run, independently of chart time zoom.

For the reviewed project, stored engineering overview capacity_verified and
timing_verified are false, with peak/reserve/E2E fields null. The capacity service
intentionally separates nominal assumptions in network.simulation_capacity
(CALCULATED_UNDER_ASSUMPTIONS, hardware_evidence=false) from verified hardware
capacity. That is why a numerical runtime peak previously appeared alongside
“Nicht nachgewiesen”. Results now shows complete frozen assumption values separately
from open hardware proof, with explicit source explanation. A historical forecast
never falls back to today's capacity snapshot. No simulation value replaces a proof.

Five focused data checks, TypeScript, production frontend compilation and actual
historical-snapshot browser checks passed. No backend/database test writes, new
simulation, new image, full campaign or complete-image gate was run. This is the
explicitly user-authorized direct frontend delivery scope, recorded in AGENTS.md.

The initial browser check found wrapping select labels included their option text;
explicit accessible names were added and verified. A second verifier failure was
the test using innerText on an SVG node; it was corrected to textContent, without
changing application behavior. The final focused check passed with no page errors.

Frontend patch 12cf76ed642e, artifact 6eb7bc0a14b4345253dee4b1fd321ff85f37aa628ab6731eb7feb462a2752769.
Base image unchanged: sha256:afffad957644b4f77b3ba831f61a62d8139a6f7b07cd3779917b812a92c3a179.
Rollback: /app/.frontend-ui-rollback-12cf76ed642e. Archive: F:\CodexOrdner\visualizations\2026\10\09\01a11f88-d6c9-7b63-bec3-26450a86e52c\frontend-ui-12cf76ed642e.tar.
This frontend overlay survives restart of the existing container; recreation from
the unchanged base image requires restoring the archived artifact or releasing the
canonical updated source. The base image PASS receipt does not cover this patch.
