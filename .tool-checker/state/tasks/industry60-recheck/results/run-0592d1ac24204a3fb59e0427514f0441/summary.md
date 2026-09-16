# S33 — PARTIAL

Run: run-0592d1ac24204a3fb59e0427514f0441

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Testpfad:

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
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED
- BROWSER_SCREENSHOT_MISSING

Evidence: 39 files
