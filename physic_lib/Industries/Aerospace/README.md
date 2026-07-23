# Aerospace

Domain structure for aerospace, avionics, satellite, UAV, flight-control, and
payload communication projects.

Automotive assumptions must not be required here. Aerospace concepts are mapped
to the simulator's neutral model:

- flight controller -> participant/node
- sensor unit -> participant/node
- actuator unit -> participant/node
- telemetry -> provided service or signal stream
- command -> consumed service or request route
- redundant bus -> hardware bus with fallback route metadata
- safe mode/degraded mode -> health and fault model

Expected folders:

- `Requests/`
- `HardwareProfiles/`
- `SignalProfiles/`
- `ServiceProfiles/`
- `MissionProfiles/`
- `Learning/`

