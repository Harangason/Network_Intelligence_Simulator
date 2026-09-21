# Network Intelligence Simulator (NIS)
## Physical Realization, Arbitration & PHY Rules
## Verdeckte physikalische Umsetzung hinter abstrahierten Verbindungen

---

# 1. Ziel

Der Network Intelligence Simulator soll Kommunikationsverbindungen weiterhin **einfach und abstrahiert** darstellen.

Beispiel:

```text
Controller A ───────── CAN-FD ───────── Controller B
```

Diese Linie ist jedoch **kein einzelnes Kabel**.

Hinter der sichtbaren Verbindung muss intern eine physikalische Realisierung stehen:

```text
Logical Connection
↓
Technology Binding
↓
Medium Access / Arbitration
↓
PHY
↓
Physical Realization
↓
Physical Constraints
```

Beispiel CAN-FD:

```text
sichtbar:
Controller A ───── CAN-FD ───── Controller B

intern:
CAN_H
CAN_L
Differential Signaling
Twisted Pair
Termination
Transceiver
Propagation Delay
Bit Timing
Arbitration
```

Zentrale Leitregel:

> **Eine Verbindungslinie in der Architektur repräsentiert eine technische Kommunikationsbeziehung – nicht automatisch einen einzelnen Leiter.**

---

# 2. Erweiterung des TechnologyProfile

Das bestehende `TechnologyProfile` wird erweitert.

```text
TechnologyProfile
│
├── RateModel
├── ParameterSchema
├── CommunicationMechanisms
├── MediumAccessModel
├── ArbitrationModel
├── PhysicalLayerProfile
├── PhysicalRealizationRules
├── ValidationRules
└── CalculationModel
```

Damit wird eine Kommunikationstechnologie nicht nur durch:

```text
Name
+
Bitrate
```

beschrieben.

Sondern durch:

```text
Technology Semantics
+
Medium Access
+
PHY
+
Physical Realization
+
Constraints
```

---

# 3. Schichtenmodell

Empfohlene NIS-Struktur:

```text
FUNCTION / DATA
↓
TRANSPORT
↓
NETWORK / ROUTING
↓
DATA LINK
↓
MEDIUM ACCESS / ARBITRATION
↓
PHY
↓
PHYSICAL REALIZATION
```

Die UI darf weiterhin abstrahieren:

```text
A ───── Technology ───── B
```

Der Core muss jedoch die darunterliegende Realität kennen.

---

# 4. PhysicalLayerProfile

Einführung:

```text
PhysicalLayerProfile
```

Mögliche Eigenschaften:

```text
medium_type
conductor_count
pair_count
differential
single_ended
duplex_mode
shared_medium
point_to_point
multidrop
voltage_model
termination_model
biasing_model
shielding_requirement
max_length
max_stub_length
propagation_speed
connector_profile
power_over_medium
encoding
clocking
transceiver_profile
wake_up_behavior
```

Nicht jede Technologie benötigt jedes Feld.

---

# 5. PhysicalRealization

Zusätzlich zum abstrakten Technology Binding:

```text
Connection
│
├── LogicalConnection
│
├── TechnologyBinding
│
└── PhysicalRealization
```

`PhysicalRealization` beschreibt die konkrete technische Umsetzung.

Beispiel:

```text
PhysicalRealization
├── Medium
├── Channels
├── Pairs
├── Conductors
├── PHY
├── Transceivers
├── Terminations
├── Connectors
├── Topology
└── Constraints
```

---

# 6. PhysicalMedium, Channel und Conductor trennen

Nicht nur:

```text
wire_count = 2
```

Sondern:

```text
PhysicalMedium
↓
PhysicalChannel
↓
Pair
↓
Conductor
```

Beispiel CAN:

```text
PhysicalMedium
└── Twisted Pair
    └── Differential Channel
        ├── CAN_H
        └── CAN_L
```

Beispiel 1000BASE-T:

```text
Cable
├── Pair 1
├── Pair 2
├── Pair 3
└── Pair 4
```

Beispiel SPI:

```text
PhysicalConnection
├── SCLK
├── MOSI
├── MISO
└── CS
```

---

# 7. MediumAccessModel

Einführung eines generischen Medium-Access-Modells:

```text
MediumAccessModel
│
├── BITWISE_PRIORITY
├── MASTER_SCHEDULED
├── TDMA
├── MINISLOT
├── TOKEN_PASSING
├── POLLING
├── CSMA_CD
├── CSMA_CA
├── WIRED_AND_ARBITRATION
├── FULL_DUPLEX_SWITCHED
├── MASTER_SLAVE
└── POINT_TO_POINT
```

Die TechnologyProfiles referenzieren das passende Modell.

---

# 8. ArbitrationModel

Zusätzlich:

```text
ArbitrationModel
```

Mögliche Eigenschaften:

```text
type
priority_source
identifier_based
non_destructive
retry_behavior
collision_behavior
schedule_based
slot_based
token_based
master_controlled
deterministic
worst_case_delay_model
```

---

# 9. CAN / CAN-FD

Sichtbar:

```text
ECU A ───── CAN-FD ───── ECU B
```

Intern:

```text
Physical Layer:
Twisted Pair

Conductors:
CAN_H
CAN_L

Signaling:
Differential

Topology:
Linear Bus

Shared Medium:
Yes

Access:
Multi-Master

Arbitration:
Bitwise Non-Destructive Priority

Logical Levels:
Dominant
Recessive

Termination:
120 Ω at both physical bus ends
```

Zusätzlich relevant:

```text
bus length
stub length
propagation delay
transceiver delay
sample point
nominal bitrate
data bitrate
```

---

# 10. CAN-Arbitration

CAN-Arbitration:

```text
Node A sends identifier
Node B sends identifier
↓
dominant bit overrides recessive bit
↓
losing node stops transmitting
↓
winner continues without destroying frame
```

Daher:

```text
Arbitration = NON_DESTRUCTIVE
```

NIS muss daraus ableiten können:

```text
priority
arbitration delay
worst-case blocking
message latency
```

---

# 11. LIN

Sichtbar:

```text
Master ───── LIN ───── Slave
```

Physikalisch:

```text
Data Conductor:
1

Signaling:
Single-Ended

Topology:
Bus

Access:
Master Scheduled

Arbitration:
None in CAN sense

Termination / Bias:
technology-specific pull-up
```

Regeln:

```text
LIN
→ kein CAN_H / CAN_L
→ kein CAN ArbitrationModel
→ kein CAN-FD RateModel
```

---

# 12. LIN Schedule Model

LIN arbeitet schedule-basiert.

Intern:

```text
ScheduleTable
├── Slot 1
├── Slot 2
├── Slot 3
└── Diagnostic Slot
```

Timing wird bestimmt durch:

```text
Header
+
Response
+
Inter-frame spacing
+
Schedule timing
```

Nicht durch CAN-Arbitration.

---

# 13. RS-485 / Modbus RTU

Sichtbar:

```text
PLC ───── Modbus RTU ───── Device
```

Physikalisch:

```text
RS-485

A
B

Differential:
Yes

Shared Medium:
Yes

Multidrop:
Yes
```

Mögliche Realisierungen:

```text
2-wire
→ one differential pair
→ usually half duplex

4-wire
→ TX pair
→ RX pair
→ full duplex possible
```

Weitere Regeln:

```text
termination
biasing
bus topology
maximum node count
stub constraints
```

---

# 14. Ethernet PHY ist nicht gleich Ethernet

Die Darstellung:

```text
Controller A ───── Ethernet ───── Controller B
```

reicht intern nicht.

Beispiele:

```text
100BASE-TX
→ 2 twisted pairs

1000BASE-T
→ 4 twisted pairs

100BASE-T1
→ 1 twisted pair

1000BASE-T1
→ 1 twisted pair
```

Daher:

```text
EthernetTechnology
↓
EthernetPHYProfile
```

---

# 15. EthernetPHYProfile

Beispiele:

```text
10BASE-T
100BASE-TX
1000BASE-T
100BASE-T1
1000BASE-T1
10BASE-T1S
```

Eigenschaften:

```text
link_rate
pair_count
duplex
encoding
point_to_point
multidrop
max_length
autonegotiation
master_slave_role
```

---

# 16. Shared Ethernet vs. switched Ethernet

Historisch:

```text
Shared Ethernet
→ CSMA/CD
```

Modern:

```text
Switched Ethernet
→ point-to-point
→ full duplex
→ no collision-domain arbitration
```

NIS darf diese beiden Modelle nicht vermischen.

---

