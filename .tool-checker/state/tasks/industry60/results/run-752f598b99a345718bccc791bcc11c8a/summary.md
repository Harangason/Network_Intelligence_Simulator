# S40 — FAILED

Run: run-752f598b99a345718bccc791bcc11c8a

- F05
- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:```text
Engineering Model
↓
Simulation Snapshot
↓
Simulation Run
↓
Fault Injection
↓
Universal Trace
↓
Trace Session
↓
Botschaften
↓
Sequenz
↓
Signale
↓
Synchronisierter Trace
↓
Golden Trace Comparison
↓
Root Cause
↓
Finding
↓
Visualization
↓
Completion
```

Pflichtprüfungen:

1. SimulationRun reproduzierbar.
2. TraceSession referenziert richtigen Run.
3. LogicalNodeAddresses werden korrekt aufgelöst.
4. Transport Units sind technology-aware.
5. Botschaften zeigt echte Events.
6. Sequenz zeigt Gateway-/Route-Hops.
7. Signale werden korrekt dekodiert.
8. Views sind synchron.
9. Faults sind sichtbar.
10. Route Correlation funktioniert.
11. Golden Trace Vergleich funktioniert.
12. First Divergence wird erkannt.
13. Root Cause besitzt Evidence.
14. Finding referenziert Source Events.
15. Deep Links führen zu Model Objects.
16. Ergebnis bleibt nach Reload bestehen.

MCP mindestens:

```text
simulation.inspect
simulation.get_result
trace.load
trace.inspect_session
trace.get_messages
trace.get_sequence
trace.get_signal_series
trace.get_window
trace.correlate_route
trace.correlate_fault
trace.compare_golden
trace.find_first_divergence
trace.root_cause
finding.create
```

Browser Skill prüft reale Klicks durch:
```text
Botschaften
Sequenz
Signale
Trace
Finding
Root Cause
```

Tool Checker Progress bleibt deterministisch:
```text
llm_calls_progress = 0
```

PASS nur bei geschlossener Kette:
```text
Simulation
+
Trace
+
Decode
+
Correlation
+
Golden Trace
+
Root Cause
+
Finding
+
Evidence
```
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED
- BROWSER_SCREENSHOT_MISSING

Evidence: 7 files
