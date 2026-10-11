# Arbeitsauftrag für Codex
## Interaktives hierarchisches Systemdiagramm mit zentralem Gateway

## 1. Ziel

Erweitere den **Network Intelligence Simulator** um eine neue interaktive Diagrammansicht für die physische bzw. logische Systemhierarchie.

Das Diagramm soll die folgende Hierarchie darstellen:

```text
Zentrales Gateway
    ↓
Systemrahmen / Systemgruppen
    ↓
ECUs / Controller
    ↓
Sensoren | Aktoren
```

Das **Gateway steht immer zentral** im Diagramm.

Die weiteren Ebenen werden wie bei einem interaktiven Baum vom Gateway aus aufgefächert.

Ziel ist keine einfache statische Baumansicht, sondern ein interaktives Engineering-Diagramm mit:

```text
Expand / Collapse
Selection
Hover Highlighting
Zoom
Pan
Focus
Search
Branch Isolation
Details
Context Actions
```

---

## 2. Grundprinzip

Das Diagramm folgt fachlich:

```text
Gateway
→ System
→ ECU
→ Sensor / Aktor
```

Beispiel:

```text
                         ┌───────────────┐
                         │   Gateway     │
                         │   Central GW  │
                         └──────┬────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
      ┌────────────┐      ┌────────────┐      ┌────────────┐
      │ Powertrain │      │   Chassis  │      │    Body    │
      │   System   │      │   System   │      │   System   │
      └─────┬──────┘      └─────┬──────┘      └─────┬──────┘
            │                   │                   │
       ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
       ▼         ▼         ▼         ▼         ▼         ▼
     ECU A     ECU B     ECU C     ECU D     ECU E     ECU F
       │                     │                   │
   ┌───┴───┐             ┌───┴───┐           ┌───┴───┐
   ▼       ▼             ▼       ▼           ▼       ▼
Sensor   Aktor        Sensor   Aktor      Sensor    Aktor
```

---

## 3. Zentrales Gateway

Das Gateway ist der Root-Knoten.

Regeln:

```text
Gateway:
- immer sichtbar
- immer zentral
- nicht durch Collapse verstecken
- visuell klar hervorgehoben
- dient als Ausgangspunkt aller Systemzweige
```

Falls mehrere Gateways existieren:

```text
Primary / Central Gateway
```

als Root verwenden.

Weitere Gateways können als:

```text
Secondary Gateway
Sub-Gateway
Domain Gateway
```

innerhalb eines Systemzweigs dargestellt werden.

---

## 4. Systemrahmen

Die erste Ebene unterhalb des Gateways sind **Systemrahmen**.

Beispiele:

```text
Powertrain
Chassis
Body
ADAS
Infotainment
Energy
Diagnostics
Thermal
Industrial Cell
Motion
Safety
```

Systemrahmen sind keine normalen Nodes.

Sie sollen als visuelle Container dargestellt werden.

Beispiel:

```text
┌─────────────────────────────────┐
│ Chassis System                  │
│                                 │
│   ECU Brake       ECU Steering  │
│      │                 │         │
│   Sensors            Sensors     │
│                                 │
└─────────────────────────────────┘
```

---

## 5. Systemrahmen-Verhalten

Jeder Systemrahmen:

```text
can expand
can collapse
contains ECUs
contains downstream Sensor/Aktor nodes
shows status summary
shows object counts
```

Beispiel Header:

```text
CHASSIS

4 ECUs
12 Sensors
8 Actors
2 Warnings
```

---

## 6. ECU-Ebene

Innerhalb eines Systemrahmens werden die zugehörigen ECUs bzw. Controller dargestellt.

Industrieneutral behandeln.

Core-Objekt:

```text
HardwareNode
```

Darstellbare Typen beispielsweise:

```text
ECU
PLC
Controller
RobotController
DomainController
ZoneController
Gateway
EmbeddedController
```

Die UI darf `ECU` als typische Darstellung verwenden, aber nicht im Core hardcoden.

---

## 7. Sensor- und Aktor-Ebene

Unterhalb einer ECU:

```text
Sensors
Actors
```

Beispiel:

```text
Motion ECU
├── RPM Sensor
├── Position Sensor
├── Temperature Sensor
├── Motor Driver
└── Brake Actuator
```

Sensoren und Aktoren bilden die Blattknoten des Standardbaums.

---

## 8. Interaktives Baumverhalten

Jede Hierarchieebene muss interaktiv auf- und zuklappbar sein.

