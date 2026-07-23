# IndustrialAutomation

Domain structure for manufacturing cells, PLC systems, fieldbus networks,
robot cells, drives, IO modules, and safety controllers.

Automotive assumptions must not be required here. Industrial concepts are
mapped to the simulator's neutral model:

- PLC -> participant/node
- IO module -> participant/node
- drive -> actuator node
- fieldbus -> hardware bus
- process value -> signal stream
- safety state -> health/status service

Expected folders:

- `Requests/`
- `HardwareProfiles/`
- `SignalProfiles/`
- `ServiceProfiles/`
- `ProcessProfiles/`
- `Learning/`

