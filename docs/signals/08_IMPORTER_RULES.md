# Importer Rules

Importers must preserve semantic evidence instead of flattening all signals into numeric fields.

Required behaviour:

- DBC `VAL_` creates enum/state value domains.
- ARXML and AXML value tables should map to value domains when available.
- CSV, XLSX, JSON and YAML should read explicit semantic columns when present.
- Missing semantics must become `UNKNOWN` and visible in audit results.
- Source format and mapping confidence are stored in `quality` and `protocol_bindings`.
