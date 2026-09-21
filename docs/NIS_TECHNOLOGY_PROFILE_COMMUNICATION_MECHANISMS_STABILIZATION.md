# Network Intelligence Simulator (NIS)
## Technology Profile & Communication Mechanisms Stabilization
## Ziel: Technologisch korrekte Parameter, harte Validierung und stabile Simulation

---

# 1. Ausgangslage

Im Simulator ist aufgefallen, dass ein **LIN-Netz mit einer CAN-/CAN-FD-Geschwindigkeit dargestellt wurde**.

Beispiel:

```text
korrekt:
LIN = 19.200 bit/s = 19,2 kbit/s

fehlerhaft:
LIN = 2.000.000 bit/s = 2 Mbit/s
```

Das ist kein reiner Darstellungsfehler.

Ein falscher Technologieparameter kann Auswirkungen haben auf:

```text
Routing
Buslast
Capacity
Timing
Latency
Simulation
Trace
Root Cause Analysis
```

Deshalb muss die Technologiesemantik stabilisiert werden.

---

# 2. Grundregel

Nicht mehr:

```text
Network
├── technology = LIN
└── bitrate = 2000000
```

Sondern:

```text
Network
↓
TechnologyBinding
↓
TechnologyProfile
↓
Technology-specific Parameter Schema
↓
Validation
↓
Calculation Model
```

Zentrale Leitregel:

```text
TECHNOLOGY
→ DEFINES PARAMETER SCHEMA
→ DEFINES UNITS
→ DEFINES LIMITS
→ DEFINES COMMUNICATION MECHANISMS
→ DEFINES VALIDATION
→ DEFINES CALCULATION MODEL
```

---

# 3. TechnologyProfile als Single Source of Truth

Einführung einer zentralen Registry:

```text
TechnologyRegistry
├── LIN
├── CAN
├── CAN_FD
├── CANopen
├── J1939
├── Modbus_RTU
├── Modbus_TCP
├── PROFINET
├── EtherCAT
├── Ethernet
├── SOME_IP
├── DDS
├── NMEA_2000
├── BACnet
└── ...
```

Jede Technologie erhält ein eigenes:

```text
TechnologyProfile
```

mit:

```text
RateModel
ParameterSchema
UnitDefinitions
Constraints
IntegrityMechanisms
AddressingMechanisms
AddressResolutionMechanisms
DiscoveryMechanisms
DiagnosticMechanisms
SupervisionMechanisms
CalculationModel
ValidationRules
```

---

# 4. LIN TechnologyProfile

Beispiel:

```yaml
id: LIN
family: SERIAL_BUS

rate_model:
  type: SINGLE_BITRATE
  field: bitrate_bps
  maximum: 20000
  typical:
    - 9600
    - 19200

integrity:
  - PID_PARITY
  - LIN_CHECKSUM

addressing:
  type: FRAME_IDENTIFIER

diagnostics:
  - LIN_DIAGNOSTIC_TRANSPORT

discovery: []

supervision:
  - RESPONSE_TIMEOUT
  - SCHEDULE_MONITORING
```

Wichtig:

```text
typical != hardcoded default
```

Wenn der Nutzer:

```text
9600 bit/s
```

konfiguriert, darf NIS daraus nicht automatisch:

```text
19200 bit/s
```

machen.

---

# 5. CAN-FD TechnologyProfile

CAN-FD besitzt ein anderes RateModel als LIN.

Beispiel:

```yaml
id: CAN_FD
family: CAN

rate_model:
  type: MULTI_PHASE_BITRATE

  arbitration:
    field: nominal_bitrate_bps

  data_phase:
    field: data_bitrate_bps

integrity:
  - CAN_FD_CRC

addressing:
  type: CAN_IDENTIFIER

supervision:
  - ERROR_COUNTER
  - ERROR_ACTIVE
  - ERROR_PASSIVE
  - BUS_OFF
```

Damit kann ein LIN-Netz technisch nicht mehr versehentlich:

```text
data_bitrate_bps = 2_000_000
```

übernehmen.

---

# 6. Kanonische Einheit

Intern werden Datenraten ausschließlich als:

```text
bit/s
```

gespeichert.

Beispiele:

```text
LIN 19,2 kbit/s
→ 19_200 bit/s

CAN 500 kbit/s
→ 500_000 bit/s

CAN-FD 2 Mbit/s
→ 2_000_000 bit/s

Ethernet 100 Mbit/s
→ 100_000_000 bit/s

Ethernet 1 Gbit/s
→ 1_000_000_000 bit/s
```

Codebeispiel:

```python
LIN_19_2K = 19_200
CAN_500K = 500_000
CANFD_2M = 2_000_000
ETH_100M = 100_000_000
ETH_1G = 1_000_000_000
```

---

# 7. UI formatiert – Core speichert

Die UI darf die Werte lesbar darstellen:

```text
19_200
→ 19,2 kbit/s

500_000
→ 500 kbit/s

2_000_000
→ 2 Mbit/s

1_000_000_000
→ 1 Gbit/s
```

Nicht erlaubt:

```text
"19.2 kbit"
"2 Mbps"
"500 kbps"
```

als gemischte interne Speicherformate.

---

# 8. Technology-spezifische RateModels

Nicht jede Kommunikationstechnologie verwendet dieselbe Geschwindigkeitslogik.

Deshalb:

```text
RateModel
│
├── SINGLE_BITRATE
│   ├── LIN
│   ├── CAN
│   ├── Modbus RTU
│   └── RS-485
│
├── MULTI_PHASE_BITRATE
│   └── CAN-FD
│       ├── arbitration
│       └── data phase
│
├── FIXED_LINK_RATE
│   └── EtherCAT
│
├── ETHERNET_LINK_RATE
│   ├── 10 Mbit/s
│   ├── 100 Mbit/s
│   ├── 1 Gbit/s
│   └── ...
│
└── SCHEDULED_CAPACITY
    ├── FlexRay
    └── weitere zeitgesteuerte Systeme
```

---

# 9. Dynamische UI nach Technologie

## LIN

```text
Baudrate
[19,2 kbit/s]
```

## CAN-FD

```text
Nominal Bitrate
[500 kbit/s]

Data Bitrate
[2 Mbit/s]
```

## Ethernet

```text
Link Speed
[1 Gbit/s]
```

Nicht mehr:

```text
universelles Feld:
"Geschwindigkeit"
```

für alle Technologien.

---

# 10. Harte Technology Validation

Ein LIN-Netz mit 2 Mbit/s muss sofort blockiert werden.

Beispiel:

```python
if technology == LIN and bitrate_bps > 20_000:
    raise TechnologyParameterViolation(
        "LIN bitrate exceeds technology limit"
    )
```

Die produktive Umsetzung soll jedoch registry-basiert erfolgen:

```text
value
↓
TechnologyProfile
↓
ParameterConstraint
↓
TechnologyValidator
```

Nicht über eine immer größere:

```text
if LIN
if CAN
if CAN_FD
if ...
```

Struktur.

---

# 11. Finding bei ungültigen Parametern

Finding:

```text
TECHNOLOGY_PARAMETER_OUT_OF_RANGE
```

Beispiel:

```text
Network:
LIN_1

Technology:
LIN

Configured:
2.0 Mbit/s

Maximum allowed by profile:
20 kbit/s

Severity:
BLOCKER
```

---

# 12. Keine Berechnung mit ungültigen Technologieparametern

Nicht:

```text
LIN
bitrate = 2 Mbit/s
↓
Capacity Calculator
↓
Bus Load = 2 %
```

Sondern:

```text
Technology Binding
↓
Parameter Validation
↓
Unit Validation
↓
Technology Compatibility
↓
Capacity Calculation
↓
Timing Calculation
```

Regel:

```text
INVALID TECHNOLOGY PARAMETERS
→ NO CAPACITY RESULT
→ NO TIMING RESULT
→ SIMULATION PREFLIGHT FAIL
```

