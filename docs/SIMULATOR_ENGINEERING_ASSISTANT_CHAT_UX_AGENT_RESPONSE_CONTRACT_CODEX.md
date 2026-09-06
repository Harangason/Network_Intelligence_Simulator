# Arbeitsauftrag für Codex
## Engineering Assistant Chat UX + Agent Response Contract

## 1. Ziel

Überarbeite die bestehende Chat-Bubble / Assistant-UI des **Network Intelligence Simulator** zu einem professionellen, schlanken und kontextbezogenen **Engineering AI Assistant**.

Der Chat soll nicht wie ein einfacher Messenger oder Support-Chat wirken.

Ziel ist eine UI, die:

```text
ruhig
schlank
technisch hochwertig
kontextbezogen
interaktiv
agentisch
hilfreich
```

wirkt.

Der Chat soll Entscheidungen möglichst direkt in der Unterhaltung ermöglichen.

Wenn eine Frage mehrere mögliche Antworten besitzt, soll der Nutzer diese über interaktive Auswahlfelder direkt im Chat beantworten können.

---

# 2. Grundprinzip

Der Chat ist kein reiner Textkanal.

Er besteht aus:

```text
Text
+
Structured Agent Responses
+
Interactive Questions
+
Recommendations
+
Findings
+
Progress
+
Approvals
```

---

# 3. Zielbild

Beispiel:

```text
┌─────────────────────────────────────────┐
│  Engineering Assistant            ⋯  × │
│  Vehicle Network · Hardware Interface  │
├─────────────────────────────────────────┤
│                                         │
│  Ich habe 3 mögliche CAN-FD-           │
│  Konfigurationen gefunden.              │
│                                         │
│  Welche soll ich weiter prüfen?         │
│                                         │
│  ☐ CAN-FD A – bestehender Bus           │
│     58 % prognostizierte Last           │
│                                         │
│  ☐ CAN-FD B – zusätzlicher Kanal        │
│     31 % prognostizierte Last           │
│                                         │
│  ☐ Ethernet – alternative Architektur   │
│                                         │
│                [ Auswahl übernehmen ]   │
│                                         │
├─────────────────────────────────────────┤
│  Frag mich etwas …                 ➤    │
└─────────────────────────────────────────┘
```

---

# 4. Keine billige Messenger-Optik

Vermeide:

```text
große bunte Sprechblasen
Neonfarben
starke Glow-Effekte
zu viele Icons
Gaming-Optik
unnötig große Karten
zu viele Rahmen
```

Bevorzugen:

```text
Whitespace
gute Typographie
dezente Trennlinien
kleine Statuspunkte
eine kontrollierte Akzentfarbe
ruhige Flächen
subtile Interaktionen
```

---

# 5. Header

Der Header soll kompakt sein.

Beispiel:

```text
Engineering Assistant
Vehicle Network · Hardware Interface
```

Optional:

```text
Project 00011 · MotorControl
```

Nicht:

```text
AI CHAT AGENT ONLINE
```

---

# 6. Context Awareness

Der Chat muss den aktuellen Agent Context berücksichtigen.

Mindestens:

```text
active_project
active_view
selected_object
selected_function
selected_interface
current_workload
current_findings
```

Dadurch kann die KI kontextbezogen antworten.

Beispiel:

```text
Das ausgewählte PowertrainECU.CAN_FD_1
liegt aktuell bei 68 % prognostizierter Buslast.
```

statt:

```text
Welches Interface meinst du?
```

---

# 7. Chat Message Types

Definiere intern:

```text
ChatMessageType
```

mit mindestens:

```text
TEXT
QUESTION
MULTI_SELECT
SINGLE_SELECT
RECOMMENDATION
FINDING
PROGRESS
RESULT
APPROVAL
ERROR
```

Der Renderer entscheidet anhand des Typs, welches UI-Element dargestellt wird.

---

