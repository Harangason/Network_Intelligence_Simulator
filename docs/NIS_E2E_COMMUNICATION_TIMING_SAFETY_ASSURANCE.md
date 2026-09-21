# Network Intelligence Simulator (NIS)
## E2E Communication Timing & Safety Assurance
## End-to-End-Laufzeit, Datenalter, Kommunikationssicherheit, FuSi/HARA und industrieweite Safety-Profile

---

# 1. Ziel

Der NIS benötigt eine durchgängige Funktion zur Bewertung der Kommunikation von einem fachlichen Sender bis zum fachlichen Empfänger.

Die Funktion muss sowohl im:

```text
Simulator
```

als auch in:

```text
Trace Analyse
```

verfügbar sein.

Sie misst und bewertet nicht nur:

```text
"Wie lange braucht eine Nachricht von A nach B?"
```

sondern:

```text
Wann wurden die Daten fachlich erzeugt?
Wann wurden sie gesendet?
Welche Netze / Gateways wurden durchlaufen?
Wann kamen sie physikalisch an?
Wann wurden sie dekodiert?
Wann wurden sie der Empfängerfunktion bereitgestellt?
Waren sie zu diesem Zeitpunkt noch gültig?
Wurden sie akzeptiert, verworfen oder als fehlerhaft bewertet?
```

Zentrale Funktion:

```text
E2E Communication Timing & Safety Assurance
```

---

# 2. Zielbild

```text
Source Function
↓
Source Data / Signal
↓
Encode
↓
Sender Queue
↓
Transport Unit
↓
Source Interface
↓
Network / Bus
↓
Gateway 1
↓
Network / Bus
↓
Gateway n
↓
Destination Interface
↓
Decode
↓
Receiver Acceptance
↓
Destination Function
```

Über die gesamte Kette werden Zeit, Datenalter, Integrität und Kommunikationsstatus verfolgt.

---

# 3. Direkte Verbindung

Beispiel:

```text
Controller A
↓
CAN-FD
↓
Controller B
```

E2E-Messung:

```text
t_source_release
↓
t_tx_start
↓
t_tx_end
↓
t_rx_start
↓
t_rx_end
↓
t_decode
↓
t_receiver_accept
```

---

# 4. Verbindung über Gateway

Beispiel:

```text
Sensor Controller
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

E2E muss über alle Hops messen.

```text
Source
↓
LIN serialization
↓
Gateway ingress
↓
Gateway queue
↓
Gateway processing
↓
Gateway egress
↓
CAN arbitration
↓
CAN transmission
↓
next gateway / switch
↓
Ethernet transmission
↓
Receiver
```

---

# 5. Definition der End-to-End-Zeit

Primäre fachliche E2E-Latenz:

```text
T_E2E =
t_receiver_accept
-
t_source_release
```

Diese Metrik beschreibt:

> Zeit zwischen fachlicher Erzeugung/Freigabe der Information beim Sender und fachlicher Akzeptanz beim Empfänger.

---

# 6. Zusätzliche Zeitmetriken

Nicht nur eine einzelne E2E-Zahl speichern.

Mindestens:

```text
T_application_source
T_encode
T_source_queue
T_arbitration
T_serialization
T_phy
T_propagation
T_gateway_queue
T_gateway_processing
T_switch
T_destination_queue
T_decode
T_receiver_acceptance
```

Gesamt:

```text
T_E2E =
T_source_processing
+ T_queue
+ T_arbitration
+ T_serialization
+ T_phy
+ T_propagation
+ T_gateway
+ T_switch
+ T_decode
+ T_receiver_acceptance
```

Nicht jede Technologie besitzt jeden Term.

---

# 7. Zeitpunkte pro Hop

Ein `E2EHopTiming` enthält mindestens:

```text
hop_id
source_node
destination_node
technology
network
transport_unit

t_ingress
t_queue_enter
t_queue_exit
t_tx_start
t_tx_end
t_rx_start
t_rx_end
t_processing_start
t_processing_end

queue_delay
arbitration_delay
serialization_delay
propagation_delay
processing_delay
```

---

# 8. Datenalter

Latenz allein reicht nicht.

Ein Empfänger interessiert sich häufig für:

```text
Age of Data
```

Definition:

```text
DataAge =
t_current
-
t_data_generation
```

Beispiel:

```text
Sensor measurement generated:
10.000 s

Receiver consumes value:
10.085 s

