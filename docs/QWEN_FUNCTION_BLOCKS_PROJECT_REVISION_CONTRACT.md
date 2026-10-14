# QWEN functions and project revisions

QWEN authors executable domain logic. NIS owns canonical project access, bounded
execution, validation, review, revision checks and persistence. No arbitrary
generated Python module is imported or executed. There is no second database,
TechnologyProfile, block registry or independent transport simulator.

## Existing owners and OOP boundaries

- `agent/tools/model.py`: `ProjectRepository` actively reads the current,
  project-scoped canonical DB; `ProjectContext` freezes its exact revision.
- `agent/tools/function_blocks.py`: local installed QWEN generates source,
  parameter schema and constraints from explicit requirements and canonical IDs.
  There is no Llama/cloud fallback for domain code. Incomplete/timed-out responses
  create no proposal. Expected-value cases are supplied independently of QWEN.
- `engineering/signals/signal_behavior_service.py`: existing `SignalBehavior`
  persistence; `FUNCTION_BLOCK` extends the existing registry/proposal contract.
- `simulation/signals/core/function_block.py`: OOP `FunctionBlock`, bounded AST
  interpreter `QwenFunctionBlock` and run-local `EcuRuntime` instances. Code,
  parameters and state never leak between ECUs or runs. Revisions cannot change
  during a run; first execution has dt=0, later dt is elapsed execution time.
- `simulation/transport_dependencies.py`: functions consume actually delivered
  input samples in the existing transport pass. Delays, drops, data age, faults,
  stale policy, source event IDs, output code hashes and state remain inspectable.
  Gateway forwarding does not execute the producer again.
- `infrastructure/storage/saved_storage.py`: `ProjectArtifactStore` extends the
  existing project save owner. DB-derived file projections share its transaction
  resource/rollback mechanism. The database remains model authority.

Class 3/4 does not specify a function. A proposal needs an existing output owned
by a canonical function on that hardware, explicit input bindings/units/age and
fallback policies, parameters, an invalid-input output policy, requirements,
independent expected-value cases and the current model revision. Missing data
remains open. Existing proposal validation, human review and guarded apply are
mandatory for future model changes. Approval of the NIS capability does not
automatically approve guessed behavior for every device in an existing project.

The interpreter only accepts finite numeric/boolean inputs, outputs and state,
simple arithmetic, comparisons, conditionals and bounded dictionary access. It
provides no database, filesystem, network, imports, loops, eval/exec or random
access to generated code. Structured perception/vision algorithms are outside
this scalar block contract; a range value does not prove an object or a track.

## Project-owned durable storage

Use the configured existing SAVED root. Do not move existing mounts or historical
files implicitly. Production's configured save root is an existing host mount.

```text
SAVED/<canonical-project-id>/
  manifest.json
  project.nis-project.json                  # existing explicit project save
  user_defined_values.json                  # existing project overrides
  revisions/<revision>/
    project.nis-project.json                # DB-derived owned project records
    manifest.json
  logic/blocks/<source-sha256>/
    source.py                               # QWEN source as inspectable data
    definitions/<definition-sha256>.json     # schema, provenance, independent cases
  runs/<run-id>/
    revision/inputs.json                    # frozen model/code/parameters/scenario/seed/build
    revision/status.json
    revision/result.json
    revision/manifest.json                  # complete artifact hashes and outcome
    values/events.jsonl                     # complete values/decisions, beyond UI page limits
    traces/...
    native/...                              # generated BLF/ASC/PCAP/PCAPNG/etc
  trace-imports/<session-id>/...             # existing original imported trace storage
```

Original NIS catalog defaults remain with their owners. File projections keep
their identity/hash references, not a new editable copy of default definitions.
Project overrides and effective run inputs retain types and provenance. Explicit
external output paths remain valid; generated files are also archived under the
owning project without removing their originals. Every newly generated native
artifact and complete value stream is indexed by checksum. Historical revisions
are immutable. Explicit project deletion retains the existing authorized
deletion behavior; revision persistence never recreates a deleted project.

## Verification and controlled improvement

Independent cases cover thresholds/equality, hysteresis direction, state reset,
timer deadlines, validity, missing/stale inputs and faults. QWEN's own assertions
do not prove correctness. Run comparison must identify model/code/parameter/input
and build revisions and use the same frozen input scenario/seed. A shared-code
improvement needs reviewed evidence, a regression test and the required NIS
release gate. Project results do not automatically train model weights or promote
project code into a shared library. Synthetic transport or simulation logic does
not establish real sensor detection, actuator physics or hardware acceptance.

SQL checks run only through the isolated runner. Changes to these agent/runtime
owners require a complete release PASS and exact tested-image production delivery.

## Shared Boolean standards and explicit composition

The existing `SignalBehaviorRegistry` owns `function_block_standards.json`. It
contains actual QWEN-authored source revisions; this is not another registry or
execution engine. `inspect_function_block_standards` exposes input contracts,
source identity and optional code. The original six scalar/stateful blocks remain
available with their explicit project parameters. AND, OR, XOR, NOT, NAND, NOR,
XNOR, BUFFER, IMPLIES, SELECT, JOIN and the grouped DECISION_ABCD example add pure Boolean
decisions. Standard reuse performs no model inference or source rewriting.

`generate_function_block_proposal` accepts either an explicit `standard_id` or a
custom `logic_expression`. A custom expression is parsed into a bounded graph as
data for QWEN; the existing bounded source interpreter alone executes its code.
UND/ODER/NICHT aliases are accepted. Use parentheses for grouping and function
notation for XOR/NAND/NOR/XNOR/IMPLIES/SELECT. Multi-input XOR is odd parity and
XNOR is even parity. SELECT(S, A, B) returns A when S is true and B otherwise.
The example is explicitly `(A OR B) AND C AND NOT D`, producing one Boolean
function output. Its canonical output identity and receiver are selected through
the existing project/model/review contract, not inferred from the label AC.

Boolean decision code may not read time or persistent state. Only JOIN may read
its explicitly declared model parameter N; other Boolean graphs have no parameters. It requires
actual Boolean values; numeric truthiness is forbidden. A physical measurement
needs an explicit comparison/threshold function before a Boolean decision.
For 1..8 inputs, independent expected-value cases must cover every Boolean vector;
missing cases, wrong types, changed source or stale model revision reject the
proposal. Actual delivered samples, validity/age and fault evidence still flow
through the existing transport/runtime. Project copies preserve the shared
standard's owner/catalog hash/source identity under the existing SAVED revisions;
the original shared catalog stays with its owner. Nothing assigns functions to
existing ECUs or approves proposals automatically.

The user defines JOIN as an exact-count Boolean decision. JOIN(N, A, B, ...) is
true iff exactly N operand values are true; nested Boolean operands are supported.
N is a required model parameter: finite, integer-valued, dimensionless, 0..operand
count. It is never a signal alias, hidden default, wire-layout or timestamp join.
With nested JOINs sharing N, its maximum is the smallest JOIN operand count.
The shared JOIN standard has four named Boolean inputs A/B/C/D; arbitrary 1..8
named inputs use an explicit expression and QWEN-authored source via the same path.
All independent Boolean vectors for every allowed N are required for verification;
missing counts/vectors, fractional N, Boolean N and out-of-range N are rejected.
Cases store explicit parameter_values for reproducible review; production uses
the project's frozen block_parameters.N. Invalid or stale inputs remain governed
by the existing transport policy; missing data is never silently counted as false.
Changing N requires a new reviewed model revision/run. The catalog has no default N.
