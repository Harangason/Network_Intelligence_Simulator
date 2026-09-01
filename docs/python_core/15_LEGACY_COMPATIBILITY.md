# Legacy Compatibility

## Rule

Compatibility layers are allowed only temporarily and must be marked as `LEGACY_COMPAT`.

## Current Needs

- TypeScript signal architecture wrappers until backend inspection endpoints cover every UI call.
- Existing API DTOs while Python core dataclasses are introduced.
- Existing technology aliases while a full technology registry contract is built.

## Removal Condition

Legacy code can be removed only after the Python implementation exists, tests pass, callers are migrated and active usage is gone.
