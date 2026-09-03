# AI-Agent: Runtime, Orchestrierung und Engineering-Audit

## Status

Die in diesem Dokument beschriebene Lösung ist implementiert, getestet und im
lokalen Communication Simulator aktiv.

Sie verbindet:

- lokale KI-Ausführung über Ollama und CUDA,
- eine zuverlässige Hybrid-Orchestrierung für Engineering-Tools,
- kontrollierte Nutzung der verfügbaren CPU- und RAM-Ressourcen,
- eine nachvollziehbare Proposal-Auditspur mit automatischer Engineering-Freigabe,
- eine kompakte Statusdarstellung im Agent-Overlay.

## Ziel

Der Engineering-Agent soll Aufgaben wie das Erzeugen von ECUs, Funktionen,
Interfaces, Nachrichten, Signalen und Relations selbstständig und sichtbar bis
zum kanonischen Ergebnis bearbeiten.

Dabei gelten zwei Grenzen:

1. Technische Zwischenschritte sollen ohne unnötige Rückfragen ausgeführt werden.
2. KI-generierte Engineering-Objekte werden als `AIProposal` auditiert,
   validiert und danach unmittelbar in das kanonische Modell übernommen.

## Lösungsarchitektur

```text
Benutzer
   |
   v
Next.js Agent-Overlay
   |
   v
ToolLoopAgent
   |-- strukturierte Spezifikation ----> deterministischer Engineering-Parser
   |
   `-- Unterhaltung und Tools --------> Ollama / qwen3.8:27b
                                           |-- OpenAI nur explizit/Recovery
                                           `-- Nemotron nur explizit/Recovery
                                                    |
                                                    v
Flask Engineering API
   |
   |-- AIProposal-Speicher
   |-- Validierung
   |-- Approval-Service
   `-- kanonisches Engineering-Modell
```

Der Agent schreibt nicht ungeprüft in das Engineering-Modell. Neue KI-Ergebnisse
werden zuerst als `AIProposal` gespeichert, serverseitig validiert und erst dann
über den Approval-Service kanonisch registriert.

## Provider-Auswahl

Standardmäßig ist `AI_PROVIDER=hybrid-demand` aktiv. Unterhaltung, Analyse und
Werkzeugsteuerung laufen mit Qwen 3.8 27B über Ollama. Ein vorhandener
Cloud-Schlüssel aktiviert allein noch keinen Cloud-Aufruf: OpenAI oder Nemotron
werden nur ausdrücklich angefordert oder bei einer bewussten Wiederaufnahme
nach einem lokalen Fehler verwendet.

| Situation | Verwendetes Modell |
| --- | --- |
| `AI_PROVIDER=local` | Ollama mit dem konfigurierten lokalen Modell für Antwort und Toolsteuerung |
| `AI_PROVIDER=hybrid-demand` (Standard) | Qwen lokal; Cloud nur auf ausdrücklichen Wunsch oder Recovery |
| `AI_PROVIDER=hybrid` | Kompatibilitätsmodus mit lokaler Antwort und bevorzugter Cloud-Orchestrierung |
| `AI_PROVIDER=nvidia` | NVIDIA NIM mit Nemotron |
| `AI_PROVIDER=openai` | OpenAI für Antwort und Toolsteuerung |

Der bei explizit aktiviertem NVIDIA-Betrieb voreingestellte Orchestrator ist:

```text
nvidia/nemotron-3-nano-30b-a3b
```

Wichtig: NVIDIA NIM ist in dieser Konfiguration ein externer
Orchestrierungsdienst. Die lokale RTX-GPU wird von Ollama genutzt. Ein später
lokal installiertes Nemotron-Modell kann über `LOCAL_AI_MODEL` und den lokalen
Provider ebenfalls per CUDA ausgeführt werden.

## Konfigurationsauflösung

Der Launcher lädt Umgebungsvariablen in folgender Priorität:

1. bereits gesetzte Prozessvariablen,
2. `My_first_Network_Simulator/.env.local`,
3. die über `NETWORKIS_SHARED_ENV_FILE` referenzierte gemeinsame `.env`,
4. interne Standardwerte.

Leere oder offensichtlich ungültige API-Key-Platzhalter in Prozessvariablen
blockieren dabei keinen gültigen Schlüssel aus `.env.local`.
Der gemeinsame Alias `OPEN_AI_KEY` wird als Organisationsschlüssel akzeptiert
und für NetworkIS auf `OPENAI_API_KEY` normalisiert.

Damit kann der vorhandene `NVIDIA_API_KEY` aus der gemeinsamen `.env` verwendet
werden, ohne ihn in das Repository zu kopieren. Schlüsselwerte werden weder in
der Oberfläche noch in den Service-Logs ausgegeben.

Relevante Variablen:

```dotenv
AI_PROVIDER=hybrid-demand
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=qwen3.8:27b
CLOUD_ESCALATION=on_failure
OLLAMA_MODELS=I:\engineering-intelligence-platform\models\ollama
OLLAMA_CONTEXT_LENGTH=8192
NETWORKIS_SHARED_ENV_FILE=C:\Users\<username>\PycharmProjects\.env
OPENAI_AI_MODEL=gpt-5-mini
NVIDIA_AI_MODEL=nvidia/nemotron-3-nano-30b-a3b
WAITRESS_THREADS=16
SIMULATION_WORKERS=12
SIMULATION_EXECUTOR=thread
```

## Nutzung der Workstation

Die Laufzeit ist für die vorhandene Workstation mit 32 logischen CPU-Kernen,
64 GB RAM und NVIDIA RTX 3070 Ti konfiguriert.

| Bereich | Konfiguration |
| --- | --- |
| Flask-Server | Waitress |
| API-Parallelität | 16 Threads |
| Simulationen | Prozess-Pool |
| Simulations-Worker | 12 Prozesse |
| Numerische Bibliotheken | 1 Thread je Worker |
| Lokale KI | Ollama mit CUDA |

Die Begrenzung numerischer Bibliotheken auf einen Thread pro Worker verhindert,
dass jeder Prozess seinerseits alle CPU-Kerne belegt. Dadurch bleibt die
Parallelisierung kontrollierbar und die Oberfläche reaktionsfähig.

## Agent-Ablauf

### Erzeugen eines Objekts

Ein bestätigter Auftrag durchläuft mindestens diese Schritte:

```text
Bestand prüfen
   -> passendes Objekt modellieren
   -> AIProposal registrieren
   -> validieren
   -> kanonisch registrieren
   -> Live-Update an die Oberfläche senden