# 17. 10BASE-T1S / PLCA

Für Single-Pair-Multidrop-Ethernet kann ein spezielles Access Model relevant sein.

Beispiel:

```text
10BASE-T1S
→ multidrop possible
→ PLCA can coordinate transmission opportunities
```

Das gehört in:

```text
MediumAccessModel
```

und nicht in eine generische Ethernet-Annahme.

---

# 18. I²C

Sichtbar:

```text
Controller ───── I²C ───── Sensor
```

Physikalisch:

```text
SDA
SCL
```

Elektrisch:

```text
open-drain
pull-up resistors
shared bus
```

Arbitration:

```text
wired-AND
```

Beispiel:

```text
Master 1 sends 1
Master 2 sends 0
↓
bus = 0
↓
Master 1 detects arbitration loss
```

---

# 19. SPI

Sichtbar:

```text
Controller ───── SPI ───── Device
```

Physikalisch typischerweise:

```text
SCLK
MOSI
MISO
CS
```

Bei mehreren Slaves:

```text
SCLK shared
MOSI shared
MISO shared
CS1
CS2
CS3
...
```

Daher:

```text
1 logical SPI connection
≠
1 physical conductor
```

---

# 20. SPI Resource Validation

Beispiel:

```text
Controller has:
2 chip-select outputs

Requested:
4 independent SPI slaves
```

Finding:

```text
PHYSICAL_CHANNEL_CAPACITY_EXCEEDED
```

---

# 21. UART

Sichtbar:

```text
Device A ───── UART ───── Device B
```

Physikalisch:

```text
TX
RX
GND / reference
```

Optionale Flow-Control-Leitungen:

```text
RTS
CTS
```

---

# 22. RS-232

Typischerweise:

```text
single-ended
point-to-point
```

Signalpfade z. B.:

```text
TX
RX
GND
```

plus optionale Handshake-Signale.

---

# 23. RS-422

Typischerweise:

```text
differential TX pair
differential RX pair
```

Daher:

```text
4 signal conductors
```

für full-duplex point-to-point.

---

# 24. FlexRay

FlexRay kann besitzen:

```text
Channel A
Channel B
```

Je Kanal:

```text
differential pair
```

Medium Access:

```text
static segment
→ TDMA / fixed slots

dynamic segment
→ minislot-based arbitration
```

Zusätzlich:

```text
cycle
slot
minislot
channel redundancy
```

---

# 25. EtherCAT

EtherCAT darf nicht wie ein klassischer Shared Bus behandelt werden.

Sichtbar:

```text
Master
 |
Slave 1
 |
Slave 2
 |
Slave 3
```

Intern:

```text
point-to-point Ethernet links
full duplex
frame processing on the fly
working counter
distributed clocks
```

Kein CAN-artiges ArbitrationModel.

---

# 26. PROFINET

PROFINET ist ein höherer Kommunikationsstack auf Ethernet.

Intern:

```text
PROFINET
↓
Ethernet Data Link
↓
Ethernet PHY
↓
Physical Realization
```

Damit können:

```text
PROFINET RT
PROFINET IRT
```

unterschiedliche Timing-/Scheduling-Regeln verwenden.

---

# 27. PROFIBUS

Relevante physikalische Aspekte:

```text
RS-485 physical layer
bus topology
termination
segment length
node count
repeater boundaries
```

Medium Access bei Multi-Master-Konfiguration:

```text
Token Passing between masters
+
Master/Slave communication
```

---

# 28. CANopen

CANopen erbt physikalisch:

```text
CAN Physical Layer
+
CAN Arbitration
```

Darüber:

```text
NMT
PDO
SDO
Heartbeat
EMCY
```

NIS muss Layer-Vererbung unterstützen.

---

# 29. J1939 / NMEA 2000

Physikalisch meist:

```text
CAN-based differential bus
```

Darüber:

```text
Address Claim
PGN
NAME
Diagnostics
```

Nicht mehrfach eigene PHY-Regeln duplizieren.

Sondern:

```text
J1939
→ CAN PHY Profile

NMEA2000
→ CAN PHY Profile
```

mit technologiespezifischen Ergänzungen.

---

# 30. TopologyModel

Einführung:

```text
TopologyModel
```

Mögliche Typen:

```text
BUS
STAR
TREE
RING
LINE
DAISY_CHAIN
POINT_TO_POINT
MULTIDROP
SWITCHED_NETWORK
HYBRID
```

TechnologyProfile kann erlaubte Topologien definieren.

---

# 31. Topology Validation

Beispiele:

```text
CAN
→ bus topology expected
→ excessive star branches = risk

RS-485
→ bus topology preferred
→ excessive stubs = risk

Ethernet switched
→ star/tree through switches valid

EtherCAT
→ line/tree/ring depending realization
```

---

# 32. TerminationModel

Einführung:

```text
TerminationModel
```

Eigenschaften:

```text
required
type
resistance
count
placement
end_of_bus_only
integrated_allowed
```

---

# 33. CAN Termination Validation

Beispiel:

```text
CAN network

termination_count = 3
```

Finding:

```text
PHYSICAL_TERMINATION_INVALID
```

oder:

```text
termination only in middle of bus
```

Finding:

```text
PHYSICAL_TERMINATION_PLACEMENT_INVALID
```

---

# 34. RS-485 Termination Validation

Beispiel:

```text
bus has no termination
```

Finding:

```text
PHYSICAL_TERMINATION_MISSING
```

---

# 35. BiasingModel

Relevant z. B. für:

```text
RS-485
LIN
I²C pull-ups
```

Eigenschaften:

```text
required
type
location
electrical parameters
```

---

# 36. PropagationModel

Einführung:

```text
PropagationModel
```

Eigenschaften:

```text
medium_propagation_speed
cable_length
propagation_delay
transceiver_delay
connector_delay
repeater_delay
switch_delay
```

---

# 37. Timing muss physikalische Realität berücksichtigen

Nicht nur:

```text
Payload
+
Bitrate
=
Transmission Time
```

Sondern:

```text
T_end_to_end =
T_queue
+
T_arbitration
+
T_serialization
+
T_phy
+
T_propagation
+
T_switch
+
T_gateway
+
T_processing
```

Nicht jede Technologie verwendet jeden Term.

---

# 38. Arbitration Delay

Beispiel CAN:

```text
higher-priority message wins
↓
lower-priority message waits
```

NIS muss Worst-Case-Arbitration berücksichtigen können.

---

# 39. Queue Delay

Relevanz:

```text
CAN controllers
Ethernet switches
Gateways
DDS queues
PROFINET queues
```

Queueing gehört nicht in den PHY selbst, aber in die End-to-End-Timing-Kette.

---

# 40. Serialization Delay

Berechnung:

```text
T_serialization = frame_bits / bitrate
```

aber nur mit:

```text
valid TechnologyProfile
+
valid RateModel
```

---

# 41. DuplexModel

Mögliche Werte:

```text
SIMPLEX
HALF_DUPLEX
FULL_DUPLEX
```

Beispiele:

```text
RS-485 2-wire
→ HALF_DUPLEX

Switched Ethernet
→ FULL_DUPLEX

UART TX/RX
→ FULL_DUPLEX possible
```

---

# 42. SharedMediumModel

Eigenschaften:

```text
shared_medium
participant_count
simultaneous_transmission_possible
collision_possible
arbitration_required
master_controlled
```

---

# 43. ClockingModel

Mögliche Typen:

```text
ASYNCHRONOUS
SOURCE_SYNCHRONOUS
COMMON_CLOCK
DISTRIBUTED_CLOCK
RECOVERED_CLOCK
```

Beispiele:

```text
UART
→ asynchronous

SPI
→ source synchronous

EtherCAT Distributed Clocks
→ distributed synchronization
```

---

# 44. EncodingModel

Mögliche Eigenschaften:

```text
line_code
symbol_rate
bits_per_symbol
scrambling
stuffing
coding_overhead
```

Wichtig für:

```text
real transmission time
physical bandwidth
frame overhead
```

---

# 45. CAN Bit Stuffing

CAN besitzt:

```text
bit stuffing
```

Daher:

```text
payload bits
≠
physical transmitted bits
```

Buslastberechnung muss Technologie-Overhead berücksichtigen.

---

# 46. Ethernet Overhead

Nicht nur Payload berücksichtigen.

Mögliche Overheads:

```text
Preamble
SFD
MAC Header
VLAN
FCS
Inter-Packet Gap
Protocol Headers
```

Capacity Engine muss TechnologyProfile-aware sein.

---

