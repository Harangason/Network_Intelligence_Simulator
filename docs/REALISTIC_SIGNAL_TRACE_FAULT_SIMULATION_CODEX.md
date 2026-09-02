# Arbeitsauftrag für Codex – Realistische Signal-, Trace- und Fehlersimulation

Zielort des Umbaus: http://127.0.0.1:13500/studio/simulation

## 1. Ziel

Überarbeite die Simulationslogik des **Network Intelligence Simulator** grundlegend.

Die Simulation darf nicht länger beliebige oder zufällige Payload- und Signalwerte erzeugen. Stattdessen müssen die im Engineering-Modell definierten Nodes, ECUs, Sensoren, Funktionen, Messages, Signale, Wertebereiche, Einheiten, Auflösungen, Zykluszeiten, Routingpfade, Busparameter und Timing-Anforderungen als Grundlage für eine **realistische und reproduzierbare Emulation des Systemverhaltens** verwendet werden.

Zielarchitektur:

```text
Engineering Model
        ↓
Signal Behavior Models
        ↓
System / Function Behavior
        ↓
Message Generation
        ↓
Routing
        ↓
Network Simulation
        ↓
Bus Load / Timing
        ↓
Trace
        ↓
Signal Plot / Analysis
```

## 2. Grundregel

Nicht mehr:

```text
Random Payload
→ Random Frame
→ Trace
```

sondern:

```text
Signal Definition
+
Signal Behavior
+
System State
+
Simulation Scenario
        ↓
Physical / Logical Signal Value
        ↓
Encode Message
        ↓
Transmit via Network
        ↓
Decode / Observe
        ↓
Trace
```

Die Signalwerte müssen die Ursache der erzeugten Netzwerkdaten sein.

## 3. Signal Behavior Model

Erweitere jedes simulierbare Signal um ein optionales:

```text
SignalBehaviorModel
```

Mindestens:

```text
signal_id
behavior_type
initial_value
minimum
maximum
resolution
unit
cycle_time
rate_of_change
noise
normal_profile
fault_profiles[]
dependencies[]
seed
```

## 4. Unterstützte Normalverläufe

Implementiere zunächst allgemeine, industrieunabhängige Verlaufstypen:

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
```

Diese Modelle müssen immer Signalgrenzen und Auflösung berücksichtigen.

## 5. Beispiel Temperatursignal

```text
Temperature
Min: -20 °C
Max: 120 °C
Resolution: 0.1 °C
Cycle: 100 ms
```

Normalbetrieb beispielsweise:

```text
Start: 20 °C
Ramp: 20 °C → 60 °C
Duration: 30 s
Regelbereich: 58–62 °C
Danach: leichte Schwankung um 60 °C
```

Damit entsteht ein plausibler Verlauf und kein zufälliges Springen über den gesamten Wertebereich.

## 6. Funktionsabhängige Signale

Signale dürfen voneinander abhängig sein.

Beispiel Temperaturregelung:

```text
Temperature
        ↓
ECU_THERMAL
        ↓
ThermalControlRequest
```

Logik:

```text
Temperature < 58
→ HEAT

58 <= Temperature <= 62
→ HOLD