Data Age:
85 ms
```

---

# 9. Kommunikationsvertrag

Ein Signal / DataObject kann einen:

```text
CommunicationTimingContract
```

besitzen.

Beispiel:

```yaml
cycle_time_ms: 10
max_e2e_latency_ms: 20
max_data_age_ms: 30
max_jitter_ms: 5
timeout_ms: 40
allowed_sequence_gap: 1
late_data_policy: REJECT
stale_data_policy: FALLBACK
```

---

# 10. ReceiverAcceptancePolicy

Der Empfänger benötigt eine definierte Policy.

```text
ReceiverAcceptancePolicy
├── max_latency
├── max_age
├── timeout
├── jitter_tolerance
├── sequence_policy
├── duplicate_policy
├── freshness_policy
├── crc_policy
├── data_id_policy
├── plausibility_policy
└── fallback_action
```

---

# 11. Beispiel: Nachricht kommt zu spät

Sender:

```text
t_generation = 12.000 s
```

Empfänger erwartet:

```text
max_e2e_latency = 20 ms
```

Tatsächlich:

```text
t_receiver_accept = 12.035 s
```

Damit:

```text
E2E = 35 ms
```

Ergebnis:

```text
DEADLINE_MISSED
```

---

# 12. Mögliche Empfängerreaktionen

Je nach Requirement:

```text
ACCEPT
ACCEPT_WITH_WARNING
REJECT
DISCARD
USE_LAST_VALID_VALUE
USE_DEFAULT_VALUE
DEGRADED_MODE
SAFE_STATE
REQUEST_RETRANSMISSION
RAISE_DIAGNOSTIC
```

---

# 13. Gefährlicher Sonderfall

Besonders kritisch:

```text
Message arrives late
↓
Receiver does not detect age
↓
Old value is interpreted as current
```

Beispiel:

```text
old brake request
old steering command
old pressure value
old position
```

Das ist nicht nur:

```text
Timing Violation
```

sondern kann sein:

```text
STALE_DATA_ACCEPTED
```

mit höherer Safety-Relevanz.

---

# 14. Kommunikationsfehlermodell

Mindestens folgende Failure Modes modellieren:

```text
LOSS
OMISSION
DELAY
EXCESSIVE_LATENCY
EARLY_ARRIVAL
JITTER
REPETITION
DUPLICATION
WRONG_SEQUENCE
SEQUENCE_GAP
CORRUPTION
MASQUERADING
WRONG_SENDER
WRONG_RECEIVER
WRONG_ROUTE
INSERTION
STALE_DATA
FROZEN_DATA
TIMEOUT
QUEUE_OVERFLOW
BUFFER_OVERFLOW
DECODE_ERROR
ENCODING_MISMATCH
UNIT_MISMATCH
SCALING_MISMATCH
ENDIANNESS_MISMATCH
DATA_ID_MISMATCH
CLOCK_SYNC_ERROR
```

---

# 15. Interne Kommunikationsüberwachung

Mechanismen im System selbst:

```text
CRC / E2E CRC
Sequence Counter
Alive Counter
Data ID
Timestamp
Freshness Counter
Timeout Monitor
Deadline Monitor
Watchdog
Heartbeat
Plausibility Check
Range Check
Rate-of-Change Check
Redundant Information
Redundant Channel
Source Authentication / Security Mechanism
```

---

# 16. Externe Bewertung durch Trace Analyse

Die Trace Analyse arbeitet als externer Beobachter.

Sie bewertet:

```text
Observed Sender Time
Observed Receiver Time
Observed Hop Times
Observed Queueing
Observed Arbitration
Observed Gateway Delay
Observed Data Age
Observed Sequence
Observed Loss
Observed Deadline
Observed Receiver Reaction
```

---

# 17. Zwei unabhängige Perspektiven

## Systeminterne Bewertung

```text
Receiver:
"Diese Nachricht ist zu alt."
```

## Externe Trace-Bewertung

```text
Trace Analyzer:
"Die Nachricht war bei Empfang bereits 35 ms alt,
Requirement erlaubt maximal 20 ms."
```

Beide Ergebnisse sollen vergleichbar sein.

---

# 18. Cross-Check intern vs extern

Beispiel:

```text
Trace:
DEADLINE_MISSED

