# Network Intelligence Simulator
## 60 industrieneutrale Engineering-Assistant-, Typing-, Architektur-, MCP-, Trace- und Generator-Prüfungen

## 1. Zweck

Dieses Dokument definiert einen abgestuften Testsatz für den **Network Intelligence Simulator** und seinen **Engineering Assistant**. Der Chat ist dabei ausschließlich die Bedienoberfläche; der Engineering Assistant muss technische Ziele verstehen, planen, über Skills/MCP/Core ausführen, validieren, Fehler analysieren und zu einem fachlichen Ergebnis führen.

Der Testsatz besteht aus **40 fachlichen A/B-Szenarien** plus **10 zusätzlichen Engineering-Assistant-/MCP-/Skill-/UI-Integrationsprüfungen**.

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


## 1.1 Verbindliches Drei-Runden-Test- und Reparaturprotokoll

Diese Testkampagne arbeitet **nicht** im Muster:

```text
Test schlägt fehl
→ sofort reparieren
→ denselben Test erneut ausführen
→ weiter testen
```

Dieses Vorgehen verfälscht den Gesamtzustand eines Runs und verhindert eine belastbare Aussage darüber, welche Fehler im gleichen Softwarestand gleichzeitig vorhanden waren.

Verbindlich ist deshalb:

```text
FULL RUN
→ FINDINGS FREEZE
→ REPAIR PHASE
→ FULL RUN
→ FINDINGS FREEZE
→ REPAIR PHASE
→ FULL RUN
```

Es sind **maximal drei vollständige Test-Runs** erlaubt.

### Runde 1 – Baseline Run

```text
RUN 1
→ alle 60 Testfälle ausführen
→ keine Produktreparatur während des Runs
→ alle Fehler/Befunde dokumentieren
→ unabhängige Tests trotz anderer Fehler weiter ausführen
→ abhängige, nicht ausführbare Tests als BLOCKED dokumentieren
→ Run vollständig abschließen
→ Finding Ledger einfrieren
```

Erst nachdem **alle 60 Testfälle** den Status

```text
PASSED
FAILED
BLOCKED
SKIPPED_WITH_REASON
```

erhalten haben, darf `REPAIR PHASE 1` beginnen.

Nicht erlaubt:

```text
FAILED TEST
→ Code ändern
→ Run fortsetzen
```

### Repair Phase 1

Nach vollständigem Abschluss von Run 1:

```text
Findings deduplizieren
→ Root Causes clustern
→ Priorität bestimmen
→ Reparaturen implementieren
→ Unit-/Component-Tests durchführen
→ direkte technische Fix-Verifikation
→ Repair Phase vollständig abschließen
```

Während dieser Phase darf **kein neuer vollständiger 60-Test-Run** gestartet werden.

Neu entdeckte Produktfehler während der Ursachenanalyse werden dem Repair Ledger hinzugefügt.

### Runde 2 – vollständiger Re-Run

Erst wenn Repair Phase 1 abgeschlossen ist:

```text
RUN 2
→ wieder alle 60 Testfälle
→ nicht nur zuvor fehlgeschlagene Tests
→ keine Reparatur während des Runs
→ neue und wiederkehrende Findings dokumentieren
→ Run vollständig abschließen
→ Finding Ledger einfrieren
```

Danach:

```text
REPAIR PHASE 2
```

nach denselben Regeln.

### Runde 3 – finaler Acceptance Run

Erst nach vollständigem Abschluss von Repair Phase 2:

```text
RUN 3
→ alle 60 Testfälle erneut
→ keine Reparatur während des Runs
→ vollständige Findings-Erfassung
→ finaler Quality-Gate-Status
```

Run 3 ist der **letzte automatische Full Run dieser Kampagne**.

### Verhalten nach Run 3

Wenn Run 3 das Quality Gate erfüllt:

```text
CAMPAIGN = PASSED
```

Wenn Run 3 noch Defekte enthält:

```text
Findings dokumentieren
→ optional REPAIR PHASE 3 durchführen
→ keine vierte automatische Full-Run-Runde starten
```

Nach einer Reparatur nach Run 3 lautet der Status:

```text
REPAIR_APPLIED_AWAITING_NEW_CAMPAIGN
```

und **nicht** `PASSED`, solange keine neue vollständige Testkampagne die Reparaturen bestätigt hat.

Damit bleibt die Regel erhalten:

> **Eine Reparatur ist nicht automatisch ein bestandener Systemtest.**

### Was nicht als zusätzlicher Full Run zählt

Innerhalb einer Repair Phase erlaubt:

```text
Unit Tests
Component Tests
Schema Tests
gezielte Entwicklerdiagnose
lokale Reproduktionschecks
```

Diese dienen ausschließlich der Reparaturverifikation.

Sie ersetzen nicht den nächsten vollständigen 60-Test-Run.

### Run-Isolation

Jeder Full Run verwendet einen definierten Software-/Modellstand:

```text
run_id
build_id / commit_id
test_manifest_version
skill_versions
mcp_registry_version
technology_profile_version
model_schema_version
started_at
finished_at
```

Während des Full Runs dürfen diese Versionen nicht verändert werden.

### Finding Ledger pro Run

Speichern:

```text
runs/
├── run-1/
│   ├── results/
│   ├── findings/
│   └── evidence/
├── repair-1/
├── run-2/
│   ├── results/
│   ├── findings/
│   └── evidence/
├── repair-2/
└── run-3/
    ├── results/
    ├── findings/
    └── evidence/
```

### Wiederkehrende Fehler

Wenn ein Fehler in mehreren Runs erneut auftritt:

```text
same_root_cause = true
```

und auf dasselbe Master Finding referenzieren.

Nicht jedes Mal einen fachlich identischen Fehler als unabhängiges Finding zählen.

### Regressionsfehler

Ein Fehler, der in Run 1 nicht vorhanden war, aber nach Repair Phase 1 in Run 2 entsteht:

```text
REGRESSION_INTRODUCED
```

Ein Fehler, der nach Repair Phase 2 erstmals in Run 3 entsteht:

```text
REGRESSION_INTRODUCED
```

### Quality Trend

Nach jeder Runde berechnen:

```text
pass_rate
failure_rate
blocked_rate
critical_findings
new_findings
reopened_findings
regressions
resolved_since_previous_run
```

Zieltrend:

```text
Run 1
→ Baseline

Run 2
→ deutliche Fehlerreduktion

Run 3
→ Acceptance
```

### Harte Drei-Runden-Regel

```text
MAX_FULL_RUNS_PER_CAMPAIGN = 3
```

Der Tool Checker darf nicht selbstständig:

```text
Run 4
Run 5
...
```

starten.

Ist das Ziel nach Run 3 nicht erreicht, wird eine neue Testkampagne bewusst gestartet.

---



## 1.2 Projektneutralität – verbindlicher Produktvertrag

`industrieneutral` oder `projektneutral` bedeutet im NIS ausdrücklich **nicht**:

```text
unbekannte Technologie
→ Automotive Default
```

und auch nicht:

```text
fehlende Parameter
→ generische Ersatzrate
→ scheinbar plausibles Ergebnis
```

Projektneutralität bedeutet:

```text
jede verwendete Technologie
→ besitzt eine eindeutige kanonische Identität
→ besitzt ein vollständiges maschinenlesbares Parameter-/PHY-Profil
→ besitzt einen expliziten Capability-Status
→ verwendet nur fachlich passende Berechnungsmodelle
→ verwendet keine versteckten technologieübergreifenden Fallbacks
```

Automotive-spezifische Modelle dürfen nur verwendet werden, wenn:

```text
Technology / Domain Profile
→ Automotive explizit verlangt oder fachlich gebunden
```

