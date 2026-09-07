# Core model

The generic core defines `HardwareNode`, `HardwareInterface`, `FunctionalInterface`, `TechnologyBinding`, `TransportUnit`, and `PayloadElement` as separate immutable Python contracts.

Devices such as PLC, ECU, Gateway, Sensor, Actuator, and RobotController are `HardwareNode.device_type` values. They are never registered as buses or protocols.
