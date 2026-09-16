# S26 — PARTIAL

Run: run-5a4f4bef0e1145b78f1c1a8ca2ed6aa3

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

Evidence: 6 files
