# Arbeitsauftrag für Codex
## Prüfung und Korrektur der Interface-, Message-, Signal-Packing- und Kapazitätslogik

## 1. Ausgangsproblem

In mehreren markierten Hardware-Interfaces wird aktuell jeweils nur **eine einzelne Nachricht** dargestellt.

Beispiel:

```text
Interface
└── Message 0x187
```

obwohl das Interface fachlich einen Kommunikationskanal einer Hardware-Schnittstelle repräsentiert und daher – abhängig von Busstandard, Timing und Buslast – normalerweise **mehrere Nachrichten** transportieren können muss.

Das Verhalten:

```text
1 Interface
→ 1 Message
```

ist als generelle Generatorregel fachlich falsch und deutet auf eine unvollständige oder falsch verstandene Implementierung der bereits definierten Message-/Interface-Zuordnungslogik hin.

Ziel dieses Auftrags ist:

```text
bestehende Implementierung inventarisieren
→ tatsächliche Fehlerursache finden
→ vorhandene Regeln wiederverwenden
→ Generatorlogik korrigieren
→ Message Packing korrekt durchführen
→ Messages anhand ihrer realen Buslast Interfaces zuordnen
→ zusätzliche physische Kommunikationskanäle nur bei Bedarf erzeugen
→ vollständig testen
```

---

## 2. Wichtige fachliche Korrektur

Es müssen zwei unterschiedliche Kapazitäten getrennt betrachtet werden:

```text
MESSAGE CAPACITY
≠
INTERFACE / BUS CAPACITY
```

### Message Capacity

Eine einzelne Nachricht besitzt eine durch den Busstandard begrenzte Payload-Kapazität.

Beispiel CAN-FD:

```text
0–8 Byte
12 Byte
16 Byte
20 Byte
24 Byte
32 Byte
48 Byte
64 Byte
```

Maximal:

```text
64 Byte Payload
```

### Interface / Bus Capacity

Ein Interface transportiert **viele Nachrichten über die Zeit**.

Seine Auslastung wird nicht durch eine einzelne Nachricht bestimmt, sondern unter anderem durch:

```text
Message Cycle Time
Frame Length
Nominal Bitrate
Data Bitrate
Protocol Overhead
Arbitration
Bit Stuffing
Priority
Burst Behavior
Gateway Traffic
```

---

## 3. Zentrale Generatorregel

Nicht:

```text
Signal
→ Message
→ neues Interface
```

und nicht:

```text
1 Message
→ 1 Interface
```

sondern:

```text
Signals
↓
Message Groups bilden
↓
Messages busstandardgerecht packen
↓
Message Bus Load berechnen
↓
Messages einem geeigneten Interface zuweisen
↓
kumulative Interface-/Buslast prüfen
↓
weitere kompatible Messages hinzufügen
↓
erst bei Kapazitätsgrenze neuen physischen Kanal / Interface-Vorschlag erzeugen
```

---

## 4. Sehr wichtige Busarchitektur-Regel

Ein zusätzliches Interface erhöht die verfügbare CAN-FD-Kapazität **nur**, wenn es einem eigenen physischen Kommunikationskanal bzw. Bussegment zugeordnet ist.

Falsch:

```text
CAN_FD_Interface_1 ─┐
                    ├── CAN_FD_Network_A
CAN_FD_Interface_2 ─┘
```

wenn dadurch angenommen wird:

```text
2 Interfaces
= doppelte Buskapazität
```

Beide Interfaces benutzen weiterhin dasselbe Busmedium.

Die relevante Kapazität bleibt:

```text
CAN_FD_Network_A
```

---

## 5. Zusätzlicher Kanal bei Überlast

Wenn ein bestehendes CAN-FD-Netzwerk die definierte Lastgrenze erreicht, muss die Logik prüfen:

```text
Kann die Hardware einen weiteren CAN-FD-Kanal bereitstellen?
```

Wenn ja:

```text
HardwareNode
├── CAN_FD_Interface_1
│      └── CAN_FD_Network_A
│
└── CAN_FD_Interface_2
       └── CAN_FD_Network_B
```

Dann stellen `Network A` und `Network B` tatsächlich zwei getrennte Kommunikationskapazitäten bereit.

---

## 6. Keine unbegrenzte Interface-Erzeugung

Vor dem Erzeugen eines weiteren Interfaces prüfen:

```text
Hardware Capability
max CAN controllers
available physical ports
supported bus technologies
configured interface limit
gateway capabilities
domain constraints
```

Wenn kein weiterer physischer Kanal möglich ist:

```text
CAPACITY_EXCEEDED
```

oder:

```text
ADDITIONAL_CHANNEL_REQUIRED
```

als Finding / Proposal erzeugen.

Nicht still beliebig weitere Interfaces anlegen.

---

## 7. Architekturprinzip

Die fachliche Pipeline lautet:

```text
Function
↓
Signals
↓
Signal Encoding
↓
Message Grouping
↓
Message Packing
↓
Technology-specific Message Sizing
↓
Message Timing
↓
Message Bus Load
↓
Network / Interface Allocation
↓
Capacity Validation
↓
Routing
```

---

## 8. Bestehende Implementierung zuerst inventarisieren

Vor Änderung des Codes zwingend prüfen:

```text
Wo werden Signals generiert?
Wo werden Messages generiert?
Wo werden Signalgrößen berechnet?
Wo findet Message Packing statt?
Wo wird CAN-FD DLC bestimmt?
Wo wird ein Message-Sender bestimmt?
Wo werden Messages einem Interface zugewiesen?
Wo werden Interfaces erzeugt?
Wo wird Bus Load berechnet?
Wo wird Network Capacity validiert?
Wo liegt die Technology Registry?
Wo liegen CAN-FD-spezifische Regeln?
Welche Logik verwendet der Projekt-Wizard?
Welche Logik verwendet die Simulation?
Welche Logik verwendet die UI-Darstellung?
```

---

## 9. Inventartabelle

Erzeuge vor dem Umbau:

| Responsibility | Current File | Current Function/Class | Runtime Caller | Status | Problem | Decision |
|---|---|---|---|---|---|---|

Status:

```text
IMPLEMENTED
PARTIAL
STUB
DUPLICATED
LEGACY
UNUSED
BROKEN
MISSING
```

Entscheidung:

```text
KEEP
REUSE
ADAPT
SPLIT
REFACTOR
REPLACE
DEPRECATE
```

---

## 10. Keine zweite Packing Engine

Wenn bereits vorhanden:

```text
MessagePackingService
```

oder gleichwertige Logik:

```text
REUSE / REFACTOR
```

Nicht parallel einen zweiten Message Packer bauen.

Dasselbe gilt für:

```text
Signal Bit Calculator
CANFDLoadCalculator
TechnologyRegistry
RoutingEngine
```

---

## 11. Producer-Regel

Signale einer Message müssen standardmäßig vom gleichen fachlichen Producer stammen.

Verbindlich:

```text
One Message
→ One Producer Function
```

Beispiel:

```text
MotorControl
├── MotorRPM
├── MotorTorque
├── MotorCurrent
└── MotorOperatingState
```

können Message-Kandidaten bilden.

Aber:

```text
ThermalManagement
└── MotorTemperature
```

wird nicht automatisch in dieselbe Message gepackt, wenn Producer Function unterschiedlich ist.

---

## 12. Physischer Sender

Zusätzlich speichern:

```text
producer_function_ref
sender_hardware_ref
```

Unterscheidung:

```text
Producer Function
= fachlicher Erzeuger

Sender Hardware
= physischer Kommunikationssender
```

---

## 13. Message-Gruppierung vor Packing

Signale vor dem eigentlichen Payload-Packing nach mindestens folgenden Kriterien gruppieren:

```text
Producer Function
Sender Hardware
Communication Technology
Network Candidate
Timing / Cycle Class
Receiver Set
Priority / Criticality
Communication Mode
```

