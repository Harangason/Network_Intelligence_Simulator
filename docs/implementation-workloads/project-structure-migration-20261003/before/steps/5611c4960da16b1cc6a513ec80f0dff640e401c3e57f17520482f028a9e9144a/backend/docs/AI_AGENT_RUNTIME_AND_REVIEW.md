# AI-Agent: aktive Runtime und menschlicher Review

Stand: 2026-09-06. Der Engineering-Chat verwendet jetzt den Python Agent Core über MCP. Die frühere TypeScript-Hybrid-Orchestrierung und automatische Übernahme sind in diesem Ausführungspfad abgelöst.

```text
Next.js Overlay → Stream-Proxy → Python EngineeringAgent
    → MCP Client → simulator-engineering-mcp → Python-Fachdienste
    → Proposal → Validierung → menschliche Freigabe → Apply → kanonisches Modell
```

## Lokale Modelle und Ressourcen

Der Launcher liest weiterhin `config/networkis.resources.json`, prüft PostgreSQL, Backend und feste Ports und startet den lokalen Modelldienst. `LOCAL_AI_BASE_URL` und `LOCAL_AI_MODEL` bestimmen das Modell des Python-Agenten, standardmäßig Ollama und `qwen3.8:27b`. Die alten Cloud-/Hybrid-Provider-Schalter des TypeScript-Agenten sind für diesen Chat nicht wirksam. Vorhandene Cloud-Schlüssel lösen keine Cloud-Aufrufe aus.

Waitress-Threads, Simulationsexecutor und Workerzahl stammen weiterhin aus der vorhandenen Laufzeitkonfiguration. Die Agent-API begrenzt gleichzeitige Läufe auf vier und jeden Lauf auf 270 Sekunden. Chat-Fortschritt wird gestreamt; beim Verbindungsabbruch endet der Lauf an der nächsten Abbruchprüfung, spätestens am Laufzeitlimit.

## Freigabe

Generierung und technische Validierung erzeugen keine menschliche Freigabe. Im Overlay stehen Änderungen, Zielobjekte, Annahmen und Findings. Nutzer geben einen validierten Vorschlag frei und übernehmen ihn anschließend ausdrücklich ins Modell. Der Agent kann diese Freigabe nicht per MCP erteilen. Bereits übernommene Vorschläge bleiben idempotent; veraltete Modellstände müssen erneut geprüft werden.

Die lokale Review-API nutzt CSRF-Schutz und explizite Aktionsheader. Sie ersetzt keine Benutzerverwaltung für öffentlich erreichbare Dienste. Mehrere lokale Browser teilen eine Projekt-ID; Konfliktschutz kommt aus Datenbanktransaktionen und Modellversionen.

## Status und Audit

`READY_FOR_REVIEW` bedeutet geprüft und zur Freigabe bereit. `COMPLETED` setzt erfüllte Workload-Ziele und bestätigte kanonische IDs voraus. `ANSWERED` kennzeichnet eine beantwortete Leseanfrage. Der Agent zeigt gezielte Auswahlfragen, Findings und Vorschlagskarten; interne Tool-Traces bleiben in der Auditspur.

`engineering_agent_audit` dokumentiert MCP-Aufrufe, Validierung, Review und Apply mit Trace-ID. Der vorhandene Proposal- und Workload-Speicher bleibt maßgeblich. Simulationen laufen für Browser und externe MCP-Clients im selben Anwendungs-Executor.

Vollständige Betriebsparameter, Tool-/Ressourcenverträge, Grenzen und Abnahme: [MCP As Built](../../docs/agent_core/14_MCP_IMPLEMENTATION.md).
