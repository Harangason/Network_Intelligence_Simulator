# Arbeitsauftrag für Codex
## Logische Interfaces vs. Hardware Interfaces im Model View und Projekt-Wizard

## 1. Ziel

Erweitere den **Network Intelligence Simulator** um eine klare Trennung zwischen zwei Interface-Arten:

```text
Interface
= logische / funktionale Schnittstelle

Hardware Interface
= physische Kommunikationsschnittstelle eines HardwareNode
```

Der bestehende View `Interface` bleibt unverändert die **logische Sicht**.

Neu einzuführen ist der View:

```text
Hardware Interface
```

Der Button wird im Model View zwischen `Hardware` und `Funktion` angeordnet:

```text
Hardware | Hardware Interface | Funktion | Interface
```

Ziel ist, eindeutig modellieren zu können:

```text
ECU XYZ
→ besitzt CAN-FD Channel 1
→ dieser Channel ist mit CAN_FD_A verbunden
→ darüber laufen mehrere Messages
→ diese Messages transportieren Signale von Funktionen
```

---

## 2. Zentrale Modellregel

Verbindlich:

```text
FunctionInterface != HardwareNetworkInterface
```

### FunctionInterface

Beschreibt die fachliche/logische Kommunikation einer Funktion:

```text
Function
→ FunctionInterface
→ Signal / DataObject / Service
```

Beispiele:

```text
MotorDynamicDataOutput
StatusOutput
ConfigurationInput
ObjectDataOutput
```

### HardwareNetworkInterface

Beschreibt die reale Kommunikationsfähigkeit einer Hardware:

```text
HardwareNode
→ HardwareNetworkInterface
→ Controller / Physical Port
→ Network / Bus Segment
```

Beispiele:

```text
CAN-FD Channel 1
CAN-FD Channel 2
Ethernet Port 1
LIN Channel 1
```

---

## 3. Canonical Model

Zielmodell:

```text
Function
├── FunctionInterface
│   ├── Signal
│   └── DataObject
│
└── mapped_to
    ↓
HardwareNode
└── HardwareNetworkInterface
    ├── PhysicalPort / ControllerChannel
    └── Network / BusSegment
```

Transportkette:

```text
Function
→ FunctionInterface
→ Signal / DataObject
→ Message
→ Sender Hardware
→ Hardware Interface
→ Network / Bus
```

Die Views sind nur Projektionen auf dieses Modell.

---

## 4. Bestehender View `Interface`

Der bestehende View darf **nicht** in eine Hardware-Schnittstellensicht umgebaut werden.

Er bleibt zuständig für:

```text
Functions
Functional Interfaces
Inputs
Outputs
Signals
DataObjects
Services
logical dependencies
```

Beispiel:

```text
MotorControl
├── MotorDynamicOutput
│   ├── MotorRPM
│   ├── MotorTorque
│   └── MotorCurrent
└── MotorStatusOutput
    ├── MotorOperatingState
    └── MotorHealthState
```

---

## 5. Neuer View `Hardware Interface`

Der neue View ist zuständig für:

```text
HardwareNode
Physical Communication Controllers
Ports / Channels
Network Technology
Network Assignment
Messages
Bus Load
Capacity
Routing Context
```

Beispiel:

```text
PowertrainECU

├── CAN-FD Interface 1
│   ├── Channel: CAN0
│   ├── Network: CAN_FD_A
│   ├── Messages: 12
│   ├── Static Load: 58 %
│   └── Runtime Peak: 64 %
│
├── CAN-FD Interface 2
│   ├── Channel: CAN1
│   └── Network: CAN_FD_B
│
└── Ethernet Interface 1
    ├── Port: ETH0
    └── Network: ETH_BACKBONE
```

---

## 6. Hardware Interface Core Model

Prüfe zuerst, ob ein gleichwertiges Modell bereits existiert. Falls ja: `REUSE / ADAPT`.

Fachlich benötigt:

```text
HardwareNetworkInterface
├── id
├── name
├── hardware_node_ref
├── technology
├── controller_ref
├── physical_port_ref
├── channel_index
├── network_ref
├── bitrate
├── data_bitrate
├── capabilities
├── status
├── message_refs[]
├── static_load
├── runtime_load
├── target_load_limit
├── warning_load_limit
├── hard_load_limit
└── provenance
```

---

## 7. Hardware Capability

Ein HardwareNode muss angeben können:

```text
supported_network_technologies
max_can_channels
max_can_fd_channels
max_lin_channels
max_ethernet_ports
available_ports
used_ports
```

Beispiel:

```text
PowertrainECU

CAN-FD channels: 2
Ethernet ports: 1
LIN channels: 1
```