---

## 14. Timing-Klassen berücksichtigen

Nicht automatisch Signale zusammenpacken wie:

```text
MotorRPM            10 ms
MotorTorque         10 ms
MotorTemperature  1000 ms
```

nur weil sie vom gleichen Sender kommen.

Besser:

```text
MotorDynamicData
Cycle = 10 ms
```

und:

```text
MotorThermalStatus
Cycle = 1000 ms
```

---

## 15. Receiver Set berücksichtigen

Beispiel:

```text
Signal A
Receivers:
ECU_1
ECU_2
```

und:

```text
Signal B
Receiver:
ECU_9
```

Nicht automatisch dieselbe Message erzeugen, wenn dadurch unnötige Kommunikation entsteht.

---

## 16. Signal Bit Requirement

Vor Message Packing muss für jedes Signal ein verlässlicher:

```text
required_bits
```

vorliegen.

Beispiele:

```text
NUMERIC
→ Range + Resolution + Signedness

STATE / ENUM
→ Number of states + reserved values

BOOLEAN
→ 1 bit

COUNTER
→ modulus / count range
```

---

## 17. Signal Encoding

Vor Packing müssen mindestens bekannt sein:

```text
bit_length
signed
factor
offset
endianness
invalid raw values
reserved raw values
```

wo fachlich notwendig.

---

## 18. Signal bleibt atomar

Ein Signal darf nicht ohne explizite Segmentierungslogik über zwei Messages geteilt werden.

Verbindlich:

```text
Signal
→ exactly one Message payload region
```

Standardfall.

---

## 19. MessagePackingService

Der Service erhält:

```text
Signal Group
Bus Technology
Timing Class
Packing Policy
```

und erzeugt:

```text
one or more Messages
```

---

## 20. CAN-FD Payloadklassen

CAN-FD unterstützt folgende Payloadlängen:

```text
0
1
2
3
4
5
6
7
8
12
16
20
24
32
48
64 Byte
```

---

## 21. Default Message Sizing Policy

Default:

```text
MINIMUM_VALID_SIZE
```

Beispiele:

```text
required 6 B
→ 6 B

required 9 B
→ 12 B

required 15 B
→ 16 B

required 17 B
→ 20 B

required 25 B
→ 32 B

required 40 B
→ 48 B

required 50 B
→ 64 B
```

---

## 22. Weitere Sizing Policies

Unterstütze:

```text
MINIMUM_VALID_SIZE
FIXED_SIZE
FIXED_SIZE_CLASSES
MANUAL
```

Projektregel darf Busstandardregel nicht überschreiben, wenn dadurch ungültige Frames entstehen.

---

## 23. Message voll

Eine Message gilt als voll, wenn kein weiteres kompatibles Signal ohne Überschreitung der ausgewählten Payload-Kapazität hineinpasst.

Dabei berücksichtigen:

```text
Signal Atomicity
Alignment
Reserved Bits
Packing Rules
```

---

## 24. Message Utilization

Für jede Message berechnen:

```text
payload_used_bits
payload_capacity_bits
payload_free_bits
payload_utilization
```

Beispiel:

```text
MotorDynamicData

Used:
48 bit

Capacity:
64 bit

Utilization:
75 %

Free:
16 bit
```

---

## 25. Message ID

IDs wie:

```text
0x187
```

dürfen nicht dazu führen, dass das Interface als exklusiv dieser einen Message betrachtet wird.

Message-Identifier identifiziert eine Message / einen Frame, nicht ein Interface.

---

## 26. CAN Identifier Allocation

CAN-/CAN-FD-Identifier getrennt von Interface-Zuordnung behandeln.

Service beispielsweise:

```text
CANIdentifierAllocator
```

Verantwortung:

```text
unique ID
priority
configured range
reserved IDs
project policy
```

---

## 27. Interface Allocation Service

Nach Message-Erstellung:

```text
InterfaceAllocationService
```

Input:

```text
Message
Sender Hardware
Technology
Network Candidates
Current Loads
Hardware Capabilities
```

Output:

```text
selected interface
selected network
projected load after allocation
```

---

## 28. Kumulative Last

Für jedes Network / Interface-Paar:

```text
current_load
+
candidate_message_load
=
projected_load
```

berechnen.

---

## 29. Buslastlimit

Keine feste universelle Grenze im Code hardcoden.

Konfiguration beispielsweise:

```text
target_limit
warning_limit
hard_limit
```

Beispiel nur als Projektpolicy:

```text
target_limit = 70 %
warning_limit = 80 %
hard_limit = 100 %
```

Die tatsächlichen Defaultwerte aus vorhandener Governance übernehmen.

---

## 30. Interface "voll"

Fachlich präziser:

```text
Interface / Network reaches allocation threshold
```

Nicht:

```text
Interface has N messages
→ full
```

Es gibt keine universelle maximale Message-Anzahl pro CAN-FD-Interface.

Entscheidend ist:

```text
timing + frame length + bus speed + overhead
```

---

## 31. CAN-FD Load Calculation

Nicht nur:

```text
payload bytes × frames/s
```

verwenden.

Der spezialisierte:

```text
CANFDLoadCalculator
```

muss berücksichtigen:

```text
Arbitration Phase
Data Phase
Nominal Bitrate
Data Bitrate
Frame Overhead
CRC
ACK
EOF
Stuffing / configured model
Frame Frequency
```

---

## 32. Message Load Contribution

Für jede Message:

```text
frame_time
frames_per_second
load_contribution
```

berechnen.

Dann pro Netzwerk / Kanal:

```text
sum(all message contributions)
```

---

## 33. Static vs Runtime Load

Unterscheiden:

```text
STATIC_PROJECTED_LOAD
```

aus Wizard / Architektur und:

```text
SIMULATED_RUNTIME_LOAD
```

aus der Simulation.

Nicht vermischen.

---

## 34. Allocation Algorithmus

Fachlicher Ablauf:

```text
for each message group:

    create packed messages

    for each message:

        find compatible existing interfaces

        calculate projected load for each candidate

        select suitable interface according to policy

        if suitable interface exists:
            assign message

        else:
            evaluate new physical channel

        if new channel supported:
            create InterfaceProposal
            create NetworkSegmentProposal
            assign message

        else:
            create CAPACITY_EXCEEDED finding
```

---

## 35. Bestehende Interfaces zuerst verwenden

Default:

```text
REUSE_EXISTING_CAPACITY_FIRST
```

Nicht für jede neue Message sofort ein neues Interface erzeugen.

---

## 36. Interface-Auswahl

Kriterien:

```text
technology compatibility
sender hardware
receiver reachability
current load
projected load
priority
gateway requirement
routing complexity
available capacity
```

---

## 37. Packing Policy für mehrere Interfaces

Wenn mehrere geeignete Interfaces existieren, Policy explizit verwenden, z. B.:

```text
BEST_FIT
LOWEST_LOAD
BEST_FIT_UNDER_TARGET
```

Nicht zufällig wählen.

---

## 38. Neues Interface / neuer Kanal

Wenn vorhandene Kapazität nicht reicht:

```text
HardwareCapabilityService
```

prüft:

```text
max supported CAN-FD controllers
used controllers
available ports
electrical support
gateway capability
```

---

## 39. InterfaceProposal statt stiller Erstellung

Wenn zusätzlicher Kanal Generator-/KI-Vorschlag ist:

```text
InterfaceProposal
```

mit:

```text
hardware_ref
technology
reason
projected_load
network_segment
affected_messages
confidence
validation_result
```

---

## 40. Nutzerfreigabe

Im Wizard:

```text
Proposal
→ Validation
→ Preview
→ User Approval
→ Core Write
```

Kein ungeprüftes automatisches Hinzufügen neuer physischer Ports, wenn es eine Architekturentscheidung ist.

---

## 41. AI-Rolle

KI darf vorschlagen:

```text
Functions
Signals
Timing Classes
Receiver Sets
Message Grouping
Message Names
Priority
Network Technology
additional channel proposal
```

---

## 42. Python-Rolle

Python berechnet deterministisch:

```text
Bit Requirement
Encoding
Packing
DLC / Payload Class
Frame Time
Bus Load
Projected Interface Load
Capacity
Routing Reachability
Technology Compatibility
```

Regel:

```text
AI proposes.
Python calculates.
```

---

## 43. Keine LLM-Buslastberechnung

Nicht:

```text
LLM:
"This interface is probably full."
```

Sondern:

```text
LLM
→ calculate_interface_load()
→ CANFDLoadCalculator
→ structured result
```

---

## 44. Wizard-Integration

Diese Logik muss bereits bei der initialen Projektgenerierung verwendet werden.

```text
Requirements
↓
Functions
↓
Hardware
↓
Signals
↓
Signal Semantics
↓
Bit Encoding
↓
Timing Classes
↓
Messages
↓
Message Packing
↓
Interface / Network Allocation
↓
Capacity
↓
Routing
↓
Validation
↓
Review
```

---

## 45. Kein später Reparatur-Hack

Die korrekte Interface-/Message-Struktur muss bereits im Wizard entstehen.

Simulation soll nicht erst nachträglich eine falsche Projektarchitektur reparieren.

---

## 46. Simulation verwendet freigegebene Architektur

Simulation liest:

```text
approved interfaces
approved networks
approved messages
approved signal packing
approved routing
```

---

## 47. UI-Darstellung

Interface-Detailansicht muss mehrere Messages darstellen können.

Beispiel:

```text
CAN-FD Interface 1
Network: CAN-FD_A
Load: 63 %

Messages:
├── 0x187 MotorDynamicData
├── 0x188 MotorStatus
├── 0x1A1 ThermalStatus
├── 0x1B0 DiagnosticStatus
└── ...
```

---

## 48. Interface Summary

Anzeigen:

```text
Technology
Network
Bitrate
Data Bitrate
Message Count
Signal Count
Average Load
Peak Load
Reserve
Allocation Status
```

---

## 49. Message Detail

Pro Message:

```text
Identifier
Producer Function
Sender Hardware
Cycle
Priority
Receiver Set
Payload Used
Payload Capacity
Signals
```

---

## 50. Beispiel korrigierter CAN-FD-Aufbau

Nicht:

```text
Interface 1
└── 0x187

Interface 2
└── 0x188

Interface 3
└── 0x189
```

wenn Interface 1 noch ausreichend Kapazität besitzt.

Sondern beispielsweise:

```text
CAN-FD Interface 1
Network A
Load 68 %

├── 0x187
├── 0x188
├── 0x189
├── 0x18A
└── 0x18B
```

Erst bei:

```text
projected load > allocation threshold
```

neuen Kanal prüfen.

---

## 51. Kritischer Architekturfall

Angenommen:

```text
CAN-FD Network A
load = 82 %

target limit = 80 %
```

und Hardware besitzt keinen zweiten CAN-Controller.

Dann:

```text
do NOT silently create interface
```

sondern:

```text
Finding:
NETWORK_CAPACITY_EXCEEDED

Recommended options:
- reduce message rate
- improve packing
- move traffic
- add hardware channel
- choose another technology
```

---

## 52. Optimierung vor neuem Kanal

Bevor neues Interface vorgeschlagen wird, prüfen:

```text
Can messages be repacked?
Are compatible messages underutilized?
Can timing classes be optimized?
Are duplicate messages present?
Are unnecessarily large fixed payloads used?
Can routing be simplified?
```

---

## 53. Reihenfolge bei Capacity Problem

```text
1. Validate current packing
2. Repack compatible signals/messages
3. Check message sizing policy
4. Recalculate load
5. Try alternative existing compatible interface
6. Try alternative network
7. Propose additional physical channel
8. Propose technology upgrade
9. Block if unresolved
```