Beispiel:

```text
Gateway
├── [+] Powertrain
├── [-] Chassis
│      ├── [-] Brake ECU
│      │      ├── Wheel Speed Sensor
│      │      └── Brake Actuator
│      └── [+] Steering ECU
└── [+] Body
```

---

## 9. Expand / Collapse

Unterstütze:

```text
Expand Node
Collapse Node
Expand Branch
Collapse Branch
Expand All
Collapse All
```

Nicht sichtbar gewordene Child Nodes dürfen nicht weiter gerendert werden.

Das ist auch aus Performance-Sicht wichtig.

---

## 10. Gateway-zentriertes Layout

Das Diagramm soll nicht wie ein klassischer links-nach-rechts Explorer aussehen.

Das zentrale Gateway bleibt geometrischer Mittelpunkt.

Die Systemzweige werden um das Gateway verteilt.

Empfohlen:

```text
radial tree
```

oder:

```text
centered multi-directional tree
```

Beispiel:

```text
                  SYSTEM A
                     │
                     │
SYSTEM D ─────── CENTRAL GW ─────── SYSTEM B
                     │
                     │
                  SYSTEM C
```

---

## 11. Zweite Layoutstufe

Innerhalb eines Systemrahmens darf die Hierarchie lokal klassisch dargestellt werden:

```text
System
  ↓
ECUs
  ↓
Sensors / Actors
```

Dadurch entsteht eine Kombination aus:

```text
Radial System Layout
+
Hierarchical Local Tree
```

---

## 12. Layout Engine

Die Layout-Logik muss klar getrennt werden von:

```text
Engineering Data
```

Implementiere fachlich:

```text
SystemHierarchyLayoutEngine
```

Verantwortung:

```text
calculate root position
calculate system sectors
calculate system frame bounds
calculate ECU positions
calculate leaf positions
calculate edge routes
respect collapsed nodes
preserve stable positions
```

---

## 13. Stabiles Layout

Beim Expand / Collapse dürfen die übrigen Elemente nicht unnötig springen.

Regel:

```text
Stable Layout > Complete Re-layout
```

Wenn möglich:

```text
existing positions retained
affected branch recalculated
```

---

## 14. View-State getrennt von Engineering Truth

Nicht in fachlichen Objekten speichern:

```text
x
y
collapsed
selected
zoom
```

Stattdessen:

```text
DiagramViewState
```

Beispiel:

```text
node_positions
collapsed_nodes
expanded_nodes
hidden_branches
viewport
zoom
selected_object
```

---

## 15. Diagramm ist nur eine View

Verbindlich:

```text
Diagram
≠
Source of Truth
```

Das Diagramm liest:

```text
Hardware Nodes
System Assignments
Sensor / Actor Relations
Gateway Relations
Network Relations
```

aus dem bestehenden Core.

---

## 16. Keine zweite Hierarchie erzeugen

Nicht:

```text
Diagram Tree Data
→ separate fachliche Datenbank
```

sondern:

```text
Canonical Model
→ Hierarchy Projection
→ Diagram
```

---

## 17. Hierarchy Projection

Implementiere backendseitig bzw. im Python-Core:

```text
SystemHierarchyProjectionService
```

Dieser erzeugt die benötigte Diagrammprojektion.

Beispiel:

```json
{
  "root": {
    "id": "gateway-01",
    "type": "gateway"
  },
  "systems": [
    {
      "id": "system-chassis",
      "controllers": [
        {
          "id": "ecu-brake",
          "sensors": [],
          "actors": []
        }
      ]
    }
  ]
}
```

Frontend erhält nur diese Projektion.

---

## 18. Python-First-Regel

Fachliche Hierarchie und Zuordnung in Python.

Frontend:

```text
render
interaction
animation
selection
viewport
```

Python:

```text
hierarchy resolution
system membership
gateway relations
hardware relations
validation
projection generation
```

---

## 19. Node-Typen

Mindestens:

```text
GATEWAY
SYSTEM_FRAME
CONTROLLER
SENSOR
ACTOR
```

Optional später:

```text
NETWORK
INTERFACE
FUNCTION
MESSAGE
```

---

## 20. Visuelle Differenzierung

Jeder Node-Typ muss ohne Lesen des Namens unterscheidbar sein.

Beispiel:

```text
Gateway
→ central / prominent

System
→ frame / container

ECU
→ rectangular controller node

Sensor
→ compact input node

Actor
→ compact output node
```

