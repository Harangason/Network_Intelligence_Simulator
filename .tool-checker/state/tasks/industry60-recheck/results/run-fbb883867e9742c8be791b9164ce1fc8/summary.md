# S38 — PARTIAL

Run: run-fbb883867e9742c8be791b9164ce1fc8

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Szenario:

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
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung

Evidence: 39 files
