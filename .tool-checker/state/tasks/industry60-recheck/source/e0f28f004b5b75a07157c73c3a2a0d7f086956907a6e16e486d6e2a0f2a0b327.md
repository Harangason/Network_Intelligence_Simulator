# Network Intelligence Simulator
## 60 industrieneutrale Agenten-, Typing-, Architektur-, MCP-, Trace- und Generator-Prüfungen

## 1. Zweck

Dieses Dokument definiert einen abgestuften Testsatz für den **Network Intelligence Simulator** und seinen Engineering Agent.

Der Testsatz besteht aus **40 fachlichen A/B-Szenarien** plus **10 zusätzlichen Chat-Agent-/MCP-/Skill-/UI-Integrationsprüfungen**.

Die ersten **20 Basisszenarien** existieren jeweils in zwei Varianten:

- **A – mit Typen/Technologien/konkreten technischen Daten**
- **B – ohne Typen/Technologien**, damit Typing, Rückfragen, Architekturwahl und Generatoren geprüft werden.

Damit ergeben sich zunächst **40 fachliche Aufgaben**:

- 5 einfache Basisszenarien × 2 = 10
- 13 mittlere Basisszenarien × 2 = 26
- 2 komplexe Basisszenarien × 2 = 4

Gesamtpipeline:

```text
User Input
→ Typing
→ Model Understanding
→ Architecture Selection
→ Required Questions
→ Hardware / Function Generation
→ Interface / Port Generation
→ Technology Binding
→ Network Generation
→ Transport / Message Generation
→ Routing
→ Capacity & Timing
→ Validation
→ Simulation Readiness
→ Visualization
```

## 2. Verbindliche Architekturvarianten

### Variante 0 – Sensor → Controller → Aktor
```text
Sensor → Controller → Aktor
```

### Variante 1 – Einfaches EVA
```text
Sensor / Aktor → Controller → Gateway
```

### Variante 2 – Controller-vermittelt
```text
Sensor ─┐
        ├→ Controller → Gateway
Aktor  ─┘
```

### Variante 3 – Gateway-direkt
```text
Sensor ──────┐
Controller ──┼→ Gateway
Aktor ───────┘
```

### Variante 4 – Gateway-Segmente
```text
Sensor/Aktor → Controller 1 ─┐
Sensor/Aktor → Controller 2 ─┼→ Gateway
weitere Controller ──────────┘
```

### KI-Kombination – Variante 2 + 3
```text
lokale Teilnehmer → Controller ─┐
                                ├→ Gateway
direkte Teilnehmer ─────────────┘
```

## 3. Agentenregeln für alle Szenarien

Der Agent muss:

1. Aufgabenstellung typisieren.
2. bestehende Modellobjekte suchen.
3. `REUSE before CREATE` anwenden.
4. Geräte klassifizieren.
5. Functions und Function Mappings bestimmen.
6. Functional Interfaces bestimmen.
7. Hardware Capabilities prüfen.
8. Hardware Interfaces und Ports prüfen.
9. fehlende Ports nur nach notwendiger Architekturentscheidung erzeugen.
10. Networks und Technology Bindings bestimmen.
11. Signals, DataObjects oder Streams passend zur Data Complexity erzeugen.
12. Transport Units technologiespezifisch erzeugen.
13. Routing vollständig erzeugen.
14. Logical Node Addresses für adressierbare Hardware vergeben.
15. Capacity und Timing berechnen.
16. Validation / Preflight ausführen.
17. Blocking Findings erkennen.
18. Completion prüfen.
19. Ergebnis passend visualisieren.

Nicht ausreichend:

```text
"Öffnen Sie den Netzwerk-Editor."
```

Der Agent soll die notwendigen Engineering-Schritte selbst ausführen.

---

# 4. Fünf einfache Basisszenarien

## S01 – Kleine lokale Regelung
**Architektur:** Variante 0

### S01-A – mit Typen
```text
1 Raspberry Pi 5
3 Sensoren:
- PT100 über SPI-ADC, -20…150 °C, 0,1 °C, 100 ms
- Drucksensor über I2C, 0…10 bar, 0,01 bar, 20 ms
- Drehzahlsensor über GPIO Counter, 0…6000 rpm, 10 ms

4 Aktoren:
- 2 PWM-Ventile
- 1 DC-Motorcontroller über CAN-FD
- 1 Relaisausgang

CAN-FD:
500 kbit/s nominal
2 Mbit/s data

Funktionen:
TemperatureMonitoring
PressureControl
SpeedControl
SafetyShutdown
```

Erzeuge Modell, Interfaces, Ports, Signale, Transport Units, Routing und Validation.

### S01-B – ohne Typen
```text
Ich habe 3 Sensoren, 4 Aktoren und einen zentralen kleinen Rechner.

Der Rechner soll:
- Temperatur überwachen,
- Druck regeln,
- eine Drehzahl regeln,
- bei kritischem Zustand die Anlage abschalten.

Lege eine sinnvolle Architektur an.
```

---

## S02 – Pumpenregelung
**Architektur:** Variante 0

### S02-A – mit Typen
```text
1 PLC
2 IO-Link-Sensoren:
- Durchfluss 0–100 l/min, 20 ms
- Druck 0–16 bar, 20 ms

2 Aktoren:
- Frequenzumrichter über PROFINET
- Magnetventil über digitales Remote-I/O

PROFINET:
100 Mbit/s

Funktionen:
FlowControl
PressureLimit
PumpCommand
```

### S02-B – ohne Typen
```text
Eine Steuerung soll eine Pumpe und ein Ventil anhand
von Durchfluss und Druck regeln.

Es gibt:
- 2 Sensoren
- 2 Aktoren
- 1 Steuerung

Erzeuge eine sinnvolle Kommunikations- und Regelungsarchitektur.
```

---

## S03 – Positioniersystem
**Architektur:** Variante 1

### S03-A – mit Typen
```text
1 Embedded Controller
2 Positionssensoren über CANopen
2 Servoantriebe über CANopen
1 Ethernet-Gateway

CANopen:
500 kbit/s
Sensorzyklus 10 ms
Drive Command 5 ms

Gateway:
CANopen ↔ Ethernet
Ethernet 1 Gbit/s

Funktionen:
PositionAcquire
PositionControl
MotionCommand
DiagnosticStatus
```

### S03-B – ohne Typen
```text
Ein System besitzt:
- 2 Positionssensoren
- 2 Servoantriebe
- 1 Controller
- 1 Verbindung zu einem übergeordneten System

Die Positionen sollen zyklisch geregelt werden.
```

---

## S04 – Klima-/Lüfterregelung
**Architektur:** Variante 2

### S04-A – mit Typen
```text
1 Controller
4 Temperatursensoren über LIN
3 Lüfteraktoren über LIN
1 Gateway mit LIN- und Ethernet-Port

LIN:
19,2 kbit/s
Sensoren 500 ms
Lüfterstatus 250 ms

Ethernet:
100 Mbit/s

Funktionen:
ZoneTemperatureAcquire
FanControl
ThermalStatus
```

### S04-B – ohne Typen
```text
Vier Temperatursensoren und drei Lüfter
sollen durch eine gemeinsame Steuerung geregelt werden.

Die Steuerung muss außerdem mit einem übergeordneten Netzwerk verbunden sein.
```

---

## S05 – Sicherheitsüberwachung
**Architektur:** Variante 3

### S05-A – mit Typen
```text
1 Safety Controller
3 digitale Sicherheitssensoren
2 Safety-Aktoren
1 Gateway

Kommunikation:
EtherCAT / FSoE

Safety Cycle:
4 ms

Funktionen:
SafetyInputMonitor
SafetyDecision
SafeStop
```

