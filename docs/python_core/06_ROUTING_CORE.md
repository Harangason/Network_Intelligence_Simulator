# Routing Core

## Target

Routes, hops, policies, gateways, candidate ranking, validation and route-path explanation belong to Python.

## Current State

Python routing generation and validation already exist under `backend/engineering/routing`. The frontend still owns matrix presentation logic and semantic helper scoring.

## Migration Path

1. Keep `backend/engineering/routing/models.py` as the current validation facade.
2. Introduce route-core mappers to `backend/engineering/core.Route`.
3. Move matrix data shaping into a backend route-matrix endpoint.
4. Let the frontend render matrix DTOs only.
