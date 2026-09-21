# Network Intelligence Simulator (NIS)
## Validation / Preflight Data Quality Integration
## Datenqualität als verbindlicher Bestandteil der Engineering-Validierung

---

# 1. Ziel

Datenqualität wird im Network Intelligence Simulator **nicht als separates Nebenmodul** implementiert.

Sie wird integraler Bestandteil von:

```text
Validation
+
Preflight
```

Ziel:

```text
INPUT
↓
MODEL
↓
VALIDATION
↓
DATA QUALITY CHECKS
↓
TECHNOLOGY CHECKS
↓
PHYSICAL CHECKS
↓
CROSS-LAYER CHECKS
↓
CALCULATION CONSISTENCY
↓
SIMULATION PREFLIGHT
↓
READY / BLOCKED
```

Zentrale Regel:

> **Kein Modell darf als simulationsbereit gelten, wenn seine Daten fachlich, technologisch, physikalisch oder semantisch inkonsistent sind.**

---

# 2. Keine separate Data-Quality-Insel

Nicht:

```text
DataQualityEngine
→ eigener paralleler Prüfpfad
```

Sondern:

```text
ValidationEngine
│
├── Schema Validation
├── Semantic Validation
├── Data Quality Validation
├── Technology Validation
├── Physical Validation
├── Relationship Validation
├── Graph Validation
├── Cross-Layer Validation
├── Calculation Consistency
└── Preflight
```

Data Quality wird somit über dieselbe Validation-Governance ausgeführt wie Routing, Capacity und Timing.

---

# 3. Gesamtpipeline

Empfohlene Pipeline:

```text
User / Import / Agent / Wizard
↓
Canonical Model
↓
ValidationEngine
│
├── V01 Schema
├── V02 Units
├── V03 Semantics
├── V04 Completeness
├── V05 Provenance
├── V06 Technology
├── V07 Physical Realization
├── V08 Relationships
├── V09 Graph Invariants
├── V10 Cross-Layer Consistency
├── V11 Plausibility
├── V12 Namespace / Uniqueness
├── V13 Derived Value Consistency
├── V14 Routing
├── V15 Capacity
├── V16 Timing
├── V17 Simulation Readiness
└── V18 Trace Readiness
↓
PreflightDecision
```

---

# 4. PreflightDecision

Der Preflight liefert einen strukturierten Status:

```text
READY
READY_WITH_WARNINGS
REVIEW_REQUIRED
BLOCKED
STALE
```

Nicht nur:

```text
true / false
```

---

# 5. Preflight Gate

Simulation darf nur starten bei:

```text
READY
```

oder – falls ausdrücklich erlaubt – bei:

```text
READY_WITH_WARNINGS
```

Nicht zulässig:

```text
BLOCKED
REVIEW_REQUIRED
STALE
```

für produktive Simulationen.

---

# 6. Validation Severity

Jeder Befund erhält:

```text
INFO
WARNING
REVIEW
ERROR
BLOCKER
```

Regel:

```text
BLOCKER
→ Preflight = BLOCKED

ERROR
→ Preflight = BLOCKED

REVIEW
→ Preflight = REVIEW_REQUIRED

WARNING
→ READY_WITH_WARNINGS möglich
```

---

# 7. Datenstatus

Wichtige technische Daten erhalten einen Qualitätsstatus:

```text
UNKNOWN
PROPOSED
CONFIRMED
DERIVED
CALCULATED
VALID
INVALID
STALE
REVIEW_REQUIRED
```

Beispiel:

```text
LIN bitrate = UNKNOWN
```

ist akzeptabler als:

```text
LIN bitrate = 2 Mbit/s
```

mit falschem Default.

---

# 8. Data Provenance

Wichtige Modellwerte sollen ihre Herkunft kennen.

Beispiel:

```yaml
value: 19200
unit: bit/s

provenance:
  source_type: USER_CONFIRMED
  source_ref: project-wizard
  source_revision: 17
  confidence: CONFIRMED
  timestamp: ...
```

---

# 9. Source Types

Mindestens:

```text
USER_CONFIRMED
IMPORTED
CATALOG
TECHNOLOGY_PROFILE
PHYSICAL_PROFILE
DERIVED
CALCULATED
AI_PROPOSED
GENERIC_ESTIMATE
LEGACY
UNKNOWN
```

---

# 10. Provenance Validation

Beispiele:

```text
critical bitrate
source = UNKNOWN
→ REVIEW_REQUIRED
```

```text
AI_PROPOSED physical port
not user approved
→ PROPOSED
```

```text
manufacturer catalog value
→ CONFIRMED / CATALOG
```

---

# 11. V01 – Schema Validation

Prüft:

```text
required fields
data types
enum values
object structure
relationship schema
```

Beispiele:

```text
cycle_time = "fast"
→ INVALID_TYPE
```

```text
network.technology = null
→ REQUIRED_FIELD_MISSING
```

---

# 12. V02 – Unit Validation

Alle physikalischen und technischen Werte müssen eine definierte Unit besitzen.

Beispiele:

```text
bitrate
→ bit/s
```

```text
cycle_time
→ s / ms / µs
```

```text
temperature
→ °C / K
```

Kanonische Speicherung wird festgelegt.

---

# 13. Unit Mismatch

Beispiel:

```text
value = 19200
unit = Mbit/s
```

→

```text
UNIT_VALUE_MISMATCH
```

---

# 14. V03 – Semantic Validation

Prüft:

```text
Signal Semantic Type
Data Complexity
State vs Numeric
Command vs Measurement
Status vs Physical Value
```

Beispiel:

```text
OperatingState
semantic_type = PHYSICAL_SCALAR
```

→

```text
SEMANTIC_TYPE_MISMATCH
```

---

# 15. V04 – Completeness Validation

Prüft nicht nur Objektanzahl.

Beispiel Signal:

```text
name
semantic type
producer
consumer
unit
range
cycle
binding
```

Beispiel Route:

```text
source
destination
network path
interfaces
transport
```

---

# 16. Completeness Status

Beispiel:

```text
Signal exists
but has no producer
```

→

```text
ENGINEERING_OBJECT_INCOMPLETE
```

---

# 17. V05 – Provenance Validation

Kritische Werte benötigen nachvollziehbare Herkunft.

Beispiele:

```text
Technology
Bitrate
Port Capability
Physical Medium
Signal Range
Cycle Time
Safety-Relevant State
```

---

# 18. V06 – Technology Validation

TechnologyProfile ist Single Source of Truth.

Prüft:

```text
RateModel
parameter schema
units
limits
supported mechanisms
```

Beispiel:

```text
LIN
bitrate = 2_000_000 bit/s
```

→

```text
TECHNOLOGY_PARAMETER_OUT_OF_RANGE
BLOCKER
```

---

# 19. V07 – Physical Realization Validation

Prüft:

```text
PHY
medium
pair count
conductors
termination
topology
port capability
transceiver capability
duplex
propagation constraints
```

Beispiele:

```text
CAN
3 terminations
→ PHYSICAL_TERMINATION_INVALID
```

```text
100BASE-T1
4-pair physical profile
→ PHY_MEDIUM_MISMATCH
```

---

# 20. V08 – Relationship Validation

Engineering-Beziehungen prüfen.

Beispiel:

```text
Signal
→ Producer Function
→ Hardware Mapping
→ Interface
→ Network
→ Consumer Route
```

Fehlt eine Ebene:

```text
ENGINEERING_CHAIN_INCOMPLETE
```

---

# 21. V09 – Graph Invariant Validation

Globale Regeln im Engineering Graph.

Beispiele:

```text
Every Signal has exactly one authoritative producer.
```

```text
Every routed TransportUnit has valid source and destination.
```

```text
Every PhysicalPort belongs to exactly one HardwareNode.
```

```text
Every route traverses only accessible networks.
```

---

# 22. Graph Invariant Finding

Beispiel:

```text
Signal MotorRPM
Producer A
Producer B
```

→

```text
MULTIPLE_AUTHORITATIVE_PRODUCERS
```

---

# 23. V10 – Cross-Layer Consistency