Nicht als Default für:

```text
Industrial
Building
Marine
Robotics
Process
Embedded
Rail
Energy
Generic
```

### Harte Neutralitätsregel

```text
AUTOMOTIVE_FALLBACK_IN_NEUTRAL_PROJECT
→ FAIL
```

Beispiele:

```text
RS-485 ohne Baudrate
→ NICHT automatisch 1 Mbit/s

unbekannter Ethernet-/Buspfad
→ NICHT automatisch 100 Mbit/s

CAN XL
→ NICHT als CAN-FD zurückgeben

EtherCAT / PROFINET / Modbus / I²C / SPI
→ NICHT durch denselben generischen Timing-Rechner
  als vermeintlich deterministisch verifiziert ausgeben
```

Wenn notwendige Daten oder Modelle fehlen:

```text
UNKNOWN
UNASSIGNED
UNVERIFIED
REVIEW_REQUIRED
BLOCKED
```

statt erfundener Präzision.

> **UNKNOWN ist fachlich besser als ein falscher Default.**

---

## 1.3 Technology Capability Registry – Single Source of Truth

Alle Kommunikationstechnologien müssen über eine zentrale:

```text
TechnologyCapabilityRegistry
```

aufgelöst werden.

Nicht über verteilte:

```text
if protocol == ...
```

Ketten in Capacity, Timing, Routing, Simulation oder UI.

### TechnologyCapability

Mindestens:

```text
TechnologyCapability
├── canonical_id
├── display_name
├── aliases[]
├── classification
├── family
├── domain_profiles[]
├── protocol_stack[]
├── lower_layer_binding
├── required_parameters[]
├── optional_parameters[]
├── physical_layer_profile
├── topology_model
├── medium_access_model
├── arbitration_model
├── addressing_model
├── integrity_mechanisms[]
├── diagnostic_mechanisms[]
├── supervision_mechanisms[]
├── routing_capability
├── capacity_capability
├── timing_capability
├── simulation_capability
├── trace_decode_capability
├── capacity_model
├── timing_model
├── simulation_model
├── fallback_allowed
├── evidence_requirements
└── verification_status
```

### Keine 125 Sonder-IFs

Eine Technologie muss nicht zwingend einen völlig eigenen Rechner besitzen.

Zulässig:

```text
PROFINET
→ expliziter Protocol Stack
→ Ethernet Lower Layer
→ PROFINET-spezifischer Overhead / Scheduling Adapter
```

oder:

```text
SOME/IP
→ Ethernet
→ IP
→ UDP/TCP
→ SOME/IP
```

Aber die Ableitung muss:

```text
explizit
maschinenlesbar
deterministisch
versioniert
```

sein.

Nicht:

```text
unbekannt
→ generic timing
```

---

## 1.4 Technologie-Reifegrade

Für jede registrierte Technologie wird mindestens folgender Reifegrad geführt:

```text
REGISTERED
↓
PARAMETERIZED
↓
CAPACITY_SUPPORTED
↓
TIMING_SUPPORTED
↓
SIMULATION_SUPPORTED
↓
VERIFIED
```

Bedeutung:

### REGISTERED

```text
Name / Canonical ID bekannt
```

### PARAMETERIZED

```text
erforderliche Parameter
PHY
Topologie
Adressierung
Arbitration / Medium Access
Mechanismen
```

sind maschinenlesbar definiert.

### CAPACITY_SUPPORTED

Deterministischer Last-/Kapazitätsnachweis ist über:

```text
eigenes Modell
oder
explizit gebundenen Technology Stack
```

möglich.

### TIMING_SUPPORTED

Deterministische Zeitberechnung ist über ein passendes Modell möglich.

### SIMULATION_SUPPORTED

Technologiespezifisches Verhalten ist in der Simulation modelliert.

### VERIFIED

Nur wenn:

```text
Parameter vollständig
+
Technology Binding valide
+
Capacity nachweisbar oder NOT_APPLICABLE
+
Timing nachweisbar oder NOT_APPLICABLE
+
Simulation nachweisbar oder NOT_APPLICABLE
+
Evidence vorhanden
```

### NOT_APPLICABLE

Für Fähigkeiten, die fachlich nicht anwendbar sind, ist ausdrücklich:

```text
NOT_APPLICABLE
```

zulässig.

Beispiel:

```text
GPIO / PWM Direct Signal
→ keine künstliche Buslast erzeugen
→ Capacity = NOT_APPLICABLE
```

Nicht:

```text
Capacity = 0 %
```

wenn tatsächlich kein Busmodell existiert.

---

## 1.5 Dynamisches Technology-Coverage-Gate

Jeder Full Run muss **alle aktuell registrierten Technologien** aus der Technology Registry enumerieren.

Nicht nur die Technologien aus den 40 Projektszenarien.

Prüfe für jede Technologie:

```text
Canonical ID
Alias Resolution
Classification
Required Parameters
Physical Layer
Medium Access / Arbitration
Routing Capability
Capacity Capability
Timing Capability
Simulation Capability
Trace Decode Capability
Fallback Policy
Verification Status
```

Erzeuge:

```text
TechnologyCoverageReport
```

### Beispiel

Wenn zur Laufzeit:

```text
registered = 125
timing_supported = 4
```

darf nicht berichtet werden:

```text
125 technologies supported
```

sondern:

```text
Registered:          125
Timing Supported:      4
Timing Incomplete:   121
```

mit konkreten Technology IDs.

### Hard Gate

Jede Technologie, die im Produkt als vollständig unterstützt dargestellt wird, aber keinen vollständigen Capability-/Verification-Pfad besitzt:

```text
TECHNOLOGY_CAPABILITY_FALSE_POSITIVE
→ FAIL
```

---

## 1.6 Canonical Technology ID Contract

Jede Technologie besitzt genau eine kanonische ID.

Beispiel:

```yaml
canonical_id: ros2
display_name: ROS 2

aliases:
  - ROS2
  - ROS_2
  - ros-2
```

Ingress darf Aliase akzeptieren.

Nach Normalisierung verwenden alle Module nur:

```text
canonical_id
```

Pflicht für:

```text
Technology Registry
Wizard
Generator
Core
Routing
Capacity
Timing
Simulation
Trace
Validation
Engineering Assistant
UI
```

### Identität darf nicht verloren gehen

Nicht erlaubt:

```text
Input: CAN_XL
↓
Capacity Adapter: CAN_FD_PHASE_ESTIMATE
↓
Output protocol: CAN_FD
```

Erlaubt:

```text
technology_id: CAN_XL
capacity_status: UNVERIFIED
reason: CAN_XL_CAPACITY_MODEL_NOT_IMPLEMENTED
```

oder bei implementiertem Modell:

```text
technology_id: CAN_XL
capacity_model: CANXLCapacityModel
status: VERIFIED
```

Finding bei Identitätsverlust:

```text
TECHNOLOGY_IDENTITY_LOSS
```

---

## 1.7 Keine versteckten Fallbacks

Für produktive Engineering-Nachweise gilt standardmäßig:

```text
fallback_allowed = false
```

Insbesondere verboten:

```text
missing bitrate
→ substitute bitrate

missing timing model
→ generic timing model

missing capacity model
→ generic bus load

unknown technology
→ CAN / CAN-FD / Ethernet default

technology-specific data missing
→ silently adopt catalog default
```

Stattdessen:

```text
UNVERIFIED
```

mit Angabe:

```text
missing_parameter
missing_model
required_user_input
affected_calculation
affected_preflight
```

### Fallback Detection

Der Tool Checker muss erkennen:

```text
TECHNOLOGY_FALLBACK_USED
GENERIC_RATE_FALLBACK_USED
GENERIC_CAPACITY_FALLBACK_USED
GENERIC_TIMING_FALLBACK_USED
CROSS_TECHNOLOGY_MODEL_REUSE
```

