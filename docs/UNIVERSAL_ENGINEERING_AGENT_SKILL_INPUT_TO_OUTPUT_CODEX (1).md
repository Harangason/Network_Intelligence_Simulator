# Arbeitsauftrag für Codex
## Universal Engineering Agent Skill
## Vom Input über Typing, Reasoning und MCP bis Visualisierung, Design und Output

## 1. Ziel

Definiere einen modernen, modularen und modellbewussten **Universal Engineering Agent Skill**.

Der Skill soll nicht nur Chatantworten erzeugen. Er soll Eingaben verstehen, typisieren, in den bestehenden Modellkontext einordnen, technische Zusammenhänge analysieren, notwendige Entscheidungen erkennen, selbstständig Tools über MCP aufrufen, technische Änderungen kontrolliert ausführen, Ergebnisse validieren und anschließend in geeigneter Form darstellen.

Gesamtfluss:

```text
INPUT
↓
UNDERSTAND
↓
TYPE
↓
STRUCTURE
↓
MODEL CONTEXT
↓
REASON
↓
DECIDE
↓
PLAN
↓
USE MCP / TOOLS
↓
CREATE / MODIFY / CALCULATE
↓
VALIDATE
↓
VISUALIZE
↓
DESIGN
↓
OUTPUT
```

Der Skill soll modern wirken, aber keine monolithische „Alles-KI“ werden. Er besteht aus klar getrennten, wiederverwendbaren Capabilities.

---

## 2. Leitbild

Der Agent soll:

```text
Inputs verstehen
Modelle verstehen
Entscheidungen erkennen
Aufgaben planen
Tools selbst verwenden
Änderungen ausführen
Ergebnisse prüfen
Outputs komponieren
Visualisierungen erzeugen
Designsysteme einhalten
```

Nicht:

```text
nur Chatantworten schreiben
nur Links zu anderen Tools liefern
nur UI-Navigation anbieten
nur Vorschläge erzeugen
```

---

## 3. Beispielziel

User:

```text
Verbinde den Parkassistenten mit der Fahrerassistenz
und zeige mir anschließend die neue Architektur.
```

Der Agent muss daraus selbst ableiten:

```text
Intent verstehen
↓
ParkAssist finden
↓
DriverAssistance finden
↓
Objekttypen bestimmen
↓
Modellbeziehungen prüfen
↓
Kommunikationsmöglichkeiten prüfen
↓
notwendige Nutzerentscheidung erkennen
↓
Port / Interface / Network anpassen
↓
Routing aktualisieren
↓
Capacity / Timing berechnen
↓
validieren
↓
Visualisierung erzeugen
↓
Ergebnis präsentieren
```

---

## 4. Input-Arten

Der Agent darf nicht auf Chattext beschränkt sein.

Unterstützte Input-Typen mindestens:

```text
TEXT
STRUCTURED_DATA
FILE
IMAGE
TABLE
MODEL_OBJECT
SELECTION
EVENT
TRACE
SIMULATION_RESULT
USER_DECISION
MCP_RESULT
```

Beispiele:

```text
User schreibt Freitext
→ TEXT
```

```text
User markiert ECU im Graph
→ MODEL_OBJECT
```

```text
User lädt DBC hoch
→ FILE
```

```text
Simulation endet
→ EVENT + SIMULATION_RESULT
```

```text
User setzt Checkbox
→ USER_DECISION
```

---

## 5. AgentInputEnvelope

Definiere einen gemeinsamen Input-Contract:

```text
AgentInputEnvelope
├── input_id
├── input_type
├── content
├── project_ref
├── selected_objects[]
├── active_view
├── files[]
├── user_intent
├── constraints[]
├── permissions[]
├── source
└── timestamp
```

Der Agent verarbeitet alle Eingaben über diesen Contract.

---

## 6. Input Adapter

Implementiere eine Schicht:

```text
InputAdapter
```

Aufgaben:

```text
normalize input
detect input type
extract metadata
resolve project context
resolve selected objects
attach source information
```

Unteradapter können sein:

```text
TextInputAdapter
FileInputAdapter
ImageInputAdapter
TableInputAdapter
ModelSelectionAdapter
EventInputAdapter
TraceInputAdapter
SimulationResultAdapter
UserDecisionAdapter
```

---

## 7. Typing Layer

