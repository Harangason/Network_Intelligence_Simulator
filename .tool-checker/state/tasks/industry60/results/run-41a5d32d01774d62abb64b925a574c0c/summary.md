# S28 — FAILED

Run: run-41a5d32d01774d62abb64b925a574c0c

- F09
- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Browser:
Klick:

```text
Trace analysieren
```
- completion_criteria:Testgrundlage:
Simulation enthält:

```text
Gateway Delay ab 12 s
→ Queue Growth
→ Message Delay
→ Deadline Miss
```
- completion_criteria:Erwarteter Toolflow:
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
- completion_criteria:Erwartetes Ergebnis:
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
- completion_criteria:Browser-Prüfung:
Prüfe:

```text
Botschaften
Sequenz
Signale
Trace
```

und synchronen Zeitkontext.
- completion_criteria:PASS:
Root Cause besitzt Evidence-Referenzen und kann auf Trace-, Route- und Modellobjekte zurückgeführt werden.

---
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED

Evidence: 12 files
