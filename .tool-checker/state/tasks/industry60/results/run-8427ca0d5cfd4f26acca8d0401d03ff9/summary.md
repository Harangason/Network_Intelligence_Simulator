# S31 — FAILED

Run: run-8427ca0d5cfd4f26acca8d0401d03ff9

- F04
- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Prüfe Simulation Trace, Import Trace und Golden Trace.

Erwartete Session-Daten:

```text
session_id
source
source_type
time_range
networks
technologies
simulation_run_ref
timebase
sync_status
metadata
```

MCP:
```text
trace.load
trace.inspect_session
trace.get_metadata
```

Negative Fälle: unbekanntes Format, fehlende Zeitbasis, ungültige Metadaten.

PASS nur bei sauberer Source-/Timebase-/Technology-Zuordnung.
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung

Evidence: 6 files
