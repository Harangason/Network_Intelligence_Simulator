# Arbeitsauftrag für Codex
## AI Requirement Expansion im Projekt-Wizard – von einfacher Anforderung zur vollständigen Engineering-Struktur

## 1. Ziel

Erweitere den **Network Intelligence Simulator** um eine intelligente, kontrollierte **Requirement-Expansion-Architektur** im Projekt-Wizard.

Die KI soll aus einer einfachen natürlichsprachlichen Anforderung eine vollständige, nachvollziehbare und technisch plausible Engineering-Struktur ableiten.

Beispiel:

```text
"Ich benötige eine Funktion, die mit Kameras das Umfeld meines Fahrzeugs erfasst."
```

Daraus soll das System nicht nur einen Funktionsnamen erzeugen, sondern strukturiert ableiten:

```text
Intent
→ Semantik
→ Annahmen
→ Funktionsstruktur
→ benötigte Sensorik
→ Parameter
→ Statusmodelle
→ Datenobjekte
→ Signale
→ Hardware
→ Kommunikationsbedarf
→ Bus-/Netzwerkvorschlag
→ Kapazitäts-/Timing-Prüfung
→ Validierung
→ Nutzerreview
→ Canonical Core Write
```

Wichtig:

```text
AI interpretiert und schlägt vor.

Python Core berechnet und validiert.

User bestätigt.

Erst dann wird in den Canonical Core geschrieben.
```

---

# 2. Zentrale Architekturregel

Verbindlich:

```text
Natural Language Requirement
        ↓
AI Understanding
        ↓
Engineering Proposal
        ↓
Deterministic Python Validation
        ↓
Human Review
        ↓
Approved Engineering Objects
```

Nicht:

```text
User Prompt
→ LLM
→ direkt Datenbank
```

---

# 3. Rolle der KI

Die KI soll insbesondere:

```text
fachliche Absicht verstehen

Begriffe semantisch auflösen

fehlende Annahmen erkennen

Funktionen ableiten

Subfunktionen vorschlagen

Inputs / Outputs erkennen

Sensoren / Aktoren vorschlagen

technische Parameter vorschlagen

Statusmodelle vorschlagen

Datenobjekte vorschlagen

Signale vorschlagen

Hardwarevorschläge erzeugen

Kommunikationsanforderungen ableiten

Bus-/Netzwerktechnologien vorschlagen

offene Engineering-Fragen identifizieren

bestehende Core-Services orchestrieren
```

---

# 4. Rolle des Python Core

Python bleibt für alle deterministischen Engineering-Logiken verantwortlich.

Beispiele:

```text
Coverage Calculation

Camera Count Calculation

Field-of-View Geometry

Coordinate Transformation

Bit Requirement

Signal Encoding

Message Packing

Protocol Payload Sizing

Bus Load

Bandwidth Calculation

Latency

Jitter

Routing Reachability

State Machine Validation

Dependency Validation

Unit Validation

Completion Counting
```

Regel:

```text
LLM proposes.
Python proves.
```

---

# 5. Rolle des Nutzers

Der Nutzer bestätigt oder korrigiert:

```text
Assumptions

Function Structure

Sensor Count

Coverage

Parameters

Status Models

Data Objects

Signals

Hardware Mapping

Network Proposal

Message Architecture

Routing

Capacity / Timing

Final Project Structure
```

---

# 6. RequirementExpansionAgent

Implementiere bzw. integriere einen spezialisierten:

```text
RequirementExpansionAgent
```

Dieser orchestriert spezialisierte Services / Generatoren.

---

# 7. Spezialisierte Komponenten

Empfohlene Struktur:

```text
RequirementExpansionAgent
├── RequirementIntentExtractor
├── SemanticResolver
├── AmbiguityDetector
├── AssumptionGenerator
├── FunctionDecomposer
├── InputOutputResolver
├── SensorArchitectureGenerator
├── ActorArchitectureGenerator
├── ParameterGenerator
├── CoordinateSystemGenerator
├── StatusModelGenerator
├── DataObjectGenerator
├── SignalGenerator
├── HardwareProposalGenerator
├── CommunicationRequirementGenerator
├── MessageProposalGenerator
├── RoutingProposalGenerator
├── ValidationOrchestrator
└── CompletionEvaluator
```

---

# 8. Keine monolithische LLM-Prompt-Logik

Nicht:

```text
one giant prompt
→ generate complete project
```

