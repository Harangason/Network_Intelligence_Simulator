# S39 — FAILED

Run: run-f6dad29a8c9d4d9dae028581e20c40c8

- F06
- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Test mit:

```text
> 100.000 Events
```

Filter:

```text
time range
source
destination
logical address
network
technology
message
signal
function
route
fault
severity
```

MCP:
```text
trace.query
trace.get_window
trace.get_page
trace.get_count
```

Pflicht:

```text
windowing
pagination
streaming
downsampling
```

Nicht:
```text
full trace in browser memory
```
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED
- BROWSER_SCREENSHOT_MISSING

Evidence: 7 files
