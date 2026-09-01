# Test Strategy

## Baseline

Current regression coverage includes startup, scope rules, job service, signal architecture, equipment clustering and core model tests.

## Required Additions

| Area | Required Tests |
|---|---|
| Signal core | Semantic classification, value domains, required bits, invalid/reserved values, packing constraints. |
| Message core | DLC, occupancy, overlap, packing and payload export. |
| Technology modules | Parameter validation, frame estimate, load, timing and protocol-specific edge cases. |
| Routing core | Candidate ranking, gateway paths, system/function matrix DTOs and validation. |
| Analysis core | Capacity totals, warning origins, queueing, jitter and latency. |
| Agent integration | Tool calls use Python services and never calculate deterministically in the prompt layer. |
| Frontend boundary | UI renders API findings and does not duplicate calculations. |
