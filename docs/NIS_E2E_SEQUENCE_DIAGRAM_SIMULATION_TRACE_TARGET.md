# Network Intelligence Simulator (NIS)
## E2E Sequence Diagram – Simulation & Trace Analyse
## Gemeinsame Zieldefinition für Soll- und Ist-Kommunikation

---

# 1. Ziel

Der Network Intelligence Simulator soll Kommunikation nicht nur als statische Netzwerkstruktur darstellen.

Jede relevante Botschaft, jedes Signal und jedes DataObject soll als zeitlich nachvollziehbare **End-to-End-Transaktion** vom fachlichen Sender bis zum fachlichen Empfänger dargestellt werden können.

Davon sind **beide Sequenzdiagramme** betroffen:

```text
1. Simulation Sequence Diagram
   → erwartete / simulierte Kommunikation

2. Trace Analysis Sequence Diagram
   → tatsächlich beobachtete Kommunikation
```

Beide Diagramme verwenden dieselbe fachliche und technische Semantik.

Unterschied:

```text
Simulation
→ WAS SOLLTE / WÜRDE PASSIEREN?

Trace Analyse
→ WAS IST TATSÄCHLICH PASSIERT?
```

---

# 2. Zentrale Produktvision

```text
MODEL
↓
VALIDATE
↓
SIMULATE
↓
TRACE
↓
ANALYZE
↓
VERIFY
```

Der NIS soll jede Kommunikation beantworten können:

```text
Wer sendet?
Was wird gesendet?
Wann wird gesendet?
Wie wird es verpackt?
Über welches Interface?
Über welches Netz?
Über welche Technologie?
Über welche Gateways?
Mit welcher Verzögerung?
Wann erreicht es den Empfänger?
Wie alt sind die Daten?
Werden die Daten akzeptiert?
Werden sie verworfen?
Welche Safety-/Timing-Regel gilt?
```

---

# 3. Grundregel

Eine Nachricht ist nicht vollständig beschrieben durch:

```text
Sender
→ Message
→ Receiver
```

Sondern durch:

```text
Source Function
↓
Source Data
↓
Encoding
↓
Transport Unit
↓
Hardware Interface
↓
Physical Port
↓
Network
↓
Technology
↓
Route
↓
Gateway / Switch / Subnet
↓
Destination Interface
↓
Decode
↓
Receiver Acceptance
↓
Destination Function
```

---

# 4. E2ETransaction als gemeinsame Grundlage

Einführung einer gemeinsamen Entität:

```text
E2ETransaction
```

Diese verbindet Simulation und Trace Analyse.

Beispiel:

```text
E2ETransaction
├── transaction_id
├── source_function
├── source_hardware
├── destination_function
├── destination_hardware
├── data_object
├── source_timestamp
├── route_id
├── hops[]
├── destination_timestamp
├── receiver_accept_timestamp
├── latency
├── data_age
├── timing_contract
├── protection_status
├── receiver_status
├── requirement_status
└── findings[]
```

---

# 5. Simulation Sequence Diagram

Das Simulation Sequence Diagram zeigt den erwarteten bzw. simulierten Kommunikationsablauf.

Beispiel:

```text
Sensor        ECU A        Gateway        ECU B        Function B
  |             |             |             |              |
  | Measurement |             |             |              |
  |------------>|             |             |              |
  |             | CAN Frame   |             |              |
  |             |------------>|             |              |
  |             |             | Ethernet    |              |
  |             |             |------------>|              |
  |             |             |             | Decode       |
  |             |             |             |------------->|
  |             |             |             |              |
  |<---------------------- E2E = 18.4 ms ------------------>|
```

---

# 6. Trace Analysis Sequence Diagram

Das Trace Sequence Diagram verwendet dieselbe Struktur.

Es basiert jedoch auf tatsächlich beobachteten Trace Events.

Beispiel:

```text
Sensor        ECU A        Gateway        ECU B        Function B
  |             |             |             |              |
  |             | 12.003 ms   |             |              |
  |             |------------>|             |              |
  |             |             | 12.014 ms   |              |
  |             |             |------------>|              |
  |             |             |             | 12.021 ms    |
  |             |             |             |------------->|
  |             |             |             |              |
  |<---------------------- E2E = 21 ms -------------------->|
```