Temperature > 62
→ COOL
```

Die Simulation muss daraus konsistente Signale erzeugen.

## 7. Drehzahlsignal

```text
MotorRPM
Range: 0–5000 U/min
Resolution: 50 U/min
```

Normaler Verlauf beispielsweise:

```text
0
→ Ramp to 1500
→ Hold
→ Ramp to 3000
→ Hold
→ Ramp to 4500
→ Hold
→ Ramp down
```

Jeder Wert muss auf die definierte Auflösung quantisiert werden.

## 8. Abhängigkeiten

Implementiere:

```text
SignalDependency
```

Beispiele:

```text
MotorRPM → beeinflusst MotorCurrent
Temperature → beeinflusst ThermalControlRequest
MotorRPM + MotorCurrent → beeinflussen MotionSystemStatus
```

## 9. Simulation Scenario

Jeder Lauf benötigt ein:

```text
SimulationScenario
```

mit:

```text
scenario_id
name
description
duration
seed
initial_conditions
signal_profiles[]
fault_injections[]
expected_behavior
created_by
```

## 10. Simulationsmodi

Implementiere mindestens:

```text
NORMAL
USER_DEFINED_FAULT
AI_GENERATED_FAULT
STRESS
```

## 11. NORMAL – Fehlerfreier Trace

Im Modus `NORMAL` wird ein idealer bzw. erwarteter Systemverlauf erzeugt.

Ziel:

```text
GOLDEN TRACE / REFERENCE TRACE
```

mit:

- gültigen Signalwerten,
- korrekten Wertebereichen,
- korrekten Auflösungen,
- plausiblen Signalabhängigkeiten,
- korrekten Zykluszeiten,
- funktionierendem Routing,
- keiner absichtlichen Frame-Corruption,
- keinem absichtlichen Packet Loss,
- keiner absichtlichen Timingverletzung.

## 12. Golden Trace

Unterstütze die explizite Erzeugung eines `GoldenTrace` für:

```text
Regressionstest
Vergleich mit Fault Trace
Vergleich mit realem Trace
AI Root Cause Analysis
Signalvergleich
Systemvalidierung
```

## 13. Fehlersimulation

Implementiere einen separaten:

```text
FaultInjectionEngine
```

Fehler müssen als explizite Fault Events modelliert werden.

## 14. Signalfehler

Mindestens:

```text
SIGNAL_STUCK
SIGNAL_OFFSET
SIGNAL_DRIFT
SIGNAL_SPIKE
SIGNAL_DROPOUT
SIGNAL_NOISE
SIGNAL_OUT_OF_RANGE
SIGNAL_FROZEN
SIGNAL_DELAYED
SIGNAL_WRONG_SCALE
SIGNAL_INVALID_VALUE
```

## 15. Kommunikationsfehler

Mindestens:

```text
MESSAGE_LOSS
MESSAGE_DELAY
MESSAGE_JITTER
MESSAGE_DUPLICATION
MESSAGE_CORRUPTION
MESSAGE_WRONG_CYCLE
MESSAGE_TIMEOUT
BURST_TRAFFIC
FRAME_ERROR
ROUTING_FAILURE
```

## 16. Netzwerkfehler

Vorbereiten:

```text
NETWORK_OVERLOAD
BUS_OFF
LINK_DOWN
GATEWAY_DELAY
GATEWAY_DROP
QUEUE_OVERFLOW
CONGESTION
TEMPORARY_DISCONNECT
```

Nur implementieren, soweit die jeweilige Technologie dies sinnvoll unterstützt.

## 17. Benutzerdefinierte Fehler

Der Benutzer muss Fehler gezielt definieren können, z. B.:

```text
Fault: MotorRPM spike
Start: 18 s
Duration: 500 ms
Value: 5200 U/min
```

```text
Fault: Temperature Sensor Frozen
Start: 40 s
Duration: 10 s
Frozen Value: 61.2 °C
```

```text
Fault: Message Loss
Message: MSG_MOTION_STATUS
Start: 30 s
Duration: 2 s
Loss: 100 %
```

## 18. KI-generierte Fehlerszenarien

Der AI Agent darf Fehlerszenarien als Proposal erzeugen. Grundlage:

```text
Engineering Model
Signals
Functions
Routing
Network
Limits
Dependencies
Previous Simulations
Knowledge / RAG
```

Ausgabe:

```text
FaultScenarioProposal
```

Die KI darf keinen Fehler unsichtbar direkt aktivieren.

## 19. Reproduzierbare KI-/Random-Faults

Auch bei „zufälligen“ Fehlern wählt die KI nur geeignete Fault-Typen und Parameter. Die eigentliche Simulation verwendet einen Seed.

```text
Scenario + Seed + Engineering Snapshot
```

muss reproduzierbar sein.

## 20. FaultScenarioProposal

Mindestens:

```text
fault_type
target
start_time
duration
parameters
reason
expected_effect
confidence
origin
```

Origin:

```text
USER
AI_GENERATED
PREDEFINED
```

Aktionen:

```text
Accept
Edit
Reject
```

## 21. Fault Campaign

Mehrere Fehler pro Lauf ermöglichen:

```text
25 s  RPM Signal Dropout
40 s  Gateway Delay
55 s  Temperature Offset +10 °C
70 s  CAN Burst Load
```

## 22. Expected Behavior

Bei bekannten Szenarien optional `ExpectedBehavior` speichern, sodass die Simulation gleichzeitig testbar wird.

## 23. Simulationspipeline

```text
SimulationScenario
        ↓