### S05-B – ohne Typen
```text
Ein Sicherheitssystem besitzt:
- 3 Sicherheitssensoren
- 2 sicherheitsrelevante Aktoren
- 1 Sicherheitssteuerung
- 1 übergeordnete Kommunikationsanbindung

Die Reaktionszeit muss kurz und deterministisch sein.
```

---

# 5. Dreizehn mittlere Basisszenarien

## S06 – Verteilte Maschinenzelle
**Architektur:** Variante 4

### S06-A – mit Typen
```text
3 PLC/Controller
12 Sensoren:
- 4 Temperatur
- 4 Position
- 4 Druck

8 Aktoren:
- 4 Ventile
- 2 Motor Drives
- 2 Linearantriebe

Netzwerke:
- 2 × PROFINET
- 1 × EtherCAT
- 1 × 1-Gbit-Ethernet Backbone

1 zentrales Gateway / Edge Controller

Zyklus:
Motion 2 ms
Position 5 ms
Pressure 20 ms
Temperature 100 ms
```

Erzeuge Segmentierung, Routing, Process Data, Capacity und Timing.

### S06-B – ohne Typen
```text
Eine verteilte Maschinenzelle besitzt:
- 3 Steuerungen
- 12 Sensoren
- 8 Aktoren
- 1 zentrale Kopplung

Ein Teil der Funktionen ist sehr zeitkritisch,
andere Messwerte sind langsam.
```

---

## S07 – Mobiles Robotersystem
**Architektur:** KI-Kombination 2+3

### S07-A – mit Typen
```text
1 Robot Controller
1 Edge Computer

8 Sensoren:
- 2 LiDAR
- 2 Kameras
- 2 Encoder
- 1 IMU
- 1 Abstandssensor

6 Aktoren:
- 4 Motor Drives
- 2 Steering Actuators

Kommunikation:
- LiDAR/Kamera: Ethernet / DDS
- Motor Drives: EtherCAT
- IMU/Encoder: CAN-FD
- Edge ↔ Robot Controller: 1-Gbit Ethernet

Funktionen:
EnvironmentPerception
Localization
MotionControl
SteeringControl
HealthMonitoring
```

### S07-B – ohne Typen
```text
Ein mobiles Robotersystem besitzt:
- 8 Sensoren mit einfachen Messwerten und hochauflösenden Umgebungsdaten,
- 6 Aktoren,
- 1 Echtzeitsteuerung,
- 1 leistungsfähigen Rechner.

Erzeuge eine sinnvolle hybride Kommunikationsarchitektur.
```

---

## S08 – Energieverteilung
**Architektur:** Variante 4

### S08-A – mit Typen
```text
4 intelligente Controller
16 Strom-/Spannungssensoren
8 Schaltaktoren
1 Gateway

Kommunikation:
- Modbus RTU / RS-485 für 8 Sensoren
- CAN-FD für 8 Sensoren + 8 Aktoren
- Ethernet / OPC UA zwischen Controllern und Gateway

Messzyklen:
- Strom/Spannung 50 ms
- Schaltstatus 20 ms
- Diagnose 1 s
```

### S08-B – ohne Typen
```text
Ein Energieverteilungssystem besitzt:
- 16 elektrische Messstellen,
- 8 Schaltelemente,
- 4 lokale Steuerungen,
- 1 zentrale Kopplung.

Messung, Schalten und Diagnose benötigen unterschiedliche Aktualisierungsraten.
```

---

## S09 – Gebäudezonen
**Architektur:** Variante 2

### S09-A – mit Typen
```text
4 Zone Controller
20 Sensoren:
- Temperatur
- CO2
- Feuchtigkeit
- Präsenz

12 Aktoren:
- Ventile
- Klappen
- Lüfter

Kommunikation:
- BACnet MS/TP lokal
- BACnet/IP zum Gateway
- Ethernet Backbone

1 Building Gateway

Zyklus:
Präsenz 100 ms
Klima 1 s
```

### S09-B – ohne Typen
```text
Vier räumliche Zonen besitzen insgesamt:
- 20 Sensoren
- 12 Aktoren
- 4 lokale Controller
- 1 zentrales Gateway

Jede Zone soll lokal arbeiten und zentral beobachtbar sein.
```

---

## S10 – Wasseraufbereitung
**Architektur:** Variante 2

### S10-A – mit Typen
```text
3 PLCs
18 Sensoren:
- pH
- Leitfähigkeit
- Füllstand
- Durchfluss
- Druck

10 Aktoren:
- Pumpen
- Ventile
- Dosierpumpen

Kommunikation:
- PROFIBUS PA für Prozesssensoren
- PROFINET für Drives / PLCs
- OPC UA zum zentralen Gateway
```

### S10-B – ohne Typen
```text
Ein Prozesssystem besitzt:
- 18 Prozesssensoren
- 10 Aktoren
- 3 lokale Steuerungen
- 1 zentrale Datenanbindung

Langsame Prozessmessungen und schnellere Pumpen-/Ventilsteuerungen
sollen gemeinsam integriert werden.
```

---

## S11 – Technischer Prüfstand
**Architektur:** Variante 3

### S11-A – mit Typen
```text
2 Real-Time Controller
1 Industrial PC
24 Sensoren
8 Aktoren
1 Data Gateway

Sensorik:
- 8 Analogkanäle, 10 kHz
- 8 CAN-FD-Sensoren, 10 ms
- 8 Ethernet-Sensoren, 1 ms

Aktoren:
- 4 CAN-FD
- 4 EtherCAT

Backbone:
1 Gbit Ethernet

Anforderung:
Messung, Regelung und Logging synchronisieren.
```

### S11-B – ohne Typen
```text
Ein technischer Prüfstand besitzt:
- 24 Sensoren mit stark unterschiedlichen Datenraten,
- 8 Aktoren,
- 2 Echtzeitsteuerungen,
- 1 Auswerte-PC,
- 1 zentrale Datenkopplung.

Erzeuge eine Architektur für Regelung und synchrones Logging.
```

---

## S12 – Autonomes Fördersystem
**Architektur:** KI-Kombination 2+3

### S12-A – mit Typen
```text
5 Controller
15 Sensoren
10 Motor Drives
1 Gateway

Kommunikation:
- EtherCAT für Drives und schnelle Positionssensoren
- IO-Link für einfache Sensoren
- Ethernet / MQTT für Zustandsdaten zum Gateway

Funktionen:
MaterialDetection
PositionTracking
ConveyorControl
JamDetection
EnergyMonitoring
```

### S12-B – ohne Typen
```text
Ein Fördersystem besitzt:
- 15 Sensoren
- 10 Antriebe
- 5 lokale Controller
- 1 zentrale Zustandsanbindung

Einige Sensoren sind zeitkritisch,
andere dienen nur der Zustandsüberwachung.
```

---

## S13 – Laborautomatisierung
**Architektur:** Variante 1

### S13-A – mit Typen
```text
4 Embedded Controller
12 Sensoren
10 Aktoren
1 Edge Gateway

Kommunikation:
- I2C/SPI lokal
- CAN-FD zwischen Embedded Controllern
- Ethernet zum Edge Gateway

Daten:
- Temperatur
- Druck
- Flüssigkeitslevel
- Position
- Pumpenstatus
- Ventilstatus
```

### S13-B – ohne Typen
```text
Eine automatisierte Laboranlage besitzt:
- 12 Sensoren
- 10 Aktoren
- 4 lokale Recheneinheiten
- 1 zentrale Schnittstelle

Viele Komponenten liegen physisch nahe an den lokalen Recheneinheiten.
```

---

## S14 – Mobile Arbeitsmaschine
**Architektur:** Variante 4

