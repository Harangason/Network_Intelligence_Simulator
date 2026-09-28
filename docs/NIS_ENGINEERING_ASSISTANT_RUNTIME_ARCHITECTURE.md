# Network Intelligence Simulator (NIS)
## Engineering Assistant Runtime Architecture
## Vom Chatfenster zum ausführenden Engineering Assistant

---

# 1. Ausgangslage

Der aktuelle Zustand zeigt:

```text
USER
↓
CHAT UI
↓
ENGINEERING-AGENT ENDPOINT
↓
500 / nicht verfügbar
```

Ein Beispielauftrag wie:

```text
"Erstelle ein einfaches Projekt mit einem Controller,
einem Druck Sensor und einem Ventil Aktor."
```

endet aktuell in einem Fehler.

Damit ist die Oberfläche zwar vorhanden, aber funktional noch kein echter:

```text
Engineering Assistant
```

vorhanden.

Das Ziel ist ausdrücklich **nicht**, lediglich einen besseren Chat zu bauen.

Das Ziel ist:

```text
ENGINEERING ASSISTANT RUNTIME
```

Der Chat ist nur eine von mehreren möglichen Bedienoberflächen.

---

# 2. Produktdefinition

Der Engineering Assistant ist ein:

```text
model-aware
stateful
goal-oriented
engineering execution system
```

Er muss:

```text
User Intent verstehen
↓
Modellkontext lesen
↓
Engineering Goal bestimmen
↓
fehlende Entscheidungen erkennen
↓
Execution Plan erzeugen
↓
Skills / MCP / Core-Funktionen auswählen
↓
Engineering-Arbeit ausführen
↓
abhängige Berechnungen durchführen
↓
Validation / Preflight ausführen
↓
Completion prüfen
↓
Engineering Result zurückgeben
```

---

# 3. Chat ist nur UI

Verbindliche Regel:

```text
CHAT UI
≠
ENGINEERING ASSISTANT
```

Sondern:

```text
Chat UI
↓
EngineeringAssistantService
```

Die UI darf:

```text
Prompt erfassen
Fragen anzeigen
Entscheidungen darstellen
Progress anzeigen
Resultate anzeigen
Deep Links anbieten
```

aber keine Engineering-Fachlogik enthalten.

---

# 4. Zielarchitektur

```text
USER
↓
CHAT UI
↓
ENGINEERING ASSISTANT RUNTIME
├── Goal Resolver
├── Context Resolver
├── Workload Manager
├── Engineering Planner
├── Capability Registry
├── Skill Registry
├── MCP Adapter
├── Executor
├── Recovery Manager
├── Completion Evaluator
└── Result Composer
↓
PYTHON ENGINEERING CORE
↓
CANONICAL MODEL
↓
VALIDATION / PREFLIGHT
↓
ENGINEERING RESULT
```

---

# 5. Architekturregel

```text
ONE ENGINEERING RUNTIME
→ MANY ENTRY POINTS
```

Mögliche Einstiegspunkte:

```text
Chat
Wizard
CLI
REST API
MCP
Automation
```

Alle verwenden dieselbe Engineering-Logik.

---

# 6. Keine Wizard-Abhängigkeit

Heute darf der User nicht gezwungen werden:

```text
Chat
→ Wizard öffnen
→ manuell weiterarbeiten
```

Ziel:

```text
Chat
→ Engineering Goal
→ Skill / Capability
→ Core
→ Result
```

Wizards bleiben erhalten, sind aber nur:

```text
guided entry points
```

---

# 7. Wizards als Skill-Frontends

Zielmodell:

```text
Wizard ──────────┐
                 ↓
Chat ─────────→ Skill
                 ↓
REST API ──────→ Core
                 ↑
MCP ────────────┘
```

Damit existiert keine zweite Fachlogik im Wizard.

---

# 8. Goal Resolver

Jede Nutzereingabe wird zuerst in ein strukturiertes Engineering Goal übersetzt.

Beispiel:

```text
"Erstelle ein einfaches Projekt mit einem Controller,
einem Druck Sensor und einem Ventil Aktor."
```

wird zu:

```text
GoalType:
CREATE_PROJECT

RequestedObjects:
- 1 Controller
- 1 PressureSensor
- 1 ValveActuator
```

---

# 9. Goal Contract

Beispiel:

```text
EngineeringGoal
├── goal_id
├── goal_type
├── project_context
├── requested_objects
├── requested_changes
├── timing_constraints
├── technology_constraints
├── target_objects
├── user_constraints
├── required_outcomes
└── unresolved_decisions
```

---

# 10. Unterstützte Goal Types

Mindestens:

```text
CREATE_PROJECT
CREATE_HARDWARE
CREATE_FUNCTION
CREATE_SIGNAL
CREATE_NETWORK
CONNECT_OBJECTS
CHANGE_CONFIGURATION
VALIDATE_MODEL
CALCULATE_CAPACITY
CALCULATE_TIMING
RUN_SIMULATION
ANALYZE_TRACE
MEASURE_E2E
DIAGNOSE
REPAIR
OPTIMIZE
EXPLAIN
COMPARE
REMOVE
```

---

# 11. Unterstützte Action Intents

Der Assistant muss natürliche Formulierungen erkennen:

```text
erstelle
lege an
füge hinzu
verbinde
ändere
konfiguriere
entferne
prüfe
finde
berechne
simuliere
analysiere
diagnostiziere
repariere
optimiere
zeige
vergleiche
```

---

# 12. Beispiel 1 – einfaches Projekt

Eingabe:

```text
"Erstelle ein einfaches Projekt mit einem Controller,
einem Druck Sensor und einem Ventil Aktor."
```

Erwartete Ausführung:

```text
CREATE_PROJECT
↓
Project anlegen
↓
Hardware
├── Controller
├── PressureSensor
└── ValveActuator
↓
Functions
├── PressureAcquire
├── Processing / Control
└── ValveCommand
↓
Data
├── PressureValue
└── ValveCommand / ValveState
↓
Mappings
↓
Relationships
↓
Validation
↓
COMPLETED
```

---

# 13. Technologie bei unvollständiger Vorgabe

Wenn der User keine Kommunikationstechnologie nennt:

Nicht:

```text
CAN-FD erfinden
```

Nicht:

```text
PROFINET erfinden
```

Sondern:

```text
Technology = UNASSIGNED
```

oder:

```text
REVIEW_REQUIRED
```

je nach Modellregel.

Das Projekt darf trotzdem erstellt werden.

---

# 14. Beispielresultat

Nach erfolgreicher Ausführung:

```text
Projekt erstellt:
SimplePressureControl

Hardware:
✓ 1 Controller
✓ 1 Drucksensor
✓ 1 Ventilaktor

Funktionen:
✓ PressureAcquire
✓ ValveControl

Daten:
✓ PressureValue
✓ ValveCommand

Validation:
✓ Modellstruktur gültig

Offen:
⚠ Kommunikationstechnologie noch nicht festgelegt
```

---

# 15. Links sind nur Navigation

Nach dem Ergebnis dürfen Links angeboten werden:

```text
[Projekt öffnen]
[Architektur ansehen]
[Validation öffnen]
```

Aber:

```text
Link
≠
Engineering Result
```

---

# 16. Beispiel 2 – ECU mit 30-s-Abfrage

Eingabe:

```text
"Lege eine ECU an, die mir die Stellgliedpositionen
im System alle 30 Sekunden abfragt."
```

Der Assistant muss erkennen:

```text
Goal:
CREATE_PERIODIC_ACQUISITION

Target:
all actuator position data

Requester:
new ECU

Trigger:
CYCLIC

Cycle:
30 s
```

---

# 17. Ausführung für den 30-s-Auftrag

```text
Model inspect
↓
alle Aktoren suchen
↓
Stellgliedpositionsdaten bestimmen
↓
bestehende Signals / DataObjects suchen
↓
neue ECU anlegen
↓
Acquisition Function anlegen
↓
cycle_time = 30 s
↓
Producer / Consumer bestimmen
↓
Functional Interfaces
↓
Hardware Interfaces / Ports
↓
Signals / DataObjects
↓
Transport Units
↓
Routing
↓
Capacity
↓
Timing
↓
Validation / Preflight
↓
Completion
```

---

# 18. Fehlende Stellgliedpositionsdaten

Beispiel:

```text
8 Aktoren gefunden
6 liefern Positionsdaten
2 liefern keine Positionsinformation
```

Ergebnis:

```text
6 Pfade erstellt
2 Findings erzeugt
```

Finding:

```text
ACTUATOR_POSITION_DATA_MISSING
```