Receiver:
ACCEPTED
```

Finding:

```text
RECEIVER_DEADLINE_MONITORING_MISSING
```

oder:

```text
RECEIVER_ACCEPTANCE_POLICY_VIOLATION
```

---

# 19. E2E Protection Profile

Einführung:

```text
E2EProtectionProfile
```

Eigenschaften:

```text
crc
counter
data_id
timestamp
freshness
timeout
sequence_monitoring
duplicate_detection
source_identity
receiver_policy
```

---

# 20. AUTOSAR E2E

Für Automotive kann AUTOSAR E2E als konkretes Profil angebunden werden.

Relevante Mechanismen umfassen je nach Profil u. a.:

```text
CRC
Counter
Data ID
Sequence monitoring
Timeout / repeated data detection
```

Wichtig:

```text
CAN CRC
≠
AUTOSAR E2E CRC
```

Der Bus-CRC schützt die Übertragung auf niedriger Ebene.

AUTOSAR E2E schützt Daten über die Kommunikationskette hinweg.

---

# 21. Black-Channel-Prinzip

Für safety-relevante Kommunikation ist das Black-Channel-Prinzip wichtig.

Prinzip:

```text
Safety Application
↓
Safety Communication Layer
↓
non-safety communication channel
↓
Safety Communication Layer
↓
Safety Application
```

Der darunterliegende Kanal darf aus Sicht des Safety-Protokolls als nicht vertrauenswürdig betrachtet werden.

IEC 61784-3 beschreibt solche Prinzipien für funktional sichere Feldbus-Kommunikation.

---

# 22. Safety Communication Profiles

NIS soll Profile unterstützen können wie:

```text
PROFIsafe
CIP Safety
FSoE
openSAFETY
```

Die konkrete Implementierung darf über:

```text
SafetyCommunicationProfile
```

erfolgen.

---

# 23. SafetyCommunicationProfile

```text
SafetyCommunicationProfile
├── base_technology
├── integrity_mechanisms
├── sequence_mechanism
├── freshness_mechanism
├── timeout_mechanism
├── source_identity
├── destination_identity
├── safety_code
├── reaction_policy
└── applicable_standard
```

---

# 24. Safety Timing Requirement

Einführung:

```text
SafetyTimingRequirement
```

Beispiel:

```yaml
id: STR-001
source_function: BrakePedalAcquire
destination_function: BrakeControl
max_e2e_latency_ms: 15
max_data_age_ms: 20
fault_reaction_time_ms: 50
criticality: ASIL_D
```

Die konkrete ASIL-Einstufung darf nicht vom Simulator erfunden werden.

Sie wird aus dem Safety Engineering übernommen.

---

# 25. Safety Requirement Trace

```text
Hazard
↓
Hazardous Event
↓
Safety Goal
↓
Functional Safety Requirement
↓
Technical Safety Requirement
↓
Communication Safety Requirement
↓
Timing Contract
↓
Simulation
↓
Trace Evidence
↓
Safety Case Evidence
```

---

# 26. HARA

Im Automotive-Umfeld gehört die:

```text
Hazard Analysis and Risk Assessment
```

zur ISO-26262-Konzeptphase.

HARA bewertet Hazardous Events unter anderem im Kontext von:

```text
Severity
Exposure
Controllability
```

und führt zur Safety-Klassifikation bzw. zu Safety Goals.

NIS soll HARA-Ergebnisse **konsumieren und tracebar machen**, nicht eigenständig ohne Systemkontext erfinden.

---

# 27. HARA-Beispiel Kommunikation

Hazard:

```text
Unexpected steering actuation
```

möglicher Kommunikationsbeitrag:

```text
Stale steering command accepted
```

daraus kann ein Requirement entstehen:

```text
SteeringCommand shall not be used
when data age exceeds X ms.
```

NIS prüft:

```text
Simulation
+
Trace
+
Receiver Policy
```

gegen dieses Requirement.

---

# 28. Functional Safety / FuSi

Für NIS bedeutet Functional Safety insbesondere:

```text
Kommunikationsfehler
dürfen nicht unkontrolliert
zu gefährlichem Systemverhalten führen.
```

Daher müssen nicht nur Fehler erkannt werden.

Auch:

```text
Fault Detection
↓
Fault Qualification
↓
Reaction
↓
Safe / Degraded State
```

muss betrachtet werden.

---

# 29. FTTI / Reaktionszeit

Ein Safety Goal kann eine tolerierbare Fehlerreaktionszeit besitzen.

Für NIS wichtig:

```text
Fault occurs
↓
Fault detected
↓
Fault qualified
↓
Reaction initiated
↓
Safe / degraded state reached
```

Metrik:

```text
T_fault_reaction
```

Diese Zeit ist von der reinen Nachrichten-E2E-Latenz zu unterscheiden.

---

# 30. E2E Deadline vs Fault Reaction Time

Nicht verwechseln:

```text
E2E Deadline
→ maximale zulässige Nachrichtentransport-/Akzeptanzzeit
```

```text
Fault Reaction Time
→ maximale Zeit von Fehlerentstehung bis sicherer Reaktion
```

Beide können miteinander gekoppelt sein.

---

# 31. Safety Budget

Ein Gesamtbudget kann aufgeteilt werden:

```text
Safety Reaction Budget = 100 ms

Detection       20 ms
Qualification   10 ms
Communication   30 ms
Processing      20 ms
Actuation       20 ms
```

NIS kann den Kommunikationsanteil prüfen.

---

# 32. Timing Budget Allocation

Einführung:

```text
E2ETimingBudget
```

Beispiel:

```text
Source processing     2 ms
Source queue          3 ms
CAN arbitration       4 ms
CAN transmission      2 ms
Gateway processing    3 ms
Ethernet transport    1 ms
Destination decode    2 ms
Receiver acceptance   1 ms
--------------------------------
Budget               18 ms
```

Requirement:

```text
max = 20 ms
```

Margin:

```text
2 ms
```

---

# 33. Timing Margin

Berechnung:

```text
TimingMargin =
AllowedLatency
-
MeasuredLatency
```

Beispiel:

```text
Allowed = 20 ms
Measured = 18 ms
Margin = 2 ms
```

---

# 34. Negative Margin

```text
Allowed = 20 ms
Measured = 35 ms
```

→

```text
Margin = -15 ms
```

Finding:

```text
E2E_DEADLINE_VIOLATION
```

---

# 35. Jitter

Nicht nur maximale Laufzeit messen.

```text
Jitter =
variation of E2E latency
```

Beispiel:

```text
Run 1 = 8 ms
Run 2 = 9 ms
Run 3 = 18 ms
Run 4 = 7 ms
```

Maximalwert allein erklärt nicht die Stabilität.

---

# 36. Statistik

Simulation und Trace Analyse sollen mindestens liefern:

```text
min
max
mean
median
p95
p99
jitter
deadline_miss_count
deadline_miss_rate
loss_count
duplicate_count
sequence_error_count
stale_count
```

---

# 37. Deterministischer Safety-Nachweis

Für harte Safety Requirements ist:

```text
average latency
```

nicht ausreichend.

Prüfe insbesondere:

```text
worst case
deadline miss
maximum observed age
fault reaction time
```

---

# 38. Clock Synchronization

E2E-Messung über mehrere Geräte benötigt eine gemeinsame oder korrigierte Zeitbasis.

Modell:

```text
TimeSynchronizationProfile
```

Eigenschaften:

```text
clock_domain
synchronization_method
offset
drift
accuracy
uncertainty
last_sync
```

---

# 39. Unsicherheit der Trace-Messung

Trace Analyse muss unterscheiden:

```text
Measured latency = 18 ms
Clock uncertainty = ±2 ms
```

Damit:

```text
effective interval:
16 ... 20 ms
```

Bei Requirement:

```text
max = 19 ms
```

kann Ergebnis sein:

```text
INCONCLUSIVE / REVIEW_REQUIRED
```

statt falschem PASS.

---

# 40. Gateway-Timing

Gateway-Hops müssen eigene Zeitkomponenten besitzen.

```text
Ingress
↓
Decode
↓
Routing lookup
↓
Gateway queue
↓
Optional transformation
↓
Re-encode
↓
Egress
```

---

# 41. Gateway-Konvertierung

Beispiel:

```text
LIN Signal
↓
Gateway
↓
CAN-FD Message
```

Prüfen:

```text
input timestamp
output timestamp
data age
mapping
scaling
unit
counter handling
CRC regeneration
E2E profile handling
```

---

# 42. Store-and-Forward vs Cut-Through

Für Ethernet-/Gateway-Modelle unterscheidbar:

```text
STORE_AND_FORWARD
CUT_THROUGH
APPLICATION_GATEWAY
SIGNAL_GATEWAY
PDU_GATEWAY
```

Diese beeinflussen:

```text
latency
error handling
E2E protection
```

---

# 43. Receiver Timing States

Empfängerstatus:

```text
ON_TIME
LATE
STALE
TIMEOUT
MISSING
DUPLICATE
OUT_OF_SEQUENCE
CORRUPT
WRONG_SOURCE
INVALID
```

---

# 44. Receiver Data States

Zusätzlich:

```text
VALID
INVALID
SUBSTITUTED
LAST_VALID
DEFAULTED
DEGRADED
NOT_AVAILABLE
```

---

# 45. Safety Reaction Model

Einführung:

```text
CommunicationFaultReaction
```

Beispiel:

```yaml
trigger: STALE_DATA
qualification_time_ms: 20
reaction: USE_LAST_VALID_VALUE
max_duration_ms: 100
escalation: SAFE_STATE
```

---

# 46. Beispiel: verspätete Botschaft

Requirement:

```text
PressureCommand
cycle = 10 ms
max E2E = 20 ms
timeout = 40 ms
```

Simulation:

```text
Message 4711