Farben ausschließlich aus dem bestehenden Theme / Design System beziehen.

Keine hartcodierten Farben, wenn Design Tokens vorhanden sind.

---

## 21. Sensor / Aktor Orientierung

Optional lokal:

```text
Sensors
→ links / oben der ECU

Actors
→ rechts / unten der ECU
```

Dadurch wird die Richtung intuitiver:

```text
Sensor
→ ECU
→ Actor
```

---

## 22. Kanten

Mindestens unterscheiden:

```text
hierarchical ownership
physical connection
logical mapping
```

Die Standardansicht zeigt primär die Hierarchiekanten.

Weitere Verbindungen optional zuschaltbar.

---

## 23. Edge-Overload verhindern

Nicht automatisch alle:

```text
Signals
Messages
Routes
Interfaces
```

gleichzeitig einblenden.

Standard:

```text
Hierarchy Mode
```

Optional:

```text
Network Mode
Signal Flow Mode
Routing Mode
```

---

## 24. Hover Interaction

Beim Hover über einen Node:

```text
highlight node
highlight parent path
highlight direct children
dim unrelated nodes
```

Beispiel:

```text
WheelSpeedSensor
→ Brake ECU
→ Chassis
→ Central Gateway
```

komplett hervorheben.

---

## 25. Selection

Click auf Node:

```text
select object
```

Details im vorhandenen Detailpanel anzeigen.

Kein separates konkurrierendes Informationsmodell bauen.

---

## 26. Breadcrumb

Bei Auswahl:

```text
Central Gateway
>
Chassis
>
Brake ECU
>
Wheel Speed Sensor
```

anzeigen.

---

## 27. Focus Mode

Unterstütze:

```text
Focus Branch
```

Beispiel:

User wählt:

```text
Chassis
```

Dann werden andere Systeme temporär gedimmt oder verborgen.

---

## 28. Isolate

Context Action:

```text
Isolate System
```

zeigt:

```text
Gateway
Selected System
contained ECUs
Sensors / Actors
```

---

## 29. Search

Diagrammsuche:

```text
Search Node
```

Treffer:

```text
automatically expand parent branch
focus node
center viewport
highlight path
```

---

## 30. Statusinformationen

Nodes können kompakte Statusanzeigen besitzen.

Beispiele:

```text
OK
WARNING
ERROR
OUTDATED
UNMAPPED
INCOMPLETE
```

Status aus bestehenden Analyse-/Validation-Services beziehen.

---

## 31. System Summary

Systemrahmen darf aggregierte Informationen anzeigen:

```text
ECU Count
Sensor Count
Actor Count
Network Count
Warnings
Errors
```

Diese Werte nicht im Frontend neu berechnen, wenn sie bereits backendseitig verfügbar sind.

---

## 32. Gateway Summary

Central Gateway optional:

```text
Connected Systems
Connected Networks
Routing Count
Current Warnings
SPOF Status
```

anzeigen.

---

## 33. Single Point of Failure Hinweis

Da ein zentrales Gateway bewusst Teil vieler Architekturen sein kann:

```text
SPOF detected
```

darf visualisiert werden.

Aber akzeptierte Findings berücksichtigen.

Beispiel:

```text
SPOF: ACTIVE
Decision: ACCEPTED_RISK
```

nicht als ungelöster Fehler darstellen.

---

## 34. Dragging

User darf Nodes für die Ansicht verschieben.

Aber:

```text
drag
→ DiagramViewState
```

nicht:

```text
drag
→ engineering topology changed
```

---

## 35. Manual Layout Lock

Optional:

```text
Lock Position
```

damit manuell platzierte Nodes beim nächsten Layout erhalten bleiben.

---

## 36. Auto Layout

Button:

```text
Auto Layout
```

setzt die aktuelle Branch-/Systemstruktur neu.

Nicht automatisch bei jeder kleinen Änderung komplett layouten.

---

## 37. Fit View

Unterstütze:

```text
Fit All
Fit System
Fit Selection
```

---

## 38. Zoom

Unterstütze:

```text
mouse wheel
trackpad
buttons
keyboard
```

---

## 39. Minimap

Bei größeren Projekten optional:

```text
Minimap
```

mit:

```text
Gateway
System Frames
current viewport
```

---

## 40. Progressive Detail

Abhängig vom Zoom-Level:

### Zoomed Out

```text
Gateway
System Frames
```

