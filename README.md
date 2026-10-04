# Communication Simulator

Die kanonischen Modulverantwortungen, Technologiepakete, Speicherpfade und
Kompatibilitätsregeln sind in der [Projektstruktur](docs/architecture/project-structure.md)
beschrieben. Auslieferungen erfolgen über `python scripts/release-and-deploy.py`
mit vollständigem Release-Gate und Überprüfung des laufenden Images.

Der Communication Simulator ist eine eigenständige, technologieoffene
Kommunikationssimulation. Er modelliert Hardware, physische Ports, logische
Netzwerk-Schnittstellen, Netzwerke, Nachrichten, Timing und Fehler unabhängig
von einer bestimmten Branche oder einem bestimmten Engineering-Werkzeug.

Die zentrale TechnologyProfile-Registry beschreibt integrierte und
benutzerdefinierte Verbindungstypen. Parameterprüfung, ausführbares
Kapazitätsmodell und native Dateiausgabe sind getrennte Fähigkeiten; ein
registriertes Profil allein belegt keine vollständige Simulation. Für CAN
und Ethernet stehen technologieabhängige native Writer zur Verfügung.

## Lizenz und Nutzung

Diese Software ist proprietär und steht unter der [NIS Proprietary Software
License](LICENSE). Ohne vorherige schriftliche Freigabe des Rechteinhabers ist
insbesondere untersagt, die Software oder wesentliche Teile davon zu nutzen,
zu kopieren, zu verändern, zu verbreiten, zu veröffentlichen, zu vermieten,
zu verkaufen, als Dienst bereitzustellen oder in andere Produkte zu integrieren.

Das öffentliche Vorliegen des Quelltextes oder seine Lesbarkeit in einem
Repository stellt keine Nutzungserlaubnis und keine Freigabe für Forks,
Weitergabe oder kommerzielle Verwendung dar. Anfragen für eine Nutzungslizenz
oder sonstige Freigabe müssen vor der betreffenden Nutzung schriftlich an den
Rechteinhaber gestellt werden. Bestandteile Dritter können eigenen
Lizenzbedingungen unterliegen; diese werden durch die Projektlizenz nicht
erweitert.

SPDX-Kennung für dieses Projekt: `LicenseRef-NIS-Proprietary-1.0`

### Quellenverzeichnis und Technikrechte

Die Hauptnavigation enthält **Quellen** (`/sources`): ein aus den registrierten
Technologieprofilen abgeleitetes Verzeichnis mit Fuzzy-Suche, deduplizierten
Quellen, alphabetischer Bustypreihenfolge und sortierbaren Spalten. Es zeigt
Kürzel, vollständigen Bustypnamen, Quellenname, kurze Links, belegtes Abrufdatum,
Veröffentlichungshinweise und projektbezogenen Freigabestatus. Unbekannte
Abrufdaten bleiben ausdrücklich nicht dokumentiert.

Das Verzeichnis veröffentlicht keine Originaldokumente. Öffentlich abrufbar
bedeutet nicht frei weiterveröffentlichbar. Das Stoppsymbol erklärt ungeklärte
oder eingeschränkte Rechte und führt zur Quelle beziehungsweise zu ihren
Bedingungen. Dokument-, Code-, Implementierungs- und Zertifizierungsrechte
werden getrennt; ungeklärte Punkte werden nicht als rechtlich geklärt ausgegeben.

Für NMEA 0183/2000 und MIPI CSI-2/DSI verlangt die vorsorgliche NIS-Policy eine
geprüfte projektbezogene Freigabe für den tatsächlichen Nutzungsumfang. Die
Techniken bleiben auswählbar, Ausführung ohne passenden Nachweis ist gesperrt.
Ein eingereichter Nachweis bleibt **PENDING** bis zur Betreiberprüfung;
Frontend-Bestätigungen schalten nichts frei. Nachweise haben Scope,
Policy-Revision, optionales Ablaufdatum und ein Änderungsprotokoll.
I3C Basic wird nicht pauschal mit vollem MIPI-Mitgliedschaftsrecht gleichgesetzt.

Details und Betreiberverfahren: [Quellen- und Lizenzvertrag](docs/SOURCE_LICENSING_CONTRACT.md).

## Weboberfläche

Das Projekt enthält eine lokale Flask-API und eine Next.js-Oberfläche. Die
Flask-Schicht verwendet die vorhandene Python-API direkt; es werden keine
CLI-Kommandos aus HTTP-Anfragen zusammengesetzt.

Der Studio-Workflow ist verbindlich aufgebaut:

```text
Define -> Route -> Connect -> Configure -> Calculate -> Validate -> Simulate -> Analyze -> Assess
```

Änderungen an früheren Schritten markieren vorhandene abhängige Analysen und
Läufe als `OUTDATED`, ohne sie zu löschen. Simulationen starten nur aus einem
aktuellen Preflight und einem unveränderlichen SimulationSnapshot. Details
stehen in `backend/docs/WORKFLOW_ARCHITECTURE.md`.

### Gemeinsam in mehreren Browsern arbeiten

Über **Projektlink** denselben Link in Chrome, Edge oder einem weiteren Browser
öffnen. Alle Browser müssen dieselbe Simulator-Instanz mit derselben Datenbank
verwenden; die Projekt-ID steht im Link. Änderungen anderer Browser werden
spätestens beim nächsten erfolgreichen 5-Sekunden-Abgleich angezeigt. Offene
Entwürfe bleiben erhalten. Veraltete Objekt-, Routing-, Parameter- und
Topologieänderungen werden mit einem Konflikthinweis abgewiesen; anschließend
den aktuellen Stand laden und die Änderungen vergleichen.

Prüfumfang, bekannte Grenzen und reproduzierbare Tests:
[Konsistenz- und Mehrbrowserprüfung](docs/implementation_audit/2026-09-06_consistency_multibrowser.md).

