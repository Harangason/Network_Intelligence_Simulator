# Arbeitsauftrag für Codex
## Network Intelligence Simulator
## Autonomer modellbewusster Engineering Agent – Goal Completion statt Werkzeug-Navigation

---

# 1. Anlass

Die bisherige Agent-/Reasoning-Definition ist nicht ausreichend.

Nicht ausreichend ist ein Agent, der:

```text
Problem erkennt
→ anderes Board / Werkzeug verlinkt
→ Nutzer soll dort selbst weiterarbeiten
```

Das entspricht nicht dem Ziel des Network Intelligence Simulator.

Der Agent soll ein technisches Ziel **selbstständig bis zum fachlich vollständigen Ergebnis bearbeiten**.

Er muss:

```text
bestehendes Modell verstehen
↓
relevante Objekte und Beziehungen finden
↓
Ist-Situation analysieren
↓
fehlende Entscheidungen erkennen
↓
nur wirklich notwendige Nutzerentscheidungen erfragen
↓
danach alle abhängigen Engineering-Schritte planen
↓
die notwendigen Tools selbst aufrufen
↓
das Modell kontrolliert verändern
↓
abhängige Daten aktualisieren
↓
Routing / Capacity / Timing neu berechnen
↓
validieren
↓
Completion prüfen
```

Ein Deep Link in ein Board ist nur eine **optionale Nachkontrolle für den Nutzer**.

Er ersetzt niemals die eigentliche Arbeit des Agenten.

---

# 2. Zentrale Zieldefinition

Der Engineering Agent ist:

> **ein modellbewusster, zustandsbehafteter Goal-Completion-Orchestrator für technische Kommunikationssysteme.**

Nicht:

> Chatbot + Linksammlung.

Nicht:

> UI-Navigator.

Nicht:

> LLM, das nur Empfehlungen formuliert.

Sondern:

```text
USER GOAL
↓
MODEL UNDERSTANDING
↓
SITUATION ANALYSIS
↓
DECISION DETECTION
↓
PLANNING
↓
EXECUTION
↓
DEPENDENCY UPDATE
↓
VALIDATION
↓
REPAIR
↓
COMPLETION
```

---

# 3. Grundsatz

Verbindlich:

```text
Der Agent soll Arbeit ausführen,
nicht Arbeit an den Nutzer zurückdelegieren.
```

Wenn der Agent die notwendigen Schritte technisch selbst ausführen kann, darf seine Antwort nicht lauten:

```text
"Öffne den Netzwerk-Editor und füge ..."
```

sondern:

```text
"Ich habe die bestehende Topologie geprüft.
Für die gewählte Verbindung sind folgende Änderungen erforderlich.
Ich führe sie nach deiner Entscheidung selbst aus."
```

Nach der Entscheidung:

```text
Agent
→ führt Änderungen aus
→ berechnet neu
→ validiert
→ meldet Ergebnis
```

---

# 4. Links sind sekundär

Deep Links wie:

```text
[Netzwerk öffnen]
[Routing öffnen]
[Hardware Interface anzeigen]
```

dürfen angeboten werden.

Aber erst:

```text
nach der eigentlichen Ausführung
```

oder:

```text
zur optionalen Kontrolle
```

Nicht als Ersatz für:

```text
Create / Update / Route / Calculate / Validate
```

---

# 5. Model Awareness ist Pflicht

Bevor der Agent plant oder schreibt, muss er die bestehende Modellstruktur verstehen.

Er darf keine Architektur aus allgemeinen Annahmen erzeugen, wenn das Projekt bereits entsprechende Objekte enthält.

Er muss mindestens prüfen:

```text
Project
HardwareNodes
Device Classes
Logical Node Addresses
Functions
Function Mappings
Functional Interfaces
Hardware Interfaces
Networks
Technology Bindings
Transport Units
Messages
Signals / DataObjects
Routes
Gateways
Capacity Results
Timing Results
Findings
Simulation State
```

---

# 6. ModelSituation

Implementiere:

```text
ModelSituation
```

mindestens mit:

```text
project_ref
project_revision

target_objects[]
related_objects[]

functions[]
function_mappings[]

hardware_nodes[]
logical_node_addresses[]
hardware_interfaces[]

functional_interfaces[]
payload_elements[]
transport_units[]

networks[]
technology_bindings[]
routes[]
gateways[]

capacity_results[]
timing_results[]

open_findings[]
stale_results[]

assumptions[]
data_gaps[]
```

---

# 7. ModelGraph Query