# 8. Structured Agent Response Contract

Der Agent darf nicht nur Freitext zurückgeben.

Definiere ein strukturiertes Antwortformat.

Beispiel:

```json
{
  "type": "question",
  "text": "Welche Daten sollen bereitgestellt werden?",
  "selection": "multi",
  "options": [
    "Object List",
    "Free Space",
    "Status",
    "Raw Image"
  ],
  "recommended": [
    "Object List",
    "Status"
  ]
}
```

---

# 9. Single-Choice

Wenn genau eine Antwort gültig ist:

```text
○ Frontbereich
○ Front + Heck
● 360° Rundumsicht    Empfohlen
○ Benutzerdefiniert
```

Technisch:

```text
selection = single
```

Keine Checkboxen für exklusive Alternativen.

---

# 10. Multi-Choice

Wenn mehrere Antworten gleichzeitig gültig sein können:

```text
☐ Objektliste
☐ Freiraum
☐ Kamerastatus
☐ Rohbild
☐ Diagnoseinformationen
```

Technisch:

```text
selection = multi
```

---

# 11. Auswahl bestätigen

Bei Multi-Select:

```text
[ Auswahl übernehmen ]
```

Bei Single-Select kann optional sofort übernommen werden oder ebenfalls explizite Bestätigung erfolgen.

Die UX muss konsistent sein.

---

# 12. Empfehlung vorauswählen

Wenn der Agent eine klare Empfehlung besitzt:

```text
○ 1280×720
● 1920×1080    Empfohlen
○ 3840×2160
```

Empfehlung muss begründbar sein.

Optional:

```text
Warum?
```

aufklappbar.

---

# 13. Keine stillen Annahmen

Wenn eine Engineering-relevante Unsicherheit existiert:

```text
Agent detects ambiguity
↓
Interactive Question
```

Nicht:

```text
Agent guesses silently
```

---

# 14. Beispiel Requirement

User:

```text
Ich brauche eine Funktion,
die mit Kameras das Umfeld meines Fahrzeuges erfasst.
```

Agent:

```text
Ich interpretiere „Umfeld“ als mögliche Rundumsicht.

Welche Abdeckung möchtest du?
```

UI:

```text
○ Frontbereich
○ Front + Heck
● 360° Rundumsicht    Empfohlen
○ Benutzerdefiniert
```

---

# 15. Mehrere Fragen kompakt bündeln

Nicht fünf einzelne Chatnachrichten erzeugen.

Beispiel:

```text
Kamera-Anforderungen

Auflösung
○ 1280×720
● 1920×1080
○ 3840×2160

Bildrate
○ 15 fps
● 30 fps
○ 60 fps

Objektklassen
☑ Fahrzeuge
☑ Fußgänger
☑ Fahrräder
☐ Tiere

[ Übernehmen ]
```

Aber maximal:

```text
2–4 Entscheidungen pro Frageblock
```

damit der Chat kein Formular wird.

---

# 16. Recommendation Message

Beispiel strukturierte Antwort:

```json
{
  "type": "recommendation",
  "title": "CAN-FD Interface 1 verwenden",
  "text": "Das Interface besitzt noch ausreichend Reserve.",
  "metrics": {
    "load_before": "58%",
    "load_after": "67%"
  },
  "actions": [
    "ACCEPT",
    "DETAILS"
  ]
}
```

UI kompakt:

```text
Empfehlung

CAN-FD Interface 1 kann die zusätzlichen
4 Messages noch aufnehmen.

58 % → 67 %

[ Übernehmen ] [ Details ]
```

---

# 17. Finding Message

Findings direkt in den Chat integrieren.

Beispiel:

```text
Ich habe einen Architekturhinweis gefunden.

⚠ Zentrales Gateway ist ein Single Point of Failure.

Das ist bei dieser Architektur nicht zwingend ein Fehler.

Was soll ich tun?

○ Maßnahme vorschlagen
○ Risiko akzeptieren
○ Später prüfen
```