---

# 13. Kein technischer Fallback auf fremde Defaultwerte

Nicht erlaubt:

```text
Technology Profile fehlt
↓
Generic Default
↓
2 Mbit/s
```

Sondern:

```text
Technology Profile fehlt
↓
TECHNOLOGY_PROFILE_MISSING
↓
BLOCKED
```

Grundregel:

> **UNKNOWN ist besser als technisch falsche Daten.**

---

# 14. CommunicationMechanism – generische Modellierung

Die Technologiesemantik wird nicht nur über Geschwindigkeit definiert.

Einführung eines generischen Mechanismusmodells:

```text
CommunicationMechanism
│
├── IntegrityMechanism
│
├── AddressingMechanism
│
├── AddressResolutionMechanism
│
├── DiscoveryMechanism
│
├── DiagnosticMechanism
│
└── SupervisionMechanism
```

---

# 15. IntegrityMechanism

Beispiele:

```text
CRC
Checksum
FCS
Working Counter
Parity
```

Zuordnung:

```text
CAN / CAN-FD
→ CRC

LIN
→ PID Parity + Checksum

Ethernet
→ FCS / CRC

Modbus RTU
→ CRC16

EtherCAT
→ Ethernet FCS + Working Counter
```

---

# 16. AddressResolutionMechanism

Beispiele:

```text
ARP
IPv6 NDP
J1939 Address Claim
NMEA 2000 Address Claim
```

Diese Mechanismen beantworten unterschiedliche Varianten der Frage:

```text
Welche Adresse / Identität gehört zu welchem Teilnehmer?
```

---

# 17. DiscoveryMechanism

Beispiele:

```text
SOME/IP-SD
PROFINET DCP
DDS Discovery
BACnet Who-Is / I-Am
mDNS
```

Wichtig:

```text
Address Resolution
≠
Service Discovery
```

---

# 18. DiagnosticMechanism

Beispiele:

```text
UDS
OBD
J1939 DM
CANopen EMCY
CANopen SDO
PROFINET Diagnostics
Modbus Diagnostics
EtherCAT AL Status / CoE
```

---

# 19. SupervisionMechanism

Beispiele:

```text
Heartbeat
Watchdog
Liveliness
Timeout
Bus-Off
Error Counter
Schedule Monitoring
Working Counter
```

---

# 20. TechnologyProfile mit CommunicationMechanisms

Gesamtmodell:

```text
TechnologyProfile
│
├── RateModel
│
├── ParameterSchema
│
├── IntegrityMechanism
│   ├── CRC
│   ├── Checksum
│   ├── FCS
│   └── WorkingCounter
│
├── AddressingMechanism
│
├── AddressResolutionMechanism
│   ├── ARP
│   ├── NDP
│   └── Address Claim
│
├── DiscoveryMechanism
│   ├── SOME/IP-SD
│   ├── PROFINET DCP
│   ├── DDS Discovery
│   └── BACnet Who-Is / I-Am
│
├── DiagnosticMechanism
│   ├── UDS
│   ├── OBD
│   ├── J1939 DM
│   ├── CANopen EMCY
│   └── Modbus Diagnostics
│
└── SupervisionMechanism
    ├── Heartbeat
    ├── Watchdog
    ├── Liveliness
    ├── Timeout
    └── Bus-Off
```

---

# 21. Beispiel Ethernet

```text
Ethernet
├── MAC Address
├── FCS / CRC
│
IPv4
├── IP Address
├── ARP
├── ICMP
│
UDP / TCP
├── Ports
│
Application
├── SOME/IP
├── DoIP
└── UDS
```

Für IPv6:

```text
IPv4 → ARP
IPv6 → NDP
```

---

# 22. Beispiel CAN / CAN-FD

```text
CAN / CAN-FD
├── Identifier
├── CRC
├── ACK
├── Error Frame
├── Error Counter
├── Error Active
├── Error Passive
└── Bus-Off
```

Bei höherem Protokoll:

```text
UDS
↓
ISO-TP
↓
CAN / CAN-FD
```

---

# 23. Beispiel J1939

```text
J1939
├── Source Address
├── NAME
├── Address Claim
├── PGN
└── Diagnostic Messages
```

Funktional:

```text
Ethernet ARP
↔
J1939 Address Claim
```

nicht technisch identisch, aber gleiche Mechanismusklasse:

```text
Address / Identity Resolution
```

---

# 24. Beispiel CANopen

```text
CANopen
├── Node-ID
├── NMT
├── Heartbeat
├── PDO
├── SDO
└── EMCY
```

Zuordnung:

```text
Addressing
→ Node-ID

Supervision
→ Heartbeat

Diagnostics
→ EMCY / SDO

Integrity
→ CAN CRC
```

---

# 25. Beispiel LIN

```text
LIN
├── Frame Identifier
├── PID Parity
├── Checksum
├── Schedule
├── Response Timeout
├── Diagnostic Request
└── Diagnostic Response
```

Kein:

```text
ARP
```

aber Diagnose und Integrität sind vorhanden.

---

# 26. Beispiel PROFINET

```text
PROFINET
├── DCP
├── Station Name
├── MAC
├── IP
├── Process Data
├── Device Diagnostics
├── Module Diagnostics
├── Channel Diagnostics
└── Alarms
```

DCP übernimmt u. a.:

```text
Identify
Set Name
Set IP
Device Discovery
```

---

# 27. Beispiel EtherCAT

```text
EtherCAT
├── Auto Increment Address
├── Configured Station Address
├── Alias Address
├── Working Counter
├── AL Status
├── AL Status Code
├── CoE
└── Emergency
```

Der Working Counter ist ein zentraler Mechanismus für die Laufzeitprüfung.

Beispiel:

```text
Expected WKC = 5
Actual WKC = 4
```

→ mindestens ein erwarteter Slave hat das Datagramm nicht korrekt verarbeitet.

---

# 28. Beispiel Modbus RTU

```text
Modbus RTU
├── Slave Address
├── Function Code
├── Data
├── CRC16
├── Diagnostics
└── Exception Codes
```

Beispiele:

```text
01 Illegal Function
02 Illegal Data Address
03 Illegal Data Value
```

---

# 29. Beispiel Modbus TCP

```text
Modbus TCP
├── IP
├── TCP
├── Port 502
├── Unit Identifier
└── Modbus Payload
```

Wichtig:

```text
Modbus RTU
→ eigener CRC16

Modbus TCP
→ kein Modbus-CRC
→ Ethernet FCS + TCP Checksum
```

Der Simulator muss layer-aware sein.

---

# 30. Beispiel DDS / ROS 2

```text
DDS
├── Participant Discovery
├── Endpoint Discovery
├── Topic
├── Publisher
├── Subscriber
└── QoS
```

QoS:

```text
Reliability
Deadline
Liveliness
Durability
History
```

---

# 31. Beispiel NMEA 2000

NMEA 2000 basiert auf J1939-artigen Mechanismen.

```text
NMEA 2000
├── Source Address
├── Address Claim
├── NAME
└── PGN
```

---

# 32. Beispiel BACnet

Discovery:

```text
Who-Is
→ I-Am
```

Objektdiscovery:

```text
Who-Has
→ I-Have
```

Diese Mechanismen gehören in:

```text
DiscoveryMechanism
```

---

# 33. Technology Change Handling

Ein besonders kritischer Fall:

```text
CAN-FD
→ LIN
```

Der Simulator darf die alten Werte nicht behalten.

Beispiel alter Zustand:

```text
nominal_bitrate_bps = 500_000
data_bitrate_bps = 2_000_000
```

Nach Wechsel zu LIN:

```text
old RateModel
≠
new RateModel
```

Pflicht:

```text
invalidate incompatible parameters
↓
clear incompatible fields
↓
propose valid target parameters
↓
validate
↓
mark dependent calculations STALE
↓
recalculate
```

