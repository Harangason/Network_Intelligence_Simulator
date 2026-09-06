# Arbeitsauftrag für Codex
## Engineering Agent + MCP Architektur für den Network Intelligence Simulator

## 1. Ziel

Definiere und implementiere eine klare Trennung zwischen:

```text
ENGINEERING AGENT
```

und:

```text
MCP SERVER
```

für den **Network Intelligence Simulator**.

Der Agent übernimmt:

```text
Verstehen
Planen
Orchestrieren
Workloads zerlegen
Tools auswählen
Fortschritt prüfen
Fehler erkennen
Reparatur auslösen
Completion prüfen
Proposals erzeugen
```

Der MCP übernimmt:

```text
standardisierten Zugriff auf Simulator-Fähigkeiten
Tools
Resources
Schemas
Context
Permissions
```

Die fachliche Engineering-Logik bleibt im Python-Core.

Verbindliche Grundregel:

```text
Agent
= Intelligence + Orchestration

MCP
= Capability Interface

Python Core
= Engineering Logic

Canonical Model
= Engineering Truth
```

---

# 2. Zielarchitektur

```text
                    USER
                      │
                      ▼
              ENGINEERING AGENT
                      │
              ┌───────┴────────┐
              │                │
        Agent Context     Workload Engine
              │                │
              └───────┬────────┘
                      ▼
                 MCP CLIENT
                      │
                      ▼
        ┌─────────────────────────┐
        │  SIMULATOR MCP SERVER   │
        │                         │
        │  Tools                  │
        │  Resources              │
        │  Schemas                │
        │  Project Context        │
        └───────────┬─────────────┘
                    ▼
               PYTHON CORE
                    │
    ┌───────────────┼────────────────┐
    ▼               ▼                ▼
 Generators      Validators       Analysis
    │               │                │
    ├ Signals       ├ Model          ├ Busload
    ├ Functions     ├ Routing        ├ Timing
    ├ Messages      ├ Packing        ├ Trace
    ├ Interfaces    ├ Capacity       └ ML
    └ Scenarios     └ Semantics
                    │
                    ▼
              CANONICAL MODEL
```

---

# 3. Engineering Agent

Empfohlener Name:

```text
EngineeringAgent
```

oder simulator-spezifisch:

```text
NetworkEngineeringAgent
```

---

# 4. Agent Core Struktur

Empfohlene Struktur:

```text
backend/
└── agent_core/
    ├── core/
    │   ├── agent.py
    │   ├── context.py
    │   ├── task.py
    │   ├── result.py
    │   └── status.py
    │
    ├── orchestration/
    │   ├── planner.py
    │   ├── executor.py
    │   ├── completion.py
    │   ├── retry.py
    │   └── repair.py
    │
    ├── workload/
    │   ├── workload.py
    │   ├── work_package.py
    │   ├── dependency_graph.py
    │   └── progress.py
    │
    ├── tools/
    │   └── mcp_client.py
    │
    ├── proposals/
    ├── validation/
    └── audit/
```

---

# 5. Keine direkte Datenbankverbindung

Verbindlich:

```text
Agent
→ MCP
→ Python Service
→ Canonical Model
```

Nicht:

```text
Agent
→ SQL
```

und nicht:

```text
Agent
→ Repository directly
```

wenn dafür ein sauberer Service / Tool existiert.

---

# 6. Agent-Arbeitsweise

Ein Auftrag wie:

```text
Erzeuge eine ECU mit zwei Funktionen,
CAN-FD,
plausiblen Signalen
und Messages.
```

wird mindestens zu:

```text
UNDERSTAND
↓
INSPECT CURRENT MODEL
↓
PLAN
↓
CREATE WORKLOAD
↓
EXECUTE WORK PACKAGES
↓
VALIDATE
↓
CHECK COMPLETION
↓
REPAIR MISSING PARTS
↓
REVALIDATE
↓
READY_FOR_REVIEW
```