Stattdessen:

```text
small specialized steps
→ validated intermediate results
→ explicit dependencies
```

---

# 9. Projekt-Wizard Zielprozess

Empfohlene Wizard-Reihenfolge:

```text
1. Project Context

2. Requirement Input

3. Requirement Understanding

4. Assumptions

5. Functions

6. Hardware / Sensors / Actors

7. Coordinate Systems

8. Parameters / Status Models

9. Data Objects / Signals

10. Networks / Bus Technologies

11. Messages / Packing

12. Routing

13. Capacity & Timing

14. Validation / Preflight

15. Review

16. Create Project
```

---

# 10. Beispielanforderung

Input:

```text
Ich benötige eine Funktion,
die mit Kameras das Umfeld meines Fahrzeugs erfasst.
```

Die KI soll dies nicht direkt als fertige Wahrheit interpretieren.

---

# 11. Intent Extraction

Erster Schritt:

```text
RequirementIntentExtractor
```

Erkennt beispielsweise:

```text
Domain:
Vehicle / Automotive

Primary Goal:
Environment Perception

Sensor Technology:
Camera

Observed Space:
Vehicle Surroundings

Likely Outputs:
Environment Model
Object List
Free Space
Sensor Status
```

---

# 12. Semantische Auflösung

Nutze bestehende:

```text
Ontology
Semantic Concepts
Aliases
Embeddings
Knowledge Graph
RAG
```

Beispiel:

```text
Umfeld
→ Environment / Surroundings

Kamera
→ Optical Sensor

erfassen
→ Perception / Observation / Detection
```

---

# 13. Ambiguity Detection

Die KI muss Unsicherheiten explizit erkennen.

Beispiel:

```text
"Umfeld erfassen"
```

kann bedeuten:

```text
front-only

front + rear

side monitoring

full surround

360° perception
```

Daher:

```text
AMBIGUOUS
```

statt stiller Annahme.

---

# 14. Assumption Proposal

Die KI darf Vorschläge machen.

Beispiel:

```text
Assumption Proposal

Concept:
Surround Coverage

Proposed Value:
360°

Reason:
"Umfeld des Fahrzeugs" wird als vollständige Rundumsicht interpretiert.

Confidence:
0.82

Requires Confirmation:
YES
```

---

# 15. Assumption Status

Mindestens:

```text
PROPOSED
CONFIRMED
REJECTED
MODIFIED
UNKNOWN
REQUIRED
OPTIONAL
```

---

# 16. Kritische vs unkritische Annahmen

Nicht jede Annahme muss sofort den Wizard blockieren.

Beispiel:

```text
critical:
required coverage

non-critical:
default naming convention
```

Kritische Annahmen benötigen Review vor Weiterverarbeitung.

---

# 17. Missing Engineering Decisions

Die KI muss fehlende technische Entscheidungen explizit auflisten.

Für das Kamera-Beispiel:

```text
Required angular coverage?

Detection range?

Minimum object size?

Day / night operation?

Frame rate?

Image resolution?

Allowed latency?

Redundancy required?

Degraded operation allowed?

Required object classes?

Environmental conditions?

Accuracy requirement?

Safety relevance?

Security relevance?
```

---

# 18. Keine stille Erfindung fehlender Werte

Nicht:

```text
missing value
→ arbitrary AI value
```

Sondern:

```text
missing value
→ proposed value
→ confidence
→ rationale
→ review status
```

---

# 19. Function Generation

Aus der Anforderung wird beispielsweise:

```text
EnvironmentPerception
```

---

# 20. Function Decomposition

Vorschlag:

```text
EnvironmentPerception
├── CaptureCameraImages
├── SynchronizeCameraData
├── CorrectCameraImage
├── DetectObjects
├── TransformCoordinates
├── FuseCameraDetections
├── TrackObjects
├── MonitorCoverage
├── MonitorCameraHealth
└── ProvideEnvironmentModel
```

---

# 21. Function Proposal Status

Jede erzeugte Funktion:

```text
PROPOSED
APPROVED
REJECTED
MODIFIED
```

---

# 22. Input / Output Resolution

Für jede Funktion:

```text
Inputs

Outputs

Required Context

Dependencies
```

Beispiel:

```text
DetectObjects

Inputs:
CameraFrames

Outputs:
CameraObjectDetections
```

---

# 23. Sensor Architecture Generation

Aus:

```text
Camera-based Environment Perception
```