### Medium

```text
ECUs
```

### Zoomed In

```text
Sensors / Actors
```

Dadurch wird Rendering entlastet.

---

## 41. Level of Detail

Implementiere:

```text
LOD 0:
Gateway + Systems

LOD 1:
+ Controllers

LOD 2:
+ Sensors / Actors

LOD 3:
+ Details / Status / optional connections
```

---

## 42. Performance

Die Diagrammansicht muss auch größere Strukturen handhaben.

Pflicht:

```text
collapsed nodes not rendered
virtualized / projected data
memoized node rendering where useful
bounded frontend state
no full-project object duplication
```

---

## 43. Graph Projection statt Full Project

Frontend lädt nicht das gesamte Projektmodell.

Beispiel:

```text
GET hierarchy projection
```

statt:

```text
GET complete project
```

---

## 44. Lazy Child Loading

Bei sehr großen Projekten optional:

```text
System opened
→ load Controllers

Controller opened
→ load Sensor / Actor children
```

---

## 45. State Persistence

View-State projektbezogen speichern:

```text
expanded systems
expanded controllers
positions
zoom
viewport
layout mode
```

Engineering-Daten bleiben davon getrennt.

---

## 46. Default Startzustand

Beim ersten Öffnen:

```text
Central Gateway
+
all System Frames
```

sichtbar.

ECUs standardmäßig:

```text
collapsed
```

oder abhängig von Projektgröße.

---

## 47. Kleine Projekte

Bei kleinen Projekten:

```text
Gateway
+ Systems
+ ECUs
```

direkt darstellen.

Sensoren / Aktoren bleiben optional aufklappbar.

---

## 48. Große Projekte

Bei großen Projekten:

```text
Gateway
+ Systems
```

Startansicht.

Details erst bei Interaktion laden / rendern.

---

## 49. Kontextmenü

Node Context Menu kann anbieten:

```text
Open Details
Expand
Collapse
Expand Branch
Focus
Isolate
Fit Selection
Show Connections
Open Analysis
Open Trace
```

Nur Aktionen zeigen, die für Node-Typ gültig sind.

---

## 50. Doppelklick

Empfohlene Interaktion:

```text
double click
→ expand / collapse
```

Single click:

```text
select
```

---

## 51. Keyboard Navigation

Optional:

```text
Arrow keys
Enter
Space
Escape
```

für Baum-/Node-Navigation.

---

## 52. Accessibility

Interaktive Elemente benötigen:

```text
keyboard focus
accessible labels
node role descriptions
clear selected state
```

---

## 53. Diagramm-Modi

Mindestens:

```text
Hierarchy
```

Später optional:

```text
Topology
Routing
Communication
Signal Flow
```

Die Hierarchy View bleibt die Default-Darstellung für dieses Diagramm.

---

## 54. Node Data Contract

Beispiel:

```text
HierarchyNode
├── id
├── object_ref
├── node_type
├── label
├── parent_id
├── children_count
├── status
├── system_ref
├── expandable
└── metadata
```

---

## 55. System Frame Contract

```text
SystemFrameProjection
├── id
├── label
├── controller_count
├── sensor_count
├── actor_count
├── warning_count
├── error_count
└── child_refs[]
```

---

## 56. Rendering-Technik

Die konkrete Library kann an die bestehende Simulator-Architektur angepasst werden.

Geeignete Ansätze können sein:

```text
React Flow
Canvas
WebGL-based graph rendering
```

Keine neue Diagramm-Library einführen, wenn bereits eine geeignete produktive Library vorhanden ist.

---

## 57. Wichtig bei React Flow

Falls React Flow verwendet wird:

```text
custom GatewayNode
custom SystemFrameNode / Group
custom ControllerNode
custom SensorNode
custom ActorNode
```

Systeme als Group / Container umsetzen, wenn dies mit der aktuellen Version und Architektur sauber funktioniert.

---

## 58. Keine fachliche Logik im Renderer

Renderer entscheidet nicht:

```text
which ECU belongs to which system
```

Diese Zuordnung kommt aus Python / Core.

Renderer entscheidet nur:

```text
where and how it is shown
```

---

## 59. API

An bestehende API-Governance anpassen.

Fachlich beispielsweise:

```text
GET /projects/{projectId}/hierarchy
GET /projects/{projectId}/hierarchy/{nodeId}/children
GET /projects/{projectId}/hierarchy/view-state
PUT /projects/{projectId}/hierarchy/view-state
```

