# Python-First Core Architecture

## Rule

Python owns engineering logic. React and TypeScript own presentation, interaction and visualization.

The boundary is:

```text
Frontend request/display
-> API DTO
-> Python application service
-> Python core / technology / analysis service
```

## Layers

| Layer | Responsibility |
|---|---|
| Core | Industry-neutral contracts: hardware, interface, network, signal, message, route, value domain, encoding, protocol binding. |
| Technology modules | Protocol-specific behavior: parameter schema, load, timing, frame size, validation, encoding and generation. |
| Analysis services | Capacity, timing, queueing, jitter, validation, trace and root-cause calculations. |
| Agent core | Planning, orchestration, workload progress, repair and proposal flow. |
| API | Thin transport boundary, error mapping and DTO shaping. |
| Frontend | User input, navigation, editing controls and visualization only. |

## Current First Anchor

`backend/engineering/core/models.py` now defines small, persistence-free dataclasses:

- `EngineeringObject`
- `HardwareNode`
- `NetworkInterface`
- `Network`
- `ValueDomain`
- `Encoding`
- `ProtocolBinding`
- `Signal`
- `Message`
- `RouteHop`
- `Route`

These are not yet a full migration. They are the stable contract future Python services should consume before API DTOs are emitted.