### Aktueller Engineering-Funktionsumfang

- Der geführte Engineering-Wizard erfasst Geräteklassen, Teilnehmer,
  Systemcluster, Netzarchitektur, Kommunikationssysteme und technische
  Parameter. Lange Agent-Läufe können kontrolliert abgebrochen werden.
- Das kanonische Modell führt Hardware-Knoten, Funktionen, Interfaces,
  Nachrichten und Signale mit Lifecycle-, Review-, Approval- und
  Knowledge-Graph-Beziehungen zusammen. Modellansichten zeigen sowohl die
  funktionale als auch die physische Hardware-/Interface-Struktur.
- Geräteklassen und Fähigkeiten steuern die fachliche Funktionsbildung. Das
  Gateway verwendet vorhandene Teilnehmerverbindungen und erzeugt keine
  künstlichen Duplikate für Sensoren, Aktoren oder ECUs.
- Systemcluster dienen als prüfbare Vorgabe für Netzsegmente. Unterstützt
  werden direkte EVA-/Gateway-Strukturen, ECU-vermittelte Strukturen,
  Gateway-Segmente mit mehreren ECUs sowie ein KI-gestützter Entwurf mit
  importierter Bild-, PDF-, PowerPoint-, SVG- oder Text-Evidence.
- Interfaces werden nach Funktion, Hardware und Netzsegment konsolidiert.
  Nachrichten werden kapazitätsgerecht auf Interfaces gepackt; Signalbreite,
  DLC, Payload, Start-Bit, Byte-Reihenfolge und verfügbare Buskapazität werden
  gemeinsam validiert.
- Signal-Wertcodierungen sind als editierbare Tabelle verfügbar. Definierte,
  reservierte und ungültige Werte sowie Default und Semantik bleiben dabei
  explizit unterscheidbar.
- Die Intelligence-Schicht kombiniert deterministische Plausibilitätsregeln
  mit Random Forest und Gradient Boosting. Vorschläge für fehlende,
  überzählige oder inkonsistente Objekte werden zur Prüfung bereitgestellt und
  erst nach Freigabe in das kanonische Modell übernommen.
- Workflow-Limits, idempotente Fortsetzung und Fortschrittsprüfungen schützen
  vor Endlosschleifen, ungebremster Objekterzeugung und zu großen
  Laufzeit-Eventmengen.

Erstinstallation:

```powershell
uv sync --project backend
Set-Location frontend
npm install
Set-Location ..
```

Anschließend startet der gemeinsame Launcher Backend, Frontend und die
Weboberfläche im Browser:

```powershell
uv run --project backend python generate_realistic_communication_tool.py
```

Für die lokale Workstation-Konfiguration mit CUDA-fähigem Ollama, Waitress und
dem begrenzten Simulationsexecutor kann alternativ direkt gestartet werden mit:

```powershell
.\start-networkis-local-ai.bat
```

Dieser Launcher ist der stabile lokale Startpfad. Er startet nicht nur die
Next.js-Oberfläche, sondern prüft vor dem Frontend auch Projektpfad,
Engineering-Datenbank, Backend-Readiness und feste Ports. `npm run dev` am
Repo-Root verweist deshalb ebenfalls auf diesen Launcher. Ein isolierter
Next.js-Start im Ordner `frontend` ist nur für reine UI-Diagnose gedacht,
weil sonst Workflow, "Neu" und Engineering-Daten ohne Backend/DB instabil
werden.

Der Launcher prüft, ob Ollama unter `http://127.0.0.1:11434` erreichbar und das
Modell `qwen3.8:27b` installiert ist. Der Engineering-Chat läuft über den Python
Agent Core und echte MCP-Aufrufe. Das lokale Modell wird durch `LOCAL_AI_MODEL`
bestimmt. Die empfohlenen Ressourcenvariablen stehen in
`runtime-performance.env.example`. Standardmäßig nutzt das Backend 16
Waitress-Threads und 12 Simulations-Worker im Thread-Modus. Der optionale
Prozessmodus besitzt zusätzliche Spawn- und PID-Sicherungen. NumPy-/BLAS-Threads
sind pro Worker auf eins begrenzt, damit die CPU-Kerne nicht mehrfach
überbucht werden.

Der Python-Agent verwendet den lokalen Modelldienst. Die bisherigen
TypeScript-Schalter für Hybrid-/Cloud-Eskalation steuern diesen Chat nicht.
Änderungen entstehen als validierte Vorschläge und benötigen eine menschliche
Freigabe sowie eine getrennte Übernahme. Details und externe MCP-Konfiguration:
[Engineering Agent und MCP](docs/agent_core/14_MCP_IMPLEMENTATION.md).

### Persistierte Ressourcen- und KI-Konfiguration

Die maschinenbezogene Laufzeitkonfiguration liegt dauerhaft in
`config/networkis.resources.json`. Beide lokalen Launcher und der Start-Doctor
lesen diese Datei; Docker-, Modell- und Ressourcenpfade müssen deshalb nicht
bei jedem Start erneut gesucht werden.

Die Konfiguration enthält:

- Projektpfad, Frontend-/Backend-URLs und feste Ports
- Docker-CLI, Docker-Compose, Docker Desktop, Ollama und Laufzeitverzeichnisse
- Waitress-Threads, Simulationsexecutor und Workerzahl
- das Workflow-Eventlimit sowie Speicherbudgets für Backend, Frontend und
  Trace-Artefakte
- alle KI-Provider mit `enabled`-/`active`-Schaltern (`0` oder `1`), aktivem
  Betriebsmodus, lokalen Modellen und Cloud-Eskalationsstrategie

Für diese Workstation sind insbesondere folgende Docker-Pfade hinterlegt:

```text
C:\Users\marti\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe
C:\Users\marti\.docker\cli-plugins\docker-compose.exe
```