Eine der wichtigsten Prüfungen.

Prüft Zusammenhänge über mehrere Modellschichten:

```text
Function
↓
Signal / DataObject
↓
Transport Unit
↓
Network
↓
Technology
↓
PHY
↓
Routing
↓
Timing
```

---

# 24. Cross-Layer Beispiel 1

```text
Camera Stream
+
CAN-FD
```

→ prüfen:

```text
Data Complexity
Payload Rate
Transport Capacity
Technology Suitability
```

Möglicher Befund:

```text
DATA_COMPLEXITY_TECHNOLOGY_MISMATCH
```

---

# 25. Cross-Layer Beispiel 2

```text
Cycle = 1 ms
+
LIN
+
large payload
```

→

```text
TIMING_INFEASIBLE
```

---

# 26. Cross-Layer Beispiel 3

```text
Function mapped to Controller A

Signal routed through Network B

Controller A has no physical access to Network B
```

→

```text
ROUTE_HARDWARE_ACCESS_MISMATCH
```

---

# 27. V11 – Plausibility Validation

Nicht jeder fachlich mögliche Wert ist plausibel.

Beispiel:

```text
Temperature sensor
range = -273.15 ... 10000 °C
```

Kann syntaktisch gültig sein.

Aber:

```text
VALID_BUT_IMPLAUSIBLE
```

---

# 28. Plausibility Profiles

Plausibilität kann abhängig sein von:

```text
Device Class
Technology
Physical Quantity
Industry Profile
Hardware Catalog
Function Type
```

---

# 29. V12 – Namespace / Uniqueness Validation

Prüft:

```text
LogicalNodeAddress
CAN Identifier
IP Address
MAC Address
Node ID
Station Name
Service ID
Topic Name
```

---

# 30. Namespace Scope

Mögliche Scopes:

```text
GLOBAL
PROJECT
NETWORK
SEGMENT
DEVICE
SERVICE
```

---

# 31. Identifier Collision

Beispiel:

```text
CAN Network A

Message 1:
ID = 0x120

Message 2:
ID = 0x120
```

wenn nicht explizit zulässig:

```text
IDENTIFIER_COLLISION
```

---

# 32. V13 – Derived Value Consistency

Abgeleitete Werte dürfen nicht unabhängig von ihren Quellen weiterleben.

Beispiele:

```text
Payload Length
Bus Load
Transmission Time
Latency
Gateway Load
```

---

# 33. Stale-Regel

Wenn:

```text
payload
cycle
bitrate
technology
route
physical realization
```

geändert werden:

```text
Capacity
Timing
Simulation Snapshot
Trace Baseline
```

werden:

```text
STALE
```

---

# 34. Derived Value Validation

Beispiel:

```text
stored_bus_load = 12 %

recalculated_bus_load = 48 %
```

→

```text
DERIVED_VALUE_MISMATCH
```

---

# 35. V14 – Routing Validation

Prüft:

```text
source reachable
destination reachable
technology transitions
gateway path
interface compatibility
network membership
address resolution
```

---

# 36. V15 – Capacity Validation

Capacity wird erst berechnet wenn:

```text
Technology valid
RateModel valid
Units valid
Physical realization valid
Transport valid
```

---

# 37. Capacity Input Gate

Nicht:

```text
invalid LIN rate
↓
calculate busload
```

Sondern:

```text
invalid LIN rate
↓
BLOCK
```

---

# 38. V16 – Timing Validation

Timing berücksichtigt:

```text
Queue Delay
Arbitration Delay
Serialization
PHY Delay
Propagation
Switch Delay
Gateway Delay
Processing Delay
```

---

# 39. V17 – Simulation Readiness

Simulation Preflight prüft mindestens:

```text
Model completeness
Technology validity
Physical validity
Routing validity
Capacity validity
Timing validity
No blocking findings
No stale critical calculations
Simulation configuration valid
Seed valid
Fault configuration valid
```

---

# 40. V18 – Trace Readiness

Vor Simulation prüfen:

```text
Source mapping
Destination mapping
Logical addresses
Transport unit bindings
Signal decode definitions
Timebase
Route references
```