---

# 7. Beide Diagramme verwenden denselben Renderer

Nicht:

```text
Simulation Sequence Diagram
→ eigene Logik

Trace Sequence Diagram
→ zweite eigene Logik
```

Sondern:

```text
E2E Sequence Model
↓
Shared Sequence Renderer
```

Datenquelle:

```text
SimulationSequenceProvider
```

oder:

```text
TraceSequenceProvider
```

---

# 8. Shared Sequence Model

Empfohlen:

```text
SequenceDiagramModel
├── transaction_id
├── participants[]
├── lifelines[]
├── events[]
├── messages[]
├── hops[]
├── timing_annotations[]
├── requirement_overlays[]
├── fault_markers[]
└── receiver_actions[]
```

---

# 9. Teilnehmer im Sequenzdiagramm

Teilnehmer können sein:

```text
Sensor
Actuator
Function
Controller
ECU
PLC
Gateway
Switch
Edge Node
HPC
Network Interface
External Tester
```

Nicht jede Ebene muss gleichzeitig sichtbar sein.

---

# 10. Drei Detailstufen

## LEVEL 1 – Functional

```text
Function A
→ Function B
```

Ziel:

```text
fachliche Kommunikation
```

---

## LEVEL 2 – Communication

```text
ECU A
→ Gateway
→ ECU B
```

Ziel:

```text
technischer Kommunikationspfad
```

---

## LEVEL 3 – Technical

```text
Signal
→ Encode
→ Queue
→ Arbitration
→ Frame
→ Gateway Mapping
→ Queue
→ Frame
→ Decode
→ Receiver Acceptance
```

Ziel:

```text
vollständige technische Analyse
```

---

# 11. Detailstufe dynamisch umschaltbar

UI:

```text
Sequence Detail

○ Functional
○ Communication
○ Technical
```

Default:

```text
Communication
```

---

# 12. Eine sichtbare Botschaft besitzt technische Tiefe

Ein Pfeil im Diagramm kann intern enthalten:

```text
Message / Transport Unit
├── source_function
├── destination_function
├── source_hardware
├── destination_hardware
├── source_interface
├── destination_interface
├── network
├── technology
├── identifier
├── payload
├── signals
├── data_objects
├── route
├── timestamp
├── latency
├── data_age
├── sequence_counter
├── crc_status
├── freshness
└── receiver_action
```

---

# 13. Direkte Verbindung

Beispiel:

```text
Controller A
↓
CAN-FD
↓
Controller B
```

Sequence:

```text
Controller A                 Controller B
    |                             |
    |------ Message X ----------->|
    |                             |
    |<----- ACK / reaction -------|
```

Zusätzlich:

```text
E2E = 4.2 ms
```

---

# 14. Multi-Hop-Verbindung

Beispiel:

```text
Sensor ECU
↓
LIN
↓
Gateway
↓
CAN-FD
↓
Domain Controller
↓
Ethernet
↓
Central Compute
```

Sequence:

```text
Sensor ECU     Gateway      Domain Ctrl      Central Compute
    |             |              |                  |
    |-- LIN ----->|              |                  |
    |             |-- CAN-FD --->|                  |
    |             |              |-- Ethernet ----->|
    |             |              |                  |
```

---

# 15. Subnetze

Subnetze müssen sichtbar und nachvollziehbar bleiben.

Beispiel:

```text
Subnet A
↓
Gateway
↓
Subnet B
```

Das Sequenzdiagramm zeigt nicht nur:

```text
Sender
→ Receiver
```

sondern den Übergang:

```text
Sender
→ Subnet A
→ Gateway
→ Subnet B
→ Receiver
```

---

# 16. Gateway-Hops

Jeder Gateway-Hop besitzt:

```text
Ingress
Queue
Decode / Mapping
Routing Decision
Transformation
Re-encode
Egress
```

Je nach Gateway-Typ.

---

# 17. Gateway-Typen

Mindestens:

```text
FRAME_GATEWAY
PDU_GATEWAY
SIGNAL_GATEWAY
APPLICATION_GATEWAY
ROUTER
SWITCH
BRIDGE
```

---

# 18. Technologie-Wechsel

Beispiel:

```text
LIN
↓
Gateway
↓
CAN-FD
```

oder:

```text
CAN-FD
↓
Gateway
↓
Ethernet / SOME-IP
```

Das Sequenzdiagramm muss diesen Wechsel sichtbar machen.

---

# 19. Transport-Transformation

Beispiel:

```text
Signal A
↓
LIN Frame 0x12
↓
Gateway
↓
CAN-FD Message 0x321
```

Beide Frames gehören zur selben:

```text
E2ETransaction
```

---

# 20. Correlation ID

Simulation besitzt intern:

```text
transaction_id
```

Beispiel:

```text
E2E-4711
```

Diese ID verbindet:

```text
Signal
Message
Frame
Gateway Mapping
Receiver Signal
```

---

# 21. Trace Correlation ohne interne ID

Bei realen Trace-Daten ist die interne ID möglicherweise nicht vorhanden.

Daher:

```text
TraceCorrelationEngine
```

verwendet:

```text
timestamps
source
destination
signal identity
payload
data ID
sequence counter
gateway mapping
route
technology
```

---

# 22. Sequenzdiagramm und E2E Timing

Jede E2ETransaction kann eine Timing-Klammer besitzen:

```text
|<---------------- E2E 18.4 ms ---------------->|
```

---

# 23. Timing Breakdown

Optional:

```text
Source Processing       2 ms
Queue                   3 ms
CAN Arbitration         4 ms
CAN Serialization       2 ms
Gateway Processing      3 ms
Ethernet                1 ms
Decode                  2 ms
Receiver Acceptance     1 ms
--------------------------------
E2E                    18 ms
```

---

# 24. Timing Events im Diagramm

Technical Mode kann anzeigen:

```text
QUEUE ENTER
ARBITRATION START
TX START
TX END
RX
GATEWAY PROCESSING
DECODE
ACCEPT
```

---

# 25. Expected vs Observed

Zentrale Vergleichsfunktion:

```text
EXPECTED
vs
OBSERVED
```

---

# 26. Beispiel Route

Expected:

```text
Sensor ECU
→ LIN
→ Gateway
→ CAN-FD
→ Controller
```

Observed:

```text
Sensor ECU
→ LIN
→ Gateway
→ CAN-FD
→ Controller
```

→

```text
ROUTE MATCH
```

---

# 27. Route Mismatch

Expected:

```text
A
→ GW1
→ B
```

Observed:

```text
A
→ GW2
→ B
```

Finding:

```text
TRACE_ROUTE_MISMATCH
```

---

# 28. Expected Timing vs Observed Timing

Requirement:

```text
max E2E = 20 ms
```

Simulation:

```text
Expected = 14 ms
```

Trace:

```text
Observed = 31 ms
```

Diagram:

```text
Expected: 14 ms
Observed: 31 ms
Limit:    20 ms

Status: FAIL
```

---

# 29. Receiver Acceptance

Das Diagramm endet nicht beim physikalischen Empfang.

Ziel:

```text
Receiver Application Acceptance
```

Beispiel:

```text
Frame arrives
↓
Decode
↓
Freshness Check
↓
Sequence Check
↓
Data Age Check
↓
Plausibility
↓
ACCEPT / REJECT
```

---

# 30. Receiver Action im Sequenzdiagramm

Beispiel:

```text
Receiver
  |
  | RECEIVE
  | DECODE
  | DEADLINE CHECK
  |
  X REJECT
```

oder:

```text
✓ ACCEPT
```

---

# 31. Late Message

Beispiel:

```text
Allowed:
20 ms

Observed:
35 ms
```

Sequence:

```text
Sender        Gateway        Receiver
  |              |              |
  |------------->|              |
  |              |------------->|
  |              |              |
  |              |              X LATE / REJECT
```

Finding:

```text
E2E_DEADLINE_VIOLATION
```

---

# 32. Stale Data

Noch kritischer:

```text
Observed:
35 ms

Receiver:
ACCEPT
```

Finding:

```text
STALE_OR_LATE_DATA_ACCEPTED
```

---

# 33. Sequence Counter

Diagramm kann anzeigen:

```text
Message #41
Message #42
Message #44
```

Finding:

```text
SEQUENCE_GAP
```

---

# 34. Duplicate

```text
Message #44
Message #44
```

Finding:

```text
DUPLICATE_MESSAGE
```

---

# 35. Integrity Failure

Beispiel:

```text
CRC invalid
```

Sequence:

```text
Sender
→ Frame
→ Receiver
→ CRC Check
→ REJECT
```

---

# 36. Internal vs External Monitoring

Beide Perspektiven darstellen:

```text
System Internal:
Receiver detected timeout.

External Trace:
Deadline miss confirmed.
```

oder:

```text
System Internal:
ACCEPT

External Trace:
STALE
```

→ Finding.

---

# 37. Safety Overlay

Optional:

```text
Safety Requirement:
TSR-4711

Max E2E:
20 ms

Criticality:
ASIL D
```

Nur anzeigen, wenn aus Safety Engineering verknüpft.

Nicht selbst erfinden.

---

# 38. Requirement Overlay

Sequenzdiagramm:

```text
Allowed E2E:
20 ms

Measured:
18.4 ms

Margin:
1.6 ms

PASS
```

---

# 39. Negative Margin

```text
Allowed:
20 ms

Measured:
31 ms

Margin:
-11 ms

FAIL
```

---

# 40. Data Age Overlay

Zusätzlich:

```text
Data Age:
34 ms

Max Age:
25 ms

STALE
```

---

# 41. Jitter

Für wiederkehrende Kommunikation:

```text
Message cycle:
10 ms

Observed E2E:
8 / 9 / 9 / 18 / 8 ms
```

Diagramm kann Ausreißer markieren.

---

# 42. Timeline Selection

Sequenzdiagramm und andere Trace Views verwenden dieselbe Zeitbasis.

```text
Botschaften
Sequenz
Signale
Trace
E2E Timing
```

---

# 43. Synchronisierte Auswahl

Klick auf:

```text
Message 4711
```

im Sequenzdiagramm:

```text
Botschaften
→ select same event

Signale
→ move playhead

Trace
→ open exact event

E2E Timing
→ show transaction
```

---

# 44. Umgekehrte Synchronisation

Klick in:

```text
Signal View
```

auf einen Zeitpunkt:

```text
Sequence Diagram
→ corresponding E2ETransaction
```

---

# 45. Simulation ↔ Trace Vergleich

Ein spezieller Vergleichsmodus:

```text
Simulation
vs
Trace
```

---

# 46. Vergleichsmatrix

Beispiel:

```text
Route:
Expected = A → GW1 → B
Observed = A → GW1 → B
PASS

E2E:
Expected = 14 ms
Observed = 31 ms
FAIL

Receiver:
Expected = REJECT
Observed = ACCEPT
FAIL
```

---

# 47. Golden Trace

Golden Trace kann als Referenz dienen.

```text
Golden Sequence
vs
Current Sequence
```

---

# 48. First Divergence

Beispiel:

```text
Source transmission:
MATCH

Gateway ingress:
MATCH

Gateway queue:
DIVERGENCE

Gateway egress:
+14 ms
```

Das Sequenzdiagramm markiert:

```text
FIRST DIVERGENCE
```

---

# 49. Root Cause

Beispiel:

```text
Camera Burst
↓
Gateway Queue
↓
Forwarding Delay
↓
Message arrives late
↓
Receiver rejects
```

Im Diagramm markierbar.

---

# 50. Findings aus dem Sequenzdiagramm

Mögliche Findings:

```text
E2E_DEADLINE_VIOLATION
TRACE_ROUTE_MISMATCH
GATEWAY_DELAY_EXCEEDED
QUEUE_DELAY_EXCEEDED
STALE_DATA
STALE_DATA_ACCEPTED
DUPLICATE_MESSAGE
SEQUENCE_GAP
MESSAGE_LOSS
CRC_ERROR
PROTECTION_FAILURE
RECEIVER_POLICY_VIOLATION
CLOCK_SYNC_ERROR
```

