# S24 — FAILED

Run: run-d124045bc5c94a8689f6021f92e6cea5

- F01
- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Ausgangsmodell:
```text
ParkAssist
→ ChassisController
→ Chassis_CAN / CAN-FD

DriverAssistance
→ ADAS_Controller
→ Ethernet

ADAS_Controller:
CAN-FD Capability = YES
CAN Controller = vorhanden
free channel = YES
CAN-FD Port = NONE
```
- completion_criteria:Erwartete Chat-Frage:
```text
Der ADAS_Controller unterstützt CAN-FD,
besitzt aber noch keinen CAN-FD-Port.

Soll ich einen CAN-FD-Port erstellen
und mit Chassis_CAN verbinden?

○ Ja – direkt anbinden
○ Gateway-Pfad prüfen
○ Ethernet-Alternative prüfen
```

Browser Skill wählt:

```text
Ja – direkt anbinden
```
- completion_criteria:Danach ohne weitere unnötige Fragen:
Agent muss über MCP/Core selbst ausführen:

```text
create/reuse HardwareInterface
create PhysicalPort
bind Controller Channel
connect Port to Chassis_CAN
update Network Membership
resolve Functional Interfaces
generate/reuse Transport Units
pack Payload
allocate Identifier
update Routing
recalculate Capacity
recalculate Timing
run Validation
run Communication Preflight
mark old dependent results STALE
Completion Check
```
- completion_criteria:Zu prüfende MCP-Schnittstellen:
Mindestens:

```text
hardware.interface.create
hardware.port.create
network.connect
transport.generate / transport.bind
routing.create / routing.update
capacity.calculate
timing.calculate
validation.run
```
- completion_criteria:PASS:
Ein einziges Nutzer-„Ja“ führt bis zur vollständig validierten Verbindung.

---
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED

Evidence: 10 files
