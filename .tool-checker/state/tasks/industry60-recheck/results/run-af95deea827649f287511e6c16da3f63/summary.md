# S34 — PARTIAL

Run: run-af95deea827649f287511e6c16da3f63

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Testsignale:

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
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED
- BROWSER_SCREENSHOT_MISSING

Evidence: 39 files