SignalBehaviorEngine
        ↓
FunctionBehaviorEngine
        ↓
Signal Values
        ↓
Message Encoder
        ↓
Routing Engine
        ↓
Network Scheduler
        ↓
Fault Injection Engine
        ↓
Trace Writer
        ↓
Runtime Metrics
```

## 24. SignalBehaviorEngine

Implementiere mindestens:

```text
generate_signal_value()
apply_resolution()
apply_limits()
apply_normal_profile()
apply_dependencies()
apply_signal_fault()
advance_state()
```

## 25. FunctionBehaviorEngine

Verarbeitet deterministische Funktionsregeln, z. B.:

```text
Temperature
→ ThermalControlFunction
→ ThermalControlRequest
```

```text
MotorRPM + MotorCurrent
→ MotionStatusFunction
→ MotionSystemStatus
```

Nicht jedes Verhalten muss sofort ein vollständiges physikalisches Modell sein, aber die Zusammenhänge müssen konsistent sein.

## 26. Erweiterbare Verhaltensmodelle

Architektur vorbereiten für:

```text
Simple Model
Formula Model
State Machine
Lookup Table
External Python Model
FMU / FMI Model
```

Zunächst eine saubere `BehaviorModel`-Schnittstelle schaffen.

## 27. Message Encoder

Signalwerte anhand der Signaldefinition in reale Message-Payloads encodieren.

Berücksichtige soweit definiert:

```text
datatype
bit_length
signed
factor
offset
endianness
enum
invalid_value
```

```text
Engineering Signal Value
→ Encoded Raw Value
→ Message Payload
```

## 28. Empfangsseite

Soweit möglich:

```text
Message Payload
→ Decoder
→ Signal Value
```

Damit `sent value` und `received value` vergleichbar werden.

## 29. Buslast

Die Buslast muss während der Simulation kontinuierlich überwacht werden.

Mindestens pro Netzwerk:

```text
Current Load
Average Load
Peak Load
Burst Load
Capacity Reserve
```

## 30. RuntimeBusLoadMonitor

Implementiere:

```text
RuntimeBusLoadMonitor
```

Input:

```text
actual frames
frame size
protocol overhead
timestamps
network bitrate
```

Keine erfundenen Prozentwerte.

## 31. Engineering vs Runtime Busload

Unterscheide:

```text
CALCULATED LOAD
```

und:

```text
SIMULATED LOAD
```

Beispiel:

```text
MOTION_CAN
Calculated: 58 %
Simulated Average: 61 %
Simulated Peak: 76 %
```

## 32. Visuelle Buslastdarstellung

Ergänze einen `Bus Load View` mit:

```text
Current Load
Average Load
Peak Load
Reserve
Status
```

Darstellung:

```text
Live Gauge / Bar
+
Time Series
```

## 33. Netzwerk-/ECU-View

Während der Simulation die aktuelle Buslast direkt am Netz anzeigen können:

```text
ECU_MOTION
    │
MOTION_CAN
Load: 67 %
Peak: 82 %
    │
    ▼
