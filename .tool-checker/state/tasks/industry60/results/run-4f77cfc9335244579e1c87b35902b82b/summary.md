# S36 — FAILED

Run: run-4f77cfc9335244579e1c87b35902b82b

- F03
- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Fault:

```text
Gateway Delay
start = 12 s
duration = 3 s
```

Trace muss zeigen:

```text
fault start
queue growth
message delay
deadline miss
fault end
recovery
```

MCP:
```text
simulation.get_faults
trace.get_fault_events
trace.correlate_fault
timing.get_deadline_misses
```

Finding:
```text
TIMING_CAUSAL_CHAIN
```

Evidence muss Fault Event, Queue Metric, Message Delay und Deadline Miss referenzieren.
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung

Evidence: 6 files