### S14-A – mit Typen
```text
6 Controller
20 Sensoren
12 Aktoren
1 Gateway

Netzwerke:
- 2 × ISOBUS / CAN
- 2 × CAN-FD
- 1 × Ethernet Backbone

Sensoren:
- Position
- Druck
- Drehzahl
- Durchfluss
- Feuchtigkeit

Aktoren:
- Ventile
- Motoren
- Dosierer
```

### S14-B – ohne Typen
```text
Eine mobile Arbeitsmaschine besitzt:
- 20 Sensoren
- 12 Aktoren
- 6 Controller
- 1 zentrale Kopplung

Die Maschine benötigt lokale Regelkreise,
mehrere getrennte Funktionsbereiche und einen Backbone.
```

---

## S15 – Technisches Hilfssystem
**Architektur:** Variante 4

### S15-A – mit Typen
```text
5 Controller
18 Sensoren
10 Aktoren
1 Gateway

Kommunikation:
- NMEA 2000 für verteilte Messgeräte
- Modbus RTU für Energie-/Pumpendaten
- Ethernet für Controller/Gateway

Funktionen:
PumpControl
TankMonitoring
PowerMonitoring
AlarmManagement
```

### S15-B – ohne Typen
```text
Ein technisches Hilfssystem besitzt:
- 18 Sensoren
- 10 Aktoren
- 5 lokale Controller
- 1 zentrale Verbindung

Messgeräte, Pumpensteuerung und Energieüberwachung
verwenden unterschiedliche Datencharakteristika.
```

---

## S16 – Lagerautomatisierung
**Architektur:** Variante 2

### S16-A – mit Typen
```text
8 Controller
24 Sensoren
16 Aktoren
1 Gateway

Kommunikation:
- PROFINET
- IO-Link
- 1-Gbit Ethernet

Sensoren:
- Lichtschranken
- Position
- Abstand
- Last

Aktoren:
- Motor Drives
- Stopper
- Greifer
```

### S16-B – ohne Typen
```text
Ein automatisches Lagersystem besitzt:
- 24 Sensoren
- 16 Aktoren
- 8 lokale Steuerungen
- 1 zentrale Kopplung

Transportbewegungen sind zeitkritisch,
Bestands-/Zustandsdaten deutlich weniger.
```

---

## S17 – Verteiltes Messsystem
**Architektur:** Variante 3

### S17-A – mit Typen
```text
10 Smart Sensor Nodes
2 Edge Controller
1 Gateway

Messgrößen:
- Vibration
- Temperatur
- Strom
- Spannung

Kommunikation:
- 6 Nodes über CAN-FD
- 4 Nodes über Ethernet
- Edge ↔ Gateway über Ethernet

Sampling:
- Vibration 5 kHz lokal aggregiert auf 10-ms-Features
- Temperatur 1 s
- Strom/Spannung 100 ms
```

### S17-B – ohne Typen
```text
Ein verteiltes Messsystem besitzt:
- 10 intelligente Messknoten,
- 2 Edge-Rechner,
- 1 zentrale Kopplung.

Ein Teil der Messungen ist hochfrequent,
andere ändern sich langsam.
```

---

## S18 – Multi-Axis Motion
**Architektur:** Variante 0 / 2

### S18-A – mit Typen
```text
2 Motion Controller
12 Servo Drives
12 Encoder
4 Safety Sensoren
1 Gateway

Kommunikation:
- EtherCAT für Motion
- FSoE für Safety
- Ethernet zum Gateway

Motion Cycle:
1 ms

Safety Cycle:
4 ms
```

### S18-B – ohne Typen
```text
Ein Mehrachssystem besitzt:
- 12 Antriebe
- 12 Positionsrückführungen
- 4 Sicherheitssensoren
- 2 Motion Controller
- 1 zentrale Kopplung

Die Achsregelung benötigt harte Echtzeit.
```

---

# 6. Zwei komplexe Basisszenarien

## S19 – Große heterogene Automatisierungsplattform
**Architektur:** Variante 4 + KI-Kombination 2+3

### S19-A – mit Typen / vollständige technische Vorgabe

```text
Erzeuge ein großes industrieneutrales Kommunikationssystem.

Systemumfang:
- 100 Sensoren
- 100 Aktoren
- 50 Funktionscontroller
- genau 1 zentrales Gateway

Sensorgruppen:
- 20 Temperatur
- 15 Druck
- 15 Strom
- 10 Spannung
- 10 Drehzahl
- 10 Position
- 10 Abstand
- 10 Zustands-/Qualitätssensoren

Aktoren:
- 25 Ventile
- 20 Motor Drives
- 15 Relais/Schalter
- 15 Linearantriebe
- 10 Pumpen
- 10 Lüfter
- 5 sonstige intelligente Aktoren

Netzwerke:
- 15 lokale Low-Speed-Segmente:
  LIN / RS-485 / IO-Link nach Geräteeignung
- 10 CAN-FD-Segmente
- 5 Industrial-Ethernet-Segmente
- 5 Ethernet-Backbone-Segmente
- 1 zentrales Gateway

Controller:
- gemischte PLC-, Embedded- und Edge-Controller
- jede Funktion erhält 5–20 fachlich notwendige Eingangs-/Ausgangsdaten

Kommunikationsregeln:
- einfache Sensoren/Aktoren bevorzugt lokal am zuständigen Controller
- zeitkritische Steuerdaten über CAN-FD / Industrial Ethernet
- datenintensive Teilnehmer über Ethernet
- Gateway verbindet notwendige Segmente
- direkte Gateway-Anbindung nur bei technischer Begründung

Adressierung:
- alle adressierbaren Controller/Gateways erhalten eine 4-stellige LogicalNodeAddress

Für alle relevanten Daten erzeugen:
- Semantic Type
- Unit
- Min/Max
- Resolution
- Cycle Time
- Producer
- Consumer
- FunctionalInterface
- HardwareInterface / Port
- Transport Unit
- Technology Binding

Erzeuge:
1. Engineering Model
2. Hardware-/Function Mapping
3. Physical Ports
4. Networks
5. Messages / Transport Units
6. Signal/DataObject Bindings
7. vollständiges Routing
8. Capacity & Timing
9. Gateway Load
10. Validation
11. Simulation Preflight
12. Netzwerkvisualisierung
13. Routingvisualisierung

Keine zufälligen fachlichen Zuordnungen.
```

### S19-B – ohne Typen / Agent muss Architektur entwickeln

```text
Erzeuge ein großes technisches System mit:

- 100 Sensoren
- 100 Aktoren
- 50 funktionalen Steuerungen
- genau einer zentralen Kopplung

Die Sensoren erfassen unterschiedliche physikalische Größen.
Die Aktoren reichen von einfachen Schaltelementen
bis zu schnellen geregelten Antrieben.

Einige Funktionen sind stark zeitkritisch.
Andere übertragen langsame Zustandsdaten.
Ein kleiner Teil der Teilnehmer erzeugt größere Datenmengen.

Jede funktionale Steuerung soll alle fachlich notwendigen
Ein- und Ausgangsdaten besitzen.

Entwickle eine belastbare industrieneutrale Architektur,
stelle notwendige Rückfragen,
erzeuge die Kommunikationsstruktur,
route alle notwendigen Datenströme,
berechne Kapazität und Timing
und führe anschließend die vollständige Validierung durch.
```

Der Agent muss selbst bestimmen bzw. erfragen:

```text
Device Classes
Data Complexity
Controller-Typen
lokal vs. direkt angebundene Teilnehmer
Segmentierung
Technology Candidates
Portbedarf
Gateway-Rolle
Signal vs. DataObject
Cycle Classes
Routing
Capacity
Timing
```

---

## S20 – Großes Multi-Technology-System mit Simulation und Trace
**Architektur:** Hybrid aus allen Varianten

### S20-A – mit Typen / konkrete Vorgabe