Nach der Input-Normalisierung muss der Agent bestimmen:

> Was ist das fachlich?

Beispiel:

```text
Motordrehzahl
```

wird:

```text
EngineeringType:
SIGNAL

SemanticType:
ROTATIONAL_SPEED

DataComplexity:
PHYSICAL_SCALAR

Unit:
rpm

Behavior:
PHYSICAL_CONTINUOUS
```

---

## 8. Typing Beispiel Hardware

Input:

```text
Kamera vorne links
```

mögliche Typisierung:

```text
EngineeringType:
HARDWARE_NODE

DeviceType:
SENSOR

Class:
CLASS_3

Typing:
PERCEPTION_SENSOR

DataComplexity:
IMAGE_STREAM
```

---

## 9. Typing Pipeline

Typing darf nicht nur vom LLM abhängen.

Empfohlene Reihenfolge:

```text
existing exact model match
↓
schema rules
↓
ontology
↓
semantic registry
↓
ML classifier
↓
LLM interpretation
↓
user clarification if necessary
```

---

## 10. TypingResult

Definiere:

```text
TypingResult
├── input_ref
├── engineering_type
├── semantic_type
├── device_type
├── device_class
├── data_complexity
├── unit
├── behavior_type
├── matched_object_ref
├── confidence
├── source
└── clarification_required
```

---

## 11. Existing Model Match

Bevor neue Objekte vorgeschlagen werden:

```text
search existing model
```

Prüfen:

```text
exact name
aliases
semantic match
existing relationships
same hardware
same signal definition
same interface
same network
```

Grundregel:

```text
MATCH / REUSE
before
CREATE
```

---

## 12. Model Context Resolver

Nach Typing:

```text
Typed Input
↓
ModelContextResolver
```

Der Agent muss den bestehenden Projektzustand verstehen.

Mindestens prüfen:

```text
Project
HardwareNodes
Functions
Function Mappings
Functional Interfaces
Hardware Interfaces
Physical Ports
Networks
Technology Bindings
Transport Units
Signals
DataObjects
Routes
Logical Node Addresses
Simulation Runs
Trace Results
Findings
```

---

## 13. ModelContext

Definiere:

```text
ModelContext
├── project_ref
├── project_revision
├── selected_objects[]
├── related_objects[]
├── upstream_relations[]
├── downstream_relations[]
├── hardware_context[]
├── function_context[]
├── communication_context[]
├── simulation_context[]
├── trace_context[]
├── findings[]
├── stale_results[]
├── assumptions[]
└── data_gaps[]
```

---

## 14. Model Awareness ist Pflicht

Nicht:

```text
LLM general knowledge
→ architecture decision
```

Sondern:

```text
project model
→ actual object relationships
→ engineering reasoning
```

---

## 15. Reasoning Layer

Der Agent erzeugt aus:

```text
Goal
+
Typed Input
+
Model Context
```

ein strukturiertes Reasoning-Ergebnis.

Mindestens:

```text
Observations
Hypotheses
Data Gaps
Decisions
Alternatives
Execution Intent
Completion Criteria
```

---

## 16. EngineeringReasoningResult

```text
EngineeringReasoningResult
├── reasoning_id
├── goal
├── observations[]
├── hypotheses[]
├── evidence_refs[]
├── data_gaps[]
├── alternatives[]
├── required_decisions[]
├── recommended_strategy
├── completion_criteria[]
├── confidence
└── status
```

---

## 17. Decision Engine

Der Agent muss unterscheiden:

```text
DETERMINISTIC
POLICY_DEFINED
ENGINEERING_DECISION
```

Regeln:

```text
DETERMINISTIC
→ Agent entscheidet / berechnet selbst

POLICY_DEFINED
→ Projektpolicy anwenden

ENGINEERING_DECISION
→ Nutzer fragen
```

---

## 18. Beispiel Decision Detection

Frage:

```text
Ist ein freier CAN-Port vorhanden?
```

ist:

```text
DETERMINISTIC
```

Frage:

```text
Soll ein neuer CAN-Port erstellt
oder ein Gateway verwendet werden?
```

ist:

```text
ENGINEERING_DECISION
```

---

## 19. Interactive Decision

Wenn Entscheidung nötig:

```text
InteractiveQuestion
```

mit:

```text
single select
multi select
approval
```

Nach Nutzerantwort:

```text
Workload resumes
```

Nicht neuen Task starten.

---

## 20. Planning Skill

Nach der Entscheidung erzeugt der Agent:

```text
EngineeringExecutionPlan
```

Beispiel:

```text
1. Inspect Hardware
2. Inspect Interfaces
3. Create Port
4. Connect Network
5. Update Transport
6. Update Routing
7. Recalculate Capacity
8. Recalculate Timing
9. Validate
10. Visualize
```

---

## 21. Dependency Plan

Plan-Schritte besitzen Abhängigkeiten.

Beispiel:

```text
Port
↓
HardwareInterface
↓
Network Connection
↓
Transport Binding
↓
Routing
↓
Capacity
↓
Timing
↓
Validation
↓
Visualization
```

---

## 22. EngineeringExecutionPlan Contract

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
├── output_plan[]
├── rollback_strategy
└── completion_criteria[]
```

---

## 23. MCP Skill

MCP ist die Capability-Schicht.

Nicht nur Navigation:

```text
open_hardware_view()
```

sondern echte Engineering-Fähigkeiten:

```text
inspect_model()
find_object()
create_port()
create_hardware_interface()
connect_network()
create_route()
update_route()
pack_messages()
calculate_bus_load()
calculate_timing()
run_preflight()
run_simulation()
analyze_trace()
```

---

## 24. MCP Architekturregel

```text
Agent
→ MCP
→ Python Core
→ Canonical Model
```

MCP implementiert keine doppelte Fachlogik.

---

## 25. Capability Registry

Der Agent sollte keine unüberschaubare statische Toolliste im Prompt tragen.

Implementiere:

```text
CapabilityRegistry
```

Beispiele:

```text
model.inspect
model.search
hardware.inspect
hardware.modify
hardware.port.create
network.inspect
network.connect
transport.generate
transport.pack
routing.inspect
routing.calculate
routing.modify
capacity.calculate
timing.calculate
validation.run
simulation.run
simulation.inspect
trace.load
trace.analyze
visualization.graph
visualization.sequence
visualization.timeline
visualization.table
design.compose
report.generate
```

---

## 26. Capability Discovery

Ablauf:

```text
Goal
↓
required capability
↓
Capability Registry
↓
compatible tool
↓
MCP
```

---

## 27. Tool Result Contract

Jedes Tool liefert:

```text
ToolResult
├── success
├── status
├── data
├── evidence_refs[]
├── affected_objects[]
├── warnings[]
├── errors[]
├── next_possible_actions[]
└── trace_id
```

---

## 28. Execution Layer

Der Agent führt den Plan selbst aus.

Nicht:

```text
"Öffne Routing View"
```

sondern:

```text
routing.update
```

Deep Links sind nur Zusatzkomfort.

---

## 29. Validation Layer

Nach Mutationen muss automatisch validiert werden.

Mindestens:

```text
Model Validation
Topology Validation
Address Validation
Binding Validation
Transport Validation
Routing Validation
Capacity Validation
Timing Validation
Simulation Preflight
```

---

## 30. Completion Evaluator

Verbindlich:

```text
Tool success
≠ Task complete
```

Implementiere:

```text
GoalCompletionEvaluator
```

Er prüft:

```text
desired state reached?
all mandatory steps complete?
all required validations passed?
no blocker remains?
all user decisions resolved?
outputs generated?
```

---

## 31. Repair Loop

Wenn:

```text
INCOMPLETE
```

dann:

```text
inspect missing condition
↓
generate repair step
↓
execute
↓
revalidate
↓
completion check
```

---

## 32. Visualization Skill

Der Agent muss anhand des fachlichen Zwecks entscheiden:

```text
Welche Visualisierung ist sinnvoll?
```

Zuordnung:

```text
Architecture
→ Graph

Routing
→ Route Diagram

Communication
→ Network Diagram

Timing
→ Timeline

Trace
→ Sequence Diagram

Signals
→ Time Series

Dependencies
→ Dependency Graph

Comparison
→ Matrix / Chart

