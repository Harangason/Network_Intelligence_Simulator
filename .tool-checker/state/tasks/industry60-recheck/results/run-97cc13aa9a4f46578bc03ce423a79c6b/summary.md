# S25 — PARTIAL

Run: run-97cc13aa9a4f46578bc03ce423a79c6b

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Test 1 – ungültiges Argument:
Rufe testweise ein MCP-Tool mit ungültigem Parameter auf.

Erwartung:

```text
INVALID_INPUT
```

mit:

```text
field
reason
expected schema
```
- completion_criteria:Test 2 – nicht unterstützte Technologie:
Erwartung:

```text
NOT_SUPPORTED
```
- completion_criteria:Test 3 – Timeout:
Simuliere einen transienten Tool-Timeout.

Erwartung:

```text
TOOL_TIMEOUT
```

Tool Checker darf nach Retry-Policy erneut versuchen.
- completion_criteria:Test 4 – fachlicher Fehler:
Beispiel:

```text
CAN Controller max_channels = 2
used_channels = 2
create_port(channel=3)
```

Erwartung:

```text
CAPACITY_EXCEEDED / NO_FREE_CHANNEL
```

Kein Auto-Retry als technischer Timeout.
- completion_criteria:PASS:
Fehler werden strukturiert behandelt und niemals als Erfolg oder erfundener Completion-Status ausgegeben.

---
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung

Evidence: 3 files
