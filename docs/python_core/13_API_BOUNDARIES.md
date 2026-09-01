# API Boundaries

## Target

API modules should map request, response and errors only. They should not contain engineering calculation logic.

## Current State

`backend/engineering/api.py` is broad and coordinates many domains. It is functional but too large for long-term maintenance.

## Migration Path

Split routes by area after core services are stable: schema, imports, workflow, routing, capacity, workloads, structure and generic resources.