Nicht:

```text
generic ERROR
```

---

# 19. Follow-up-Kontext

Der Assistant benötigt persistenten Engineering-Kontext.

```text
ConversationContext
├── active_project
├── active_workload
├── selected_objects
├── last_goal
├── last_result
├── active_findings
├── last_validation
├── pending_decisions
└── model_revision
```

---

# 20. Beispiel Follow-up

Nach einem eindeutigen Fehler:

```text
"Dann weißt du ja, was du zu tun hast:
Fehleranalyse und Korrektur."
```

Der Assistant muss auflösen:

```text
"den Fehler"
→ aktuelles eindeutiges Finding
```

---

# 21. Follow-up-Ausführung

```text
active finding
↓
Evidence laden
↓
Root Cause bestimmen
↓
Repair Scope
↓
Repair Plan
↓
Repair
↓
Validation
↓
Result
```

---

# 22. Kein unnötiges Nachfragen

Nicht:

```text
"Welchen Fehler meinen Sie?"
```

wenn nur ein eindeutiger aktiver Fehler vorhanden ist.

Nur wenn mehrere unabhängige aktive Findings existieren:

```text
WAITING_FOR_ENGINEERING_DECISION
```

---

# 23. Anaphorische Folgeaufträge

Der Assistant muss verstehen:

```text
"Mach das auch für die anderen Aktoren."
```

```text
"Ändere das auf 30 Sekunden."
```

```text
"Prüfe das gleiche für CAN-FD."
```

```text
"Behebe die restlichen Fehler."
```

---

# 24. Workload statt Einzelprompt

Intern soll nicht nur eine Chat-Nachricht verarbeitet werden.

Einführung:

```text
EngineeringWorkload
```

---

# 25. EngineeringWorkload

Beispiel:

```text
Workload:
WL-00471

Goal:
CREATE_PERIODIC_ACQUISITION

Status:
IN_PROGRESS

Project:
Project_001

Required Outcomes:
✓ ECU
✓ Acquisition Function
✓ Cycle = 30 s
□ Data Bindings
□ Routing
□ Validation
□ Completion
```

---

# 26. Workload-Status

Mindestens:

```text
RECEIVED
PLANNING
WAITING_FOR_ENGINEERING_DECISION
IN_PROGRESS
VALIDATING
REPAIRING
INCOMPLETE
BLOCKED
READY_FOR_REVIEW
COMPLETED
FAILED
```

---

# 27. Engineering Planner

Der Planner bestimmt:

```text
Goal
↓
Required Outcomes
↓
Dependencies
↓
Execution Plan
```

---

# 28. Execution Plan

Beispiel:

```text
WP01 inspect current model
WP02 identify actuators
WP03 identify position data
WP04 create ECU
WP05 create acquisition function
WP06 create/reuse signals
WP07 create interfaces
WP08 create/reuse transport
WP09 route data
WP10 calculate capacity/timing
WP11 validate
WP12 completion check
```

---

# 29. Capability Registry

Der Assistant benötigt eine Capability Registry.

Nicht:

```text
LLM guesses tool names
```

Sondern:

```text
CapabilityRegistry
```

---

# 30. Beispiel Capability Registry

```text
Project
├── project.create
├── project.inspect
└── project.validate

Hardware
├── hardware.search
├── hardware.create
├── hardware.inspect
├── hardware.map
└── hardware.validate

Function
├── function.search
├── function.create
├── function.inspect
└── function.map

Communication
├── signal.search
├── signal.create
├── transport.generate
├── network.connect
└── routing.generate

Analysis
├── capacity.calculate
├── timing.calculate
└── validation.run

Simulation
├── simulation.prepare
├── simulation.run
└── simulation.inspect

Trace
├── trace.analyze
├── trace.e2e
└── trace.root_cause

Repair
├── finding.inspect
├── repair.plan
├── repair.apply
└── repair.validate
```

---

# 31. Capability Discovery

Pipeline:

```text
Goal
↓
Required Capabilities
↓
Capability Registry
↓
Available Skills / MCP Tools / Core Services
↓
Execution Plan
```

---

# 32. Keine Giant-if-Logik

Nicht:

```text
if project:
if hardware:
if network:
if trace:
...
```

Sondern registry-/strategy-basiert.

---

# 33. Python Core bleibt Engineering-Wahrheit

Verbindlich:

```text
LLM
→ Reasoning / Intent / Planning

Python Core
→ Engineering Logic

Canonical Model
→ Truth
```

---

# 34. Keine Engineering-Formeln im Prompt

Nicht:

```text
LLM calculates busload from free text
```

Sondern:

```text
capacity.calculate
```

---

# 35. Lokale deterministische Verarbeitung

Einfache Befehle sollen ohne externes großes LLM funktionieren können.

Beispiel:

```text
"Erstelle ein Projekt mit
1 Controller
1 Drucksensor
1 Ventilaktor."
```

Pipeline:

```text
Intent Parser
↓
Entity Extraction
↓
Schema Validation
↓
Deterministic Planner
↓
Python Core
```

---

# 36. LLM nur bei echter Semantik

LLM wird benötigt bei:

```text
ambiguous engineering intent
complex architecture reasoning
novel technology
root-cause hypotheses
natural-language explanation
```

Nicht bei:

```text
CRUD
deterministic mapping
validation
calculation
known workflow
```

---

# 37. Engineering Assistant Recovery

Der aktuelle Fehler:

```text
Engineering-Agent nicht verfügbar (500)
```

darf nicht direkt der normale Endzustand eines Workloads sein.

---

# 38. Recovery Pipeline

```text
Tool / Agent Failure
↓
Failure Classification
↓
transient?
├── yes → Retry
└── no
    ↓
precondition missing?
├── yes → repair precondition
└── no
    ↓
alternative valid execution path?
├── yes → use it
└── no
    ↓
BLOCKED_WITH_EXPLICIT_CAUSE
```

---

# 39. Zulässige Endzustände

Ein verständlicher Engineering-Auftrag muss enden in:

```text
COMPLETED
WAITING_FOR_ENGINEERING_DECISION
BLOCKED_WITH_EXPLICIT_CAUSE
NOT_SUPPORTED_WITH_CAPABILITY_GAP
```

---

# 40. Nicht zulässiger Normalzustand

Nicht:

```text
generic ERROR
```

wenn die Funktion grundsätzlich unterstützt ist.

---

# 41. Engineering Assistant Execution Defect

Wenn ein verständlicher unterstützter Auftrag in:

```text
500
generic error
no action
```

endet:

```text
ENGINEERING_ASSISTANT_EXECUTION_DEFECT
```

---

# 42. Completion Evaluator

Tool Success bedeutet nicht:

```text
Goal Complete
```

---

# 43. Beispiel

```text
ECU created
```

ist für den Auftrag:

```text
"ECU, die alle 30 s Stellgliedpositionen abfragt"
```

noch nicht ausreichend.

---

# 44. Completion Criteria

Mindestens:

```text
ECU exists
Function exists
30-s timing exists
data sources resolved
interfaces valid
transport valid
routing valid
capacity/timing evaluated
validation executed
blocking findings reported
```

---

# 45. Completion Contract

```text
CompletionEvaluator
├── required_outcomes
├── achieved_outcomes
├── missing_outcomes
├── blocking_findings
└── status
```

---

# 46. Assistant Evidence

Für jeden schreibenden Auftrag speichern:

```text
user_intent
resolved_goal
model_context
execution_plan
objects_reused
objects_created
objects_modified
engineering_decisions
skills_used
mcp_tools_used
model_before
model_after
model_diff
validation
completion
```

---

# 47. Model Diff

Pflicht für Mutationen:

```text
before
vs
after
```

Beispiel:

```text
+ Project SimplePressureControl
+ Controller Controller_1
+ PressureSensor PressureSensor_1
+ ValveActuator ValveActuator_1
+ Function PressureAcquire
+ Function ValveControl
```

---

# 48. Engineering Assistant UI

Das Chatfenster darf bestehen bleiben.

Aber der sichtbare Bereich:

```text
Fähigkeiten und Wizards
```

wird zu:

```text
optional shortcuts
```

---

# 49. Empfohlenes UI-Ziel

```text
Engineering Assistant

[ Fähigkeiten & Wizards ]

User:
Erstelle ein einfaches Projekt ...

Assistant:
Projekt wird erstellt.

Progress:
42 %

...

Result:
Projekt erfolgreich erstellt.

[Projekt öffnen]
[Architektur]
[Validation]
```

---

# 50. Kein Tool-Debug im Hauptchat

Nicht:

```text
calling project.create
calling hardware.create
...
```

Standardmäßig anzeigen.

---

# 51. Activity Log separat

Details:

```text
Aktivitätsprotokoll
```

können enthalten:

```text
Goal resolved
Model inspected
3 objects created
Validation executed
```

---

# 52. Progress

Kompakt:

```text
0–99 %
```

100 % erst bei:

```text
Completion Evaluator = COMPLETED
```

---

# 53. Progress ohne LLM

```text
llm_calls_progress = 0
```

Progress wird deterministisch aus Workload-Schritten berechnet.

---

# 54. Engineering Assistant Backend-Struktur

Empfohlen:

```text
backend/
└── engineering_assistant/
    ├── service.py
    ├── goal_resolver.py
    ├── context_resolver.py
    ├── workload.py
    ├── planner.py
    ├── capability_registry.py
    ├── executor.py
    ├── recovery.py
    ├── completion.py
    │
    ├── goals/
    │   ├── project.py
    │   ├── hardware.py
    │   ├── function.py
    │   ├── communication.py
    │   ├── validation.py
    │   ├── simulation.py
    │   ├── trace.py
    │   └── repair.py
    │
    └── contracts/
        ├── input.py
        ├── context.py
        ├── plan.py
        └── result.py
```

---

# 55. service.py

Hauptschnittstelle:

```text
EngineeringAssistantService
```

Aufgaben:

```text
receive input
resolve context
resolve goal
build workload
plan
execute
validate
complete
compose result
```

---

# 56. goal_resolver.py

Aufgaben:

```text
natural language
↓
EngineeringGoal
```

---

# 57. context_resolver.py

Aufgaben:

```text
active project
selected object
previous workload
last finding
pending decision
model revision
```

---

# 58. workload.py

Persistiert:

```text
EngineeringWorkload
```

---

# 59. planner.py

Erzeugt:

```text
EngineeringExecutionPlan
```

---

# 60. capability_registry.py

Liefert:

```text
available capabilities
schemas
permissions
versions
```

---

# 61. executor.py

Führt:

```text
Skills
MCP
Python Core
```

aus.

---

# 62. recovery.py

Behandelt:

```text
timeout
invalid precondition
tool unavailable
stale plan
revision conflict
```

---

# 63. completion.py

Prüft:

```text
Goal Completion
```

nicht:

```text
Tool Completion
```

---

# 64. Revision Safety

Vor Mutationen:

```text
model_revision
```

merken.

Vor Apply:

```text
current_revision == planned_revision?
```

Wenn nicht:

```text
PLAN_STALE
```

→ neu planen.

---

# 65. REUSE before CREATE

Vor neuen Objekten:

```text
search existing
```

Beispiel:

```text
PressureSensor exists?
```

Wenn fachlich dasselbe Objekt existiert:

```text
REUSE
```

statt Duplikat.

---

# 66. Natürliche Kommunikation für alle NIS-Bereiche

Die gleiche Kommunikationsart muss funktionieren für:

```text
Project
Hardware
Function
Signal / DataObject
Interface / Port
Network
Technology Binding
Transport
Routing
Capacity
Timing
Validation / Preflight
Simulation
Trace Analysis
E2E
Finding / Repair
```

---

# 67. Beispiele

```text
"Füge einen zweiten CAN-FD-Kanal hinzu."
```

```text
"Verbinde Controller A mit Gateway B."
```

```text
"Ändere LIN auf 19,2 kbit/s und berechne alles neu."
```

```text
"Prüfe, warum PressureCommand zu spät ankommt."
```

```text
"Simuliere den Ausfall des Gateways."
```

```text
"Finde alle Signale ohne Consumer."
```

```text
"Behebe die eindeutigen Validation-Fehler."
```

```text
"Zeige mir die E2E-Verbindung von Function A zu Function B."
```

---

# 68. Periodische Sprachmuster

Der Assistant muss erkennen:

```text
alle 30 Sekunden
alle 100 ms
zyklisch
bei Änderung
bei Ereignis
bei Fehler
auf Anfrage
```

und übersetzen zu:

```text
CYCLIC
ON_CHANGE
EVENT_DRIVEN
FAULT_TRIGGERED
ON_REQUEST
```

---

# 69. Deterministische Informationen nicht erneut fragen

Wenn der User sagt:

```text
alle 30 Sekunden
```

darf der Assistant nicht fragen:

```text
"Welchen Zyklus möchten Sie?"
```

---

# 70. Engineering Decisions

Nur echte fachliche Entscheidungen erfragen.

Beispiel:

```text
Für die neue ECU sind zwei technisch valide Anbindungen möglich:

○ bestehendes CAN-FD-Segment
○ Ethernet über Gateway
```

---

# 71. Keine irrelevanten Rückfragen

Nicht:

```text
"Wie soll die ECU heißen?"
```

wenn ein systematischer Name generiert werden kann.

---

# 72. Skill- und MCP-Auswahl

Der Assistant soll notwendige Fähigkeiten selbst auswählen.

Nicht:

```text
"Bitte öffnen Sie den Routing Wizard."
```

---

# 73. Assistant muss Fehler analysieren können

Beispiel:

```text
"Warum funktioniert die Verbindung nicht?"
```

Erwartung:

```text
Model inspect
↓
Validation
↓
Routing
↓
Interfaces
↓
Technology
↓
Findings
↓
Root Cause
```

---

# 74. Assistant muss reparieren können

Beispiel:

```text
"Behebe den Fehler."
```

Wenn eindeutig und autorisiert:

```text
Root Cause
↓
Repair Plan
↓
Repair
↓
Revalidation
```

---

# 75. Assistant darf Security-/Safety-Governance nicht umgehen

Nicht:

```text
repair by weakening validation
```

oder:

```text
disable security
```

um einen Test zu bestehen.

---

# 76. Tool Checker – kritische Prüfung

Der Tool Checker muss künftig testen:

```text
INPUT TEXT
↓
ENGINEERING ASSISTANT
↓
CORE
↓
MODEL DIFF
↓
VALIDATION
```

---

# 77. Nicht ausreichend für PASS

Nicht:

```text
Assistant sent response
```

Nicht:

```text
Wizard opened
```

Nicht:

```text
MCP returned success
```

---

# 78. PASS-Kriterium

Nur:

```text
EXPECTED ENGINEERING EFFECT
```

im Core.

---

# 79. Direkter Chat-Test ohne Wizard

Tool Checker muss explizit einen Test ausführen:

```text
open Engineering Assistant
↓
do NOT click wizard
↓
send free-text engineering command
```

Beispiel:

```text
"Erstelle ein einfaches Projekt mit einem Controller,
einem Druck Sensor und einem Ventil Aktor."
```

---

# 80. Erwartete Prüfung

Danach im Core:

```text
project exists
controller exists
pressure sensor exists
valve actuator exists
relationships exist
validation executed
```

---

# 81. Chat-only Detection

Neuer Fehlercode:

```text
ASSISTANT_IS_CHAT_ONLY
```

Auslösen wenn:

```text
chat response exists
+
no engineering effect
```

oder:

```text
wizard link offered
+
no engineering execution
```

---

# 82. Weitere Fehlercodes

```text
ASSISTANT_GENERIC_ERROR_ON_VALID_COMMAND
ASSISTANT_NO_MODEL_CONTEXT
ASSISTANT_NO_CORE_EFFECT
ASSISTANT_ONLY_NAVIGATES
ASSISTANT_STOPS_AFTER_TOOL_CALL
ASSISTANT_LOSES_FOLLOWUP_CONTEXT
ASSISTANT_ASKS_ALREADY_ANSWERED_PARAMETER
ASSISTANT_SKIPS_DEPENDENCIES
ASSISTANT_SKIPS_VALIDATION
ASSISTANT_PREMATURE_COMPLETE
```

---

# 83. Test EA-PROJECT-001

Eingabe:

```text
"Erstelle ein einfaches Projekt mit einem Controller,
einem Druck Sensor und einem Ventil Aktor."
```

PASS:

```text
project_created = true
controller_created = true
pressure_sensor_created = true
valve_actuator_created = true
relationships_valid = true
validation_executed = true
generic_error = false
```

---

# 84. Test EA-HARDWARE-001

```text
"Lege eine ECU an, die mir die Stellgliedpositionen
im System alle 30 Sekunden abfragt."
```

PASS nur bei vollständigem Engineering-Ergebnis.

---

# 85. Test EA-FOLLOWUP-001

Nach einem eindeutigen Finding:

```text
"Dann weißt du ja, was du zu tun hast:
Fehleranalyse und Korrektur."
```

PASS:

```text
context_resolved = true
root_cause = true
repair_executed = true
revalidation = true
```

---

# 86. Test EA-FOLLOWUP-002

```text
"Mach das auch für die anderen Aktoren."
```

PASS:

```text
previous operation reused
remaining objects resolved
duplicates = 0
validation = true
```

---

# 87. Test EA-TECH-001

```text
"Ändere das LIN-Netz auf 19,2 kbit/s
und berechne alles neu."
```

PASS:

```text
bitrate = 19200 bit/s
capacity recalculated
timing recalculated
preflight rerun
```

---

# 88. Test EA-TRACE-001

```text
"Warum kommt PressureCommand zu spät an?"
```

PASS:

```text
E2E measured
timing breakdown
root cause
evidence
```

---

# 89. Test EA-SIM-001

```text
"Simuliere den Ausfall des Gateways."
```

PASS:

```text
fault scenario
simulation
trace
affected communication
findings
```

---

# 90. Test EA-VALIDATION-001

```text
"Finde alle Signale ohne Empfänger
und korrigiere die eindeutigen Fälle."
```

PASS:

```text
findings generated
deterministic fixes applied
ambiguous = review
validation rerun
```

---

# 91. Test EA-E2E-001

```text
"Zeige mir den Weg von Function A zu Function B
und wie lange die Botschaft benötigt."
```

PASS:

```text
source
route
hops
technology transitions
E2E timing
sequence view
```

---

# 92. Infrastrukturfehler testen

500-/Timeout-Fälle absichtlich testen.

PASS nur wenn:

```text
error classified
recovery attempted
workload state preserved
```

---

# 93. Kein Verlust des Workloads

Bei transientem Fehler:

```text
IN_PROGRESS
→ RETRY
→ IN_PROGRESS
```

Nicht:

```text
new independent conversation
```

---

# 94. Activity Log

Das vorhandene Aktivitätsprotokoll sollte strukturiert anzeigen:

```text
Goal resolved
Model inspected
Execution plan created
3 objects created
Validation completed
```

---

# 95. Kein Roh-Chain-of-Thought

Nicht speichern:

```text
raw hidden reasoning
```

Sondern:

```text
Goal
Observations
Evidence
Decision
Plan
Tool Trajectory
Result
```

---

# 96. Engineering Assistant Result Contract

```text
EngineeringAssistantResult
├── status
├── goal
├── summary
├── created_objects[]
├── modified_objects[]
├── reused_objects[]
├── findings[]
├── validation
├── completion
├── evidence_refs[]
└── deep_links[]
```

---

# 97. UI Status

Mögliche Status:

```text
PLANNING
IN_PROGRESS
WAITING_FOR_DECISION
VALIDATING
REPAIRING
COMPLETED
BLOCKED
```

---

# 98. 500-Fehler UI

Nicht nur:

```text
Engineering-Agent nicht verfügbar (500)
```

Sondern intern:

```text
Execution failure
↓
Recovery
```

Wenn endgültig blockiert:

```text
Auftrag konnte nicht abgeschlossen werden.

Ursache:
Engineering Assistant Service nicht verfügbar.

Status:
BLOCKED_WITH_EXPLICIT_CAUSE

Workload:
gespeichert
```

---

# 99. Retry Button

`Erneut versuchen` soll:

```text
same workload
```

fortsetzen.

Nicht:

```text
new independent prompt
```

---

# 100. Architekturziel

Heute:

```text
USER
↓
CHAT
↓
AGENT ENDPOINT
↓
500
```

Ziel:

```text
USER
↓
CHAT UI
↓
ENGINEERING ASSISTANT RUNTIME
├── Context
├── Goals
├── Workloads
├── Planner
├── Skills
├── MCP
├── Recovery
└── Completion
↓
PYTHON ENGINEERING CORE
↓
CANONICAL MODEL
↓
VALIDATION
↓
ENGINEERING RESULT
```

---

# 101. Codex-Arbeitsauftrag

