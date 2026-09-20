# Network Intelligence Simulator
## Vollständige Master-Test-Suite S01–S60
## 80 reale Prüfungen · Hauptwizard · Wizards · Chat-Agent · MCP · Simulation · Trace · Repair · Quality Gate

> **Kanonische Einzeldatei.** Diese Datei konsolidiert den fachlichen A/B-Testsatz, Chat-/MCP-/UI-Tests, Trace-Tests, die zuvor fehlenden Wizard-Systemtests S41–S50, die Engineering-Agent-Systemtests S51–S60 sowie den VERIFY_AND_REPAIR-Quality-Gate-Prozess.

---

# 0. Audit und korrigierter Prüfumfang

Bei der Konsolidierung wurde eine reale Lücke bestätigt:

```text
S01-A … S20-B  → 40 fachliche Prüfungen
S21 … S30      → 10 Chat-Agent/MCP/UI-Prüfungen
S31 … S40      → 10 Trace-Analyse-Prüfungen
S41 … S50      → 10 Wizard-Systemprüfungen
S51 … S60      → 10 Engineering-Agent-Systemprüfungen
```

Damit gilt:

```text
40 + 10 + 10 + 10 + 10 = 80 reale Prüfungen
```

Wichtig: Das Kennungsschema reicht nur bis `S60`, weil `S01–S20` jeweils zwei Varianten `A` und `B` besitzen.

Die frühere 60er-Datei enthielt S01–S40. Die Engineering-Agent-Erweiterung begann direkt bei S51. Der S41–S50-Block war in einer Zwischenfassung nur als escaped Text (`\n`) angehängt und dadurch für normale Markdown-/Heading-Parser faktisch nicht als sauberer Testblock vorhanden. Diese Datei behebt das.

Verbindlicher Mastermodus:

```text
VERIFY_AND_REPAIR
```

Ziel:

```text
Mandatory Requirements Pass Rate = 100 %
Critical Journey Pass Rate = 100 %
P0 = 0
Blocking P1 = 0
Blocked Mandatory Checks = 0
Residual Non-Critical Failure Rate < 1 %
```

---

# Network Intelligence Simulator
## Kanonischer Szenario- und Integrationstestbestand S01–S40

## 1. Zweck

Dieses Dokument definiert einen abgestuften Testsatz für den **Network Intelligence Simulator** und seinen Engineering Agent.

Der Basisteil enthält **40 fachliche A/B-Prüfungen**, **10 Chat-Agent-/MCP-/Skill-/UI-Integrationsprüfungen** und **10 Trace-Analyse-Prüfungen**. Die fehlenden Wizard- und Engineering-Agent-Blöcke S41–S60 werden in dieser Masterdatei direkt anschließend ergänzt.

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

---

# 26. Zehn verbindliche Wizard-Systemprüfungen

Die bisherigen Prüfungen behandeln einzelne Wizard-Einstiege und fachliche Funktionen. Dieser Block prüft die **Wizard-Infrastruktur selbst** und stellt sicher, dass Wizards nicht nur dekorative Buttons oder Navigationselemente sind.

Verbindlicher Prüfpfad:

```text
Wizard Entry
→ Wizard Context
→ Input / Selection
→ Validation
→ Agent / Skill
→ MCP Capability
→ Core Service
→ Model Change / Analysis
→ Result
→ Completion
→ Persistence / Resume
```

Ein Wizard gilt nicht als bestanden, wenn er lediglich:

```text
ein Board öffnet
eine Seite verlinkt
einen Prompt vorfüllt
einen statischen Dialog zeigt
```

Er muss den fachlichen Auftrag wirklich bis zum definierten Zielzustand führen.

## S41 – Wizard-Startseite und Capability-Zuordnung
**Schwierigkeit:** UI / Integration  
**Prüfbereich:** Fähigkeiten und Wizards

### Erwartete Startfläche

Mindestens:

```text
Architektur erstellen
Signal prüfen
Trace analysieren
Finding bewerten
```

### Browser Skill

Prüft:

1. Bereich `Fähigkeiten und Wizards` ist sichtbar.
2. Jeder Wizard ist anklickbar.
3. Fokus- und Hoverzustände funktionieren.
4. Tastaturbedienung funktioniert.
5. Wizard-Buttons sind nicht nur Links ohne Capability.
6. Wizard startet erst nach der vorgesehenen Aktion.
7. Freitext kann alternativ eingegeben werden.
8. `Senden` startet denselben Agenten-/Skill-Mechanismus wie der Wizard.

### Capability-Prüfung

Jeder Wizard muss einem registrierten Skill/Goal zugeordnet sein:

```text
architecture.create
signal.validate
trace.analyze
finding.review
```

### MCP-Prüfung

Capability Registry muss für jeden Wizard die benötigten MCP-Familien auflösen können.

### PASS

```text
UI Wizard
→ Skill
→ Agent Goal
→ Capability Registry
```

ist eindeutig nachgewiesen.

---

## S42 – Architektur-Wizard vollständig
**Schwierigkeit:** E2E  
**Prüfbereich:** Architektur erstellen

### Start

Browser klickt:

```text
Architektur erstellen
```

### Eingabe

```text
Ich habe 3 Sensoren, 4 Aktoren und einen Raspberry Pi.
Erzeuge eine lokale Regelungsarchitektur.
```

### Wizard muss mindestens durchführen

```text
Systemziel erfassen
↓
Geräte typisieren
↓
Device Classes bestimmen
↓
Functions erzeugen
↓
Function Mappings bestimmen
↓
Communication Requirements bestimmen
↓
Hardware Capabilities prüfen
↓
Interfaces / Ports planen
↓
Netzwerke erzeugen / wiederverwenden
↓
Transport erzeugen
↓
Routing erzeugen
↓
Capacity / Timing
↓
Validation
↓
Architektur visualisieren
```

### Pflichtfragen

Nur echte Engineering-Entscheidungen.

### Nicht erlaubt

```text
"Öffnen Sie jetzt den Netzwerkeditor."
```

als Endzustand.

### MCP mindestens

```text
model.inspect
hardware.generate
function.generate
hardware.interface.create
network.create/connect
transport.generate
routing.create
capacity.calculate
timing.calculate
validation.run
```

### PASS

Wizard erzeugt eine validierte Architektur im Core.

---

## S43 – Architektur-Wizard mit bestehendem Modell
**Schwierigkeit:** E2E  
**Prüfbereich:** Model Awareness / Reuse

### Ausgangslage

Projekt enthält bereits:

```text
Controller_A
CAN_FD_1
Network_A
TemperatureSignal
```

### Eingabe

```text
Ergänze einen zweiten Temperatursensor
und binde ihn an die vorhandene Regelung an.
```

### Erwartung

Wizard muss zuerst bestehendes Modell prüfen.

Grundregel:

```text
REUSE before CREATE
```

### Zu prüfen

Nicht erzeugen:

```text
Controller_A_Copy
CAN_FD_1_New
Network_A_2
TemperatureSignal_Copy
```

wenn vorhandene Objekte fachlich wiederverwendbar sind.

### MCP

```text
model.search
hardware.inspect
network.inspect
signal.find_similar
routing.inspect
```

### PASS

Wizard erweitert das vorhandene Modell ohne unnötige Duplikate.

---

## S44 – Signal-prüfen-Wizard vollständig
**Schwierigkeit:** E2E  
**Prüfbereich:** Signal prüfen

### Start

Browser klickt:

```text
Signal prüfen
```

### Testsignal

```text
MotorRPM
0…5000 rpm
Auflösung 50 rpm
Cycle 10 ms
CAN-FD
```

### Wizard prüft

```text
Semantic Type
Unit
Range
Resolution
required bit length
signed/unsigned
factor
offset
invalid/reserved values
Message Binding
Transport Unit
Cycle Time
Producer
Consumer
Encoding
```

### Fehlerfall

Binding:

```text
4 Bit
```

obwohl Wertebereich mehr benötigt.

### Erwartung

```text
Finding
+
Begründung
+
betroffenes Binding
+
Korrekturvorschlag
```

### MCP

```text
signal.inspect
signal.semantic.classify
signal.bit_length.calculate
signal.encoding.resolve
transport.inspect
signal.validate
finding.create
```

### PASS

Wizard führt echte Signalprüfung durch, nicht nur Navigation.

---

## S45 – Trace-analysieren-Wizard vollständig
**Schwierigkeit:** E2E  
**Prüfbereich:** Trace analysieren

### Start

Browser klickt:

```text
Trace analysieren
```

### Wizard-Schritte

```text
Trace Source wählen
↓
TraceSession erzeugen
↓
Timebase prüfen
↓
Technologien erkennen
↓
Botschaften laden
↓
Sequenz ableiten
↓
Signale dekodieren
↓
Views synchronisieren
↓
Faults korrelieren
↓
Routing korrelieren
↓
Root Cause erzeugen
↓
Finding erzeugen
```

### MCP

```text
trace.load
trace.inspect_session
trace.get_messages
trace.get_sequence
trace.get_signal_series
trace.correlate_route
trace.correlate_fault
trace.root_cause
```

### Browser

Prüft alle Trace-Views real.

### PASS

Wizard beendet erst nach nachvollziehbarer Trace-Auswertung.

---

## S46 – Finding-bewerten-Wizard vollständig
**Schwierigkeit:** E2E  
**Prüfbereich:** Finding bewerten

### Start

Browser klickt:

```text
Finding bewerten
```

### Wizard muss anzeigen

```text
Finding
Severity
Affected Object
Evidence
Current Decision State
```

### Auswahl

Mindestens:

```text
Maßnahme erforderlich
Risiko akzeptieren
False Positive
Nicht anwendbar
Später prüfen
```

### Bei Risk Acceptance

Pflicht:

```text
Begründung
Scope
Revision
Review Trigger
```

### MCP

```text
finding.inspect
finding.get_evidence
finding.decision.create
finding.decision.validate
audit.write
```

### PASS

Entscheidung bleibt nach Reload persistent und wird bei relevanter Modelländerung stale/review-required.

---

## S47 – Wizard State, Zurück, Weiter und Resume
**Schwierigkeit:** UI / State  
**Prüfbereich:** Wizard Runtime

### Test

Architektur-Wizard starten.

Schritte:

```text
1 Geräte
2 Funktionen
3 Kommunikation
4 Review
```

### Browser prüft

```text
Weiter
Zurück
Abbrechen
Resume
```

### Pflicht

Beim Zurückgehen:

```text
keine doppelte Core-Mutation
```

Beim UI-Reload:

```text
Wizard State bleibt erhalten
```

Beim Abbruch:

```text
keine halbfertige fachliche Wahrheit
```

### State Contract

Mindestens:

```text
wizard_id
workload_id
current_step
completed_steps
pending_decisions
draft_changes
model_revision
status
```

### PASS

Wizard ist zustandsbehaftet und revisionssicher.

---

## S48 – Wizard Validation und Pflichtfelder
**Schwierigkeit:** UI / Validation  
**Prüfbereich:** Eingabequalität

### Testfälle

```text
keine Funktion
ungültiger Wertebereich
negative Cycle Time
nicht unterstützte Technologie
Port-Limit überschritten
doppelter Identifier
```

### Erwartung

Wizard verhindert Weitergehen nur bei echten Blockern.

Darstellung:

```text
field
reason
required correction
```

### Nicht erlaubt

```text
generic "Error"
```

ohne Ursache.

### MCP/Core

Validierung muss aus denselben Core-Validatoren kommen wie außerhalb des Wizards.

### PASS

Wizard besitzt keine parallele eigene Fachvalidierung.

---

## S49 – Wizard → MCP → Core Vertrags- und Revisionsprüfung
**Schwierigkeit:** Integration  
**Prüfbereich:** Contract Integrity

### Prüfkette

```text
Wizard Input
↓
AgentInputEnvelope
↓
Skill Contract
↓
MCP Tool
↓
Python Core Service
↓
Canonical Model
↓
Projection
```

### Zu prüfen

Für jeden MCP Call:

```text
registered tool
valid schema
project scope
actor
permission
expected revision
structured result
trace_id
```

### Revisionstest

Modell zwischen Wizard-Schritt und Commit ändern.

Erwartung:

```text
PLAN_STALE / REVISION_CONFLICT
```

Wizard muss:

```text
re-inspect
→ re-plan
```

### PASS

Keine Wizard-Mutation umgeht MCP/Core-Governance.

---

## S50 – Vollständiger Wizard-Regressionslauf
**Schwierigkeit:** System E2E  
**Prüfbereich:** alle Wizards

### Browser führt nacheinander aus

```text
1 Architektur erstellen
2 Signal prüfen
3 Trace analysieren
4 Finding bewerten
```

### Tool Checker prüft

```text
Wizard UI
Agent State
Skill Selection
MCP Calls
Core Changes
Validation
Persistence
Browser Result
Evidence
```

### Progress

Nur deterministisch:

```text
Wizard Regression
84 %

Trace Wizard wird geprüft …
```

```text
llm_calls_progress = 0
```

### Pflicht-Evidence

```text
Wizard screenshots
tool-calls.json
wizard-state.json
model-before.json
model-after.json
model-diff.json
validation.json
trace-session.json
finding-decision.json
audit references
```

### PASS

Nur wenn alle vier Wizards fachlich und technisch durchgängig funktionieren.

---

# 27. Wizard-Abnahmematrix