wird eine Sensorarchitektur abgeleitet.

Aber Sensorzahl muss nicht rein durch das LLM geraten werden.

---

# 24. Coverage Proposal

Beispiel:

```text
Required Coverage:
360°
```

nach Nutzerbestätigung.

---

# 25. Kameraanzahl deterministisch berechnen

Python Service:

```text
SensorCoverageCalculator
```

fachlich:

```text
required_sensor_count
=
ceil(
    required_coverage
    /
    effective_sensor_coverage
)
```

Zusätzlich berücksichtigen:

```text
Field of View

Required Overlap

Blind Zones

Mounting Position

Occlusion

Safety Margin
```

---

# 26. Beispiel

Gegeben:

```text
Required Coverage:
360°

Camera HFOV:
110°

Required Overlap:
20°
```

Effektive Abdeckung ungefähr:

```text
90°
```

Dann:

```text
360 / 90
= 4 Cameras
```

Ergebnis:

```text
Camera Count Proposal:
4
```

---

# 27. Kein Hardcode "360° = 4 Kameras"

Verbindlich:

```text
Camera count
depends on actual FOV and overlap.
```

Nicht:

```text
360° always = 4 cameras
```

---

# 28. Sensor Proposal

Beispiel:

```text
CameraFront
CameraRear
CameraLeft
CameraRight
```

---

# 29. Sensorpositionen

Die KI darf initiale Positionen vorschlagen.

Beispiel:

```text
CameraFront
position = front
orientation = 0°

CameraRight
position = right
orientation = -90°

CameraRear
position = rear
orientation = 180°

CameraLeft
position = left
orientation = +90°
```

Diese Werte bleiben Proposals.

---

# 30. Bezugssystem erkennen

Sobald räumliche Objekte oder Sensororientierungen benötigt werden, muss die KI erkennen:

```text
Coordinate System Required
```

---

# 31. Vehicle Coordinate System

Beispiel:

```text
VehicleFrame

Origin:
Vehicle Reference Point

X:
forward

Y:
left

Z:
up
```

Die konkrete Konvention muss projektbezogen bestätigt werden.

---

# 32. Sensor Pose

Jeder räumliche Sensor erhält:

```text
position_x
position_y
position_z

yaw
pitch
roll
```

---

# 33. Intrinsic / Extrinsic Parameters

Für Kameras:

```text
intrinsic parameters

extrinsic parameters
```

vorsehen.

Mindestens konzeptionell modellierbar.

---

# 34. Coordinate Transformation

Python Service:

```text
CoordinateTransformationService
```

Beispiel:

```text
Camera Frame
→ Vehicle Frame
→ optional World Frame
```

---

# 35. Parameter Generator

Die KI erkennt typische Parameter eines Sensors / Systems.

Für Kamera beispielsweise:

```text
horizontal_fov

vertical_fov

resolution_x

resolution_y

frame_rate

bit_depth

range

latency

exposure

position

yaw

pitch

roll

calibration

synchronization
```

---

# 36. Parameter Status

Jeder Parameter:

```text
KNOWN

PROPOSED

UNKNOWN

REQUIRED

OPTIONAL

DEFAULTED
```

---

# 37. Parameter Provenance

Speichere:

```text
source
reason
confidence
approval
```

---

# 38. Statusmodelle automatisch erkennen

Die KI soll erkennen, dass Sensoren / Funktionen Status benötigen.

Nicht nur:

```text
CameraStatus = 1
```

---

# 39. Operating State

Beispiel:

```text
CameraOperatingState
```

```text
OFF
INIT
CALIBRATING
READY
ACTIVE
STANDBY
```

---

# 40. Health State

Beispiel:

```text
CameraHealthState
```

```text
OK
WARNING
DEGRADED
ERROR
CRITICAL
```

---

# 41. Data Quality State

Beispiel:

```text
CameraDataQuality
```

```text
VALID
DEGRADED
BLOCKED
DIRTY
OVEREXPOSED
UNDEREXPOSED
NOT_AVAILABLE
STALE
```

---

# 42. Mehrdimensionale Statuslogik

Ermögliche gleichzeitig:

```text
OperatingState = ACTIVE
HealthState = OK
DataQuality = DEGRADED
```

---

# 43. State Machine Vorschlag

Die KI kann:

```text
StateMachineProposal
```

erzeugen.

Python validiert:

```text
states

allowed transitions

guards

initial state

invalid transitions
```