Diese Findings sind für Mandatory Checks:

```text
FAIL
```

---

## 1.8 Vollständige produktive Projekterzeugung

Jeder fachliche Szenariofall muss im **laufenden produktiven Testsystem** vollständig angelegt werden.

Nicht ausreichend:

```text
Projekt-Kachel existiert
```

oder:

```text
Projektname wurde gespeichert
```

Pflicht:

```text
Project
↓
Engineering Objects
↓
Functions
↓
Mappings
↓
Interfaces / Ports
↓
Networks
↓
Technology Bindings
↓
Signals / DataObjects
↓
Transport Units
↓
Routes
↓
Capacity / Timing Status
↓
Validation / Preflight
↓
Persistence / Reload
```

soweit für den jeweiligen Testfall fachlich anwendbar.

### PROJECT_SHELL_ONLY

Wenn nur:

```text
Projektname
Kachel
leere Struktur
```

existiert:

```text
PROJECT_SHELL_ONLY
→ FAIL
```

### Produktiver Pfad

Die Projekterzeugung muss über den realen Produktpfad laufen:

```text
Wizard
Engineering Assistant
registrierte API/MCP/Core-Pfade
```

Nicht durch einen Test-Hack, der das Produkt umgeht.

---

## 1.9 Lücken im Projekt bleiben sichtbar

Ein Testprojekt darf trotz Lücken erzeugt werden.

Beispiel:

```text
Hardware erzeugt
Network erzeugt
Technology Parameter fehlt
```

Dann:

```text
Projekt bleibt vorhanden
+
betroffenes Objekt wird markiert
+
Preflight = BLOCKED / REVIEW_REQUIRED
```

Nicht:

```text
gesamte Projekterzeugung verwerfen
```

und nicht:

```text
fehlenden Wert still erfinden
```

---

## 1.10 Fehler- und Blockermarkierung in bestehenden Views

Blocker und Fehler sollen **an der fachlich betroffenen Stelle** sichtbar sein.

Keine neue Ansicht und kein zusätzlicher Haupt-Navigationsbutton nur für diese Fehler einführen.

Beispiele:

```text
Network Fehler
→ bestehender Network Editor

Routing Fehler
→ bestehende Routing View

Capacity Fehler
→ bestehender Capacity/Analysis Bereich

Timing Fehler
→ bestehender Timing Bereich

Signal Fehler
→ bestehende Signal-/Message-Details

Preflight Blocker
→ bestehender Validation/Preflight Bereich

Trace Fehler
→ bestehende Trace Views

Engineering Assistant Fehler
→ bestehender Assistant Result / Finding Context
```

Zulässige Darstellung:

```text
Badge
Status
Icon
Inline Marker
Existing Detail Drawer
Existing Finding Link
Tooltip
Row State
Object Detail
```

Nicht:

```text
neuer "Fehler anzeigen"-Hauptbutton
```

nur um fehlende Produktintegration zu kaschieren.

### Aggregation bleibt erlaubt

Eine bestehende Finding-/Issue-Sicht darf Findings zentral aggregieren.

Aber:

> **Das Quellobjekt muss den Fehler ebenfalls sichtbar markieren.**

---

## 1.11 Reparaturfähiger Finding Contract

Jeder gefundene Fehler muss so detailliert gespeichert werden, dass daraus direkt ein RepairWorkPackage erzeugt werden kann.

Mindestens:

```text
finding_id
campaign_id
run_id
scenario_id
project_id
project_revision

classification
severity
status
repair_owner

subsystem
first_failing_layer
affected_objects[]
canonical_object_ids[]

technology_id
technology_profile_version
capability_status

symptom
expected_behavior
observed_behavior

input_parameters
missing_parameters
calculated_values
fallback_detected

reproduction_steps[]
evidence_refs[]
logs[]
screenshots[]
trace_refs[]

root_cause_status
root_cause
causal_chain[]
dependent_findings[]

affected_services[]
suspected_files[]

required_fix
acceptance_criteria[]
targeted_retest[]
regression_scope[]

runtime_build_id
runtime_component_versions

created_at
updated_at
```

### Befund muss reparierbar sein

Nicht ausreichend:

```text
"Timing falsch"
```

Erforderlich z. B.:

```text
Technology: I2C
Expected:
I2C-specific timing model

Observed:
generic 0.256 ms result

First failing layer:
Timing Model Resolution

Fallback:
GENERIC_TIMING_FALLBACK_USED

Affected service:
Timing Engine

Acceptance:
I2C timing uses clock frequency,
addressing, ACK/NACK, Start/Stop
and optional clock stretching.
```

---

## 1.12 Folgefehler nicht als neue Root Cause

Beispiel:

```text
Technology Timing Model fehlt
↓
Capacity/Timing unverified
↓
Preflight blocked
↓
Simulation unavailable
```

Master Finding:

```text
TECHNOLOGY_TIMING_MODEL_MISSING
```

Dependent Findings referenzieren diese Ursache.

`TC_EXPECTATION_MISMATCH` bei einem bereits fehlgeschlagenen Ablauf ist:

```text
dependent / consequential finding
```

und keine zweite unabhängige Root Cause.

---

## 1.13 Technology Capability – technologiespezifische Mindestsemantik

Der Tool Checker prüft bei relevanten Technologien nicht nur den Namen.

Beispiele:

### EtherCAT

Mindestens berücksichtigen:

```text
Ethernet PHY / Link
Frame Structure
Processing-on-the-fly
Topology
Slave Count / Hop Behavior
Cycle
Working Counter
Distributed Clock / Timing Context, wenn genutzt
```

### PROFINET

Mindestens:

```text
RT / IRT Profile
Cycle
Ethernet Frames
Scheduling
Topology
Protocol Overhead
```

### Modbus RTU

Mindestens:

```text
Baudrate
Character Format
Silent Interval
Request/Response
CRC
Slave Address
```

### I²C

Mindestens:

```text
Clock Frequency
Addressing
Start / Stop
ACK / NACK
Transfer Direction
Clock Stretching, wenn relevant
Arbitration, wenn Multi-Master
```

### SPI

Mindestens:

```text
Clock Frequency
Chip Select
Word Length
Transfer Structure
Duplex Mode
Clock Polarity / Phase, wenn für Modell relevant
```

### CAN XL

Muss als:

```text
CAN_XL
```

identitätsstabil bleiben.

Kein implizites Zurückfallen auf:

```text
CAN_FD
```

---

## 1.14 Daten- und Generierungsqualität

Projektneutralität bedeutet auch:

```text
erzeugte Engineering-Daten
müssen fachlich zum jeweiligen Szenario passen.
```

Verboten:

```text
random device mapping
random signal assignment
cross-technology defaults
generic message generation without technology contract
unvalidated placeholder treated as verified
```

Jeder generierte Wert erhält:

```text
source
status
```

z. B.:

```text
USER_CONFIRMED
DERIVED
CALCULATED
CATALOG
TECHNOLOGY_PROFILE
PROPOSED
UNKNOWN
```

---

## 1.15 Technologie-Readiness im Preflight

Preflight muss getrennt ausweisen:

```text
Technology Registered
Technology Parameterized
PHY Ready
Routing Ready
Capacity Ready
Timing Ready
Simulation Ready
Trace Ready
```

Beispiel:

```text
EtherCAT

Registered:        READY
Parameterized:     READY
PHY:               READY
Routing:           READY
Capacity:          UNVERIFIED
Timing:            UNVERIFIED
Simulation:        BLOCKED
```

Kein scheinbares Gesamt-PASS.

---

## 1.16 Simulation Gate

