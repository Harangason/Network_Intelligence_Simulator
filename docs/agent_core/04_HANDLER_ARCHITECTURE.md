# Handler Architecture

## Base Handler Contract

`BaseWorkloadHandler` defines:

```text
plan, inspect_existing_objects, select_generator, execute
validate, repair, regenerate_missing, get_progress, is_complete
```

Handlers coordinate a complete domain workflow. They may inspect existing canonical objects, establish dependencies and persist generator results through an adapter. They do not decide completion and should not contain object-generation catalogues.

## Registered Handlers

The simulator registers `SignalGenerationWorkloadHandler` and structured handlers for the other workload types. Handler namespaces exist in `agent_core/handlers`; implementations that know signals, routing, networks, parameters, simulation or traces remain in engineering modules.

## Handler Lifecycle

1. `plan` resolves context and required child workloads.
2. `select_generator` uses `GeneratorRegistry` with workload type and package category.
3. `execute` requests only missing candidates and persists proposals.
4. `validate` invokes domain and shared validators.
5. `repair` applies safe strategies; uncertain changes become `NEEDS_REVIEW`.
6. Core progress and completion services recount persisted results.

## Handler vs Generator

The handler knows that a signal workload requires 10 thermal and 25 motion signals. The thermal generator receives only the missing thermal count plus structured context and returns candidates. This separation keeps orchestration generic and generators replaceable.
