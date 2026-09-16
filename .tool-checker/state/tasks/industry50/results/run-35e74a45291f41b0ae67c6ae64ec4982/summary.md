# S30 — FAILED

Run: run-35e74a45291f41b0ae67c6ae64ec4982

- TC_OBSERVED_CONTRACT_DEVIATION
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Erwartete Ausführung:
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
- completion_criteria:MCP-Vertragsprüfung:
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
- completion_criteria:Browser Skill:
Browser prüft reale:

```text
Clicks
Choices
Progress
Views
Result
```
- completion_criteria:Progress:
Tool Checker zeigt nur deterministischen Fortschritt:

```text
0–99 %
```

100 % erst bei erfolgreicher Completion.

Für die Fortschrittsanzeige:

```text
llm_calls_progress = 0
```
- completion_criteria:Audit:
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
- completion_criteria:PASS:
Nur wenn die gesamte Kette technisch und fachlich geschlossen ist.

---
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED

Evidence: 5 files