Large Data
→ Table
```

---

## 33. VisualizationRequest

```text
VisualizationRequest
├── visualization_type
├── purpose
├── source_objects[]
├── relationships[]
├── metrics[]
├── filters[]
├── emphasis[]
├── layout_preferences
└── interaction
```

---

## 34. Visualization Types

Mindestens:

```text
GRAPH
NETWORK_DIAGRAM
ROUTE_DIAGRAM
SEQUENCE_DIAGRAM
TIMELINE
TIME_SERIES
MATRIX
TABLE
TREE
FLOW
STATUS_OVERVIEW
```

---

## 35. Visualization ist nicht Design

Unterscheide:

```text
Visualization
= Welche Information wird dargestellt?
```

von:

```text
Design
= Wie wird diese Information dargestellt?
```

---

## 36. Design Skill

Design Skill steuert:

```text
Hierarchy
Spacing
Grouping
Typography
Density
Labels
Cards
Controls
Responsive Layout
Interaction
```

---

## 37. DesignSystemRegistry

Implementiere:

```text
DesignSystemRegistry
```

mit mindestens:

```text
layout tokens
spacing tokens
typography tokens
surface tokens
border tokens
status semantics
icon registry
component registry
interaction patterns
responsive rules
```

---

## 38. Keine freie CSS-Halluzination

Nicht:

```text
LLM writes arbitrary CSS
```

sondern:

```text
Agent
→ Visualization Intent
→ Design System Registry
→ approved component composition
```

---

## 39. Moderne Designprinzipien

UI soll wirken:

```text
ruhig
hochwertig
technisch
modern
kompakt
kontextbezogen
```

Vermeiden:

```text
zu viele Karten
starke Glow-Effekte
Neonfarben
Gaming-Optik
unnötige Icons
überladene Formulare
```

Bevorzugen:

```text
Whitespace
klare Typographie
dezente Trennlinien
subtile Statusfarben
funktionale Interaktionen
```

---

## 40. Output Layer

Der Agent muss unterschiedliche Output-Arten unterstützen.

```text
AgentOutput
├── CHAT
├── QUESTION
├── MODEL_CHANGE
├── FINDING
├── PROPOSAL
├── TABLE
├── GRAPH
├── DIAGRAM
├── CHART
├── TRACE_VIEW
├── FILE
├── REPORT
├── CODE
├── SIMULATION
└── MCP_RESPONSE
```

---

## 41. AgentOutputEnvelope

```text
AgentOutputEnvelope
├── output_id
├── output_type
├── status
├── content
├── affected_objects[]
├── evidence[]
├── visualization
├── actions[]
├── files[]
├── validation
├── confidence
└── provenance
```

---

## 42. Ein Auftrag kann mehrere Outputs erzeugen

Beispiel:

```text
Verbinde ParkAssist mit Fahrerassistenz
und prüfe die Verbindung.
```

Ergebnis kann sein:

```text
MODEL_CHANGE
→ CAN-Port erzeugt

MODEL_CHANGE
→ Netzwerkverbindung hergestellt

MODEL_CHANGE
→ Routing aktualisiert

CALCULATION
→ Buslast 64 %

VALIDATION
→ PASS

VISUALIZATION
→ Network Graph

CHAT
→ Zusammenfassung
```

---

## 43. Output Composer

Implementiere:

```text
OutputComposer
```

Aufgaben:

```text
collect execution results
select relevant outputs
group related results
select visualization
apply design system
generate concise summary
attach evidence and actions
```

---

## 44. Chat Integration

Der Chat ist nur eine mögliche Ausgabefläche.

Er kann darstellen:

```text
Text
Progress
Interactive Question
Finding
Recommendation
Validation Result
Visualization
Approval
```

---

## 45. Beispiel moderner Chat-Ausgabe

```text
Verbindung eingerichtet

ParkAssist
0x0012
      │
      │ CAN-FD
      ▼
Chassis_CAN
      │
      ▼
ADAS_Controller
0x0020
      │
      ▼
DriverAssistance

✓ CAN-Port erzeugt
✓ Routing aktualisiert
✓ Buslast geprüft
✓ Timing geprüft
✓ Preflight bestanden

