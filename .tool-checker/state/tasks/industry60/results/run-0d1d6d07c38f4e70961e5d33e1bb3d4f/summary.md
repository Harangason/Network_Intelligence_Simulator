# S33 — FAILED

Run: run-0d1d6d07c38f4e70961e5d33e1bb3d4f

- F03
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

Evidence: 6 files