Simulation darf keine technologiespezifische Genauigkeit vortäuschen.

Wenn:

```text
capacity/timing model missing
```

und der Test diese Modelle benötigt:

```text
Simulation Preflight = BLOCKED
```

mit Finding.

Nicht:

```text
generic estimate
→ Simulation READY
```

---

## 1.17 Runtime-/Produktivitätsnachweis

Jeder Full Run arbeitet gegen den tatsächlich laufenden Produktbuild.

Pflicht:

```text
runtime_build_id
runtime_component_versions
```

Für Reparaturen gilt:

```text
FIXED IN CHECKOUT
≠
FIXED IN PRODUCT
```

Vor dem nächsten Full Run müssen relevante Repairs:

```text
gebaut
bereitgestellt
Runtime-verifiziert
```

sein.

Ein Test darf nicht gegen Build A laufen und seine Reparatur nur aus Checkout B bewerten.

---

## 1.18 Mandatory Cross-Cutting Assertions

Die folgenden Assertions gelten für **alle 60 Prüfungen**, soweit fachlich anwendbar:

```text
canonical_technology_identity_preserved = true
hidden_fallback_used = false
project_materialized_in_running_product = true
project_shell_only = false
required_objects_persisted = true
gaps_explicitly_marked = true
blockers_visible_in_existing_view = true
finding_detail_repair_ready = true
validation_status_truthful = true
capacity_status_truthful = true
timing_status_truthful = true
simulation_status_truthful = true
```

Mandatory Failure:

```text
FALSE PRECISION
→ FAIL

HIDDEN FALLBACK
→ FAIL

TECHNOLOGY IDENTITY LOSS
→ FAIL

PROJECT SHELL ONLY
→ FAIL

BLOCKER WITHOUT SOURCE-VIEW MARKER
→ FAIL

FINDING WITHOUT REPAIR EVIDENCE
→ FAIL
```

---


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


Zusätzlich muss der Agent:

20. Technology IDs ausschließlich kanonisch verwenden.
21. Aliase am Eingang normalisieren, aber nie als interne Identität weiterreichen.
22. vor Technology Binding den Capability-/Verification-Status prüfen.
23. keine Automotive- oder Cross-Technology-Fallbacks in neutralen Projekten verwenden.
24. fehlende Parameter als `UNKNOWN / UNVERIFIED` behandeln.
25. fehlende Capacity-/Timing-Modelle als Lücke ausweisen statt generische Präzision zu erzeugen.
26. Projektobjekte vollständig im produktiven Modell anlegen und persistieren.
27. fachliche Lücken am betroffenen Objekt markieren.
28. Blocking Findings in Validation / Preflight übernehmen.
29. Findings mit ausreichender Repair-Evidence erzeugen.
30. `PROJECT_SHELL_ONLY` niemals als Completion akzeptieren.


Nicht ausreichend:

```text
"Öffnen Sie den Netzwerk-Editor."
```

Der Agent soll die notwendigen Engineering-Schritte selbst ausführen.


### Engineering Assistant – verbindliche Produktdefinition

Der produktive Name und die fachliche Rolle lauten:

```text
Engineering Assistant
```

Der Chat ist lediglich:

```text
Chat UI
```

für den Engineering Assistant.

Der Engineering Assistant darf daher **nicht** als reiner Text-Chat implementiert oder getestet werden.

Verbindliches Ziel:

```text
USER ENGINEERING INTENT
↓
UNDERSTAND
↓
RESOLVE MODEL CONTEXT
↓
DETERMINE GOAL
↓
INSPECT EXISTING MODEL
↓
DETECT ENGINEERING DECISIONS
↓
ASK ONLY IF NECESSARY
↓
PLAN
↓
SELECT SKILLS / MCP CAPABILITIES
↓
EXECUTE
↓
VALIDATE
↓
REPAIR IF AUTHORIZED
↓
COMPLETE
↓
RETURN ENGINEERING RESULT
```

### Ergebnisvertrag für natürliche Engineering-Eingaben

Eine syntaktisch und fachlich verständliche Nutzereingabe darf nicht einfach in:

```text
ERROR
```

oder:

```text
"Das kann ich nicht."
```

enden, wenn die notwendige NIS-Funktion grundsätzlich vorhanden ist.

Zulässige Endzustände:

```text
COMPLETED
WAITING_FOR_ENGINEERING_DECISION
BLOCKED_WITH_EXPLICIT_CAUSE
NOT_SUPPORTED_WITH_CAPABILITY_GAP
```

Ein unerwarteter technischer Fehler ist:

```text
ENGINEERING_ASSISTANT_EXECUTION_DEFECT
```

und muss als Produktbefund erfasst werden.

### Grundsatz

```text
VALID ENGINEERING COMMAND
→ ENGINEERING RESULT
```

oder – wenn eine echte Entscheidung fehlt:

```text
VALID ENGINEERING COMMAND
→ PRECISE ENGINEERING QUESTION
→ USER DECISION
→ RESUME
→ ENGINEERING RESULT
```

Nicht:

```text
VALID ENGINEERING COMMAND
→ GENERIC CHAT ERROR
```

### Engineering Assistant muss Handlungssprache verstehen

Mindestens folgende Intents:

```text
CREATE
ADD
CONNECT
CHANGE
CONFIGURE
REMOVE
INSPECT
FIND
VALIDATE
CALCULATE
SIMULATE
ANALYZE
COMPARE
DIAGNOSE
REPAIR
OPTIMIZE
EXPLAIN
TRACE
MEASURE
```

Diese Intents müssen auf die NIS-Fachbereiche abbildbar sein:

```text
Project
Hardware
Function
Signal / DataObject
Interface / Port
Network
Technology Binding
Transport Unit
Routing
Capacity
Timing
Validation / Preflight
Simulation
Trace Analysis
E2E Timing
Finding / Repair
Diagnostics
Visualization
```

### Folgekommunikation und Kontext

Der Engineering Assistant muss anaphorische und verkürzte Folgeaufträge aus dem aktiven Engineering-Kontext verstehen.

Beispiel nach einem zuvor festgestellten Fehler:

```text
"Dann weißt du ja, was du zu tun hast:
Fehleranalyse und Korrektur."
```

Erwartung:

```text
resolve previous failed goal / finding
→ load evidence
→ root-cause analysis
→ determine repair scope
→ implement authorized repair
→ validate repair
→ return result
```

Nicht:

```text
"Fehler: unklare Eingabe"
```

oder:

```text
"Bitte beschreiben Sie, welchen Fehler Sie meinen."
```

wenn der aktive Workload und das vorherige Finding den Referenten eindeutig machen.

Nur wenn mehrere fachlich unterschiedliche aktive Findings existieren und keine eindeutige Zuordnung möglich ist:

```text
WAITING_FOR_ENGINEERING_DECISION
```

mit konkreter Auswahl.

### Modellierungsauftrag in natürlicher Sprache

Beispiel:

```text
"Lege eine ECU an, die mir die Stellgliedpositionen
im System alle 30 Sekunden abfragt."
```

Diese Eingabe muss zu einem Engineering-Ergebnis führen.

Erwarteter Ablauf:

```text
Goal = CREATE_PERIODIC_ACQUISITION_FUNCTION
↓
aktuelles Projekt lesen
↓
Stellglieder identifizieren
↓
verfügbare Stellgliedpositionsdaten identifizieren
↓
bestehende ECU / Hardware prüfen
↓
CREATE vs REUSE entscheiden
↓
falls neue ECU ausdrücklich verlangt:
ECU anlegen
↓
Function für zyklische Positionsabfrage anlegen
↓
cycle_time = 30 s
↓
Producer/Consumer bestimmen
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
Result
```