---

# 7. Completion-Regel

Verbindlich:

```text
Tool Call successful
≠
Task complete
```

Beispiel:

```text
Requested Functions = 2
Generated Functions = 2
Valid Functions = 2

Signals required = 12
Generated = 12
Valid = 11
```

Ergebnis:

```text
INCOMPLETE
```

Nicht:

```text
COMPLETED
```

---

# 8. Agent Context

Implementiere:

```text
AgentContext
```

mit mindestens:

```text
active_project_id
active_workflow
active_view
selected_object_refs[]
current_requirement
current_workload
project_domain
assumptions[]
unresolved_findings[]
user_constraints[]
permissions[]
```

Beispiel:

```text
active_view = Hardware Interface
selected_object = PowertrainECU
project_domain = automotive
```

---

# 9. Workload Engine

Der Agent soll komplexe Aufgaben in Work Packages zerlegen.

Beispiel:

```text
EngineeringWorkload
├── WP-01 Requirement Understanding
├── WP-02 Functions
├── WP-03 Hardware
├── WP-04 Interfaces
├── WP-05 Signals
├── WP-06 Messages
├── WP-07 Routing
├── WP-08 Capacity
├── WP-09 Validation
└── WP-10 Review
```

---

# 10. Workload Status

Mindestens:

```text
RECEIVED
PLANNING
IN_PROGRESS
VALIDATING
REPAIRING
INCOMPLETE
READY_FOR_REVIEW
COMPLETED
FAILED
BLOCKED
```

---

# 11. MCP Server

Definiere einen MCP Server:

```text
simulator-engineering-mcp
```

oder später generischer:

```text
engineering-core-mcp
```

Der MCP ist die standardisierte Werkzeug- und Resource-Schicht des Python-Core.

---

# 12. MCP enthält keine doppelte Fachlogik

Verbindlich:

```text
MCP Tool
≠
Engineering Logic
```

Beispiel:

```text
calculate_bus_load
↓
BusLoadAnalysisService.calculate(...)
```

Nicht:

```text
calculate_bus_load
→ eigene Formel im MCP Tool
```

---

# 13. MCP Hauptbereiche

```text
MCP SERVER
│
├── Resources
├── Read Tools
├── Generator Tools
├── Calculation Tools
├── Validation Tools
├── Simulation Tools
├── Trace Tools
├── Analysis Tools
└── Proposal Tools
```

---

# 14. MCP Resources

Mindestens:

```text
simulator://project/{project_id}

simulator://project/{project_id}/model

simulator://project/{project_id}/hardware

simulator://project/{project_id}/functions

simulator://project/{project_id}/interfaces

simulator://project/{project_id}/hardware-interfaces

simulator://project/{project_id}/signals

simulator://project/{project_id}/messages

simulator://project/{project_id}/networks

simulator://project/{project_id}/routing

simulator://project/{project_id}/findings
```

Zusätzlich:

```text
simulator://schemas/signal

simulator://schemas/message

simulator://schemas/function

simulator://schemas/hardware-interface

simulator://technologies/can-fd

simulator://device-classes
```

---

# 15. Read Tools

Mindestens:

```text
inspect_project()

inspect_object()

inspect_function()

inspect_hardware()

inspect_function_interface()

inspect_hardware_interface()

inspect_signal()

inspect_message()

inspect_network()

inspect_route()

inspect_findings()

search_model()
```

---

# 16. Generator Tools

Mindestens:

```text
generate_functions()

generate_function_interfaces()

classify_device()

generate_device_capabilities()

generate_signals()

generate_status_models()

generate_data_objects()

generate_hardware_interfaces()

generate_messages()

generate_routing()

generate_simulation_scenario()
```

Wichtig:

```text
generate_*
→ Proposal
```

Nicht automatisch:

```text
→ final Core Write
```

---

# 17. Signal Tools

Mindestens:

```text
classify_signal_semantics()

calculate_signal_bit_length()

resolve_signal_encoding()

resolve_signal_emulator()

validate_signal()

find_similar_signals()
```

Beispiel:

```text
MotorRPM
↓
classify_signal_semantics()
↓
ROTATIONAL_SPEED
↓
calculate_signal_bit_length()
↓
7 bits
↓
resolve_signal_emulator()
↓
rotational_speed.py
```

---

# 18. Device-Class Tools

Mindestens:

```text
classify_device()

get_device_class_profile()

get_device_capabilities()

validate_device_classification()
```

Beispiel:

```text
TemperatureSensor
→ Class 1
→ Basic Sensor
→ PHYSICAL_SCALAR
→ no dedicated Function
```

oder:

```text
Camera
→ Class 3
→ Perception Sensor
→ IMAGE_STREAM
→ Function Model required
```

---

# 19. Function Tools

Mindestens:

```text
generate_function_structure()

decompose_function()

map_function_to_hardware()

validate_function_mapping()

get_function_interfaces()
```

---

# 20. Message Tools

Mindestens:

```text
group_signals_for_messages()

pack_message()

pack_function_messages()

calculate_message_payload()

allocate_message_identifier()

validate_message()
```

Ablauf:

```text
Function Signals
↓
group_signals_for_messages()
↓
pack_function_messages()
↓
technology-specific payload sizing
↓
Messages
```

---

# 21. Hardware-Interface Tools

Mindestens:

```text
inspect_hardware_capabilities()

create_hardware_interface_proposal()

assign_network_to_interface()

allocate_message_to_hardware_interface()

calculate_interface_load()

validate_interface_capacity()
```

---

# 22. Network Tools

Mindestens:

```text
create_network_proposal()

calculate_network_load()

calculate_capacity()

validate_network()

find_available_capacity()

find_alternative_network()
```

---

# 23. Technologie-Tools

Agent nicht mit technologiespezifischen Details überfrachten.

Bevorzugt generische Tools:

```text
calculate_message_size(
    technology="CAN_FD"
)
```

```text
calculate_bus_load(
    technology="CAN_FD"
)
```

Intern:

```text
TechnologyRegistry
↓
CANFDTechnology
↓
CANFDLoadCalculator
```

Damit bleibt der MCP industrieneutral.

---

# 24. Routing Tools

Mindestens:

```text
find_route_candidates()

validate_route()

calculate_route_metrics()

rank_routes()

create_route_proposal()
```

Ablauf:

```text
Python
→ valid routes

ML
→ ranking

Qwen
→ explanation

User
→ approval
```

---

# 25. Simulation Tools

Mindestens:

```text
validate_simulation_preflight()

create_simulation_snapshot()

start_simulation()

get_simulation_status()

stop_simulation()

get_simulation_results()
```

Zusätzlich:

```text
generate_signal_behavior_proposal()

generate_fault_scenario_proposal()
```

---

# 26. Trace Tools

Mindestens:

```text
load_trace()

get_trace_window()

analyze_trace()

classify_trace_fault()

find_trace_root_cause()

correlate_signals()

compare_golden_trace()
```

---

# 27. Intelligence Tools

Mindestens:

```text
classify_semantics()

find_anomalies()

classify_fault()

rank_candidates()

evaluate_architecture()

find_graph_gaps()

find_single_points_of_failure()
```

---

# 28. Proposal System

Alle generierenden oder ändernden Tools sollen ein gemeinsames Proposal-Modell verwenden:

```text
EngineeringProposal
├── proposal_id
├── proposal_type
├── object_refs[]
├── changes[]
├── rationale
├── assumptions[]
├── validation_result
├── confidence
├── evidence[]
└── status
```

Status:

```text
PROPOSED
VALIDATED
REJECTED
APPROVED
APPLIED
OUTDATED
```

---

# 29. Schreib-Tools bewusst begrenzen

Keine freien Tools wie:

```text
update_any_object()

delete_anything()
```

Bevorzugt:

```text
apply_approved_proposal()

update_object_via_proposal()

delete_object_via_impact_analysis()
```

---

# 30. Human Approval Boundary

Verbindlich:

```text
AI
→ Proposal

Python
→ Validation

User
→ Approval

MCP
→ Apply
```

---

# 31. MCP Tool Result Contract

Jedes Tool soll strukturiert antworten:

```text
ToolResult
├── success
├── status
├── data
├── findings[]
├── warnings[]
├── evidence[]
├── affected_objects[]
├── next_actions[]
└── trace_id
```

Nicht nur:

```text
"done"
```

---

# 32. Fehlerzustände

Mindestens:

```text
SUCCESS
PARTIAL
INVALID_INPUT
VALIDATION_FAILED
CAPACITY_EXCEEDED
CONFLICT
NOT_FOUND
NOT_SUPPORTED
PERMISSION_DENIED
BLOCKED
INTERNAL_ERROR
```

---

# 33. Agent Workload Beispiel

User:

```text
Erzeuge 35 Signale:
10 Temperatur
25 Motion
```

Agent:

```text
create workload
↓
inspect context
↓
create work packages
↓
generate
↓
validate
↓
count
↓
repair
↓
completion check
```

Ergebnis erst:

```text
READY_FOR_REVIEW
```

wenn alle Zielkriterien erfüllt sind.

---

# 34. Requirement-Expansion Beispiel

User:

```text
Erzeuge eine Funktion zur 360°-Umfelderkennung mit Kameras.
```

Agent Tool Flow:

```text
1. resolve_requirement_intent()

2. identify_ambiguities()

3. propose_assumption(
   coverage=360°
)

4. classify_device(camera)

5. calculate_sensor_coverage()

6. generate_function_structure()

7. generate_data_objects()

8. generate_status_models()

9. generate_signals()

10. calculate_bandwidth()

11. propose_hardware()

12. generate_hardware_interfaces()

13. generate_messages()

14. allocate_messages()

15. calculate_capacity()

16. validate_architecture()

17. completion_check()
```

Danach:

```text
READY_FOR_REVIEW
```

Nicht:

```text
COMPLETED
```

---

# 35. Python-First Prinzip

Diese Architektur muss folgenden Datenfluss sicherstellen:

```text
Agent
→ MCP
→ Python

Frontend
→ API
→ Python

Simulation
→ Python

Analysis
→ Python
```

Alle greifen auf dieselben Services zu.

---

# 36. One Logic → Many Consumers

Verbindlich:

```text
ONE LOGIC
→ MANY CONSUMERS
```

Beispiel:

```text
CANFDLoadCalculator
```

wird verwendet durch:

```text
Wizard
MCP
Agent
Simulation
Analysis
UI API
```

Nicht mehrfach implementieren.

---

# 37. EIP-Kompatibilität vorbereiten

Die MCP-Tool-Contracts möglichst generisch gestalten.

Empfohlen:

```text
engineering-core-mcp
```

als gemeinsame spätere Capability-Schicht.

Simulator-spezifisch:

```text
network-simulator-mcp
```

kann darauf aufsetzen.

Später:

```text
EIP
→ engineering-core-mcp
```

---

# 38. Empfohlene MCP Struktur

```text
mcp/
├── server.py
├── context.py
├── permissions.py
├── schemas/
├── resources/
│   ├── project.py
│   ├── model.py
│   ├── schemas.py
│   └── documentation.py
├── tools/
│   ├── inspection/
│   ├── functions/
│   ├── hardware/
│   ├── interfaces/
│   ├── signals/
│   ├── messages/
│   ├── networks/
│   ├── routing/
│   ├── simulation/
│   ├── trace/
│   ├── analysis/
│   └── proposals/
└── adapters/
    └── python_services/
```

---

# 39. Permissions

MCP Tools müssen Berechtigungen respektieren.