---

# 44. Data Objects erkennen

Die KI muss erkennen, dass komplexe dynamische Daten nicht immer als einzelne Signals modelliert werden sollten.

Beispiel:

```text
Environment Object List
```

ist ein strukturiertes Data Object.

---

# 45. EnvironmentObject

Beispielmodell:

```text
EnvironmentObject
├── object_id
├── object_class
├── position
├── orientation
├── velocity
├── acceleration
├── dimensions
├── confidence
├── timestamp
├── source_sensor_refs[]
└── quality
```

---

# 46. EnvironmentObjectList

```text
EnvironmentObjectList
├── timestamp
├── reference_frame
├── object_count
└── objects[]
```

---

# 47. Keine künstlichen Object1_X Signals

Nicht:

```text
Object1_X
Object1_Y
Object2_X
Object2_Y
...
```

wenn fachlich ein dynamisches Objekt-Array gemeint ist.

---

# 48. Position

Ein Objekt kann kartesisch dargestellt werden:

```text
x
y
z
```

bezogen auf:

```text
reference_frame
```

---

# 49. Orientierung

Optional:

```text
yaw
pitch
roll
```

---

# 50. Sphärische Darstellung

Optional:

```text
range
azimuth
elevation
```

---

# 51. Object Classification

Beispiel:

```text
UNKNOWN
VEHICLE
TRUCK
MOTORCYCLE
BICYCLE
PEDESTRIAN
ANIMAL
OBSTACLE
```

---

# 52. Motion State

Optional:

```text
STATIONARY
MOVING
ACCELERATING
DECELERATING
UNKNOWN
```

---

# 53. Confidence

Erkannte Objekte:

```text
confidence = 0.0 ... 1.0
```

mit klarer Semantik.

---

# 54. Signal Generation

Neben Data Objects weiterhin klassische Signals erzeugen.

Für Kamera z. B.:

```text
CameraOperatingState
CameraHealthState
CameraDataQuality
CameraTemperature
CameraFrameCounter
CameraTimestamp
CameraBlocked
CameraSyncState
```

---

# 55. Signal Definition vollständig erzeugen

Jedes Signal möglichst mit:

```text
producer_function

sender_hardware

semantic_type

unit

range

resolution

cycle

receivers

quality

behavior model candidate

encoding candidate
```

---

# 56. Bit Requirement

Python berechnet:

```text
required_bits
```

nicht das LLM.

---

# 57. Enum / State Bit Requirement

Beispiel:

```text
6 states
→ minimum 3 bits
```

Reservierte / Invalid States berücksichtigen.

---

# 58. Sensor zu Funktion Mapping

Beispiel:

```text
CameraFront
→ provides_input_to
→ CaptureCameraImages
```

---

# 59. Hardware Proposal

Aus Functions + Sensorik erzeugt die KI:

```text
VisionController
ADASController
DomainController
```

als mögliche Compute-Hardware.

---

# 60. Hardware Mapping

Beispiel:

```text
EnvironmentPerception
→ mapped_to
→ VisionController
```

Bei verteilten Funktionen mehrere Hardware-Mappings zulassen.

---

# 61. Kommunikationsbedarf ableiten

Die KI soll erkennen:

```text
Raw Camera Data
= high bandwidth
```

und:

```text
Camera Status
= low bandwidth
```

---

# 62. Keine ungeeignete Bustechnologie wählen

Beispiel:

```text
4 × camera video
```

darf nicht einfach auf CAN-FD vorgeschlagen werden.

---

# 63. Bandbreite deterministisch berechnen

Python Service:

```text
BandwidthCalculator
```

Beispiel:

```text
1920 × 1080
× 24 bit
× 30 fps
≈ 1.49 Gbit/s raw
```

pro Kamera.

---

# 64. Vier Kameras

```text
≈ 5.97 Gbit/s raw
```

vor:

```text
compression
protocol overhead
transport overhead
```

---

# 65. Communication Proposal

KI kann danach vorschlagen:

```text
Raw Camera Streams
→ Automotive Ethernet

Camera Status Signals
→ CAN-FD or Ethernet
```

abhängig von Architektur und Requirements.

---

# 66. Technology Registry verwenden

Keine Technologie-Regeln im Wizard hardcoden.

Pipeline:

```text
CommunicationProposalGenerator
↓
TechnologyRegistry
↓
Technology-specific Python Services
```

