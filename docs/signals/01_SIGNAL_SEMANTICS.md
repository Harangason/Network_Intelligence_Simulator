# Signal Semantics

Supported semantic types are `NUMERIC`, `ENUM`, `BOOLEAN`, `STATE`, `BITFIELD`, `COUNTER`, `FLAG`, `RAW`, `STRING`, `BYTE_ARRAY`, `DERIVED`, `CUSTOM` and `UNKNOWN`.

Imported or generated signals should contain:

- `semantic.semantic_type`
- `semantic.meaning`
- `semantic.quantity`
- `semantic.unit`
- `semantic.system_context`

Legacy signals without explicit meaning are classified as `UNKNOWN`. They must not be silently treated as numeric only because `min_value`, `max_value` or `length_bits` exist.