API-Schlüssel werden nicht in der JSON-Datei gespeichert. OpenAI und NVIDIA
verwenden bei Aktivierung weiterhin `OPENAI_API_KEY` beziehungsweise
`NVIDIA_API_KEY` aus der Umgebung. Der Standardwert
`workflow_event_limit: 100000` begrenzt interaktive Workflow-Läufe; größere
Offline-Läufe können bewusst separat konfiguriert werden.

Der kanonische Projektpfad ist `I:\PycharmProjects\My_first_Network_Simulator`.
Details zum Umzug und zu den externen Laufzeitdaten stehen in
`backend/docs/PROJECT_LOCATION.md`.

Die vollständige Beschreibung der Agent-Laufzeit, Provider-Auswahl,
Ressourcennutzung, kompakten Statusdarstellung und des Human-Review-Ablaufs
steht in `backend/docs/AI_AGENT_RUNTIME_AND_REVIEW.md`.

- Oberfläche: `http://127.0.0.1:13500`
- Flask-API: `http://127.0.0.1:15050/api`

Das Engineering-Modell benötigt `DATABASE_URL` für PostgreSQL. Beim ersten
Zugriff wird das versionierte Schema idempotent aufgebaut. Die Readiness ist
unter `http://127.0.0.1:15050/api/engineering/health` sichtbar. KI-Vorschläge
werden getrennt gespeichert und verändern das kanonische Modell nicht direkt.

Der serverseitige KI-Agent verwendet standardmäßig
`http://127.0.0.1:15050/api/engineering`. Für abweichende Deployments kann der
vollständige Engineering-Pfad über `SIMULATOR_ENGINEERING_API_URL` gesetzt
werden. Externe MCP-Clients verwenden für Simulationsjobs dieselbe Anwendungs-API über
`SIMULATOR_JOB_API_URL` (Standard `http://127.0.0.1:15050/api`).

Vor dem Webstart kann der lokale Start-Doctor ohne Nebenwirkungen ausgeführt
werden:

```powershell
backend\.venv\Scripts\python.exe generate_realistic_communication_tool.py doctor
```

Der Doctor prüft Projektpfad, feste Ports, lokale Next.js-Abhängigkeiten,
Docker Engine und den Engineering-Datenbank-Port. Erkennt er den bekannten
Docker-Desktop-Fehler rund um den `dockerInference`-Listener, meldet er diesen
gezielt, statt die Anwendung nur teilweise zu starten. Die Oberfläche sollte
erst geöffnet werden, wenn `/api/engineering/health` bereit ist.

Beide Ports werden exklusiv verwendet. Ist `13500` oder `15050` bereits durch
ein anderes Werkzeug belegt, bricht der Launcher mit einer eindeutigen Meldung
ab, statt unbemerkt einen fremden Dienst zu verwenden oder auf einen anderen
Port auszuweichen. Beim Beenden räumt er den vollständigen Backend- und
Frontend-Prozessbaum auf.

Backend- und Frontend-Ausgaben liegen pro Start unter
`backend/runtime/service-logs/`, auch wenn der Launcher im Hintergrund läuft.

Nur das Backend starten:

```powershell
uv run --project backend python generate_realistic_communication_tool.py backend
```

## MCP-Schnittstellen

Der Server `simulator-engineering-mcp` stellt Engineering-Werkzeuge und
Modellressourcen über das Model Context Protocol (MCP) bereit. Der Python-Agent
nutzt ihn eingebettet über den MCP-SDK-Client; externe Clients können denselben
Server als eigenen Prozess starten:

| Zugang | Verwendung |
|---|---|
| Eingebettet | Interner Engineering-Agent mit serverseitigem Projektkontext |
| stdio | Ein MCP-Client startet den Server und kommuniziert über Standardein-/ausgabe |
| Streamable HTTP | Separater MCP-Server, standardmäßig unter `http://127.0.0.1:15052/mcp` |

### Start und Konfiguration

Voraussetzungen sind die installierten Backend-Abhängigkeiten, die konfigurierte
PostgreSQL-Datenbank und eine vorhandene Projekt-ID. Für Simulationsjobs muss
zusätzlich die Anwendungs-API laufen. `PROJEKT_ID` in den folgenden Befehlen
durch die ID aus dem gewünschten Projektlink ersetzen. Aus dem Projektstamm:

```powershell
# Standardtransport: stdio; normalerweise vom MCP-Client gestartet.
backend\.venv\Scripts\python.exe -m backend.simulator_engineering_mcp --project PROJEKT_ID

# Alternativ: eigener Streamable-HTTP-Server auf Loopback.
backend\.venv\Scripts\python.exe -m backend.simulator_engineering_mcp `
  --project PROJEKT_ID --transport streamable-http --port 15052
```

Für einen stdio-Client das Arbeitsverzeichnis auf den Projektstamm setzen und
folgende Prozesskonfiguration verwenden:

- Programm: `I:\PycharmProjects\My_first_Network_Simulator\backend\.venv\Scripts\python.exe`
- Argumente: `-m`, `backend.simulator_engineering_mcp`, `--project`, `PROJEKT_ID`
- Umgebung: `DATABASE_URL` und bei abweichender API-Adresse `SIMULATOR_JOB_API_URL`
  explizit an den gestarteten Prozess weiterreichen.

| Umgebungsvariable | Bedeutung |
|---|---|
| `DATABASE_URL` | PostgreSQL-Verbindung derselben Simulator-Instanz; erforderlich, keine Zugangsdaten in Client-Konfigurationen veröffentlichen |
| `SIMULATOR_JOB_API_URL` | Anwendungs-API für den zentralen Job-Executor; Standard `http://127.0.0.1:15050/api` |
| `SIMULATOR_ENGINEERING_API_URL` | Engineering-API für den Web-/Agent-Pfad; Standard `http://127.0.0.1:15050/api/engineering`, kein MCP-Endpunkt |