```

Der erste Bestandscheck und mindestens ein fachlich passender Schreibschritt
werden orchestratorseitig abgesichert. Bei einem vollständigen Modellauftrag
erzwingt der Controller zusätzlich `createEngineeringChain`. Dieses Werkzeug
registriert in korrekter Reihenfolge:

```text
HardwareNode -> Function -> Interface -> Message -> Signal
```

Jedes Kind verwendet die soeben erzeugte kanonische ID seines Elternobjekts.

### Routing-Paket

Ein Routing-Auftrag kann erst abgeschlossen werden, wenn mindestens zwei
verschiedene HardwareNodes sowie die referenzierte Message und ihre Signals
kanonisch vorhanden sind. Fehlen diese Voraussetzungen, erzwingt der Controller
`createRoutableEngineeringPair`. Das Werkzeug registriert atomisch:

```text
Producer: HardwareNode -> Function -> Interface -> Message -> Signal
Consumer: HardwareNode -> Function -> Interface
Routing:  Producer -> Consumer mit kanonischen Message-/Signal-IDs
```

Source und Destination werden vor der Generierung aufgelöst und müssen
verschieden sein. Ein bereits aktiver Vorschlag mit identischer Source,
Destination und Message wird wiederverwendet statt dupliziert. Eine leere
Routing-Tabelle ist ausdrücklich nicht valide und liefert den Befund
`ROUTING_TABLE_EMPTY`.

Eine frühere starre Vorgabe von fünf Schreibschritten wurde entfernt. Sie führte
bei einfachen Aufträgen zu mehrfachen Vorschlägen und unnötig langen Läufen.

### Duplikatschutz

Vor dem Speichern prüft der Agent, ob bereits ein offener, gleichnamiger
Vorschlag für denselben Ressourcentyp existiert. In diesem Fall wird der
vorhandene Proposal wiederverwendet.

`APPROVED`, `REJECTED` und `SUPERSEDED` gelten nicht als offene Vorschläge.

### Audit und Review

Engineering-Objekt- und Relationsvorschläge werden automatisch validiert und
freigegeben. Die Proposal-Datensätze bleiben als Auditspur erhalten. Der
vorhandene Wizard sowie Bearbeiten-, Validieren- und Freigabe-Werkzeuge sind im
`KI-Audit`-Dropdown direkt unter dem ausgewählten kanonischen Objekt erreichbar.

Das verbindliche Human-Review-Gate bleibt für `OptimizationProposal` bestehen;
diese Vorschläge werden niemals autonom angewendet.

## Kompakte Darstellung

Interne Listen-, Prüf- und Approval-Toolkarten werden im normalen Chatverlauf
nicht mehr einzeln dargestellt. Der Benutzer sieht pro Objekt eine kompakte
Statuszeile.

```text
Temperatur-ECU · gefunden · modelliert · registriert
```

Ausführlichere technische Tool-Aktivitäten bleiben im einklappbaren
Aktivitätsprotokoll verfügbar.

Der Agent selbst wird als animierte Graph-Chat-Bubble dargestellt. Das Overlay
öffnet sich erst auf Benutzerwunsch und belegt vorher keinen dauerhaften
Seitenbereich. Der Chatverlauf bleibt während mehrerer Prompts und aller
Live-Aktualisierungen erhalten. Schließen des Overlays oder ein Seiten-Reload
beginnt bewusst eine neue Unterhaltung.

Die geführte technische Abfrage ist nicht Bestandteil des Chats. Sie öffnet als
eigenständiger Workbench-Dialog über `+ Neu anlegen`. Nach Abschluss wird nur
der daraus erzeugte strukturierte Auftrag gepuffert, der Agent geöffnet und der
Auftrag automatisch an den Chat übergeben. Schnellaktionen wie `+ ECU`,
`+ Gateway` und `+ Sensor` bleiben für die direkte manuelle Anlage verfügbar.

## Betrieb

Start über den gemeinsamen Launcher:

```powershell
.\start-networkis-local-ai.bat
```

Alternativ:

```powershell
backend\.venv\Scripts\python.exe generate_realistic_communication_tool.py web
```

Lokale Endpunkte:

- Oberfläche: `http://127.0.0.1:13500`
- Backend-API: `http://127.0.0.1:15050/api`
- Health-Check: `http://127.0.0.1:15050/api/health`
- Ollama: `http://127.0.0.1:11434`