source release:
100.000 ms

receiver arrival:
128.000 ms

receiver accept:
130.000 ms
```

Ergebnis:

```text
E2E = 30 ms
```

Status:

```text
LATE
```

Receiver Policy:

```text
REJECT
```

Trace:

```text
Message rejected due to age/deadline
```

---

# 47. Beispiel: falsche Systemreaktion

Gleiche Situation:

```text
E2E = 30 ms
max = 20 ms
```

aber Receiver:

```text
ACCEPTS VALUE
```

Finding:

```text
STALE_OR_LATE_DATA_ACCEPTED
```

Safety-Relevanz:

```text
Communication Safety Mechanism Failure
```

---

# 48. Externe Bewertung

Trace Analyse prüft unabhängig:

```text
Expected
vs
Observed
vs
Receiver Reaction
```

Tabelle:

```text
Requirement   20 ms
Observed      30 ms
Receiver      ACCEPT
Expected      REJECT
```

→

```text
FAIL
```

---

# 49. Interne Bewertung

System selbst kann prüfen:

```text
CRC
Counter
Timestamp
Age
Timeout
Sequence
Data ID
Plausibility
```

---

# 50. Kombination beider Ebenen

```text
Internal Protection
+
External Trace Verification
```

liefert stärkeren Nachweis.

---

# 51. Validation / Preflight Integration

Vor Simulation prüfen:

```text
E2E requirements defined?
Timing contracts complete?
Source/receiver mapping valid?
Clock model valid?
Protection profile valid?
Receiver policy defined?
Safety links valid?
```

---

# 52. Preflight Finding

Beispiel:

```text
ASIL-relevant communication
has no timeout requirement
```

→

```text
SAFETY_COMM_TIMEOUT_REQUIREMENT_MISSING
```

---

# 53. Weitere Preflight Findings

Mindestens:

```text
E2E_REQUIREMENT_MISSING
E2E_DEADLINE_INVALID
E2E_BUDGET_INCOMPLETE
CLOCK_SYNC_UNDEFINED
CLOCK_ACCURACY_INSUFFICIENT
RECEIVER_POLICY_MISSING
E2E_PROTECTION_MISSING
SEQUENCE_MONITORING_MISSING
TIMEOUT_MONITORING_MISSING
FRESHNESS_MONITORING_MISSING
SAFETY_TRACEABILITY_INCOMPLETE
```

---

# 54. Simulation Integration

Simulation erzeugt für jede relevante Dateninstanz:

```text
E2ETransaction
```

---

# 55. E2ETransaction

```text
E2ETransaction
├── transaction_id
├── source_function
├── destination_function
├── data_object
├── source_timestamp
├── route
├── hops[]
├── destination_timestamp
├── receiver_accept_timestamp
├── latency
├── data_age
├── jitter_context
├── protection_status
├── receiver_status
├── requirement_status
└── findings[]
```

---

# 56. Trace Integration

Universal Trace Event erweitert um:

```text
transaction_id
source_release_time
hop_id
route_id
data_age
deadline
timing_status
sequence_counter
freshness
protection_status
receiver_action
```

---

# 57. Transaction Correlation

Eine fachliche Information muss über Gateway-/Technologiewechsel hinweg korrelierbar bleiben.

```text
Signal
↓
LIN Frame
↓
Gateway
↓
CAN-FD Frame
↓
Gateway
↓
Ethernet Packet
↓
Receiver Data
```

Alle gehören zu:

```text
E2ETransaction
```

---

# 58. Correlation ID

Intern:

```text
transaction_id
```

In echten Traces existiert diese ID ggf. nicht.

Dann benötigt Trace Analysis:

```text
Correlation Engine
```

mit:

```text
timestamp
signal identity
payload
sequence counter
routing
gateway mapping
data ID
```

---

# 59. Trace Analyse View

Neue Ansicht:

```text
E2E Timing
```

---

# 60. E2E Timing View

Darstellung:

```text
SOURCE              GW1               GW2              DEST
  |                  |                 |                 |
  |--- LIN ---------->|                 |                 |
  |                   |--- CAN-FD ---->|                 |
  |                   |                |--- Ethernet --->|
  |                   |                |                 |
  0 ms               8 ms             17 ms            24 ms
