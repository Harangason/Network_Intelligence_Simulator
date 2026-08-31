# Bit Optimizer

The optimizer compares configured bit length with the required bit length.

Statuses:

- `OK`: encoding fits the value domain.
- `OPEN`: required semantic or value domain data is missing.
- `OVERSIZED`: configured length is larger than needed.
- `TOO_NARROW`: configured length cannot represent the value domain.

Optimisation proposals must include a reason, confidence and evidence so the user can understand the warning origin.