damit der spätere Trace analysierbar ist.

---

# 41. PreflightResult

Struktur:

```text
PreflightResult
├── project_id
├── model_revision
├── status
├── blockers[]
├── errors[]
├── reviews[]
├── warnings[]
├── stale_items[]
├── validation_results[]
├── quality_metrics
└── readiness
```

---

# 42. Readiness

Beispiel:

```yaml
readiness:
  engineering_model: READY
  technology: READY
  physical: READY
  routing: READY
  capacity: READY
  timing: READY
  simulation: READY
  trace: READY
```

---

# 43. Preflight Blocking Rules

Simulation blockieren bei:

```text
invalid technology
invalid PHY
missing route
capacity invalid
timing invalid
critical unknown value
stale critical calculation
blocking finding
invalid signal encoding
unresolved identifier conflict
```

---

# 44. Warning Rules

Simulation darf ggf. weiterlaufen bei:

```text
non-critical plausibility warning
optional metadata missing
non-critical documentation gap
```

aber:

```text
READY_WITH_WARNINGS
```

---

# 45. Quality Metrics im Preflight

Nicht nur ein Quality Score.

Mindestens getrennt:

```text
Completeness
Consistency
Validity
Plausibility
Traceability
Provenance
Freshness
Technology Compliance
Physical Compliance
Simulation Readiness
Trace Readiness
```

---

# 46. Beispiel Quality Summary

```text
Completeness:          99.2 %
Consistency:         100.0 %
Validity:            100.0 %
Plausibility:         97.5 %
Traceability:        100.0 %
Provenance:           98.0 %
Freshness:           100.0 %
Technology:          100.0 %
Physical:            100.0 %
Simulation Ready:    100.0 %
```

---

# 47. Kein Durchschnitt darf Blocker verdecken

Beispiel:

```text
Overall Score = 99.8 %
```

aber:

```text
LIN = 2 Mbit/s
```

Dann:

```text
Preflight = BLOCKED
```

---

# 48. Critical Escape Rate

Neue Qualitätsmetrik:

```text
Critical Data Quality Escape Rate
```

Definition:

```text
critical invalid data reaching
calculation / simulation / trace
/
critical invalid data introduced
```

Ziel:

```text
0 %
```

---

# 49. Data Quality Escape

Beispiel:

```text
LIN 2 Mbit/s
```

wird von Validation nicht erkannt und erreicht:

```text
Capacity Engine
```

→

```text
DATA_QUALITY_ESCAPE
```

Dieser Fehler gilt selbst als Critical Finding.

---

# 50. Round-Trip Validation

Für Import/Export:

```text
Canonical Model
↓
Export
↓
Re-Import
↓
Semantic Diff
```

Prüfen:

```text
Technology unchanged
Units unchanged
Signals unchanged
Identifiers unchanged
Relationships unchanged
Routing unchanged
```

---

# 51. Round-Trip Findings

Beispiele:

```text
ROUNDTRIP_TECHNOLOGY_CHANGED
ROUNDTRIP_UNIT_CHANGED
ROUNDTRIP_SIGNAL_SEMANTICS_CHANGED
ROUNDTRIP_ROUTE_CHANGED
```

---

# 52. Property-Based Validation Tests

Zusätzlich zu festen Testfällen:

```text
generate many valid/invalid combinations
↓
validate invariants
```

Beispiele:

```text
LIN rates
CAN-FD payload sizes
CAN identifiers
Ethernet PHY profiles
RS-485 topology
Cycle times
Signal ranges
```

---

# 53. Mutation Testing

Gezielt Fehler injizieren.

Beispiele:

```text
19_200
→ 2_000_000
```

```text
CAN differential PHY
→ single wire
```

```text
CAN-FD TechnologyProfile
→ LIN profile
```

Validator muss Fehler erkennen.

---

# 54. Validation Coverage

Metrik:

```text
Validation Rule Coverage
```

Beispiel:

```text
defined technology constraints: 250
covered by automated tests: 248
```

Ziel:

```text
>= 99 %
```

kritische Regeln:

```text
100 %
```

---

# 55. Preflight Rule Registry

