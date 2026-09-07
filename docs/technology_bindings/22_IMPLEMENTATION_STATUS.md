# Implementation status

The live catalog publishes counts and a status for every profile:

- `IMPLEMENTED`: binding, generator, validator, encoder/decoder, timing, and load components are registered.
- `PARTIAL`, `EXPERIMENTAL`, `LEGACY`: executable baseline exists, with documented conformance limitations.
- `PLANNED`: catalog/documentation only; generator resolution is rejected.
- `NOT_SUPPORTED`: intentionally unavailable.

The registry response is the authoritative machine-readable as-built status.