```text
Erzeuge ein großes Multi-Technology-System.

Hardware:
- 100 Sensoren
- 100 Aktoren
- 50 Controller
- 1 Central Gateway
- 4 Edge Compute Nodes
- 2 High-Performance Compute Nodes

Kommunikationsstruktur:
- 10 CAN-FD
- 10 Modbus-RTU / RS-485 Segmente
- 5 PROFINET-Netze
- 5 EtherCAT-Netze
- 5 Ethernet-Netze
- 1 Ethernet Backbone

Sensoren:
- 30 PHYSICAL_SCALAR
- 20 MULTI_VALUE
- 20 STATE / QUALITY
- 10 STRUCTURED_OBJECT
- 10 STRUCTURED_OBJECT_LIST
- 5 IMAGE_STREAM
- 5 High-Rate Data Sources

Aktoren:
- 40 einfache Schalt-/Ventilaktoren
- 30 geregelte Motor-/Motion-Aktoren
- 20 intelligente Aktoren mit Diagnose
- 10 sicherheitsrelevante Aktoren

Architekturvorgaben:
- einfache lokale Geräte → Controller-vermittelt
- Smart/Perception Devices dürfen direkt am Backbone liegen
- Motion → EtherCAT
- klassische Prozesssteuerung → PROFINET / CAN-FD
- langsame Registerkommunikation → Modbus RTU
- Streams / Object Lists → Ethernet
- Gateway verbindet notwendige Segmente
- Edge Nodes übernehmen lokale Aggregation
- HCP Nodes verarbeiten datenintensive Datenobjekte

Für jeden Controller:
- 5–20 fachlich erforderliche Ein-/Ausgangsdaten
- OperatingState
- HealthState
- CommunicationState, wenn sinnvoll

Erzeuge zusätzlich:
- LogicalNodeAddresses
- vollständige Route Table
- Transport Units
- Gateway Forwarding
- Capacity & Timing
- Queueing
- End-to-End Latency
- Validation
- Simulation Snapshot
- Golden-Trace-fähige Konfiguration
- Trace-Analyse-fähige Source-/Destination-Zuordnung

Simulation:
- 60 s
- reproduzierbarer Seed
- keine Faults im Golden Run

Trace muss auflösbar sein nach:
- Source
- Destination
- Logical Address
- Function
- Message / Transport Unit
- Signal / DataObject
- Network
- Route
```

### S20-B – ohne Typen / Zielvorgabe

```text
Erzeuge ein großes verteiltes technisches System.

Umfang:
- 100 Sensoren
- 100 Aktoren
- 50 Steuerungs-/Rechenknoten
- 1 zentrale Kopplung
- mehrere leistungsfähige Rechenknoten

Die Daten reichen von:
- einfachen langsamen Messwerten
bis
- zeitkritischen Regelungsdaten
bis
- strukturierten Objektlisten
und
- sehr datenintensiven Streams.

Die Aktoren reichen von:
- einfachen Schaltern
bis
- schnellen geregelten Antrieben
und
- intelligenten diagnostizierbaren Geräten.

Entwickle selbst eine sinnvolle segmentierte Architektur.

Der Agent soll:
- Teilnehmer klassifizieren,
- sinnvolle lokale und direkte Anbindungen bestimmen,
- notwendige Architekturentscheidungen erfragen,
- passende Kommunikationstechnologien vorschlagen,
- Ports und Interfaces planen,
- Networks erzeugen,
- Transportstrukturen erzeugen,
- Routing vollständig aufbauen,
- Capacity und Timing berechnen,
- das Gateway dimensionieren,
- validieren,
- eine reproduzierbare Simulation vorbereiten,
- einen fehlerfreien Golden Run ermöglichen,
- die Trace-Analyse vollständig vorbereiten.
```

---

# 7. Szenario-Matrix

| ID | Schwierigkeit | Architektur | Variante A | Variante B |
|---|---|---|---|---|
| S01 | Einfach | V0 | Raspberry Pi / SPI / I2C / CAN-FD | 3 Sensoren / 4 Aktoren / Rechner |
| S02 | Einfach | V0 | PLC / IO-Link / PROFINET | Pumpe / Ventil / 2 Sensoren |
| S03 | Einfach | V1 | CANopen + Ethernet Gateway | Positioniersystem |
| S04 | Einfach | V2 | LIN + Ethernet | Klima-/Lüfterregelung |
| S05 | Einfach | V3 | EtherCAT / FSoE | Safety-System |
| S06 | Mittel | V4 | PROFINET / EtherCAT | verteilte Maschinenzelle |
| S07 | Mittel | KI 2+3 | DDS / Ethernet / EtherCAT / CAN-FD | mobiler Roboter |
| S08 | Mittel | V4 | Modbus / CAN-FD / OPC UA | Energieverteilung |
| S09 | Mittel | V2 | BACnet | Gebäudezonen |
| S10 | Mittel | V2 | PROFIBUS PA / PROFINET | Prozessanlage |
| S11 | Mittel | V3 | CAN-FD / Ethernet / EtherCAT | Prüfstand |
| S12 | Mittel | KI 2+3 | EtherCAT / IO-Link / MQTT | Fördersystem |
| S13 | Mittel | V1 | I2C/SPI / CAN-FD / Ethernet | Laborautomatisierung |
| S14 | Mittel | V4 | ISOBUS / CAN-FD / Ethernet | mobile Maschine |
| S15 | Mittel | V4 | NMEA / Modbus / Ethernet | technisches Hilfssystem |
| S16 | Mittel | V2 | PROFINET / IO-Link | Lagerautomatisierung |
| S17 | Mittel | V3 | CAN-FD / Ethernet | verteiltes Messsystem |
| S18 | Mittel | V0/V2 | EtherCAT / FSoE | Multi-Axis Motion |
| S19 | Komplex | V4 + KI | 100/100/50 + Gateway | gleicher Umfang ohne Technologien |
| S20 | Komplex | Hybrid | Multi-Technology + Simulation/Trace | gleicher Umfang als Zielbeschreibung |

---

# 8. Was die B-Varianten gezielt testen

Die Varianten ohne Typangaben prüfen:

```text
Typing Quality
Model Understanding
Decision Detection
Clarification Quality
Architecture Reasoning
Technology Selection
Device Classification
Data Complexity Classification
Port / Interface Reasoning
Network Segmentation
Transport Selection
Completion Behavior
```

Der Agent soll nicht unnötig fragen.

Nicht erforderlich:

```text
"Wie soll Sensor 1 heißen?"
```

wenn dies keine relevante Architekturentscheidung ist.

Relevant kann dagegen sein:

```text
"Soll der datenintensive Sensor direkt am Backbone
oder über den lokalen Controller angebunden werden?"
```

---

# 9. Bewertungsmetriken

Für jedes Szenario mindestens:

```text
Typing Accuracy
Correct Existing-Object Reuse
Architecture Validity
Correct Questions
Unnecessary Question Count
Device Classification Accuracy
Technology Compatibility
Port / Interface Validity
Routing Completeness
Transport Completeness
Capacity Validation
Timing Validation
Blocking Findings
Completion Accuracy
Hallucinated Objects
Duplicate Objects
```

---

# 10. A/B-Vergleich

Für jedes Szenariopaar:

```text
A – konkreter Input
vs.
B – unvollständiger Input
```

Ziel:

Die B-Variante soll nach notwendigen Nutzerentscheidungen dieselbe Qualitätsstufe erreichen wie die A-Variante.

Nicht notwendig:

```text
identische Technologien
```

wenn B technologieoffen ist.

Notwendig:

```text
technisch begründete Architektur
+
vollständige Validierung
+
nachvollziehbare Entscheidungen
```

---

# 11. Architekturvielfalt

Der Testsatz gilt nur dann als sinnvoll, wenn der Agent nicht immer dieselbe Architektur erzeugt.