Mindestens fachlich:

```text
READ_MODEL

GENERATE_PROPOSAL

VALIDATE

RUN_SIMULATION

ANALYZE_TRACE

APPLY_APPROVED_PROPOSAL

DELETE_WITH_IMPACT_ANALYSIS

ADMIN
```

An bestehende Permission-/Scope-Logik anpassen.

---

# 40. Audit

Jede relevante Agent-/MCP-Aktion auditieren:

```text
Tool Called

Proposal Created

Validation Executed

Proposal Approved

Proposal Rejected

Proposal Applied

Simulation Started

Trace Analysis Executed

Completion Evaluated
```

---

# 41. Docs-First Regel

Bei simulatorbezogenen Agent- oder MCP-Änderungen zuerst die bestehende Dokumentation unter:

```text
I:\PycharmProjects\My_first_Network_Simulator\docs
```

rekursiv durchsuchen.

Bestehende Services und Tool Contracts wiederverwenden.

Keine parallele Architektur erzeugen.

---

# 42. Tests

Mindestens:

```text
MCP resource read
MCP tool success
MCP validation failure
permission denied
tool registration
tool schema validation
proposal creation
proposal approval
proposal apply
agent workload completion
agent repair loop
agent tool selection
simulation tool
trace tool
routing tool
message packing tool
hardware interface allocation tool
```

---

# 43. E2E Test

Beispiel:

```text
User Request
→ Agent
→ Workload
→ MCP Tools
→ Python Services
→ Proposal
→ Validation
→ User Approval
→ Apply
→ Canonical Model
```

vollständig testen.

---

# 44. Keine vorzeitige Fertigmeldung

Nicht:

```text
MCP server starts
→ COMPLETE
```

Nicht:

```text
Agent can call one tool
→ COMPLETE
```

Nicht:

```text
Proposal created
→ COMPLETE
```

Erst nach vollständigem E2E-Nachweis.

---

# 45. Definition of Done

Die Aufgabe gilt erst als abgeschlossen, wenn:

1. EngineeringAgent klar vom MCP getrennt ist.
2. MCP keine doppelte Engineering-Logik besitzt.
3. Agent keine direkte DB-Verbindung verwendet.
4. AgentContext vorhanden ist.
5. Workload Engine vorhanden ist.
6. Completion Evaluator vorhanden ist.
7. Repair / Retry vorhanden ist.
8. MCP Resources implementiert sind.
9. Read Tools implementiert sind.
10. Generator Tools Proposal-basiert arbeiten.
11. Signal Tools vorhanden sind.
12. Device-Class Tools vorhanden sind.
13. Function Tools vorhanden sind.
14. Message Tools vorhanden sind.
15. Hardware-Interface Tools vorhanden sind.
16. Network Tools vorhanden sind.
17. Routing Tools vorhanden sind.
18. Simulation Tools vorhanden sind.
19. Trace Tools vorhanden sind.
20. Intelligence Tools vorhanden sind.
21. EngineeringProposal gemeinsamer Write-Mechanismus ist.
22. Human Approval Boundary funktioniert.
23. ToolResult strukturiert ist.
24. Permission Checks funktionieren.
25. Audit vorhanden ist.
26. Agent Workloads erst nach echter Completion abgeschlossen werden.
27. Python-Core Source der Fachlogik bleibt.
28. One Logic → Many Consumers eingehalten wird.
29. MCP Contracts später EIP-tauglich sind.
30. Unit-, Integration- und E2E-Tests erfolgreich sind.
31. Dokumentation dem As-Built-Stand entspricht.

---

# Zentrale Leitregel

```text
The Agent decides WHAT to do.

The MCP exposes HOW to access capabilities.

The Python Core performs engineering logic.

The Canonical Model stores engineering truth.
```

Kurz:

```text
USER
→ AGENT
→ MCP
→ PYTHON CORE
→ CANONICAL MODEL
```
