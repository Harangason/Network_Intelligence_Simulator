# Arbeitsauftrag für Codex
## Modulare Signal-Emulation für Zustände, physikalische Verläufe und Trace-Erzeugung

## 1. Ziel

Erweitere die bestehende Python-first Simulation Engine des Network Intelligence Simulator um eine klar modulare Signal-Emulationsarchitektur.

Die Simulation soll zwei grundsätzlich unterschiedliche Arten von Signalen korrekt behandeln:

```text
DISCRETE / STATE SIGNALS
→ zeigen Zustände, Events, Flags, Counter

CONTINUOUS / PHYSICAL SIGNALS
→ zeigen zeitliche physikalische Verläufe
```

Beispiele:

```text
GatewayOperatingState
→ OFF
→ INIT
→ CONFIGURING
→ READY
→ ACTIVE
```

und:

```text
MotorTemperature
→ 22.0
→ 22.2
→ 22.8
→ 24.1
→ 27.0
→ ...
```

Die Signal-Trace-Erzeugung muss beide Typen unterschiedlich behandeln.

Python bleibt Hauptsprache. C++ darf nur später und ausschließlich für nachgewiesene Performance-Hotspots ergänzt werden.

---

## 2. Zentrale Architekturregel

```text
STATE SIGNAL
→ State Machine / Discrete Emulator

PHYSICAL SIGNAL
→ Continuous / Physical Model

DERIVED SIGNAL
→ Formula / Dependency Model

FAULT
→ Overlay on normal signal behavior

TRACE
→ Result Consumer
```

Nicht:

```text
all signals
→ random(min, max)
```

---

## 3. Keine zweite Simulation Engine

Bestehende Runtime weiterverwenden:

```text
Existing Simulation Runtime
→ Signal Emulation Layer
→ SignalSample
→ Encoding
→ Message Packing
→ Communication Runtime
→ Trace
```

Keine parallele neue Runtime aufbauen.

---

## 4. Python bleibt Hauptsprache

```text
Python
= Signal Logic
= State Machines
= Physical Models
= Dependency Models
= Simulation Orchestration
= Trace Preparation
```

C++ nur optional für:

```text
high event rates
hard real-time kernels
very large Monte-Carlo runs
heavy numeric solvers
very large scheduling workloads
```

und nur nach Profiling.

---

## 5. Zielstruktur

```text
backend/simulator/signals/
├── core/
│   ├── emulator.py
│   ├── context.py
│   ├── sample.py
│   ├── registry.py
│   ├── runtime_state.py
│   └── model_type.py
├── states/
│   ├── state_machine.py
│   ├── operating_state.py
│   ├── health_state.py
│   ├── safety_state.py
│   ├── quality_state.py
│   ├── communication_state.py
│   ├── boolean.py
│   ├── event.py
│   └── counter.py
├── status_models/
│   ├── gateway.py
│   ├── controller.py
│   ├── sensor.py
│   ├── camera.py
│   ├── actuator.py
│   ├── motor.py
│   ├── network_interface.py
│   ├── function.py
│   └── generic.py
├── physical/
│   ├── temperature.py
│   ├── rotational_speed.py
│   ├── torque.py
│   ├── pressure.py
│   ├── voltage.py
│   ├── current.py
│   ├── position.py
│   ├── velocity.py
│   ├── acceleration.py
│   └── generic_physical.py
├── mathematical/
│   ├── constant.py
│   ├── step.py
│   ├── ramp.py
│   ├── sine.py
│   ├── triangle.py
│   ├── pulse.py
│   ├── random_walk.py
│   └── bounded_random.py
├── derived/
│   ├── formula.py
│   ├── lookup.py
│   ├── dependency_graph.py
│   └── evaluator.py
├── constraints/
│   ├── range.py
│   ├── rate.py
│   ├── cross_signal.py
│   └── validator.py
├── noise/
│   ├── gaussian.py
│   ├── bounded.py
│   ├── sensor_noise.py
│   └── registry.py
└── faults/
    ├── stuck.py
    ├── drift.py
    ├── offset.py
    ├── dropout.py
    ├── delayed.py
    ├── invalid_state.py
    └── registry.py
```

Nicht in `off.py`, `init.py`, `ready.py` usw. zersplitten. Nach Verhalten und Objekttyp modularisieren.

---

## 6. Gemeinsamer Emulator Contract

```python
class SignalEmulator:
    def initialize(self, definition, context):
        ...

    def step(self, time, dt, context):
        ...

    def reset(self):
        ...
```