```

---

# 61. Breakdown View

```text
Source Processing     2 ms
Queue                 3 ms
LIN                    3 ms
Gateway 1              4 ms
CAN Arbitration        2 ms
CAN Transmission       2 ms
Gateway 2              3 ms
Ethernet               1 ms
Receiver               4 ms
--------------------------------
E2E                   24 ms
```

---

# 62. Requirement Overlay

```text
Allowed:
20 ms

Observed:
24 ms

Difference:
+4 ms

Status:
FAIL
```

---

# 63. Sequence View Integration

Sequence View kann E2E anzeigen:

```text
A        GW       B
|        |        |
|------->|        |
|        |------->|
|                 |
<--- 24 ms ------->
```

---

# 64. Signal View Integration

Signal-Zeitreihen können:

```text
source value
receiver value
age
latency
```

synchron darstellen.

---

# 65. Golden Trace

Golden Trace enthält erwartete:

```text
E2E latency envelope
jitter envelope
sequence behavior
receiver reactions
```

---

# 66. Golden Trace Vergleich

Vergleiche:

```text
Golden E2E = 12 ms
Current E2E = 28 ms
```

Ergebnis:

```text
+16 ms degradation
```

---

# 67. First Divergence

Root Cause kann bestimmen:

```text
first timing divergence
```

Beispiel:

```text
Gateway queue begins to grow
at t = 12.250 s
```

---

# 68. Root Cause Chain

Beispiel:

```text
Camera Burst
↓
Ethernet Queue Growth
↓
Gateway Processing Delay
↓
CAN Forwarding delayed
↓
PressureCommand arrives late
↓
Receiver rejects command
```

---

# 69. Safety Finding

Ergebnis:

```text
E2E_SAFETY_TIMING_VIOLATION
```

mit:

```text
Requirement
Observed Timing
Route
Root Cause
Receiver Reaction
Safety Reference
Evidence
```

---

# 70. Safety Traceability

Neue Beziehungen:

```text
CommunicationSafetyRequirement
→ Signal / DataObject
→ Function
→ Route
→ Network
→ Simulation Scenario
→ E2E Transaction
→ Trace Evidence
→ Test Case
→ Finding
```

---

# 71. ISO 26262

Automotive Functional Safety:

```text
ISO 26262
```

Relevant insbesondere:

```text
Concept Phase
HARA
Safety Goals
Functional Safety Concept
Technical Safety Requirements
Verification / Validation
```

NIS dient hierbei als Engineering-/Evidence-Werkzeug.

---

# 72. ISO 26262 aktuelle Einordnung

Die veröffentlichte zweite Ausgabe der ISO-26262-Reihe stammt aus 2018.

ISO 26262-3:2018 behandelt die Konzeptphase einschließlich:

```text
Item Definition
Hazard Analysis and Risk Assessment
Functional Safety Concept
```

Eine neue Ausgabe befindet sich 2026 in Entwicklung.

NIS sollte Standards deshalb über:

```text
StandardProfile + Version
```

referenzieren und nicht hart in Code einbetten.

---

# 73. SOTIF – ISO 21448

SOTIF betrachtet Gefährdungen durch:

```text
functional insufficiencies
```

und nicht die klassischen zufälligen/ systematischen Fehler, die ISO 26262 adressiert.

Für Kommunikation kann SOTIF relevant sein, wenn z. B.:

```text
Sensor-/Perception-Daten zwar technisch korrekt übertragen werden,
aber zu spät oder inhaltlich unzureichend sind,
sodass die beabsichtigte Funktion unzureichend arbeitet.
```

Die aktuell veröffentlichte Ausgabe ist ISO 21448:2022; eine zweite Ausgabe befindet sich 2026 in Entwicklung.

---

# 74. Cybersecurity – ISO/SAE 21434

Kommunikationssicherheit umfasst auch Security.

ISO/SAE 21434 adressiert Cybersecurity Engineering für Straßenfahrzeuge über den Lebenszyklus.

Mögliche Kommunikationsbedrohungen:

```text
message spoofing
replay
masquerading
injection
denial of service
routing manipulation
freshness attack
```

---

# 75. UNECE R155 / R156

Für Fahrzeug-Cybersecurity und Softwareupdates relevant:

```text
UN R155
→ Cyber Security / CSMS

