# Agent Core Integration

## Target

Agents orchestrate Python services. They do not calculate bus load, bit requirements, routing, timing or validation directly.

## Current State

`backend/agent_core` already contains workload, registry, generator, handler, validation, repair and persistence modules. The frontend agent still owns deterministic wizard generation and parser logic.

## Migration Path

Turn frontend agent functions into thin API calls. Keep deterministic generation in Python workload handlers and return proposal objects for review.