Der externe Server ist für seine Laufzeit an `--project` gebunden. Projekt-ID,
Akteur und Berechtigungen werden serverseitig festgelegt und können nicht durch
Tool-Argumente gewechselt werden. Der HTTP-Start bindet an `127.0.0.1`; Port
`15052` gehört zum separat gestarteten MCP-Prozess.

### Werkzeuge und Ressourcen

Der aktuelle Werkzeugkatalog wird über MCP-Discovery (`tools/list`)
einschließlich Eingabeschemas bereitgestellt. Beispiele:

| Bereich | Werkzeuge (Auswahl) |
|---|---|
| Modell und Fähigkeiten | `inspect_project`, `search_model`, `inspect_object`, `inspect_assistant_capabilities`, `discover_engineering_tools` |
| Modellvorschläge | `create_objects_via_proposal`, `update_object_via_proposal`, `generate_signals`, `generate_messages`, `generate_routing` |
| Prüfung und Kapazität | `validate_signal`, `validate_message`, `calculate_bus_load`, `calculate_capacity`, `evaluate_architecture` |
| Review und Nachvollziehbarkeit | `inspect_proposal`, `validate_proposal`, `apply_approved_proposal`, `inspect_agent_audit` |
| Simulation | `validate_simulation_preflight`, `create_simulation_snapshot`, `start_simulation`, `get_simulation_status`, `stop_simulation`, `get_simulation_results` |
| Trace-Analyse | `get_trace_window`, `analyze_trace`, `correlate_signals`, `compare_golden_trace`, `find_trace_root_cause` |

Tools besitzen einen typisierten Parameter `request`. Beispielsweise erhält
`inspect_project` die MCP-Argumente `{"request": {}}`, `search_model` etwa
`{"request": {"query": "Sensor"}}`. Objekt-IDs aus Suchergebnissen verwenden.
Die strukturierten Antworten enthalten unter anderem `success`, `status`,
`data`, `findings`, `warnings` und `trace_id`. Ein erfolgreicher Tool-Aufruf
belegt noch keinen abgeschlossenen Engineering-Auftrag.

Lesbare MCP-Ressourcen und Ressourcenvorlagen:

| URI | Inhalt |
|---|---|
| `simulator://project/{project_id}` | Projekt und Workflow-Stand |
| `simulator://project/{project_id}/model` | Vollständiges kanonisches Modell |
| `simulator://project/{project_id}/{section}` | `hardware`, `functions`, `interfaces`, `hardware-interfaces`, `signals`, `messages`, `networks`, `routing`, `findings` oder `capabilities` |
| `simulator://schemas/{object_type}` | Schema für `signal`, `message`, `function` oder `hardware-interface` |
| `simulator://technologies/can-fd` | CAN-FD-Payloadklassen und Frameberechnungsdienst |
| `simulator://device-classes` | Geräteklassen aus dem zentralen Register |

### Berechtigungen und Ausführung

Standardmäßig erlaubt der Server Lesen, Vorschläge, Validierung, Simulation,
Trace-Analyse und die Ausführung bereits nutzerautorisierter Engineering-Ziele.
Modellvorschläge durchlaufen Validierung und menschliches Review. Mit
`--allow-apply-approved` darf ein externer Client bereits freigegebene Vorschläge
übernehmen; `--allow-delete-proposals` ergänzt die Berechtigung für Löschungen
mit Auswirkungsanalyse. Eine menschliche Freigabe kann kein MCP-Tool erteilen.
Ein bereits serverseitig freigegebener Engineering-Gesamtplan darf über
`continue_engineering_goal` innerhalb seines gespeicherten Umfangs fortgesetzt
werden.

Simulationen verwenden die Reihenfolge Preflight → unveränderlicher Snapshot →
Start → Status/Ergebnisse/Trace. Der MCP-Server nutzt dafür den bestehenden
Job-Executor der Anwendungs-API. Die Projektbindung ersetzt keine
Benutzerauthentifizierung für einen öffentlich erreichbaren Mehrbenutzerdienst.

Implementierung: [MCP-Server](backend/simulator_engineering_mcp/server.py),
[Startparameter](backend/simulator_engineering_mcp/__main__.py) und
[Werkzeugregistrierung](backend/engineering/agent_tools/services.py).
Weitere Details: [Engineering Agent und MCP](docs/agent_core/14_MCP_IMPLEMENTATION.md)
und [Assistentenfähigkeiten](docs/assistant-capabilities-mcp-2026-09-11.md).

## Docker-Start

Die vollständige lokale Umgebung kann auch als Docker-Setup gestartet werden.
Der App-Container heißt `NetworkIS`; die Engineering-Datenbank läuft als
`NetworkIS-db` und verwendet dieselben lokalen Zugangsdaten wie `DATABASE_URL`.

```powershell
.\start-networkis.bat
```

Geänderten Quellcode vollständig prüfen und das exakt geprüfte Image produktiv
übernehmen:

```powershell
backend\.venv\Scripts\python.exe scripts/release-and-deploy.py
```

Wenn `docker` nicht im `PATH` liegt, verwendet `start-networkis.bat` die in
`config/networkis.resources.json` gespeicherten ausführbaren Dateien. Der
Launcher startet außerdem die nur lokal erreichbare Windows-Hosttelemetrie auf
Port `13502`. Dadurch zeigt der Engineering-Auftrag die aktuelle CPU-, RAM-,
GPU- und VRAM-Auslastung des Rechners statt der Ressourcen des Docker-Containers.
Ist die Hosttelemetrie nicht erreichbar, kennzeichnet die Oberfläche die
Ersatzmessung ausdrücklich als `Container`.

Der normale Start verwendet das bereits installierte Image. Die Lieferung
verwendet ein vollständiges PASS-Protokoll mit passender Quellcode-, Test- und
Git-Identität, führt andernfalls das Release-Gate aus und kontrolliert nach dem
Deployment das laufende Image. Historische Images werden dabei nicht gelöscht.