---

# 67. Bus-/Netzwerkvalidierung

Python prüft:

```text
payload limits

bandwidth

cycle times

protocol compatibility

routing

latency

jitter

gateway constraints
```

---

# 68. Message Generation

Nach Signaldefinition:

```text
Signals
↓
Group by Producer Function
↓
Group by Sender Hardware
↓
Group by Network
↓
Group by Timing Class
↓
Group by Receiver Set
↓
Group by Priority
↓
Pack
```

---

# 69. Producer Function Regel

Standard:

```text
One Message
→ one Producer Function
```

---

# 70. Sender Hardware separat speichern

```text
Producer Function
= fachlicher Erzeuger

Sender Hardware
= physischer Sender
```

---

# 71. Timing-basiertes Message Grouping

Nicht Signale mit:

```text
10 ms
100 ms
1000 ms
```

blind zusammenpacken.

---

# 72. CAN-FD Payload Größen

Für CAN-FD unterstützen:

```text
0–8 Byte
12 Byte
16 Byte
20 Byte
24 Byte
32 Byte
48 Byte
64 Byte
```

---

# 73. Message Sizing Policy

Unterstütze:

```text
MINIMUM_VALID_SIZE
FIXED_SIZE
FIXED_SIZE_CLASSES
MANUAL
```

Default:

```text
MINIMUM_VALID_SIZE
```

---

# 74. Message Packing deterministisch

Python entscheidet:

```text
payload_used_bits

payload_capacity_bits

payload_free_bits

DLC / valid payload class
```

---

# 75. Signal bleibt atomar

Ein Signal darf nicht ohne explizite Segmentierungslogik über mehrere Messages geteilt werden.

---

# 76. Capacity & Timing

Nach Message Generation:

```text
Bus Load

Peak Load

Burst Load

Latency

Jitter

Queueing

Reserve
```

deterministisch berechnen.

---

# 77. AI Repair Loop

Wenn Python Validierung Probleme findet:

```text
Problem
→ AI gets structured finding
→ creates repair proposal
→ Python revalidates
```

Beispiel:

```text
Raw video exceeds network capacity.
```

KI kann vorschlagen:

```text
higher bandwidth Ethernet

compression

lower frame rate

lower resolution

additional network segmentation
```

---

# 78. Keine automatische Änderung

Repair:

```text
Proposal
→ Review
→ Approval
```

---

# 79. Wizard Preview

Vor Core Write:

```text
AI GENERATED ENGINEERING ARCHITECTURE
```

anzeigen.

---

# 80. Preview Bereiche

Mindestens:

```text
Requirement Interpretation

Assumptions

Functions

Sensors

Actors

Coordinate Systems

Parameters

Status Models

Data Objects

Signals

Hardware

Networks

Messages

Routing

Capacity

Timing

Warnings

Open Decisions
```

---

# 81. Review Aktionen

```text
Accept

Edit

Reject

Regenerate

Resolve Assumptions

Optimize

Recalculate
```

---

# 82. Kein Core Write vor Review

Verbindlich:

```text
AI Generation
↓
Python Validation
↓
Preview
↓
Human Review
↓
Approval
↓
Canonical Core Write
```

---

# 83. Canonical Core

Nach Approval:

```text
Requirements

Functions

Hardware

Sensors

Actors

Data Objects

Signals

Networks

Messages

Routing

Mappings

Parameters
```

als reguläre Engineering Objects / Beziehungen speichern.

---

# 84. Proposal Provenance

Jedes KI-generierte Objekt muss nachvollziehbar sein.

Mindestens:

```text
generated_by

model

prompt/task

source requirement

confidence

assumptions

validation status

approved_by

approved_at
```

---

# 85. Digital Thread

Requirement Expansion soll den Digital Thread aufbauen:

```text
Requirement
→ Function
→ Subfunction
→ Sensor / Actor
→ Signal / Data Object
→ Hardware
→ Message
→ Network
→ Route
```

---

# 86. Unknowns bleiben sichtbar

Nicht bestätigte oder unbekannte Werte:

```text
UNKNOWN
```

oder:

```text
OPEN_DECISION
```

Nicht unsichtbar mit Defaults überschreiben.

---

# 87. Confidence

Confidence getrennt je Proposal.

Nicht ein globaler LLM-Score für das ganze Projekt.

Beispiel:

```text
360° coverage:
0.82

4-camera architecture:
0.91 after FOV calculation

network recommendation:
0.95 after bandwidth validation
```