Wenn einzelne Stellglieder keine Positionsinformation bereitstellen:

```text
Finding / Data Gap
```

erzeugen und die eindeutig möglichen Teile trotzdem bearbeiten.

Keine pauschale Fehlermeldung.

### Periodische Kommunikationsaufträge

Der Assistant muss Aussagen erkennen wie:

```text
alle 30 Sekunden
alle 100 ms
zyklisch
bei Änderung
bei Ereignis
bei Fehler
auf Anfrage
```

und korrekt in Kommunikationssemantik übersetzen:

```text
CYCLIC
EVENT_DRIVEN
ON_CHANGE
ON_REQUEST
DIAGNOSTIC_REQUEST
FAULT_TRIGGERED
```

### Deterministische Ableitungen nicht erfragen

Bei:

```text
"alle 30 Sekunden"
```

darf nicht gefragt werden:

```text
"Welchen Zyklus möchten Sie?"
```

Der Zyklus ist bereits bestimmt:

```text
cycle_time = 30 s
```

### Domain-weite Wiederverwendung

Diese Art der Kommunikation gilt nicht nur für Hardware-Erzeugung.

Der gleiche Engineering-Assistant-Vertrag muss gelten für:

```text
"Füge einen zweiten CAN-FD-Kanal hinzu."

"Verbinde Controller A mit Gateway B."

"Ändere das LIN-Netz auf 19,2 kbit/s
und berechne alles neu."

"Prüfe, warum PressureCommand zu spät ankommt."

"Simuliere den Ausfall des Gateways."

"Finde alle Signale ohne Consumer."

"Behebe die Validation-Fehler, die eindeutig korrigierbar sind."

"Zeige mir die E2E-Verbindung von Function A zu Function B."

"Lege eine Diagnoseabfrage für alle Stellglieder an."

"Mach das auch für die anderen Aktoren."
```

### Kein Delegieren an UI-Werkzeuge

Nicht erlaubt:

```text
"Öffne den Hardware Editor und lege die ECU dort an."
```

wenn der Engineering Assistant selbst über Skill/MCP/Core die Änderung ausführen kann.

Deep Links dürfen zusätzlich angeboten werden:

```text
[ECU öffnen]
[Route ansehen]
```

aber erst nach bzw. neben der fachlichen Ausführung.

### Fehlerbehandlung des Engineering Assistant

Tool-/Core-Fehler:

```text
tool failed
```

dürfen nicht unmittelbar als Nutzerergebnis enden.

Erwartung:

```text
tool failure
↓
classify
↓
retry only if transient
↓
inspect model / preconditions
↓
alternative valid tool path if available
↓
repair if within authorization
↓
revalidate
```

Nur wenn der Auftrag objektiv blockiert ist:

```text
BLOCKED_WITH_EXPLICIT_CAUSE
```

mit:

```text
cause
affected_object
missing_capability / decision
what_was_already_done
what_is_needed_next
```

### Engineering Assistant Completion

Tool Success ist kein Completion-Kriterium.

Beispiel:

```text
ECU created
```

ist für den 30-Sekunden-Abfrageauftrag nicht ausreichend.

Completion erst wenn mindestens:

```text
ECU exists
Function exists
30 s timing semantics exist
required data sources resolved
interfaces valid
transport valid
routing valid
capacity/timing evaluated
validation executed
blocking findings reported
```

### Assistant Evidence

Für jeden schreibenden Assistant-Auftrag speichern:

```text
user_intent
resolved_goal
model_context
objects_reused
objects_created
engineering_decisions
execution_plan
skills_used
mcp_tools_used
model_before
model_after
model_diff
validation
completion
```


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

Zusätzlich für jede in S20-A verwendete Technologie:

```text
Canonical Technology ID
Required Parameters
PHY Profile
Capacity Capability Status
Timing Capability Status
Simulation Capability Status
Trace Decode Capability Status
Verification Status
```

Fehlt ein technologiespezifischer Nachweis:

```text
UNVERIFIED / BLOCKED
```

statt Fallback.

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


Zusätzliche Querschnittsmetriken:

```text
Technology Registry Coverage
Parameterized Technology Coverage
Capacity Supported Coverage
Timing Supported Coverage
Simulation Supported Coverage
Trace Decode Coverage
Canonical ID Consistency
Alias Resolution Accuracy
Technology Identity Loss Count
Hidden Fallback Count
Generic Rate Fallback Count
Generic Timing Fallback Count
Generic Capacity Fallback Count
Productive Project Materialization Rate
Project Shell Only Count
Persistence / Reload Pass Rate
In-Place Blocker Marker Coverage
Repair-Ready Finding Coverage
```

Harte Zielwerte:

```text
Technology Identity Loss Count = 0
Hidden Fallback Count = 0
Project Shell Only Count = 0
Mandatory In-Place Blocker Marker Coverage = 100 %
Mandatory Repair-Ready Finding Coverage = 100 %
```


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

# 18.1 Mandatory Technology Capability & Product Reality Gate

Diese Prüfungen ändern die Anzahl der 60 Testfälle nicht.

Sie sind **verbindliche Assertions innerhalb der bestehenden Fälle**.

## TC-TECHCAP-01 – Registry vollständig enumerierbar

```text
technology_registry.list_all()
```

muss jede registrierte Technologie liefern.

PASS nur wenn:

```text
canonical_id unique
display name defined
aliases normalized
classification defined
verification status defined
```

---

## TC-TECHCAP-02 – Alias Normalization

Mindestens prüfen:

```text
ROS2
ROS_2
ros-2
```

→ dieselbe kanonische ID.

Analog für registrierte Aliase weiterer Technologien.

---

## TC-TECHCAP-03 – Technology Identity Preservation

Beispiel:

```text
CAN_XL
```

muss durch:

```text
Registry
Generator
Routing
Capacity
Timing
Simulation
Trace
UI
```

als:

```text
CAN_XL
```

identifizierbar bleiben.

---

## TC-TECHCAP-04 – Required Parameter Completeness

Für jede Technologie:

```text
required_parameters
```

prüfen.

Fehlende Pflichtparameter:

```text
UNVERIFIED
```

Nicht automatisch ergänzen.

---

## TC-TECHCAP-05 – No Generic Rate Fallback

Gezielt Pflichtparameter entfernen.

Erwartung:

```text
missing rate
→ UNVERIFIED
```

Nicht:

```text
1 Mbit/s
100 Mbit/s
generic default
```

---

## TC-TECHCAP-06 – Capacity Capability Truth

Wenn kein deterministischer Capacity-Pfad existiert:

```text
capacity = UNVERIFIED
```

Nicht numerischer Fake-Wert.

---

## TC-TECHCAP-07 – Timing Capability Truth

Wenn kein passendes Timing-Modell existiert:

```text
timing = UNVERIFIED
```

Nicht:

```text
0.256 ms
```

aus einem technologieunabhängigen Defaultpfad.

---

## TC-TECHCAP-08 – Cross-Technology Timing Differenzierung

Für Technologien mit vollständig definierten Parametern prüfen:

```text
EtherCAT
PROFINET
Modbus RTU
I2C
SPI
```

Die Berechnung muss technologiespezifische Mechanismen verwenden.

Ein identisches Ergebnis ist nur zulässig, wenn die konkreten Parameter dies tatsächlich ergeben und der Berechnungspfad dies nachweist.

Nicht ausreichend:

```text
all technologies
→ same generic timing equation
```

---

## TC-TECHCAP-09 – Direct Signal N/A

GPIO/PWM oder vergleichbare Direct-Signal-Technologien:

```text
Capacity = NOT_APPLICABLE
```

wenn kein Buslastmodell fachlich anwendbar ist.

Keine künstliche Buslast.

---

