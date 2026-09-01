# Frontend Boundaries

## Target

Frontend code may request, edit, display and visualize. It must not be the source of engineering calculations or generation rules.

## Current State

Several TypeScript files still contain deterministic engineering behavior, especially under `frontend/src/lib/agent` and capacity inspection helpers.

## Migration Path

Move one logic group at a time to Python and retain temporary TypeScript compatibility wrappers only while callers migrate.