---

# 18. Accepted Risk Interaction

Bei:

```text
Risiko akzeptieren
```

direkt im Chat:

```text
Begründung
[________________________________]

Review bei Architekturänderung
☑ Ja

[ Entscheidung speichern ]
```

---

# 19. Progress Message

Bei längeren Agent-Aufgaben:

```text
Analysiere Kommunikationsarchitektur …

✓ Funktionen
✓ Signale
✓ Nachrichten
● Hardware Interfaces
○ Routing
○ Validierung
```

Keine unnötig große Progressbar.

---

# 20. Progress Contract

Beispiel:

```json
{
  "type": "progress",
  "title": "Analysiere Kommunikationsarchitektur",
  "steps": [
    {"label": "Funktionen", "status": "done"},
    {"label": "Signale", "status": "done"},
    {"label": "Nachrichten", "status": "done"},
    {"label": "Hardware Interfaces", "status": "active"},
    {"label": "Routing", "status": "pending"},
    {"label": "Validierung", "status": "pending"}
  ]
}
```

---

# 21. Tool Calls nicht roh anzeigen

Nicht:

```text
Calling tool...
calculate_bus_load()
Tool succeeded
```

Besser:

```text
✓ Architektur geprüft
✓ CAN-FD-Auslastung berechnet
✓ 4 Nachrichten validiert
```

Optional:

```text
Details anzeigen
```

---

# 22. Debug Details optional

Technische Details nur auf Wunsch.

Beispiel:

```text
Details
- calculate_bus_load()
- validate_messages()
- check_interface_capacity()
```

Nicht permanent sichtbar.

---

# 23. Result Message

Nach längerer Arbeit:

```text
Architektur vorbereitet.

2 Entscheidungen benötigen noch deine Freigabe.
```

Dann:

```text
[ Entscheidungen prüfen ]
[ Details ]
```

---

# 24. Approval Message

Für Core-Write-relevante Änderungen:

```text
APPROVAL
```

mit:

```text
Summary
Affected Objects
Impact
Validation Result
Actions
```

Beispiel:

```text
4 neue Signale
2 neue Messages
1 Hardware Interface Mapping

Validierung:
✓ keine Blocking Findings

[ Freigeben ]
[ Bearbeiten ]
[ Ablehnen ]
```

---

# 25. Agent soll Fragen selbst erkennen

Der Agent muss unterscheiden:

```text
missing information
```

von:

```text
optional information
```

und:

```text
critical engineering decision
```

Nur relevante Entscheidungen aktiv erfragen.

---

# 26. InteractiveQuestion Model

Definiere:

```text
InteractiveQuestion
```

mit:

```text
id
question
description
selection_mode
options[]
recommended_options[]
required
engineering_impact
context_refs[]
status
```

---

# 27. Option Model

```text
InteractiveOption
```

mit:

```text
id
label
description
recommended
disabled
reason
metadata
```

---

# 28. Question Status

```text
OPEN
ANSWERED
SKIPPED
EXPIRED
OUTDATED
```

Wenn sich Engineering Context ändert:

```text
OUTDATED
```

setzen.

---

# 29. Chat soll Agent-artig arbeiten

Nicht nur:

```text
User asks
→ Assistant answers
```

sondern:

```text
User Goal
→ Agent Understands
→ Agent Plans
→ Agent Executes
→ Agent Detects Missing Decisions
→ Chat asks user
→ Agent continues
→ Agent validates
→ Agent presents result
```

---

# 30. Beispiel kompletter Chatflow

User:

```text
Ich brauche eine Funktion,
die mit Kameras das Umfeld meines Fahrzeuges erfasst.
```

Assistant:

```text
Ich interpretiere „Umfeld“ als mögliche Rundumsicht.

Welche Abdeckung möchtest du?
```