Er muss situationsabhängig beherrschen:

```text
V0 – lokale Sensor-Controller-Aktor-Regelung
V1 – einfaches EVA mit Gateway
V2 – Controller-vermittelte Kommunikation
V3 – direkte Gateway-Anbindung
V4 – segmentierte Gateway-Architektur
KI – hybride Kombination aus lokaler und direkter Anbindung
```

---

# 12. Komplexitätssteigerung

Empfohlene Reihenfolge:

```text
S01–S05
→ Basiskompetenz

S06–S10
→ Segmentierung / Multi-Controller

S11–S15
→ heterogene Technologien / Datenraten

S16–S18
→ größere Topologien / Echtzeit / Mixed Criticality

S19
→ großer Architektur- und Routing-Workload

S20
→ vollständiger Multi-Technology-Workflow
   bis Simulation und Trace Readiness
```

---

# 13. Komplexe Szenarien als Workload

S19 und S20 dürfen nicht in einem einzigen LLM-Schritt erzeugt werden.

Pflicht:

```text
Goal
↓
Workload
↓
Work Packages
↓
Batch Generation
↓
Validation per Batch
↓
Global Reconciliation
↓
Routing
↓
Capacity
↓
Timing
↓
Preflight
↓
Completion
```

Beispiel:

```text
WP01 Device Classification
WP02 Function Model
WP03 Sensor/Actuator Mapping
WP04 Hardware Interfaces / Ports
WP05 Network Segmentation
WP06 Payload Model
WP07 Transport Generation
WP08 Routing
WP09 Capacity
WP10 Timing
WP11 Validation
WP12 Simulation Readiness
WP13 Visualization
```

---

# 14. Completion-Regel

Objektanzahlen allein reichen nicht.

Beispiel:

```text
100 Sensoren generated
100 Aktoren generated
50 Controller generated
```

ist noch nicht COMPLETE.

Zusätzlich erforderlich:

```text
valid classification
valid mappings
valid ports
valid networks
valid payload semantics
valid transport units
complete routes
no unresolved identifier conflicts
capacity valid
timing valid
preflight valid
```

---

# 15. Verwendung für lokales LLM-Training

Die 40 Aufgaben können aufgeteilt werden in:

```text
typing
architecture_selection
decision_detection
tool_selection
tool_trajectory
completion
repair
visualization
```

Für jede B-Variante besonders speichern:

```text
User Input
→ Model Context
→ Missing Information
→ Correct Question
→ User Decision
→ Execution Trajectory
→ Validation Result
→ Final Output
```

---

# 16. Golden Evaluation

Empfehlung:

```text
Training:
S01–S15

Validation:
S16–S18

Golden / Holdout:
S19–S20
```

Wichtig:

A- und B-Variante desselben Basisszenarios nicht auf Training und Holdout aufteilen, wenn dadurch nahezu identische Inhalte durchsickern.

---

# 17. Referenz zum großen Umfang

Die beiden komplexen Szenarien orientieren sich am großen Referenzumfang der bereitgestellten Datei:

```text
100 Sensoren
100 Aktoren
50 Funktions-ECUs/-Controller
1 zentrales Gateway
mehrere LIN-/CAN-FD-/Ethernet-Netze
5–20 Signale je Funktion
vollständiges Routing
Capacity & Timing
Simulation
Trace-Analyse
```

Für die industrieneutrale Fassung werden die fahrzeugspezifischen Rollen abstrahiert zu:

```text
Sensor
Aktor
Controller
Gateway
Edge/HPC
Technology Binding
Transport Unit
Network
Route
```

---

# 18. Leitregel

```text
SAME ENGINEERING GOAL
+
DIFFERENT INPUT DETAIL
→ SAME QUALITY STANDARD
```

Der Agent soll sowohl mit:

```text
"3 Sensoren, 4 Aktoren, Raspberry Pi, CAN-FD ..."
```

als auch mit:

```text
"3 Sensoren, 4 Aktoren und ein Rechner ..."
```

arbeiten können.

Bei detailliertem Input:

```text
weniger Rückfragen
```

Bei offenem Input:

```text
Typing
→ Context
→ gezielte Engineering-Fragen
→ vollständige Ausführung
```

> **Ziel ist nicht, dass der Agent immer dieselbe Technologie auswählt. Ziel ist, aus unterschiedlich detaillierten industrieneutralen Anforderungen eine nachvollziehbare, vollständige und validierbare Kommunikationsarchitektur zu entwickeln.**

---
# 19. Zehn zusätzliche Chat-Agent-, MCP-, Skill- und UI-Integrationsprüfungen

Diese zehn Prüfungen ergänzen die fachlichen A/B-Szenarien um die technische Agenten- und Integrationsschicht.

Sie prüfen insbesondere:

```text
Chat Agent UX
Skill / Wizard Entry
Model Context
MCP Capability Discovery
MCP Read Tools
MCP Mutation Tools
Tool Schemas
User Decisions
Workload Resume
Browser Skill
Routing / Capacity / Timing
Simulation / Trace
Finding Lifecycle
Permissions
Audit
Deterministic Progress
```

Für UI-Schritte ist der **Browser Skill tatsächlich aufzurufen**. Ein Test gilt nicht als bestanden, nur weil ein API-Endpunkt oder ein MCP-Tool technisch erreichbar ist.

---

## S21 – Fähigkeiten/Wizards: Einstieg „Architektur erstellen“
**Schwierigkeit:** Integration  
**Prüfbereich:** Chat Agent + Wizard + Browser + Skill Routing

### Testeingabe

Browser öffnet die Agent-Startfläche:

```text
Fähigkeiten und Wizards

Woran möchtest du arbeiten?

[Architektur erstellen]
[Signal prüfen]
[Trace analysieren]
[Finding bewerten]
```

Browser klickt:

```text
Architektur erstellen
```

Danach Eingabe:

```text
Ich habe 3 Sensoren, 4 Aktoren und einen Raspberry Pi.
Erzeuge eine sinnvolle lokale Architektur.
```

### Erwartetes Agentenverhalten

```text
Wizard Selection
→ AgentInputEnvelope
→ Goal Type = CREATE_ARCHITECTURE
→ Typing
→ Model Context
→ Architecture Reasoning
→ benötigte Entscheidungen
→ Execution Plan
```

Der Agent darf nicht nur einen anderen Editor öffnen.

### MCP-Prüfung

Mindestens prüfen:

```text
Capability Discovery
model.inspect
hardware.inspect
function.inspect
hardware.interface.inspect
network.inspect
```

Wenn noch kein Modell existiert:

```text
controlled proposal / create path
```

### Browser-Prüfung

Browser Skill prüft:

1. Wizard-Button ist sichtbar.
2. Klick aktiviert den richtigen Modus.
3. Prompt wird korrekt übernommen.
4. Agent beginnt erst nach dem vorgesehenen Start/Senden.
5. Ergebnis erscheint im selben Chat-Kontext.
6. Keine unnötige Navigation zu einem anderen Werkzeug als Ersatz für die Ausführung.

### PASS

```text
Wizard → Agent Goal → MCP Context → Engineering Execution
```

ist durchgängig nachgewiesen.

---

## S22 – MCP Capability Discovery und Tool Registry
**Schwierigkeit:** Integration  
**Prüfbereich:** MCP Discovery / Registry / Schemas

### Testeingabe

```text
Prüfe die bestehende Architektur und stelle fest,
ob ParkAssist mit DriverAssistance kommunizieren kann.
```

### Erwartung

Der Agent bestimmt zuerst die benötigten Capabilities.

Beispiel:

```text
model.search
function.inspect
hardware.inspect
hardware.interface.inspect
network.inspect
routing.inspect
```

### MCP-Prüfung

Prüfe:

```text
Tool Registry erreichbar
Skill Registry erreichbar
Tool Name eindeutig
Input Schema verfügbar
Output Schema verfügbar
Permission Contract vorhanden
Tool Version vorhanden
```

Nicht erlaubt:

```text
hardcoded giant if/elif technology switch
unregistriertes Tool
freie Toolnamen aus LLM-Text
```

### Negative Prüfung

Fordere bewusst eine nicht existierende Capability an.

Erwartung:

```text
NOT_SUPPORTED / TOOL_NOT_FOUND
```

und keine erfundene erfolgreiche Ausführung.

### PASS

Der Agent findet nur registrierte Capabilities und kann deren Schemas korrekt verwenden.

---

## S23 – MCP Read Path: bestehendes Modell wirklich verstehen
**Schwierigkeit:** Integration  
**Prüfbereich:** Model Awareness / Read Tools / Canonical IDs

### Ausgangsmodell

```text
ParkAssist
→ ChassisController
→ CAN_FD_1
→ Chassis_CAN

DriverAssistance
→ ADAS_Controller
→ ETH_1
→ ADAS_ETHERNET
```

### Testeingabe

```text
Wie sind ParkAssist und DriverAssistance aktuell angebunden?
```

### Erwartete MCP-Aufrufe

Mindestens:

```text
find_function("ParkAssist")
find_host_hardware(...)
find_hardware_interfaces(...)
find_network_membership(...)

find_function("DriverAssistance")
find_host_hardware(...)
find_hardware_interfaces(...)
find_network_membership(...)

find_routes_between(...)
```

### Zu prüfen

```text
gleiche Canonical IDs in Agent, UI und Core
keine erfundenen Interfaces
keine erfundene Route
keine neue Model Mutation bei reinem Read-Auftrag
```

### PASS

Der Chat beschreibt den tatsächlichen Modellzustand und kann alle Aussagen auf Core-Objekte zurückführen.

---

## S24 – MCP Mutation: fehlenden CAN-Port nach Nutzerentscheidung vollständig umsetzen
**Schwierigkeit:** Integration / E2E  
**Prüfbereich:** Chat Decision + Port + Network + Routing + Validation

### Ausgangsmodell

```text
ParkAssist
→ ChassisController
→ Chassis_CAN / CAN-FD

DriverAssistance
→ ADAS_Controller
→ Ethernet

ADAS_Controller:
CAN-FD Capability = YES
CAN Controller = vorhanden
free channel = YES
CAN-FD Port = NONE
```

### Erwartete Chat-Frage

```text
Der ADAS_Controller unterstützt CAN-FD,
besitzt aber noch keinen CAN-FD-Port.

Soll ich einen CAN-FD-Port erstellen
und mit Chassis_CAN verbinden?

○ Ja – direkt anbinden
○ Gateway-Pfad prüfen
○ Ethernet-Alternative prüfen
```

Browser Skill wählt:

```text
Ja – direkt anbinden
```

### Danach ohne weitere unnötige Fragen

Agent muss über MCP/Core selbst ausführen:

```text
create/reuse HardwareInterface
create PhysicalPort
bind Controller Channel
connect Port to Chassis_CAN
update Network Membership
resolve Functional Interfaces
generate/reuse Transport Units
pack Payload
allocate Identifier
update Routing
recalculate Capacity
recalculate Timing
run Validation
run Communication Preflight
mark old dependent results STALE
Completion Check
```

### Zu prüfende MCP-Schnittstellen

Mindestens:

```text
hardware.interface.create
hardware.port.create
network.connect
transport.generate / transport.bind
routing.create / routing.update
capacity.calculate
timing.calculate
validation.run
```

### PASS

Ein einziges Nutzer-„Ja“ führt bis zur vollständig validierten Verbindung.

---

## S25 – MCP Schema-, Fehler- und Timeout-Verhalten
**Schwierigkeit:** Integration  
**Prüfbereich:** Robustheit / ToolResult / Retry

### Test 1 – ungültiges Argument

Rufe testweise ein MCP-Tool mit ungültigem Parameter auf.

Erwartung:

```text
INVALID_INPUT
```

mit:

```text
field
reason
expected schema
```

### Test 2 – nicht unterstützte Technologie

Erwartung:

```text
NOT_SUPPORTED
```

### Test 3 – Timeout

Simuliere einen transienten Tool-Timeout.

Erwartung:

```text
TOOL_TIMEOUT
```

Tool Checker darf nach Retry-Policy erneut versuchen.

### Test 4 – fachlicher Fehler

Beispiel:

```text
CAN Controller max_channels = 2
used_channels = 2
create_port(channel=3)
```

Erwartung:

```text
CAPACITY_EXCEEDED / NO_FREE_CHANNEL
```

Kein Auto-Retry als technischer Timeout.

### PASS

Fehler werden strukturiert behandelt und niemals als Erfolg oder erfundener Completion-Status ausgegeben.

---

## S26 – Chat Agent: Single-/Multi-Choice und Workload Resume
**Schwierigkeit:** Integration  
**Prüfbereich:** Chat UX / Structured Decisions

### Testeingabe

```text
Verbinde eine bestehende Funktion mit einem Zielcontroller,
für den mehrere technisch valide Netzwerkoptionen existieren.
```

### Erwartung

Der Agent erkennt:

```text
ENGINEERING_DECISION
```

und zeigt eine strukturierte Single-Choice-Frage.

Beispiel:

```text
○ bestehendes CAN-FD
○ Gateway-Pfad
○ Ethernet
```

Für eine Mehrfachauswahl:

```text
Welche Daten sollen übertragen werden?

☐ Status
☐ Diagnose
☐ Messwerte
☐ Raw Stream
```

### Browser-Prüfung

Browser Skill:

```text
select option
click confirm
```

### State-Prüfung

Vor Auswahl:

```text
Workload = SUSPENDED_FOR_DECISION
```

Nach Auswahl:

```text
Workload = RESUME
```

Nicht:

```text
new independent task
```

### MCP-Prüfung

Nach der Auswahl müssen die zuvor geplanten MCP-Schritte fortgesetzt werden.

### PASS

Frage → strukturierte Antwort → gleicher Workload → Ausführung → Completion.

---

## S27 – Wizard „Signal prüfen“: MCP bis zur fachlichen Validation
**Schwierigkeit:** Integration  
**Prüfbereich:** Chat Wizard + Signal Semantics + Binding + Validation

### Browser

Klick:

```text
Signal prüfen
```

### Testsignal

```text
MotorRPM

Range:
0…5000 rpm

Resolution:
50 rpm

Cycle:
10 ms

Technology:
CAN-FD
```

### Erwarteter Flow

```text
inspect signal
→ classify semantic type
→ inspect definition vs message binding
→ calculate required bit length
→ inspect encoding
→ inspect TransportUnit
→ validate cycle / range / scaling
→ create Finding if necessary
```

### MCP-Prüfung

Mindestens:

```text
signal.inspect
signal.semantic.classify
signal.encoding.resolve
signal.bit_length.calculate
transport.inspect
signal.validate
```

### Negative Fall

Message Binding verwendet z. B.:

```text
4 bit
```

obwohl Wertebereich/Auflösung mehr benötigt.

Erwartung:

```text
VALIDATION_FAILED
Finding
```

### PASS

Der Wizard führt eine echte fachliche Prüfung durch und zeigt nicht nur die Signal-Detailseite.

---

## S28 – Wizard „Trace analysieren“: MCP, Simulation Trace und Root Cause
**Schwierigkeit:** Integration / E2E  
**Prüfbereich:** Trace Tools + Reasoning + Evidence

### Browser

Klick:

```text
Trace analysieren
```

### Testgrundlage

Simulation enthält:

```text
Gateway Delay ab 12 s
→ Queue Growth
→ Message Delay
→ Deadline Miss
```

### Erwarteter Toolflow

```text
trace.load
trace.get_window
trace.get_events
signal.get_series
routing.get_route
capacity.get_metrics
timing.get_metrics
fault.get_events
trace.correlate
trace.root_cause
```

### Erwartetes Ergebnis

Nicht nur:

```text
"Es gibt ein Timingproblem."
```

sondern:

```text
Observation
Evidence
Causal Chain
Root Cause
Confidence
Affected Objects
```

### Browser-Prüfung

Prüfe:

```text
Botschaften
Sequenz
Signale
Trace
```

und synchronen Zeitkontext.

### PASS

Root Cause besitzt Evidence-Referenzen und kann auf Trace-, Route- und Modellobjekte zurückgeführt werden.

---

## S29 – Wizard „Finding bewerten“: Entscheidung, Persistenz und Audit
**Schwierigkeit:** Integration  
**Prüfbereich:** Finding Lifecycle + Chat + MCP + Audit

### Browser

Klick:

```text
Finding bewerten
```

### Ausgangs-Finding

```text
SINGLE_POINT_OF_FAILURE

CentralGateway
is articulation point of topology.
```

### Erwartete Optionen

```text
○ Maßnahme vorschlagen
○ Risiko akzeptieren
○ False Positive
○ Später prüfen
```

Bei:

```text
Risiko akzeptieren
```

zusätzlich:

```text
Begründung
Review bei Architekturänderung
```

### Fachregel

Technischer Befund bleibt erhalten:

```text
Detection = ACTIVE
```

Entscheidung:

```text
Decision = ACCEPTED_RISK
```

Nicht:

```text
Finding gelöscht
```

### MCP-Prüfung

Mindestens:

```text
finding.inspect
finding.decision.create
finding.decision.validate
audit.write
```

### Persistenzprüfung

Nach Reload:

```text
Decision exists
Rationale exists
Source revision exists
```

Bei Architekturänderung:

```text
ACCEPTED_RISK
→ REVIEW_REQUIRED / OUTDATED
```

### PASS

Finding-Entscheidung ist persistent, revisionsgebunden und auditiert.

---

## S30 – Vollständiger Chat-Agent/MCP/Browser-Systemtest
**Schwierigkeit:** Integration / System E2E  
**Prüfbereich:** gesamter Agentenpfad

### Ziel

Ein einzelner Test prüft die vollständige Kette:

```text
Wizard
→ Chat Agent
→ Typing
→ Model Context
→ Decision
→ MCP
→ Core Mutation
→ Routing
→ Capacity
→ Timing
→ Validation
→ Simulation
→ Trace
→ Finding
→ Visualization
→ Completion
```

### Start

Browser klickt:

```text
Architektur erstellen
```

Prompt:

```text
Verbinde ParkAssist mit DriverAssistance,
prüfe die Kommunikation in einer kurzen Simulation
und analysiere auftretende Timingprobleme.
```

### Erwartete Ausführung

1. Agent liest bestehendes Modell.
2. Agent erkennt fehlenden CAN-Port oder vorhandene Alternative.
3. Nur notwendige Engineering-Frage wird gestellt.
4. Browser beantwortet die Frage.
5. Agent setzt denselben Workload fort.
6. MCP erzeugt/ändert Port, Interface, Network und Route.
7. Capacity wird neu berechnet.
8. Timing wird neu berechnet.
9. Preflight läuft.
10. Simulation wird gestartet.
11. Universal Trace wird erzeugt.
12. Trace wird analysiert.
13. Findings werden erzeugt.
14. Ergebnis wird visualisiert.
15. Completion Evaluator entscheidet.

### MCP-Vertragsprüfung

Für jeden Tool Call prüfen:

```text
registered tool
valid input schema
valid output schema
actor / permission
project scope
canonical IDs
structured ToolResult
evidence / trace_id
```

### Browser Skill

Browser prüft reale:

```text
Clicks
Choices
Progress
Views
Result
```

### Progress

Tool Checker zeigt nur deterministischen Fortschritt:

```text
0–99 %
```

100 % erst bei erfolgreicher Completion.

Für die Fortschrittsanzeige:

```text
llm_calls_progress = 0
```

### Audit

Prüfe:

```text
user decision
MCP mutations
model revision
routing change
simulation run
finding
completion
```

sind nachvollziehbar.

### PASS

Nur wenn die gesamte Kette technisch und fachlich geschlossen ist.

---

# 20. Zusätzliche MCP-Abnahmematrix

Die zehn neuen Prüfungen müssen zusammen mindestens folgende MCP-Bereiche abdecken:

| Bereich | Muss geprüft werden |
|---|---|
| Discovery | Tool/Capability Registry, Versions- und Schemaauflösung |
| Context | Projekt, Model Revision, Selected Object, Canonical IDs |
| Read | Hardware, Function, Interface, Network, Route, Signal, Trace |
| Mutation | Port, Interface, Connection, Route, Binding |
| Calculation | Capacity, Timing, Encoding/Bit Length |
| Validation | Topology, Binding, Routing, Capacity, Timing, Preflight |
| Simulation | Preflight, Start, Status, Result |
| Trace | Window, Events, Signals, Route Correlation, Root Cause |
| Finding | Inspect, Decision, Review/Outdated |
| Governance | Permission, Actor, Project Scope, Audit |
| Failure | Invalid Input, Not Supported, Timeout, Conflict |
| Result Contract | Structured ToolResult, Evidence, trace_id |

---

# 21. Zusätzliche Chat-Agent-Abnahmekriterien

Der Chat Agent gilt in diesen Prüfungen nur als erfolgreich, wenn:

```text
1. Wizard Entry funktioniert.
2. Agent versteht den gewählten Arbeitsmodus.
3. Agent liest das bestehende Modell.
4. Agent fragt nur bei echten Engineering Decisions.
5. Checkboxen / Single Choice funktionieren.
6. Antwort wird strukturiert übernommen.
7. Workload wird fortgesetzt.
8. Agent verwendet MCP selbst.
9. Agent delegiert Arbeit nicht unnötig an den Nutzer.
10. Agent berechnet abhängige Werte selbst.
11. Agent validiert selbst.
12. Agent zeigt kompakten Progress.
13. Resultat wird im Chat verständlich zusammengefasst.
14. Deep Links sind optional, nicht Ersatz für Ausführung.
15. Completion wird nicht zu früh gemeldet.
```

---

# 22. Gesamtumfang nach Ergänzung

Der Testsatz enthält nun:

```text
40 fachliche A/B-Szenarien
+
10 Chat-Agent-/MCP-/Skill-/UI-Integrationsprüfungen
=
50 Prüfungen
```

Die zusätzlichen S21–S30 prüfen insbesondere die Ebene, die in den ersten 40 Szenarien nur implizit enthalten war:

```text
Chat UX
→ Skill/Wizard
→ Agent State
→ MCP Contract
→ Core Execution
→ Browser Evidence
→ Validation
→ Completion
```

---
# 23. Zehn zusätzliche Trace-Analyse-Prüfungen

Diese Prüfungen ergänzen die bisherigen Tests um die vollständige Abnahme von:

```text
Trace Session
→ Botschaften
→ Sequenz
→ Signale
→ synchronisierter Trace
→ Decode
→ Zeitkorrelation
→ Routing-Korrelation
→ Fault-Korrelation
→ Golden Trace
→ Root Cause
→ Finding
```

## S31 – Trace Session laden
Prüfe Simulation Trace, Import Trace und Golden Trace.

Erwartete Session-Daten:

```text
session_id
source
source_type
time_range
networks
technologies
simulation_run_ref
timebase
sync_status
metadata
```

MCP:
```text
trace.load
trace.inspect_session
trace.get_metadata
```