Einführung:

```text
ValidationRuleRegistry
```

Jede Rule:

```text
rule_id
name
category
scope
severity
applicability
validator
message
repair_hint
version
```

---

# 56. Rule Categories

Mindestens:

```text
SCHEMA
UNIT
SEMANTIC
COMPLETENESS
PROVENANCE
TECHNOLOGY
PHYSICAL
RELATIONSHIP
GRAPH
CROSS_LAYER
PLAUSIBILITY
NAMESPACE
DERIVED
ROUTING
CAPACITY
TIMING
SIMULATION
TRACE
```

---

# 57. Rules nicht im Frontend duplizieren

Frontend darf:

```text
instant input hints
```

geben.

Aber autoritative Validierung:

```text
Python Core
```

---

# 58. Engineering Agent Integration

Agent muss Preflight lesen können:

```text
Agent
↓
validation.run
↓
preflight.get_result
```

und:

```text
blockers analysieren
↓
Repair Plan
```

---

# 59. Agent darf Preflight nicht umgehen

Nicht:

```text
Preflight = BLOCKED
```

und trotzdem:

```text
Agent starts simulation
```

---

# 60. MCP-Schnittstellen

Empfohlen:

```text
validation.run
validation.get_result
validation.get_findings
validation.get_rule
validation.explain

preflight.run
preflight.get_result
preflight.get_blockers
preflight.get_readiness

quality.get_metrics
quality.get_provenance
quality.get_stale_items
```

---

# 61. Python Core Services

Empfohlen:

```text
ValidationEngine
ValidationRuleRegistry
PreflightService
SchemaValidator
UnitValidator
SemanticValidator
CompletenessValidator
ProvenanceValidator
TechnologyValidator
PhysicalValidator
RelationshipValidator
GraphInvariantValidator
CrossLayerValidator
PlausibilityValidator
NamespaceValidator
DerivedConsistencyValidator
SimulationReadinessValidator
TraceReadinessValidator
QualityMetricsService
```

---

# 62. Finding Integration

Validation Findings werden über den normalen Finding-Mechanismus verwaltet.

Beispiel:

```text
Finding
├── rule_id
├── object_refs
├── severity
├── evidence
├── root_cause
├── repair_hint
├── source_revision
└── status
```

---

# 63. Finding Repair Loop

Verbindlich:

```text
Validation Finding
↓
Root Cause
↓
Fix
↓
Re-Validation
↓
Preflight
↓
Regression
↓
Close
```

---

# 64. Keine reine Dokumentation

Nicht:

```text
Preflight detects 18 errors
→ report
→ stop
```

Sondern im Tool Checker / Repair Mode:

```text
detect
→ repair
→ validate
→ rerun
```

---

# 65. Preflight nach jeder relevanten Modelländerung

Änderungen an:

```text
Technology
Rate
Signal
Message
Route
Port
Interface
PHY
Topology
Hardware Mapping
```

setzen Preflight:

```text
STALE
```

---

# 66. Incremental Validation

Nicht jedes Mal das gesamte Modell vollständig neu prüfen.

Unterstütze:

```text
changed objects
↓
affected dependency graph
↓
incremental validation
```

Danach optional globaler Preflight.

---

# 67. Dependency Graph

Beispiel:

```text
LIN bitrate changed
↓
Network
↓
Transport Units
↓
Capacity
↓
Timing
↓
Simulation Snapshot
↓
Trace Baseline
```

---

# 68. Validation Cache

Nur verwenden wenn:

```text
same object revision
same rule version
same TechnologyProfile version
same PhysicalProfile version
```

sonst:

```text
invalidate cache
```

---

# 69. Validation Evidence

Jeder Validation Run speichert:

```text
run_id
project_revision
rule_versions
profile_versions
inputs
results
findings
timestamp
```

---

# 70. Regression Tests – Data Quality / Preflight

Mindestens:

```text
TC-DQ-001
missing required technology
→ BLOCKED

TC-DQ-002
LIN 2 Mbit/s
→ BLOCKED

TC-DQ-003
unknown critical bitrate
→ REVIEW_REQUIRED / BLOCKED

TC-DQ-004
duplicate CAN ID
→ BLOCKED

TC-DQ-005
signal without producer
→ BLOCKED

TC-DQ-006
camera stream over insufficient network
→ FAIL / REVIEW

TC-DQ-007
stale capacity after rate change
→ PRECHECK FAIL

TC-DQ-008
PHY mismatch
→ BLOCKED

TC-DQ-009
wrong derived busload
→ DERIVED_VALUE_MISMATCH

TC-DQ-010
valid model
→ READY
```

---

# 71. Regression Tests – Provenance

```text
TC-PROV-001
user confirmed value
→ CONFIRMED

TC-PROV-002
AI proposed critical value
→ PROPOSED

TC-PROV-003
critical unknown value
→ REVIEW_REQUIRED

TC-PROV-004
derived value
→ source dependencies available
```

---

# 72. Regression Tests – Graph

```text
TC-GRAPH-001
two authoritative signal producers
→ FAIL

TC-GRAPH-002
route uses inaccessible network
→ FAIL

TC-GRAPH-003
orphan PhysicalPort
→ FAIL

TC-GRAPH-004
valid source-to-consumer chain
→ PASS
```

---

# 73. Regression Tests – Staleness

```text
TC-STALE-001
bitrate changed
→ capacity stale

TC-STALE-002
route changed
→ timing stale

TC-STALE-003
PHY changed
→ simulation snapshot stale

TC-STALE-004
signal encoding changed
→ trace decode baseline stale
```

---

# 74. Tool Checker Integration

Tool Checker muss den Preflight nicht nur starten.

Er muss prüfen:

```text
Expected Findings
Actual Findings

Expected Blockers
Actual Blockers

Expected Readiness
Actual Readiness

Expected Stale Dependencies
Actual Stale Dependencies
```

---

# 75. NO EVIDENCE → NO PASS

Auch für Validation / Preflight:

```text
NO EVIDENCE
→ NO PASS
```

---

# 76. Quality Gate

Release-/Master-Test-Ziel:

```text
Mandatory Validation Rules = 100 % PASS
Critical Validation Rule Coverage = 100 %
P0 = 0
Blocking P1 = 0
Critical Data Quality Escape Rate = 0 %
Blocked Mandatory Checks = 0
Residual Non-Critical Failure Rate < 1 %
```

---

# 77. Preflight Quality Gate

Simulation Ready nur wenn:

```text
Schema = READY
Units = READY
Semantics = READY
Completeness = READY
Technology = READY
Physical = READY
Relationships = READY
Graph = READY
Cross-Layer = READY
Routing = READY
Capacity = READY
Timing = READY
Simulation = READY
Trace = READY
```

oder explizit nicht anwendbare Bereiche:

```text
NOT_APPLICABLE
```

---

# 78. Preflight UI

Kompakt:

```text
Preflight

READY
```

oder:

```text
Preflight

BLOCKED

3 Blocker
2 Reviews
5 Warnings
```

Details nur auf Wunsch.

---

# 79. Preflight Detailansicht

Beispiel:

```text
Technology       BLOCKED
Physical         READY
Routing          READY
Capacity         BLOCKED
Timing           BLOCKED
Simulation       BLOCKED
Trace            STALE
```

Root cause:

```text
LIN_1 bitrate = 2 Mbit/s
```

---

# 80. Validation darf Folgefehler gruppieren

Ein primärer Fehler:

```text
LIN bitrate invalid
```

kann verursachen:

```text
Capacity blocked
Timing blocked
Simulation blocked
```

Nicht vier unabhängige Root Causes erzeugen.

Sondern:

```text
Primary Finding
↓
Dependent Blockers
```

---

# 81. Root-Cause-aware Validation

Beispiel:

```text
TECHNOLOGY_PARAMETER_OUT_OF_RANGE
├── blocks CAPACITY
├── blocks TIMING
└── blocks SIMULATION
```

Das verbessert Finding-Qualität.

---

# 82. Codex-Arbeitsauftrag

