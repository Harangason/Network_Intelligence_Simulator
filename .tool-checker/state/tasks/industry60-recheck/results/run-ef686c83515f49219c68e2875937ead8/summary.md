# S32 — PARTIAL

Run: run-ef686c83515f49219c68e2875937ead8

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Prüfe:

```text
Timestamp
Source
Destination
Logical Addresses
Network
Technology
Transport Unit
Identifier
Payload Length
Cycle
Status
Fault
```

Technology-aware Labels:

```text
CAN-FD → Frame
DDS → Topic Sample
Modbus → Request/Response
PROFINET → Process Data
ARINC429 → Word
```

MCP:
```text
trace.get_messages
trace.decode_transport_unit
trace.resolve_source
trace.resolve_destination
```

Browser öffnet `Trace Analyse → Botschaften`, prüft Filter, Details und Source/Destination.
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED
- BROWSER_SCREENSHOT_MISSING

Evidence: 39 files