| Bereich | Pflichtprüfung |
|---|---|
| Startseite | Cards, Freitext, Senden, Tastatur |
| Skill Mapping | eindeutiger Goal-/Skill-Identifier |
| Context | Projekt, Auswahl, Revision |
| Typing | Input korrekt klassifiziert |
| Fragen | nur notwendige Engineering Decisions |
| State | Back/Next/Resume/Cancel |
| MCP | registrierte Tools + Schemas |
| Core | echte fachliche Wirkung |
| Validation | gemeinsame Core-Validatoren |
| Revision | Konflikt / Replan |
| Persistence | Reload-fest |
| Browser | reale Klicks |
| Progress | deterministisch, kein LLM |
| Evidence | Screenshots + Core-Nachweis |
| Completion | kein vorzeitiges COMPLETE |

---

# 28. Wizard-Anti-Patterns

```text
WIZARD_ONLY_NAVIGATES
WIZARD_ONLY_PREFILLS_PROMPT
WIZARD_NO_MCP_CALL
WIZARD_NO_CORE_EFFECT
WIZARD_DUPLICATE_OBJECT
WIZARD_SKIPS_MODEL_CONTEXT
WIZARD_ASKS_DETERMINISTIC_QUESTION
WIZARD_LOSES_STATE
WIZARD_DUPLICATES_ON_BACK
WIZARD_NO_REVISION_CHECK
WIZARD_VALIDATION_ONLY_FRONTEND
WIZARD_PREMATURE_COMPLETE
WIZARD_NO_EVIDENCE
```

---

---

# 29. Engineering-Agent-Systemprüfungen S51–S60

# 7. S51 – Goal Understanding und Typing
**Prüfbereich:** Input → Goal

### Inputs

Beispiele:

```text
Verbinde ParkAssist mit DriverAssistance.
```

```text
Prüfe MotorRPM.
```

```text
Analysiere den letzten Trace.
```

```text
Erzeuge eine Architektur für 3 Sensoren, 4 Aktoren und einen Rechner.
```

### Erwartung

Agent klassifiziert korrekt:

```text
CONNECT_FUNCTIONS
VALIDATE_SIGNAL
ANALYZE_TRACE
CREATE_ARCHITECTURE
```

### Zusätzlich

Typing muss relevante Objekte erkennen:

```text
Function
Signal
TraceSession
HardwareNode
```

### Fehler

```text
AGENT_GOAL_MISCLASSIFIED
AGENT_TYPING_FAILED
```

### PASS

Goal und Hauptobjekte werden korrekt erkannt.

---

# 8. S52 – Model Awareness
**Prüfbereich:** Agent versteht das bestehende Modell

### Ausgangslage

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

### Aufgabe

```text
Verbinde ParkAssist mit DriverAssistance.
```

### Agent muss lesen

```text
Functions
Function Mappings
HardwareNodes
HardwareInterfaces
Physical Ports
Networks
Routes
Technology Bindings
LogicalNodeAddresses
```

### Nicht erlaubt

```text
neuen ChassisController erfinden
neuen ADAS_Controller erfinden
bestehende Networks ignorieren
```

### PASS

Plan basiert nachweislich auf dem aktuellen Canonical Model.

---

# 9. S53 – Decision Detection
**Prüfbereich:** Wann fragt der Agent?

### Fall A – deterministisch

```text
Ist ein CAN-Port frei?
```

Agent prüft selbst.

Keine Nutzerfrage.

### Fall B – echte Architekturentscheidung

```text
direkter CAN-FD-Port
vs.
Gateway-Pfad
```

Agent fragt Nutzer.

### Fall C – Policy Defined

Projektpolicy:

```text
reuse existing interface before create
```

Agent folgt Policy ohne Frage.

### Metriken

```text
correct_questions
missing_questions
unnecessary_questions
```

### PASS

Agent fragt nur bei echten Engineering Decisions.

---

# 10. S54 – Engineering Planning
**Prüfbereich:** vollständiger Plan vor Execution

### Aufgabe

```text
Verbinde ParkAssist direkt per CAN-FD mit DriverAssistance.
```

### Erwarteter Plan

Mindestens:

```text
inspect model
check capability
check controller
check free channel
create/reuse interface
create/reuse port
connect network
resolve payload
generate/reuse transport
update routing
recalculate capacity
recalculate timing
validate
preflight
completion
```

### Fehler

```text
AGENT_PLAN_INCOMPLETE
AGENT_DEPENDENCY_MISSING
```

### PASS

Alle notwendigen Abhängigkeiten sind vor Ausführung bekannt.

---

# 11. S55 – Skill- und MCP-Tool-Auswahl
**Prüfbereich:** Agent wählt die richtigen Fähigkeiten

### Erwartete Skills

Beispiel:

```text
model.context.resolve
engineering.reason
engineering.plan
communication.route
capacity.calculate
timing.calculate
validation.run
```

### MCP

Agent muss passende registrierte Tools wählen.

Nicht erlaubt:

```text
Tool erfinden
falsches Tool verwenden
UI-Link statt Engineering Tool
```

### Negative Test

Tool Registry enthält kein passendes Tool.

Erwartung:

```text
BLOCKED / NOT_SUPPORTED
```

nicht:

```text
halluzinierter Tool-Erfolg
```

---

# 12. S56 – Autonomous Execution
**Prüfbereich:** Agent führt freigegebenes Ziel selbst aus

### Entscheidung

User bestätigt:

```text
Ja – CAN-FD-Port erstellen und direkt anbinden.
```

### Danach ohne weitere triviale Fragen

Agent führt selbst aus:

```text
Port
Interface
Network Connection
Transport
Routing
Capacity
Timing
Validation
Preflight
```

### Verboten

```text
"Soll ich jetzt Routing aktualisieren?"
"Soll ich jetzt Buslast berechnen?"
"Soll ich validieren?"
```

### Finding

```text
AGENT_UNNECESSARY_DELEGATION
```

### PASS

Agent arbeitet bis zum Zielzustand selbstständig weiter.

---

# 13. S57 – Workload Persistence und Resume
**Prüfbereich:** Agent verliert Auftrag nicht

### Ablauf

```text
Agent arbeitet
↓
Engineering Decision erforderlich
↓
SUSPENDED_FOR_DECISION
↓
User antwortet
↓
RESUME
```

### Prüfe

```text
same workload_id
same goal
same execution_plan
completed steps retained
pending steps retained
```

### UI Reload

Während Entscheidung UI neu laden.

Agent muss danach denselben Auftrag fortsetzen können.

### Fehler

```text
AGENT_WORKLOAD_LOST
AGENT_STARTED_NEW_TASK
```

---

# 14. S58 – Validation und Repair Loop
**Prüfbereich:** Agent erkennt eigene Unvollständigkeit

### Szenario

Routing erfolgreich.

Timing Validation schlägt fehl.

### Falsch

```text
Agent:
"Verbindung erfolgreich erstellt."
COMPLETE
```