- Oberfläche: `http://127.0.0.1:13500`
- Backend/API: `http://127.0.0.1:15050/api`
- Logs: `docker logs -f NetworkIS`
- Stoppen: `docker compose -f docker-compose.networkis.yml stop`
- Container und Compose-Netz entfernen: `docker compose -f docker-compose.networkis.yml down`

Die bisherige CLI bleibt als Fallback kompatibel. Verwende den Unterbefehl
`cli`, wenn eine Konsolen-Simulation statt der Oberfläche gewünscht ist:

```powershell
uv run --project backend python generate_realistic_communication_tool.py cli --list-technologies
```

## Architektur

Das Kernmodell trennt vier Ebenen:

```text
Hardware
  └─ physischer Port
       └─ logische Netzwerk-Schnittstelle
            └─ Bus oder Netzwerk
```

Beispiel: Eine ECU kann zwei CAN-FD-Ports, einen LIN-Port und einen
Ethernet-Port besitzen. Auf dem Ethernet-Port können mehrere logische
Schnittstellen mit eigenen VLANs, IP-Adressen und Protokollen liegen.

Die Implementierung ist ebenfalls geschichtet:

```text
CommunicationSimulator
├─ HardwareProfileService
│  ├─ HardwareProfileNormalizer
│  └─ HardwareProfileValidator
├─ TechnologyRegistry
│  └─ branchenspezifische BaseTechnologyGenerator-Klassen
└─ UniversalTraceGenerator
   ├─ JsonLinesTraceWriter
   └─ CsvTraceWriter
```

Der optionale KI-Assistent verwendet zusätzlich eine industriespezifische
Speicherschicht:

```text
IndustryContext
└─ IndustryKnowledgeService
   ├─ IndustryMemoryStore → Industries/<Domain>/Learning/simulation_memory.db
   └─ KnowledgeGraphStore → Industries/<Domain>/Knowledge/knowledge_graph.db
```

Der Knowledge Graph speichert Topologie-, Profil-, Technologie- und
Fehlerbeziehungen. Vollständige Trace-Events verbleiben ausschließlich unter
`backend/runtime/traces/`.

Die Technologieprofile liegen nicht im Simulationsskript, sondern in
`backend/simulator/physic_lib/Industries/<Branche>/generators/technology_generator.py`.
`bus_technologies.py`, `hardware_profile.py` und `universal_trace.py` behalten
ihre bisherigen Funktions-APIs als schlanke Kompatibilitätsfassaden.

Aktuelle Generatorbereiche:

- `Automotive`
- `IndustrialAutomation`
- `EmbeddedSystems`
- `Aerospace`
- `Rail`
- `Marine`
- `BuildingAutomation`
- `Energy`
- `RoboticsROS`
- `Generic`

Ein neuer Fachgenerator erbt von `BaseTechnologyGenerator`, implementiert
`generate()` und wird in `TechnologyRegistry.DEFAULT_GENERATORS` registriert.

## Unterstützte Verbindungstypen und Technologien

Die zentrale Registry enthält **125 einzeln geprüfte Technologieprofile**.
Die folgende Liste wird nach Protokollschicht gegliedert. Branchen beeinflussen
Empfehlungen und Vorlagen, begrenzen aber nicht die Technologieauswahl.
Ein gemischtes Projekt führt Parameter und Nachweise je Technologie, Netz und
Geräteanschluss getrennt. Ethernet wird beispielsweise nicht als NMEA-2000-
oder I²C-Verbindung bewertet.

- **Physikalische Verbindungen:** ADC, DAC, GPIO, LVDS, PWM, RS-232, RS-422, RS-485.
- **Bus- und Sicherungsschichten:** 5G, ARINC 429, Bluetooth LE, CAN 2.0A/B, CAN-FD, CAN XL, Ethernet, FlexRay, Generic CAN, Generic Ethernet, Generic Serial, I2C, I3C, LIN, LTE-M, MIL-STD-1553, MIPI CSI-2, MIPI DSI, MOST, MVB, NB-IoT, NFC, 1-Wire, PCIe, POWERLINK, PROFIBUS DP, PROFIBUS PA, PROFINET RT/IRT, Sercos III, SpaceWire, SPI / separately qualified QSPI, UART / USART, USB, UWB, Wi-Fi, WTB.
- **Netzwerkschichten:** Internet Protocol, Thread.
- **Transportschichten:** TCP, UDP.
- **Anwendungsprotokolle:** AMQP, BACnet/IP, BACnet MS/TP, BACnet/SC, CANopen, CCP, CoAP, Custom Binary, Custom Protocol, Custom TCP, Custom Text, Custom UDP, DALI, DDS, DNP3, DoIP, EtherNet/IP, FOUNDATION Fieldbus H1, FSoE, GOOSE, HTTP, IEC 60870-5-101, IEC 60870-5-104, IEC 61162, IEC 61850, SAE J1939, M-Bus, Matter, MMS, Modbus ASCII, Modbus RTU, Modbus TCP, MQTT, MQTT-SN, NMEA 0183, OCPP, OPC UA Client/Server, OPC UA PubSub, IEC 61850 Sampled Values, SOME/IP, SOME/IP-SD, TRDP, UDS, WebSocket, Wireless M-Bus, WirelessHART, XCP, Zigbee.
- **Anwendungsprofile:** ARINC 664 / AFDX, AVB, CAN Aerospace, CC-Link, CC-Link IE, CIP Safety, DeviceNet, Ethernet Train Backbone, EtherCAT, HART (wired), INTERBUS, IO-Link, IO-Link Wireless, ISO 11783 / ISOBUS, KNX IP, KNX RF, KNX TP, LonWorks, LoRaWAN, NMEA 2000, OBD-II, openSAFETY, PROFIsafe, RFID, ROS 2, Sparkplug B, SunSpec Modbus, Time-Sensitive Networking, Time-Triggered Ethernet.

