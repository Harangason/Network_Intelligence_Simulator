# S21 — PARTIAL

Run: run-d231120e604141739ae6767ac3728ffc

- TC_WRONG_TOOL_SEQUENCE:Originalfall ausführen und Nachweise sichern
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- completion_criteria:Erwartetes Agentenverhalten:
```text
Wizard Selection
→ AgentInputEnvelope
→ Goal Type = CREATE_ARCHITECTURE
→ Typing
→ Model Context
→ Architecture Reasoning
→ benötigte Entscheidungen
→ Execution Plan
```

Der Agent darf nicht nur einen anderen Editor öffnen.
- completion_criteria:MCP-Prüfung:
Mindestens prüfen:

```text
Capability Discovery
model.inspect
hardware.inspect
function.inspect
hardware.interface.inspect
network.inspect
```

Wenn noch kein Modell existiert:

```text
controlled proposal / create path
```
- completion_criteria:Browser-Prüfung:
Browser Skill prüft:

1. Wizard-Button ist sichtbar.
2. Klick aktiviert den richtigen Modus.
3. Prompt wird korrekt übernommen.
4. Agent beginnt erst nach dem vorgesehenen Start/Senden.
5. Ergebnis erscheint im selben Chat-Kontext.
6. Keine unnötige Navigation zu einem anderen Werkzeug als Ersatz für die Ausführung.
- completion_criteria:PASS:
```text
Wizard → Agent Goal → MCP Context → Engineering Execution
```

ist durchgängig nachgewiesen.

---
- UNASSESSED_FAILURE_CONDITION:Erfundene erfolgreiche Ausführung
- TC_BROWSER_ACTION_FAILED

Evidence: 4 files