---

# 88. Engineering Evidence

Jeder wichtige Vorschlag soll Evidence / Rationale haben.

Beispiel:

```text
Proposal:
4 cameras

Evidence:
360° required coverage
110° HFOV
20° overlap
effective coverage ≈ 90°
```

---

# 89. Semantic Knowledge

Nutze vorhandene:

```text
Ontology

Taxonomy

Alias Dictionary

Embedding Search

Knowledge Graph

RAG
```

---

# 90. Learned Examples

Bereits bestätigte Projekte / Engineering-Beispiele dürfen als:

```text
Few-Shot / Retrieval Examples
```

verwendet werden.

Nicht ungeprüfte KI-Ausgaben.

---

# 91. Training Feedback

Bestätigte Korrekturen können später:

```text
TrainingCandidate
```

werden.

---

# 92. Active Learning

Besonders wertvolle Review-Fälle:

```text
low confidence

ambiguous requirement

model disagreement

rare domain

high engineering impact

failed validation
```

---

# 93. Python-First-Struktur

Empfohlen:

```text
backend/
└── engineering/
    └── requirement_expansion/
        ├── core/
        │   ├── request.py
        │   ├── context.py
        │   ├── proposal.py
        │   ├── result.py
        │   └── status.py
        ├── intent/
        ├── semantics/
        ├── assumptions/
        ├── functions/
        ├── io/
        ├── sensors/
        ├── actors/
        ├── coordinates/
        ├── parameters/
        ├── status_models/
        ├── data_objects/
        ├── signals/
        ├── hardware/
        ├── communication/
        ├── validation/
        ├── repair/
        └── orchestration/
```

An bestehende Projektstruktur anpassen.

---

# 94. Specialized Files

Keine monolithische:

```text
requirement_generator.py
```

mit sämtlicher Fachlogik.

Spezialisierte Dateien nach Responsibility / Domain / Technology.

---

# 95. Agent Tools

Der RequirementExpansionAgent verwendet Tools wie:

```text
resolve_semantics()

find_related_concepts()

calculate_sensor_coverage()

validate_coordinate_system()

calculate_bandwidth()

calculate_signal_bits()

pack_messages()

validate_protocol()

calculate_bus_load()

validate_routing()

validate_completion()
```

---

# 96. Tools sind dünne Adapter

Tool selbst enthält keine doppelte Fachlogik.

Beispiel:

```text
calculate_bandwidth tool
→ BandwidthCalculator Python Service
```

---

# 97. Completion Evaluator

Die KI darf nicht melden:

```text
Project ready
```

wenn offene Pflichtpunkte existieren.

---

# 98. Completion Criteria

Beispiel:

```text
Requirement interpreted

critical assumptions resolved

functions generated

required sensors generated

coordinate frame defined if spatial data exists

status models defined where required

data objects / signals generated

hardware mapped

network validated

messages packed

routing valid

capacity valid

timing valid

blocking errors = 0
```

---

# 99. Statusmodell für Wizard Workload

Mindestens:

```text
RECEIVED

ANALYZING

AMBIGUOUS

WAITING_FOR_INPUT

GENERATING

VALIDATING

REPAIRING

INCOMPLETE

READY_FOR_REVIEW

APPROVED

COMPLETED

FAILED

BLOCKED
```

---

# 100. Keine vorzeitige Completion

Verbindlich:

```text
TECHNICAL SUCCESS
≠
TASK COMPLETE
```

---

# 101. Umsetzungsschleife

```text
UNDERSTAND
→ GENERATE
→ VALIDATE
→ FIND GAPS
→ REPAIR
→ REVALIDATE
→ REVIEW
→ APPROVE
→ WRITE CORE
```

---

# 102. Kamera-End-to-End-Test

Input:

```text
Ich benötige eine Funktion,
die mit Kameras das Umfeld meines Fahrzeugs erfasst.
```

Das System muss mindestens erkennen / vorschlagen:

```text
Environment Perception

Coverage Requirement ambiguous

360° Assumption Proposal

Camera Sensor Technology

Camera Count Calculation

Vehicle Reference Frame

Sensor Positions / Orientations

Function Decomposition

Object Detection

Environment Object Model

Object Position

Object Orientation

Object Classification

Camera Operating State

Camera Health State

Camera Data Quality

Camera Status Signals

High-bandwidth Camera Data

Compute Hardware Proposal

Ethernet Candidate

Bandwidth Calculation

Status Communication

Message Proposal

Open Engineering Decisions
```

