# Engineering Agent und MCP — As Built

Stand: 2026-09-06. Grundlage: `../SIMULATOR_ENGINEERING_AGENT_MCP_ARCHITECTURE_CODEX.md` und der Chat „Simulator erweitern Funktionen“. Die angehängten Dokumente wurden als Spezifikation ausgewertet; ihre internen Agentenanweisungen ersetzen keine Nutzerfreigabe.

## Aktiver Ausführungspfad

```text
Chat-Overlay → Next.js Stream-Proxy → Python EngineeringAgent
    → offizieller MCP Client → simulator-engineering-mcp
    → vorhandene Python-Fachdienste → kanonisches PostgreSQL-Modell
```

`frontend/src/lib/agent/engineering-agent.ts` enthält nur Transporttypen. Die bisherige parallele TypeScript-Orchestrierung wurde entfernt. `backend/agent_core/core/engineering_agent.py` orchestriert ohne SQL-, Repository- oder Simulator-Domain-Imports. Workload-Planer, Generatoren, Validatoren und Completion-Evaluator bleiben im vorhandenen Agent Core bzw. dessen Engineering-Adaptern.

Im Backend nutzt der offizielle MCP-SDK-Client einen eingebetteten MCP-Server mit Protokollinitialisierung, Discovery und strukturierten Tool-Aufrufen. Externe Clients können denselben Server über stdio oder Streamable HTTP nutzen. Das ist kein zweiter Simulations-Executor: Start, Status, Stop und Trace-Zugriff laufen über den Job-Gateway zur bestehenden Anwendungs-API.

## Betrieb

Die bestehenden Launcher und PostgreSQL bleiben Voraussetzung. Python-Abhängigkeiten: `backend/requirements.txt`, einschließlich `mcp>=2.1,<3`; geprüft mit MCP 2.1.1.

| Variable | Bedeutung / Standard |
|---|---|
| `DATABASE_URL` | Dieselbe PostgreSQL-Datenbank wie der Simulator; serverseitig konfigurieren |
| `LOCAL_AI_BASE_URL` | Lokaler OpenAI-kompatibler Ollama-Endpunkt, `http://127.0.0.1:11434/v1` |
| `LOCAL_AI_MODEL` | `qwen3.8:27b`, durch die Launcher-Konfiguration überschreibbar |
| `SIMULATOR_ENGINEERING_API_URL` | Next.js → Python Engineering-API, `http://127.0.0.1:15050/api/engineering` |
| `SIMULATOR_JOB_API_URL` | MCP → zentraler Job-Executor, `http://127.0.0.1:15050/api` |

Der neue Engineering-Chat verwendet den konfigurierten lokalen Modelldienst. Die früheren TypeScript-Schalter für Cloud-Eskalation und Fast-Model-Routing steuern diesen Pfad nicht. Ein vorhandener Cloud-Schlüssel löst keinen Aufruf aus. Docker kann die vorgesehenen lokalen Hostnamen `host.docker.internal` oder `ollama` verwenden.

Aus dem Projektstamm starten:

```powershell
# DATABASE_URL muss in der Umgebung des MCP-Prozesses gesetzt sein.
backend\.venv\Scripts\python.exe -m backend.simulator_engineering_mcp --project PROJEKT_ID

# Alternativ: http://127.0.0.1:15052/mcp
backend\.venv\Scripts\python.exe -m backend.simulator_engineering_mcp --project PROJEKT_ID --transport streamable-http --port 15052
```

Ein externer Server ist an eine Projekt-ID gebunden. Unterschiedliche Browser öffnen denselben Projektlink und verwenden dieselbe Anwendungs-API. Ein MCP-Client übergibt keine Projektwechsel oder Berechtigungen in Tool-Argumenten. Bei stdio muss seine Prozesskonfiguration insbesondere `DATABASE_URL` explizit weiterreichen; der SDK vererbt nicht jede Umgebungsvariable automatisch.

## Verträge und Ressourcen

101 registrierte, typisierte Werkzeuge decken alle 85 ausdrücklich benannten erlaubten Werkzeuge der Spezifikation ab. `update_any_object`, `delete_anything` und autonome Freigabewerkzeuge fehlen absichtlich. Der ausführbare Katalog liegt in `backend/engineering/agent_tools/services.py`; doppelte Registrierungen brechen beim Start ab.