## TC-TECHCAP-10 – Technology Stack Resolution

Höhere Protokolle müssen explizite Lower-Layer-Bindings verwenden.

Beispiele:

```text
SOME/IP
→ Ethernet / IP / UDP or TCP / SOME-IP

PROFINET
→ Ethernet + PROFINET Profile
```

---

## TC-PROJECT-01 – Vollständige Projektrealisierung

Jeder S01-A…S20-B-Fall muss im laufenden Produkt ein reales, persistentes Projekt erzeugen.

Nicht nur Kachel.

---

## TC-PROJECT-02 – Required Object Coverage

Vergleiche Scenario Specification gegen tatsächlich erzeugte:

```text
Hardware
Functions
Signals/DataObjects
Interfaces/Ports
Networks
Transport Units
Routes
```

---

## TC-PROJECT-03 – Persistenz

```text
Create
→ Save
→ Reload
→ same canonical objects / relations
```

---

## TC-PROJECT-04 – Lücken erhalten

Fehlende Information:

```text
UNKNOWN / UNVERIFIED
```

bleibt als Gap bestehen.

Kein stilles Auffüllen.

---

## TC-PROJECT-05 – Blocker am Quellobjekt

Jeder Blocking Finding muss zusätzlich in der bestehenden fachlichen View am betroffenen Objekt sichtbar sein.

---

## TC-FINDING-01 – Repair-Ready Detail

Jeder FAIL/BLOCKED-Befund muss mindestens:

```text
Expected
Observed
First Failing Layer
Affected Objects
Evidence
Runtime Build
Acceptance Criteria
```

enthalten.

---

## TC-FINDING-02 – Root-Cause Dependency

Folgefehler dürfen auf Master Finding verweisen.

Keine künstliche Root-Cause-Vervielfachung.

---

## TC-RUNTIME-01 – Running Product Only

Product Flow Tests müssen gegen den laufenden Build erfolgen.

Checkout-only Proof:

```text
nicht ausreichend
```

---

## Mandatory Gate

```text
TC-TECHCAP mandatory pass rate = 100 %
TC-PROJECT mandatory pass rate = 100 %
TC-FINDING mandatory pass rate = 100 %
TC-RUNTIME mandatory pass rate = 100 %
```

---


# 19. Zehn zusätzliche Engineering-Assistant-, MCP-, Skill- und UI-Integrationsprüfungen

Diese zehn Prüfungen ergänzen die fachlichen A/B-Szenarien um die technische Agenten- und Integrationsschicht.

Sie prüfen insbesondere:

```text
Engineering Assistant UX
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


## Engineering Assistant – verpflichtende Akzeptanzsuite für S21–S30

Die Prüfungen S21–S30 dürfen nicht nur kontrollieren, ob Chat-UI, MCP und einzelne Buttons technisch reagieren.

Sie müssen beweisen, dass hinter der Oberfläche tatsächlich ein **Engineering Assistant** arbeitet.

Die folgenden Tests sind verbindliche Subtests von S21–S30 und zählen als Mandatory Assertions.

### EA-01 – Natürlicher Create-Auftrag

Eingabe:

```text
"Lege eine ECU an, die mir die Stellgliedpositionen
im System alle 30 Sekunden abfragt."
```

Pflicht:

```text
Projektkontext lesen
Stellglieder finden
Positionsdaten finden
ECU anlegen
30-s-Funktion anlegen
Datenfluss erzeugen
Interfaces/Ports prüfen
Transport erzeugen
Routing erzeugen
Capacity/Timing prüfen
Validation ausführen
```

PASS nur bei nachweisbarer Core-Wirkung.

### EA-02 – Fehleranalyse und Korrektur als Follow-up

Voraussetzung:

Der vorherige Assistant-Auftrag oder Validation Run hat einen eindeutigen Fehler/Finding erzeugt.

Eingabe:

```text
"Dann weißt du ja, was du zu tun hast:
Fehleranalyse und Korrektur."
```

Pflicht:

```text
vorherigen Kontext auflösen
Finding/Evidence laden
Root Cause bestimmen
Korrektur planen
Korrektur ausführen, wenn autorisiert
Validation erneut ausführen
Resultat liefern
```

Ein generischer Chat-Fehler ist:

```text
FAIL
```

### EA-03 – Kontextfortsetzung

Nach erfolgreicher Anlage einer zyklischen Abfrage:

```text
"Mach das auch für die anderen Aktoren."
```

Pflicht:

```text
same engineering context
→ remaining actuators determine
→ no duplicate existing configuration
→ extend model
→ validate
```

### EA-04 – Bestehende Technologie ändern

```text
"Ändere das LIN-Netz auf 19,2 kbit/s
und prüfe alle abhängigen Berechnungen."
```

Pflicht:

```text
TechnologyProfile prüfen
bitrate setzen
abhängige Ergebnisse STALE
Capacity neu
Timing neu
Preflight neu
Simulation/Trace Baselines stale
```

### EA-05 – Verbindung erzeugen

```text
"Verbinde Function A mit Function B
und prüfe anschließend die Kommunikation."
```

Pflicht:

```text
Model Inspection
→ Hardware Mapping
→ Interface/Port
→ Network
→ Transport
→ Routing
→ Capacity
→ Timing
→ Validation
```

### EA-06 – Diagnose / Root Cause

```text
"Warum kommt PressureCommand zu spät an?"
```

Pflicht:

```text
E2E / Trace
→ Timing Breakdown
→ Queue / Arbitration / Gateway
→ Evidence
→ Root Cause
```

### EA-07 – Simulation aus natürlicher Sprache

```text
"Simuliere den Ausfall dieses Gateways
und zeige mir, welche Kommunikation betroffen ist."
```

Pflicht:

```text
selected gateway resolve
→ fault scenario
→ simulation
→ trace
→ affected routes
→ findings
```

### EA-08 – Modellqualitätsauftrag

```text
"Finde alle Signale ohne Empfänger
und korrigiere die eindeutigen Fälle."
```

Pflicht:

```text
scan model
→ findings
→ deterministic fixes
→ ambiguous cases remain review-required
→ validation
```

### EA-09 – Hardware Capability Auftrag

```text
"Füge dem Controller einen zweiten CAN-FD-Kanal hinzu."
```

Pflicht:

```text
hardware capability inspect
controller/channel limit inspect
free channel inspect
physical interface/port create if valid
no impossible channel invention
validation
```

Wenn Hardware dies nicht unterstützt:

```text
BLOCKED_WITH_EXPLICIT_CAUSE
```

statt generischem Fehler.

### EA-10 – E2E-Auftrag

```text
"Zeige mir den Weg von Function A zu Function B
und wie lange die Botschaft benötigt."
```

Pflicht:

```text
resolve transaction
route
hops
technology transitions
E2E timing
receiver action if available
sequence visualization
```

### EA-11 – Unvollständige, aber verständliche Engineering-Eingabe

```text
"Lege eine Diagnoseabfrage für alle Stellglieder an."
```

Assistant muss vorhandenes Modell prüfen.

Wenn Zyklus/Trigger fachlich nicht vorgegeben und wirklich relevant:

```text
gezielte Engineering-Frage
```

Nicht:

```text
generic error
```

### EA-12 – Tool-/Backend-Fehler wird fachlich behandelt

Während eines gültigen Auftrags schlägt ein Tool transient oder aufgrund einer erfüllbaren Vorbedingung fehl.

Erwartung:

```text
failure classify
→ retry if transient
or
→ precondition repair
→ resume workload
```

Nur ein echter nicht lösbarer Blocker darf als `BLOCKED_WITH_EXPLICIT_CAUSE` enden.

### Mandatory Assistant Assertions

Für **jeden** EA-Test:

```text
goal_understood = true
model_inspected = true
generic_chat_error = false
tool_only_completion = false
core_effect_matches_goal = true   # bei schreibendem Auftrag
validation_executed = true         # soweit fachlich anwendbar
completion_correct = true
evidence_complete = true
```

### Assistant Fail Conditions

Sofortiger Testfehler:

```text
ASSISTANT_IS_CHAT_ONLY
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