Negative Fälle: unbekanntes Format, fehlende Zeitbasis, ungültige Metadaten.

PASS nur bei sauberer Source-/Timebase-/Technology-Zuordnung.

---

## S32 – Botschaften-View
Prüfe:

```text
Timestamp
Source
Destination
Logical Addresses
Network
Technology
Transport Unit
Identifier
Payload Length
Cycle
Status
Fault
```

Technology-aware Labels:

```text
CAN-FD → Frame
DDS → Topic Sample
Modbus → Request/Response
PROFINET → Process Data
ARINC429 → Word
```

MCP:
```text
trace.get_messages
trace.decode_transport_unit
trace.resolve_source
trace.resolve_destination
```

Browser öffnet `Trace Analyse → Botschaften`, prüft Filter, Details und Source/Destination.

---

## S33 – Sequenz-View und Gateway-Hops
Testpfad:

```text
Source Controller
→ CAN-FD
→ Gateway
→ Ethernet
→ Destination Controller
```

Prüfe Sender, Gateway-Hop, Receiver, Delay und Technology Change.

MCP:
```text
trace.get_sequence
routing.get_route
trace.correlate_route
```

Bei Abweichung:
```text
TRACE_ROUTE_MISMATCH
```

---

## S34 – Signale-View und Decode
Testsignale:

```text
Temperature
MotorRPM
MotorCurrent
OperatingState
HealthState
```

Prüfe:

```text
time
value
unit
quality
min/max
state changes
fault markers
```

MCP:
```text
trace.get_signal_series
signal.decode
signal.get_definition
signal.get_binding
```

Negative Fälle:
```text
wrong bit length
wrong factor
wrong offset
missing decode schema
invalid enum value
```

---

## S35 – Synchronisierte Trace Views
Alle Views verwenden dieselbe Zeitbasis:

```text
Botschaften
Sequenz
Signale
Trace
```

Browser wählt Event bei `t = 12.500 s`.

Erwartung:
- Sequenz fokussiert denselben Kontext.
- Signal-Playhead springt auf 12.500 s.
- Trace Detail zeigt dasselbe Event.

MCP:
```text
trace.resolve_time
trace.resolve_event_context
```

Fehler:
```text
TRACE_TIMEBASE_MISMATCH
```

---

## S36 – Fault Injection bis Trace Evidence
Fault:

```text
Gateway Delay
start = 12 s
duration = 3 s
```

Trace muss zeigen:

```text
fault start
queue growth
message delay
deadline miss
fault end
recovery
```

MCP:
```text
simulation.get_faults
trace.get_fault_events
trace.correlate_fault
timing.get_deadline_misses
```

Finding:
```text
TIMING_CAUSAL_CHAIN
```

Evidence muss Fault Event, Queue Metric, Message Delay und Deadline Miss referenzieren.

---

## S37 – Golden Trace Vergleich
Vergleiche:

```text
Run A → Golden Trace
Run B → Changed/Faulted Trace
```

Prüfe:

```text
missing events
additional events
timing deviation
signal deviation
state deviation
route deviation
fault deviation
```

MCP:
```text
trace.compare_golden
trace.find_first_divergence
trace.get_deviation_summary
```

PASS nur, wenn die `first credible divergence` bestimmt wird.

---

## S38 – Root Cause Analyse
Szenario:

```text
Camera Burst
→ Gateway Queue Growth
→ CAN-FD Load steigt
→ MotorStatus Deadline Miss
```

Hypothesen mindestens:

```text
A: MotorStatus selbst verursacht Last
B: Camera Burst verursacht Queueing
C: Gateway Processing verursacht Verzögerung
```

MCP:
```text
trace.get_window
trace.get_events
capacity.get_metrics
timing.get_metrics
routing.get_route
trace.correlate
trace.root_cause
```

Ergebnis muss enthalten:

```text
observations
evidence
causal chain
rejected alternatives
confidence
```

Keine reine LLM-Behauptung.

---

## S39 – Filter, Suche und große Trace-Datenmengen
Test mit:

```text
> 100.000 Events
```

Filter:

```text
time range
source
destination
logical address
network
technology
message
signal
function
route
fault
severity
```

MCP:
```text
trace.query
trace.get_window
trace.get_page
trace.get_count
```

Pflicht:

```text
windowing
pagination
streaming
downsampling
```

Nicht:
```text
full trace in browser memory
```

---

## S40 – Vollständiger Trace-Analyse-E2E-Test

```text
Engineering Model
↓
Simulation Snapshot
↓
Simulation Run
↓
Fault Injection
↓
Universal Trace
↓
Trace Session
↓
Botschaften
↓
Sequenz
↓
Signale
↓
Synchronisierter Trace
↓
Golden Trace Comparison
↓
Root Cause
↓
Finding
↓
Visualization
↓
Completion
```

Pflichtprüfungen:

1. SimulationRun reproduzierbar.
2. TraceSession referenziert richtigen Run.
3. LogicalNodeAddresses werden korrekt aufgelöst.
4. Transport Units sind technology-aware.
5. Botschaften zeigt echte Events.
6. Sequenz zeigt Gateway-/Route-Hops.
7. Signale werden korrekt dekodiert.
8. Views sind synchron.
9. Faults sind sichtbar.
10. Route Correlation funktioniert.
11. Golden Trace Vergleich funktioniert.
12. First Divergence wird erkannt.
13. Root Cause besitzt Evidence.
14. Finding referenziert Source Events.
15. Deep Links führen zu Model Objects.
16. Ergebnis bleibt nach Reload bestehen.

MCP mindestens:

```text
simulation.inspect
simulation.get_result
trace.load
trace.inspect_session
trace.get_messages
trace.get_sequence
trace.get_signal_series
trace.get_window
trace.correlate_route
trace.correlate_fault
trace.compare_golden
trace.find_first_divergence
trace.root_cause
finding.create
```

Browser Skill prüft reale Klicks durch:
```text
Botschaften
Sequenz
Signale
Trace
Finding
Root Cause
```

Tool Checker Progress bleibt deterministisch:
```text
llm_calls_progress = 0
```

PASS nur bei geschlossener Kette:
```text
Simulation
+
Trace
+
Decode
+
Correlation
+
Golden Trace
+
Root Cause
+
Finding
+
Evidence
```

---

# 24. Trace-Analyse-Abnahmematrix

| Bereich | Pflicht |
|---|---|
| Session | Source, Timebase, Technology, SimulationRef |
| Botschaften | Transport Units, Source/Destination, Payload |
| Sequenz | Teilnehmer, Gateway Hops, Delay |
| Signale | Decode, Unit, Quality, State |
| Sync | gemeinsame Zeitbasis aller Views |
| Routing | Trace ↔ Route ↔ Network |
| Faults | Fault Event ↔ Auswirkungen |
| Golden Trace | Diff + First Divergence |
| Root Cause | Evidence + Causal Chain |
| Findings | persistent + verlinkt |
| Performance | Windowing / Pagination / Streaming |
| Browser | echte Klicks und View-Prüfung |
| MCP | vollständige Trace Tool Contracts |
| Completion | kein PASS ohne Evidence |

---

# 25. Gesamtumfang

```text
40 fachliche A/B-Szenarien
+
10 Chat-Agent-/MCP-/Skill-/UI-Prüfungen
+
10 Trace-Analyse-Prüfungen
=
60 Prüfungen
```

Vollständige Prüfkette:

```text
INPUT
→ AGENT
→ MODEL
→ MCP
→ ENGINEERING EXECUTION
→ ROUTING
→ CAPACITY
→ TIMING
→ VALIDATION
→ SIMULATION
→ UNIVERSAL TRACE
→ TRACE ANALYSE
→ ROOT CAUSE
→ FINDING
→ COMPLETION
```