GW_01
```

## 34. Signal Plot

Ergänze eine zentrale `Signal Plot View`.

Mehrfachauswahl von Signalen, z. B.:

```text
[x] Temperature
[x] MotorRPM
[x] MotorCurrent
```

## 35. Signalplot-Funktionen

Mindestens:

```text
Time on X-axis
Physical Value on Y-axis
Current Value
Min / Max
Engineering Limits
Playhead
Zoom
Pan
Signal Selection
Show / Hide Signals
```

## 36. Unterschiedliche Einheiten

Inkompatible Einheiten nicht blind auf dieselbe Y-Achse legen.

Bevorzugt:

```text
stacked signal lanes
```

mit gemeinsamer Zeitachse.

## 37. Grenzwerte im Plot

Engineering Limits sichtbar darstellen, z. B.:

```text
5000 rpm  LIMIT
4800 rpm  WARNING
```

bzw. Temperatur-Schwellen wie Sollwert, Regelband und Overtemperature Limit.

## 38. Fault Marker

Im Signalplot markieren:

```text
Fault Start
Fault End
Warning
Error
Timeout
Message Loss
```

## 39. Golden Trace vs Fault Trace

Vergleich ermöglichen:

```text
GOLDEN TRACE
vs
FAULT TRACE
```

mit:

```text
Expected
Actual
Deviation
```

## 40. Trace-Arten

```text
GOLDEN
NORMAL
FAULT_INJECTED
AI_FAULT_INJECTED
STRESS
CUSTOM
```

Jeder Trace referenziert:

```text
SimulationScenario
SimulationSnapshot
FaultCampaign
Seed
```

## 41. Trace Metadata

Mindestens:

```text
trace_id
simulation_id
scenario_id
scenario_type
seed
engineering_snapshot
start_time
duration
networks
faults[]
generated_at
```

## 42. Stress Simulation

Modus `STRESS` vorbereiten für:

```text
increase message frequency
increase event rate
burst traffic
additional diagnostics traffic
gateway congestion
```

## 43. Simulation UI

Die Seite bleibt einfach. Oben nur:

```text
Scenario
Duration
Speed
Seed
Trace Formats

