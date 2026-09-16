# S23 — PARTIAL

Run: run-bbaf01e055f24d9b9257c10687596166

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Ausgangsmodell:
```text
ParkAssist
→ ChassisController
→ CAN_FD_1
→ Chassis_CAN

DriverAssistance
→ ADAS_Controller
→ ETH_1
→ ADAS_ETHERNET
```
- completion_criteria:Erwartete MCP-Aufrufe:
Mindestens:

```text
find_function("ParkAssist")
find_host_hardware(...)
find_hardware_interfaces(...)
find_network_membership(...)

find_function("DriverAssistance")
find_host_hardware(...)
find_hardware_interfaces(...)
find_network_membership(...)

find_routes_between(...)
```
- completion_criteria:Zu prüfen:
```text
gleiche Canonical IDs in Agent, UI und Core
keine erfundenen Interfaces
keine erfundene Route
keine neue Model Mutation bei reinem Read-Auftrag
```
- completion_criteria:PASS:
Der Chat beschreibt den tatsächlichen Modellzustand und kann alle Aussagen auf Core-Objekte zurückführen.

---
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED
- BROWSER_SCREENSHOT_MISSING

Evidence: 8 files