## S21 – Fähigkeiten/Wizards: Einstieg „Architektur erstellen“
**Schwierigkeit:** Integration  
**Prüfbereich:** Engineering Assistant + Wizard + Browser + Skill Routing

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

## S26 – Engineering Assistant: Single-/Multi-Choice und Workload Resume
**Schwierigkeit:** Integration  
**Prüfbereich:** Engineering Assistant UX / Structured Decisions

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

## S30 – Vollständiger Engineering-Assistant/MCP/Browser-Systemtest
**Schwierigkeit:** Integration / System E2E  
**Prüfbereich:** gesamter Agentenpfad

### Ziel

Ein einzelner Test prüft die vollständige Kette:

```text
Wizard
→ Engineering Assistant
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
| Technology Registry | Canonical IDs, Aliases, Capability-/Verification-Status |
| Technology Models | Parameter, PHY, Capacity, Timing, Simulation, Trace Decode |
| Product Reality | Project Objects/Relations, Persistence, Runtime Build |

---

# 21. Zusätzliche Engineering-Assistant-Abnahmekriterien

Der Engineering Assistant gilt in diesen Prüfungen nur als erfolgreich, wenn:

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


## Zusätzliche Engineering-Assistant-Abnahmekriterien

Der Engineering Assistant gilt nur als erfolgreich, wenn er **Engineering Work** erzeugt und nicht nur Text.

Pflicht für natürliche Befehle:

```text
Natural Language
→ Goal
→ Context
→ Plan
→ Skill/MCP
→ Core Result
→ Validation
→ Engineering Result
```

Jede verständliche Eingabe aus den NIS-Fachbereichen muss einen der folgenden fachlichen Endzustände erreichen:

```text
COMPLETED
WAITING_FOR_ENGINEERING_DECISION
BLOCKED_WITH_EXPLICIT_CAUSE
NOT_SUPPORTED_WITH_CAPABILITY_GAP
```

Nicht zulässig als normale Antwort auf einen gültigen NIS-Auftrag:

```text
ERROR
UNKNOWN_COMMAND
OPEN_EDITOR_YOURSELF
I_CANNOT_DO_THIS
```

wenn die fachliche Capability registriert und verfügbar ist.

Der Tool Checker muss hierzu **UI, Assistant State, Tool Trajectory und Core State gemeinsam prüfen**.

### Generische Assistant Capability Matrix

| Bereich | Beispiel-Nutzereingabe | Erwartete Wirkung |
|---|---|---|
| Hardware | `Lege eine ECU an ...` | HardwareNode + notwendige Capabilities/Relations |
| Function | `Lege eine Funktion zur Abfrage ... an` | Function + Mapping + Interfaces |
| Periodik | `alle 30 Sekunden` | Cycle/Trigger = 30 s / CYCLIC |
| Network | `Verbinde A mit B` | Connection + Route + Validation |
| Technology | `LIN auf 19,2 kbit/s` | validierter Parameter + Recalculation |
| Signals | `Finde Signale ohne Empfänger` | Analyse + Findings + eindeutige Fixes |
| Validation | `Behebe die Fehler` | Root Cause + Repair + Revalidation |
| Simulation | `Simuliere Ausfall ...` | Scenario + Simulation + Result |
| Trace | `Warum kam X zu spät?` | Trace/E2E Root Cause |
| Follow-up | `Mach das auch für ...` | aktiven Kontext fortsetzen |
| E2E | `Wie lange von A nach B?` | Route/Hops/Timing/Sequence |
| Finding | `Korrigiere das Problem` | Finding → Repair Workflow |

### Kritische Produktregel

Wenn eine Eingabe wie:

```text
"Lege eine ECU an, die mir die Stellgliedpositionen
im System alle 30 Sekunden abfragt."
```

zu einem generischen Fehler führt, ist dies kein Bedienfehler des Nutzers.

Es ist mindestens:

```text
ENGINEERING_ASSISTANT_EXECUTION_DEFECT
```

und bei Kernfunktionalität:

```text
P1 / CRITICAL WORKFLOW FAILURE
```

### Regression nach Assistant-Reparatur

Eine Reparatur des Engineering Assistant muss mindestens erneut prüfen:

```text
EA-01 Create
EA-02 Follow-up Repair
EA-03 Context Continuation
EA-05 Connect
EA-06 Root Cause
EA-07 Simulation
EA-10 E2E
```

im **nächsten vollständigen Run**.

Während der laufenden Runde wird nach der Drei-Runden-Regel nicht repariert.


# 22. Gesamtumfang nach Ergänzung

Der Testsatz enthält nun:

```text
40 fachliche A/B-Szenarien
+
10 Engineering-Assistant-/MCP-/Skill-/UI-Integrationsprüfungen
=
50 Prüfungen
```

Die zusätzlichen S21–S30 prüfen insbesondere die Ebene, die in den ersten 40 Szenarien nur implizit enthalten war:

```text
Engineering Assistant UX
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


# 24.1 Testkampagnen-Governance für alle 60 Prüfungen

Die 60 Tests werden pro Full Run **als unveränderliche Gesamtheit** ausgeführt.

```text
RUN 1 = S01-A ... S20-B + S21 ... S40
RUN 2 = S01-A ... S20-B + S21 ... S40
RUN 3 = S01-A ... S20-B + S21 ... S40
```

Kein Full Run darf nur aus den zuvor fehlgeschlagenen Fällen bestehen.

Der Engineering Assistant, MCP, Wizards und Trace werden in jedem Full Run im selben Build-Zustand bewertet.

## Befundbehandlung

Während eines Full Runs:

```text
detect
→ document
→ continue independent tests
```

Nicht:

```text
detect
→ repair
```

Nach Abschluss des Full Runs:

```text
freeze findings
→ repair phase
```

## Assistant Findings

Engineering-Assistant-Fehler werden ebenfalls erst nach dem vollständigen Run repariert.

Beispiel:

```text
EA-01 fails in test 12
```

Dann:

```text
Finding dokumentieren
→ restliche 60-Test-Kampagne mit unverändertem Build fortsetzen
→ Repair nach Run-Ende
```

Damit bleibt sichtbar, welche weiteren Fehler aus demselben Assistant-Defekt entstehen.

## Root-Cause Clustering

Folgefehler eines defekten Engineering Assistant nicht künstlich als viele unabhängige Root Causes werten.

Beispiel:

```text
Assistant cannot execute create command
├── ECU not created
├── route absent
├── simulation blocked
└── trace absent
```

Master Finding:

```text
ENGINEERING_ASSISTANT_EXECUTION_DEFECT
```

Dependent Findings referenzieren diese Root Cause.

## Maximal drei vollständige Runs

```text
Run 1
→ Repair 1

Run 2
→ Repair 2

Run 3
→ Final Acceptance
```

Optional kann nach Run 3 noch eine Reparatur erfolgen, aber ohne automatischen vierten Full Run.

Dann:

```text
status = REPAIR_APPLIED_AWAITING_NEW_CAMPAIGN
```

---


# 25. Gesamtumfang

```text
40 fachliche A/B-Szenarien
+
10 Engineering-Assistant-/MCP-/Skill-/UI-Prüfungen
+
10 Trace-Analyse-Prüfungen
=
60 Prüfungen
```

Vollständige Prüfkette pro Full Run:

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

---