### Richtig

```text
Completion = INCOMPLETE
↓
inspect failure
↓
repair candidate
↓
execute repair
↓
revalidate
↓
completion check
```

### Beispiel Repair

```text
message rate reduce
repacking
different route
alternative interface
```

wenn innerhalb der freigegebenen Strategie zulässig.

### PASS

Agent stoppt nicht bei erstem Teilerfolg.

---

# 15. S59 – Completion Evaluator
**Prüfbereich:** Wann ist Agent wirklich fertig?

### CONNECT_FUNCTIONS Completion Contract

Mindestens:

```text
source function resolved
target function resolved
host hardware resolved
required data resolved
interfaces valid
ports valid
network connectivity valid
transport valid
route valid
capacity valid
timing valid
preflight valid
no blocking finding
```

### Test

Ein Punkt fehlt:

```text
timing = UNKNOWN
```

Erwartung:

```text
INCOMPLETE
```

Nicht:

```text
COMPLETE
```

### PASS

Agent meldet Completion nur bei erfülltem Zielvertrag.

---

# 16. S60 – Vollständiger Engineering-Agent-E2E-Test
**Prüfbereich:** gesamter Agent

### User Goal

```text
Verbinde ParkAssist mit DriverAssistance,
prüfe die Kommunikation,
simuliere den Pfad
und analysiere mögliche Timingprobleme.
```

### Agent muss selbst durchführen

```text
Goal Understanding
↓
Typing
↓
Model Inspection
↓
Situation Analysis
↓
Decision Detection
↓
User Question
↓
Resume
↓
Execution Plan
↓
Skill Discovery
↓
MCP Tool Selection
↓
Model Mutation
↓
Routing
↓
Capacity
↓
Timing
↓
Validation
↓
Simulation
↓
Trace
↓
Root Cause
↓
Finding
↓
Completion
```

### Tool Checker prüft getrennt

```text
Agent reasoning contract
Agent execution contract
MCP contract
Core result
Browser result
Simulation result
Trace result
Completion result
```

### PASS

Nur wenn der Agent das vollständige technische Ziel selbst bis zum validierten Ergebnis führt.

---

# 17. Engineering-Agent-Abnahmematrix

| Agent-Fähigkeit | Pflicht |
|---|---|
| Goal Understanding | Ja |
| Typing | Ja |
| Model Awareness | Ja |
| Context Resolution | Ja |
| Reasoning | Ja |
| Decision Detection | Ja |
| Question Quality | Ja |
| Planning | Ja |
| Dependency Planning | Ja |
| Skill Discovery | Ja |
| MCP Tool Selection | Ja |
| Autonomous Execution | Ja |
| Workload Resume | Ja |
| Revision Safety | Ja |
| Validation | Ja |
| Repair Loop | Ja |
| Completion Evaluator | Ja |
| Evidence | Ja |
| Compact Output | Ja |

---

# 18. Agent-Anti-Patterns

Tool Checker muss mindestens erkennen:

```text
AGENT_NO_MODEL_INSPECTION
AGENT_HALLUCINATED_OBJECT
AGENT_DUPLICATE_OBJECT
AGENT_WRONG_GOAL
AGENT_WRONG_TYPING
AGENT_UNNECESSARY_QUESTION
AGENT_MISSING_QUESTION
AGENT_WRONG_TOOL
AGENT_INVENTED_TOOL
AGENT_WRONG_TOOL_ORDER
AGENT_ONLY_NAVIGATES
AGENT_DELEGATES_TO_USER
AGENT_STOPS_AFTER_ONE_TOOL
AGENT_SKIPS_DEPENDENCY
AGENT_SKIPS_VALIDATION
AGENT_NO_REPAIR
AGENT_WORKLOAD_LOST
AGENT_PREMATURE_COMPLETE
AGENT_NO_EVIDENCE
```

---

# 19. Agent Tool-Trajectory Evidence

Für jeden Agent-Test speichern:

```text
goal.json
typing.json
model-context.json
reasoning-result.json
decision.json
execution-plan.json
skill-selection.json
tool-calls.json
tool-results.json
validation.json
repair.json
completion.json
```

---

# 20. Agent-Fragen-Evidence

Zusätzlich:

```text
expected_questions[]
actual_questions[]
forbidden_questions[]
```

Metriken:

```text
correct_question_rate
unnecessary_question_rate
missing_question_rate
```

---

# 21. Agent-Plan-Evidence

Vergleiche:

```text
Expected Dependency Plan
vs.
Actual Dependency Plan
```

Nicht zwingend identische interne Reihenfolge, solange:

```text
alle notwendigen Abhängigkeiten
+
korrekte technische Reihenfolge
```

vorhanden sind.

---

# 22. Tool Sequence Check

Beispiel erwartete Sequenz:

```text
inspect
→ capability
→ port
→ network
→ transport
→ routing
→ capacity
→ timing
→ validation
```

Actual:

```text
inspect
→ routing view link
→ stop
```

Ergebnis:

```text
FAIL
```

---

# 23. Reasoning-Qualität

Der Agent soll nicht nur Tool Calls auslösen.

Er muss nachvollziehbare fachliche Observations liefern.

Beispiel:

```text
Source function uses CAN-FD.
Target function uses Ethernet.
Target controller supports CAN-FD.
No CAN-FD port currently exists.
```

Daraus folgt:

```text
engineering decision required
```

---

# 24. Kein Raw Chain-of-Thought Logging

Nicht speichern:

```text
hidden internal chain of thought
```

Stattdessen strukturierte:

```text
Observations
Evidence
Decision
Plan
Conclusion
```

---

# 25. Revision Safety

Agent muss vor Mutation:

```text
model_revision
```

prüfen.

Ändert sich das Modell während der Planung:

```text
PLAN_STALE
```

Dann:

```text
re-inspect
→ re-plan
```

---

# 26. Permission / Actor Check

Agent Tool Calls müssen:

```text
user actor
project scope
permission
```

mitführen.

Agent darf keine höhere Berechtigung besitzen als der Benutzer.

---

# 27. Engineering Agent vs. Wizard

Verbindliche Trennung:

```text
Wizard
= Einstieg / strukturierte Interaktion

Engineering Agent
= Zielverständnis / Reasoning / Planung / Orchestrierung

MCP
= Capability Layer

Python Core
= Engineering Logic
```

Ein funktionierender Wizard beweist deshalb nicht automatisch einen funktionierenden Engineering Agent.

---

# 28. Engineering Agent vs. MCP

Ein funktionierendes MCP beweist ebenfalls nicht den Agenten.

MCP kann korrekt sein, während Agent:

```text
falsches Tool auswählt
zu früh stoppt
falsche Fragen stellt
Dependencies übersieht
```

Deshalb S51–S60 separat.

---

