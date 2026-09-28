# Network Intelligence Simulator (NIS)
## Device Class 0–4, Direct I/O & Technology Binding
## NIS-spezifische Umsetzung für Sensoren, Aktoren, Smart Devices und Subsysteme

---

# 1. Ziel

NIS soll Geräteklassen und Kommunikationstechnologien fachlich sauber trennen.

Insbesondere gilt:

```text
Device Class
≠
Technology
```

Die Device Class beschreibt:

```text
Komplexität
Eigenintelligenz
Datencharakter
Kommunikationsfähigkeit
Verarbeitungsgrad
```

Die Technology beschreibt:

```text
wie das Gerät technisch angebunden ist
```

---

# 2. Geräteklassen

## Class 0 – Passive

Typische Geräte:

```text
passiver Schalter
Widerstandssensor
PT100/PT1000
Potentiometer
passiver Geber
```

Typische Anbindung:

```text
Analog Input
Digital Input
GPIO
```

Kein eigener Kommunikationsstack.

---

## Class 1 – Basic

Typische Geräte:

```text
einfacher Sensor
einfacher Aktor
Relais
Ventil
PWM-Aktor
einfacher digitaler Sensor
```

Typische Anbindung:

```text
GPIO
PWM
Analog I/O
Digital I/O
einfache serielle Verbindung
LIN möglich
```

---

## Class 2 – Smart / Controlled

Typische Geräte:

```text
intelligenter Sensor
Smart Actuator
Sensor mit eigener Elektronik
Sensor mit internem ADC
intelligentes Ventil
Motorcontroller
IO-Link Device
```

Typische Technologien:

```text
I2C
SPI
LIN
CAN
CAN-FD
IO-Link
RS-485
Modbus RTU
```

---

## Class 3 – Perception / Intelligent

Typische Geräte:

```text
Kamera
LiDAR
Radar
komplexe Sensorik
Edge Sensor
intelligente Perception Unit
```

Typische Technologien:

```text
Ethernet
Automotive Ethernet
DDS
SOME/IP
CAN-FD
High-Speed Serial
```

---

## Class 4 – Intelligent Subsystem

Typische Geräte:

```text
ECU
PLC
Gateway
Edge Computer
HPC
Domain Controller
Central Computer
Subsystem Controller
```

Typische Technologien:

```text
Ethernet
CAN-FD
EtherCAT
PROFINET
DDS
OPC UA
Modbus TCP
mehrere Technologien gleichzeitig
```

---

# 3. Zentrale NIS-Regel

Die Device Class darf niemals automatisch eine konkrete Technology erzwingen.

Nicht:

```text
Class 2
→ CAN-FD
```

Sondern:

```text
Device Class
↓
Technology Candidates
↓
Capability / Hardware Interface
↓
Engineering Decision / Existing Model
↓
Technology Binding
```

---

# 4. Direct I/O als eigene Kategorie

NIS benötigt eine explizite Kategorie:

```text
DIRECT_IO
```

für:

```text
GPIO
Digital Input
Digital Output
PWM
Analog Input
Analog Output
```

Diese Verbindungen sind keine klassischen Kommunikationsbusse.

---

# 5. Direct I/O – Capacity

Für klassische Buslast gilt:

```text
GPIO
PWM
Analog I/O
Digital I/O
```

→

```text
Capacity = NOT_APPLICABLE
```

Nicht:

```text
Capacity = 0 %
```

und nicht:

```text
Capacity = UNVERIFIED
```

wenn Buslast fachlich nicht anwendbar ist.

---

# 6. Direct I/O – Timing

Timing kann trotzdem relevant sein.

Beispiele:

```text
GPIO edge propagation
PWM period
ADC sample time
DAC update time
digital debounce
driver latency
```

Daher:

```text
Capacity = NOT_APPLICABLE
Timing = SUPPORTED / UNVERIFIED
```

abhängig vom vorhandenen Modell.

---

# 7. I2C / SPI sind keine Direct-I/O-Bypass-Fälle

I2C und SPI haben:

```text
Clock
Protocol Semantics
Transfer Time
Bus/Channel Capacity
```

Deshalb:

```text
I2C
SPI
```