---

# 51. Sequence Filter

Mindestens:

```text
Source
Destination
Function
Hardware
Network
Technology
Message
Signal
DataObject
Route
Gateway
Finding
Timing Status
Safety Requirement
```

---

# 52. Transaktionsfilter

Beispiel:

```text
Show only:
PressureCommand
```

Ergebnis:

```text
alle E2E-Transaktionen dieses Signals
```

---

# 53. Grouping

Mögliche Gruppierung:

```text
by Function
by Hardware
by Network
by Technology
by Transaction
by Finding
```

---

# 54. High-Level View

Bei vielen Events:

```text
Function A
→ Function B
```

mit:

```text
1,420 transactions
p99 E2E = 18 ms
3 deadline misses
```

---

# 55. Drill-Down

Klick:

```text
3 deadline misses
```

→ konkrete Transaktionen.

---

# 56. Simulation Sequence Source

Datenquelle:

```text
Simulation Event Stream
+
Universal Trace
+
Routing
+
E2ETransaction
```

---

# 57. Trace Sequence Source

Datenquelle:

```text
Imported / Captured Trace
+
Trace Decoder
+
Correlation Engine
+
Routing Model
+
E2ETransaction Reconstruction
```

---

# 58. Shared Sequence Service

Empfohlen:

```text
SequenceDiagramService
```

Methoden:

```text
build_from_simulation()
build_from_trace()
build_comparison()
get_transaction()
get_timing_breakdown()
get_route()
get_findings()
```

---

# 59. E2ESequenceBuilder

Intern:

```text
E2ESequenceBuilder
├── ParticipantResolver
├── RouteResolver
├── HopResolver
├── EventCorrelator
├── TimingResolver
├── ReceiverActionResolver
└── RequirementOverlayResolver
```

---

# 60. ParticipantResolver

Bestimmt:

```text
welche Teilnehmer
```

auf der gewählten Detailstufe angezeigt werden.

---

# 61. RouteResolver

Verwendet:

```text
Canonical Routing
```

für Simulation.

Für Trace:

```text
Observed Route
```

plus Vergleich mit Canonical Routing.

---

# 62. HopResolver

Ein Hop ist:

```text
source interface
→ medium/network
→ destination interface
```

oder:

```text
gateway ingress
→ gateway egress
```

---

# 63. EventCorrelator

Verbindet:

```text
Signal
Transport Unit
Network Event
Gateway Event
Receiver Event
```

zu einer E2ETransaction.

---

# 64. TimingResolver

Berechnet:

```text
per-hop timing
total E2E
data age
margin
jitter context
```

---

# 65. ReceiverActionResolver

Bestimmt:

```text
ACCEPT
REJECT
DISCARD
FALLBACK
SAFE_STATE
```

aus Simulation oder Trace Evidence.

---

# 66. RequirementOverlayResolver

Lädt:

```text
Timing Contract
Safety Requirement
Max Age
Deadline
Receiver Policy
```

---

# 67. Datenmodell – SequenceParticipant

```text
SequenceParticipant
├── id
├── type
├── object_ref
├── label
├── technology_context
└── detail_level
```

---

# 68. Datenmodell – SequenceEvent

```text
SequenceEvent
├── id
├── transaction_id
├── timestamp
├── participant
├── event_type
├── object_ref
├── route_ref
├── hop_ref
├── timing
├── status
└── evidence_ref
```

---

# 69. Event Types

Mindestens:

```text
DATA_GENERATED
ENCODE
QUEUE_ENTER
QUEUE_EXIT
ARBITRATION_START
ARBITRATION_END
TX_START
TX_END
RX_START
RX_END
GATEWAY_INGRESS
GATEWAY_PROCESS
GATEWAY_EGRESS
DECODE
VALIDATE
ACCEPT
REJECT
TIMEOUT
FAULT
```

---

# 70. Datenmodell – SequenceMessage

```text
SequenceMessage
├── transaction_id
├── source_participant
├── destination_participant
├── label
├── transport_unit
├── technology
├── network
├── timestamp_start
├── timestamp_end
├── delay
├── status
└── finding_refs[]
```