Nicht zwingend genau diese Pfade verwenden.

Bestehende Endpunkte und Versionierung vorher prüfen.

---

## 60. Fehlerfälle

Sauber darstellen:

```text
ECU without System
Sensor without Controller
Actor without Controller
System without Gateway Mapping
Multiple Parent Conflict
Unknown Hardware Type
```

Nicht still verstecken.

---

## 61. Unmapped Objects

Beispiel eigener Bereich:

```text
UNMAPPED
```

oder Hinweis im Diagramm:

```text
3 Hardware Objects not assigned
```

---

## 62. Keine Datenverluste

Collapse:

```text
only hide
```

nicht:

```text
delete
```

---

## 63. Tests

Mindestens:

```text
Gateway root positioning
System frame generation
ECU assignment
Sensor assignment
Actor assignment
Expand / collapse
Path highlight
Search expansion
Focus mode
View-state persistence
Stable layout
Unmapped objects
Large project rendering
```

---

## 64. Integrationstest

Beispiel:

```text
Central Gateway
3 Systems
6 Controllers
12 Sensors
8 Actors
```

Prüfen:

```text
correct hierarchy
correct system frames
correct parent paths
correct expand state
correct selection
```

---

## 65. Performance-Test

Beispiel:

```text
1 Gateway
20 Systems
200 Controllers
2,000 Sensors / Actors
```

Das Frontend darf nicht automatisch alle 2.000 Blätter rendern.

---

## 66. Architekturkonformität

Nach Implementierung prüfen:

```text
Gateway is central
Systems are first-level frames
Controllers belong to Systems
Sensors / Actors belong to Controllers
Hierarchy is interactive
No duplicate engineering hierarchy
View state separated from Core
Collapsed objects not rendered unnecessarily
Python owns hierarchy logic
```

---

## 67. Dokumentation

Erzeuge:

```text
docs/diagrams/SYSTEM_HIERARCHY_GATEWAY_TREE.md
```

Inhalt:

```text
Purpose
Hierarchy Model
Projection Model
Interaction
Layout
Node Types
System Frames
View State
Performance
API
Tests
Known Limitations
```

---

## 68. Definition of Done

Die Aufgabe ist erst abgeschlossen, wenn:

1. das zentrale Gateway als Root sichtbar ist,
2. das Gateway geometrisch zentral positioniert ist,
3. Systemrahmen um das Gateway angeordnet werden,
4. jeder Systemrahmen seine ECUs enthält,
5. jede ECU ihre Sensoren und Aktoren als Children darstellen kann,
6. System- und ECU-Zweige auf- und zuklappbar sind,
7. Expand / Collapse ohne unnötige Voll-Neuberechnung funktioniert,
8. Hover den kompletten Parent-Pfad hervorhebt,
9. Auswahl mit dem bestehenden Detailpanel verbunden ist,
10. Search automatisch Parent-Zweige öffnet,
11. Focus / Isolate funktioniert,
12. View-State von Engineering-Daten getrennt ist,
13. Dragging nur Layout verändert,
14. Hierarchie aus dem Python-Core / Canonical Model stammt,
15. keine zweite fachliche Tree-Datenbank existiert,
16. große Projekte über LOD / Lazy Loading / Collapse performant bleiben,
17. System Summary und Status korrekt angezeigt werden,
18. akzeptierte Findings korrekt berücksichtigt werden,
19. Tests erfolgreich sind,
20. Dokumentation den tatsächlichen As-Built-Stand beschreibt.

---

## 69. Zielbild

```text
                      SYSTEM 1
                   ┌─────────────┐
                   │ ECU         │
                   │ ├ Sensor    │
                   │ └ Actor     │
                   └──────┬──────┘
                          │
                          │
      SYSTEM 4 ───── CENTRAL GATEWAY ───── SYSTEM 2
                          │
                          │
                   ┌──────┴──────┐
                   │ ECU         │
                   │ ├ Sensor    │
                   │ └ Actor     │
                   └─────────────┘
                      SYSTEM 3
```

Das Gateway bleibt die zentrale Orientierung.

Die Systemrahmen bilden die ersten Hauptzweige.

ECUs bilden die zweite Hierarchieebene.

Sensoren und Aktoren bilden die aufklappbaren Blätter.

Das Ergebnis soll sich wie ein interaktiver Baum bedienen lassen, visuell aber wie ein modernes Engineering-Systemdiagramm wirken.
