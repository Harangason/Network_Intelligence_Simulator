# Arbeitsauftrag für Codex
## Device-Class- und Typisierungsmodell im Hardware-Model-View und Objekt-Wizard

## 1. Ziel

Erweitere den **Network Intelligence Simulator** um ein verbindliches Klassifizierungsmodell für Hardwaregeräte.

Die bestehende Hardware-Knoten-Sicht und der Objekt-Wizard sollen künftig neben:

```text
Name
Gerätetyp
Domäne
```

zusätzlich anzeigen und verwalten:

```text
Class
Typisierung
```

Zielbild der Tabellenansicht:

```text
Name | Gerätetyp | Class | Typisierung | Domäne
```

Beispiele:

```text
FrontCamera    | Sensor  | 3 | Perception / Intelligent Sensor | automotive
CentralGateway | Gateway | 4 | Intelligent Subsystem           | automotive
CoolantSensor  | Sensor  | 1 | Basic Sensor                    | automotive
BrakeActuator  | Aktor   | 2 | Controlled Actuator             | automotive
```

Diese Klassifizierung steuert auch die Generatorlogik.

---

## 2. Grundregel

```text
Hardware vorhanden
≠
automatisch eigene Systemfunktion
```

Der Generator muss zuerst bestimmen:

```text
Gerätetyp
+
Device Class
+
Typisierung
+
Capabilities
+
Data Complexity
```

und daraus ableiten:

```text
Function erforderlich?
Signals erforderlich?
Statusmodell erforderlich?
Health erforderlich?
Quality erforderlich?
DataObject erforderlich?
Stream erforderlich?
Hardware Interface erforderlich?
```

---

## 3. Device Classes

```text
CLASS 0 – PASSIVE
CLASS 1 – BASIC
CLASS 2 – SMART / CONTROLLED
CLASS 3 – PERCEPTION / INTELLIGENT
CLASS 4 – INTELLIGENT SUBSYSTEM
```

---

## 4. Class 0 – Passive

Typisierung:

```text
Passive Component
```

Beispiele:

```text
Thermistor
PT100
Potentiometer
Switch
Hall Element
Passive Pressure Element
Simple Relay
Simple Lamp
```

Generatorregel:

```text
NO automatic Function
RAW / BASIC Signal only
kein komplexes Statusmodell
kein DataObject
```

---

## 5. Class 1 – Basic

Typisierungen:

```text
Basic Sensor
Basic Actuator
Basic Communication Device
```

Beispiele:

```text
Temperature Sensor
Pressure Sensor
RPM Sensor
Position Sensor
Wheel Speed Sensor
Current Sensor
Voltage Sensor
Simple Valve
Relay
Solenoid
Lamp
```

Generatorregel Sensor:

```text
Physical Signal
optional Quality
optional ECU-diagnosed Health
NO dedicated auto Function
```

Generatorregel Aktor:

```text
Command / State Signal
optional feedback
NO dedicated auto Function
```

---

## 6. Class 2 – Smart / Controlled

Typisierungen:

```text
Smart Sensor
Controlled Actuator
Smart I/O Device
Embedded Device
```

Beispiele:

```text
Digital Pressure Sensor
IMU
Encoder with Diagnostics
Smart Current Sensor
Servo
Controlled Pump
Controlled Valve
Motor Driver
```

Generatorregel:

```text
Signals
Status likely required
Health required
Quality likely required
Capabilities
optional local Function
```

---

## 7. Class 3 – Perception / Intelligent

Typisierungen:

```text
Perception Sensor
Intelligent Sensor
Perception Device
```

Beispiele:

```text
Camera
Radar
LiDAR
Ultrasonic Array
3D Scanner
Advanced IMU
```

Generatorregel:

```text
Functions / Subfunctions likely required
DataObjects / Streams
Status Model required
Health required
Quality required
Hardware Interface requirements
```

---

## 8. Class 4 – Intelligent Subsystem

Typisierung:

```text
Intelligent Subsystem
```

Beispiele:

```text
Central Gateway
ADAS Sensor Unit
Vision ECU
Sensor Fusion Unit
Smart LiDAR Unit
Robot Vision System
Domain Controller
Zone Controller
Smart Actuator Subsystem
```

Generatorregel:

```text
full Function Model
multiple Functions possible
Status Models
Health
Communication State
Hardware Interfaces
DataObjects
Messages
Diagnostics
local capabilities
```

---

## 9. Gerätetyp und Class getrennt

Beispiel:

```text
Gerätetyp = Sensor
```

kann sein:

```text
Class 0 – Passive Component
Class 1 – Basic Sensor
Class 2 – Smart Sensor
Class 3 – Perception / Intelligent Sensor
```

Ein Gerätetyp bestimmt nicht automatisch die Class.

---

## 10. Beispiele