[ Start ]
[ Pause ]
[ Stop ]
[ Reset ]
```

Szenarioauswahl:

```text
Golden / Ideal
Normal
User Fault
AI Fault
Stress
```

Keine Busparameter hier konfigurieren.

## 44. Simulation Views

Während des Laufs mindestens:

```text
NETWORK / ECU
SIGNALS
BUS LOAD
EVENTS
```

## 45. Synchronisierung

Alle Views verwenden denselben:

```text
Simulation Clock
Playhead
```

Damit sind Signal Plot, Bus Load Plot, Network Animation und Event List zeitlich synchron.

## 46. Live Event List

Mindestens:

```text
Timestamp
Severity
Event Type
Node
Message
Signal
Network
Description
```

## 47. KI-Unterstützung

Agent Tools mindestens vorbereiten:

```text
inspect_simulation_scenario()
inspect_signal_behavior()
create_normal_scenario()
create_fault_scenario()
suggest_faults()
create_fault_campaign()
compare_golden_and_fault_trace()
analyze_signal_deviation()
analyze_bus_load()
identify_first_anomaly()
identify_causal_chain()
```

## 48. KI und RAG

Fault-Vorschläge dürfen verwenden:

```text
Engineering Model
Signal Definitions
Functions
Routing
Network Topology
Requirements
Historical Simulations
Trace Analysis
Knowledge Graph
RAG Knowledge
```

## 49. Random-Fault-Modus

Optional:

```text
Fault Probability
Maximum Fault Count
Allowed Fault Categories
```

Aber immer:

- seed-basiert,
- aus Fault Catalog,
- keine beliebigen kaputten Daten.

## 50. Fault Catalog

Implementiere zentral:

```text
FaultCatalog
```

Jeder Fault Type beschreibt:

```text
id
name
category
applicable_object_types
parameters
constraints
simulation_handler
```

## 51. FaultScenarioValidator

Vor Fehlerausführung prüfen:

```text
Target exists
Fault compatible with target
Start time valid
Duration valid
Values valid
Fault technically possible
Required model available
```

Wenn nur synthetisch approximierbar:

```text
SIMPLIFIED_FAULT_MODEL
```

kennzeichnen.

## 52. Modelltyp kennzeichnen

Unterscheide:

```text
PHYSICS_BASED
RULE_BASED
EMPIRICAL
SYNTHETIC
GENERIC_ESTIMATE
```

Keine falsche Behauptung physikalischer Genauigkeit.

## 53. Ergebnisse

Nach Simulation mindestens:

```text
Signal Summary
Fault Summary
Network Load Summary
Timing Summary
Trace Artifacts
Golden Trace Comparison
Warnings / Errors
First Anomaly
Affected Routes
Affected Signals
```

## 54. Verbindung zur Trace-Analyse

Jeder Simulation Trace muss direkt im Prozess `TRACE ANALYSE` geöffnet werden können:

```text
Simulation
→ Trace
→ Open Trace Analysis
→ Botschaften
→ Sequenz
→ Signale
→ Trace
→ Findings
→ Root Cause
```

## 55. Tests

Mindestens:

```text
Signal range respected
Signal resolution respected
Cycle time respected
Normal profile reproducible
Same seed = same result
Different seed = valid variation
Fault starts at correct time
Fault ends correctly
Fault modifies correct signal
Dependent signals react consistently
Message encoding correct
Runtime bus load correct
Peak load detected
Signal plot data consistent with trace
Golden trace contains no injected faults
Fault trace contains configured fault
AI fault proposal requires confirmation
```

## 56. Demo-Test

Für das vorhandene einfache Demo-System mit `Temperature`, `MotorRPM` und `MotorCurrent` mindestens:

### Scenario A – Golden

```text
Temperature: 20 → 60 °C → stable
MotorRPM: 0 → 3000 → 4500 → 2000
MotorCurrent: plausibly follows RPM/load
No injected faults
```

### Scenario B – RPM Fault

```text
At 30 s:
MotorRPM: 4500 → 5200 U/min
Expected: RPM_LIMIT_EXCEEDED
```

### Scenario C – Temperature Fault

```text
At 40 s:
Temperature Sensor frozen at 61 °C
actual modeled temperature continues changing
```

### Scenario D – Network Fault

```text
At 50 s:
MSG_MOTION_STATUS loss for 2 s
Expected: Timeout / stale signal behavior
```

### Scenario E – AI Fault Campaign

KI erzeugt drei plausible Fehler als Proposal. Benutzer bestätigt. Simulation führt sie reproduzierbar aus.

## 57. Definition of Done

Die neue Simulation ist erst abgeschlossen, wenn:

1. Signalwerte aus Engineering-Signaldefinitionen erzeugt werden.
2. Min/Max, Unit, Resolution und Cycle berücksichtigt werden.
3. realistische Signalverläufe über Behavior Models erzeugt werden.
4. Signalabhängigkeiten möglich sind.
5. Funktionslogik auf Signalwerte reagieren kann.
6. Signalwerte zu echten Message-Payloads führen.
7. Routing und Netzwerkparameter den Transport bestimmen.
8. Runtime-Buslast aus tatsächlich übertragenen Frames berechnet wird.
9. Average, Peak und Burst Load verfügbar sind.
10. Golden/Ideal Traces erzeugt werden können.
11. Nutzer Fault Scenarios definieren können.
12. KI Fault Proposals erzeugen kann.
13. Faults reproduzierbar seed-basiert ausgeführt werden.
14. mehrere Faults als Campaign möglich sind.
15. Signalplots live angezeigt werden.
16. Buslast live visualisiert wird.
17. Events synchron mit Signal- und Buslastplots dargestellt werden.
18. Golden und Fault Traces vergleichbar sind.
19. erzeugte Traces direkt in Trace-Analyse geöffnet werden können.
20. synthetische Modelle nicht als physikalisch validierte Modelle ausgegeben werden.

# Architektur-Leitsatz

```text
Signals create values.
Functions create behavior.
Messages transport values.
Networks create timing and load.
Faults create controlled deviations.
Simulation creates evidence.
Trace Analysis explains what happened.
```

Die Simulation soll damit von einem **generischen Trace-Generator** zu einer **modellbasierten, reproduzierbaren Kommunikations- und Signalverhaltenssimulation** weiterentwickelt werden.
