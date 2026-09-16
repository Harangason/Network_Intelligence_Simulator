# S02-B — PARTIAL

Run: run-673e88d9b9bb48378d91856d65f45443

- TC_WRONG_TOOL_SEQUENCE:Modellkontext erfassen
- TC_WRONG_TOOL_SEQUENCE:Originalauftrag an Engineering-Agent senden
- TC_WRONG_TOOL_SEQUENCE:Agentenantwort und Persistenz prüfen
- TC_WRONG_TOOL_SEQUENCE:Ergebnis im Browser prüfen
- REQUIRED_TOOLS:Browser
- REQUIRED_VIEWS:Engineering
- REQUIRED_OUTPUTS:Originalantwort und persistierter Modellzustand
- expected_model_changes:Hardware, Funktionen, Zuordnungen, Interfaces, Ports, Netze, Payloads und Transport gemäß Originalauftrag
- expected_calculations:Capacity, Timing und gegebenenfalls Gateway Load getrennt belegt
- expected_validations:Typing, Technologiekompatibilität, Ports, Transport, Routing und Simulation Preflight validiert
- expected_visualizations:Netzwerk- und Routingdarstellung passend zum gespeicherten Modell
- completion_criteria:Technisch begründete Architektur und nachvollziehbare Entscheidungen
- completion_criteria:Vollständige Validierung ohne offene Identifier-Konflikte
- completion_criteria:Keine Fertigmeldung ohne vollständige fachliche Artefakte
- completion_criteria:Wiederholung verwendet bestehende passende Objekte ohne Duplikate
- UNASSESSED_FAILURE_CONDITION:Fachfremde Automotive-Zuordnung ohne Begründung
- UNASSESSED_FAILURE_CONDITION:Erfundene bestätigte Hardwarefakten oder Kodierungen
- UNASSESSED_FAILURE_CONDITION:Unnötige Delegation der Engineering-Ausführung an den Nutzer
- TC_BROWSER_ACTION_FAILED
- BROWSER_SCREENSHOT_MISSING

Evidence: 13 files