---

## 54. MessagePacking-Optimierung

Beispiel:

```text
Message A:
2 / 8 Byte

Message B:
3 / 8 Byte
```

gleicher:

```text
Producer
Timing
Receiver Set
Network
Priority Class
```

Dann prüfen:

```text
merge candidate
```

statt direkt zwei Frames zu senden.

---

## 55. Kein Merge bei inkompatiblem Timing

Nicht mergen:

```text
10 ms signal
+
1000 ms signal
```

wenn dadurch unnötig hohe Übertragungsrate entsteht.

---

## 56. Keine reine Byteoptimierung

Packing-Ziel ist nicht nur:

```text
max payload utilization
```

sondern:

```text
correct timing
correct semantics
correct receiver scope
acceptable latency
acceptable bus load
```

---

## 57. Tests – Message Packing

Mindestens:

```text
multiple signals same producer
different producers
different timing
different receivers
message overflow
signal atomicity
DLC sizing
unused payload
message merge
message split
```

---

## 58. Tests – Interface Allocation

Mindestens:

```text
1 message on empty interface
10 messages fitting one interface
messages filling interface below threshold
candidate crossing threshold
second existing interface available
new physical channel available
new physical channel unavailable
same network on two interfaces does not double capacity
separate network segment does increase capacity
```

---

## 59. CAN-FD DLC Tests

```text
8 B  → 8 B
9 B  → 12 B
12 B → 12 B
13 B → 16 B
20 B → 20 B
21 B → 24 B
25 B → 32 B
33 B → 48 B
49 B → 64 B
65 B → must not fit one frame
```

---

## 60. Load Tests

Für CAN-FD verschiedene:

```text
nominal bitrate
data bitrate
cycle times
payload sizes
message counts
```

testen.

---

## 61. E2E-Test Wizard

Erzeuge beispielsweise:

```text
1 HardwareNode
1 Producer Function
20 Signals
CAN-FD
```

Erwartung:

```text
signals
→ multiple Messages
→ several Messages on same Interface
```

solange Lastlimit nicht überschritten wird.

---

## 62. E2E Capacity-Split-Test

Erzeuge genügend Traffic, dass:

```text
CAN-FD Network A
```

den Target Load überschreitet.

Wenn Hardware zweiten Kanal unterstützt:

```text
Interface 2 Proposal
+
Network B Proposal
```

und verbleibende Messages dorthin verteilen.

---

## 63. UI-Regression

Prüfe:

```text
Interface displays all assigned Messages
Message count correct
Signal count correct
Busload correct
no duplicate Messages
no orphan Signals
no orphan Interfaces
```

---

## 64. Architecture Compliance

Nach Implementierung prüfen:

```text
No 1-message-per-interface rule
No duplicate MessagePacking logic
No duplicate CAN-FD load calculation
No frontend busload calculation
No LLM capacity calculation
No arbitrary interface creation
No capacity increase assumed from second interface on same bus
Technology-specific logic stays in technology modules
```

---

## 65. Findings bei bestehendem Fehler

Wenn der aktuelle Generator tatsächlich:

```text
1 Message
→ 1 Interface
```

erzwingt:

```text
Finding:
GENERATOR_INTERFACE_ALLOCATION_INVALID

Severity:
HIGH

Expected:
Multiple compatible messages share an interface/network
until configured capacity threshold is reached.
```

---

## 66. Dokumentation

Erzeuge / aktualisiere:

```text
docs/communication_generation/

00_MESSAGE_INTERFACE_ALLOCATION_OVERVIEW.md
01_CURRENT_IMPLEMENTATION_AUDIT.md
02_SIGNAL_TO_MESSAGE_GROUPING.md
03_MESSAGE_PACKING.md
04_CAN_FD_PAYLOAD_SIZING.md
05_CAN_IDENTIFIER_ALLOCATION.md
06_INTERFACE_ALLOCATION.md
07_NETWORK_CAPACITY.md
08_BUSLOAD_CALCULATION.md
09_ADDITIONAL_CHANNEL_PROPOSALS.md
10_WIZARD_INTEGRATION.md
11_AI_AND_PYTHON_RESPONSIBILITIES.md
12_TEST_STRATEGY.md
```

