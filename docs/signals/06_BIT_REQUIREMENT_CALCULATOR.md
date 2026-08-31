# Bit Requirement Calculator

The bit requirement calculator derives the minimum required bit length from semantics and value domain.

Rules:

- `BOOLEAN` and `FLAG`: 1 bit.
- `ENUM` and `STATE`: ceil(log2(number of allowed plus reserved values)).
- `COUNTER`: modulus or numeric range.
- `BITFIELD`: highest bit member plus one.
- `NUMERIC`: range and resolution.
- `RAW`, `STRING` and `BYTE_ARRAY`: explicit encoded length.
- `UNKNOWN`: no optimisation until semantics are clarified.

The result is advisory. It does not mutate the engineering model automatically.
