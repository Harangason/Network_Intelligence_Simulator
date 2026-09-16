# S26 — PARTIAL

Run: run-e3103d2c42f04f63b91eaf2586db17b7

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Erwartung:
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
- completion_criteria:Browser-Prüfung:
Browser Skill:

```text
select option
click confirm
```
- completion_criteria:State-Prüfung:
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
- completion_criteria:MCP-Prüfung:
Nach der Auswahl müssen die zuvor geplanten MCP-Schritte fortgesetzt werden.
- completion_criteria:PASS:
Frage → strukturierte Antwort → gleicher Workload → Ausführung → Completion.

---
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED
- BROWSER_SCREENSHOT_MISSING

Evidence: 9 files