```text
○ Frontbereich
○ Front + Heck
● 360° Rundumsicht    Empfohlen
○ Benutzerdefiniert
```

Nach Auswahl:

```text
Für 360° ergeben sich mit dem aktuellen
Kameraprofil mindestens 4 Kameras.

Welche Ergebnisse soll die Funktion bereitstellen?
```

```text
☑ Objektliste
☑ Freiraum
☑ Kamerastatus
☐ Rohbild an weitere Steuergeräte
```

Nach Auswahl:

```text
Ich würde folgende Struktur erzeugen:

EnvironmentPerception
├── 4 × Perception Camera
├── Vision Controller
├── EnvironmentObjectList
├── Camera Status
└── Ethernet-Kommunikation

Die Rohbildübertragung benötigt deutlich mehr
Bandbreite als CAN-FD bereitstellen kann.

[ Architektur erstellen ]
[ Details ansehen ]
```

---

# 31. Quick Prompts

Wenn noch kein Chat läuft:

```text
Was möchtest du tun?
```

Chips:

```text
[ Architektur prüfen ]
[ Signals erzeugen ]
[ Trace analysieren ]
[ Finding erklären ]
```

Nicht zu viele gleichzeitig.

---

# 32. Chat Input

Eingabefeld:

```text
Frag mich etwas …
```

Optional kleine kontextbezogene Actions:

```text
＋
@
```

Nicht mit vielen permanent sichtbaren Buttons überladen.

---

# 33. Collapsed Bubble

Collapsed State:

```text
◉
```

oder bestehendes animiertes Graph-Icon (Hinweis: den aktuell vorhanden Bubble nicht ersetzen, aber vielleicht etwas stabilisieren in der animation.).

Hover:

```text
Engineering Assistant
```

---

# 34. Expanded Size

Zielbreite ungefähr:

```text
380–440 px
```

Nicht unnötig:

```text
600–800 px
```

Wenn große Tabellen/Analysen nötig sind:

```text
[ Im Workspace öffnen ]
```

---

# 35. Chat Bubble Layout

Empfohlen:

```text
Header
Context Line
Conversation
Interactive Controls
Input Bar
```

Keine zusätzliche Sidebar innerhalb der Bubble.

---

# 36. Scroll Behavior

Neue Agentantworten sollen:

```text
smoothly append
```

aber nicht aggressiv automatisch scrollen, wenn der Nutzer ältere Inhalte liest.

Bei neuer Nachricht:

```text
"Neue Antwort"
```

Indicator optional.

---

# 37. Long Content

Lange Erklärungen:

```text
summary first
details collapsible
```

Beispiel:

```text
CAN-FD ist für den Rohbildstrom ungeeignet.

[ Details ]
```

---

# 38. Tabellen vermeiden

In der Chat-Bubble keine großen Tabellen.

Kleine Vergleiche erlaubt.

Für große Tabellen:

```text
Open Workspace
```

---

# 39. Context Links

Objekte im Chat klickbar machen:

```text
PowertrainECU
CAN_FD_A
MotorControl
0x187
```

Klick:

```text
select corresponding EngineeringObject
```

oder passenden View öffnen.

---

# 40. Chat ↔ Views

Der Chat muss mit bestehenden Views kommunizieren:

```text
Hardware
Hardware Interface
Funktion
Interface
Nachrichten
Signale
Routing
Simulation
Trace
```

---

# 41. View Navigation Action

Agent Response kann Actions enthalten:

```text
OPEN_OBJECT
OPEN_VIEW
FOCUS_OBJECT
OPEN_ANALYSIS
OPEN_TRACE
```

---

# 42. Action Contract

Beispiel:

```json
{
  "type": "result",
  "text": "Das Interface ist zu 78 % ausgelastet.",
  "actions": [
    {
      "type": "OPEN_VIEW",
      "view": "hardware-interface",
      "object_ref": "if-canfd-01",
      "label": "Interface öffnen"
    }
  ]
}
```