---

# 103. Beispiel Zielproposal

```text
FUNCTION
EnvironmentPerception

SUBFUNCTIONS
- CaptureCameraImages
- SynchronizeCameraData
- DetectObjects
- TransformCoordinates
- FuseDetections
- TrackObjects
- MonitorCameraHealth
- ProvideEnvironmentModel

SENSORS
4 Surround Cameras

COVERAGE
360° proposed / confirmed

REFERENCE FRAME
Vehicle Coordinate System

OUTPUT
EnvironmentObjectList

OBJECT ATTRIBUTES
position
orientation
velocity
acceleration
dimensions
class
confidence
quality

STATUS MODELS
CameraOperatingState
CameraHealthState
CameraDataQuality

COMMUNICATION
Raw Camera Streams → Automotive Ethernet Candidate
Status Signals → CAN-FD / Ethernet Candidate

COMPUTE
Vision / ADAS Controller

OPEN DECISIONS
Detection Range
Resolution
Frame Rate
Latency
Object Classes
Redundancy
Safety Relevance
```

---

# 104. Test – andere Domäne

Die Architektur darf nicht nur Kamera / Automotive verstehen.

Beispiele:

```text
"Ich brauche eine Funktion zur Temperaturüberwachung eines Motors."

"Ich brauche eine Funktion zur Druckregelung."

"Ich brauche eine Funktion zur Positionsüberwachung eines Roboters."

"Ich brauche eine Funktion zur Überwachung eines Energieverteilnetzes."
```

Der gleiche Requirement-Expansion-Prozess muss funktionieren.

---

# 105. Industrieneutralität

Core Begriffe:

```text
Function

Sensor

Actor

Controller

HardwareNode

DataObject

Signal

Network

Message

Route

CoordinateSystem
```

Nicht Automotive-spezifisch hardcoden.

---

# 106. Domain Profiles

Domains dürfen typische Vorschläge liefern:

```text
Automotive

Industrial Automation

Aerospace

Rail

Robotics

Energy

Generic
```

Aber Domain Profile:

```text
proposal source
```

nicht:

```text
canonical truth
```

---

# 107. Validation Layer

Jeder Generator muss seine Ergebnisse durch bestehende Validatoren schicken.

Keine unvalidierten Objektketten weiterreichen.

---

# 108. Blocking vs Warning

Blocking:

```text
impossible requirement

missing mandatory relationship

invalid unit

invalid coordinate frame

unsupported payload

routing impossible

capacity exceeded without alternative
```

Warnings:

```text
assumed parameter

generic estimate

low confidence

missing optional detail
```

---

# 109. Architecture Compliance

Nach Implementierung prüfen:

```text
No direct AI database writes

No duplicate core model

No duplicate calculations

No bus rules hardcoded in wizard

No silent assumptions

No arbitrary sensor count

No arbitrary message size

No arbitrary bandwidth decision

No premature completion
```

---

# 110. Dokumentation

Erzeuge:

```text
docs/project_wizard/

00_REQUIREMENT_EXPANSION_OVERVIEW.md

01_REQUIREMENT_INTENT_EXTRACTION.md

02_SEMANTIC_RESOLUTION.md

03_ASSUMPTION_MANAGEMENT.md

04_FUNCTION_DECOMPOSITION.md

05_SENSOR_ACTOR_GENERATION.md

06_COORDINATE_SYSTEMS.md

07_PARAMETER_GENERATION.md

08_STATUS_MODEL_GENERATION.md

09_DATA_OBJECT_GENERATION.md

10_SIGNAL_GENERATION.md

11_HARDWARE_PROPOSALS.md

12_COMMUNICATION_PROPOSALS.md

13_MESSAGE_PACKING.md

14_ROUTING_GENERATION.md

15_CAPACITY_TIMING_VALIDATION.md

16_AI_REPAIR_LOOP.md

17_HUMAN_REVIEW.md

18_DIGITAL_THREAD.md

19_COMPLETION_LOGIC.md

20_CAMERA_SURROUND_EXAMPLE.md
```

---

# 111. As-Built Dokumentation

Nach Umsetzung nur tatsächlich vorhandene Fähigkeiten als:

```text
IMPLEMENTED
```

kennzeichnen.

Andere:

```text
PARTIAL

PLANNED

BLOCKED
```

---

# 112. Tests

Mindestens:

```text
simple requirement

ambiguous requirement

missing parameter

sensor count calculation

function decomposition

coordinate-system generation

state-model generation

data-object generation

signal generation

bandwidth calculation

technology selection

message packing

routing

capacity

timing

repair loop

user correction

approval

core write
```

---

# 113. Regression

Bestehender Projekt-Wizard darf durch die Erweiterung nicht funktional verschlechtert werden.

---

# 114. Performance

Requirement Expansion darf in Work Packages laufen.

Große Projekte nicht in einem riesigen LLM-Call erzeugen.

---

# 115. Work Packages

Beispiel:

```text
WP-01 Requirement Understanding

WP-02 Functions

WP-03 Sensors / Actors

WP-04 Parameters

WP-05 Status Models

WP-06 Data Objects / Signals

WP-07 Hardware

WP-08 Communication

WP-09 Validation

WP-10 Review Package
```

---

# 116. Retry / Repair

Wenn ein Work Package fehlschlägt:

```text
inspect error

repair only affected package

revalidate dependencies

continue
```

Nicht komplettes Projekt blind neu generieren.

---

# 117. Definition of Done

Die Requirement-Expansion-Architektur gilt erst als abgeschlossen, wenn:

1. natürliche Anforderungen strukturiert interpretiert werden,
2. Semantik / Ontologie verwendet wird,
3. Ambiguitäten erkannt werden,
4. Annahmen explizit als Proposals gespeichert werden,
5. kritische Annahmen Nutzerreview benötigen,
6. Functions und Subfunctions generiert werden,
7. Inputs / Outputs abgeleitet werden,
8. passende Sensor-/Aktorvorschläge entstehen,
9. Sensoranzahl nicht blind vom LLM geraten wird,
10. Coverage deterministisch berechenbar ist,
11. räumliche Systeme Coordinate Systems erhalten,
12. Sensorpose modellierbar ist,
13. Parameter generiert und als KNOWN/PROPOSED/UNKNOWN markiert werden,
14. Operating-/Health-/Quality-Statusmodelle erzeugt werden können,
15. State Machines validiert werden,
16. strukturierte Data Objects erkannt werden,
17. dynamische Objektlisten nicht in künstliche Object1_X-Signale zerlegt werden,
18. Signals vollständig beschrieben werden,
19. Bit Requirement deterministisch berechnet wird,
20. Hardwarevorschläge erzeugt werden,
21. Function-Hardware-Mappings erzeugt werden,
22. Kommunikationsbedarf aus Datentyp und Bandbreite abgeleitet wird,
23. Bandbreite deterministisch berechnet wird,
24. ungeeignete Bustechnologien erkannt werden,
25. Message Grouping Producer/Timing/Receiver berücksichtigt,
26. Message Packing durch Python erfolgt,
27. Routing validiert wird,
28. Capacity & Timing validiert werden,
29. AI Repair nur Proposals erzeugt,
30. der Nutzer vor Core Write alles reviewen kann,
31. keine KI direkt in den Canonical Core schreibt,
32. Digital Thread die Ableitung vom Requirement bis zur Kommunikation nachvollziehbar macht,
33. offene Entscheidungen sichtbar bleiben,
34. Completion Criteria objektiv geprüft werden,
35. der Kamera-End-to-End-Test vollständig funktioniert,
36. die Architektur industrieneutral bleibt,
37. Dokumentation den tatsächlichen As-Built-Stand beschreibt.

---

# 118. Zentrale Leitregel

```text
A simple requirement is not a complete engineering model.

The AI must expand intent into structured proposals.

Python must validate all deterministic engineering facts.

Unknowns must remain visible.

Assumptions must be explicit.

Humans approve engineering truth.
```

Kurz:

```text
REQUIREMENT
→ UNDERSTAND
→ RESOLVE SEMANTICS
→ FIND ASSUMPTIONS
→ DECOMPOSE
→ GENERATE
→ CALCULATE
→ VALIDATE
→ REPAIR
→ REVIEW
→ APPROVE
→ WRITE CORE
```

Das Ziel ist eine KI, die aus einer einfachen fachlichen Aussage schrittweise eine vollständige, nachvollziehbare und technisch belastbare Engineering-Struktur erzeugt, ohne dabei Annahmen, Berechnungen und Engineering Truth miteinander zu vermischen.