---

# 71. Diagrammstatus

Mögliche Status:

```text
NORMAL
WARNING
LATE
STALE
LOST
DUPLICATE
CORRUPT
REJECTED
FAULT
UNKNOWN
```

---

# 72. Keine Farbe als alleinige Information

Status zusätzlich als:

```text
Text
Icon
Marker
```

anzeigen.

---

# 73. Sequence Diagram Performance

Große Traces können Millionen Events besitzen.

Nicht:

```text
render every event
```

Sondern:

```text
time window
transaction filter
aggregation
virtualization
progressive drill-down
```

---

# 74. Default Window

Trace Sequence lädt zunächst einen relevanten:

```text
time window
```

statt die gesamte Session.

---

# 75. Transaction Aggregation

Beispiel:

```text
1,000 identische erfolgreiche Zyklen
```

können aggregiert werden:

```text
PressureCommand
1000 transactions
995 PASS
5 FAIL
```

---

# 76. Failure First

Optional:

```text
Show anomalies only
```

für Trace Analyse.

---

# 77. Simulation Interaktion

Im Simulator:

```text
Select Function / Message
↓
Run Simulation
↓
Open Sequence
↓
Follow E2E
```

---

# 78. Trace Interaktion

In Trace Analyse:

```text
Select Trace Event
↓
Resolve Transaction
↓
Open Sequence
↓
Follow Source → Destination
```

---

# 79. Deep Links

Vom Sequenzdiagramm:

```text
Function
Hardware
Interface
Network
Route
Message
Signal
Finding
Safety Requirement
```

öffnen können.

Deep Link ist Navigation.

Nicht Ersatz für Analyse.

---

# 80. Validation / Preflight

Preflight muss sicherstellen:

```text
Source mapping exists
Destination mapping exists
Route exists
Transport binding exists
Trace decode definition exists
Timing contract valid
Clock model valid
```

damit Sequence/E2E später auswertbar ist.

---

# 81. Trace Readiness

Neuer Teil des Preflights:

```text
Trace Correlation Ready
```

prüft:

```text
source identity
destination identity
message identity
signal binding
gateway mapping
timebase
route references
```

---

# 82. Sequence Readiness

Zusätzlich:

```text
Sequence Visualization Ready
```

---

# 83. Engineering Agent

Agent kann Fragen beantworten:

```text
"Zeige mir, wie PressureCommand
vom Sensor bis zum Controller gelangt."
```

Agent:

```text
resolve E2ETransaction
↓
open sequence
↓
highlight route
```

---

# 84. Engineering Agent Timing-Frage

```text
"Warum kam PressureCommand zu spät?"
```

Agent:

```text
Sequence
+
Timing Breakdown
+
Trace
+
Root Cause
```

analysieren.

---

# 85. Beispiel Agent-Ergebnis

```text
PressureCommand

Allowed:
20 ms

Observed:
31 ms

Primary delay:
Gateway queue = 14 ms

Receiver action:
REJECT

Finding:
E2E_DEADLINE_VIOLATION
```

---

# 86. Tool Checker

Tool Checker muss beide Sequenzdiagramme prüfen.

---

# 87. Simulation Sequence Tests

Mindestens:

```text
TC-SEQ-SIM-001
direct connection

TC-SEQ-SIM-002
gateway connection

TC-SEQ-SIM-003
multi-network route

TC-SEQ-SIM-004
technology conversion

TC-SEQ-SIM-005
receiver acceptance

TC-SEQ-SIM-006
late message

TC-SEQ-SIM-007
message loss

TC-SEQ-SIM-008
sequence gap

TC-SEQ-SIM-009
safety timing overlay

TC-SEQ-SIM-010
E2E timing breakdown
```

---

# 88. Trace Sequence Tests