---

# 43. Styling Tokens

Keine hartcodierten Farben, wenn Theme Tokens existieren.

Verwende:

```text
surface
surface-muted
border-subtle
text-primary
text-secondary
accent
warning
error
success
```

---

# 44. Typography

Bevorzugen:

```text
13–15 px body
compact headings
clear hierarchy
monospace only for IDs / technical values
```

---

# 45. Icons

Icons nur für:

```text
status
warning
success
expand
navigation
```

Nicht jede Zeile mit Icon versehen.

---

# 46. Animation

Subtil:

```text
fade
height transition
small activity pulse
```

Keine:

```text
glow
bounce
large motion
```

---

# 47. Assistant Graph Bubble

Das bestehende Graph-Icon darf als Assistant-Symbol bleiben.

Es soll:

```text
subtle node movement
small connection activity
state-aware animation
```

zeigen.

Nicht überladen.

---

# 48. Agent States im Icon

Optional:

```text
IDLE
LISTENING
THINKING
RESPONDING
WARNING
ERROR
```

über subtile Animation statt starke Farbwechsel darstellen.

---

# 49. Accessibility

Alle interaktiven Controls brauchen:

```text
keyboard focus
aria labels
clear selected state
screen-reader labels
```

Checkboxen und Single-Choice müssen vollständig per Tastatur bedienbar sein.

---

# 50. Mobile / Small Width

Bei kleiner Breite:

```text
full-height drawer
```

oder fast vollflächige Chatansicht.

Desktop:

```text
compact floating panel
```

---

# 51. Agent Response Schema

Empfohlene Basis:

```text
AgentResponse
├── id
├── type
├── text
├── title
├── context_refs[]
├── options[]
├── actions[]
├── findings[]
├── progress[]
├── recommendation
├── approval
├── metadata
└── created_at
```

---

# 52. Kein UI-Markup aus dem LLM

LLM darf nicht direkt:

```text
HTML
React JSX
CSS
```

für Chatkomponenten erzeugen.

LLM erzeugt:

```text
structured AgentResponse
```

Frontend rendert deterministisch.

---

# 53. Response Validation

Alle Agent Responses gegen Schema validieren.

Wenn ungültig:

```text
fallback to TEXT
```

und Finding / Log erzeugen.

---

# 54. Suggested Agent Types

Mindestens:

```text
TEXT
QUESTION
MULTI_SELECT
SINGLE_SELECT
RECOMMENDATION
FINDING
PROGRESS
RESULT
APPROVAL
ERROR
```

---

# 55. Conversation State

Speichere:

```text
current_question
answered_questions
active_proposal
active_workload
pending_approvals
selected_context
```

---

# 56. Antworten als Agent Input

Checkbox-/Single-Choice-Antworten müssen als strukturierte Agent Inputs zurückgegeben werden.

Beispiel:

```json
{
  "question_id": "q-123",
  "selected_options": [
    "OBJECT_LIST",
    "CAMERA_STATUS"
  ]
}
```

Nicht als synthetischer Freitext wie:

```text
"Der Nutzer hat Object List und Status gewählt."
```

---

# 57. Agent setzt danach fort

Nach Antwort:

```text
Question Answered
→ Agent Context updated
→ Workload resumes
```

Kein neuer separater Workflow.

---

# 58. Approval Separation

Normale Auswahl:

```text
Question Answer
```

Engineering-relevante Freigabe:

```text
Approval
```

Nicht verwechseln.

---

# 59. Findings

Finding Messages sollen mindestens darstellen:

```text
title
severity
description
affected object
decision status
actions
```

---

# 60. Error UX

Fehler nicht als rohe Exception anzeigen.

Beispiel:

```text
Die Analyse konnte nicht abgeschlossen werden.

Grund:
Routing-Daten fehlen für 2 Messages.

[ Details ]
[ Erneut prüfen ]
```