---

## 67. Pflicht-Audit-Bericht vor größerem Refactor

Vor Änderung dokumentieren:

```text
Observed behavior
Expected behavior
Existing implementation
Root cause
Duplicate logic
Affected files
Proposed migration
Regression risk
```

---

## 68. Umsetzungsschleife

```text
ANALYZE
→ REUSE EXISTING CORE
→ CORRECT MESSAGE GROUPING
→ CORRECT MESSAGE PACKING
→ CORRECT INTERFACE ALLOCATION
→ RUN UNIT TESTS
→ RUN INTEGRATION TESTS
→ RUN E2E WIZARD TEST
→ RUN CAPACITY TESTS
→ RUN REGRESSION
→ FIX
→ RETEST
→ DOCUMENT
```

---

## 69. Keine vorzeitige Fertigmeldung

Nicht:

```text
UI shows more messages
→ COMPLETE
```

Nicht:

```text
generator creates second interface
→ COMPLETE
```

Nicht:

```text
tests compile
→ COMPLETE
```

---

## 70. Definition of Done

Die Aufgabe gilt erst als abgeschlossen, wenn:

1. bestehende Generatorlogik inventarisiert wurde,
2. Ursache der bisherigen 1-Message-pro-Interface-Darstellung identifiziert wurde,
3. keine parallele Packing Engine entstanden ist,
4. Signals nach Producer Function gruppiert werden,
5. Sender Hardware separat berücksichtigt wird,
6. Timing-Klassen berücksichtigt werden,
7. Receiver Sets berücksichtigt werden,
8. Signal-Bitbedarf vor Packing bekannt ist,
9. Signals atomar gepackt werden,
10. CAN-FD Payloadklassen korrekt verwendet werden,
11. Messages mehrere Signals enthalten können,
12. mehrere Messages demselben Interface zugeordnet werden können,
13. Interface-Auslastung aus realer Frame-/Timing-Logik berechnet wird,
14. Buslastlimit konfigurierbar ist,
15. ein Interface nicht anhand einer Message-Anzahl als voll gilt,
16. zusätzliche Interfaces nicht automatisch Buskapazität verdoppeln,
17. zusätzlicher CAN-FD-Kanal nur mit eigenem Bussegment Kapazität erhöht,
18. Hardware Capabilities vor neuem Interface geprüft werden,
19. neue physische Kanäle als Proposal behandelt werden, sofern architekturrelevant,
20. vor neuem Kanal vorhandenes Packing optimiert wird,
21. Wizard diese Logik bereits beim Projektstart verwendet,
22. Simulation ausschließlich die freigegebene Kommunikationsarchitektur verwendet,
23. UI mehrere Messages pro Interface korrekt anzeigt,
24. keine Message-/Signal-Dubletten entstehen,
25. keine orphan Messages / Signals / Interfaces entstehen,
26. CAN-FD DLC Tests erfolgreich sind,
27. Interface Allocation Tests erfolgreich sind,
28. Capacity Split E2E erfolgreich ist,
29. Regression vorhandener Kommunikation funktioniert,
30. Dokumentation den tatsächlichen As-Built-Stand beschreibt.

---

# Zentrale Leitregel

```text
Signals fill Messages.

Messages consume bus time.

Interfaces connect Hardware to Networks.

Networks provide communication capacity.

Capacity is determined by time and protocol behavior,
not by a one-message-per-interface rule.
```

Kurz:

```text
SIGNALS
→ PACK INTO MESSAGES
→ CALCULATE FRAME COST
→ ASSIGN TO INTERFACE / NETWORK
→ ACCUMULATE LOAD
→ REUSE CAPACITY
→ OPTIMIZE
→ ADD PHYSICAL CHANNEL ONLY IF NECESSARY
```