# 29. Anwendung auf alle Wizard Journeys

Bei jeder der 40 A/B-Wizard-Journeys zusätzlich:

```text
Agent Contract Check
```

ausführen.

Damit prüfen die Szenarien gleichzeitig:

```text
Wizard UX
+
Engineering Agent
+
MCP
+
Core
+
Simulation
+
Trace
```

---

---

# 30. Master-Quality-Gate und Reparaturlogik

## Network Intelligence Simulator
### Master-Test-, Wizard-, Agent-, MCP-, Trace- und Reparaturlogik
### Verbindlicher Umfang: 80 reale Prüfungen / Kennungen S01–S60
### Ziel: Alle Pflichtanforderungen bestehen, kritische Fehler = 0, Restfehlerquote < 1 %

---

## 1. Korrektur des Prüfumfangs

Der verbindliche Prüfumfang besteht aus **80 realen Prüfungen**. Das Kennungsschema reicht von S01 bis S60; S01–S20 enthalten jeweils A- und B-Variante und ergeben dadurch 40 reale fachliche Prüfungen.

Zusammensetzung:

```text
40 fachliche A/B-Szenarien
+
10 Chat-Agent-/MCP-/Skill-/UI-Integrationsprüfungen (S21–S30)
+
10 Trace-Analyse-Prüfungen (S31–S40)
+
10 Wizard-Systemprüfungen (S41–S50)
+
10 Engineering-Agent-Systemprüfungen (S51–S60)
=
80 reale Prüfungen
```

Die Master-Prüflogik darf sich nicht nur auf die ersten 40 fachlichen Szenarien beschränken.

Alle 80 realen Prüfungen gehören zum verbindlichen Quality Gate.

---

## 2. Aufteilung der 60 Prüfungen

### Gruppe A – 40 fachliche Musterprojekte

```text
S01-A
S01-B
S02-A
S02-B
...
S20-A
S20-B
```

Diese 40 Szenarien bilden die eigentlichen Musterprojekte.

Jedes dieser Projekte muss über den echten Hauptwizard:

```text
Neue Projektanlage
```

erzeugt werden.

---

### Gruppe B – 10 Chat-Agent-/MCP-/UI-Prüfungen

```text
S21
S22
S23
S24
S25
S26
S27
S28
S29
S30
```

Diese Prüfungen testen gezielt:

```text
Wizard Entry
Chat Agent
Capability Discovery
MCP Registry
MCP Read Tools
MCP Mutation Tools
Tool Schemas
User Decisions
Workload Resume
Signal Wizard
Trace Wizard
Finding Wizard
Browser Skill
Audit
Completion
```

Diese Prüfungen werden nicht separat von den Musterprojekten betrachtet.

Sie müssen innerhalb der durch Gruppe A erzeugten Projekte ausgeführt werden.

---

### Gruppe C – 10 Trace-Analyse-Prüfungen

```text
S31
S32
S33
S34
S35
S36
S37
S38
S39
S40
```

Diese Prüfungen testen gezielt:

```text
Trace Session
Botschaften
Sequenz
Signale
synchronisierter Trace
Decode
Zeitbasis
Routing-Korrelation
Fault-Korrelation
Golden Trace
First Divergence
Root Cause
Finding
Performance
```

Auch diese Prüfungen sind Bestandteil des gleichen Master-Laufs.

---


### Gruppe D – 10 Wizard-Systemprüfungen

```text
S41
S42
S43
S44
S45
S46
S47
S48
S49
S50
```

Diese Prüfungen testen die Wizard-Infrastruktur selbst: Registry, Skill-Mapping, State/Resume, Validation, MCP/Core-Vertrag, Revision Safety, Persistenz und vollständige Wizard-Regression.

---

### Gruppe E – 10 Engineering-Agent-Systemprüfungen

```text
S51
S52
S53
S54
S55
S56
S57
S58
S59
S60
```

Diese Prüfungen testen den Engineering Agent als eigenes Subsystem: Goal Understanding, Typing, Model Awareness, Decision Detection, Planning, Skill-/MCP-Auswahl, autonome Execution, Resume, Repair Loop und Completion.

---

## 3. Zentrale Testlogik

Der Gesamtprozess lautet:

```text
40 Musterprojekte
↓
Hauptwizard
↓
Projektanlage
↓
Projekt öffnen
↓
alle anwendbaren Wizards
↓
Chat-Agent
↓
MCP
↓
Validation
↓
Positive Simulation
↓
Negative/Fault Simulation
↓
Trace Analyse
↓
S21–S30 Integrationsprüfungen
↓
S31–S40 Trace-Prüfungen
↓
S41–S50 Wizard-Systemprüfungen
↓
S51–S60 Engineering-Agent-Systemprüfungen
↓
Befunde
↓
Reparatur
↓
Re-Test
↓
Regression
↓
Quality Gate
```

---

## 4. Alle 40 Musterprojekte müssen über den Hauptwizard erstellt werden

Verbindlich:

```text
S01-A ... S20-B
```

werden ausschließlich über den produktiven Hauptwizard angelegt.

Nicht als bestandener End-to-End-Test zulässig:

```text
direkter DB-Insert
Fixture-only
Backend Shortcut
manuelle Testdatenanlage außerhalb des Wizards
```

---

## 5. Hauptwizard ist Quality Gate 0

Wenn die Projektanlage fehlschlägt:

```text
PROJECT_CREATION_FAILED
```

gilt:

```text
Scenario = BLOCKED
Quality Gate = FAIL
```

Danach:

```text
Root Cause
→ Fix
→ Re-Test
```

bevor der vollständige Lauf fortgesetzt wird.

---

## 6. Hauptwizard-Prüfkette pro Musterprojekt

Für jedes der 40 Musterprojekte:

```text
1. Hauptwizard öffnen
2. Projektdaten eingeben
3. fachliche Beschreibung eingeben
4. technische Vorgaben übernehmen
5. offene Angaben erfassen
6. Agentenunterstützung auslösen
7. notwendige Rückfragen beantworten
8. Project Proposal erzeugen
9. Proposal prüfen
10. Projekt anlegen
11. Projekt öffnen
12. Project ID prüfen
13. Core Objects prüfen
14. Relationships prüfen
15. Reload durchführen
16. Persistenz erneut prüfen
```

---

## 7. Alle produktiven Wizards in jedem Musterprojekt prüfen

Nach erfolgreicher Projektanlage:

```text
Wizard Registry lesen
↓
alle produktiven Wizards bestimmen
↓
Applicability je Projekt prüfen
↓
alle anwendbaren Wizards ausführen
```

Mindestens:

```text
Architektur erstellen
Signal prüfen
Trace analysieren
Finding bewerten
```

Neue produktive Wizards dürfen nicht unbemerkt außerhalb des Tool Checkers bleiben.

---

## 8. Wizard-Ergebnis