Der Agent benötigt einen zentralen modellbewussten Query-Service.

Beispiel:

```text
ModelGraphService
```

Funktionen mindestens:

```text
find_object()

find_related_objects()

find_host_hardware(function_ref)

find_functions_on_hardware(hardware_ref)

find_function_interfaces(function_ref)

find_hardware_interfaces(hardware_ref)

find_network_membership(hardware_ref)

find_networks_for_interface(interface_ref)

find_routes_between(source_ref, target_ref)

find_transport_units_between(source_ref, target_ref)

find_gateways_between(source_ref, target_ref)

find_upstream_dependencies()

find_downstream_dependencies()

find_technology_bindings()

find_available_hardware_capabilities()
```

---

# 8. Kein Arbeiten aus UI-State allein

Der Agent darf nicht nur wissen:

```text
current_view = Hardware
selected_row = ECU_1
```

sondern muss auf den kanonischen Modellgraphen zugreifen.

UI Context ist nur zusätzlicher Kontext.

Verbindlich:

```text
UI Selection
→ resolve Core Object
→ inspect Canonical Model
→ reason over actual relationships
```

---

# 9. Intent → Desired State

Der Nutzer beschreibt ein Ziel.

Beispiel:

```text
"Der Parkassistent soll mit der Fahrerassistenz verbunden werden."
```

Der Agent erzeugt daraus nicht sofort einzelne Tool Calls.

Zuerst:

```text
DesiredState
```

Beispiel:

```text
ParkAssist Function
must be able to exchange required data
with
DriverAssistance Function
through a valid communication path.
```

---

# 10. DesiredState Contract

Implementiere:

```text
DesiredEngineeringState
```

mit:

```text
goal
target_objects[]
required_relationships[]
required_connectivity[]
required_transport[]
required_validation[]
optional_constraints[]
completion_criteria[]
```

---

# 11. Bestehende Struktur zuerst untersuchen

Für das Beispiel Parkassistent muss der Agent zuerst feststellen:

```text
Wo ist ParkAssist im Modell verortet?
```

Prüfen:

```text
Function
↓
mapped HardwareNode
↓
Hardware Interfaces
↓
Networks
↓
Technology Bindings
↓
existing Routes
```

Danach:

```text
Wo ist DriverAssistance verortet?
```

Wieder:

```text
Function
↓
mapped HardwareNode
↓
Hardware Interfaces
↓
Networks
↓
Technology Bindings
↓
existing Routes
```

Erst danach darf eine Verbindungsstrategie vorgeschlagen werden.

---

# 12. Keine stereotypen Automotive-Annahmen

Nicht:

```text
ParkAssist gehört immer ins Fahrwerk.
```

Nicht:

```text
DriverAssistance ist immer Ethernet.
```

Sondern:

```text
inspect actual project model
```

Wenn das Modell zeigt:

```text
ParkAssist
→ ChassisController
→ CAN_FD_CH1
→ Chassis_CAN

DriverAssistance
→ ADAS_Controller
→ ETH_1
→ ADAS_ETHERNET
```

dann basiert die weitere Planung genau auf diesem Projektzustand.

---

# 13. Situation Summary

Der Agent soll intern eine Situation erzeugen wie:

```text
SOURCE FUNCTION
ParkAssist

HOST
ChassisController
Logical Address: 0x0012

AVAILABLE COMMUNICATION
CAN_FD_CH1
Network: Chassis_CAN

TARGET FUNCTION
DriverAssistance

HOST
ADAS_Controller
Logical Address: 0x0020

AVAILABLE COMMUNICATION
ETH_1
Network: ADAS_ETHERNET

CURRENT DIRECT ROUTE
NONE

CURRENT GATEWAY ROUTE
NONE / or detected route

TECHNOLOGY MISMATCH
CAN-FD ↔ Ethernet
```

---

# 14. Reasoning über Verbindungsoptionen

Der Agent bestimmt technisch mögliche Kandidaten.

Beispiel:

```text
Option A
ParkAssist / ChassisController
→ direkte CAN-FD-Anbindung
→ ADAS_Controller erhält / nutzt CAN-FD Interface

Option B
ParkAssist CAN-FD
→ existing Gateway
→ Ethernet
→ ADAS_Controller

Option C
ChassisController erhält Ethernet
→ direkte Ethernet-Anbindung
```

Nur tatsächlich modell- und hardwareseitig mögliche Optionen dürfen angeboten werden.

---

# 15. Capability Check vor Nutzerfrage

Bevor eine Option angeboten wird, muss Python prüfen:

```text
Does ADAS_Controller support CAN-FD?
Is a CAN controller available?
Is a port/channel free?
Can existing Chassis_CAN be extended?
Is topology valid?
Is a Gateway already available?
Can required payload fit?
Does expected bandwidth fit?
```

Ungültige Optionen nicht als gleichwertige Wahl anbieten.

---

# 16. Nutzer nur bei echter Architekturentscheidung fragen

Wenn mehrere fachlich valide Varianten existieren und keine davon aus Projektregeln eindeutig folgt:

```text
BLOCKED_BY_ENGINEERING_DECISION
```

Dann fragt der Agent.

Beispiel:

```text
ParkAssist ist aktuell über CAN-FD angebunden.
DriverAssistance liegt auf dem ADAS_Controller und nutzt Ethernet.

Der ADAS_Controller unterstützt zusätzlich CAN-FD.

Soll die Verbindung direkt über CAN-FD aufgebaut werden?

○ Ja – ADAS_Controller direkt an Chassis_CAN anbinden
○ Nein – vorhandenen / neuen Gateway-Pfad verwenden
○ Ethernet-Anbindung des ParkAssist-Pfads prüfen
```

---

# 17. Entscheidung ist ein Authorization Envelope

Wenn der Nutzer auswählt:

```text
Ja – direkte CAN-FD-Anbindung
```

dann bedeutet dies:

> Der Agent ist autorisiert, alle technisch notwendigen abhängigen Schritte innerhalb dieses gewählten Lösungswegs auszuführen.

Der Agent darf danach nicht für jeden impliziten Folgeschritt erneut fragen:

```text
"Soll ich den Netzwerk-Editor aktualisieren?"
"Soll ich Routing ändern?"
"Soll ich Buslast berechnen?"
"Soll ich validieren?"
```

Diese Schritte sind Bestandteil des freigegebenen Ziels.

---

# 18. Bounded Authorization

Implementiere:

```text
ExecutionAuthorization
```

mit:

```text
decision_id
approved_goal
approved_strategy
allowed_change_types[]
affected_scope[]
forbidden_changes[]
expires_on_context_change
```

---

# 19. Wann erneut gefragt werden muss

Neue Nutzerentscheidung nur wenn während der Ausführung eine neue relevante Alternative entsteht.

Beispiele:

```text
kein freier CAN Controller vorhanden

neuer HardwareNode wäre erforderlich

bestehender Bus überschreitet Kapazitätsgrenze

Sicherheits-/Architekturregel verbietet Lösung

zwei gleichwertige Netzwerke vorhanden

Technology change required

bestehende freigegebene Route müsste aufgehoben werden
```

Dann:

```text
PAUSE WORKLOAD
→ ask focused question
→ preserve state
→ resume after answer
```

---

# 20. Nach "Ja – direkte CAN-FD-Anbindung"

Der Agent muss selbst einen vollständigen Dependency Plan erzeugen.

Beispiel:

```text
1. Re-read current model revision

2. Validate ADAS_Controller CAN-FD capability

3. Reuse existing compatible CAN-FD HardwareInterface
   OR
   create a new HardwareInterface proposal if capability permits

4. Connect ADAS_Controller interface to Chassis_CAN
   OR
   create required network segment if explicitly necessary

5. Update topology relations

6. Resolve ParkAssist FunctionalInterface

7. Resolve DriverAssistance FunctionalInterface

8. Determine exchanged PayloadElements

9. Reuse existing TransportUnits where semantically valid

10. Generate / update CAN-FD TransportUnits if missing

11. Pack required signals/data according to CAN-FD rules

12. Allocate identifiers without collisions

13. Bind TransportUnits to source / destination hardware interfaces

14. Create / update route entries

15. Remove or supersede obsolete route entries only if required

16. Recalculate interface load

17. Recalculate network load

18. Recalculate timing / deadlines

19. Validate LogicalNodeAddress resolution

20. Validate route completeness

21. Validate technology compatibility

22. Validate message packing

23. Validate capacity

24. Validate timing

25. Run communication preflight

26. Mark affected simulation results / traces STALE

27. Update all projections / views from the Core

28. Run Completion Evaluator
```

---

# 21. Netzwerk-Editor wird nicht manuell gepflegt

Der Netzwerk-Editor ist eine Projektion auf das Modell.

Wenn der Agent:

```text
HardwareInterface
Network Membership
Connection
```

korrekt im Core ändert, muss der Netzwerk-Editor daraus automatisch aktualisiert werden.

Nicht:

```text
Core change
+
separate hidden Network Editor truth
```

---

# 22. Routing Table wird aktiv geändert

Der Agent muss Routing nicht nur anzeigen.

Er muss über autorisierte Services:

```text
create route
update route
supersede route
invalidate route
validate route
```

ausführen können.

---

# 23. Routing Delta

Vor Änderung:

```text
RoutingDelta
```

berechnen.

Beispiel:

```text
Existing:
ParkAssist → no route → DriverAssistance

Desired:
ParkAssist
→ Chassis_CAN
→ ADAS_CAN_FD_1
→ DriverAssistance
```

oder bei vorhandenen Einträgen:

```text
KEEP:
unaffected routes

UPDATE:
route R-18

ADD:
route R-24

SUPERSEDE:
route R-09
```

---

# 24. Keine pauschale Routing-Neuerzeugung

Nicht:

```text
delete all routes
→ regenerate everything
```

Sondern:

```text
impact-scoped delta
```

Nur betroffene Einträge verändern.

---

# 25. Relationship Impact Resolver

Implementiere:

```text
EngineeringImpactResolver
```

Input:

```text
proposed model delta
```

Output:

```text
affected_objects
affected_relations
affected_routes
affected_transport_units
affected_networks
affected_calculations
affected_simulation_runs
affected_trace_results
required_revalidation
```

---

# 26. Model Delta

Jeder Plan erzeugt:

```text
EngineeringModelDelta
```

mindestens:

```text
create[]
update[]
supersede[]
invalidate[]
recalculate[]
validate[]
```

---

# 27. Plan vor Execution

Der Agent plant zuerst vollständig.

```text
Goal
↓
Current Model
↓
Desired State
↓
Gap
↓
Model Delta
↓
Dependency Plan
↓
Execution
```

Nicht:

```text
first tool call
↓
think later
```

---

# 28. Dependency Graph

Plan-Schritte besitzen Abhängigkeiten.

Beispiel:

```text
CAN HardwareInterface
        ↓
Network Membership
        ↓
Transport Binding
        ↓
Route
        ↓
Capacity
        ↓
Timing
        ↓
Validation
```

Ein Schritt darf erst ausgeführt werden, wenn seine Voraussetzungen erfüllt sind.

---

# 29. EngineeringExecutionPlan

Implementiere:

```text
EngineeringExecutionPlan
├── plan_id
├── goal
├── model_revision
├── strategy
├── authorization_ref
├── steps[]
├── dependencies[]
├── validation_steps[]
├── rollback_strategy
└── completion_criteria[]
```

---

# 30. Execution Step

```text
EngineeringExecutionStep
├── step_id
├── action
├── target_refs[]
├── tool
├── inputs
├── prerequisites[]
├── expected_result
├── validation
├── rollback
└── status
```

Status:

```text
PENDING
READY
RUNNING
SUCCEEDED
FAILED
BLOCKED
ROLLED_BACK
SKIPPED
```

---

# 31. Agent führt Tools selbst aus

Verbindlicher Pfad:

```text
EngineeringAgent
↓
MCP Client
↓
MCP Tool
↓
Python Core Service
↓
Canonical Model
```

Frontend-Buttons sind nicht die primäre Ausführungslogik.

Der Agent darf dieselben Services verwenden wie die UI.

---

# 32. MCP Tool Families

Mindestens:

```text
model.inspect.*
hardware.inspect.*
hardware.interface.*
function.inspect.*
function.interface.*
network.*
technology.binding.*
transport.*
message.*
signal.*
routing.*
capacity.*
timing.*
validation.*
simulation.*
trace.*
```

---

# 33. Mutation Tools

Keine generischen:

```text
update_anything()
```

Sondern kontrollierte Engineering Commands.

Beispiele:

```text
create_hardware_interface()
connect_interface_to_network()
bind_transport_unit()
create_route()
update_route()
supersede_route()
pack_transport_unit()
allocate_identifier()
recalculate_network_load()
recalculate_timing()
run_communication_preflight()
```

---

# 34. Existing Object Reuse

Vor jeder Neuanlage prüfen:

```text
Does compatible object already exist?
```

Beispiele:

```text
existing CAN-FD interface?
existing network?
existing signal?
existing TransportUnit?
existing route?
```

Grundregel:

```text
REUSE
before
CREATE
```

wenn semantisch und technisch korrekt.

---

# 35. Keine Duplikate erzeugen

Der Agent darf nicht wegen fehlender Context-Nutzung erzeugen:

```text
CAN_FD_1
CAN_FD_1_copy
CAN_FD_2_new
```

wenn bereits ein geeignetes Interface existiert.

---

# 36. Technology Binding Awareness

Wenn Quelle CAN-FD und Ziel Ethernet verwenden, muss der Agent erkennen:

```text
technology boundary
```

und prüfen:

```text
direct common interface possible?
gateway available?
protocol conversion available?
payload semantics compatible?
```

---

# 37. Gateway Reasoning

Bei Gateway-Pfad prüfen:

```text
input technology
output technology
supported protocol conversion
routing capability
queueing
latency
capacity
logical addresses
```

Ein Gateway ist nicht nur ein grafischer Zwischenknoten.

---

# 38. Transport Semantics

Der Agent muss unterscheiden:

```text
Signal
DataObject
Service
Stream
```

und darf nicht jedes Datum automatisch in eine CAN-artige Message pressen.

---

# 39. CAN-FD Beispiel

Wenn direkte CAN-FD-Verbindung gewählt wurde:

```text
PayloadElements
↓
group by:
- producer
- timing
- receiver set
- criticality
↓
pack
↓
valid CAN-FD DLC
↓
identifier allocation
↓
TransportUnit
↓
HardwareInterface
↓
Network
↓
Route
```

---

# 40. Logical Node Address

Routing verwendet:

```text
LogicalNodeAddress
```

zur stabilen Node-Auflösung.

Nicht direkt als:

```text
CAN ID
IP Address
```

missbrauchen.

---

# 41. Capacity muss automatisch folgen

Nach jeder topologischen oder Transportänderung:

```text
affected network
↓
recalculate load
```

Nicht dem Nutzer sagen:

```text
"Bitte anschließend Buslastanalyse starten."
```

Agent startet sie selbst.

---

# 42. Timing muss automatisch folgen

Wenn Message / Route / Network verändert wurde:

```text
recalculate:
cycle
latency
deadline
jitter
route delay
queue effects
```

soweit für die Technologie unterstützt.

---

# 43. Validation muss automatisch folgen

Nach Ausführung:

```text
Model Validation
↓
Topology Validation
↓
Address Validation
↓
Binding Validation
↓
Transport Validation
↓
Routing Validation
↓
Capacity Validation
↓
Timing Validation
↓
Communication Preflight
```

---

# 44. Completion ist Zielzustand, nicht Tool-Erfolg

Verbindlich:

```text
tool succeeded
≠ task complete
```

Completion bedeutet beim Beispiel mindestens:

```text
ParkAssist located
DriverAssistance located

valid communication strategy approved

required HardwareInterfaces exist

network connectivity exists

required PayloadElements bound

TransportUnits valid

route exists

route resolves source → destination

no identifier conflict

capacity valid

timing valid

preflight valid

all affected views reflect same Core state

no blocking finding remains
```

---

# 45. CompletionEvaluator

Implementiere:

```text
GoalCompletionEvaluator
```

Input:

```text
DesiredEngineeringState
CurrentModelSituation
ExecutionPlan
ValidationResults
```

Output:

```text
COMPLETE
INCOMPLETE
BLOCKED
FAILED
READY_FOR_REVIEW
```

mit:

```text
missing_conditions[]
blocking_findings[]
remaining_decisions[]
```

---

# 46. Repair Loop

Wenn Completion:

```text
INCOMPLETE
```

Agent muss:

```text
inspect missing conditions
↓
create repair steps
↓
execute
↓
revalidate
↓
recount
↓
completion check
```

Nicht einfach abbrechen.

---

# 47. Failure Handling

Wenn ein Step fehlschlägt:

```text
classify failure
↓
can repair automatically?
├── YES → repair
└── NO  → rollback / pause / ask
```

---

# 48. Atomicity

Mehrere zusammengehörige Core-Änderungen sollen möglichst:

```text
transactional
```

oder über kontrollierte:

```text
proposal / command batch
```

laufen.

Keine halbfertige Topologie hinterlassen.

---

# 49. Revision Safety

Vor Mutation:

```text
expected model revision
```

prüfen.

Wenn sich Modell zwischen Planung und Ausführung geändert hat:

```text
PLAN_STALE
```

Dann:

```text
re-inspect
re-plan
```

Nicht blind ausführen.

---

# 50. Execution Journal

Persistiere:

```text
EngineeringExecutionJournal
```

mit:

```text
goal
decision
plan
model_revision
steps
tool_results
changes
validation_results
completion_result
```

---

# 51. Chat-Verhalten