```text
Refactor the current Engineering Assistant from a chat-centric implementation
into a model-aware Engineering Assistant Runtime.

The chat must remain only a UI.

Implement:

- EngineeringAssistantService
- GoalResolver
- ContextResolver
- EngineeringWorkload
- EngineeringPlanner
- CapabilityRegistry
- SkillRegistry integration
- MCP integration
- Executor
- RecoveryManager
- CompletionEvaluator
- EngineeringAssistantResult

Natural-language engineering commands must execute real engineering work.

Required acceptance examples:

1.
"Erstelle ein einfaches Projekt mit einem Controller,
einem Druck Sensor und einem Ventil Aktor."

2.
"Lege eine ECU an, die mir die Stellgliedpositionen
im System alle 30 Sekunden abfragt."

3.
"Dann weißt du ja, was du zu tun hast:
Fehleranalyse und Korrektur."

4.
"Mach das auch für die anderen Aktoren."

5.
"Ändere das LIN-Netz auf 19,2 kbit/s
und berechne alles neu."

6.
"Warum kommt PressureCommand zu spät an?"

Do not solve these by returning editor links.

Do not require wizard navigation.

Do not treat successful chat output as engineering completion.

For write operations, verify the resulting Core model.

Use:
REUSE before CREATE.

Do not invent technologies, ports, capabilities or signals when missing.

Unknown is preferable to a fabricated default.

Use deterministic Python Core logic whenever possible.

Use LLMs only for semantic interpretation, complex reasoning and explanation.

Every supported engineering command must end as:

COMPLETED
WAITING_FOR_ENGINEERING_DECISION
BLOCKED_WITH_EXPLICIT_CAUSE
NOT_SUPPORTED_WITH_CAPABILITY_GAP

A generic 500/error for a supported engineering command is:

ENGINEERING_ASSISTANT_EXECUTION_DEFECT

Persist the active EngineeringWorkload so retry and follow-up commands
continue the same engineering task.

Tool success is not goal completion.

Completion requires all dependent engineering outcomes and Validation/Preflight.
```

---

# 102. Definition of Done

Die Umstellung ist abgeschlossen, wenn:

1. der Chat nur noch UI ist.
2. EngineeringAssistantService existiert.
3. GoalResolver existiert.
4. ContextResolver existiert.
5. Workloads persistent sind.
6. Follow-ups auf bestehende Workloads zugreifen.
7. CapabilityRegistry existiert.
8. Skills über Registry gefunden werden.
9. MCP über registrierte Capabilities genutzt wird.
10. Python Core die Engineering-Logik enthält.
11. einfache Befehle deterministisch ausgeführt werden können.
12. `Projekt mit Controller/Drucksensor/Ventilaktor` funktioniert.
13. `ECU mit 30-s-Stellgliedabfrage` funktioniert.
14. `Fehleranalyse und Korrektur` als Follow-up funktioniert.
15. `Mach das auch für die anderen Aktoren` Kontext versteht.
16. Technologieänderungen funktionieren.
17. Routing-Aufträge funktionieren.
18. Simulation-Aufträge funktionieren.
19. Trace-/Root-Cause-Aufträge funktionieren.
20. E2E-Aufträge funktionieren.
21. Assistant nicht nur Links liefert.
22. Wizard nicht erforderlich ist.
23. Core-Mutation nachgewiesen wird.
24. Validation nach Mutationen ausgeführt wird.
25. CompletionEvaluator aktiv ist.
26. Tool Success nicht als Completion gilt.
27. 500-Fehler klassifiziert werden.
28. Retry denselben Workload fortsetzt.
29. REUSE before CREATE gilt.
30. generische Fehler bei unterstützten Befehlen als Defect gelten.
31. Tool Checker Free-Chat-Tests ohne Wizard enthält.
32. `ASSISTANT_IS_CHAT_ONLY` erkannt werden kann.
33. Model Before/After/Diff gespeichert wird.
34. Evidence vorhanden ist.
35. `NO EVIDENCE → NO PASS` gilt.

---

# 103. Leitregel

```text
ENGINEERING ASSISTANT
≠
CHATBOT
```

sondern:

```text
NATURAL ENGINEERING INTENT
↓
MODEL CONTEXT
↓
GOAL
↓
WORKLOAD
↓
PLAN
↓
SKILL / MCP / CORE
↓
ENGINEERING EFFECT
↓
VALIDATION
↓
COMPLETION
↓
RESULT
```

> **Der Nutzer soll mit dem NIS sprechen können, als würde er einem technischen Assistenten einen Engineering-Auftrag geben. Der Assistant muss daraus reale, überprüfbare Änderungen und Analysen im Engineering-Modell erzeugen – nicht nur Text, Links oder Wizard-Verweise.**