# 47. ConnectorProfile

Optional für spätere Erweiterung:

```text
ConnectorProfile
├── connector type
├── pin count
├── assigned signals
├── shielding
└── current / voltage constraints
```

Standard-UI muss das nicht anzeigen.

---

# 48. TransceiverProfile

Beispiel:

```text
CAN Transceiver
LIN Transceiver
RS-485 Transceiver
Ethernet PHY
```

Eigenschaften:

```text
supported rates
wake-up support
delay
voltage domain
standby mode
fault behavior
```

---

# 49. Wake-Up-Mechanismen

Relevant für:

```text
CAN
LIN
Automotive Ethernet
```

Mögliche Zustände:

```text
SLEEP
STANDBY
WAKE_REQUEST
ACTIVE
```

Das kann später Simulation und Power Management beeinflussen.

---

# 50. Shielding / Ground Reference

Nicht primär visualisieren.

Aber modellierbar:

```text
shielding_required
shielding_recommended
ground_reference_required
common_mode_constraints
```

---

# 51. Power over Medium

Beispiele:

```text
PoE
PoDL
IO-Link
sensor supply over cable
```

Optionales PhysicalLayer-Merkmal:

```text
power_over_medium = true
```

---

# 52. Hardware Capability muss Physical Realization begrenzen

Beispiel:

```text
Controller
CAN Controller:
2 channels

Physical Ports:
2
```

NIS darf keinen dritten CAN-Kanal erfinden.

Beispiel:

```text
Ethernet PHY:
1 × 100BASE-T1
```

NIS darf daraus nicht:

```text
4 independent Ethernet physical links
```

machen.

---

# 53. HardwareInterface vs PhysicalPort

Weiterhin trennen:

```text
HardwareNode
↓
CommunicationCapability
↓
CommunicationController
↓
HardwareInterface
↓
PhysicalPort
↓
PhysicalRealization
↓
Network
```

---

# 54. Physical Channel Capacity

Ein Controller kann z. B.:

```text
CAN Controller
max_channels = 2
```

haben.

Wenn:

```text
used_channels = 2
```

dann:

```text
new physical CAN channel
→ BLOCKED
```

Finding:

```text
PHYSICAL_CHANNEL_CAPACITY_EXCEEDED
```

---

# 55. Physical Realization darf versteckt bleiben

Standardansicht:

```text
[ECU A] ───── CAN-FD ───── [ECU B]
```

Keine Darstellung von:

```text
CAN_H
CAN_L
termination
shield
connector pins
```

im normalen Architekturdiagramm.

---

# 56. Optionale Detailansicht

Optional:

```text
Connection Details
```

Beispiel:

```text
Technology:
CAN-FD

PHY:
CAN Differential PHY

Medium:
Twisted Pair

Conductors:
2

Signals:
CAN_H
CAN_L

Termination:
2 × 120 Ω

Topology:
Bus

Arbitration:
Bitwise Priority

Rate:
500 kbit/s nominal
2 Mbit/s data
```

---

# 57. Abstraktionsregel

```text
DISPLAY MODEL
≠
PHYSICAL MODEL
```

Aber:

```text
DISPLAY MODEL
→ references
→ PHYSICAL MODEL
```

Diagramme sind Sichten.

Die technische Wahrheit liegt im Core.

---

# 58. Validierungsbeispiele

## Beispiel A – LIN mit CAN-Rate

```text
LIN
2 Mbit/s
```

→

```text
TECHNOLOGY_PARAMETER_OUT_OF_RANGE
```

---

## Beispiel B – CAN mit falscher Terminierung

```text
CAN
3 × 120 Ω
```

→

```text
PHYSICAL_TERMINATION_INVALID
```

---

## Beispiel C – RS-485 Star mit langen Stubs

→

```text
PHYSICAL_TOPOLOGY_RISK
```

---

## Beispiel D – 100BASE-T1 mit 4-Pair-Profil

→

```text
PHY_MEDIUM_MISMATCH
```

---

## Beispiel E – SPI mit zu wenig Chip Selects

→

```text
PHYSICAL_CHANNEL_CAPACITY_EXCEEDED
```

---

# 59. Finding-Typen

Mindestens:

```text
PHYSICAL_PROFILE_MISSING
PHY_MEDIUM_MISMATCH
PHYSICAL_TOPOLOGY_INVALID
PHYSICAL_TOPOLOGY_RISK
PHYSICAL_TERMINATION_MISSING
PHYSICAL_TERMINATION_INVALID
PHYSICAL_TERMINATION_PLACEMENT_INVALID
PHYSICAL_CHANNEL_CAPACITY_EXCEEDED
PHYSICAL_PORT_INCOMPATIBLE
ARBITRATION_MODEL_MISMATCH
DUPLEX_MODEL_MISMATCH
PROPAGATION_LIMIT_EXCEEDED
STUB_LENGTH_EXCEEDED
BUS_LENGTH_EXCEEDED
TRANSCEIVER_RATE_EXCEEDED
CLOCKING_MODEL_INVALID
```

---

# 60. MCP-Erweiterung

Empfohlene MCP-Tools:

```text
physical.get_profile
physical.get_realization
physical.validate_realization
physical.get_medium
physical.get_topology
physical.get_termination
physical.get_propagation
physical.get_transceiver
physical.get_port_constraints

arbitration.get_model
arbitration.calculate_delay
arbitration.validate

timing.calculate_physical_delay
timing.calculate_end_to_end
```

---

# 61. Python Core Services

Empfohlene Services:

```text
PhysicalLayerProfileRegistry
PhysicalRealizationResolver
PhysicalConstraintValidator
MediumAccessResolver
ArbitrationModelResolver
ArbitrationDelayCalculator
TopologyValidator
TerminationValidator
PropagationCalculator
TransceiverCapabilityValidator
PhysicalImpactResolver
```

---

# 62. Datenmodell – PhysicalLayerProfile

```text
PhysicalLayerProfile
├── id
├── technology_profile_id
├── medium_type
├── conductor_model
├── pair_model
├── differential
├── duplex_model
├── topology_constraints
├── termination_model
├── propagation_model
├── transceiver_constraints
├── encoding_model
├── clocking_model
└── version
```

---

# 63. Datenmodell – PhysicalRealization

```text
PhysicalRealization
├── id
├── connection_id
├── physical_layer_profile_id
├── ports[]
├── channels[]
├── media[]
├── pairs[]
├── conductors[]
├── terminations[]
├── transceivers[]
├── topology
├── length
├── validation_status
└── revision
```

---

# 64. Datenmodell – ArbitrationModel

```text
ArbitrationModel
├── id
├── type
├── priority_model
├── deterministic
├── destructive_collision
├── retry_model
├── blocking_model
├── timing_parameters
└── calculator_id
```

---

# 65. TechnologyProfile-Verknüpfung

Beispiel:

```text
CAN_FD
├── RateModel = MULTI_PHASE_BITRATE
├── MediumAccessModel = BITWISE_PRIORITY
├── ArbitrationModel = NON_DESTRUCTIVE
├── PhysicalLayerProfile = CAN_DIFFERENTIAL_PAIR
└── Integrity = CAN_FD_CRC
```

LIN:

```text
LIN
├── RateModel = SINGLE_BITRATE
├── MediumAccessModel = MASTER_SCHEDULED
├── ArbitrationModel = NONE
├── PhysicalLayerProfile = LIN_SINGLE_WIRE
└── Integrity = PID_PARITY + CHECKSUM
```

---

# 66. Layer-Vererbung

Vermeide Duplikate.

Beispiel:

```text
CANopen
↓
CAN Data Link
↓
CAN PhysicalLayerProfile
```

J1939:

```text
J1939
↓
CAN Data Link
↓
CAN PhysicalLayerProfile
```

NMEA 2000:

```text
NMEA2000
↓
CAN/J1939-compatible lower layers
```

---

# 67. Capacity Engine Erweiterung

Capacity darf nicht nur mit:

```text
payload / bitrate
```

arbeiten.

Mindestens:

```text
payload
+
protocol overhead
+
framing overhead
+
coding overhead
+
arbitration
+
schedule
```

berücksichtigen.

---

# 68. Timing Engine Erweiterung

Neue Timingkette:

```text
Application Release
↓
Queue
↓
Arbitration / Schedule
↓
Serialization
↓
PHY Delay
↓
Propagation
↓
Switch / Gateway
↓
Receiver Processing
```

---

# 69. Simulation Erweiterung

Simulation kann PhysicalLayer-Effekte optional berücksichtigen:

```text
bus contention
arbitration delay
link down
transceiver unavailable
termination fault
signal quality degradation
propagation delay
port failure
```

Nicht alles muss in Phase 1 numerisch hochgenau simuliert werden.

---

# 70. Realism Levels

Empfohlen:

```text
PHYSICAL_EXACT
PHYSICAL_PARAMETERIZED
RULE_BASED
GENERIC_ESTIMATE
NOT_MODELED
```

Damit bleibt transparent, wie realistisch die Physical Simulation ist.

---

# 71. UI-Abstraktion

Standard:

```text
Technology Connection
```

Optional:

```text
Show Physical Details
```

oder:

```text
Physical Layer Inspector
```

Keine Pflichtdarstellung aller Leiter im normalen Diagramm.

---

# 72. Harness-/Cable Engineering später möglich

Durch:

```text
PhysicalMedium
Pair
Conductor
Connector
Pin
```

kann später optional:

```text
Cable Harness
Cable Length
Connector Mapping
Pin Assignment
Mass
Cost
```

ergänzt werden.

Das ist jedoch nicht Bestandteil der Standarddarstellung.

---

# 73. Regressionstests – PHY

Mindestens:

```text
TC-PHY-001
CAN
→ 2 conductors CAN_H/CAN_L

TC-PHY-002
CAN
→ differential = true

TC-PHY-003
LIN
→ single data conductor

TC-PHY-004
100BASE-TX
→ 2 pairs

TC-PHY-005
1000BASE-T
→ 4 pairs

TC-PHY-006
100BASE-T1
→ 1 pair

TC-PHY-007
SPI
→ SCLK/MOSI/MISO/CS

TC-PHY-008
I2C
→ SDA/SCL + open-drain model

TC-PHY-009
RS-485 2-wire
→ one differential pair

TC-PHY-010
RS-422 full duplex
→ TX pair + RX pair
```

---

# 74. Regressionstests – Arbitration

```text
TC-ARB-001
CAN
→ bitwise non-destructive arbitration

TC-ARB-002
LIN
→ master scheduled

TC-ARB-003
I2C
→ wired-AND arbitration

TC-ARB-004
FlexRay static
→ TDMA

TC-ARB-005
FlexRay dynamic
→ minislot model

TC-ARB-006
Switched Ethernet
→ full duplex / no CSMA-CD arbitration

TC-ARB-007
PROFIBUS multi-master
→ token passing

TC-ARB-008
EtherCAT
→ point-to-point forwarding model
```

---

# 75. Regressionstests – Physical Constraints

```text
TC-PHYC-001
CAN missing termination
→ FAIL

TC-PHYC-002
CAN three terminations
→ FAIL

TC-PHYC-003
RS-485 excessive stub
→ WARNING / FAIL by profile

TC-PHYC-004
CAN controller no free channel
→ BLOCKED

TC-PHYC-005
100BASE-T1 with incompatible port
→ BLOCKED

TC-PHYC-006
SPI slaves > available chip selects
→ BLOCKED

TC-PHYC-007
bus length exceeds technology profile
→ FAIL
```

---

# 76. Tool Checker Integration

Tool Checker muss zusätzlich prüfen:

```text
TechnologyProfile
PhysicalLayerProfile
ArbitrationModel
PhysicalRealization
Hardware Capability
Port Compatibility
Termination
Topology
Timing Impact
```

---

# 77. Positive Test

Beispiel CAN-FD:

```text
Technology = CAN-FD
Nominal Rate = 500 kbit/s
Data Rate = 2 Mbit/s
PHY = differential twisted pair
Termination = 2 × 120 Ω
Topology = bus
Arbitration = bitwise priority
```

→

```text
PASS
```

---

# 78. Negative Test

Beispiel:

```text
Technology = LIN
Rate = 2 Mbit/s
PHY = CAN differential pair
Arbitration = CAN bitwise
```

→

```text
TECHNOLOGY_PARAMETER_OUT_OF_RANGE
PHY_MEDIUM_MISMATCH
ARBITRATION_MODEL_MISMATCH
```

→

```text
Simulation Preflight = FAIL
```

---

# 79. Physical Profile Audit

Bestehende Projekte prüfen:

```text
PhysicalRealizationAudit
```

Audit:

```text
technology
rate model
medium
pair count
conductor model
termination
topology
port capability
arbitration
```