---

# 34. Stale Dependency Chain

Wenn sich Technology oder Bitrate ändert:

```text
Technology / Bitrate
↓
Transport Timing
↓
Bus Load
↓
Latency
↓
Routing Feasibility
↓
Simulation Snapshot
↓
Trace Expectations
```

Diese abhängigen Ergebnisse müssen:

```text
STALE
```

werden.

---

# 35. Bestehende Projekte auditieren

Nicht nur neue Projekte schützen.

Einführung:

```text
TechnologyParameterAudit
```

Dieser prüft bestehende Daten.

Beispiele:

```text
LIN > 20 kbit/s
→ Finding

CAN implausible rate
→ Finding

CAN-FD missing phases
→ Finding

EtherCAT wrong rate model
→ Finding

Modbus RTU missing baudrate
→ Finding

Ethernet invalid link speed
→ Finding
```

---

# 36. Keine blinde automatische Reparatur

Beispiel:

```text
Network = LIN
configured = 2_000_000
```

Wenn eine vertrauenswürdige Quelle sagt:

```text
expected = 19_200
```

kann NIS vorschlagen:

```text
2_000_000
→ 19_200
```

Wenn die Zielrate nicht eindeutig ist:

```text
REVIEW_REQUIRED
```

Nicht automatisch raten.

---

# 37. Generatoren müssen TechnologyProfile verwenden

Jeder Generator:

```text
Network Generator
Interface Generator
Transport Generator
Simulation Generator
Trace Decoder
```

muss Parameter aus:

```text
TechnologyRegistry
```

beziehen.

Nicht aus:

```text
hardcoded defaults
```

---

# 38. Wizard muss TechnologyProfile verwenden

Bei Projektanlage oder Netzwerk-Wizard:

```text
Technology gewählt
↓
TechnologyProfile laden
↓
zulässige Parameter anzeigen
↓
User Input validieren
↓
Core speichern
```

---

# 39. Engineering Agent muss TechnologyProfile verwenden

Der Agent darf nicht selbst technische Grenzwerte halluzinieren.

Stattdessen:

```text
Agent
↓
MCP
↓
TechnologyRegistry
↓
TechnologyProfile
↓
Validator / Calculator
```

---

# 40. MCP-Schnittstellen

Empfohlene MCP-Familie:

```text
technology.list
technology.get_profile
technology.get_rate_model
technology.get_constraints
technology.get_mechanisms
technology.validate_parameters
technology.audit_project
```

---

# 41. Python Core Services

Empfohlene Services:

```text
TechnologyRegistryService
TechnologyProfileResolver
TechnologyParameterValidator
TechnologyRateModelResolver
TechnologyMechanismResolver
TechnologyChangeImpactResolver
TechnologyParameterAuditService
UnitNormalizationService
RateFormatter
```

---

# 42. Datenmodell

## TechnologyProfile

```text
id
name
family
rate_model_type
parameter_schema
constraints
mechanisms
calculation_model
validation_rules
version
```

## TechnologyBinding

```text
binding_id
technology_profile_id
network_id
hardware_interface_id
parameters
profile_version
validation_status
```

---

# 43. Unit Contract

Alle Parameter erhalten explizite Units.

Beispiel:

```json
{
  "name": "bitrate",
  "value": 19200,
  "unit": "bit/s"
}
```

Nicht:

```json
{
  "bitrate": 19200
}
```

ohne semantische Unit-Definition im Schema.

---

# 44. Validation Status

Mindestens:

```text
VALID
INVALID
UNKNOWN
REVIEW_REQUIRED
STALE
```

---

# 45. Finding-Typen

Mindestens:

```text
TECHNOLOGY_PROFILE_MISSING
TECHNOLOGY_PARAMETER_OUT_OF_RANGE
TECHNOLOGY_PARAMETER_INVALID
TECHNOLOGY_RATE_MODEL_MISMATCH
TECHNOLOGY_UNIT_MISMATCH
TECHNOLOGY_MECHANISM_MISSING
TECHNOLOGY_BINDING_STALE
TECHNOLOGY_LEGACY_DATA_INVALID
```

