# Signal Core

## Target

Signal semantics, value domains, encoding, reserved values, invalid values, bit requirement and optimization belong to Python.

## Current State

Python has `backend/engineering/signal_audit.py`. TypeScript still mirrors important logic in `frontend/src/lib/signal-architecture.ts` and `frontend/src/lib/capacity-network-inspection.ts`.

## Migration Path

1. Extract Python signal dataclasses from `backend/engineering/core/models.py` into specialized signal services only when behavior grows.
2. Move TypeScript bit requirement consumers to a backend endpoint.
3. Keep TypeScript signal DTOs as display-only API mirrors.
4. Remove TypeScript calculations after callers migrate.
