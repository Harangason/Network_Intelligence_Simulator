# S27 — PARTIAL

Run: run-57617f36fd9f4246aa57146992a8e42c

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Browser:
Klick:

```text
Signal prüfen
```
- completion_criteria:Testsignal:
```text
MotorRPM

Range:
0…5000 rpm

Resolution:
50 rpm

Cycle:
10 ms

Technology:
CAN-FD
```
- completion_criteria:Erwarteter Flow:
```text
inspect signal
→ classify semantic type
→ inspect definition vs message binding
→ calculate required bit length
→ inspect encoding
→ inspect TransportUnit
→ validate cycle / range / scaling
→ create Finding if necessary
```
- completion_criteria:MCP-Prüfung:
Mindestens:

```text
signal.inspect
signal.semantic.classify
signal.encoding.resolve
signal.bit_length.calculate
transport.inspect
signal.validate
```
- completion_criteria:Negative Fall:
Message Binding verwendet z. B.:

```text
4 bit
```

obwohl Wertebereich/Auflösung mehr benötigt.

Erwartung:

```text
VALIDATION_FAILED
Finding
```
- completion_criteria:PASS:
Der Wizard führt eine echte fachliche Prüfung durch und zeigt nicht nur die Signal-Detailseite.

---
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED

Evidence: 7 files