→

```text
Capacity = SUPPORTED
```

wenn Technology Model vorhanden.

Sonst:

```text
Capacity = UNVERIFIED
```

Nicht:

```text
NOT_APPLICABLE
```

---

# 8. I2C Capability Model

Mindestens:

```text
clock_frequency
addressing
start_condition
stop_condition
ack_nack
transfer_direction
clock_stretching
multi_master
arbitration
```

Capacity:

```text
bits_per_transaction
/
clock_frequency
```

plus Protokolloverhead.

Timing:

```text
Start
Address
ACK
Payload
ACK/NACK
Stop
Clock Stretch
```

---

# 9. SPI Capability Model

Mindestens:

```text
clock_frequency
chip_select
word_length
duplex_mode
transfer_length
CPOL
CPHA
```

Capacity:

```text
transferred_bits
/
clock_frequency
```

Timing abhängig von:

```text
CS setup
word length
clock
duplex
inter-transfer gaps
```

---

# 10. LIN / CAN / RS-485

Class 1–2 Geräte können echte Buskommunikation verwenden.

Dann gelten normale:

```text
TechnologyProfile
Capacity
Timing
PHY
Validation
```

Regeln.

---

# 11. Physical Realization

Bei Direct I/O:

```text
Logical Signal
↓
Hardware Port
↓
Physical Conductor
```

Beispiel:

```text
PressureSwitch
→ Digital Input
→ GPIO Port
→ 1 Signal Line
```

Bei CAN:

```text
Logical Communication
↓
CAN Interface
↓
CAN PHY
↓
CAN_H / CAN_L
```

---

# 12. DeviceClassProfile

Einführung:

```text
DeviceClassProfile
```

Felder:

```text
class_id
name
description
typical_device_types[]
allowed_data_complexities[]
typical_connection_types[]
requires_controller
supports_local_processing
supports_network_stack
supports_diagnostics
supports_multiple_interfaces
```

---

# 13. TechnologyCandidateResolver

NIS soll einen:

```text
TechnologyCandidateResolver
```

verwenden.

Input:

```text
Device Class
Data Complexity
Cycle Time
Required Bandwidth
Distance
Topology
Existing Hardware Capabilities
Existing Network
```

Output:

```text
Technology Candidates
```

Nicht direkt:

```text
final technology
```

---

# 14. Beispiel – Class 0

```text
PT100
```

→

```text
Class 0
```

mögliche technische Realisierung:

```text
PT100
↓
Analog Frontend
↓
ADC
↓
Controller
```

Kein künstlicher Bus.

---

# 15. Beispiel – Class 1

```text
PWM Ventil
```

→

```text
Class 1
```

Binding:

```text
PWM Output
```

Capacity:

```text
NOT_APPLICABLE
```

Timing:

```text
PWM period / update latency
```

---

# 16. Beispiel – Class 2

```text
Smart Pressure Sensor
```

mögliche Kandidaten:

```text
I2C
SPI
IO-Link
CAN
RS-485
```

Auswahl abhängig von:

```text
Hardware
Distance
Cycle
Data Volume
Topology
```

---

# 17. Beispiel – Class 3

```text
Camera
```

→

```text
Class 3
```

Data Complexity:

```text
IMAGE_STREAM
```

Technology Candidate:

```text
Ethernet
```

Nicht:

```text
LIN
```

nur weil LIN vorhanden ist.

---

# 18. Beispiel – Class 4

```text
Gateway
```

→

```text
Class 4
```

kann besitzen:

```text
CAN-FD
LIN
Ethernet
RS-485
```

gleichzeitig.

---

# 19. Data Complexity als zweite Achse

Die Device Class reicht allein nicht.

Zusätzlich:

```text
DataComplexity
```

mindestens:

```text
BOOLEAN
SCALAR
ENUM
STATE
MULTI_VALUE
STRUCTURED_OBJECT
STRUCTURED_OBJECT_LIST
IMAGE
IMAGE_STREAM
AUDIO
POINT_CLOUD
COMMAND
EVENT
SERVICE
```

---

# 20. Class × Data Complexity

Beispiel:

```text
Class 2
+
SCALAR
→ I2C / SPI / LIN / CAN / IO-Link möglich
```

```text
Class 3
+
IMAGE_STREAM
→ Ethernet / High-Speed Link
```

---

# 21. Hardware Capability bleibt entscheidend

Keine Technology-Auswahl ohne:

```text
Hardware Capability
```

Beispiel:

```text
Controller has no I2C controller
```

→

```text
I2C not selectable
```

---

# 22. NIS Core Chain

Für Class 0–2:

```text
Device
↓
DeviceClass
↓
Function
↓
Signal / DataObject
↓
Connection Type
↓
Hardware Capability
↓
Physical Port
↓
Technology Binding / Direct IO
```

---

# 23. DirectSignalBinding

Einführung:

```text
DirectSignalBinding
```

für:

```text
GPIO
PWM
Analog
Digital
```

Beispiel:

```text
DirectSignalBinding
├── source
├── destination
├── port
├── signal_type
├── electrical_profile
├── update_rate
├── timing_profile
└── validation_status
```

---

# 24. Keine Message für Direct I/O

Nicht:

```text
GPIO
→ Message
→ TransportUnit
```

wenn fachlich kein Protokoll existiert.

Sondern:

```text
Signal
→ DirectSignalBinding
```

---

# 25. Keine künstliche Buslast

Direct I/O:

```text
GPIO
PWM
Analog
Digital
```

dürfen nicht durch:

```text
Capacity Engine
```

wie CAN/Ethernet gerechnet werden.

---

# 26. Validation

Neue Regeln:

```text
DIRECT_IO_MESSAGE_CREATED
→ FAIL

DIRECT_IO_CAPACITY_CALCULATED
→ FAIL

BUS_TECHNOLOGY_WITHOUT_CAPACITY_MODEL
→ UNVERIFIED

BUS_TECHNOLOGY_WITHOUT_TIMING_MODEL
→ UNVERIFIED
```

---

# 27. Device Class Validation

Beispiele:

```text
Class 0 Camera
→ DEVICE_CLASS_MISMATCH
```

```text
Class 4 passive switch
→ DEVICE_CLASS_MISMATCH
```

---

# 28. Technology Suitability

Beispiele:

```text
IMAGE_STREAM over LIN
→ DATA_COMPLEXITY_TECHNOLOGY_MISMATCH
```

```text
simple boolean sensor over GPIO
→ VALID
```

---

# 29. Wizard Verhalten

Wenn Nutzer Gerät anlegt:

```text
Device Type
↓
Class Proposal
↓
Data Complexity
↓
Connection Candidates
```

Nicht:

```text
Device Type
↓
hardcoded CAN
```

---

# 30. Engineering Assistant Verhalten

Beispiel:

```text
"Lege einen einfachen Endschalter an."
```

Assistant soll typisieren:

```text
Class 0 / 1
BOOLEAN
Digital Input
```

wenn Hardware dies unterstützt.

---

# 31. Engineering Assistant – Smart Sensor

```text
"Lege einen intelligenten Drucksensor an."
```

Assistant:

```text
Class 2
PHYSICAL_SCALAR
```

und prüft:

```text
I2C
SPI
IO-Link
CAN
RS-485
```

gegen vorhandene Hardware.

---

# 32. Kein unnötiger Nutzerentscheid

Wenn nur eine technisch valide Option existiert:

```text
automatisch verwenden
```

Wenn mehrere:

```text
Engineering Decision
```

---

# 33. Technology Capability Registry

DeviceClass-Logik wird mit:

```text
TechnologyCapabilityRegistry
```

verbunden.

Jede Technology kennt:

```text
supported_device_classes[]
supported_data_complexities[]
capacity_status
timing_status
simulation_status
```

---

# 34. Beispiel I2C Registry

```yaml
canonical_id: i2c
display_name: I²C

supported_device_classes:
  - CLASS_1
  - CLASS_2

supported_data_complexities:
  - BOOLEAN
  - SCALAR
  - ENUM
  - STATE
  - MULTI_VALUE

capacity:
  status: SUPPORTED

timing:
  status: SUPPORTED
```

---

# 35. Beispiel GPIO Registry