### Parameter, Standardvorschläge und Nachweise

- Wizard, Parametereditor und API verwenden das profilgebundene Schema. Die
  Technologieauswahl bietet eine Suche über den vollständigen Katalog.
- Literaturwerte werden als überprüfbare Vorschläge angeboten. Bedingte Werte
  gelten nur bei passender Betriebsart, Version und Gerätekonfiguration; bei
  I²C ist Standard-mode mit 100 kbit/s der bekannte Basismodus. Es werden
  weder fremde CAN-Werte noch eine erfundene Gerätefrequenz eingesetzt.
- Ein vorhandener bestätigter Wert bleibt erhalten. Geräteadresse, tatsächliche
  Verkabelung, Clock-Stretching, Arbitration, Transaktionsumfang, Security und
  gemessene Verzögerungen brauchen eigene Quellen und Bestätigung.
- Der Geräteeditor bewahrt unveränderte Bestätigungen und zeigt Standardvorschläge
  als unbestätigt. Eine Änderung der Gerätewerte oder Frequenz erfordert eine neue
  Bestätigung. Bei fehlenden Wizard-Nachweisen werden die konkreten Profilfelder
  und der Weg zu ihrer Bearbeitung angezeigt.
- Der vollständige Technologiekatalog wird pro Registry-Revision bereitgestellt.
  Bei einem Dienstausfall erscheint eine Fehlermeldung mit erneutem Ladeversuch;
  ein kleinerer Entwicklungskatalog ersetzt ihn nicht.
- Einzelne geprüfte Werte können gespeichert werden, während andere Angaben
  offen bleiben. Der Simulator-Export erhält alle zum gewählten Profil gehörenden
  Felder, ihren Prüfstatus und ihre Herkunft; ein Teilnachweis gibt keine Kapazität
  oder Simulation frei.
- Große ganzzahlige Protokollwerte werden im Browser als Dezimaltext verlustfrei
  gespeichert; die Python-Prüfung berechnet sie als exakte Ganzzahlen.
- Bestätigung einer Busfrequenz ist kein Kapazitätsnachweis. Kapazität und
  Schedule werden getrennt von funktionaler Deadline, Datenalter und
  Fehlerreaktion geprüft. I²C unterscheidet Controller-Port, Target-Port und
  Transaktion; ein Controller-Port benötigt keine erfundene Slave-Adresse.

### Ausführbarer Umfang

| Fähigkeit | Bedeutung |
|---|---|
| Profil und Parameterprüfung | Literatur- und implementierungsbezogene Felder, Grenzen und Abhängigkeiten; keine Hardwarezertifizierung. |
| `MODEL_AVAILABLE` | Ein registriertes Kapazitätsmodell existiert; Berechnung setzt den tatsächlichen, vollständigen und bestätigten Projekt-Nachweis voraus. |
| `MODEL_MISSING` | Profil kann ausgewählt und geprüft werden; Kapazität oder vollständige Protokollausführung wird als fehlend gemeldet. Es gibt keinen Ersatz durch CAN oder Ethernet. |
| `NOT_APPLICABLE` | Direkte I/O-Verbindung; kein Buslastmodell. Geräte-, Prozess- und Funktionsnachweise bleiben erforderlich. |
| `PARTIAL` / `EXPERIMENTAL` | Umfang des integrierten Modells; keine Aussage über Reife oder Normkonformität der Bus-Technologie selbst. |

Kapazitätsmodelle sind registriert für: CAN 2.0A/B, CAN-FD, Ethernet, I2C, LIN, SPI / separately qualified QSPI.
Direkte I/O-Verbindungen ohne Buslastmodell: ADC, DAC, GPIO, PWM.
Alle anderen hier aufgeführten Profile bleiben ohne ausführbaren
Kapazitätsnachweis `MODEL_MISSING`. Beispiele sind Matter, M-Bus, Wireless
M-Bus, WirelessHART, MIL-STD-1553, WTB, XCP und Zigbee. Ihre überprüften
Parameter und Mechanismen installieren keinen PHY-, Security- oder Schedule-
Executor und ersetzen keine Geräte- oder Systemzertifizierung.

Benutzerdefinierte Technologiepakete ergänzen die Registry mit geprüften
Beschreibungen und Parameterschemata. Sie installieren keinen ausführbaren
Kapazitätscode; ihr Kapazitätsstatus bleibt `MODEL_MISSING`.

Quellen, einzelne Parameterentscheidungen und Tests:
[Prüfprotokoll aller Technologieprofile](docs/implementation-workloads/technology-full-parameter-audit-20261001/progress.json).
Die Einzelprüfungen beziehen sich auf die dort dokumentierten Quellen,
Editionen und Implementierungen; sie behaupten keine vollständige Zertifizierung
aller optionalen Normteile.

Native Dateiformate sind technologieabhängig. Ein neutraler JSONL-/CSV-Trace
ist eine gemeinsame Darstellung und beweist keine native Bus-Ausführung.

| Bereich | Native Formate |
|---|---|
| CAN/CAN FD | BLF, DBC, ASC, TRC, CSV, JSON, XML, YAML, ARXML, FIBEX |
| CAN XL | universeller Trace; CAN-FD-kompatible BLF-Ausgabe bildet keine native CAN-XL-Datei |
| Ethernet/IP-basierte Technologien | PCAP und PCAPNG im jeweils implementierten Writer-Umfang |
| Messdaten | optional MDF und MF4 |
| andere Technologien | neutraler JSONL-/CSV-Trace im ausführbaren Modellumfang |

### Verifizierte Produktivübernahme