`SignalSample` enthält mindestens:

```text
signal_ref
timestamp
semantic_type
physical_value
display_value
quantized_value
raw_value
unit
quality
state
model_type
source
golden_value
fault_state
```

---

## 7. State-Signal-Emulation

State-Signale zeigen den aktuellen diskreten Zustand.

Beispiel Gateway:

```text
t=0.00  OFF
t=0.10  INIT
t=0.50  CONFIGURING
t=1.20  READY
t=1.50  ACTIVE
```

Kein kontinuierlicher Zahlenverlauf.

---

## 8. Statusmodelle

### Gateway

Operating:

```text
OFF
INIT
CONFIGURING
READY
ACTIVE
STANDBY
SHUTTING_DOWN
```

Health:

```text
OK
WARNING
DEGRADED
ERROR
CRITICAL
```

Communication:

```text
OFFLINE
INITIALIZING
CONNECTED
PARTIAL
BUS_OFF
LINK_LOSS
ERROR
```

### Controller / ECU

```text
OFF
INIT
SELF_TEST
READY
RUNNING
SHUTDOWN
```

plus:

```text
RUNNING → DEGRADED
RUNNING → ERROR
```

### Sensor

Operating:

```text
OFF
INIT
CALIBRATING
READY
MEASURING
STANDBY
```

Health:

```text
OK
WARNING
DEGRADED
ERROR
```

Quality:

```text
VALID
DEGRADED
STALE
NOT_AVAILABLE
INVALID
```

### Kamera

Operating:

```text
OFF
INIT
CALIBRATING
READY
ACTIVE
STANDBY
```

Data Quality:

```text
VALID
DEGRADED
BLOCKED
DIRTY
OVEREXPOSED
UNDEREXPOSED
NOT_AVAILABLE
STALE
```

### Aktor

```text
OFF
INIT
READY
ENABLED
ACTIVE
HOLDING
STOPPING
LIMITED
ERROR
```

Safety:

```text
NORMAL
SAFE_STATE
EMERGENCY_STOP
```

### Motor

Operating:

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

Health:

```text
OK
WARNING
DEGRADED
ERROR
CRITICAL
```

Safety:

```text
NORMAL
SAFE_STATE
EMERGENCY_STOP
```

### Funktion

```text
INACTIVE
INITIALIZING
READY
ACTIVE
DEGRADED
TERMINATING
ERROR
```

---

## 9. StateMachineEngine

Implementiere zentral:

```text
StateMachineEngine
```

mit:

```text
initial_state
allowed_states
allowed_transitions
transition_guards
transition_delays
fault_transitions
reset_behavior
```

Status muss auf die Simulation wirken.

Beispiel Gateway:

```text
INIT
→ RoutingActive = false

READY
→ configuration valid

ACTIVE
→ RoutingActive = true
→ MessageForwarding = true
```

---

## 10. Physikalische Modelle

Spezialisierte Modelle:

```text
temperature.py
rotational_speed.py
torque.py
pressure.py
voltage.py
current.py
position.py
velocity.py
acceleration.py
```

### Temperatur

```text
T_next
=
T_current
+
heating(dt)
-
cooling(dt)
```

Berücksichtigen:

```text
ambient temperature
thermal mass
heat input
cooling
rate limits
physical limits
```

### Drehzahl

Berücksichtigen:

```text
target speed
current speed
load
acceleration
deceleration
inertia
operating state
limits
```

State-Abhängigkeit:

```text
OFF        → target = 0
STARTING   → ramp up
RUNNING    → follow command/load
LIMITED    → cap target
STOPPING   → ramp down
```

### Position

```text
target position
current position
velocity
acceleration
travel limits
state
```

---

## 11. State ↔ Physics Kopplung

Beispiel:

```text
MotorOperatingState
→ MotorRPM
→ MotorCurrent
→ MotorTemperature
```

Physik darf zurückwirken:

```text
Temperature > 110 °C
→ HealthState = WARNING
```

```text
Temperature > 130 °C
→ HealthState = CRITICAL
→ OperatingState = STOPPING
→ SafetyState = SAFE_STATE
```

---

## 12. Cross-Signal Dependencies

Beispiel:

```text
ThrottleCommand
→ TargetTorque
→ MotorTorque
→ MotorRPM
→ MotorCurrent
→ MotorTemperature
```

Nicht unabhängig randomisieren.

Implementiere:

```text
SignalDependencyGraph
```

mit:

```text
topological ordering
cycle detection
dirty propagation
dependency lookup
```

---

## 13. Derived Signals

Beispiele:

```text
BatteryPower = Voltage × Current
MechanicalPower = Torque × AngularVelocity
```

Derived-Signale nie unabhängig emulieren.

---

## 14. Mathematical Models

Für synthetische Testsignale weiterhin:

```text
CONSTANT
STEP
RAMP
SINE
TRIANGLE
PULSE
RANDOM_WALK
BOUNDED_RANDOM
```

Kennzeichnung:

```text
SYNTHETIC
```

---

## 15. Model Type

Jedes Modell:

```text
PHYSICS_BASED
RULE_BASED
EMPIRICAL
SYNTHETIC
GENERIC_ESTIMATE
```

`GENERIC_ESTIMATE` nur als Fallback und nicht als echte Physik ausgeben.

---

## 16. Rate Limits

Unterstütze:

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

## 17. Noise

Pipeline:

```text
Golden Physical Value
→ Noise
→ Fault Injection
→ Actual Value
```

Noise:

```text
NONE
LOW
REALISTIC
CUSTOM
```

reproduzierbar über zentralen Seed.

---

## 18. Quality

Zusätzliche Quality-Zustände:

```text
VALID
DEGRADED
STALE
NOT_AVAILABLE
SUBSTITUTED
ESTIMATED
INVALID
```

---

## 19. Fault Injection

Numeric:

```text
STUCK
OFFSET
DRIFT
SPIKE
DROPOUT
WRONG_SCALE
DELAYED
```

State:

```text
INVALID_STATE
STUCK_STATE
WRONG_TRANSITION
DELAYED_TRANSITION
```

Boolean:

```text
STUCK_TRUE
STUCK_FALSE
TOGGLE
```

Counter:

```text
STUCK
SKIP
RESET
WRONG_INCREMENT
```

Golden und Actual getrennt nachvollziehbar halten.

---

## 20. Trace Rendering

### Numeric

```text
continuous / sampled curve
```

### State / Enum

```text
state lane / step trace
```

Beispiel:

```text
ACTIVE      ────────────────
                    │
READY        ───────┘
        │
INIT ───┘
```

### Boolean

```text
0 / 1 step trace
```

### Counter

```text
discrete step trace
```

### Event

```text
marker / impulse
```

Keine Interpolation zwischen Enum-Werten.

---

## 21. TraceWriter bleibt Consumer

TraceWriter erzeugt keine Werte.

```text
Signal Emulator
→ SignalSample
→ Encoding
→ Message
→ TraceWriter
```

---

## 22. Registry

Implementiere:

```text
SignalEmulatorRegistry
StatusModelRegistry
PhysicalModelRegistry
```

Beispiele:

```text
MotorTemperature
semantic = TEMPERATURE
producer = Motor
→ physical/temperature.py
```

```text
CentralGateway
dimension = OPERATING
→ status_models/gateway.py
```

---

## 23. AI-Rolle

AI darf vorschlagen:

```text
BehaviorModelProposal
StatusModelProposal
PhysicalParameterProposal
RateLimitProposal
NoiseModelProposal
```

Aber:

```text
Proposal
→ Validation
→ User Approval
```

Kein LLM pro Simulationsschritt.

Nicht:

```text
LLM → next RPM every 10 ms
```

Sondern:

```text
LLM → model proposal
Python → runtime execution
```

---

## 24. Performance

Python zuerst optimieren über:

```text
dependency graph
dirty propagation
NumPy where useful
batch evaluation
cached static metadata
```

C++ erst nach Profiling.

---

## 25. Optionale Native-Kernel-Architektur

Nur bei nachgewiesenem Hotspot:

```text
Python Simulation Orchestration
→ Native Kernel Interface
→ C++ / Rust
```

Beispielsweise via `pybind11`.

Python bleibt zuständig für:

```text
orchestration
registry
configuration
validation
trace pipeline
```

Native nur für:

```text
hot numeric/runtime kernels
```

---

## 26. Tests

### Gateway

```text
OFF → INIT
INIT → CONFIGURING
CONFIGURING → READY
READY → ACTIVE
invalid transition rejected
transition delay honored
fault transition honored
```

### Motor

```text
OFF
→ INIT
→ READY
→ STARTING
→ RUNNING
→ STOPPING
```

Prüfen:

```text
RPM follows state
Current follows load
Temperature evolves continuously
Health reacts to overtemperature
Safety reacts to critical temperature
```

