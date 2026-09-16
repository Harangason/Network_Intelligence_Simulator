# S35 — FAILED

Run: run-433ae47be4134d8a8f6d7ae546d9e3ea

- F05
- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Alle Views verwenden dieselbe Zeitbasis:

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
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED
- BROWSER_SCREENSHOT_MISSING

Evidence: 7 files