### Thermostatsensor

```text
Gerätetyp:
Sensor

Class:
1

Typisierung:
Basic Sensor
```

Generator:

```text
Temperature Signal
optional Quality
optional Health diagnosed by ECU
```

Nicht automatisch:

```text
TemperatureSensorFunction
```

### Kamera

```text
Gerätetyp:
Sensor

Class:
3

Typisierung:
Perception / Intelligent Sensor
```

### Gateway

```text
Gerätetyp:
Gateway

Class:
4

Typisierung:
Intelligent Subsystem
```

### Motor

Einfach:

```text
Gerätetyp:
Aktor
Class:
1
Typisierung:
Basic Actuator
```

Geregelt:

```text
Gerätetyp:
Aktor
Class:
2
Typisierung:
Controlled Actuator
```

Smart Drive:

```text
Gerätetyp:
Aktor
Class:
4
Typisierung:
Intelligent Subsystem
```

---

## 11. Zweite Achse: Data Complexity

Zusätzlich intern modellieren:

```text
RAW_SCALAR
PHYSICAL_SCALAR
MULTI_VALUE
STRUCTURED_OBJECT
STRUCTURED_OBJECT_LIST
IMAGE_STREAM
POINT_CLOUD
AUDIO_STREAM
SERVICE_DATA
CONTROL_COMMAND
EVENT
```

Beispiele:

```text
Temperature Sensor
→ PHYSICAL_SCALAR

IMU
→ MULTI_VALUE

Radar
→ STRUCTURED_OBJECT_LIST

LiDAR
→ POINT_CLOUD

Camera
→ IMAGE_STREAM
```

---

## 12. DeviceCapabilityProfile

Implementiere bzw. konsolidiere:

```text
DeviceCapabilityProfile
```

mit mindestens:

```text
device_class
classification_name
device_role
intelligence_level
data_complexity
measurement_capabilities[]
actuation_capabilities[]
processing_capabilities[]
diagnostic_capabilities[]
communication_capabilities[]
output_types[]
requires_function_model
requires_status_model
requires_health_model
requires_quality_model
requires_data_object_model
requires_hardware_interface_model
supports_raw_data
supports_streaming
provenance
```

---

## 13. DeviceClassificationRegistry

Implementiere:

```text
DeviceClassificationRegistry
```

Aufgaben:

```text
resolve_class()
resolve_typing()
resolve_default_capabilities()
resolve_data_complexity()
validate_combination()
```

Spezialisierte Profile bevorzugen, keine riesige Monolithdatei.

---

## 14. Objekt-Wizard erweitern

Bisher:

```text
Identität
→ Zuordnung
→ technische Details
→ Prüfung
```

Neu:

```text
1. Identität
2. Gerätetyp
3. Class
4. Typisierung
5. Capabilities
6. Data Complexity
7. Zuordnung
8. technische Details
9. Generator-Auswirkungen
10. Prüfung
```

---

## 15. Class im Wizard

UI:

```text
Class
```

mit:

```text
0 – Passive
1 – Basic
2 – Smart / Controlled
3 – Perception / Intelligent
4 – Intelligent Subsystem
```

---

## 16. Typisierung im Wizard

Typisierung wird aus:

```text
Gerätetyp
+
Class
```

vorgeschlagen.

Beispiel:

```text
Gerätetyp = Sensor
Class = 3
→ Perception / Intelligent Sensor
```

AI/Heuristik darf Vorschläge erzeugen, aber:

```text
Proposal
→ User Review
→ Approval
```

---

## 17. Model-View-Tabelle erweitern

Bestehende Tabelle:

```text
Name | Gerätetyp | Domäne
```

ändern zu:

```text
Name | Gerätetyp | Class | Typisierung | Domäne
```

Reihenfolge verbindlich:

```text
Gerätetyp
→ Class
→ Typisierung
```

---

## 18. Filter und Sortierung

Neue Filter:

```text
Class
Typisierung
```

Neue Sortierung:

```text
Class
Typisierung
```

---

## 19. Detailansicht

Hardware-Knoten-Details zeigen:

```text
Gerätetyp
Class
Typisierung
Data Complexity
Capabilities
Generator Policy
```

---

## 20. Generator Policy sichtbar machen

Beispiel Basic Sensor:

```text
Auto Function:
NO

Signal:
YES

Status:
OPTIONAL

Health:
ECU_DIAGNOSED

Quality:
OPTIONAL

DataObject:
NO
```

---

## 21. Generatorlogik

Vor Generierung:

```text
HardwareNode
→ DeviceClassificationRegistry
→ DeviceCapabilityProfile
→ GeneratorPolicy
→ Engineering Objects
```

---

## 22. Class-Policies

### Class 0

```text
Function: NO
Signals: RAW / BASIC
Status: NO
Quality: NO / optional external
DataObjects: NO
```