Service-Logs:

```text
backend/runtime/service-logs/
```

## Verifikation

Die Umsetzung wurde mit folgenden Prüfungen abgeschlossen:

- Next.js-Produktions-Build erfolgreich,
- TypeScript-Prüfung erfolgreich,
- Backend-Testlauf: `124 passed, 6 skipped`,
- Launcher-Konfiguration: `19 passed`,
- Flask-Health-Check: `ok`,
- Ollama erreichbar und `qwen3.8:27b` installiert,
- lokaler Agent-Endpunkt mit `modelSource=local` verifiziert,
- kompakte Inline-Spezifikationen deterministisch erkannt und mit zwei
  vollständigen Engineering-Ketten end-to-end registriert,
- CUDA und RTX 3070 Ti erkannt,
- Waitress mit 16 Threads aktiv,
- Prozess-Executor mit 12 Workern aktiv,
- automatische Proposal-Validierung und kanonische Registrierung implementiert,
- vollständige Engineering-Kette bis zum Signal abgesichert,
- atomisches Producer-/Consumer-Routing-Paket und Routing-Duplikatschutz geprüft,
- leere Routing-Tabelle wird nicht mehr als technisch bestanden bewertet,
- stabiler Chatverlauf während der Sitzung und Live-Refresh implementiert.

## Zentrale Implementierungsdateien

- `generate_realistic_communication_tool.py`
- `runtime-performance.env.example`
- `start-networkis-local-ai.bat`
- `frontend/src/lib/agent/engineering-agent.ts`
- `frontend/src/lib/engineering-events.ts`
- `frontend/src/app/api/agent/chat/route.ts`
- `frontend/src/components/agent-chat-core.tsx`
- `frontend/src/components/assistant/AssistantGraphBubble.tsx`
- `frontend/src/components/assistant/AssistantGraphCanvas.tsx`
- `backend/tests/test_server_startup.py`

## Sicherheits- und Governance-Eigenschaften

- Keine Ausgabe oder Speicherung von API-Schlüsselwerten im Repository.
- Keine ungeprüfte KI-Schreibberechtigung: `AIProposal`, Validierung und
  Approval-Service bleiben verbindliche technische Stufen.
- Menschliche Freigabe bleibt für Optimierungsvorschläge verbindlich.
- Gleichnamige offene Proposals werden nicht mehrfach erzeugt.
- Hintergrundanimationen und Dienste berücksichtigen Ressourcenverbrauch.
- Der Launcher prüft belegte Ports und beendet ausschließlich seinen eigenen
  Prozessbaum.