# 26. Verbindlicher Tool-Checker-Ausführungsbefehl

```text
Execute the complete 60-test suite as a three-run campaign.

RULE 1:
During a full run, execute every test case before any product repair starts.

RULE 2:
Document every failure, blocker and dependent failure.
Do not modify product code, Assistant behavior, MCP wiring or model logic during the run.

RULE 3:
After all 60 tests have completed, freeze the finding ledger.
Only then start the repair phase.

RULE 4:
Complete the entire repair phase before starting the next full run.

RULE 5:
The next run must execute all 60 tests again, not only previously failed tests.

RULE 6:
Repeat this process for a maximum of three full runs.

RUN 1
→ FINDINGS
→ REPAIR 1
→ RUN 2
→ FINDINGS
→ REPAIR 2
→ RUN 3
→ FINAL QUALITY GATE

If Run 3 still contains defects:
- document them,
- optionally apply Repair Phase 3,
- do not automatically start Run 4,
- set status to REPAIR_APPLIED_AWAITING_NEW_CAMPAIGN if repairs were applied.

The Engineering Assistant is not a chatbot.
The chat is only its user interface.

For every valid engineering command, the Engineering Assistant must:
- understand the goal,
- inspect the current model,
- resolve context,
- ask only necessary engineering decisions,
- select Skills/MCP capabilities,
- execute the engineering work,
- update the Core model when required,
- calculate dependent artifacts,
- validate the result,
- continue follow-up context,
- return an engineering result.

Commands such as:

"Lege eine ECU an, die mir die Stellgliedpositionen
im System alle 30 Sekunden abfragt."

or:

"Dann weißt du ja, was du zu tun hast:
Fehleranalyse und Korrektur."

must not terminate in a generic chat error.

They must produce:
COMPLETED,
WAITING_FOR_ENGINEERING_DECISION,
BLOCKED_WITH_EXPLICIT_CAUSE,
or NOT_SUPPORTED_WITH_CAPABILITY_GAP.

A generic error for a supported, understandable NIS engineering command is a product defect and must be recorded as:
ENGINEERING_ASSISTANT_EXECUTION_DEFECT.

Apply the same Assistant interaction model across:
Project,
Hardware,
Functions,
Signals/DataObjects,
Interfaces/Ports,
Networks,
Routing,
Capacity,
Timing,
Validation/Preflight,
Simulation,
Trace Analysis,
E2E Timing,
Findings and Repair.

Additional mandatory technology/product rules:

- Never use Automotive as a neutral fallback.
- Never substitute missing rates with hidden defaults.
- Preserve canonical technology identity end-to-end.
- Resolve aliases only at registry ingress.
- Do not claim deterministic Capacity/Timing support without a valid technology-specific or explicitly composed stack model.
- If a model or required parameter is missing, report UNVERIFIED instead of fabricating a numeric result.
- Enumerate every registered technology and report Capability/Verification coverage.
- Fully materialize each scenario project in the running product; a project tile alone is a FAIL.
- Preserve explicit gaps in the model.
- Mark blockers in the existing affected views; do not invent a new main navigation button just for errors.
- Findings must be detailed enough to create a RepairWorkPackage.
- Product-flow verification must run against the actual running build, not only a repaired checkout.
```

# 27. Definition of Done – angepasste Testlogik

Die Teststrategie ist erst korrekt umgesetzt, wenn:

1. alle 60 Tests pro Full Run ausgeführt werden.
2. während eines Full Runs keine Produktreparatur erfolgt.
3. alle Fehler des Runs zuerst vollständig dokumentiert werden.
4. Findings nach Run-Ende eingefroren werden.
5. Reparatur erst danach startet.
6. der nächste Full Run erst nach abgeschlossener Repair Phase startet.
7. jeder neue Full Run wieder alle 60 Tests ausführt.
8. maximal drei vollständige Runs automatisch ausgeführt werden.
9. Regressionen zwischen Run 1, Run 2 und Run 3 explizit erkannt werden.
10. der Engineering Assistant als Engineering-Orchestrator geprüft wird.
11. der Engineering Assistant nicht nur als Chat-UI geprüft wird.
12. natürliche Create-Aufträge zu Core-Ergebnissen führen.
13. periodische Angaben wie `alle 30 Sekunden` korrekt modelliert werden.
14. verkürzte Follow-ups den bestehenden Kontext fortsetzen.
15. `Fehleranalyse und Korrektur` einen echten Repair-Workflow auslöst.
16. schreibende Assistant-Aufträge einen überprüfbaren Model Diff erzeugen.
17. Assistant-Aufträge abhängige Routing/Capacity/Timing/Validation-Schritte abschließen.
18. generische Fehler bei unterstützten Engineering-Kommandos als Produktdefekt gelten.
19. Assistant-Fehler erst nach Abschluss des Full Runs repariert werden.
20. die Reparatur im nächsten vollständigen Run regressionsgeprüft wird.
21. jede registrierte Technologie eine eindeutige Canonical ID besitzt.
22. Alias-Normalisierung zentral erfolgt.
23. Technologieidentität über alle Engines erhalten bleibt.
24. Automotive nicht als neutraler Fallback verwendet wird.
25. fehlende Raten nicht durch versteckte Ersatzwerte ersetzt werden.
26. Capacity ohne gültiges Modell `UNVERIFIED` meldet.
27. Timing ohne gültiges Modell `UNVERIFIED` meldet.
28. Direct-Signal-Technologien `NOT_APPLICABLE` statt künstlicher Buslast verwenden.
29. Technology Capability Coverage vollständig berichtet wird.
30. als vollständig beworbene Technologien keinen Capability-False-Positive besitzen.
31. alle S01-A…S20-B-Projekte im laufenden Produkt vollständig materialisiert werden.
32. reine Projekt-Kacheln als `PROJECT_SHELL_ONLY` fehlschlagen.
33. gespeicherte Projekte nach Reload vollständig erhalten bleiben.
34. fehlende Daten als Lücken sichtbar bleiben.
35. Blocker am betroffenen Quellobjekt in bestehenden Views sichtbar sind.
36. keine neue Hauptansicht nur für Blocker erforderlich ist.
37. Findings erwartetes und beobachtetes Verhalten enthalten.
38. Findings First Failing Layer und Evidence enthalten.
39. Findings direkt in RepairWorkPackages überführbar sind.
40. Folgefehler auf Master Root Causes referenzieren.
41. Produktfluss gegen den tatsächlich laufenden Build geprüft wird.
42. Checkout-only-Reparaturen nicht als Produkt-PASS gelten.
43. `Hidden Fallback Count = 0` erreicht wird.
44. `Technology Identity Loss Count = 0` erreicht wird.
45. `Project Shell Only Count = 0` erreicht wird.
46. Mandatory In-Place Blocker Marker Coverage 100 % erreicht.
47. Mandatory Repair-Ready Finding Coverage 100 % erreicht.

---

# 28. Leitregel

```text
FULL RUN FIRST
→ DOCUMENT EVERYTHING
→ REPAIR AFTER RUN
→ FULL RE-RUN
→ MAXIMUM THREE RUNS
```

und für den Engineering Assistant:

```text
USER INTENT
→ ENGINEERING WORK
→ VALIDATED RESULT
```

nicht:

```text
USER INTENT
→ CHAT ERROR
```

und für Technologie-/Projektqualität:

```text
REGISTERED
≠
TECHNICALLY MODELED
≠
VERIFIED
```

sowie:

```text
PROJECT TILE
≠
PRODUCTIVE ENGINEERING PROJECT
```

und:

```text
MISSING MODEL
→ UNVERIFIED
```

nicht:

```text
MISSING MODEL
→ GENERIC FALLBACK
→ FALSE PRECISION
```

