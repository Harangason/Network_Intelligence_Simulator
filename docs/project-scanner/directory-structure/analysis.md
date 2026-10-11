# Quellengeprüfte Einordnung der Verzeichnisstruktur

Projekt: `I:\PycharmProjects\My_first_Network_Simulator`.
Stand: 02.10.2026; Commit und Datei-Hashes im [Inventar](inventory.json).
Analysemodus: Dokumentation, keine funktionalen Änderungen.

## Einstieg und Betrieb

Der gemeinsame [Launcher](../../../generate_realistic_communication_tool.py)
liest `config/networkis.resources.json`, prüft Abhängigkeiten und verwaltet die
Backend-/Frontendprozesse. Die Windows-Einstiege sind
[start-networkis.bat](../../../start-networkis.bat),
[start-networkis.ps1](../../../start-networkis.ps1) und
[start-networkis-local-ai.bat](../../../start-networkis-local-ai.bat).
[host_metrics_bridge.py](../../../host_metrics_bridge.py) stellt Hostmetriken
für die Docker-Oberfläche bereit.

[Dockerfile](../../../Dockerfile) baut Python-/Node-Laufzeit und Frontend.
[docker-compose.networkis.yml](../../../docker-compose.networkis.yml) beschreibt
PostgreSQL und den NIS-Service mit Ports 13500/15050, Healthchecks und persistenten
Volumes. Diese Aussage beschreibt Konfiguration, keinen geprüften Livezustand.
Release-/Deploymentwerkzeuge liegen unter `scripts/`; der Projektvertrag verlangt
eine passende PASS-Receipt und das genaue getestete Image.

## Backend

- `backend/app/`: Flask-App-Factory `create_app`, API-Blueprints,
  Simulationsjobs, Storage, Trace-Import und Analysezugriff.
  [__init__.py](../../../backend/app/__init__.py) registriert die Fach-APIs und
  versucht außerhalb des Testmodus unterbrochene Läufe wiederherzustellen.
  [__main__.py](../../../backend/app/__main__.py) startet Waitress beziehungsweise
  den Entwicklungsserver mit exklusiver Portbindung.
- `backend/engineering/`: kanonisches Fachmodell, Validierung, Generation,
  Routing, Kapazitätsberechnung und Workflow-Persistenz.
  [repository.py](../../../backend/engineering/repository.py) kapselt CRUD und
  Governance für Hardware, Funktionen, Interfaces, Nachrichten und Signale.
  [db.py](../../../backend/engineering/db.py) verwaltet Pool, Transaktionen,
  Projektlocks und Revisionserkennung.
- `backend/communication/technologies/`: Technologieprofile, Registry,
  Bindings, Generatoren und Onboarding.
  [core/models.py](../../../backend/communication/technologies/core/models.py)
  trennt Geräte-/Interfaceobjekte, Protokollebenen und Payloadtypen;
  [core/registry.py](../../../backend/communication/technologies/core/registry.py)
  registriert Profile, Validatoren, Codecs sowie Last-/Timingmodelle.
- `backend/simulator/`: Scheduling, modellbasierte Signal-/Fehlersimulation,
  Transport, Physikbibliotheken und Traceausgabe.
  [model_based_simulation.py](../../../backend/simulator/model_based_simulation.py)
  definiert deterministische Verhaltens-/Codec-/Fault-Primitiven.
  `physic_lib/Industries/` enthält Branchenmaterial getrennt von den
  Technologiepfaden. Vorhandene Datenbanken werden als Binärdateien inventarisiert;
  ihr Tabelleninhalt wurde nicht gelesen.
- `backend/agent_core/`: Agentkontext, Planung, Dispatch, Workloads, Grenzen und
  Validierung. [EngineeringAgent](../../../backend/agent_core/core/engineering_agent.py)
  verwendet den MCP-Client und strukturierte Toolantworten.
- `backend/simulator_engineering_mcp/`:
  [server.py](../../../backend/simulator_engineering_mcp/server.py) registriert
  Tools/Ressourcen, validiert deren Eingaben und delegiert Fachoperationen an den
  Python-Core. Toolregistrierung allein beweist keine fachliche Umsetzung.
- `backend/tests/`: Backend-Prüfungen; SQL-Prüfungen dürfen ausschließlich über
  `scripts/run-isolated-tests.py` gegen isolierte Datenbanken laufen.

## Frontend und Datenfluss

`frontend/src/app/` enthält Next.js-Seiten und Serverrouten. Die Marketingseite
`/workflow` erklärt den Ablauf; die tatsächlichen Engineeringansichten liegen
unter `/studio`. [studio/page.tsx](../../../frontend/src/app/studio/page.tsx)
erhält den Projektkontext aus Suchparametern und leitet ohne Modus zur
Engineeringansicht weiter.

`frontend/src/components/` enthält React-Bedienoberflächen,
`frontend/src/features/workflow/` die Workflow-Bereiche und
`frontend/src/lib/` Typen, API-Clients und Fachhilfen.
[workflow-api.ts](../../../frontend/src/lib/workflow-api.ts) führt Zustand,
Quellversionen und Snapshots zusammen.
[api/_backend.ts](../../../frontend/src/app/api/_backend.ts) reicht Requests mit
Projekt-ID, Timeout und Antwortheadern an das Backend weiter.

Die dokumentierte fachliche Reihenfolge lautet:

```text
Engineering-Modell -> Routing -> Netzwerk -> Parameter -> Capacity/Timing
-> Validation/Preflight -> Simulation -> Results/Analysis -> Intelligence
```

[WorkflowStatusService](../../../backend/engineering/workflow/service.py)
persistiert Zustände und Versionen. Die
[Workflowarchitektur](../../../backend/docs/WORKFLOW_ARCHITECTURE.md) beschreibt
Invalidierung als OUTDATED, unveränderliche Simulationssnapshots und getrennte
Analyse-/Review-/Apply-Schritte. Die Übersicht übernimmt diese Regeln als
Architekturkontext; sie weist keine neue Laufzeitabnahme nach.

## Abdeckung und Verifikation

| Bereich | Nachweis | Grenze |
| --- | --- | --- |
| Pfade und Dateigrößen | Vorhandener Arbeitsbaum, explizite Ausnahmen | Ausgenommene Bäume nicht rekursiv erfasst |
| Python | AST, Modul-/Symboltexte, Imports, Dekoratorrouten | Keine Ausführung, keine semantische Vollprüfung |
| JavaScript/TypeScript | Installierter TypeScript-Compilerparser, Definitionen, Imports, Test-/UI-Texte | Keine Typeprüfung oder Anwendungsausführung |
| Markdown und Konfiguration | Abschnitte, Textauszüge, Schlüssel, XML-/CSV-Struktur | Werte nicht kopiert; keine Konfigurationswirksamkeit geprüft |
| Zentrale Architekturdateien | Gezielt gelesene Implementierungsabschnitte, Quellenlinks oben | Keine vollständige Prüfung sämtlicher Fehlerpfade |
| Binär-/Großdateien | Metadaten; Hash nur unter 2 MB | Inhalt offen |
| Suchbare HTML-Übersicht | Browserprüfung in verification.json | Prüft Dokumentationsartefakt, keinen NIS-Workflow |

Dateiweise Symbole und Zeilennummern stehen im
[Markdown-Katalog](file-descriptions.md) und im [JSON-Inventar](inventory.json).
Die separate Scannerprüfung meldet vorhandene Stil-/Docstring-Befunde; diese
wurden im Rahmen des Verzeichnisauftrags nicht durch Quellcodeänderungen behoben.
