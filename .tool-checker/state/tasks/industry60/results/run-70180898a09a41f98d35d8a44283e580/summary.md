# S37 — PARTIAL

Run: run-70180898a09a41f98d35d8a44283e580

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Vergleiche:

```text
Run A → Golden Trace
Run B → Changed/Faulted Trace
```

Prüfe:

```text
missing events
additional events
timing deviation
signal deviation
state deviation
route deviation
fault deviation
```

MCP:
```text
trace.compare_golden
trace.find_first_divergence
trace.get_deviation_summary
```

PASS nur, wenn die `first credible divergence` bestimmt wird.
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung

Evidence: 5 files