UN R156
→ Software Update / SUMS
```

NIS kann hierfür Evidence und technische Kommunikationsprüfungen unterstützen.

---

# 76. AUTOSAR E2E ist kein Safety-Standard-Ersatz

AUTOSAR E2E ist ein technischer Schutzmechanismus.

Es ersetzt nicht:

```text
ISO 26262
HARA
Safety Concept
Safety Case
```

sondern kann ein technisches Mittel zur Erfüllung entsprechender Requirements sein.

---

# 77. IEC 61508

Industrieübergreifende Basisnorm für funktionale Sicherheit von:

```text
electrical
electronic
programmable electronic
safety-related systems
```

NIS kann ein generisches:

```text
SIL / Safety Integrity Profile
```

referenzieren.

---

# 78. IEC 61784-3

Für funktional sichere Feldbus-Kommunikation besonders relevant.

Sie beschreibt gemeinsame Prinzipien und Safety Communication Profiles für Safety-Kommunikation über Feldbusse, einschließlich des Black-Channel-Ansatzes.

---

# 79. IEC 62061

Für Safety-related Control Systems in Maschinen relevant.

NIS kann Safety Functions und Kommunikationspfade mit:

```text
SIL
```

bzw. entsprechenden Projektanforderungen verknüpfen.

---

# 80. ISO 13849

Für safety-related parts of control systems in Maschinen relevant.

NIS kann Kommunikationspfade mit:

```text
Performance Level / PLr
```

verknüpfen.

---

# 81. IEC 61511

Für Safety Instrumented Systems in der Prozessindustrie.

Anwendungsfälle:

```text
Emergency Shutdown
Pressure Protection
Process Interlock
Safety Instrumented Function
```

Kommunikation kann Teil der SIF-Kette sein.

---

# 82. ISO 25119

Für land- und forstwirtschaftliche Maschinen.

Relevant für safety-related parts of control systems.

NIS kann entsprechende:

```text
AgPL / safety requirements
```

referenzieren.

---

# 83. ISO 19014

Für funktionale Sicherheit von Erdbaumaschinen.

NIS sollte dies als weiteres Domain Safety Profile unterstützen.

---

# 84. Standards sind Profile – nicht Core-Logik

Nicht:

```text
if automotive:
    special simulator
```

Sondern:

```text
CommunicationSafetyCore
↓
SafetyStandardProfile
```

Beispiele:

```text
ISO26262_PROFILE
IEC61508_PROFILE
IEC62061_PROFILE
ISO13849_PROFILE
IEC61511_PROFILE
ISO25119_PROFILE
ISO19014_PROFILE
```

---

# 85. SafetyStandardProfile

```text
SafetyStandardProfile
├── standard
├── edition
├── domain
├── integrity_level_model
├── required_work_products
├── applicable_validation_rules
├── evidence_requirements
└── traceability_rules
```

---

# 86. Keine automatische ASIL-/SIL-Erfindung

NIS darf nicht anhand einer Nachricht behaupten:

```text
"Das ist ASIL D."
```

ohne Hazard-/Systemkontext.

Zulässig:

```text
Requirement references ASIL D
→ apply corresponding project validation profile
```

---

# 87. Communication Safety Requirement

Datenmodell:

```text
CommunicationSafetyRequirement
├── id
├── source
├── destination
├── data_object
├── max_latency
├── max_age
├── max_jitter
├── timeout
├── fault_reaction_time
├── protection_profile
├── receiver_policy
├── safety_integrity_reference
├── hazard_ref
├── safety_goal_ref
├── fsr_ref
├── tsr_ref
└── evidence_refs
```

---

# 88. Validation / Preflight

Neue Checks:

```text
E2E timing requirement complete
Receiver policy complete
Protection profile valid
Clock sync adequate
Route valid
Gateway transformations valid
Timeout configured
Sequence monitoring configured
Data age monitoring configured
Fault reaction defined
Safety traceability complete
```

---

# 89. Preflight Status

Beispiel:

```text
Communication Safety

E2E Timing          READY
Freshness           READY
Sequence            READY
Integrity           READY
Receiver Policy     READY
Clock Sync          READY
Fault Reaction      REVIEW_REQUIRED
```

Gesamt:

```text
REVIEW_REQUIRED
```

---

# 90. Blocking Rules

Safety-relevante Kommunikation blockieren bei:

```text
missing E2E requirement
missing timeout
invalid protection profile
missing receiver reaction
unresolved route
clock accuracy insufficient
stale timing result
```

abhängig vom Projektprofil.

---

# 91. Safety Fault Injection

Simulation muss gezielt injizieren können:

```text
delay
jitter
loss
duplication
reordering
corruption
stale data
frozen data
wrong sender
wrong data ID
counter jump
counter freeze
gateway delay
queue overload
clock offset
clock drift
```

---

# 92. Safety Test Pattern

Für jede sicherheitsrelevante Kommunikation:

```text
Normal Case
+
Boundary Case
+
Deadline Violation
+
Timeout
+
Sequence Fault
+
Integrity Fault
+
Freshness Fault
+
Receiver Reaction
```

---

# 93. Beispiel Test

Requirement:

```text
max E2E = 20 ms
```

Tests:

```text
18 ms
→ ACCEPT

20 ms
→ ACCEPT

21 ms
→ REJECT

40 ms
→ TIMEOUT

duplicate
→ REJECT

wrong sequence
→ REJECT / DEGRADED

