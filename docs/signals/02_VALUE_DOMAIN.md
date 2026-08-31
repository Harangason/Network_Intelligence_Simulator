# Value Domain

The value domain defines which values are valid independently of the transport format.

Common fields:

- `data.minimum`
- `data.maximum`
- `data.resolution`
- `data.allowed_values`
- `data.enum_values`
- `data.reserved_values`
- `data.invalid_values`
- `data.default_value`

Enums and states must preserve imported value tables, for example DBC `VAL_` entries or ARXML compu methods.
