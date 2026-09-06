# Daueranweisung – Network Intelligence Simulator
## Dokumentation zuerst durchsuchen

## 1. Geltungsbereich

Diese Anweisung gilt für **alle Aufgaben, Fragen, Analysen, Architekturentscheidungen und Implementierungen** zum Projekt:

```text
I:\PycharmProjects\My_first_Network_Simulator
```

Verbindliche Dokumentationsquelle:

```text
I:\PycharmProjects\My_first_Network_Simulator\docs
```

---

## 2. Zentrale Pflichtregel

Bei **jeder simulatorbezogenen Aufgabe** muss zuerst das gesamte Verzeichnis

```text
I:\PycharmProjects\My_first_Network_Simulator\docs
```

rekursiv nach relevanter bestehender Dokumentation durchsucht werden.

Erst danach darf eine fachliche Antwort, Architekturentscheidung, Änderungsplanung oder Implementierung erfolgen.

```text
SIMULATOR TASK
→ SEARCH docs/
→ READ relevant documentation
→ COMPARE with current request
→ INSPECT code if necessary
→ ANSWER / PLAN / IMPLEMENT
```

---

## 3. `docs/` ist die primäre projektspezifische Wissensbasis

Vor jeder neuen Lösung prüfen:

```text
Ist das Thema bereits dokumentiert?
Existiert bereits eine Architekturentscheidung?
Existiert bereits ein Core-Modell?
Existiert bereits ein Generator?
Existiert bereits ein Validator?
Existiert bereits eine Registry?
Existiert bereits ein API-Vertrag?
Existiert bereits ein Workflow?
Existiert bereits eine Migration?
Existiert bereits eine Definition of Done?
Existiert bereits eine ältere Codex-Anweisung?
```

Bestehende Logik darf nicht unnötig parallel neu aufgebaut werden.

---

## 4. Rekursive Suche

Nicht nur das Root-Verzeichnis durchsuchen.

Alle Unterordner unter `docs/` automatisch berücksichtigen, auch künftig neu angelegte.

Beispiele:

```text
docs/
├── architecture/
├── simulation/
├── communication/
├── project_wizard/
├── model_views/
├── device_classification/
├── ai_training/
├── performance/
├── implementation_audit/
└── ...
```

---

## 5. Relevante Dateitypen

Primär durchsuchen:

```text
*.md
*.txt
*.yaml
*.yml
*.json
```

Wenn Dokumente auf weitere relevante Dateien verweisen, diese ebenfalls berücksichtigen.

---

## 6. Suchstrategie

Zuerst gezielt nach Begriffen aus der Nutzeranforderung suchen.

Beispiele:

```text
Hardware Interface
Interface
Message Packing
CAN-FD
Signal Emulation
Gateway
Device Class
Requirement Expansion
Simulation Engine
Trace
Random Forest
Gradient Boosting
```

Danach die relevantesten Dokumente ausreichend tief lesen.

Nicht nur das erste Suchergebnis verwenden.

---

## 7. Mehrere Dokumente zusammenführen

Wenn mehrere Dokumente dasselbe Thema behandeln:

```text
SEARCH
→ IDENTIFY
→ COMPARE
→ MERGE UNDERSTANDING
```

Ältere und neuere Aussagen vergleichen.

---

## 8. Widersprüche erkennen

Wenn zwei Dokumente unterschiedliche Architekturregeln definieren:

```text
CONFLICT
```

explizit erkennen und dokumentieren.

Nicht still selbst eine Variante wählen.

Beispiel:

```text
Dokument A:
Interface = logical

Dokument B:
Interface = hardware port
```

Dann muss geprüft werden, welche Regel aktuell freigegeben bzw. im As-Built umgesetzt ist.

---

## 9. Aktualität berücksichtigen

Bei mehreren Versionen bevorzugen:

```text
aktuelle As-Built-Dokumentation
aktuelle freigegebene Architektur
aktuelle Implementierungsanweisung
```

Alte Planungsstände nicht automatisch als aktuellen Soll-Stand behandeln.

---

## 10. Dokumentiert ist nicht automatisch implementiert

Wenn gefragt wird:

```text
Ist X umgesetzt?
```

muss zusätzlich der reale Code geprüft werden:

```text
docs
→ code
→ call path
→ tests
→ runtime evidence
```

Nicht:

```text
Dokument sagt IMPLEMENTED
→ deshalb sicher umgesetzt
```

---

## 11. Dokumentations-/Codeabweichung

Wenn Dokumentation und Code widersprechen:

```text
IMPLEMENTATION GAP
```

melden.

Beispiel:

```text
Docs:
Message Packing implemented

Code:
1 Message → 1 Interface
```

Dann nicht die Dokumentation wiederholen, sondern die reale Abweichung benennen.

---

## 12. Keine stillen Annahmen

Wenn die Dokumentation eine Information nicht enthält, klar unterscheiden:

```text
DOCUMENTED
IMPLEMENTED
PROPOSED
INFERRED
UNKNOWN
```

Nicht allgemeines Wissen als bestehende Simulatorlogik ausgeben.

---

## 13. Implementierungsanweisungen

Bevor eine neue Codex-Anweisung für den Simulator erstellt wird:

```text
1. docs durchsuchen
2. verwandte Dokumente identifizieren
3. vorhandene Architektur übernehmen
4. bestehende Services/Modelle/Registries wiederverwenden
5. keine parallele Logik erzeugen
6. nur fehlende oder fehlerhafte Teile ergänzen
7. bestehende Definition of Done berücksichtigen
```

---

## 14. Architekturänderungen

Vor jeder größeren Änderung prüfen:

```text
Current Architecture
Current Code
Dependencies
Affected Models
Affected Services
Affected Views
Affected APIs
Affected Generators
Affected Validators
Affected Tests
Affected Documentation
```

---

## 15. Python-First und Canonical Core

Wenn in der aktuellen Simulator-Dokumentation weiterhin gültig, insbesondere folgende Grundsätze respektieren:

```text
Python-first
Canonical Core
One Logic → Many Consumers
No duplicate Engineering Truth
AI Proposal → Validation → Human Review
No direct AI database write
No premature completion
```

---

## 16. Dokumentation zuerst, Code danach

Bei technischen Aufgaben:

```text
docs/
↓
understand architecture
↓
inspect code
↓
inspect call path
↓
run tests / runtime verification
↓
propose or implement
```

---

## 17. Nach Änderungen Dokumentation aktualisieren

Nach freigegebener Umsetzung:

```text
Code
→ Tests
→ Verification
→ As-Built Documentation
```

Die Dokumentation unter

```text
I:\PycharmProjects\My_first_Network_Simulator\docs
```

muss den tatsächlichen neuen Stand widerspiegeln.

---

## 18. Keine unnötigen neuen Dokumentationsorte

Neue Simulator-Dokumentation bevorzugt unter:

```text
I:\PycharmProjects\My_first_Network_Simulator\docs
```

anlegen.

Keine parallelen Dokumentationsordner erzeugen, wenn `docs/` geeignet ist.

---

## 19. Technische Nichterreichbarkeit

Wenn die ausführende Umgebung keinen Zugriff auf

```text
I:\PycharmProjects\My_first_Network_Simulator\docs
```

hat, darf niemals behauptet werden:

```text
Ich habe die Dokumentation durchsucht.
```

Stattdessen klar melden:

```text
Der lokale Simulator-Dokumentationspfad ist in dieser Umgebung nicht erreichbar.
```

Erst nach tatsächlichem Zugriff darf daraus gearbeitet werden.

---

## 20. Simulator-Erkennung

Diese Dauerregel gilt immer, wenn der Kontext eindeutig auf den Simulator verweist, z. B.:

```text
Simulator
Network Simulator
Network Intelligence Simulator
My_first_Network_Simulator
Communication Simulator
CAN Simulator
Projekt-Wizard des Simulators
Model View des Simulators
Trace Analyse des Simulators
```

---

## 21. Projekttrennung

Diese Daueranweisung gilt nur für:

```text
My_first_Network_Simulator
```

Nicht automatisch für:

```text
EIP
JUREVIX
Solar-System
andere Projekte
```

Andere Projekte verwenden ihre jeweilige eigene Dokumentationsbasis.

---

## 22. Prioritätsregel

Für simulatorbezogene Aufgaben:

```text
1. aktuelle lokale Simulator-Dokumentation
2. tatsächlicher Simulator-Code
3. Tests und Runtime-Evidence
4. aktuelle Nutzeranforderung
5. allgemeines Modellwissen
6. externe Quellen
```

Allgemeines Wissen darf die projektspezifische Architektur nicht still überschreiben.

---

## 23. Abschluss-Check

Vor Abschluss einer größeren Simulatorantwort oder Implementierungsanweisung intern prüfen:

```text
Did I search the simulator docs?
Did I find related existing architecture?
Did I compare multiple relevant documents?
Did I inspect code where implementation status matters?
Did I avoid duplicating existing logic?
Did I distinguish documented vs implemented?
Did I identify conflicts?
Did I preserve the Canonical Model?
Did I use the correct docs location?
```

---

# Zentrale Leitregel

```text
FOR EVERY SIMULATOR TASK:

SEARCH THE DOCUMENTATION FIRST.

UNDERSTAND THE EXISTING DESIGN.

THEN INSPECT THE CODE.

THEN PROPOSE OR IMPLEMENT.
```

Kurz:

```text
SIMULATOR
→ DOCS FIRST
→ CODE SECOND
→ VERIFY
→ CHANGE
→ TEST
→ UPDATE DOCS
```

Verbindlicher Pfad:

```text
I:\PycharmProjects\My_first_Network_Simulator\docs
```
