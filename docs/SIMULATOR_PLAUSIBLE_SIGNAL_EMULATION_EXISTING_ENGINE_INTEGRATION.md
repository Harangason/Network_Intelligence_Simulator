# Arbeitsauftrag für Codex
## Bestehende Simulation Engine + plausible Signal-Emulation konsolidieren

## 1. Ziel

Erweitere die **bereits vorhandene Python-first Simulation Engine** des Network Intelligence Simulator um eine fachlich plausible, typabhängige Signal-Emulation.

Wichtig:

```text
KEINE zweite Simulation Engine bauen.
KEINE Parallel-Logik für Signalwerte aufbauen.
Bestehende funktionierende Logik zuerst inventarisieren und wiederverwenden.
```

Die vorhandene Runtime bleibt maßgeblich:

```text
Frontend
→ backend/engineering/simulation.py
→ backend/simulator/communication_simulator.py
→ backend/simulator/universal_trace.py
→ backend/simulator/model_based_simulation.py
→ Trace / Signals / Busload / Events
```

`ModelBasedSimulationEngine` berechnet bereits Signalwerte, Golden Values, Fault-Effekte, Payload-Encoding und Model Trace. Diese Verantwortung soll fachlich erweitert und modularisiert werden.

---

## 2. Vor Umbau zwingend inventarisieren

Prüfe zuerst:

```text
bestehende Signalwertgeneratoren
bestehende Golden-Value-Logik
bestehende Fault-Logik
bestehende Randomisierung
bestehende State-/Status-Logik
bestehende Encoding-Logik
bestehende Function-Behavior-Logik
bestehende Constraints
bestehende Quality-Logik
bestehende Trace-/Export-Verarbeitung
```

Für jede Komponente:

```text
KEEP
REUSE
ADAPT
SPLIT
REFACTOR
REPLACE
DEPRECATE
```

Keine unnötige Neuentwicklung.

---

## 3. Bestehende Zuständigkeiten beibehalten

### `backend/engineering/simulation.py`

```text
Engineering Model laden
Routing laden
Workflow-Topologie laden
Simulation Scope bestimmen
Scenario / Snapshot erzeugen
```

### `backend/simulator/communication_simulator.py`

```text
Runtime Entry
Konfiguration validieren
Simulation starten
Artefakte schreiben
```

### `backend/simulator/universal_trace.py`

```text
Zeitachse / Events
Cycle Times
Routing
Networks
Fault Events
```

### `backend/simulator/model_based_simulation.py`

```text
Signalwerte
Golden Values
Fault Effects
Encoding
Model Trace
```

### `backend/simulator/nemotron.py`

Nur:

```text
AI-Vorschläge
Konfigurationshilfe
Recovery
```

Nicht:

```text
deterministische Emulationsquelle
```

---

## 4. Zielarchitektur innerhalb der bestehenden Engine

`ModelBasedSimulationEngine` intern modularisieren:

```text
ModelBasedSimulationEngine
├── SignalBehaviorEngine
├── SignalStateMachineEngine
├── FunctionBehaviorEngine
├── DerivedSignalEngine
├── SignalConstraintEngine
├── SignalNoiseEngine
├── SignalQualityEngine
├── FaultInjectionEngine
├── SignalEncodingService
└── SignalValidationService
```

Keine neue parallele Runtime.

---

## 5. Zielpipeline

```text
Engineering Signal Definition
↓
Semantic Resolution
↓
Behavior Model Resolution
↓
System / Function Context
↓
SignalBehaviorEngine
↓
Golden Physical Value
↓
Derived Dependencies
↓
Physical Constraints
↓
Noise / Sensor Effects
↓
Fault Injection
↓
Quality Evaluation
↓
Resolution / Quantization
↓
Signal Encoding
↓
Message Packing
↓
Network Event
↓
Universal Trace
```

Verbindlich:

```text
Emulation
≠ Encoding
≠ Message Packing
```

---

## 6. Signaltypen

Auf bestehende Signal-Semantik abstimmen und mindestens unterstützen:

```text
NUMERIC_PHYSICAL
ENUM
STATE
BOOLEAN
COUNTER
BITFIELD
COMMAND
EVENT
DERIVED
QUALITY
RAW
```

Keine zweite konkurrierende Signaltyp-Taxonomie erzeugen.

---

## 7. Numerische physikalische Signale

Physikalische Werte nicht zufällig durch den gesamten Wertebereich springen lassen.

Beispiel:

```text
MotorTemperature
unit = °C
physical_min = -40
physical_max = 150
normal_min = 70
normal_max = 105
initial_value = 20
max_rise_rate = 3 °C/s
max_fall_rate = 2 °C/s
```

Plausibel:

```text
20 → 22 → 27 → 35 → 48 → 67 → 82 → 88 → 90
```

Nicht:

```text
20 → 135 → -10 → 91 → 4 → 145
```

---

## 8. Behavior Models

Modular unterstützen:

```text
CONSTANT
STEP
RAMP
LINEAR
SINE
TRIANGLE
SAWTOOTH
PULSE
RANDOM_WALK
BOUNDED_RANDOM
STATE_DEPENDENT
FORMULA
LOOKUP_TABLE
EXTERNAL_SERIES
PHYSICS_MODEL
```

Implementiere eine:

```text
SignalBehaviorRegistry
```

Keine große `if/elif`-Monolithdatei.

---

## 9. Empfohlene Python-Struktur

```text
backend/simulator/signals/
├── core/
│   ├── emulator.py
│   ├── context.py
│   ├── sample.py
│   ├── runtime_state.py
│   └── registry.py
├── numeric/
│   ├── constant.py
│   ├── step.py
│   ├── ramp.py
│   ├── sine.py
│   ├── triangle.py
│   ├── sawtooth.py
│   ├── pulse.py
│   ├── random_walk.py
│   ├── bounded_random.py
│   └── physical.py
├── discrete/
│   ├── boolean.py
│   ├── enum.py
│   ├── state.py
│   ├── counter.py
│   └── bitfield.py
├── commands/
├── events/
├── derived/
├── quality/
├── constraints/
├── noise/
└── faults/
```

---

## 10. Gemeinsamer Emulator Contract

Fachlich:

```python
class SignalEmulator:
    def initialize(self, definition, context):
        ...

    def step(self, time, dt, context):
        ...

    def reset(self):
        ...
```

Sample:

```text
SignalSample
├── signal_ref
├── timestamp
├── physical_value
├── quantized_value
├── raw_value
├── unit
├── quality
├── behavior_model
├── state
├── source
├── fault_state
└── golden_value
```

---

## 11. SimulationContext

Erweitere bzw. konsolidiere:

```text
SimulationContext
├── current_time
├── dt
├── seed
├── scenario
├── system_state
├── function_states
├── signal_values
├── commands
├── faults
├── environment
├── routing_context
└── network_context
```

---

## 12. Statussignale über State Machines

Keine zufälligen Statuswechsel.

Beispiel:

```text
DriveOperatingState
```

mit:

```text
OFF
INIT
READY
STARTING
RUNNING
STOPPING
STANDBY
LIMITED
```

Transitions beispielsweise:

```text
OFF → INIT → READY → STARTING → RUNNING → STOPPING → READY
RUNNING → LIMITED
READY → STANDBY
STANDBY → READY
```

Zusätzliche Fehler-/Safety-Transitions über Guards.

---

## 13. Operating, Health und Safety trennen

### Operating

```text
DriveOperatingState
OFF
INIT
READY
STARTING
RUNNING
STOPPING
STANDBY
LIMITED
```

### Health

```text
DriveHealthState
OK
WARNING
DEGRADED
ERROR
CRITICAL
```

### Safety

```text
DriveSafetyState
NORMAL
SAFE_STATE
EMERGENCY_STOP
```

Damit ist möglich:

```text
OperatingState = RUNNING
HealthState = WARNING
SafetyState = NORMAL
```

---

## 14. StateMachineEngine

Implementiere / konsolidiere:

```text
SignalStateMachineEngine
```

mit:

```text
allowed_states
allowed_transitions
initial_state
transition_guards
transition_delays
error_transitions
```

---

## 15. State-dependent physikalische Signale

Beispiel `MotorRPM`:

```text
OFF        → 0 rpm
INIT       → 0 rpm
READY      → 0 rpm
STARTING   → Ramp 0 → Startdrehzahl
RUNNING    → Last-/Sollwertabhängig
LIMITED    → begrenzte Drehzahl
STOPPING   → Ramp current → 0
STANDBY    → 0 rpm
```

---

## 16. Boolean Signals

Beispiel:

```text
MotorEnabled
```

```text
OFF        → false
INIT       → false
READY      → true
STARTING   → true
RUNNING    → true
STOPPING   → true
STANDBY    → false / configurable
EMERGENCY  → false
```

---

## 17. Commands sind keine States

Beispiel:

```text
MotorStartCommand = TRUE
↓
State Machine
↓
STARTING
↓
RUNNING
```

Command und resultierender Zustand müssen getrennt bleiben.

---

## 18. Events

Beispiel:

```text
EmergencyStopPressed
```

kurzzeitig:

```text
false → true → false
```

Wirkung:

```text
EmergencyStopPressed
↓
SafetyState = EMERGENCY_STOP
↓
MotorEnabled = false
↓
RPM → 0
```

---

## 19. Counter

Beispiel:

```text
AliveCounter
0 → 1 → 2 → ... → 15 → 0
```

Definition:

```text
modulus = 16
increment = 1
update_on = MESSAGE_TRANSMIT
```

---

## 20. Bitfields

Beispiel:

```text
MotorStatusFlags

bit 0 = enabled
bit 1 = warning
bit 2 = error
bit 3 = temperature_high
bit 4 = current_high
bit 5 = communication_fault
```

Flags aus echten Zuständen ableiten.

---

## 21. Derived Signals

Nicht unabhängig randomisieren.

Beispiel:

```text
BatteryPower = BatteryVoltage × BatteryCurrent
```

oder:

```text
MechanicalPower = Torque × AngularVelocity
```

Implementiere / konsolidiere:

```text
DerivedSignalEngine
```

mit:

```text
dependency resolution
formula evaluation
dependency ordering
cycle detection
unit validation
```

---

## 22. Cross-Signal-Abhängigkeiten

Beispiel Motor:

```text
ThrottleCommand
↓
TargetTorque
↓
MotorTorque
↓
MotorRPM
↓
MotorCurrent
↓
MotorTemperature
```

Die Werte dürfen nicht unabhängig voneinander randomisiert werden.

---

## 23. Function Behavior nutzen

Das Engineering-Modell enthält bereits Functions.

Deshalb:

```text
Function State
→ Function Behavior
→ Output Signals
→ Message Encoding
```

Wenn bereits Function-Behavior-Logik existiert:

```text
REUSE / ADAPT
```

sonst `FunctionBehaviorEngine` ergänzen.

---

## 24. Plausibles Motor-Beispiel

```text
ThrottleCommand
0 ... 100 %
        │
        ▼
TargetTorque
        │
        ▼
MotorTorque
0 ... 250 Nm
        │
        ├───────────────┐
        ▼               ▼
MotorRPM            MotorCurrent
0 ... 5000 rpm      0 ... 200 A
        │               │
        └───────┬───────┘
                ▼
        MotorTemperature
         20 ... 120 °C
```

Beispielzeitreihe:

```text
t=0s
OperatingState = OFF
RPM = 0
Current = 0 A
Temperature = 22 °C

t=3s
OperatingState = STARTING
RPM = 350
Current = 42 A
Temperature = 22.3 °C

t=10s
OperatingState = RUNNING
RPM = 1450
Current = 31 A
Temperature = 27 °C

t=60s
OperatingState = RUNNING
RPM = 1620
Current = 35 A
Temperature = 54 °C
```

---

## 25. Rate Limits

Physikalische Signale optional mit:

```text
max_rise_rate
max_fall_rate
```

Beispiel:

```text
Temperature:
+2 °C/s
-1 °C/s

RPM:
+1000 rpm/s
-1500 rpm/s
```

---

## 26. Resolution / Quantization

Bestehende Encoding-Definition wiederverwenden.

Beispiel:

```text
resolution = 50 rpm
```

Ein physikalischer Wert von:

```text
1473 rpm
```

wird vor Encoding entsprechend der definierten Quantisierungsregel auf einen gültigen Schritt gebracht.

---

## 27. Noise

Optional:

```text
NONE
LOW
REALISTIC
CUSTOM
```

Noise muss:

```text
bounded
reproducible
semantic-aware
```

sein.

Nicht globale beliebige Zufallswerte addieren.

---

## 28. Environment

Optional im Context:

```text
AmbientTemperature
Pressure
SupplyVoltage
ExternalLoad
Humidity
VehicleSpeed
MachineLoad
```

Industrieneutral halten.

---

## 29. Realismus-Kennzeichnung

Jedes Behavior Model erhält:

```text
PHYSICS_BASED
RULE_BASED
EMPIRICAL
SYNTHETIC
GENERIC_ESTIMATE
```

Eine einfache Regel darf nicht als echtes Physikmodell ausgegeben werden.

---

## 30. ConstraintEngine

Implementiere / erweitere:

```text
SignalConstraintEngine
```

Beispiele:

```text
MotorRPM > 0
→ MotorEnabled == true
```

```text
Current > 5 A
AND RPM == 0
→ possible BLOCKED_MOTOR
```

```text
Temperature > 110 °C
→ HealthState >= WARNING
```

---

## 31. Quality

Optional unterstützen:

```text
VALID
INVALID
NOT_AVAILABLE
STALE
SUBSTITUTED
ESTIMATED
```

Beispiel:

```text
MotorTemperature = 87.4 °C
Quality = VALID
```

Sensorausfall:

```text
MotorTemperature = last known value
Quality = STALE
```

---

## 32. Fault Injection auf Golden Behavior

Bestehende Fault-Logik nicht ersetzen.

Reihenfolge:

```text
Golden Behavior
↓
Physical Constraints
↓
Noise
↓
Fault Injection
↓
Quality Evaluation
↓
Encoding
```

---

## 33. Faults nach Signaltyp

### Numeric

```text
STUCK
OFFSET
DRIFT
SPIKE
NOISE
DROPOUT
OUT_OF_RANGE
FROZEN
WRONG_SCALE
DELAYED
```

### State

```text
INVALID_STATE
STUCK_STATE
WRONG_TRANSITION
UNEXPECTED_STATE
DELAYED_TRANSITION
```

### Boolean

```text
STUCK_TRUE
STUCK_FALSE
TOGGLE
```

### Counter

```text
STUCK
SKIP
RESET
WRONG_INCREMENT
```

---

## 34. Golden vs Actual

Pro Sample nach Möglichkeit:

```text
golden_value
actual_value
```

beibehalten.

Dadurch sind:

```text
Golden Trace
vs
Fault Trace
```

direkt vergleichbar.

---

## 35. Reproduzierbarkeit

Bestehendes Prinzip beibehalten:

```text
Engineering Snapshot
+
Scenario
+
Seed
=
Reproducible Simulation
```

Alle Random-/Noise-Modelle müssen einen zentralen Seed-Kontext verwenden.

Keine verstreuten unkontrollierten `random.random()`-Aufrufe.

---

## 36. SimulationRandomService

Falls noch nicht vorhanden:

```text
SimulationRandomService
```

mit:

```text
seed
named streams
reproducible random walk
reproducible noise
reproducible scenario variation
```

---

## 37. Universal Trace bleibt zentrale Zeitbasis

`universal_trace.py` bleibt:

```text
single event timeline
```

Keine zweite Timeline Engine ergänzen.

---

## 38. Communication Simulator bleibt Runtime Entry

`communication_simulator.py` bleibt primärer Startpunkt der Runtime.

Neue Signal-Engines werden intern über Model-Based Simulation eingebunden.

---

## 39. Frontend bleibt View

Frontend darf nur:

```text
Scenario konfigurieren
Duration konfigurieren
Scope auswählen
Start / Pause / Stop
Signals darstellen
Busload darstellen
Events darstellen
```

Keine Signalphysik oder State Machines im Frontend.

---

## 40. Result Data erweitern

Bestehende Signalresultate optional ergänzen um:

```text
semantic_type
behavior_model
model_type
golden_value
actual_value
quality
state
fault_state
source_dependencies[]
```

---

## 41. Preflight Validation

Vor Simulation prüfen:

```text
Signal Definition valid?
Semantic Type known?
Behavior Model supported?
State Machine valid?
Derived dependencies resolvable?
Dependency cycle?
Units compatible?
Encoding available?
Message mapping valid?
```

Blocking:

```text
dependency cycle
invalid encoding
missing mandatory mapping
invalid state machine
invalid formula
broken message packing
```

Warnings:

```text
GENERIC_ESTIMATE
missing realistic behavior
unknown rate limit
```

---

## 42. AI-Unterstützung

Nemotron / LLM darf vorschlagen:

```text
BehaviorModelProposal
StateMachineProposal
TypicalRangeProposal
RateLimitProposal
FaultScenarioProposal
```

Aber:

```text
Proposal
→ Review
→ Approval
```

Keine automatische Aktivierung ungeprüfter KI-Vorschläge.

---

## 43. Heuristische Vorschläge

Beispiel:

```text
semantic = TEMPERATURE
→ propose thermal bounded model

semantic = ROTATIONAL_SPEED
→ propose state-dependent ramp

semantic = OPERATING_STATE
→ propose state machine
```

Nur als Proposal, sofern nicht bereits freigegeben.

---

## 44. Performance

Bei vielen abhängigen Signalen:

```text
dependency graph
dirty propagation
only affected signals
cached static metadata
```

verwenden.

Nicht bei jedem Event sämtliche Signale komplett neu berechnen.

---

## 45. Tests

### Numeric

```text
constant
ramp
sine
bounded random
random walk
rate limit
resolution
noise
```

### State

```text
valid transition
invalid transition
delayed transition
stuck state
error transition
```

### Derived

```text
formula
dependency order
cycle detection
unit mismatch
```

### Faults

```text
golden vs faulted
offset
drift
spike
dropout
stuck
```

---

## 46. Motor End-to-End-Test

Mindestens:

```text
MotorStartCommand
DriveOperatingState
MotorEnabled
MotorRPM
MotorTorque
MotorCurrent
MotorTemperature
DriveHealthState
DriveSafetyState
AliveCounter
```

Ablauf:

```text
OFF
→ START
→ RUNNING
→ LOAD
→ HEATING
→ STOP
```

mit gekoppelten plausiblen Werten.

---

## 47. Golden/Fault-End-to-End

Run A:

```text
GOLDEN
```

Run B:

```text
same snapshot
same seed
same scenario
+ fault
```

Prüfen:

```text
identical baseline
fault changes only expected behavior
```

---

## 48. Dokumentation

Erzeuge / aktualisiere:

```text
docs/simulation/
00_SIMULATION_ENGINE_OVERVIEW.md
01_EXISTING_ENGINE_INVENTORY.md
02_SIGNAL_EMULATION_ARCHITECTURE.md
03_SIGNAL_BEHAVIOR_MODELS.md
04_STATE_MACHINE_SIGNALS.md
05_DERIVED_SIGNALS.md
06_PHYSICAL_PLAUSIBILITY.md
07_NOISE_AND_RESOLUTION.md
08_FAULT_INJECTION.md
09_SIGNAL_QUALITY.md
10_FUNCTION_BEHAVIOR.md
11_SIMULATION_CONTEXT.md
12_REPRODUCIBILITY.md
13_TRACE_INTEGRATION.md
14_VALIDATION_AND_PREFLIGHT.md
15_TEST_STRATEGY.md
```

---

## 49. Definition of Done

Die Erweiterung gilt erst als abgeschlossen, wenn:

1. die bestehende Simulation Engine zentrale Runtime bleibt,
2. keine zweite Simulation Engine entstanden ist,
3. bestehende Logik vor Umbau inventarisiert wurde,
4. `ModelBasedSimulationEngine` modular erweitert wurde,
5. numerische physikalische Signale plausible Werte erzeugen,
6. Statussignale State Machines verwenden,
7. Operating-, Health- und Safety-State getrennt modellierbar sind,
8. Boolean Signals zustandsabhängig sind,
9. Commands und Events von States getrennt sind,
10. Counter zyklisch korrekt arbeiten,
11. Bitfields aus echten Zuständen abgeleitet werden,
12. Derived Signals aus Abhängigkeiten entstehen,
13. abhängige Signale nicht unabhängig randomisiert werden,
14. Function Behavior integriert ist,
15. Rate Limits unterstützt werden,
16. Resolution / Quantization korrekt wirkt,
17. Noise kontrolliert und reproduzierbar ist,
18. Quality States unterstützt werden,
19. Fault Injection auf Golden Behavior aufsetzt,
20. Golden Value und Actual Value nachvollziehbar bleiben,
21. alle Zufallsmodelle denselben kontrollierten Seed-Kontext verwenden,
22. Universal Trace zentrale Zeitbasis bleibt,
23. bestehende Trace-/Export-Formate funktionieren,
24. Preflight Validation neue Behavior-Modelle prüft,
25. AI nur Proposals erzeugt,
26. Motor-End-to-End-Test plausible gekoppelte Werte erzeugt,
27. Golden/Fault-Vergleich reproduzierbar ist,
28. Regression der bisherigen Simulation erfolgreich ist,
29. Dokumentation den tatsächlichen As-Built-Stand beschreibt.

---

# Zentrale Leitregel

```text
Do not generate random signal values.

Generate observable values from:
system state,
function behavior,
physical constraints,
dependencies,
environment
and controlled faults.
```

Und:

```text
Do not replace the existing simulation engine.

Extend the existing Python runtime
with specialized, reusable signal-behavior components.
```

Kurz:

```text
INVENTORY
→ REUSE
→ MODULARIZE
→ ADD PLAUSIBILITY
→ VALIDATE
→ SIMULATE
→ TRACE
→ TEST
```