```yaml
canonical_id: gpio
display_name: GPIO

classification:
  type: DIRECT_IO

supported_device_classes:
  - CLASS_0
  - CLASS_1

capacity:
  status: NOT_APPLICABLE

timing:
  status: PARAMETERIZED
```

---

# 36. Beispiel Ethernet Registry

```yaml
canonical_id: ethernet
display_name: Ethernet

supported_device_classes:
  - CLASS_2
  - CLASS_3
  - CLASS_4
```

Class 2 nur wenn Gerät:

```text
Smart / Network-capable
```

---

# 37. Mapping ist keine harte Ausschlussliste

`supported_device_classes` darf als:

```text
default suitability
```

dienen.

Ausnahmen müssen möglich sein, wenn Hardware-/Gerätespezifikation sie explizit zulässt.

---

# 38. Preflight

Preflight prüft:

```text
Device Class valid
Data Complexity valid
Technology suitable
Hardware Capability valid
Physical Port valid
Capacity applicable/supported
Timing supported
```

---

# 39. Preflight Example

```text
Class 1 PWM Valve
```

Ergebnis:

```text
Device Class: READY
Connection: DIRECT_IO
Capacity: NOT_APPLICABLE
Timing: READY
Simulation: READY
```

---

# 40. Preflight Example I2C

```text
Class 2 Pressure Sensor
Technology: I2C
```

Ergebnis:

```text
Device Class: READY
Technology: READY
Capacity: READY
Timing: READY
```

wenn Parameter vollständig sind.

---

# 41. Fehlende Clock Frequency

```text
I2C
clock_frequency = UNKNOWN
```

Ergebnis:

```text
Capacity: UNVERIFIED
Timing: UNVERIFIED
Preflight: BLOCKED / REVIEW_REQUIRED
```

Nicht:

```text
400 kHz default
```

sofern nicht explizit aus Hardwareprofil bestätigt.

---

# 42. Testfälle

Mindestens:

```text
TC-CLASS-001
Class 0 analog sensor
→ Direct I/O

TC-CLASS-002
Class 1 PWM actuator
→ Direct I/O

TC-CLASS-003
Class 2 I2C sensor
→ bus capacity/timing

TC-CLASS-004
Class 2 SPI actuator
→ bus capacity/timing

TC-CLASS-005
Class 3 camera
→ Ethernet candidate

TC-CLASS-006
Class 4 gateway
→ multi-interface

TC-CLASS-007
GPIO
→ Capacity NOT_APPLICABLE

TC-CLASS-008
PWM
→ Capacity NOT_APPLICABLE

TC-CLASS-009
I2C missing clock
→ UNVERIFIED

TC-CLASS-010
SPI missing clock
→ UNVERIFIED
```

---

# 43. Negative Tests

```text
TC-CLASS-N01
Image Stream over GPIO
→ FAIL

TC-CLASS-N02
Camera over LIN
→ FAIL / REVIEW

TC-CLASS-N03
GPIO generates TransportUnit
→ FAIL

TC-CLASS-N04
PWM busload calculated
→ FAIL

TC-CLASS-N05
I2C silently assumes rate
→ FAIL
```

---

# 44. Tool Checker Integration

Tool Checker muss prüfen:

```text
DeviceClass
DataComplexity
ConnectionType
TechnologyBinding
HardwareCapability
CapacityStatus
TimingStatus
```

---

# 45. Mandatory Assertions

```text
direct_io_not_treated_as_bus = true
capacity_not_applicable_for_direct_io = true
i2c_spi_not_marked_not_applicable = true
technology_selection_matches_class_and_data = true
hardware_capability_respected = true
hidden_default_rate = false
```

---

# 46. UI

Standardansicht bleibt einfach.

Beispiel:

```text
PressureSensor ─── Controller
```

Details optional:

```text
Class: 2
Connection: I2C
Clock: 400 kHz
Capacity: VERIFIED
Timing: VERIFIED
```

---

# 47. Keine unnötige technische Überladung

Für Class 0:

```text
Switch
→ Digital Input
```

Nicht im UI:

```text
Pseudo-Network
Pseudo-Message
Pseudo-Busload
```

---