`python scripts/release-and-deploy.py` prüft den vollständigen Release-Gate
mit isolierter SQL-Datenbank und temporärer Laufzeit. Es übernimmt ausschließlich
das exakt getestete Image aus einem vollständigen PASS-Nachweis und prüft
danach Image-Identität und Betriebsbereitschaft. Ein Neustart eines alten Images
ist keine Übernahme von Codeänderungen. Historische Images werden ohne
dokumentierten Aufbewahrungsnachweis nicht gelöscht.

## Installation

Voraussetzungen:

- Python 3.12 oder 3.13 (siehe `backend/pyproject.toml`)
- `uv` empfohlen

```powershell
uv sync --project backend
```

Alternativ:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install python-can openai
```

MDF/MF4 benötigen zusätzlich:

```powershell
python -m pip install asammdf
```

## Schnellstart

Für die grafische Konfiguration ist die Weboberfläche der Standard-Einstieg:

```powershell
python generate_realistic_communication_tool.py
```

Die technologieoffene CLI bleibt für automatisierte oder terminalbasierte
Läufe verfügbar:

```powershell
python generate_realistic_communication_tool.py cli
```

Ohne Parameter führt sie interaktiv durch:

1. technologieoffene Standalone-Simulation oder native CAN/Ethernet-Ausgabe
2. Branche und eine der 54 Technologien des älteren CLI-Katalogs
3. Bitrate und Anzahl der Hardware-Knoten
4. Dauer, Zyklus und Payload-Größe
5. Seed und maximales Eventlimit
6. Dropout- und Korruptionswahrscheinlichkeit
7. Ausgabeformate und Zielordner

Alle Technologien anzeigen:

Die Weboberfläche und die Engineering-API verwenden die zentrale Registry mit
125 Profilen. Der ältere Standalone-CLI-Katalog enthält 54 Einträge; diese
Kataloggröße beschreibt keine zusätzliche Simulations- oder Kapazitätsfreigabe.

```powershell
python generate_realistic_communication_tool.py cli --list-technologies
```

Nicht-interaktive Aerospace-Konfiguration prüfen:

Die folgenden ARINC-429- und Modbus-TCP-Beispiele prüfen die Topologie mit
`--validate-only`. Ihr Kapazitätsmodell ist `MODEL_MISSING`; sie erzeugen damit
keinen Simulationstrace.

```powershell
python generate_realistic_communication_tool.py cli `
  --technology arinc429 `
  --industry Aerospace `
  --bitrate 100000 `
  --nodes 3 `
  --duration 5 `
  --cycle-ms 20 `
  --payload-bytes 4 `
  --max-events 10000 `
  --dropout-probability 0.01 `
  --corruption-probability 0.001 `
  --formats universal-jsonl,universal-csv `
  --out-dir aerospace_demo `
  --validate-only
```

Industrial-Automation-Konfiguration prüfen:

```powershell
python generate_realistic_communication_tool.py cli `
  --technology modbus_tcp `
  --nodes 4 `
  --cycle-ms 50 `
  --payload-bytes 64 `
  --duration 10 `
  --out-dir modbus_demo `
  --validate-only
```

Der bisherige native CAN/Ethernet-Pfad bleibt erreichbar:

```powershell
python generate_realistic_communication_tool.py cli `
  --native-cli `
  --bus fd `
  --formats blf,dbc,asc `
  --out-dir native_can_demo
```

Konfigurationsvorlage erstellen:

```powershell
uv run --project backend python backend/simulator/communication_simulator.py `
  --write-config-template simulation_config.json
```

Simulation starten:

```powershell
uv run --project backend python backend/simulator/communication_simulator.py --config simulation_config.json
```

Technologiekatalog anzeigen:

```powershell
uv run --project backend python backend/simulator/communication_simulator.py --list-technologies
```

Nur Topologie und Hardware validieren:

```powershell
uv run --project backend python backend/simulator/communication_simulator.py `
  --config simulation_config.json `
  --validate-only
```

Relative CLI-Ausgabeordner werden unter `traces/` abgelegt. Web-Läufe werden
isoliert unter `backend/runtime/traces/` gespeichert. Absolute Zielpfade
werden respektiert.

## Standalone-Konfiguration

Diese gemischte Konfiguration veranschaulicht die Objektstruktur. Für eine
Simulation müssen die nativen Parameter und Geräte-/Transaktionsnachweise
jedes verwendeten Busses vollständig vorliegen. Insbesondere reicht der unten
angegebene I²C-Takt allein dafür nicht aus.

```json
{
  "schema": "communication-simulator.simulation-config.v1",
  "name": "multi_bus_system",
  "output_dir": "multi_bus_system",
  "duration_s": 2.0,
  "seed": 42,
  "formats": [
    "universal-jsonl",
    "universal-csv",
    "blf",
    "dbc",
    "pcapng"
  ],
  "networks": [
    {
      "id": "control_can",
      "technology": "can_fd",
      "arbitration_bitrate": 500000,
      "data_bitrate": 2000000
    },
    {
      "id": "sensor_bus",
      "technology": "i2c",
      "bitrate": 400000
    }
  ],
  "hardware": [
    {
      "id": "controller",
      "type": "ecu",
      "health": "nominal",
      "ports": [
        {
          "id": "controller_can1",
          "physical_type": "can",
          "network_interfaces": [
            {
              "id": "controller_can_if",
              "technology": "can_fd",
              "network": "control_can",
              "channel": 0
            }
          ]
        },
        {
          "id": "controller_i2c0",
          "physical_type": "i2c",
          "network_interfaces": [
            {
              "id": "controller_i2c_if",
              "technology": "i2c",
              "network": "sensor_bus",
              "address": "controller"
            }
          ]
        }
      ]
    }
  ],
  "communications": [
    {
      "id": "temperature",
      "sender_interface": "sensor_i2c_if",
      "receivers": ["controller_i2c_if"],
      "cycle_ms": 100,
      "payload_bytes": 4
    }
  ]
}
```

Wenn `communications` fehlt, erzeugt der Simulator für Netzwerke mit mindestens
zwei Schnittstellen reproduzierbare Standardrouten.