```text
TC-SEQ-TRACE-001
reconstruct direct route

TC-SEQ-TRACE-002
reconstruct gateway route

TC-SEQ-TRACE-003
correlate technology conversion

TC-SEQ-TRACE-004
detect deadline violation

TC-SEQ-TRACE-005
detect stale accepted data

TC-SEQ-TRACE-006
detect route mismatch

TC-SEQ-TRACE-007
Golden Trace comparison

TC-SEQ-TRACE-008
First Divergence

TC-SEQ-TRACE-009
Root Cause overlay

TC-SEQ-TRACE-010
cross-view synchronization
```

---

# 89. Comparison Tests

```text
TC-SEQ-CMP-001
Simulation route == Trace route
→ PASS

TC-SEQ-CMP-002
Simulation timing != Trace timing
→ deviation

TC-SEQ-CMP-003
Expected receiver REJECT
Observed ACCEPT
→ FAIL

TC-SEQ-CMP-004
Expected gateway GW1
Observed GW2
→ FAIL
```

---

# 90. Browser Tests

Browser Skill muss real prüfen:

```text
open Simulation Sequence
select transaction
change detail level
open technical detail
open Trace Sequence
select same transaction
compare timing
open finding
open root cause
```

---

# 91. Evidence

Speichern:

```text
sequence-simulation.json
sequence-trace.json
e2e-transaction.json
timing-breakdown.json
route-comparison.json
receiver-action.json
findings.json
screenshots/
```

---

# 92. Shared Renderer Rule

Verbindlich:

```text
ONE SEQUENCE MODEL
→ TWO DATA SOURCES
→ ONE RENDERING CONCEPT
```

Nicht zwei inkonsistente Diagrammimplementierungen.

---

# 93. UI-Konsistenz

Simulation und Trace Analyse verwenden dieselben:

```text
Participant Labels
Event Types
Timing Markers
Finding Symbols
Status Begriffe
Detail Levels
```

---

# 94. Unterschiedliche Kennzeichnung der Datenquelle

Simulation:

```text
SOURCE: SIMULATION
```

Trace:

```text
SOURCE: OBSERVED TRACE
```

Comparison:

```text
SOURCE: SIMULATION vs TRACE
```

---

# 95. Zielbild beider Diagramme

```text
                  SAME E2E MODEL
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
       SIMULATION            TRACE ANALYSIS
       "expected"              "observed"
             │                   │
             └─────────┬─────────┘
                       ▼
                    COMPARE
                       │
                       ▼
                ROOT CAUSE
                       │
                       ▼
                   FINDING
```

---

# 96. Produktziel

NIS soll nicht nur beantworten:

```text
"Welche Teilnehmer sind verbunden?"
```

sondern:

```text
"Wie gelangt diese konkrete Information
vom fachlichen Sender zum fachlichen Empfänger,
wie lange dauert jeder Teil des Pfades
und was macht der Empfänger damit?"
```

---

# 97. Abgrenzung Netzwerkdiagramm vs Sequenzdiagramm

Netzwerkdiagramm:

```text
zeigt Struktur
```

Sequenzdiagramm:

```text
zeigt Kommunikation über Zeit
```

Beide referenzieren dieselben Core-Objekte.

---

# 98. Abgrenzung Routingdiagramm vs Sequenzdiagramm

Routingdiagramm:

```text
zeigt den möglichen / gewählten Pfad
```

Sequenzdiagramm:

```text
zeigt konkrete Transaktionen auf diesem Pfad
```

---

# 99. Sequenzdiagramm als zentrale Verifikationssicht

Das Sequenzdiagramm wird damit eine zentrale Sicht für:

```text
Communication Engineering
Timing Analysis
Simulation
Trace Analysis
Functional Safety
Root Cause Analysis
Validation
```

---

# 100. Codex-Arbeitsauftrag