17 spezifizierte Ressourcen sind abrufbar: Projekt, vollständiges Modell, Hardware, Funktionen, logische und physische Interfaces, Signale, Nachrichten, Netze, Routing, Findings, vier Objektschemas, CAN-FD-Nutzlastklassen und Geräteklassen. Projektressourcen sind serverseitig gebunden und werden auditiert.

`AgentContext`, `ToolResult`, `EngineeringProposal` und Berechtigungen liegen unter `backend/agent_core/context` bzw. `backend/agent_core/api`. Tool-Erfolg und Auftragserfüllung bleiben getrennt. Jeder Tool-Aufruf liefert eine Trace-ID. Validation, Review, Apply und Workload-Completion bleiben im vorhandenen Proposal-/Workload-Speicher nachvollziehbar; zusätzlich speichert `engineering_agent_audit` Aufrufstatus und die relevanten Ergebnisreferenzen.

## Änderungen und menschliche Freigabe

```text
PROPOSED → VALIDATED → APPROVED → APPLIED
               ↘ REJECTED       ↘ OUTDATED bei geändertem Modellstand
```

Generatoren erstellen den gemeinsamen Vertrag in `engineering_ai_proposals.engineering_contract`. Sie schreiben dabei keine freigegebenen Modellobjekte. Ein Signal-Workload wird für den Review zu einem gemeinsamen Vorschlag zusammengefasst; dadurch machen sich seine Teilvorschläge nicht gegenseitig durch Modelländerungen ungültig.

Die Oberfläche zeigt Änderungen, Zielobjekte, Annahmen und Findings. „Vorschlag freigeben“ und „Ins Modell übernehmen“ sind getrennte bewusste Aktionen. Freigabe ist nicht als MCP-Tool verfügbar. Die lokale Review-API fordert ein SameSite-CSRF-Cookie, den zugehörigen Header und einen expliziten Review-Header. Eine behauptete `approved_by`-Angabe aus einem Modellaufruf ist keine Berechtigung.

Die Anwendung ist weiterhin eine lokale, vertrauenswürdige Arbeitsumgebung. `local-human` ist keine personenbezogene Enterprise-Identität. Für einen öffentlich zugänglichen Mehrbenutzerdienst sind authentifizierte Benutzer, Projektmitgliedschaften und serverseitige Rollenzuordnung zusätzlich nötig; diese werden nicht durch eine Projekt-ID ersetzt.

Standardrechte: Lesen, Vorschläge erzeugen, validieren, Simulation ausführen und Trace analysieren. Externe Betreiber können `--allow-apply-approved` und `--allow-delete-proposals` gezielt ergänzen. Auch dann setzt Apply eine bereits persistierte menschliche Freigabe voraus. Löschungen benötigen eine transitive Auswirkungsanalyse und erfüllen die bestehenden Lifecycle-Regeln.

Apply prüft den aktuellen Modellstand, validiert erneut und übernimmt alle Änderungen atomar. Projektweite Datenbanksperren serialisieren konkurrierende Mutationen. Gleichzeitige Apply-Aufrufe desselben Vorschlags geben dieselben kanonischen IDs zurück. Eine zwischenzeitliche Modelländerung führt zu `OUTDATED` und erneuter Prüfung.

## Fachliche Durchgängigkeit

