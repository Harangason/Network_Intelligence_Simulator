# Encoding

Encoding describes how a value domain is represented in bits.

Common fields:

- `configuration.bit_length`
- `configuration.raw_datatype`
- `configuration.signed`
- `configuration.factor`
- `configuration.offset`
- `configuration.endianness`
- `configuration.encoding_type`

Encoding is not the same as meaning. A status may be transported as `uint8`, but its semantics can still be `STATE` with a small enum domain.