---

# 61. Retry

Agent kann anbieten:

```text
[ Erneut versuchen ]
```

aber nicht automatisch endlos retryen.

---

# 62. Performance

Chat muss schlank bleiben.

Vermeiden:

```text
full project state
large traces
large tables
thousands of messages rendered
```

Use:

```text
windowed conversation
bounded message history
lazy details
```

---

# 63. Chat History

Nur notwendige UI-Historie im Browser halten.

Langfristiger Conversation Context über Backend / Agent Context verwalten.

---

# 64. Docs-First

Bei simulatorbezogenen Chat-/Agent-Änderungen zuerst bestehende Dokumentation unter:

```text
I:\PycharmProjects\My_first_Network_Simulator\docs
```

durchsuchen.

Bestehende Chat-/Agent-Architektur wiederverwenden.

---

# 65. Tests

Mindestens:

```text
TEXT rendering
single-select question
multi-select question
recommended option
question submission
agent resumes after answer
recommendation rendering
finding rendering
progress rendering
approval rendering
error rendering
view navigation action
context update
schema validation
fallback to text
keyboard navigation
```

---

# 66. E2E Test

Beispiel:

```text
User requirement
→ Agent detects ambiguity
→ SINGLE_SELECT
→ User selects
→ Agent continues
→ MULTI_SELECT
→ User selects
→ Agent generates proposal
→ Recommendation
→ Approval
→ Core Write
```

vollständig testen.

---

# 67. UX Regression

Bestehende:

```text
open chat
close chat
send message
receive response
scroll
resize
theme
```

dürfen nicht brechen.

---

# 68. Definition of Done

Die Aufgabe gilt erst als abgeschlossen, wenn:

1. Chat deutlich schlanker und professioneller wirkt.
2. große Messenger-Bubbles reduziert sind.
3. `AgentResponse` strukturiert ist.
4. TEXT, QUESTION, MULTI_SELECT, SINGLE_SELECT, RECOMMENDATION, FINDING, PROGRESS, RESULT, APPROVAL und ERROR unterstützt werden.
5. Multi-Select über Checkboxen im Chat funktioniert.
6. Single-Select exklusive Optionen korrekt behandelt.
7. Empfehlungen vorausgewählt bzw. markiert werden können.
8. Engineering-relevante Unsicherheiten aktiv als Frage dargestellt werden.
9. Antworten strukturiert an den Agent zurückgehen.
10. Agent Workload nach Beantwortung fortgesetzt wird.
11. Tool Calls nicht roh dargestellt werden.
12. Progress kompakt dargestellt wird.
13. Findings interaktiv behandelbar sind.
14. Accepted-Risk-Entscheidungen im Chat möglich sind.
15. Approval klar von normalen Fragen getrennt ist.
16. Context Awareness sichtbar funktioniert.
17. Chat mit Engineering Views navigieren kann.
18. große Analysen in Workspace ausgelagert werden können.
19. LLM kein UI-Markup erzeugt.
20. Response Schema validiert wird.
21. Fallback bei ungültiger Response funktioniert.
22. Keyboard Accessibility vorhanden ist.
23. Chat History begrenzt und performant bleibt.
24. Theme Tokens verwendet werden.
25. Unit-, UI- und E2E-Tests erfolgreich sind.
26. Dokumentation dem As-Built-Stand entspricht.

---

# Zentrale Leitregel

```text
The chat should not behave like a messenger.

It should behave like an Engineering AI Copilot.

Ask only when needed.

Offer structured choices.

Explain recommendations.

Show progress subtly.

Keep engineering approvals explicit.

Keep the UI calm and compact.
```

Kurz:

```text
UNDERSTAND
→ ASK
→ SELECT
→ CONTINUE
→ ANALYZE
→ RECOMMEND
→ APPROVE
→ APPLY
```
