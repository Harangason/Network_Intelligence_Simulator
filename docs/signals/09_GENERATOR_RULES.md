# Generator Rules

AI generated signals must include semantic and encoding metadata from the start.

Generated signals should contain:

- semantic type and meaning
- value domain with allowed, reserved and invalid values
- encoding with bit length and transport constraints
- quality confidence and assumptions
- protocol binding evidence

If a generated signal is uncertain, the generator should prefer an explicit `UNKNOWN` or low-confidence state over hiding the uncertainty.
