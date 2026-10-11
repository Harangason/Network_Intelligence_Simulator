# Arbeitsauftrag für Codex
## Erweiterung des zentralen Gateway-Systemdiagramms um Funktionen und Funktions-Mappings

## 1. Ziel

Erweitere das bestehende interaktive Systemdiagramm des **Network Intelligence Simulator** um eine optionale Funktionsebene.

Die bestehende Hardware-Hierarchie bleibt erhalten:

```text
Central Gateway
→ System Frame
→ ECU / Controller
→ Sensor | Actor
```

Zusätzlich sollen Funktionen sichtbar gemacht werden können.

Wichtig:

```text
Function
≠
Child of exactly one ECU
```

Eine Funktion kann mehrere ECUs, Sensoren, Aktoren und Netzwerke betreffen.

Daher darf die Funktion nicht starr als zusätzliche Besitzhierarchie zwischen ECU und Sensor/Aktor modelliert werden.

---

# 2. Grundregel

Nicht:

```text
Gateway
→ System
→ ECU
→ Function
→ Sensor / Actor
```

als generelle fachliche Wahrheit.

Diese Darstellung würde fälschlicherweise suggerieren:

```text
Function belongs to exactly one ECU
```

Stattdessen:

```text
Function
→ mapped_to → ECU / Controller
→ input_from → Sensor
→ output_to → Actor
→ communicates_via → Signal / Message
→ interacts_with → Function
```

---

# 3. Empfohlenes Zielmodell

Innerhalb eines Systemrahmens werden Hardware und Funktionen gemeinsam dargestellt.

```text
CENTRAL GATEWAY
        ↓
SYSTEM FRAME
        ↓
┌──────────────────────────────────┐
│                                  │
▼                                  ▼
FUNCTIONS                       HARDWARE
│                                  │
│                              ECU / Controller
│                                  │
│                              Sensor / Actor
│                                  │
└────────────── MAPPINGS ──────────┘
```

---

# 4. Diagramm-Modi

Implementiere mindestens drei Modi:

```text
[ Hardware ] [ Functions ] [ Combined ]
```

## Hardware

Darstellung:

```text
Gateway
→ System
→ ECU / Controller
→ Sensor / Actor
```

Dieser Modus bleibt die klare Default-Sicht für Hardware, Topologie und Kommunikationsstruktur.

## Functions

Darstellung:

```text
System
→ Function
→ Subfunction
→ Inputs / Outputs
```

Diese Sicht fokussiert die Funktionsstruktur.

## Combined

Darstellung:

```text
Gateway
→ System
   ├── Functions
   ├── ECUs / Controllers
   └── Sensors / Actors
```

plus Mapping-Kanten:

```text
Function ──mapped_to──→ ECU

Function ──input_from──→ Sensor

Function ──output_to──→ Actor

Function ──communicates_via──→ Signal / Message
```

---

# 5. Default-Verhalten

Standardmäßig beim Öffnen:

```text
Hardware Mode
```

Optional:

```text
Show Functions
```

oder Umschalten auf:

```text
Combined
```

Damit bleibt die Ansicht für kleine Projekte übersichtlich.

---

# 6. Function Model

Funktionen müssen aus dem bestehenden Core kommen.

Keine zweite Diagramm-Funktionsdatenbank erzeugen.

Beispiel:

```text
Function
├── id
├── name
├── type
├── parent_function_ref
├── child_function_refs[]
├── mapped_hardware_refs[]
├── input_refs[]
├── output_refs[]
├── signal_refs[]
├── message_refs[]
├── interface_refs[]
├── status
└── provenance
```

---

# 7. Function Ownership

Die Diagrammansicht darf Funktionen nicht fachlich besitzen.

Verbindlich:

```text
Function Manager / Canonical Core
= Source of Truth

Diagram
= Projection / View
```

---

# 8. Mapping statt Ownership

Beispiel:

```text
Brake Control
→ mapped_to → Brake ECU
```

Nicht:

```text
Brake Control
→ owned_by → Brake ECU
```

wenn die tatsächliche Fachlogik dies nicht ausdrücklich definiert.

---

# 9. Distributed Functions

Unterstütze explizit verteilte Funktionen.

Beispiel:

```text
Adaptive Cruise Control
```

kann beteiligt haben:

```text
Radar ECU
Camera ECU
ADAS Controller
Brake ECU
Powertrain ECU
```

Darstellung:

```text
             Adaptive Cruise Control
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
      ADAS ECU    Brake ECU   Powertrain ECU
```

Eine solche Funktion darf nicht unter nur einer ECU dargestellt werden.

---

# 10. Function Mapping Contract

Beispiel:

```text
FunctionHardwareMapping
├── function_ref
├── hardware_ref
├── mapping_type
├── role
├── confidence
├── source
├── status
└── provenance
```

Mögliche Mapping Types:

```text
PRIMARY_EXECUTION

PARTIAL_EXECUTION

SUPPORTING

MONITORING

INPUT_PROVIDER

OUTPUT_PROVIDER
```

---

# 11. Sensor-Input-Beziehung

Beispiel:

```text
WheelSpeedSensor
→ input_to
→ Brake Control
```

Darstellung optional:

```text
Wheel Speed Sensor
      │
      ▼
Brake Control
```

---

# 12. Aktor-Output-Beziehung

Beispiel:

```text
Brake Control
→ output_to
→ Brake Actuator
```

---

# 13. Funktion-zu-Funktion-Beziehungen

Unterstütze:

```text
calls

triggers

depends_on

provides_input_to

receives_output_from

precedes

follows
```

Diese Relationen standardmäßig nicht alle gleichzeitig anzeigen.

---

# 14. Progressive Darstellung

Standard Combined Mode zeigt nur:

```text
Function
→ Hardware Mapping
```

Optional zuschaltbar:

```text
Function Inputs

Function Outputs

Signals

Messages

Interfaces

Function-to-Function Relations
```

---

# 15. Edge Overload vermeiden

Nicht gleichzeitig:

```text
all functions
all hardware mappings
all signals
all messages
all interfaces
all routing paths
```

rendern.

Stattdessen Layer / Filter verwenden.

---

# 16. Layer Controls

Beispiel:

```text
[x] Functions

[x] Hardware Mapping

[ ] Sensors / Inputs

[ ] Actors / Outputs

[ ] Signals

[ ] Messages

[ ] Interfaces

[ ] Function Relations
```

---

# 17. Systemrahmen mit Functions und Hardware

Beispiel:

```text
┌──────────────────────────────────────────────┐
│ MOTION SYSTEM                                │
│                                              │
│ Functions                   Hardware         │
│                                              │
│ Speed Control ─────────────→ Motion ECU      │
│      │                          │             │
│      │                          ├ RPM Sensor  │
│      │                          └ Motor Act.  │
│      │                                        │
│ Torque Control ────────────→ Motion ECU      │
│                                              │
└──────────────────────────────────────────────┘
```

---

# 18. Baum-Interaktion

Auch Functions sollen expand / collapse unterstützen.

Beispiel:

```text
[-] Chassis
    ├── [-] Functions
    │       ├── [-] Brake Control
    │       │       ├── Input: Wheel Speed
    │       │       └── Output: Brake Command
    │       └── [+] Stability Control
    │
    └── [-] Hardware
            ├── Brake ECU
            └── Steering ECU
```

---

# 19. Alternative kompakte Darstellung

Für kompakte Projekte optional:

```text
[-] Brake ECU
    ├── Mapped Functions
    │   ├── Brake Control
    │   └── ABS Control
    │
    ├── Sensors
    │   └── Wheel Speed Sensor
    │
    └── Actors
        └── Brake Actuator
```