### Class 1

```text
Function: NO by default
Signals: YES
Physical Value: YES for sensor
Command: YES for actuator
Status: OPTIONAL
Quality: OPTIONAL
DataObjects: NO
```

### Class 2

```text
Function: OPTIONAL
Signals: YES
Status: YES / recommended
Health: YES
Quality: YES for sensor
Capabilities: YES
DataObjects: OPTIONAL
```

### Class 3

```text
Function: YES / likely
Subfunctions: YES where justified
Signals: YES
Status: YES
Health: YES
Quality: YES
DataObjects / Streams: YES
Hardware Interfaces: YES as required
```

### Class 4

```text
Function: YES
Multiple Functions: YES
Signals: YES
Status: YES
Health: YES
Communication State: YES where relevant
DataObjects: YES
Hardware Interfaces: YES
Messages: YES
Diagnostics: YES
```

---

## 23. Statusmodell abhängig von Class

Nicht jedem Gerät automatisch:

```text
INIT
READY
ACTIVE
ERROR
```

geben.

Class 1 Sensor:

```text
Physical Value
optional Quality
Health ggf. durch ECU diagnostiziert
```

Class 3 Camera:

```text
OperatingState
HealthState
DataQuality
```

Class 4 Gateway:

```text
OperatingState
HealthState
CommunicationState
```

---

## 24. Signal/DataObject-Entscheidung

```text
PHYSICAL_SCALAR
→ Signal

MULTI_VALUE
→ grouped Signals / Structured Data

STRUCTURED_OBJECT_LIST
→ DataObject

IMAGE_STREAM
→ Stream / DataObject

POINT_CLOUD
→ Stream / DataObject
```

Keine künstliche Zerlegung komplexer Daten in tausende Einzel-Signale.

---

## 25. Hardware-Interface-Generator

Class / Typisierung beeinflusst den Kommunikationsbedarf.

Beispiele:

```text
Basic Temperature Sensor
→ may require no network interface

Smart Camera
→ Ethernet likely
→ status communication
→ streaming capability

Gateway
→ multiple Hardware Interfaces likely
```

Die konkrete Technologie weiterhin deterministisch validieren.

---

## 26. Projekt-Wizard

Die gleiche Device-Class-Logik muss bei der Projekt-Neuanlage gelten:

```text
Requirement
→ Hardware Proposal
→ Device Class Proposal
→ Typing Proposal
→ Capability Profile
→ Generator Policy
→ Functions only where justified
→ Signals / DataObjects
→ Status Models
→ Hardware Interfaces
→ Messages
→ Networks
```

---

## 27. Beispiel Motortemperatur

Requirement:

```text
Motortemperatur überwachen.
```

Erwartung:

```text
Function:
MotorTemperatureMonitoring

Hardware:
TemperatureSensor

Class:
1

Typisierung:
Basic Sensor

Signal:
MotorTemperature

Unit:
°C
```

Nicht:

```text
TemperatureSensorFunction
```

zusätzlich erzeugen.

---

## 28. Beispiel Kamera

Requirement:

```text
Umfeld mit Kameras erfassen.
```

Hardware:

```text
CameraFront
CameraRear
CameraLeft
CameraRight
```

jeweils:

```text
Gerätetyp:
Sensor
Class:
3
Typisierung:
Perception / Intelligent Sensor
```

Dann sind Function Model, DataObjects und Statusmodelle plausibel.

---

## 29. Beispiel Central Gateway

```text
Name:
System

Gerätetyp:
Gateway

Class:
4

Typisierung:
Intelligent Subsystem
```

Generator darf ableiten:

```text
routing capability
multiple hardware interfaces
gateway lifecycle
communication state
diagnostics
```

---

## 30. Legacy-Migration

Bestehende HardwareNodes zuerst inventarisieren.

Für bestehende Objekte:

```text
classification_status
```

mit:

```text
CONFIRMED
PROPOSED
UNKNOWN
REVIEW_REQUIRED
```

Heuristik/AI darf Class/Typisierung vorschlagen.

Keine pauschale automatische Wahrheit.

Keine rückwirkende Funktionsflut für Class-1-Geräte.

---

## 31. DTO/API

HardwareNode DTO mindestens ergänzen um:

```text
device_class
device_typing
data_complexity
classification_status
capability_profile_ref
```

---

## 32. Python-First

Classification und Generator Policy gehören in Python/Core.

Frontend zeigt und editiert:

```text
Class
Typisierung
Capabilities
Data Complexity
```

---

## 33. Findings

Mögliche Findings:

```text
DEVICE_CLASS_MISSING
DEVICE_TYPING_MISSING
DEVICE_CLASSIFICATION_CONFLICT
DEVICE_CAPABILITY_PROFILE_MISSING
DEVICE_FUNCTION_MODEL_OVERGENERATED
DEVICE_FUNCTION_MODEL_MISSING
DEVICE_DATA_COMPLEXITY_UNKNOWN
```

---

## 34. Audit bestehender Generatorlogik

Prüfe insbesondere:

```text
wird für jeden Sensor eine Function erzeugt?
wird für jeden Aktor eine Function erzeugt?
werden einfache Geräte unnötig mit Statusmodellen aufgebläht?
werden Camera/Radar/LiDAR zu simpel behandelt?
werden DataObjects als viele Einzelsignale modelliert?
```

---

## 35. Tests

Mindestens:

```text
Class 0 passive sensor
Class 1 temperature sensor
Class 1 simple actuator
Class 2 smart sensor
Class 2 controlled actuator
Class 3 camera
Class 3 radar
Class 3 lidar
Class 4 gateway
Class 4 intelligent subsystem
```

Generator Tests:

```text
Basic Sensor
→ no dedicated auto Function

Perception Sensor
→ Function model allowed/required

Class 4 Gateway
→ full interface/status model

IMAGE_STREAM
→ no scalar-signal explosion
```

UI Tests:

```text
Class column visible
Typisierung column visible
Class filter works
Typisierung filter works
Wizard fields work
Detail view works
Sorting works
```

---

## 36. Regression

Bestehende Views dürfen nicht brechen:

```text
Hardware
Hardware Interface
Funktion
Interface
Nachrichten
Signale
Structure Tree
```

---

## 37. Dokumentation

Erzeuge / aktualisiere:

```text
docs/device_classification/

00_DEVICE_CLASSIFICATION_OVERVIEW.md
01_DEVICE_CLASSES.md
02_DEVICE_TYPINGS.md
03_DEVICE_CAPABILITY_PROFILE.md
04_DATA_COMPLEXITY.md
05_GENERATOR_POLICY.md
06_SENSOR_CLASSIFICATION.md
07_ACTUATOR_CLASSIFICATION.md
08_PERCEPTION_DEVICES.md
09_INTELLIGENT_SUBSYSTEMS.md
10_OBJECT_WIZARD_INTEGRATION.md
11_PROJECT_WIZARD_INTEGRATION.md
12_MODEL_VIEW_COLUMNS.md
13_LEGACY_MIGRATION.md
14_TEST_STRATEGY.md
```

---

## 38. Definition of Done

Die Aufgabe ist erst abgeschlossen, wenn:

1. HardwareNode eine Device Class besitzt.
2. HardwareNode eine Typisierung besitzt.
3. Class und Typisierung getrennte Felder sind.
4. Classes 0–4 implementiert sind.
5. Typisierungen zu Class und Gerätetyp passen.
6. Model View `Class` und `Typisierung` zeigt.
7. `Class` direkt nach `Gerätetyp` steht.
8. `Typisierung` direkt nach `Class` steht.
9. Filter und Sortierung funktionieren.
10. Objekt-Wizard Class und Typisierung verwaltet.
11. Projekt-Wizard dieselbe Klassifizierung verwendet.
12. DeviceCapabilityProfile vorhanden ist.
13. DataComplexity modellierbar ist.
14. Generator Policy aus Class/Capabilities abgeleitet wird.
15. Class 0 keine künstliche Function erzeugt.
16. Class 1 standardmäßig keine dedizierte Device-Function erzeugt.
17. Class 2 optionale lokale Functions unterstützen kann.
18. Class 3 Function/DataObject/Status-Modelle unterstützt.
19. Class 4 vollständige Subsystem-Modelle unterstützt.
20. Statusmodelle nicht pauschal für jedes Gerät gleich erzeugt werden.
21. Basic Sensoren primär Physical Signals liefern.
22. Camera/Radar/LiDAR komplexe DataObjects/Streams unterstützen.
23. bestehende Objekte migrationsfähig sind.
24. Migration keine künstliche Funktionsflut erzeugt.
25. Python-Core die Generatorentscheidung besitzt.
26. Unit-, Generator-, UI- und Regressionstests erfolgreich sind.
27. Dokumentation dem tatsächlichen As-Built-Stand entspricht.

---

# Zentrale Leitregel

```text
A device class defines HOW intelligent a device is.

A device typing defines WHAT kind of device behavior it represents.

Capabilities define WHAT the device can actually do.

Data complexity defines WHAT kind of data it produces or consumes.

The generator must use these facts before deciding
whether Functions, Signals, Status Models, Data Objects
or Hardware Interfaces are required.
```

Kurz:

```text
DEVICE TYPE
→ CLASS
→ TYPING
→ CAPABILITIES
→ DATA COMPLEXITY
→ GENERATOR POLICY
→ ENGINEERING OBJECTS
```