CRC error
→ REJECT
```

je nach definierter Policy.

---

# 94. Fault Reaction Measurement

Nicht nur feststellen:

```text
error detected
```

sondern messen:

```text
t_fault
t_detection
t_qualification
t_reaction_start
t_safe_state
```

---

# 95. Safety Reaction Metrics

```text
Detection Time
Qualification Time
Reaction Time
Time to Safe State
```

---

# 96. Trace Evidence

Safety Evidence enthält:

```text
requirement
simulation configuration
model revision
route
timing measurement
protection status
receiver reaction
fault injection
trace window
root cause
validation result
```

---

# 97. Evidence Bundle

```text
evidence/
├── communication_requirement.json
├── e2e_timing.json
├── route.json
├── protection_profile.json
├── receiver_policy.json
├── simulation_run.json
├── fault_injection.json
├── trace_window.json
├── root_cause.json
└── validation.json
```

---

# 98. Tool Checker Integration

Tool Checker muss prüfen:

```text
Requirement exists
↓
Simulation executed
↓
E2E measured
↓
Receiver reaction checked
↓
Trace checked
↓
Evidence generated
```

---

# 99. Tool Checker Anti-Patterns

Mindestens:

```text
E2E_MEASUREMENT_MISSING
E2E_TRANSACTION_NOT_CORRELATED
E2E_DEADLINE_NOT_CHECKED
DATA_AGE_NOT_CHECKED
RECEIVER_POLICY_NOT_CHECKED
CLOCK_UNCERTAINTY_IGNORED
GATEWAY_DELAY_IGNORED
SEQUENCE_ERROR_NOT_DETECTED
STALE_DATA_ACCEPTED
SAFETY_REACTION_NOT_MEASURED
SAFETY_TRACEABILITY_INCOMPLETE
```

---

# 100. MCP-Erweiterung

Empfohlene Tools:

```text
e2e.get_requirements
e2e.create_requirement
e2e.calculate_path
e2e.measure
e2e.get_breakdown
e2e.compare_requirement
e2e.get_transactions

communication_safety.get_profile
communication_safety.validate
communication_safety.get_receiver_policy

trace.correlate_e2e
trace.get_e2e_timing
trace.get_data_age
trace.get_receiver_reaction

safety.get_hazard_links
safety.get_safety_goal
safety.get_fsr
safety.get_tsr
```

---

# 101. Python Core Services

Empfohlen:

```text
E2EPathResolver
E2ETransactionService
E2ETimingCalculator
E2ETimingBudgetService
DataAgeCalculator
JitterAnalyzer
ReceiverAcceptanceEvaluator
CommunicationSafetyValidator
ProtectionProfileResolver
FaultReactionAnalyzer
ClockUncertaintyService
E2ETraceCorrelator
SafetyTraceabilityResolver
```

---

# 102. UI – Simulation

Neue Funktion:

```text
Measure E2E
```

Auswahl:

```text
Source
Destination
Signal / DataObject
Scenario
```

Ergebnis:

```text
E2E = 18.4 ms
Allowed = 20 ms
Margin = 1.6 ms
Status = PASS
```

---

# 103. UI – Trace Analyse

Neue Ansicht:

```text
E2E Timing
```

mit:

```text
Path
Timing Breakdown
Requirement
Margin
Data Age
Jitter
Sequence
Protection Status
Receiver Action
Safety References
```

---

# 104. Farblogik

Beispiel:

```text
PASS
WARNING
REVIEW
FAIL
BLOCKED
```

Nicht nur Farbe verwenden.

Status immer als Text.

---

# 105. Direkte vs Gateway-Verbindung

Die gleiche Funktion muss beide Fälle beherrschen.

```text
DIRECT
```

und:

```text
MULTI_HOP
```

---

# 106. Technologieunabhängigkeit

Nicht nur Automotive.

Core:

```text
E2E Timing
Communication Safety
Receiver Acceptance
Fault Reaction
```

ist industrieneutral.

Standards werden als Profile ergänzt.

---

# 107. Domain Profiles

Beispiel:

```text
Automotive
Industrial Automation
Machinery
Process Industry
Agriculture
Earth Moving
Rail
Marine
Aerospace
```

Weitere Profile können später ergänzt werden.

---

# 108. Aktuelle Standards – Referenz

Stand der Recherche: September 2026.

Automotive:

```text
ISO 26262:2018 series
ISO 26262-3:2018 – Concept phase / HARA
ISO/DIS 26262-3 – next edition under development

ISO 21448:2022 – SOTIF
Edition 2 under development in 2026

ISO/SAE 21434:2021 – Cybersecurity Engineering

UN R155 – Cyber Security / CSMS
UN R156 – Software Update / SUMS

AUTOSAR E2E Protocol Specification
```

Industrie/Maschinen:

```text
IEC 61508:2010
IEC 61784-3 – Functional Safety Fieldbuses
IEC 62061:2021 + amendments
ISO 13849-1:2023
IEC 61511 series
```

Weitere Domänen:

```text
ISO 25119
ISO 19014
```

---

# 109. Standards-Versionierung

Normen ändern sich.

Deshalb:

```text
standard_id
edition
status
effective_date
profile_version
```

nicht hart im Code.

---

# 110. Wichtige Abgrenzung

NIS darf:

```text
Requirements prüfen
Timing messen
Safety Mechanisms prüfen
Evidence erzeugen
Traceability herstellen
Faults simulieren
```

NIS darf nicht automatisch behaupten:

```text
"ISO 26262 compliant"
```

nur weil einzelne technische Checks bestehen.

Normkonformität erfordert den vollständigen jeweiligen Lifecycle, Prozesse, Work Products und Reviews.

---

# 111. Codex-Arbeitsauftrag

```text
Implement an industry-neutral E2E Communication Timing & Safety Assurance capability.