Der Chat soll nicht jeden internen Schritt als Frage präsentieren.

Schlecht:

```text
Soll ich Hardware Interface erstellen?
Soll ich CAN verbinden?
Soll ich Routing ändern?
Soll ich Buslast berechnen?
Soll ich validieren?
```

Gut:

```text
"ParkAssist liegt auf CAN-FD, DriverAssistance aktuell auf Ethernet.
Der ADAS-Controller unterstützt zusätzlich CAN-FD.

Soll ich die Fahrerassistenz direkt an Chassis_CAN anbinden
oder über einen Gateway-Pfad routen?"
```

Nach Auswahl:

```text
Agent executes complete plan.
```

---

# 52. Progress im Chat

Kompakt:

```text
Direkte CAN-FD-Anbindung wird umgesetzt …

✓ Modellkontext geprüft
✓ CAN-FD-Fähigkeit bestätigt
✓ Hardware Interface angebunden
✓ Netzwerk aktualisiert
✓ TransportUnits angepasst
✓ Routing aktualisiert
✓ Buslast neu berechnet
● Timing wird validiert
○ Preflight
```

---

# 53. Ergebnis im Chat

Beispiel:

```text
Verbindung hergestellt und validiert.

ParkAssist
0x0012
ChassisController
        │
        └── CAN-FD / Chassis_CAN
                    │
                    └── ADAS_Controller
                        0x0020
                        │
                        └── DriverAssistance

Routing:
✓ gültig

CAN-FD Buslast:
58 % → 64 %

Timing:
✓ innerhalb Grenzwert

Preflight:
✓ bestanden

Betroffene ältere Simulationen:
STALE: 2
```

Optional:

```text
[Netzwerk ansehen]
[Routing ansehen]
[Validierungsdetails]
[Simulation starten]
```

---

# 54. Optionaler nächster Schritt statt Pflichtdelegation

Nach erfolgreicher Validierung kann Agent anbieten:

```text
"Die Architektur ist simulationsbereit.
Soll ich den Kommunikationspfad jetzt simulieren?"
```

Wenn der ursprüngliche Auftrag bereits Simulation umfasste:

```text
nicht erneut fragen
→ Simulation direkt ausführen
```

---

# 55. Scope Inheritance

Der Agent muss aus dem ursprünglichen User Goal ableiten, welche Folgeschritte enthalten sind.

Beispiel:

```text
"Verbinde ParkAssist mit DriverAssistance und prüfe,
ob die Kommunikation funktioniert."
```

enthält automatisch:

```text
model update
network update
routing
capacity
timing
validation
simulation / functional communication check
trace analysis if needed
```

Nicht jedes Teilziel neu bestätigen lassen.

---

# 56. Goal Types

Mindestens:

```text
CREATE_ARCHITECTURE
CONNECT_FUNCTIONS
CONNECT_HARDWARE
ADD_NETWORK
CHANGE_ROUTE
OPTIMIZE_NETWORK
FIX_VALIDATION
SIMULATE_SCENARIO
ANALYZE_TRACE
FIX_TRACE_ROOT_CAUSE
COMPARE_ARCHITECTURES
```

Jeder Goal Type besitzt einen Default Completion Contract.

---

# 57. CONNECT_FUNCTIONS Completion Contract

Für:

```text
CONNECT_FUNCTIONS
```

mindestens:

```text
source function exists
target function exists
source host resolved
target host resolved
required data identified
functional interface relation valid
technology path valid
hardware interfaces valid
network membership valid
transport valid
route valid
capacity valid
timing valid
preflight valid
```

---

# 58. Änderungsfolgen

Nach erfolgreicher Modelländerung:

```text
SimulationSnapshot
SimulationRun
TraceAnalysis
CapacityResult
TimingResult
```

die von alten Revisionen abhängen:

```text
STALE / OUTDATED
```

markieren.

---

# 59. Views automatisch synchron

Betroffene Views:

```text
Hardware
Hardware Interface
Function
Interface
Transport / Message
Signal
Network Editor
Routing
Analysis
Simulation
Trace
```

lesen dieselbe Core-Wahrheit.

Es gibt keinen separaten manuellen "View Update"-Datensatz.

---

# 60. Reasoning + Execution müssen getrennt, aber verbunden sein

```text
Reasoning
→ determines what must happen

Planner
→ orders required steps

Executor
→ performs steps

Validator
→ proves result

Completion Evaluator
→ decides whether goal is fulfilled
```

---

# 61. Reasoning darf nicht bei Empfehlung enden

Nicht:

```text
"I recommend adding a CAN interface."
END
```

Sondern:

```text
Recommendation required?
↓
user decision
↓
execution authorization
↓
implement
↓
validate
↓
complete
```

---

# 62. Beispiel – vollständiger ParkAssist-Ablauf

User:

```text
"Der Parkassistent soll Daten mit der Fahrerassistenz austauschen."
```

Agent intern:

```text
STEP A – Resolve intent
Need bidirectional / defined data exchange between functions.

STEP B – Inspect ParkAssist
Function: ParkAssist
Host: ChassisController
Logical Address: 0x0012
Network: Chassis_CAN
Technology: CAN-FD

STEP C – Inspect DriverAssistance
Function: DriverAssistance
Host: ADAS_Controller
Logical Address: 0x0020
Network: ADAS_ETHERNET
Technology: Ethernet

STEP D – Inspect existing relations
No valid route found.

STEP E – Inspect capabilities
ADAS_Controller:
ETH_1 = used
CAN_FD capability = available
CAN channel = free

STEP F – Evaluate candidates
A direct CAN-FD
B gateway CAN↔Ethernet
C add Ethernet path to source

STEP G – ask ONE engineering decision
```

Chat:

```text
ParkAssist ist aktuell auf Chassis_CAN verortet.
DriverAssistance läuft auf dem ADAS_Controller über Ethernet.

Der ADAS_Controller besitzt einen freien CAN-FD-Kanal.

Soll ich den ADAS_Controller direkt an Chassis_CAN anbinden?

○ Ja – direkte CAN-FD-Verbindung
○ Nein – Gateway-Pfad prüfen
○ Ethernet-Pfad für ParkAssist prüfen
```

User:

```text
Ja.
```

Agent:

```text
STEP H – Authorization envelope created

STEP I – Revalidate model revision

STEP J – Create/reuse ADAS CAN-FD HardwareInterface

STEP K – Connect interface to Chassis_CAN

STEP L – Update topology relationships

STEP M – Resolve exchanged data

STEP N – Bind / generate CAN-FD TransportUnits

STEP O – Pack signals

STEP P – Allocate CAN identifiers

STEP Q – Update Routing Table

STEP R – Recalculate interface/network load

STEP S – Recalculate timing

STEP T – Run validation chain

STEP U – Run communication preflight

STEP V – Mark old downstream results stale

STEP W – Completion check
```

Nur wenn beispielsweise bei STEP R herauskommt:

```text
Chassis_CAN = 94 %
capacity policy violated
```

entsteht eine neue echte Entscheidung:

```text
Die direkte Verbindung ist technisch möglich,
überschreitet aber die zulässige Buslast.

○ Nachrichtenrate optimieren
○ separaten CAN-FD-Kanal verwenden
○ Gateway/Ethernet-Variante wählen
```

---

# 63. Keine unnötigen Fragen

Der Agent fragt nicht zu Dingen, die:

```text
deterministisch ableitbar
bereits im Modell definiert
durch Projektpolicy festgelegt
Teil des freigegebenen Goals
```

sind.

---

# 64. Data Gap Handling

Wenn Informationen fehlen, unterscheiden:

```text
can infer safely from Core
→ continue

can calculate
→ calculate

can use configured default
→ apply and record

requires engineering decision
→ ask user
```

---

# 65. Assumptions

Jede automatisch verwendete Annahme erhält:

```text
assumption
source
scope
confidence
reason
```

Kritische Annahmen benötigen Nutzerentscheidung.

---

# 66. Agent darf laufende Aufgabe nicht vergessen

Nach einer Frage:

```text
Workload = SUSPENDED_FOR_DECISION
```

Nach Antwort:

```text
Workload = RESUME
```

Nicht neuen unabhängigen Chat-Task beginnen.

---

# 67. Persistence der Workload

Persistiere:

```text
goal
current plan
completed steps
pending steps
pending decision
authorization
model revision
validation state
```

---

# 68. MCP ist Capability Layer, nicht UI Router

MCP Tool darf:

```text
create_route
connect_network
calculate_load
validate_binding
```

ausführen.

Nicht nur:

```text
open_routing_view
open_network_editor
```

Navigationstools können zusätzlich existieren, sind aber sekundär.

---

# 69. Python-First

Verbindlich:

```text
Agent
→ MCP
→ Python Core
```

Die fachliche Engineering-Logik lebt nicht im LLM und nicht im Frontend.

---

# 70. Tests – Navigation darf nicht Completion sein

Negativtest:

```text
Agent detects missing route
→ returns link to Routing View
```

Erwartung:

```text
TEST FAIL
```

wenn der Agent selbst die Route erstellen dürfte.

---

# 71. Tests – Automatic Follow-up

User approves direct CAN-FD.

Erwartet ohne weitere Fragen:

```text
interface
network membership
transport binding
routing
capacity
timing
preflight
completion
```

---

# 72. Tests – Existing Interface Reuse

Wenn ADAS_Controller bereits passendes CAN-FD Interface besitzt:

```text
reuse existing interface
```

Kein neues Interface erzeugen.

---

# 73. Tests – Capacity Blocker

Wenn direkte Anbindung Buslimit überschreitet:

```text
pause
ask decision
```

Nicht stillschweigend zweiten Bus erzeugen.

---

# 74. Tests – Revision Change

Modell ändert sich nach Plan, vor Execution.

Erwartung:

```text
PLAN_STALE
→ re-inspect
→ re-plan
```

---

# 75. Tests – Partial Failure

Route write succeeds, timing update fails.

Erwartung:

```text
repair or rollback
```

Kein falsches:

```text
COMPLETED
```

---

# 76. Tests – Completion

Task darf nur abgeschlossen werden, wenn:

```text
desired state
+
all mandatory validations
+
no unresolved blocker
```

erfüllt sind.

---

# 77. E2E Pflichtszenario ParkAssist

Automatisierter End-to-End-Test:

```text
ParkAssist Function
mapped to ChassisController
with CAN-FD

DriverAssistance Function
mapped to ADAS_Controller
with Ethernet

ADAS_Controller has available CAN-FD capability

No current route
```

User decision:

```text
DIRECT_CAN_FD
```

System muss danach selbst:

```text
resolve objects
create/reuse HNI
connect network
bind transport
pack signals
allocate identifiers
update routing
calculate capacity
calculate timing
validate
preflight
mark stale results
complete
```

prüfbar durchführen.

---

# 78. Definition of Done

Die Agentenarchitektur gilt erst als fachlich ausreichend, wenn:

1. Agent bestehendes Modell vor Planung vollständig inspiziert.
2. Funktionen auf ihre tatsächlichen HardwareNodes aufgelöst werden.
3. HardwareInterfaces und Networks berücksichtigt werden.
4. bestehende Technology Bindings berücksichtigt werden.
5. bestehende Routen berücksichtigt werden.
6. Agent Zielzustände statt nur Tool Calls plant.
7. EngineeringModelDelta erzeugt wird.
8. Dependency Plan erzeugt wird.
9. Nutzer nur bei echten Architekturentscheidungen gefragt wird.
10. Nutzerentscheidung einen begrenzten Ausführungsauftrag autorisiert.
11. Agent danach notwendige Folgeschritte selbst ausführt.
12. Netzwerkänderungen selbst ausgeführt werden.
13. Routingänderungen selbst ausgeführt werden.
14. Transport-/Message-Anpassungen selbst ausgeführt werden.
15. Capacity automatisch neu berechnet wird.
16. Timing automatisch neu berechnet wird.
17. vollständige Validation automatisch läuft.
18. Preflight automatisch läuft.
19. alte abhängige Ergebnisse als stale markiert werden.
20. Completion Evaluator den Zielzustand prüft.
21. Repair Loop existiert.
22. Revision Safety existiert.
23. Existing Objects bevorzugt wiederverwendet werden.
24. Agent nicht unnötig neue Interfaces/Networks erzeugt.
25. Deep Links nur Zusatzkomfort sind.
26. MCP echte Engineering-Aktionen bereitstellt.
27. Python Core die Fachlogik enthält.
28. Workload nach Nutzerentscheidung fortgesetzt wird.
29. Execution Journal vorhanden ist.
30. ParkAssist-E2E-Szenario vollständig bestanden ist.

---

# 79. Leitregel

```text
DO NOT TELL THE USER WHICH TOOL TO USE
WHEN THE AGENT CAN USE THE TOOL ITSELF.
```

Und:

```text
UNDERSTAND MODEL
→ DETERMINE GAP
→ ASK ONLY NECESSARY DECISION
→ PLAN ALL DEPENDENCIES
→ EXECUTE
→ RECALCULATE
→ VALIDATE
→ REPAIR
→ COMPLETE
```

> **Der Engineering Agent ist dafür verantwortlich, ein freigegebenes technisches Ziel vollständig umzusetzen – nicht dafür, den Nutzer durch eine Reihe von Werkzeugen zu schicken.**