### Sensor

```text
OFF
→ INIT
→ CALIBRATING
→ READY
→ MEASURING
```

Quality:

```text
VALID
→ DEGRADED
→ STALE
→ NOT_AVAILABLE
```

### Trace

Prüfen:

```text
numeric curve
state lane
boolean step
counter step
event marker
```

---

## 27. Golden/Fault-Test

Gleicher:

```text
snapshot
seed
scenario
```

Run A:

```text
GOLDEN
```

Run B:

```text
FAULT
```

Prüfen:

```text
same baseline
only expected fault deviations
```

---

## 28. Regression

Bestehende:

```text
universal_trace
model_trace
busload
messages
faults
encoding
exports
```

dürfen nicht brechen.

---

## 29. Dokumentation

Erzeuge:

```text
docs/simulation_signal_models/

00_OVERVIEW.md
01_SIGNAL_MODEL_ARCHITECTURE.md
02_STATE_SIGNAL_MODELS.md
03_STATUS_MODEL_REGISTRY.md
04_GATEWAY_STATUS_MODEL.md
05_CONTROLLER_STATUS_MODEL.md
06_SENSOR_STATUS_MODEL.md
07_MOTOR_STATUS_MODEL.md
08_PHYSICAL_SIGNAL_MODELS.md
09_TEMPERATURE_MODEL.md
10_ROTATIONAL_SPEED_MODEL.md
11_DERIVED_SIGNALS.md
12_STATE_PHYSICS_COUPLING.md
13_NOISE_AND_QUALITY.md
14_FAULT_OVERLAY.md
15_TRACE_RENDERING.md
16_PERFORMANCE_AND_NATIVE_KERNELS.md
17_TEST_STRATEGY.md
```

---

## 30. Definition of Done

Die Aufgabe ist erst abgeschlossen, wenn:

1. State- und Physical-Signale getrennte Emulatorlogik besitzen.
2. Statussignale nicht als Zufallswerte erzeugt werden.
3. Gateway einen Lifecycle mit INIT / READY / ACTIVE besitzt.
4. Controller einen plausiblen Lifecycle besitzt.
5. Sensoren INIT / CALIBRATING / READY / MEASURING unterstützen.
6. Motoren OFF / INIT / READY / STARTING / RUNNING / STOPPING unterstützen.
7. Operating-, Health-, Safety-, Communication- und Quality-Status getrennt modellierbar sind.
8. StateMachineEngine Transitionen validiert.
9. physikalische Signalmodelle spezialisierte Python-Dateien besitzen.
10. Temperature einen kontinuierlichen Verlauf besitzt.
11. Rotational Speed einen zustandsabhängigen Verlauf besitzt.
12. Current / Torque / Position / Velocity / Acceleration modular erweiterbar sind.
13. Derived Signals über Dependency Graph berechnet werden.
14. Cross-Signal-Abhängigkeiten unterstützt werden.
15. Physics Status beeinflussen kann.
16. Status Physical Models beeinflussen kann.
17. Noise getrennt und reproduzierbar ist.
18. Faults normales Verhalten überlagern.
19. Golden und Actual getrennt nachvollziehbar sind.
20. Trace State-Signale als State-/Step-Trace darstellt.
21. Numeric Signals als plausible Kurve dargestellt werden.
22. TraceWriter keine Signalwerte selbst erzeugt.
23. Encoding und Packing getrennt bleiben.
24. Registries die richtigen Modelle auflösen.
25. kein Monolith-Signalmodul entstanden ist.
26. Python Hauptsprache bleibt.
27. C++ nicht ohne Profiling eingeführt wurde.
28. optionale Native Kernel sauber entkoppelt sind.
29. Unit-, Integration- und Regressionstests erfolgreich sind.
30. Dokumentation dem tatsächlichen As-Built entspricht.

---

# Zentrale Leitregel

```text
A state signal describes WHAT STATE the system is in.

A physical signal describes HOW A PHYSICAL VALUE evolves over time.

A derived signal describes WHAT follows from other values.

A fault modifies expected behavior.

The trace only visualizes the resulting samples.
```

Kurz:

```text
STATE MODEL
+
PHYSICAL MODEL
+
DEPENDENCIES
+
FAULTS
→ SIGNAL SAMPLE
→ ENCODING
→ MESSAGE
→ TRACE
```

Python bleibt die führende Implementierungssprache.

C++ / Rust wird nur dort ergänzt, wo Profiling später einen echten Performance-Hotspot nachweist.
