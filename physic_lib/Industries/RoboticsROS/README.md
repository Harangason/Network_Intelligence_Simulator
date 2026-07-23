# RoboticsROS

Domain structure for robotics projects, ROS architectures, and ROS2/DDS based
systems.

Automotive assumptions must not be required here. ROS concepts are mapped to
the simulator's neutral model:

- ROS node -> participant/node
- topic -> service or signal stream
- publisher -> provided service
- subscriber -> consumed service
- service/action -> request/response route
- QoS/deadline/rate -> timing and reliability metadata
- DDS domain/namespace -> routing metadata

Expected folders:

- `Requests/`
- `HardwareProfiles/`
- `SignalProfiles/`
- `ServiceProfiles/`
- `RosGraphs/`
- `Learning/`