[Architektur anzeigen]
[Routing]
[Simulation starten]
```

---

## 46. Agent State

Der Agent benötigt einen persistierenden Arbeitszustand.

```text
AgentWorkState
├── goal
├── context
├── typed_inputs[]
├── reasoning_result
├── execution_plan
├── completed_steps[]
├── pending_steps[]
├── pending_decisions[]
├── tool_results[]
├── generated_outputs[]
├── validations[]
└── completion_status
```

---

## 47. Workload Resume

Nach einer Nutzerfrage:

```text
SUSPENDED_FOR_DECISION
```

Nach Antwort:

```text
RESUME
```

Der Agent setzt denselben Workload fort.

---

## 48. Input-to-Output Pipeline

Zielarchitektur:

```text
                    USER / EVENT
                         │
                         ▼
                 INPUT ADAPTER
                         │
                         ▼
                     TYPING
                         │
                         ▼
               CONTEXT RESOLVER
                         │
                         ▼
               MODEL UNDERSTANDING
                         │
                         ▼
                    REASONING
                         │
                         ▼
                 DECISION ENGINE
                         │
              ┌──────────┴──────────┐
              │                     │
         USER DECISION          DETERMINISTIC
              │                     │
              └──────────┬──────────┘
                         ▼
                       PLAN
                         │
                         ▼
                CAPABILITY REGISTRY
                         │
                         ▼
                        MCP
                         │
                         ▼
                    PYTHON CORE
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
        MODEL       SIMULATION       TRACE
           │             │             │
           └─────────────┼─────────────┘
                         ▼
                    VALIDATION
                         │
                         ▼
                    COMPLETION
                         │
                  ┌──────┴──────┐
                  │             │
             INCOMPLETE       COMPLETE
                  │             │
                REPAIR          ▼
                  │       OUTPUT COMPOSER
                  └───────►     │
                                ▼
                     VISUALIZATION / DESIGN
                                │
                                ▼
                       USER / FILE / API
```

---

## 49. Skill-Aufteilung

Empfohlene Skill-Struktur:

```text
agent_skills/
├── input/
│   ├── typing/
│   ├── file_understanding/
│   ├── image_understanding/
│   └── event_understanding/
├── context/
│   ├── model_context/
│   └── project_context/
├── reasoning/
│   ├── engineering_reasoning/
│   ├── decision_detection/
│   ├── hypothesis/
│   └── completion/
├── planning/
│   ├── execution_plan/
│   └── dependency_plan/
├── mcp/
│   ├── capability_discovery/
│   └── tool_execution/
├── engineering/
│   ├── hardware/
│   ├── function/
│   ├── communication/
│   ├── routing/
│   ├── simulation/
│   └── trace/
├── validation/
├── visualization/
│   ├── graph/
│   ├── network/
│   ├── sequence/
│   ├── timeline/
│   ├── chart/
│   └── table/
├── design/
│   ├── composition/
│   ├── components/
│   └── responsive/
└── output/
    ├── chat/
    ├── report/
    ├── file/
    └── api/
```

---

## 50. Skill Contract

Jeder Skill definiert mindestens:

```text
skill_id
purpose
accepted_inputs[]
required_context[]
required_capabilities[]
outputs[]
validation[]
failure_modes[]
```

---

## 51. Skill Discovery

Agent soll Skills dynamisch auflösen können:

```text
Goal
↓
required skill
↓
Skill Registry
↓
Skill Contract
↓
Execution
```

---

## 52. Skill Registry

Implementiere:

```text
SkillRegistry
```

Beispiele:

```text
input.typing
model.context.resolve
engineering.reason
engineering.plan
engineering.execute
communication.route
simulation.run
trace.root_cause
visualization.network
visualization.sequence
design.compose
output.report
```

---

## 53. Skills dürfen keine zweite Fachlogik erzeugen

Skill orchestriert. Python Core führt Engineering-Berechnungen aus.

Verbindlich:

```text
Skill
→ Core Service
```

Nicht:

```text
Skill
→ eigene Buslastformel
```

---

## 54. Input und Output müssen symmetrisch gedacht werden

Der Agent kann Eingaben aus vielen Quellen erhalten:

```text
Text
File
Image
Model
Event
Trace
Simulation
```

und Outputs in vielen Formen erzeugen:

```text
Text
Model Change
Visualization
Report
Simulation
Trace Finding
File
API Result
```

---

## 55. Provenance

Jeder Output muss nachvollziehbar sein.

Mindestens:

```text
source inputs
model revision
tool calls
validation results
agent capability version
created_at
```

---

## 56. Permissions

Der Agent darf nur Skills, Tools, Daten und Model Changes verwenden, für die der aktuelle Benutzer berechtigt ist.

---

## 57. Audit

Mindestens protokollieren:

```text
Input Received
Typing Completed
Context Resolved
Reasoning Started
Decision Requested
Decision Received
Plan Created
Skill Selected
MCP Tool Called
Model Changed
Validation Completed
Visualization Generated
Output Created
Completion Evaluated
```

---

## 58. Fehlerbehandlung

Wenn ein Skill fehlschlägt:

```text
classify failure
↓
repair possible?
├── YES → repair
└── NO → block / ask / rollback
```

---

## 59. Keine falsche Completion

Nicht:

```text
Visualization generated
→ COMPLETE
```

wenn Modelländerung oder Validierung noch fehlt.

Nicht:

```text
MCP tool succeeded
→ COMPLETE
```

Completion kommt ausschließlich vom GoalCompletionEvaluator.

---

## 60. Beispiel: ParkAssist End-to-End

User:

```text
Verbinde ParkAssist mit DriverAssistance
und zeige mir die neue Architektur.
```

Agent:

```text
INPUT
→ TEXT
```

```text
TYPING
→ CONNECT_FUNCTIONS
```

```text
CONTEXT
→ ParkAssist
→ ChassisController
→ CAN-FD
→ DriverAssistance
→ ADAS_Controller
→ Ethernet
```

```text
REASONING
→ direct common route missing
→ ADAS CAN capability available
→ CAN port missing
```

```text
DECISION
→ Ask user:
  CAN port create?
