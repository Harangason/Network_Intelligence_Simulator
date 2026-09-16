# S22 — PARTIAL

Run: run-4e71cd8be349474da12a2c3dafa290f7

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Erwartung:
Der Agent bestimmt zuerst die benötigten Capabilities.

Beispiel:

```text
model.search
function.inspect
hardware.inspect
hardware.interface.inspect
network.inspect
routing.inspect
```
- completion_criteria:MCP-Prüfung:
Prüfe:

```text
Tool Registry erreichbar
Skill Registry erreichbar
Tool Name eindeutig
Input Schema verfügbar
Output Schema verfügbar
Permission Contract vorhanden
Tool Version vorhanden
```

Nicht erlaubt:

```text
hardcoded giant if/elif technology switch
unregistriertes Tool
freie Toolnamen aus LLM-Text
```
- completion_criteria:Negative Prüfung:
Fordere bewusst eine nicht existierende Capability an.

Erwartung:

```text
NOT_SUPPORTED / TOOL_NOT_FOUND
```

und keine erfundene erfolgreiche Ausführung.
- completion_criteria:PASS:
Der Agent findet nur registrierte Capabilities und kann deren Schemas korrekt verwenden.

---
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung

Evidence: 10 files
