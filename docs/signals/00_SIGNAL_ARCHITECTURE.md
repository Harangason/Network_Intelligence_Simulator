# Signal Architecture

Signals are modelled in layers so names do not carry technical properties such as ECU, Sensor or Actuator.

1. Signal Semantics: meaning, type, quantity and functional context.
2. Value Domain: allowed, reserved, invalid and default values.
3. Encoding: bit length, signedness, scale, offset and byte order.
4. Message Packing: start bit, byte order, DLC and frame placement.
5. Protocol Binding: CAN, CAN_FD, LIN, Ethernet or other transport mapping.
6. Simulation: generated values and boundary cases.
7. Trace: evidence from import, AI generation or user approval.

Capacity and Data Science must use these layers before proposing bit optimisation.
