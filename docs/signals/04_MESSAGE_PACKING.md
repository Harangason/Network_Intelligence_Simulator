# Message Packing

Message packing places encoded signals inside a frame or payload.

Common fields:

- `configuration.start_bit`
- `configuration.bit_length`
- `configuration.endianness`
- message `dlc`
- message cycle time

Packing checks must detect overlaps, unused padding, impossible DLC usage and inconsistent byte order.