# 48. Architekturziel

```text
DEVICE
↓
DEVICE CLASS
↓
DATA COMPLEXITY
↓
CONNECTION TYPE
├── DIRECT IO
└── COMMUNICATION TECHNOLOGY
↓
HARDWARE CAPABILITY
↓
PHYSICAL REALIZATION
↓
CAPACITY / TIMING
```

---

# 49. Codex-Arbeitsauftrag

```text
Implement NIS-specific Device Class 0–4 handling.

Do not map device class directly to a fixed technology.

Introduce:
- DeviceClassProfile
- DataComplexity
- ConnectionType
- DirectSignalBinding
- TechnologyCandidateResolver

Treat:
GPIO
PWM
Analog I/O
Digital I/O

as DIRECT_IO.

For DIRECT_IO:
Capacity = NOT_APPLICABLE.

Do not generate TransportUnits or artificial busload.

Timing may still be modeled.

Treat:
I2C
SPI

as real serial communication technologies.

For I2C/SPI:
Capacity and Timing must be technology-specific.

If required parameters such as clock frequency are missing:
Capacity = UNVERIFIED
Timing = UNVERIFIED

Do not silently apply default rates.

Connect DeviceClassProfile with TechnologyCapabilityRegistry.

Technology selection must consider:
- Device Class
- Data Complexity
- Hardware Capability
- Existing Interfaces
- Distance
- Cycle Time
- Bandwidth
- Topology

Add Validation and Preflight rules.

Update Wizard and Engineering Assistant behavior.

Add Tool Checker tests.

Do not introduce a parallel data model.
Use the canonical NIS model.
```

---

# 50. Definition of Done

Die Umsetzung ist fertig, wenn:

1. Class 0–4 im Core definiert sind.
2. DeviceClassProfile existiert.
3. DataComplexity integriert ist.
4. ConnectionType existiert.
5. DIRECT_IO existiert.
6. GPIO als Direct I/O behandelt wird.
7. PWM als Direct I/O behandelt wird.
8. Analog I/O als Direct I/O behandelt wird.
9. Digital I/O als Direct I/O behandelt wird.
10. Direct I/O keine künstliche Buslast erzeugt.
11. Direct I/O keine künstlichen TransportUnits erzeugt.
12. Capacity für Direct I/O `NOT_APPLICABLE` ist.
13. Timing für Direct I/O separat modellierbar ist.
14. I2C als echte Kommunikationstechnologie behandelt wird.
15. SPI als echte Kommunikationstechnologie behandelt wird.
16. I2C Capacity/Timing technologiespezifisch ist.
17. SPI Capacity/Timing technologiespezifisch ist.
18. fehlende Clockrate zu `UNVERIFIED` führt.
19. Device Class keine feste Technology erzwingt.
20. TechnologyCandidateResolver existiert.
21. Hardware Capability berücksichtigt wird.
22. Data Complexity berücksichtigt wird.
23. Class 3 datenintensive Geräte korrekt behandelt werden.
24. Class 4 Multi-Interface unterstützt.
25. Wizard die neue Logik verwendet.
26. Engineering Assistant die neue Logik verwendet.
27. Preflight Class/Technology/Capability prüft.
28. Tool Checker passende Regressionstests enthält.
29. keine versteckten Rate-Fallbacks existieren.
30. `UNKNOWN / UNVERIFIED` vor falschem Default gilt.

---

# 51. Leitregel

```text
DEVICE CLASS
≠
TECHNOLOGY
```

Sondern:

```text
DEVICE
↓
CLASS
↓
DATA COMPLEXITY
↓
CONNECTION TYPE
↓
HARDWARE CAPABILITY
↓
TECHNOLOGY / DIRECT IO
↓
PHYSICAL REALIZATION
↓
VALIDATION
```

> **Einfache Class-0/1-Geräte sollen in NIS nicht künstlich zu Netzwerkteilnehmern gemacht werden. Class-2-Geräte können echte serielle/basierte Kommunikation nutzen. Class-3/4-Geräte erhalten entsprechend ihrer Datenkomplexität und Hardwarefähigkeiten leistungsfähigere Kommunikationstechnologien.**