---

# 80. Keine automatische Erfindung fehlender Hardware

Wenn:

```text
CAN network exists
```

aber:

```text
controller has no CAN transceiver
```

nicht automatisch:

```text
CAN transceiver generated
```

Sondern:

```text
HARDWARE_CAPABILITY_MISSING
```

oder Engineering Proposal.

---

# 81. Engineering Agent

Agent muss bei Fragen wie:

```text
"Kann dieser Controller an CAN-FD angeschlossen werden?"
```

prüfen:

```text
Controller Capability
CAN Controller
Free Channel
Transceiver
Physical Port
PHY Compatibility
Network Compatibility
```

Nicht nur:

```text
technology string matches
```

---

# 82. Codex-Arbeitsauftrag

```text
Extend the NIS technology architecture with a hidden physical realization layer.

The normal UI must stay abstract.
One displayed connection line may represent multiple physical conductors,
pairs, channels, terminations and PHY elements.

Implement:

- PhysicalLayerProfile
- PhysicalRealization
- PhysicalMedium
- PhysicalChannel
- Pair
- Conductor
- MediumAccessModel
- ArbitrationModel
- TopologyModel
- TerminationModel
- PropagationModel
- DuplexModel
- ClockingModel
- EncodingModel
- TransceiverProfile

Bind them to TechnologyProfile.

Do not duplicate lower-layer rules in higher-level protocols.
Use layer inheritance / composition.

Examples:
- CANopen → CAN lower layers
- J1939 → CAN lower layers
- PROFINET → Ethernet lower layers
- Modbus TCP → TCP/IP/Ethernet lower layers

The UI must not display CAN_H/CAN_L or all cable conductors
in normal engineering diagrams.

Instead, expose them through an optional Physical Layer Inspector.

Use physical rules in:
- validation,
- capacity,
- timing,
- simulation preflight,
- simulation,
- trace analysis,
- Engineering Agent reasoning.

Include arbitration and medium-access delays in end-to-end timing.

Reject impossible combinations before simulation.

Do not silently invent missing transceivers, channels, ports or terminations.

Audit existing projects for invalid physical realizations.

Create regression tests for:
- PHY conductor counts,
- pair counts,
- topology,
- termination,
- arbitration,
- hardware channel capacity,
- technology/PHY mismatches.
```

---

# 83. Definition of Done

Die Erweiterung gilt als abgeschlossen, wenn:

1. `PhysicalLayerProfile` existiert.
2. `PhysicalRealization` existiert.
3. `MediumAccessModel` existiert.
4. `ArbitrationModel` existiert.
5. CAN_H/CAN_L intern modellierbar sind.
6. LIN als Single-Wire-Realization modellierbar ist.
7. Ethernet PHY-Varianten unterscheidbar sind.
8. SPI mehrere physische Leitungen berücksichtigt.
9. I²C SDA/SCL berücksichtigt.
10. RS-485 und RS-422 unterschieden werden.
11. FlexRay A/B-Kanäle berücksichtigt werden.
12. EtherCAT nicht wie Shared CAN behandelt wird.
13. PROFINET Ethernet-Lower-Layer referenziert.
14. Topology Constraints validiert werden.
15. Termination Constraints validiert werden.
16. Hardware-Port-/Channel-Limits geprüft werden.
17. Arbitration Delay in Timing eingehen kann.
18. PHY-/Propagation Delay in E2E-Timing eingehen kann.
19. Capacity Technology-Overhead berücksichtigt.
20. Simulation Preflight physikalisch unmögliche Konfigurationen blockiert.
21. UI weiterhin abstrahiert bleibt.
22. Physical Layer Inspector optional verfügbar ist.
23. bestehende Projekte auditierbar sind.
24. Tool Checker PHY-/Arbitration-Tests enthält.
25. keine technisch unmögliche PhysicalRealization als PASS gelten kann.

---

# 84. Leitregel

```text
VISIBLE CONNECTION
≠
ONE WIRE
```

Sondern:

```text
VISIBLE CONNECTION
↓
TECHNOLOGY
↓
MEDIUM ACCESS / ARBITRATION
↓
PHY
↓
PHYSICAL REALIZATION
↓
REAL HARDWARE CONSTRAINTS
```

> **Der Simulator darf die physikalische Realität abstrahieren, aber nicht ignorieren.**