The same core capability must be usable from:
- Simulation,
- Trace Analysis,
- Validation / Preflight,
- Engineering Agent,
- Safety Engineering.

Measure E2E from source application release to receiver application acceptance.

Support:
- direct communication,
- multi-hop paths,
- multiple technologies,
- gateways,
- switches,
- bus arbitration,
- queueing,
- physical delay,
- gateway processing,
- decoding,
- receiver acceptance.

Track:
- E2E latency,
- data age,
- jitter,
- deadline,
- sequence,
- freshness,
- integrity,
- receiver reaction,
- fault reaction time.

Create:
- CommunicationTimingContract
- ReceiverAcceptancePolicy
- E2EProtectionProfile
- CommunicationSafetyRequirement
- E2ETimingBudget
- E2ETransaction
- SafetyCommunicationProfile
- SafetyStandardProfile

Integrate with:
- TechnologyProfile,
- PhysicalLayerProfile,
- Routing,
- Capacity,
- Timing,
- Simulation,
- Universal Trace,
- Trace Analysis,
- Findings,
- Validation / Preflight.

Support internal monitoring mechanisms such as:
- CRC,
- E2E CRC,
- counter,
- Data ID,
- timestamp,
- freshness,
- timeout,
- deadline monitor,
- heartbeat,
- watchdog,
- plausibility checks.

Support external trace verification independently from receiver-internal monitoring.

Compare:
EXPECTED
vs
OBSERVED
vs
RECEIVER REACTION.

Implement trace correlation across gateway and technology conversions.

Do not invent ASIL, SIL, PL or other safety classifications.
Consume them from approved Safety Engineering artifacts.

Provide traceability:
Hazard
→ Safety Goal
→ FSR
→ TSR
→ Communication Safety Requirement
→ Simulation
→ Trace Evidence
→ Finding.

Support standard profiles for:
- ISO 26262,
- ISO 21448,
- ISO/SAE 21434,
- IEC 61508,
- IEC 61784-3,
- IEC 62061,
- ISO 13849,
- IEC 61511,
- ISO 25119,
- ISO 19014.

Do not claim full standard compliance solely from simulator results.

Generate objective evidence for safety verification.
```

---

# 112. Definition of Done

Die Funktion ist fertig, wenn:

1. direkte E2E-Verbindungen gemessen werden.
2. Multi-Hop-Verbindungen gemessen werden.
3. Gateway-Zeiten aufgelöst werden.
4. Technologie-Wechsel unterstützt werden.
5. Source Release Time verfügbar ist.
6. Receiver Acceptance Time verfügbar ist.
7. E2E-Latenz berechnet wird.
8. Data Age berechnet wird.
9. Jitter berechnet wird.
10. Timing Margin berechnet wird.
11. Deadline Miss erkannt wird.
12. Timeout erkannt wird.
13. Sequence Error erkannt wird.
14. Duplicate erkannt wird.
15. Stale Data erkannt wird.
16. Receiver Reaction ausgewertet wird.
17. externe Trace-Bewertung funktioniert.
18. interne Systembewertung vergleichbar ist.
19. Clock Uncertainty berücksichtigt wird.
20. Gateway-Konvertierung berücksichtigt wird.
21. E2ETransaction existiert.
22. E2E Timing View existiert.
23. Simulation E2E erzeugt.
24. Trace E2E korreliert.
25. Golden Trace E2E vergleichen kann.
26. First Timing Divergence bestimmt werden kann.
27. Root Cause erzeugt werden kann.
28. CommunicationSafetyRequirement existiert.
29. ReceiverAcceptancePolicy existiert.
30. E2EProtectionProfile existiert.
31. SafetyTimingRequirement verlinkbar ist.
32. HARA-/Safety-Goal-Traceability möglich ist.
33. FSR/TSR verlinkbar sind.
34. AUTOSAR-E2E-Mechanismen modellierbar sind.
35. Black-Channel-Safety-Profile modellierbar sind.
36. Validation / Preflight Safety Checks enthält.
37. Fault Injection Kommunikationsfehler abdeckt.
38. Fault Reaction Time gemessen wird.
39. Evidence Bundle erzeugt wird.
40. Tool Checker E2E Safety prüft.
41. keine ASIL-/SIL-Klassifikation halluziniert wird.
42. Standards versioniert referenziert werden.
43. kein technischer PASS automatisch als vollständige Normkonformität ausgegeben wird.

---

# 113. Leitregel

```text
SOURCE DATA
↓
TRANSPORT
↓
NETWORK
↓
GATEWAYS
↓
DESTINATION
↓
RECEIVER ACCEPTANCE
↓
SAFETY REACTION
```

muss vollständig messbar sein.

Und:

```text
EXPECTED
vs
OBSERVED
vs
SYSTEM REACTION
```

muss objektiv vergleichbar sein.

> **Eine Nachricht ist nicht sicher angekommen, nur weil sie physikalisch beim Empfänger eingetroffen ist. Entscheidend ist, ob sie rechtzeitig, unverfälscht, in der richtigen Reihenfolge, mit ausreichender Frische und gemäß der definierten Empfängerreaktion verarbeitet wurde.**