Ein Wizard gilt nicht als bestanden, wenn er nur:

```text
ein Board öffnet
einen Link liefert
einen Prompt vorfüllt
einen statischen Dialog zeigt
```

Er muss einen realen fachlichen Workflow ausführen:

```text
Wizard
→ Agent
→ Skill
→ MCP
→ Core
→ fachliche Wirkung
→ Validation
→ Persistence
→ Completion
```

---

## 9. Chat-Agent in jedem der 40 Musterprojekte

Der Chat-Agent wird nicht nur in S21–S30 geprüft.

Er wird zusätzlich in jedem Musterprojekt ausgeführt.

Pflichtaufgaben pro Projekt:

```text
READ
MUTATION
QUESTION / DECISION
VALIDATION
SIMULATION / ANALYSIS
FOLLOW-UP
```

---

## 10. Chat-Agent Pflichtprüfung: Projektverständnis

Beispiel:

```text
Welche Hardware, Funktionen, Interfaces und Netzwerke enthält dieses Projekt?
```

Erwartung:

```text
Core lesen
→ reale Modellobjekte nennen
→ keine Halluzination
```

---

## 11. Chat-Agent Pflichtprüfung: Änderung

Beispiel:

```text
Verbinde Funktion A mit Funktion B.
```

Erwartung:

```text
Model Inspection
→ Situation Analysis
→ Decision Detection
→ User Question falls nötig
→ Workload Resume
→ MCP Execution
→ Routing
→ Capacity
→ Timing
→ Validation
→ Completion
```

---

## 12. Chat-Agent Pflichtprüfung: Analyse

Beispiel:

```text
Warum ist diese Route ungültig?
```

Erwartung:

```text
Evidence
Model References
Route
Validation Result
```

---

## 13. Chat-Agent Pflichtprüfung: Simulation

Beispiel:

```text
Simuliere den Ausfall dieses Gateways.
```

Erwartung:

```text
Fault Scenario
→ Simulation
→ Universal Trace
→ Trace Analyse
→ Root Cause
→ Finding
```

---

## 14. Chat-Agent Pflichtprüfung: Folgeauftrag

Beispiel:

```text
Behebe das Problem.
```

Der Agent muss den bestehenden Kontext fortsetzen.

Nicht:

```text
neuen unverbundenen Task erzeugen
```

---

## 15. S21–S30 werden zusätzlich als spezialisierte Integrationsprüfungen ausgeführt

Die zehn Integrationsprüfungen bleiben eigenständige Pflichtprüfungen.

Mindestens:

```text
S21 Wizard-/Capability-Einstieg
S22 MCP Capability Discovery
S23 MCP Read Path
S24 MCP Mutation Path
S25 MCP Fehler-/Timeout-Verhalten
S26 Chat Single-/Multi-Choice + Resume
S27 Signal-Wizard
S28 Trace-Wizard
S29 Finding-Wizard
S30 vollständiger Chat-Agent/MCP/Browser-Systemtest
```

---

## 16. S21–S30 müssen reale Musterprojekte verwenden

Nicht:

```text
isolierte Mock-Objekte allein
```

Sondern bevorzugt:

```text
aus Gruppe A erzeugtes Projekt
```

Wenn ein Spezialfall eine kontrollierte Fixture benötigt, muss zusätzlich ein realer Projekt-End-to-End-Lauf vorhanden sein.

---

## 17. Verteilung der S21–S30 über die Musterprojekte

Die zehn Integrationsprüfungen müssen mindestens in mehreren Komplexitätsklassen laufen:

```text
Simple A
Simple B
Medium A
Medium B
Complex A
Complex B
```

Kritische Agent-/MCP-Pfade zusätzlich in allen Projekten als Contract Check.

---

## 18. S31–S40 werden vollständig ausgeführt

Die zehn Trace-Prüfungen sind Pflichtbestandteil.

Mindestens:

```text
S31 Trace Session
S32 Botschaften
S33 Sequenz
S34 Signale / Decode
S35 Synchronisierung
S36 Fault → Trace Evidence
S37 Golden Trace
S38 Root Cause
S39 große Trace-Datenmenge
S40 vollständiger Trace E2E
```

---

## 19. Trace-Prüfung in jedem Musterprojekt

Zusätzlich zu S31–S40 gilt:

```text
jedes Musterprojekt
→ mindestens 1 Positive Simulation
→ mindestens 1 Negative/Fault Simulation
→ TraceSession
→ Botschaften
→ Sequenz
→ Signale
→ synchronisierter Trace
```

---

## 20. Positive Simulation pro Musterprojekt

Pflicht:

```text
Preflight PASS
Simulation starts
Simulation completes
Universal Trace exists
No unexpected blocker
```

---

## 21. Negative/Fault Simulation pro Musterprojekt

Passender reproduzierbarer Fehler:

```text
Signal Stuck
Signal Out of Range
Message Loss
Message Delay
Wrong Cycle
Network Overload
Gateway Delay
Link Down
Node Offline
```

---

## 22. Negative Run muss Finding erzeugen

Erwartung:

```text
Fault
→ Trace Evidence
→ Root Cause
→ Finding
→ Finding Wizard
```

---

## 23. MCP in allen relevanten Pfaden prüfen

MCP-Familien mindestens:

```text
model.*
hardware.*
function.*
signal.*
transport.*
network.*
routing.*
capacity.*
timing.*
validation.*
simulation.*
trace.*
finding.*
```

---

## 24. MCP Contract

Für jeden relevanten Call:

```text
registered tool
input schema valid
output schema valid
actor valid
project scope valid
permission valid
model revision valid
canonical IDs valid
ToolResult structured
trace_id / evidence present
```

---

## 25. Browser Skill ist Pflicht

Reale End-to-End-Prüfung mit Browser Skill:

```text
Hauptwizard öffnen
Projekt anlegen
Projekt öffnen
Wizard klicken
Chat öffnen
Option auswählen
Simulation starten
Trace öffnen
Finding öffnen
Reload
```

---

## 26. UI-Erfolg allein reicht nicht

```text
green UI
≠
test pass
```

Zusätzlich:

```text
Core State
API / MCP State
Model Revision
Routes
Validation
Persistence
```

prüfen.

---

## 27. Befunde werden nicht nur dokumentiert

Verbindlich:

```text
FINDING
≠
END OF WORK
```

Jeder bestätigte Defekt führt zu:

```text
FIND
→ CLASSIFY
→ ROOT CAUSE
→ REPAIR
→ UNIT TEST
→ TARGETED RE-TEST
→ DEPENDENCY REGRESSION
→ CRITICAL JOURNEY RE-RUN
→ CLOSE
```

---

## 28. RepairWorkPackage

Für jeden bestätigten Defekt:

```text
repair_id
finding_ids[]
category
severity
root_cause
affected_files[]
affected_services[]
affected_tests[]
required_fix
acceptance_criteria[]
regression_scope[]
status
```

---

## 29. Defektklassen

Mindestens:

```text
PROJECT_CREATION_BUG
WIZARD_BUG
AGENT_BUG
MCP_BUG
MODEL_BUG
ROUTING_BUG
VALIDATION_BUG
SIMULATION_BUG
TRACE_BUG
PERSISTENCE_BUG
UI_BUG
```

---

## 30. Reparaturmodus

Default:

```text
VERIFY_AND_REPAIR
```

Nicht:

```text
VERIFY_ONLY
```

für den Master-Qualitätslauf.

---

## 31. Verbindlicher Reparaturbefehl

```text
DO NOT STOP AFTER REPORTING FINDINGS.

For every confirmed defect:

1. determine the root cause,
2. implement the smallest architecture-compliant fix,
3. add or update regression tests,
4. rerun the failed test,
5. rerun all directly affected dependent tests,
6. rerun the relevant Browser/Wizard/Agent/MCP flow,
7. verify persistence after reload,
8. store evidence,
9. close the finding only after objective verification.
```

---

## 32. Finding Closure Contract

Ein Finding darf erst geschlossen werden wenn:

```text
root cause known
fix implemented
direct re-test PASS
dependent tests PASS
critical journey PASS
evidence stored
```

---

## 33. Quality Gate 0 – Projektanlage

```text
40 / 40 Musterprojekte
```

müssen erfolgreich über den Hauptwizard entstehen.

Wenn:

```text
39 / 40
```

dann:

```text
QUALITY GATE = FAIL
```

unabhängig von Gesamtfehlerquote.

---

## 34. Quality Gate 1 – Wizards

Für jedes Projekt:

```text
all applicable productive wizards PASS
```

---

## 35. Quality Gate 2 – Chat-Agent

Kritische Chat-Agent-Flows:

```text
100 % PASS
```

---

## 36. Quality Gate 3 – MCP

Kritische MCP-Flows:

```text
READ
MUTATE
CALCULATE
VALIDATE
SIMULATE
ANALYZE
```

müssen funktionieren.

---

## 37. Quality Gate 4 – Validation

```text
Routing
Capacity
Timing
Preflight
```

für alle positiven Runs gültig.

---

## 38. Quality Gate 5 – Simulation

Pro Projekt:

```text
Positive Run PASS
Negative/Fault Run PASS
```

---

## 39. Quality Gate 6 – Trace

Pro Projekt:

```text
TraceSession valid
Botschaften valid
Sequenz valid
Signale valid
Sync valid
```

Für Negative Run:

```text
Root Cause
Finding
Evidence
```

---

## 40. Quality Gate 7 – Persistenz

Nach Reload:

```text
Project
Objects
Relations
Routes
Wizard State
Finding Decisions
```

bleiben korrekt.

---

## 41. Quality Gate 8 – Regression

Jeder Repair muss:

```text
direct test
+
dependent tests
+
critical journey
```

erneut bestehen.

---

## 42. Fehlerquote

Objektive Definition:

```text
Residual Non-Critical Failure Rate
=
failed non-critical assertions
/
executed non-critical assertions
× 100
```

---

## 43. Kritische Fehler werden nicht in die <1-%-Quote eingerechnet

Sie sind harte Blocker.

Verbindlich:

```text
P0 = 0
Blocking P1 = 0
Critical Journey Failures = 0
```

---

## 44. Qualitätsziel

```text
Mandatory Requirements Pass Rate = 100 %
Critical Journey Pass Rate = 100 %
P0 Findings = 0
Blocking P1 Findings = 0
Residual Non-Critical Failure Rate < 1 %
Blocked Mandatory Checks = 0
```

---

## 45. Warum 99 % alleine nicht genügt

Wenn:

```text
Neue Projektanlage
```

nicht funktioniert, darf ein hoher Gesamtwert das Problem nicht verdecken.

Beispiel:

```text
Residual Failure Rate = 0.4 %
Project Creation FAIL
```

Ergebnis:

```text
QUALITY GATE = FAIL
```

---

## 46. Canary-Lauf vor Volltest

Vor dem vollständigen Batch:

```text
CANARY-01 Simple A
CANARY-02 Simple B
CANARY-03 Medium A
CANARY-04 Medium B
CANARY-05 Complex B
```

Jeder Canary beinhaltet:

```text
Main Wizard
Chat Agent
MCP
Validation
Simulation
Trace
```

---

## 47. Bei Canary-Fehler zuerst reparieren

Nicht:

```text
Canary fails
→ trotzdem 40 Projekte starten
```

Sondern:

```text
Canary fails
→ Root Cause
→ Fix
→ Canary Re-Test
→ Full Batch
```

---

## 48. Vollständiger Prüfumfang

Die 80 realen Prüfungen bleiben explizit erhalten:

```text
GROUP A
40 fachliche A/B-Szenarien

GROUP B
10 Chat-Agent-/MCP-/UI-Integrationsprüfungen

GROUP C
10 Trace-Analyse-Prüfungen

GROUP D
10 Wizard-Systemprüfungen

GROUP E
10 Engineering-Agent-Systemprüfungen
```

---

## 49. Gruppen dürfen nicht voneinander isoliert geprüft werden

Verbindlich:

```text
Group A erzeugt echte Projekte
↓
Group B prüft Agent/MCP/Wizard innerhalb dieser Projekte
↓
Group C prüft Simulation/Trace innerhalb dieser Projekte
↓
Group D prüft die Wizard-Infrastruktur innerhalb derselben Projekt-Journeys
↓
Group E prüft den Engineering Agent als eigenes Subsystem und quer über die Projekt-Journeys
```

---

## 50. Mindestabdeckung je Musterprojekt

Jedes der 40 Musterprojekte muss mindestens durchlaufen:

```text
Main Project Wizard
Architecture Wizard
Signal Wizard
Chat-Agent READ
Chat-Agent MUTATION
Chat-Agent DECISION
MCP READ
MCP MUTATION
Routing
Capacity
Timing
Validation
Positive Simulation
Negative Simulation
Trace Wizard
Trace Views
Finding Wizard
Reload / Persistence
```

---

## 51. Zusätzliche Systemtests S21–S60

Die spezialisierten Prüfungen S21–S60 bleiben zusätzlich verpflichtend.

Sie sind keine Ersatztests für die projektbezogene Mindestabdeckung.

---

## 52. Tool Checker Progress

Darstellung:

```text
Tool Checker

64 %

27 / 80 Prüfungen abgeschlossen
```

Zusätzlich:

```text
Projects:
18 / 40 created

Open Findings:
6

Repaired:
14
```

---

## 53. Progress bleibt deterministisch

```text
llm_calls_progress = 0
```

---

## 54. Bericht darf nicht Completion sein

