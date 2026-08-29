# Generator Architecture

## Generator Contract

All generators implement `BaseGenerator.generate` and return `GeneratorResult`:

```json
{
  "status": "SUCCESS",
  "requested": 10,
  "generated": 10,
  "valid": 9,
  "invalid": 1,
  "remaining": 1,
  "objects": [],
  "findings": []
}
```

Counts cannot be negative and `valid + invalid` cannot exceed `generated`. `SUCCESS` means the generator call succeeded; it never means the workload is complete.

## Signal Generators

The simulator registers `TemperatureSignalGenerator` for category `thermal` and `MotionSignalGenerator` for `motion`. They create candidate definitions from engineering context. Reuse of existing approved objects is explicit. The catalogues remain outside the generic Core.

## Other Generator Areas

Message, interface, routing, network, parameter, scenario and fault generators use the same base contract. Their namespaces are extension points; concrete implementations belong to the owning domain module.

## Generator Registry

`GeneratorRegistry` keys entries by `(WORKLOAD_TYPE, category)`. A category-specific generator wins; `*` is the fallback. Registrations reject accidental replacement unless `replace=True` is explicit. A new generator can be added without changing planner, dispatcher, execution loop or completion logic.