Dies ist nur eine View-Projektion.

Die Funktion bleibt fachlich unabhängig.

---

# 20. Hover-Verhalten für Funktionen

Hover auf Function:

```text
highlight function

highlight mapped ECUs

highlight relevant sensors

highlight relevant actors

highlight parent system

dim unrelated objects
```

---

# 21. Hover-Verhalten für ECU

Hover auf ECU:

```text
highlight mapped functions

highlight sensors / actors

highlight parent system

highlight gateway path
```

---

# 22. Selection

Click auf Function:

```text
select Function EngineeringObject
```

Im vorhandenen Detailpanel anzeigen:

```text
Function Name

Description

Parent / Child Functions

Mapped Hardware

Inputs

Outputs

Signals

Messages

Requirements

Validation Status
```

---

# 23. Breadcrumb

Beispiel:

```text
Central Gateway
>
Chassis
>
Brake Control
```

oder Hardware:

```text
Central Gateway
>
Chassis
>
Brake ECU
>
Wheel Speed Sensor
```

---

# 24. Focus Function

Unterstütze:

```text
Focus Function
```

Darstellung:

```text
Selected Function

Mapped Hardware

Inputs

Outputs

Related Functions
```

Andere Objekte dimmen oder temporär ausblenden.

---

# 25. Isolate Function

Context Action:

```text
Isolate Function
```

zeigt ausschließlich:

```text
Function

Parent System

Mapped ECUs

Sensors

Actors

optional Signals / Messages
```

---

# 26. Distributed Function Focus

Bei verteilten Funktionen:

```text
Focus Function
```

muss alle beteiligten Hardwareknoten sichtbar machen.

Beispiel:

```text
Adaptive Cruise Control
        │
        ├ Radar ECU
        ├ Camera ECU
        ├ ADAS ECU
        ├ Brake ECU
        └ Powertrain ECU
```

---

# 27. Search

Suche muss auch Functions finden.

Beispiel:

```text
Search:
Brake Control
```

Erwartung:

```text
expand System

show Function

show mapped Hardware

center viewport

highlight mapping
```

---

# 28. Mapping Status

Function-Hardware-Mappings können Status besitzen:

```text
VALID

INCOMPLETE

UNMAPPED

OUTDATED

CONFLICTING

PROPOSED
```

---

# 29. Unmapped Functions

Funktion ohne Hardware-Mapping nicht still verstecken.

Darstellung:

```text
UNMAPPED FUNCTIONS
```

oder innerhalb des Systemrahmens:

```text
Brake Diagnostics
⚠ no hardware mapping
```

---

# 30. Multi-Mapped Function

Wenn mehrere Hardwareknoten zugeordnet sind:

```text
mapped_count = N
```

sichtbar machen.

---

# 31. Function Summary im Systemrahmen

System Header kann enthalten:

```text
Functions

Mapped Functions

Unmapped Functions

ECUs

Sensors

Actors

Warnings
```

Beispiel:

```text
CHASSIS

8 Functions
4 ECUs
12 Sensors
8 Actors
1 Unmapped Function
```

---

# 32. Gateway Summary

Optional:

```text
Systems

Functions

Controllers

Networks

Current Findings
```

---

# 33. Functional vs Physical Relationship

Kanten visuell unterscheiden.

Mindestens:

```text
Hierarchy Edge

Function Mapping Edge

Input Edge

Output Edge
```

Das genaue Styling aus dem vorhandenen Design System beziehen.

---

# 34. Stable Layout

Beim Einblenden von Functions darf nicht die gesamte Hardwareansicht unkontrolliert springen.

Bevorzugen:

```text
stable hardware positions

function lanes / local overlays

re-layout only affected system
```

---

# 35. Layout innerhalb eines Systemrahmens

Empfohlen:

```text
Functions lane
+
Hardware lane
```

Beispiel:

```text
FUNCTIONS                 HARDWARE

Brake Control  ────────→  Brake ECU

ABS Control    ────────→  Brake ECU

Steering Ctrl  ────────→  Steering ECU
```

---

# 36. Layout für verteilte Funktionen

Bei mehreren Targets:

```text
Function
   ├──→ ECU A
   ├──→ ECU B
   └──→ ECU C
```

Kanten müssen lesbar und kollisionsarm geroutet werden.

---

# 37. View Modes Contract

Beispiel:

```text
DiagramMode =
HARDWARE
FUNCTIONS
COMBINED
```

Optional später:

```text
SIGNAL_FLOW
ROUTING
COMMUNICATION
```

---

# 38. View-State

View State getrennt von Core speichern.

Beispiel:

```text
mode

show_functions

show_inputs

show_outputs

show_signals

show_messages

expanded_functions

expanded_hardware

focused_object

isolated_object

positions

zoom

viewport
```

---

# 39. Keine Core-Veränderung durch View-Toggle

Beispiel:

```text
Show Functions = false
```

darf keinerlei fachliche Mapping-Daten löschen oder verändern.

---

# 40. Python-First-Regel

Python / Core ist verantwortlich für:

```text
Function Resolution

Function Hierarchy

Hardware Mapping

Input / Output Mapping

Validation

Projection Generation
```

Frontend verantwortlich für:

```text
render

interaction

selection

animation

view state
```

---

# 41. Projection Service

Erweitere den bestehenden:

```text
SystemHierarchyProjectionService
```

oder integriere einen:

```text
FunctionalSystemProjectionService
```

Nicht parallel duplizieren, wenn ein geeigneter Projection Service existiert.

---

# 42. Projection Output

Beispiel:

```json
{
  "system": {
    "id": "chassis"
  },
  "functions": [
    {
      "id": "brake-control",
      "mappedHardware": ["brake-ecu"],
      "inputs": ["wheel-speed"],
      "outputs": ["brake-actuator"]
    }
  ],
  "hardware": [
    {
      "id": "brake-ecu"
    }
  ]
}
```

---

# 43. API

Vorhandene API-Governance wiederverwenden.

Fachlich beispielsweise:

```text
GET /projects/{projectId}/hierarchy?mode=combined

GET /projects/{projectId}/functions/{functionId}/mapping

GET /projects/{projectId}/hierarchy/view-state
```

Tatsächliche Endpunkte an bestehende API-Struktur anpassen.

---

# 44. Requirements Integration

Optional Function Details / Overlay:

```text
Function
→ derived_from / satisfies
→ Requirements
```

Nicht standardmäßig alle Requirement-Kanten rendern.

---

# 45. Signal Integration

Optional:

```text
Function
→ consumes
→ Signal

Function
→ produces
→ Signal
```

---

# 46. Message Integration

Optional:

```text
Function
→ communicates_via
→ Message
```

---

# 47. Trace Integration

Optional Context Action:

```text
Open Trace for Function
```

zeigt relevante:

```text
Signals

Messages

Mapped ECUs
```

---

# 48. Analysis Integration

Context Actions:

```text
Open Function Analysis

Open Mapping Validation

Open Communication Analysis
```

---

# 49. Performance

Bei großer Funktionsanzahl:

```text
functions collapsed by default

mapping edges rendered only when needed

lazy details

LOD
```

---

# 50. Level of Detail

Beispiel:

```text
LOD 0
Gateway + Systems

LOD 1
+ Hardware

LOD 2
+ Functions

LOD 3
+ Sensors / Actors

LOD 4
+ Signals / Messages / Mapping Details
```

Alternativ je nach Diagramm-Modus optimieren.

---

# 51. Keine vollständige Mapping-Matrix rendern

Bei:

```text
500 Functions
500 Hardware Nodes
```

nicht alle theoretischen Beziehungen in den Browser laden.

Nur existierende / relevante Mappings projizieren.