```

User:

```text
Yes
```

Agent:

```text
PLAN
→ create port
→ connect network
→ bind transport
→ update routing
→ calculate
→ validate
→ visualize
```

```text
MCP / CORE
→ execute
```

```text
VALIDATION
→ PASS
```

```text
VISUALIZATION
→ Network Graph
```

```text
OUTPUT
→ model changes
→ validation result
→ graph
→ chat summary
```

---

## 61. Definition of Done

Der Universal Engineering Agent Skill gilt erst als umgesetzt, wenn:

1. mehrere Input-Typen unterstützt werden.
2. AgentInputEnvelope existiert.
3. Typing Layer vorhanden ist.
4. Existing Model Match vor Create funktioniert.
5. ModelContextResolver vorhanden ist.
6. Engineering Reasoning strukturiert arbeitet.
7. Decision Engine zwischen deterministisch, Policy und Engineering Decision unterscheidet.
8. Interactive Decisions unterstützt werden.
9. EngineeringExecutionPlan erzeugt wird.
10. Dependency Planning funktioniert.
11. CapabilityRegistry vorhanden ist.
12. MCP echte Engineering-Aktionen ausführt.
13. ToolResult standardisiert ist.
14. Validation automatisch folgt.
15. GoalCompletionEvaluator vorhanden ist.
16. Repair Loop funktioniert.
17. Visualization Skill vorhanden ist.
18. VisualizationRequest vorhanden ist.
19. Design Skill vom Visualization Skill getrennt ist.
20. DesignSystemRegistry vorhanden ist.
21. keine freie CSS-/UI-Halluzination erfolgt.
22. mehrere Output-Typen unterstützt werden.
23. AgentOutputEnvelope existiert.
24. OutputComposer vorhanden ist.
25. ein Auftrag mehrere Outputs erzeugen kann.
26. AgentWorkState persistent ist.
27. Workload nach Nutzerentscheidung fortgesetzt wird.
28. SkillRegistry vorhanden ist.
29. Skills über definierte Contracts arbeiten.
30. Skills keine doppelte Engineering-Logik enthalten.
31. Provenance vorhanden ist.
32. Permissions berücksichtigt werden.
33. Audit vollständig ist.
34. Completion nicht mit Tool-Erfolg verwechselt wird.
35. ParkAssist-End-to-End-Szenario vollständig funktioniert.

---

## 62. Zentrale Leitregel

```text
INPUT
→ TYPE
→ CONTEXT
→ REASON
→ DECIDE
→ PLAN
→ EXECUTE
→ VALIDATE
→ VISUALIZE
→ DESIGN
→ OUTPUT
```

> **Der Agent soll Eingaben nicht nur verstehen und Ausgaben nicht nur formulieren. Er soll den vollständigen Weg zwischen beiden beherrschen: vom unstrukturierten Input über das bestehende Engineering-Modell und die tatsächliche Ausführung bis zur validierten, verständlich gestalteten Ausgabe.**
