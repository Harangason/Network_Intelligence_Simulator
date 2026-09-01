# Ontology And Taxonomy

The initial ontology is industry-neutral and intentionally small. It contains root engineering concepts, physical quantities, state concepts, commands, requests and diagnostics.

The first seed concepts are:

- `ENGINEERING_CONCEPT`
- `PHYSICAL_QUANTITY`
- `TEMPERATURE`
- `PRESSURE`
- `VOLTAGE`
- `CURRENT`
- `POSITION`
- `VELOCITY`
- `ROTATIONAL_SPEED`
- `STATUS`
- `OPERATING_STATE`
- `HEALTH_STATE`
- `SAFETY_STATE`
- `COMMUNICATION_STATE`
- `COMMAND`
- `REQUEST`
- `WARNING`
- `ERROR`
- `DIAGNOSTIC`

Aliases are normalized before lookup, so separators, casing and common German umlauts do not decide semantics. Domain-specific examples may map into this taxonomy, but they do not create special-case truth.