---

# 52. Tests

Mindestens:

```text
single ECU function mapping

multiple function to one ECU

one function to multiple ECUs

function with sensor input

function with actor output

unmapped function

nested function

distributed function

expand / collapse

mode switching

search

focus

isolate

view-state persistence
```

---

# 53. Integrationstest

Beispiel:

```text
Central Gateway

System: Chassis

Functions:
- Brake Control
- ABS Control
- Steering Control

Hardware:
- Brake ECU
- Steering ECU

Sensors:
- Wheel Speed Sensor
- Steering Angle Sensor

Actors:
- Brake Actuator
- Steering Actuator
```

Prüfen:

```text
correct mappings

correct input/output relations

correct hierarchy

correct visual modes
```

---

# 54. Distributed Function Test

Beispiel:

```text
Adaptive Cruise Control

Mapped:
- Radar ECU
- Camera ECU
- ADAS ECU
- Brake ECU
- Powertrain ECU
```

Prüfen:

```text
all mappings visible

no false single-owner hierarchy

focus shows all participants
```

---

# 55. Architecture Compliance

Nach Implementierung prüfen:

```text
Functions are not hard-owned by ECUs

Function Manager / Core remains Source of Truth

Diagram only projects mappings

Hardware hierarchy remains intact

Distributed Functions supported

No duplicate Function model

View State separated from Engineering Data

Python owns mapping logic
```

---

# 56. Dokumentation

Erweitere:

```text
docs/diagrams/SYSTEM_HIERARCHY_GATEWAY_TREE.md
```

oder ergänze:

```text
docs/diagrams/SYSTEM_HIERARCHY_FUNCTION_OVERLAY.md
```

Dokumentiere:

```text
Hardware Mode

Functions Mode

Combined Mode

Function Mapping

Distributed Functions

Input / Output Relations

View State

Performance

API

Tests
```

---

# 57. Definition of Done

Die Erweiterung ist erst abgeschlossen, wenn:

1. Hardware Mode weiterhin unverändert funktioniert.
2. Functions Mode vorhanden ist.
3. Combined Mode vorhanden ist.
4. Functions aus dem Canonical Core stammen.
5. keine zweite Function-Datenbank entsteht.
6. Function-to-Hardware-Mappings korrekt dargestellt werden.
7. eine Function mehrere ECUs mappen kann.
8. mehrere Functions dieselbe ECU mappen können.
9. Sensor Inputs sichtbar gemacht werden können.
10. Actor Outputs sichtbar gemacht werden können.
11. Distributed Functions korrekt dargestellt werden.
12. Expand / Collapse für Functions funktioniert.
13. Search Functions automatisch fokussieren kann.
14. Focus Function alle relevanten Teilnehmer zeigt.
15. Isolate Function funktioniert.
16. Unmapped Functions sichtbar bleiben.
17. Mapping Status visualisiert werden kann.
18. View-State von Core-Daten getrennt ist.
19. Python / Core die fachliche Mappinglogik besitzt.
20. Performance bei großen Projekten stabil bleibt.
21. Tests erfolgreich sind.
22. Dokumentation den tatsächlichen As-Built-Stand beschreibt.

---

# 58. Zentrale Leitregel

```text
Hardware describes WHERE something exists.

Functions describe WHAT the system does.

Mappings describe WHERE a function is executed.

Sensors provide inputs.

Actors receive outputs.

The diagram visualizes these relationships
without turning mappings into false ownership.
```

Kurz:

```text
GATEWAY
→ SYSTEM
→ HARDWARE

plus

SYSTEM
→ FUNCTION

connected by

FUNCTION ↔ HARDWARE MAPPING
```

Das Ergebnis soll eine klare Hardwarehierarchie behalten und gleichzeitig die funktionale Architektur sichtbar machen, ohne verteilte Funktionen fachlich falsch in einen starren ECU-Baum zu zwingen.