Zwischenbericht:

```text
Findings gefunden
```

ist kein Abschluss.

Completion erst:

```text
Findings repaired
+
Regression PASS
+
Quality Gate PASS
```

---

## 55. Master Completion Contract

Gesamtauftrag ist erst fertig wenn:

```text
ALL 80 TESTS EXECUTED
+
40 / 40 PROJECTS CREATED
+
ALL APPLICABLE WIZARDS PASS
+
CHAT AGENT CRITICAL FLOWS PASS
+
MCP CRITICAL FLOWS PASS
+
VALIDATION PASS
+
POSITIVE SIMULATIONS PASS
+
NEGATIVE SIMULATIONS PASS
+
TRACE ANALYSIS PASS
+
FINDING FLOW PASS
+
PERSISTENCE PASS
+
ALL P0/P1 BLOCKERS RESOLVED
+
MANDATORY PASS RATE = 100 %
+
CRITICAL JOURNEY PASS RATE = 100 %
+
RESIDUAL NON-CRITICAL FAILURE RATE < 1 %
```

---

## 56. Verbindlicher Codex-Befehl

```text
Execute the complete 80-check verification in VERIFY_AND_REPAIR mode.

The test inventory is:

- 40 domain A/B checks (S01-A through S20-B),
- 10 Chat-Agent/MCP/UI integration tests (S21–S30),
- 10 Trace Analysis tests (S31–S40),
- 10 Wizard System tests (S41–S50),
- 10 Engineering Agent System tests (S51–S60).

Do not limit execution to the first 40 domain checks or to S01–S40. S41–S60 are mandatory parts of the same Quality Gate.

Create every domain scenario through the real main project wizard.

Use the generated project pool for the integration and trace tests.

In every project:
- test all applicable productive wizards,
- test the Chat Agent,
- test relevant MCP capabilities,
- validate routing/capacity/timing,
- run positive and negative simulations,
- analyze traces,
- test finding handling,
- reload and verify persistence.

Do not stop after reporting findings.

For every confirmed defect:
- determine root cause,
- implement the smallest architecture-compliant fix,
- add/update regression tests,
- rerun the failed flow,
- rerun dependent flows,
- rerun the real Browser/Wizard/Agent/MCP path,
- store evidence,
- close only after objective verification.

Continue repair loops until:
- all 80 checks are executed,
- all mandatory requirements pass,
- all critical journeys pass,
- P0 = 0,
- blocking P1 = 0,
- blocked mandatory checks = 0,
- residual non-critical failure rate < 1 %.
```

---

## 57. Finaler PASS-Beispiel

```text
TEST INVENTORY
80 / 80 executed

DOMAIN PROJECTS
40 / 40 created

MAIN PROJECT WIZARD
40 / 40 PASS

OTHER WIZARDS
100 % applicable PASS

CHAT AGENT
100 % critical flows PASS

MCP
100 % critical contracts PASS

POSITIVE SIMULATIONS
40 / 40 PASS

NEGATIVE SIMULATIONS
40 / 40 PASS

TRACE
all required project traces PASS

SPECIALIZED INTEGRATION TESTS
10 / 10 PASS

SPECIALIZED TRACE TESTS
10 / 10 PASS

WIZARD SYSTEM TESTS
10 / 10 PASS

ENGINEERING AGENT SYSTEM TESTS
10 / 10 PASS

P0
0

BLOCKING P1
0

BLOCKED MANDATORY
0

RESIDUAL FAILURE RATE
0.7 %

QUALITY GATE
PASS
```

---

## 58. Finaler FAIL-Beispiel

```text
TEST INVENTORY
80 / 80 executed

DOMAIN PROJECTS
40 / 40 created

SPECIALIZED TESTS
40 / 40 executed

PROJECT CREATION
1 critical regression found

RESIDUAL FAILURE RATE
0.5 %

QUALITY GATE
FAIL
```

Ein kritischer Journey schlägt die Prozentquote.

---

## 59. Definition of Done

Diese korrigierte Master-Anweisung gilt erst als erfüllt, wenn:

1. alle 80 realen Prüfungen im Testinventar enthalten sind.
2. keine Begrenzung auf die ersten 40 oder auf S01–S40 erfolgt.
3. alle 40 A/B-Musterprojekte über den Hauptwizard angelegt werden.
4. S21–S30 vollständig ausgeführt werden.
5. S31–S40 vollständig ausgeführt werden.
6. S41–S50 vollständig ausgeführt werden.
7. S51–S60 vollständig ausgeführt werden.
8. S21–S60 reale Projekte aus dem Projektpool verwenden bzw. deren produktive Projektkontexte nutzen.
7. alle produktiven anwendbaren Wizards je Projekt geprüft werden.
8. Chat-Agent je Projekt geprüft wird.
9. MCP je Projekt geprüft wird.
10. Positive Simulation je Projekt läuft.
11. Negative/Fault Simulation je Projekt läuft.
12. Trace Analyse je Projekt läuft.
13. Finding Flow je Projekt geprüft wird.
14. Persistenz nach Reload geprüft wird.
15. Befunde repariert werden.
16. Re-Tests erfolgen.
17. Dependency Regression erfolgt.
18. P0 = 0.
19. Blocking P1 = 0.
20. Blocked Mandatory Checks = 0.
21. Mandatory Pass Rate = 100 %.
22. Critical Journey Pass Rate = 100 %.
23. Residual Non-Critical Failure Rate < 1 %.
24. finaler Quality-Gate-Bericht alle 60 Prüfungen ausweist.

---

## Leitregel

```text
80 CHECKS
→ 40 REAL PROJECTS
→ MAIN WIZARD
→ ALL APPLICABLE WIZARDS
→ CHAT AGENT
→ MCP
→ VALIDATION
→ SIMULATION
→ TRACE
→ FINDINGS
→ FIX
→ RE-TEST
→ REGRESSION
→ QUALITY GATE
```

> **Kein Teil des 80-Prüfungen-Inventars darf außerhalb des Master-Quality-Gates stehen.**

---

# 31. Kanonischer Gesamtabschluss

```text
S01-A … S20-B = 40
S21 … S30     = 10
S31 … S40     = 10
S41 … S50     = 10
S51 … S60     = 10
-------------------
TOTAL          = 80
```

Leitregel:

```text
CREATE THROUGH MAIN WIZARD
→ TEST ALL PRODUCTIVE WIZARDS
→ TEST CHAT AGENT
→ TEST MCP
→ VALIDATE
→ SIMULATE
→ TRACE
→ FIND
→ FIX
→ RE-TEST
→ REGRESSION
→ QUALITY GATE
```

**Kein Finding beendet den Auftrag. Ein bestätigter Defekt muss – sofern keine neue Produktentscheidung erforderlich ist – repariert, erneut geprüft und regressionsseitig abgesichert werden.**