Der Generator darf keine beliebige Anzahl physischer Interfaces erzeugen.

---

## 8. Network / Bus Segment

Ein Hardware Interface verbindet den HardwareNode mit genau dem vorgesehenen Network/Bussegment.

Beispiel:

```text
PowertrainECU.CAN_FD_1
→ CAN_FD_A

Gateway.CAN_FD_1
→ CAN_FD_A

BrakeECU.CAN_FD_1
→ CAN_FD_A
```

Alle teilen die Kapazität von:

```text
CAN_FD_A
```

---

## 9. Buslast-Regel

Verbindlich:

```text
Bus Load belongs to Network / Bus Segment.
```

Nicht:

```text
Bus Load belongs to Function.
```

Nicht:

```text
one Interface = one Message.
```

Die Buslast entsteht kumulativ aus allen Messages aller Funktionen und Hardwareteilnehmer auf demselben Bus.

---

## 10. Functions und Hardware Interfaces

Eine Function besitzt nicht automatisch ein eigenes Hardware Interface.

Falsch:

```text
Function A → CAN Interface A
Function B → CAN Interface B
Function C → CAN Interface C
```

wenn alle Funktionen auf derselben ECU laufen und denselben CAN-Bus verwenden können.

Richtig:

```text
PowertrainECU
└── CAN-FD Interface 1
    └── CAN_FD_A
        ├── Messages von Function A
        ├── Messages von Function B
        └── Messages von Function C
```

---

## 11. Message Producer und Sender

Jede Message benötigt mindestens:

```text
producer_function_ref
sender_hardware_ref
hardware_interface_ref
network_ref
```

Unterscheidung:

```text
Producer Function
= fachlicher Erzeuger der Information

Sender Hardware
= Hardware, die den Frame physisch sendet
```

Default:

```text
One Message
→ One Producer Function
```

---

## 12. Message Packing vor Interface Allocation

Verbindliche Reihenfolge:

```text
Functions
→ Functional Interfaces
→ Signals / DataObjects
→ Signal Encoding
→ Message Grouping
→ Message Packing
→ Hardware Mapping
→ Hardware Interface Allocation
→ Bus Load
→ Capacity Validation
→ Routing
```

Interface Allocation darf nicht vor Message Packing passieren.

---

## 13. Message Grouping

Signale werden mindestens gruppiert nach:

```text
Producer Function
Sender Hardware
Timing / Cycle Class
Receiver Set
Priority
Communication Technology
```

Nicht blind alle Signale einer Funktion in eine einzige Message legen.

---

## 14. CAN-FD Payload

CAN-FD unterstützt:

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

Wichtig:

```text
64 Byte = maximale Payload
```

nicht automatisch:

```text
jede CAN-FD Message = 64 Byte
```

Default:

```text
MINIMUM_VALID_SIZE
```

Beispiele:

```text
9 Byte required  → 12 Byte
17 Byte required → 20 Byte
25 Byte required → 32 Byte
40 Byte required → 48 Byte
50 Byte required → 64 Byte
```

Optional:

```text
FIXED_SIZE
FIXED_SIZE_CLASSES
MANUAL
```

als Projektpolicy.

---

## 15. Hardware Interface Allocation

Implementiere bzw. konsolidiere:

```text
HardwareInterfaceAllocationService
```

Input:

```text
Message
Sender Hardware
Required Technology
Current Hardware Interfaces
Network Candidates
Current Network Loads
Hardware Capabilities
```

Output:

```text
selected_hardware_interface
selected_network
projected_network_load
```

---

## 16. Bestehende Kapazität zuerst verwenden

Default:

```text
REUSE_EXISTING_CAPACITY_FIRST
```

Mehrere Messages dürfen dasselbe Hardware Interface nutzen.

Mehrere Functions dürfen über dasselbe Hardware Interface kommunizieren.

Das Interface ist nicht anhand einer Message-Anzahl „voll“.

---

## 17. Wann ist ein Kanal ausgelastet?

Entscheidend sind:

```text
Frame Length
Cycle Time
Nominal Bitrate
Data Bitrate
Protocol Overhead
Arbitration
Stuffing
Gateway Traffic
other Messages on same Network
```

Technologie-spezifische Python-Calculator verwenden.

Für CAN-FD:

```text
CANFDLoadCalculator
```

Keine Buslastberechnung im Frontend oder LLM.

---

## 18. Zweites Hardware Interface

Ein weiteres Interface darf erst vorgeschlagen werden, wenn:

```text
bestehende Kapazität reicht nicht
AND
Packing wurde geprüft/optimiert
AND
kein geeignetes bestehendes Interface verfügbar
AND
Hardware unterstützt zusätzlichen Controller/Port
```

Dann:

```text
InterfaceProposal
```

erzeugen.

---

## 19. Zweites Interface auf demselben Bus

Wichtige Regel:

```text
2 Interfaces
→ same CAN bus
≠
double capacity
```

Ein zusätzlicher CAN-FD-Controller bringt nur zusätzliche Buskapazität, wenn er auf einem separaten Bussegment liegt:

```text
CAN-FD Interface 1
→ CAN_FD_A

CAN-FD Interface 2
→ CAN_FD_B
```

---

## 20. Wizard-Integration

Der Projekt-Wizard muss diese Logik **bereits bei der Neuanlage** anwenden.

Zielprozess:

```text
Requirement
→ Functions
→ Functional Interfaces
→ Signals / DataObjects
→ Hardware Proposal
→ Function-Hardware Mapping
→ Hardware Capability Analysis
→ Hardware Interface Proposal
→ Networks / Bus Segments
→ Message Packing
→ Message-to-Hardware-Interface Allocation
→ Bus Load
→ Capacity
→ Routing
→ Validation
→ Review
→ Core Write
```

---

## 21. Beispiel Wizard

Input:

```text
MotorControl soll über CAN-FD kommunizieren.
```

Ergebnisvorschlag:

```text
Function:
MotorControl

Hardware:
PowertrainECU

Functional Interface:
MotorDynamicOutput

Signals:
MotorRPM
MotorTorque
MotorCurrent
MotorOperatingState

Hardware Capability:
CAN-FD available

Hardware Interface:
PowertrainECU.CAN_FD_1

Network:
CAN_FD_A
```

Danach:

```text
Signals
→ Messages packen
→ Messages CAN_FD_1 zuweisen
→ Load(CAN_FD_A) berechnen
```

---

## 22. Beispiel mehrere Functions

```text
PowertrainECU

Functions:
- MotorControl
- ThermalManagement
- Diagnostics

Hardware Interface:
CAN-FD Interface 1
→ CAN_FD_A
```

Messages:

```text
MotorDynamicData
MotorStatus
ThermalStatus
DiagnosticStatus
```

dürfen alle:

```text
→ PowertrainECU.CAN_FD_1
→ CAN_FD_A
```

verwenden, solange die Kapazität zulässig ist.

---

## 23. View-Kommunikation

Die Views müssen bidirektional verknüpft sein:

```text
Hardware
↔ Hardware Interface
↔ Funktion
↔ Interface
↔ Message
↔ Network
```

### Hardware → Hardware Interface

```text
ECU auswählen
→ Hardware Interface View
→ alle Ports/Channels dieser ECU
```

### Hardware Interface → Funktion

Zeige:

```text
welche Functions Messages über dieses Interface senden
```

### Funktion → Hardware Interface

Zeige:

```text
mapped Hardware
→ verwendete Hardware Interfaces
```

### Interface → Hardware Interface

Zeige:

```text
Functional Interface
→ Signals / DataObjects
→ Messages
→ Transport Mapping
→ Hardware Interface
```

### Message → Hardware Interface

Zeige:

```text
Producer Function
Sender Hardware
Hardware Interface
Network
```

### Network → Hardware Interfaces

Zeige:

```text
connected interfaces
hardware nodes
messages
bus load
reserve
```

---

## 24. UI des Hardware Interface Views

Mindestens anzeigen:

```text
Hardware Node
Interface Name
Technology
Controller / Channel
Physical Port
Network
Bitrate
Data Bitrate
Message Count
Signal Count
Static Load
Runtime Load
Reserve
Status
```

Aktionen:

```text
Add Interface
Edit
Assign Network
Show Messages
Show Signals
Show Bus Load
Open Hardware
Open Function
Open Routing
```

---

## 25. Status und Findings

Hardware Interface Status:

```text
CONFIGURED
UNMAPPED
ACTIVE
OUTDATED
OVERLOADED
ERROR
```

Findings:

```text
HARDWARE_INTERFACE_MISSING
HARDWARE_CAPABILITY_EXCEEDED
INTERFACE_NETWORK_UNMAPPED
MESSAGE_INTERFACE_UNMAPPED
FUNCTION_INTERFACE_TRANSPORT_UNMAPPED
NETWORK_CAPACITY_EXCEEDED
```

---

## 26. Python-First

Python / Core verantwortet:

```text
Hardware Capabilities
Hardware Interface Creation Logic
Technology Compatibility
Message Packing
Message Allocation
Bus Load
Capacity
Routing Validation
```

