# Technology Bindings – As-built overview

The simulator separates `HardwareNode → HardwareInterface → link/network → TechnologyBinding → TransportUnit → PayloadElement`.
The registry is deliberately industry-neutral. Project model types only filter suitable devices and technology candidates; they do not change the generic core.

Executable behavior is restricted by `implementation_status`. `PLANNED` entries are documented and selectable for planning, but cannot be resolved to a generator.

Source of truth: `backend/communication/technologies/`. The HTTP catalog and Engineering Wizard consume this registry.