- Signale: exakte Sollzahlen und Teilmengen, Semantik, Bitbedarf, Wertebereich, Überlappung und Nutzlast. Der Fall 35 = 10 Temperatur + 25 Bewegung ist mit echten PostgreSQL-Daten bis `COMPLETED` nach menschlichem Apply geprüft.
- Funktionen und Geräte: vorhandene Anforderungsexpansion und Geräteklassenregister; Annahmen bleiben im Vorschlag. Nicht begründbare Mengen werden nicht mit Platzhaltern aufgefüllt.
- Nachrichten: bestehender Packer gruppiert nach Funktion, Sender, Zyklus, Empfängern und Priorität; CAN FD hat höchstens 64 Byte. Namen bleiben über mehrere Gruppen eindeutig. Identifier werden erst beim Apply verbindlich geprüft.
- Interfaces und Netze: vorgeschlagene Zuordnungen prüfen Hardware, Technologie und Last. Netzparameter werden in den kanonischen Workflow-Parametern gespeichert und von Kapazitätsrechnung und eingefrorener Simulation verwendet.
- Routing: gemeinsamer Validator, semantische Duplikatprüfung, menschlich freigegebene Routen und vorhandene Graph-Publikation. Optional unterschiedliche JSON-Standardfelder oder eine andere Reihenfolge von Signal-IDs umgehen die Duplikatprüfung nicht.
- Simulation: Preflight → unveränderlicher Snapshot → einmaliger Start im zentralen Executor → Status/Ergebnisse/Trace. Der zweite Start desselben Snapshots wird als Konflikt abgewiesen.
- Trace und Graph: Zeitfenster mit begrenztem Speicher, Korrelation auf gemeinsamen Zeitstempeln, Golden-Trace-Vergleich einschließlich Wertabweichungen, Hypothesen statt behaupteter Kausalität, Zusammenhang und Ausfallpunkte einschließlich Gateway-Hops.
- Modellartefakte: SignalBehavior verwendet die vorhandene kanonische Verhaltenstabelle. StatusModel und DataObject werden als freigegebene Architekturmetadaten unter `parameters.engineering_models` gespeichert; sie behaupten keine zusätzliche ausführbare Objektsimulation.

ML ist beratend. Die vorhandenen Klassifikatoren nutzen den trainierten Token-Weight-Fallback auf synthetischen Golden-Set-Daten und weisen diese Implementierung aus. Routing-, Packing- und Architektur-Scores sind deterministische Feature-Bewertungen und werden nicht mehr als echte Random-Forest-/Gradient-Boosting-Inferenz bezeichnet. Registry-Schreibvorgänge sind prozessübergreifend gesperrt und atomar. Eine spätere produktive ML-Freigabe mit realen Trainingsdaten bleibt ein eigener Modell-Review.

## Laufzeitgrenzen

Vier gleichzeitige Agentenläufe, höchstens 12 normale Tool-Runden und drei Reparaturrunden, maximal 270 Sekunden pro Chatlauf. Fehler oder Zeitlimits lassen den Auftrag offen. Ein LLM-Text setzt keinen Workload auf `COMPLETED`. Reine Leseantworten verwenden `ANSWERED`; vollständige Vorschläge `READY_FOR_REVIEW`. Die Workload-Zustände einschließlich `REPAIRING` stammen aus persistierten Prüfergebnissen.

Direktanalysen sind auf 100.000 Trace-Ereignisse beschränkt. `get_trace_window` kann größere gespeicherte Traces streamend durchsuchen und ein begrenztes Fenster zurückgeben. Berechnungen und Snapshots laden kanonische Objekte vollständig über Pagination.

## Abnahme am 2026-09-06

| DoD-Punkte der Spezifikation | Umsetzung / Nachweis |
|---|---|
| 1–7, 26–28 | Python-Agent und bestehender Workload Core; exakter 35-Signal-Test, Repair/Completion, getrennte Schichten |
| 8–20, 23 | 101 Tools, sämtliche 85 erlaubten Toolnamen, 17 Ressourcen; offizieller SDK über eingebettet, stdio und HTTP |
| 21–22, 24–25 | gemeinsame Vorschläge, CSRF-Review, Rechte, Projektbindung, transitive Löschfolgen, Audit, Konkurrenztests |
| 29 | konsumierbare MCP-/Pydantic-Verträge; keine EIP-Laufzeitabhängigkeit |
| 30 | 483 Backend-Tests, 109 Frontend-Tests, TypeScript und Produktionsbuild; Chrome/Edge sowie Simulation/Trace-End-to-End |
| 31 | diese As-Built-Dokumentation, aktualisierter Runtime-/Review-Pfad und persistierte Testnachweise |

Befehle, Berichte und Screenshots: [Abnahmebericht](../implementation_audit/2026-09-06_agent_mcp.md). Die Prüfung lief auf isolierten Testports und einer separaten PostgreSQL-Instanz; bestehende Nutzermodelle wurden nicht als Testdaten verändert.

Die reguläre Docker-Anwendung wurde nach Sicherung der Datenbank auf Schema 21 aktualisiert und auf 13500/15050 lesend nachgeprüft. Chat-Folgefragen erhalten bis zu zwölf vorherige Nutzer-/Assistentennachrichten; übergebene Systemrollen sind nicht zugelassen.
