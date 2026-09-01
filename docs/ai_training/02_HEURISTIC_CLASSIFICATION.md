# Heuristic Classification

The active heuristic classifier recognizes obvious structure from names, descriptions, units, datatype and discrete value domains.

Current examples:

- temperature units and aliases map to `TEMPERATURE`
- `rpm` and `1/min` map to `ROTATIONAL_SPEED`
- pressure units such as `bar` map to `PRESSURE`
- status/state/mode terms with enum-like values map to `OPERATING_STATE`

Heuristics are evidence, not final truth. The confidence aggregator still produces a proposal.
