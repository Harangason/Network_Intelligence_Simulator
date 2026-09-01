# Canonical Core

## Purpose

The canonical core defines industry-neutral engineering concepts. It must not know about automotive, rail, aerospace, industrial automation or any specific bus naming convention.

## Implemented Anchor

`backend/engineering/core/models.py` contains persistence-free dataclasses:

| Model | Purpose |
|---|---|
| `EngineeringObject` | Common identity, name, description and metadata. |
| `HardwareNode` | Physical or logical participant. |
| `NetworkInterface` | Technology-facing connection point on hardware. |
| `Network` | Communication segment with a technology id. |
| `ValueDomain` | Semantic value constraints, enum, reserve and invalid values. |
| `Encoding` | Transport encoding shape: bit length, start bit, byte order, data type, factor and offset. |
| `ProtocolBinding` | Link from signal/message semantics to a protocol or network. |
| `Signal` | Semantic signal contract. |
| `Message` | Transport payload container. |
| `RouteHop` | One source, gateway or destination position. |
| `Route` | Source, destinations, messages, signals, timing and policy references. |

## Boundary Rules

- Core models do not import API, database, frontend, AI or simulator infrastructure.
- Core models contain only generic validation that protects impossible state.
- Technology-specific checks belong in technology modules.
- Domain-specific recommendations belong in domain profiles.
- Persistence adapters may map database rows into these models, but persistence is not part of the core.

## Next Step

Move signal semantic and bit requirement logic from the TypeScript mirror into a Python signal-core service and expose it through a backend inspection endpoint. Keep the TypeScript code as temporary `LEGACY_COMPAT` until all callers use the endpoint.