## Eigene Bus-Technologie

```json
{
  "technology_profiles": [
    {
      "id": "vendor_bus_x",
      "kind": "bus",
      "family": "custom",
      "medium": "fiber",
      "topology": "ring",
      "access": "time_triggered",
      "addressing": "node_id",
      "default_bitrate": 25000000,
      "max_payload_bytes": 128,
      "native_formats": []
    }
  ],
  "networks": [
    {
      "id": "vendor_network",
      "technology": "vendor_bus_x"
    }
  ]
}
```

Ein eigener Katalogeintrag beschreibt Payload-Grenzen und Technologiemetadaten.
Er installiert keinen Timing-Executor. Ohne registrierte Technologie und
ausführbares Modell bleibt die Übertragungszeit unbestätigt; eine produktive
Simulation ersetzt sie nicht durch generische CAN- oder Ethernet-Annahmen.

## Python-API

```python
from communication_simulator import CommunicationSimulator

simulator = CommunicationSimulator()
result = simulator.run(
    {
        "schema": "communication-simulator.simulation-config.v1",
        "output_dir": "api_demo",
        "duration_s": 1,
        "formats": ["universal-jsonl", "universal-csv"],
        "networks": [{"id": "serial", "technology": "rs485"}],
        "hardware": [
            {
                "id": "controller",
                "ports": [
                    {
                        "id": "rs485_a",
                        "network_interfaces": [
                            {
                                "id": "controller_if",
                                "technology": "rs485",
                                "network": "serial",
                            }
                        ],
                    }
                ],
            }
        ],
    }
)

print(result["status"])
print(result["artifacts"])
```

Die bisherige Funktion `run_simulation(config)` bleibt weiterhin verfügbar.

## Ausgabe

```text
traces/<lauf>/
  traces/
    universal_trace.jsonl
    universal_trace.csv
  native/
    traces/
    datenbasen/
    generation_manifest.json
    simulation_interface.json
  generation_manifest.json
  simulation_result.json
```

`generation_manifest.json` enthält:

- Hardware-, Port-, Schnittstellen- und Netzwerkanzahl
- verwendete Technologien
- Validierungsbefunde
- Routen- und Eventanzahl
- erzeugte Artefakte
- Status der nativen Writer

## Hardwarevalidierung

Die Validierung verändert importierte Definitionen nicht. Sie meldet:

- doppelte Hardware-, Port-, Schnittstellen- oder Netzwerk-IDs
- Schnittstellen ohne Netzwerk
- Verweise auf unbekannte Netzwerke
- Ports ohne logische Schnittstelle
- Hardware ohne Ports
- ungenutzte Netzwerke
- Technologien ohne integriertes oder benutzerdefiniertes Profil

## Native CAN-/Ethernet-Werkzeuge

`generate_realistic_communication_tool.py` bleibt als spezialisierter nativer
Writer erhalten. Sein öffentlicher Konfigurationseinstieg ist neutral:

```powershell
uv run --project backend python generate_realistic_communication_tool.py `
  --write-config-template native_config.json

uv run --project backend python generate_realistic_communication_tool.py `
  --config native_config.json
```

Für Python-Integrationen ist `backend/simulator/communication_simulator.py`
der primäre Einstieg.

## Projektstruktur

```text
generate_realistic_communication_tool.py   gemeinsamer CLI-/Web-Launcher
backend/
  app/                                     Flask-API und Hintergrundjobs
  simulator/                               Simulationskern und native Writer
  tests/                                   Backend-Regressionstests
  runtime/traces/                          isolierte Web-Laufzeitausgaben
  docs/                                    technische Projektdokumentation
frontend/
  src/app/                                 Next.js App Router
  src/components/                          Assistent und Ergebnisanzeige
  src/lib/                                 API-Client und TypeScript-Typen
config/
  networkis.resources.json                 persistierte Laufzeit-/KI-Ressourcen
```

## Prüfung

Backend, Frontend-Spezifikationen und TypeScript können unabhängig geprüft
werden:

```powershell
backend\.venv\Scripts\python.exe scripts/run-isolated-tests.py -- backend/tests -q

Set-Location frontend
npm run test:specification
npm run test:intelligence
npm run test:capacity
npx tsc --noEmit
Set-Location ..
```

SQL-Prüfungen verwenden ausschließlich die vom Launcher erzeugte temporäre
Datenbank. Für die vollständige Abnahme einschließlich echter Wizard-, HTTP-,
Neustart- und Simulationstests mit anschließender produktiver Lieferung:

```powershell
backend\.venv\Scripts\python.exe scripts/release-and-deploy.py
```

Weiterführend:

- [Standalone-Schnittstelle](backend/docs/SIMULATION_INTERFACE.md)
- [Hardware- und Netzwerkmodell](backend/docs/HARDWARE_INTERFACE_ROADMAP.md)
- [Industrieneutrale Architektur](backend/docs/INDUSTRY_NEUTRAL_SIMULATOR.md)
- [Format-Writer](backend/simulator/format_generators/README.md)
- [Aktueller Stand](backend/docs/CURRENT_STATUS.md)
- [AI-/RAG-Implementierungsstand](backend/docs/IMPLEMENTATION_STATUS.md)

## Grenzen

- Das universelle Traceformat kann verschiedene Technologieidentitäten führen.
  Das Erzeugen zeitbewerteter Ereignisse benötigt trotzdem ein ausführbares
  Modell und die passenden Nachweise; ein binäres natives Herstellerformat
  benötigt zusätzlich einen eigenen Writer.
- CAN XL wird vom vorhandenen BLF-Writer noch nicht als natives
  CAN-XL-Frameobjekt unterstützt.
- Das Zeit- und Fehlermodell ist synthetisch und reproduzierbar, aber kein
  zertifiziertes Anlagen- oder Physikmodell.