Frontend verantwortet:

```text
Darstellung
Navigation
Editieren
View State
```

---

## 27. API

Bestehende API-Governance verwenden.

Fachlich werden mindestens Operationen benötigt für:

```text
list Hardware Interfaces of HardwareNode
create Hardware Interface proposal
update Hardware Interface
delete Hardware Interface with impact check
assign Network
list assigned Messages
get Load / Capacity
resolve FunctionInterface transport mapping
```

Keine parallele API-Welt erzeugen.

---

## 28. Tests

### Core Model

```text
FunctionInterface != HardwareNetworkInterface
Hardware owns HardwareNetworkInterface
Function owns FunctionInterface
Function maps to Hardware
FunctionInterface maps to transport
Message maps to HardwareInterface
HardwareInterface maps to Network
```

### Wizard

```text
single function / one CAN-FD
multiple functions / same ECU / same CAN-FD
multiple messages / same Hardware Interface
capacity threshold reached
second CAN-FD channel available
second channel unavailable
CAN-FD + Ethernet mixed architecture
```

### View Navigation

```text
Hardware → Hardware Interface
Hardware Interface → Function
Function → Hardware Interface
Interface → Hardware Interface
Message → Hardware Interface
Network → Hardware Interface
```

---

## 29. Architektur-Compliance

Nach Umsetzung zwingend prüfen:

```text
No FunctionInterface / HardwareInterface conflation
No one-interface-per-function rule
No one-interface-per-message rule
No duplicate interface data model
No frontend busload calculation
No LLM capacity calculation
No second Source of Truth
No silent creation beyond Hardware Capability
```

---

## 30. Dokumentation

Erzeuge / aktualisiere:

```text
docs/model_views/

00_INTERFACE_MODEL_OVERVIEW.md
01_FUNCTIONAL_INTERFACE_VIEW.md
02_HARDWARE_INTERFACE_VIEW.md
03_INTERFACE_TRANSPORT_MAPPING.md
04_HARDWARE_CAPABILITIES.md
05_NETWORK_ASSIGNMENT.md
06_MESSAGE_INTERFACE_ALLOCATION.md
07_WIZARD_INTEGRATION.md
08_VIEW_COMMUNICATION.md
09_VALIDATION_AND_FINDINGS.md
10_TEST_STRATEGY.md
```

---

## 31. Definition of Done

Die Aufgabe ist erst abgeschlossen, wenn:

1. `Interface` weiterhin die logische/funktionale Sicht ist.
2. `Hardware Interface` als neuer View existiert.
3. Der Button zwischen `Hardware` und `Funktion` liegt.
4. FunctionInterface und HardwareNetworkInterface getrennte Core-Modelle sind.
5. HardwareNode physische Communication Channels besitzen kann.
6. Hardware Capabilities die erlaubte Anzahl begrenzen.
7. Hardware Interface einem Network/Bussegment zugeordnet ist.
8. Function-Hardware-Mapping vorhanden ist.
9. FunctionInterface-to-Transport-Mapping vorhanden ist.
10. Messages ein Hardware Interface referenzieren.
11. Mehrere Messages dasselbe Hardware Interface verwenden können.
12. Mehrere Functions dasselbe Hardware Interface verwenden können.
13. Buslast auf Network-Ebene kumuliert wird.
14. Message Packing vor Interface Allocation erfolgt.
15. CAN-FD-Payloadregeln korrekt verwendet werden.
16. Ein zweiter Hardware Channel nur bei Bedarf erzeugt/vorgeschlagen wird.
17. Ein zweites Interface auf demselben Bus nicht als zusätzliche Kapazität gilt.
18. Capacity Split ein separates Bussegment verwendet.
19. Wizard diese Logik bereits bei Projektanlage erzeugt.
20. Alle betroffenen Views miteinander navigieren können.
21. Python die deterministischen Regeln besitzt.
22. Keine parallele fachliche Wahrheit entsteht.
23. Unit-, Integration-, Wizard- und View-Tests erfolgreich sind.
24. Dokumentation den tatsächlichen As-Built-Stand beschreibt.

---

# Leitregel

```text
Functions define WHAT the system does.

Functional Interfaces define WHAT data/functions expose logically.

Hardware defines WHERE functions execute.

Hardware Interfaces define HOW the hardware communicates physically.

Messages carry Signals/DataObjects.

Networks provide shared communication capacity.
```

Kurz:

```text
FUNCTION
→ FUNCTION INTERFACE
→ SIGNAL / DATA OBJECT
→ MESSAGE
→ HARDWARE
→ HARDWARE INTERFACE
→ NETWORK / BUS
```