```text
Unify the Simulation Sequence Diagram and the Trace Analysis Sequence Diagram around one shared E2E transaction model.

Do not maintain two independent sequence semantics.

Create:
- E2ETransaction
- SequenceDiagramModel
- SequenceParticipant
- SequenceEvent
- SequenceMessage
- E2ESequenceBuilder
- SequenceDiagramService
- SimulationSequenceProvider
- TraceSequenceProvider
- TraceCorrelationEngine

Both diagrams must support:
- direct communication,
- multi-hop communication,
- gateways,
- switches,
- subnets,
- multiple technologies,
- technology conversion,
- signals,
- DataObjects,
- Transport Units,
- per-hop timing,
- total E2E timing,
- data age,
- jitter,
- timing margins,
- deadline violations,
- sequence errors,
- duplicates,
- integrity errors,
- receiver acceptance/rejection,
- safety requirements,
- findings,
- root cause.

Provide three detail levels:
1. Functional
2. Communication
3. Technical

Simulation Sequence must represent expected/simulated behavior.

Trace Sequence must represent observed/reconstructed behavior.

Provide comparison:
EXPECTED
vs
OBSERVED
vs
RECEIVER REACTION.

Synchronize Sequence with:
- Messages,
- Signals,
- Trace,
- E2E Timing.

Use the same timebase and selection context.

Use the shared Sequence model for visualization.
Do not implement duplicate business logic in the frontend.

Add Tool Checker tests for:
- direct route,
- gateway route,
- multi-network route,
- technology conversion,
- receiver acceptance,
- deadline violation,
- stale data,
- route mismatch,
- Golden Trace comparison,
- First Divergence,
- Root Cause,
- cross-view synchronization.

Store evidence for every failed E2E transaction.
```

---

# 101. Definition of Done

Die Zieldefinition ist umgesetzt, wenn:

1. Simulation Sequence Diagram existiert.
2. Trace Sequence Diagram existiert.
3. beide dasselbe Sequence Model verwenden.
4. beide E2ETransaction verwenden.
5. direkte Kommunikation darstellbar ist.
6. Multi-Hop-Kommunikation darstellbar ist.
7. Gateways sichtbar sind.
8. Subnetzübergänge sichtbar sind.
9. Technologie-Wechsel sichtbar sind.
10. Signals/DataObjects korrelierbar sind.
11. Transport Units sichtbar sind.
12. Route referenziert wird.
13. Per-Hop-Zeiten verfügbar sind.
14. Gesamt-E2E verfügbar ist.
15. Data Age verfügbar ist.
16. Jitter verfügbar ist.
17. Timing Margin verfügbar ist.
18. Receiver Acceptance sichtbar ist.
19. Receiver Rejection sichtbar ist.
20. Late Messages sichtbar sind.
21. Stale Data sichtbar ist.
22. Sequence Gaps sichtbar sind.
23. Duplicates sichtbar sind.
24. Integrity Errors sichtbar sind.
25. Safety Requirements überlagerbar sind.
26. Simulation vs Trace vergleichbar ist.
27. Expected vs Observed Route vergleichbar ist.
28. Expected vs Observed Timing vergleichbar ist.
29. Expected vs Observed Receiver Reaction vergleichbar ist.
30. Golden Trace unterstützt wird.
31. First Divergence unterstützt wird.
32. Root Cause markierbar ist.
33. Findings erzeugt werden können.
34. Botschaften/Sequenz/Signale/Trace synchronisiert sind.
35. drei Detailstufen existieren.
36. große Traces aggregierbar sind.
37. Browser Skill beide Diagramme testen kann.
38. Tool Checker Regressionstests existieren.
39. UI keine doppelte Fachlogik enthält.
40. Sequence Diagram als zentrale E2E-Verifikationssicht funktioniert.

---

# 102. Leitregel

```text
SIMULATION
→ EXPECTED E2E TRANSACTION

TRACE ANALYSIS
→ OBSERVED E2E TRANSACTION
```

Beide:

```text
SOURCE
↓
MESSAGE / DATA
↓
ROUTE
↓
GATEWAYS
↓
TIMING
↓
DESTINATION
↓
RECEIVER ACTION
```

und anschließend:

```text
EXPECTED
vs
OBSERVED
vs
SYSTEM REACTION
```

> **Der NIS soll nicht nur darstellen, dass zwei Teilnehmer miteinander verbunden sind. Er soll sichtbar und messbar machen, wie eine konkrete Botschaft vom Sender bis zum Empfänger gelangt, welche technischen Stationen sie durchläuft, wie lange jeder Abschnitt dauert und ob der Empfänger die Information fachlich korrekt und rechtzeitig verarbeitet.**