---

# 46. Simulation Preflight

Simulation darf erst starten wenn:

```text
TechnologyBindings valid
RateModels valid
Units valid
Required Mechanisms resolved
Routing valid
Capacity valid
Timing valid
```

---

# 47. Trace Decode

Trace Decode muss ebenfalls TechnologyProfile-aware sein.

Beispiel:

```text
CAN-FD
→ CAN-FD frame decoder

LIN
→ LIN frame + PID/checksum decoder

Ethernet
→ Ethernet/IP/ARP/SOME-IP decoder

Modbus RTU
→ Modbus RTU + CRC decoder
```

---

# 48. Regressionstests – Technologieparameter

Mindestens:

```text
TC-TECH-001
LIN 19.2 kbit/s
→ PASS

TC-TECH-002
LIN 2 Mbit/s
→ BLOCKER

TC-TECH-003
CAN-FD 500 kbit/s + 2 Mbit/s
→ PASS

TC-TECH-004
CAN-FD missing required rate phase
→ INVALID / REVIEW

TC-TECH-005
Ethernet 1 Gbit/s
→ PASS

TC-TECH-006
LIN accidentally loaded from CAN-FD profile
→ FAIL

TC-TECH-007
19_200 bps formatting
→ 19,2 kbit/s

TC-TECH-008
2_000_000 bps formatting
→ 2 Mbit/s

TC-TECH-009
save → reload
→ value + unit unchanged

TC-TECH-010
CAN-FD → LIN
→ incompatible values invalidated
```

---

# 49. Regressionstests – CommunicationMechanisms

Zusätzlich:

```text
TC-MECH-001
CAN-FD
→ CRC present

TC-MECH-002
LIN
→ checksum + PID parity present

TC-MECH-003
Ethernet IPv4
→ ARP available

TC-MECH-004
Ethernet IPv6
→ NDP available

TC-MECH-005
J1939
→ Address Claim available

TC-MECH-006
PROFINET
→ DCP available

TC-MECH-007
DDS
→ Discovery available

TC-MECH-008
BACnet
→ Who-Is / I-Am available

TC-MECH-009
CANopen
→ Heartbeat + EMCY available

TC-MECH-010
EtherCAT
→ Working Counter + AL Status available
```

---

# 50. Cross-Layer-Regression

Beispiel:

```text
Technology changed
↓
Parameter invalidated
↓
Capacity stale
↓
Timing stale
↓
Simulation stale
↓
Trace expectation stale
```

Tool Checker muss genau diese Kette prüfen.

---

# 51. Quality Gate

Technologiebezogene Pflichtanforderungen:

```text
Technology Profile Coverage = 100 %
Invalid Technology Parameters = 0
Unknown Critical Rate Models = 0
Technology Unit Errors = 0
Simulation with Invalid Binding = 0
Critical Technology Findings = 0
```

---

# 52. LIN-spezifisches Quality Gate

Für LIN:

```text
bitrate_bps <= 20_000
```

und:

```text
RateModel = SINGLE_BITRATE
```

Nicht zulässig:

```text
data_bitrate_bps
nominal/data phase model
2 Mbit/s fallback
```

---

# 53. Beispiel Fehlerreaktion

Konfiguration:

```text
Network: LIN_1
Technology: LIN
Configured: 2_000_000 bit/s
```

Ergebnis:

```text
Technology Validation
→ FAIL

Finding
→ TECHNOLOGY_PARAMETER_OUT_OF_RANGE

Capacity
→ BLOCKED

Timing
→ BLOCKED

Simulation Preflight
→ FAIL

Trace Baseline
→ STALE / NOT_AVAILABLE
```

---

# 54. Reparaturpfad

Wenn eindeutige Sollinformation vorhanden:

```text
Finding
↓
Root Cause
↓
Correct Technology Profile
↓
Correct Parameter
↓
Revalidate
↓
Recalculate Capacity
↓
Recalculate Timing
↓
Rebuild Simulation Snapshot
↓
Re-run Trace Baseline
↓
Regression
↓
Close Finding
```

---

# 55. Codex-Arbeitsauftrag

```text
Implement a technology-profile-driven communication model.

Do not use generic or cross-technology bitrate defaults.

For every supported communication technology:

1. define a TechnologyProfile,
2. define its RateModel,
3. define parameter units,
4. define valid ranges and constraints,
5. define IntegrityMechanisms,
6. define Addressing/AddressResolutionMechanisms,
7. define DiscoveryMechanisms,
8. define DiagnosticMechanisms,
9. define SupervisionMechanisms,
10. bind validators and calculation models.

Store canonical data rates in bit/s.

Use TechnologyProfile as the single source of truth for:
- UI parameter forms,
- generators,
- validators,
- capacity calculation,
- timing calculation,
- simulation preflight,
- trace decoding,
- Engineering Agent reasoning,
- MCP technology tools.

Reject invalid technology parameters before capacity, timing or simulation.

Do not silently fall back to generic defaults.

If a technology profile is missing:
→ BLOCK with TECHNOLOGY_PROFILE_MISSING.

When technology changes:
- invalidate incompatible fields,
- mark dependent calculations stale,
- revalidate,
- recalculate,
- rebuild simulation snapshot.

Audit all existing projects for technology parameter violations.

Create regression tests for:
- LIN 19.2 kbit/s,
- LIN invalid 2 Mbit/s,
- CAN-FD nominal/data rates,
- Ethernet rates,
- unit persistence,
- technology switching,
- communication mechanisms.

Do not close a technology finding until:
- root cause is known,
- fix is implemented,
- direct test passes,
- dependent calculations pass,
- simulation preflight passes,
- regression tests pass.
```

---

# 56. Definition of Done

Die Stabilisierung gilt als abgeschlossen, wenn:

1. TechnologyRegistry existiert.
2. TechnologyProfile existiert.
3. RateModels technologiespezifisch sind.
4. Datenraten intern in bit/s gespeichert werden.
5. UI korrekt formatiert.
6. LIN kein CAN-FD-RateModel verwenden kann.
7. LIN > 20 kbit/s blockiert wird.
8. CAN-FD nominal/data rate getrennt modelliert wird.
9. Ethernet eigene Link-Speed-Modelle besitzt.
10. Technology Change inkompatible Parameter invalidiert.
11. Capacity keine ungültigen Parameter akzeptiert.
12. Timing keine ungültigen Parameter akzeptiert.
13. Simulation Preflight ungültige Bindings blockiert.
14. Trace Decoder TechnologyProfile-aware ist.
15. CommunicationMechanisms generisch modelliert sind.
16. CRC/Checksum/FCS/WorkingCounter abgebildet sind.
17. ARP/NDP/Address Claim abgebildet sind.
18. SOME/IP-SD/DCP/DDS/BACnet Discovery abgebildet sind.
19. UDS/OBD/J1939 DM/CANopen EMCY/Modbus Diagnostics abgebildet sind.
20. Heartbeat/Watchdog/Liveliness/Bus-Off abgebildet sind.
21. bestehende Projekte per TechnologyParameterAudit geprüft werden.
22. Regressionstests TC-TECH-001…010 existieren.
23. Regressionstests TC-MECH-001…010 existieren.
24. LIN 19,2 kbit/s korrekt gespeichert und angezeigt wird.
25. LIN mit 2 Mbit/s zuverlässig als BLOCKER erkannt wird.

---

# 57. Leitregel

```text
TECHNOLOGY
→ PROFILE
→ VALID PARAMETER MODEL
→ VALID UNIT
→ VALID MECHANISMS
→ VALID CALCULATION
→ VALID SIMULATION
→ VALID TRACE
```

> **Der Simulator darf keinen technisch plausibel aussehenden Wert akzeptieren, wenn er nicht zur ausgewählten Kommunikationstechnologie passt.**