```text
Integrate data quality directly into the existing Validation / Preflight architecture.

Do not build a parallel standalone data-quality application.

Validation must cover:

- schema,
- units,
- semantics,
- completeness,
- provenance,
- technology constraints,
- physical realization,
- relationships,
- graph invariants,
- cross-layer consistency,
- plausibility,
- namespace uniqueness,
- derived-value consistency,
- routing,
- capacity,
- timing,
- simulation readiness,
- trace readiness.

Use TechnologyProfile and PhysicalLayerProfile as authoritative sources.

Reject invalid technology or physical data before capacity, timing and simulation.

Unknown is preferable to an invented default.

Track provenance and status for critical engineering values.

Mark dependent calculations STALE whenever their source data changes.

Implement a structured PreflightResult with:
READY,
READY_WITH_WARNINGS,
REVIEW_REQUIRED,
BLOCKED,
STALE.

Do not allow BLOCKED, REVIEW_REQUIRED or STALE models to start a productive simulation.

Integrate all Validation Findings with the normal Finding/Repair lifecycle.

Do not stop after reporting findings in VERIFY_AND_REPAIR mode.

For confirmed defects:
- determine root cause,
- repair,
- revalidate,
- rerun preflight,
- rerun affected calculations,
- rerun regression tests,
- close only with evidence.

Add regression tests for:
- technology parameters,
- units,
- provenance,
- graph invariants,
- cross-layer consistency,
- physical realization,
- namespace collisions,
- stale dependencies,
- derived calculations,
- simulation readiness.

Target:
- Mandatory Validation Pass Rate = 100 %
- Critical Validation Rule Coverage = 100 %
- Critical Data Quality Escape Rate = 0 %
- P0 = 0
- Blocking P1 = 0
- Residual Non-Critical Failure Rate < 1 %
```

---

# 83. Definition of Done

Die Integration ist fertig, wenn:

1. Data Quality Bestandteil von Validation / Preflight ist.
2. keine parallele Data-Quality-Wahrheit entsteht.
3. Schema Validation integriert ist.
4. Unit Validation integriert ist.
5. Semantic Validation integriert ist.
6. Completeness Validation integriert ist.
7. Provenance Validation integriert ist.
8. Technology Validation integriert ist.
9. Physical Validation integriert ist.
10. Relationship Validation integriert ist.
11. Graph Invariants integriert sind.
12. Cross-Layer Validation integriert ist.
13. Plausibility Validation integriert ist.
14. Namespace Validation integriert ist.
15. Derived Value Consistency integriert ist.
16. Routing Validation eingebunden ist.
17. Capacity Validation nur valide Eingaben akzeptiert.
18. Timing Validation nur valide Eingaben akzeptiert.
19. Simulation Readiness integriert ist.
20. Trace Readiness integriert ist.
21. PreflightResult strukturiert ist.
22. READY/BLOCKED/STALE/REVIEW Status funktionieren.
23. Critical Unknowns den Preflight blockieren oder Review erfordern.
24. Technology-/PHY-Fehler Calculation und Simulation blockieren.
25. abhängige Ergebnisse automatisch STALE werden.
26. Validation Findings Root-Cause-Abhängigkeiten abbilden.
27. Round-Trip Validation vorgesehen ist.
28. Property-Based Tests vorgesehen sind.
29. Mutation Tests vorgesehen sind.
30. Critical Data Quality Escape Rate messbar ist.
31. Tool Checker Preflight-Erwartungen prüft.
32. Findings in Repair Loop überführt werden.
33. NO EVIDENCE → NO PASS gilt.
34. Mandatory Validation Pass Rate 100 % erreicht.
35. Critical Data Quality Escape Rate 0 % erreicht.

---

# 84. Leitregel

```text
DATA
↓
VALIDATION
↓
QUALITY
↓
TECHNOLOGY
↓
PHYSICAL
↓
CROSS-LAYER
↓
ROUTING
↓
CAPACITY
↓
TIMING
↓
PREFLIGHT
↓
SIMULATION
```

> **Datenqualität ist keine Zusatzfunktion. Sie ist eine Voraussetzung für einen erfolgreichen Validation-/Preflight-Status.**
