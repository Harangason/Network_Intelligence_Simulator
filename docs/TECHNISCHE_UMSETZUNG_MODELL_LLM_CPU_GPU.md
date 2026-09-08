# Technische Umsetzungszusammenfassung

## Engineering-Modell, Signalkette, LLM-, CPU- und GPU-Ausführung

**Stand:** 8. September 2026  
**Repository:** `My_first_Network_Simulator`  
**Bezugsstand:** `8fe1508` (`Busbestände global reservieren und Start entkoppeln`)

## 1. Zweck und Systemgrenze

Der Network Simulator verbindet eine versionierte Engineering-Datenhaltung mit
einem geführten Projektaufbau, technologieabhängiger Lastberechnung,
Simulation und Auswertung. Das kanonische Engineering-Modell ist die einzige
Source of Truth. Darstellungen im Netzwerk-Editor, LLM-Antworten,
RAG-Treffer, Capacity-Szenarien und Simulationsergebnisse sind davon
abgeleitete Sichten oder prüfpflichtige Vorschläge.

Der verbindliche Ablauf lautet:

```text
Anforderung / Import
    -> geführte Spezifikation und Systemcluster
    -> Engineering-Modell
    -> Routing-Tabelle
    -> physische Netzwerktopologie
    -> Technologieparameter
    -> Capacity & Timing
    -> Validation / Preflight
    -> Simulation
    -> Results / Analysis
    -> Data Science & Intelligence
```

Jeder Schritt wird projektgebunden persistiert. Änderungen an einer Quelle
markieren abhängige Ergebnisse als `OUTDATED`; sie werden nicht stillschweigend
gelöscht. Parameter bleiben als explizite Nutzervorgaben erhalten.

## 2. Modellierung von der Hardware bis zum Signal

### 2.1 Kanonische Ebenen

Die fachliche Containment-Kette ist:

```text
HardwareNode
  ├─ HAS_HARDWARE_INTERFACE -> HardwareNetworkInterface
  └─ HAS_FUNCTION           -> Function
       └─ HAS_INTERFACE     -> Interface
            └─ HAS_MESSAGE  -> Message
                 └─ CONTAINS_SIGNAL -> Signal
```

Die zusätzliche physische Schnittstelle ist absichtlich von der funktionalen
Schnittstelle getrennt:

- `HardwareNetworkInterface` beschreibt den realen Controller-/Port-Kanal,
  seine Technologie, Bitraten, Netzreferenz, Kanalnummer, Fähigkeiten und
  Lastgrenzen.
- `Interface` beschreibt den funktionalen Kommunikationszugang einer Funktion.
  Bei einfachen Geräten der Klassen 0–2 darf sie direkt am Hardwareknoten
  hängen; ansonsten gehört sie zur Funktion.
- `Message` verweist sowohl auf die funktionale Schnittstelle als auch – wenn
  vorhanden – auf das physische Hardware-Interface.

| Ebene | Verbindlicher Parent | Zentrale technische Daten |
| --- | --- | --- |
| `HardwareNode` | – | Gerätetyp/-klasse, Produkt-/Hardware-/Softwaredaten, Ports, Diagnoseadressierbarkeit, Logical Node Address |
| `HardwareNetworkInterface` | `HardwareNode` | Technologie, Kanal, physisches Netz, Nominal-/Datenbitrate, Fähigkeiten, Message-Referenzen, statische und Laufzeitlast |
| `Function` | `HardwareNode` | Funktionsname, Domäne, Beschreibung und Hardwarebesitz |
| `Interface` | `Function` oder einfacher `HardwareNode` | Interface-Typ und funktionale Konfiguration |
| `Message` | `Interface` | Message-ID, TX/RX-Richtung, Zykluszeit, DLC, Transportkonfiguration, physisches Interface |
| `Signal` | `Message` | Semantik, Wertebereich, Kodierung, Bitposition, Einheit, Produzent/Consumer, Qualität und Protokollbindung |

Die Repository-Schicht prüft den direkten Parent vor der Anlage und schreibt
Fremdschlüssel und typisierte Relation in derselben PostgreSQL-Transaktion.
Damit kann kein Signal ohne Nachricht und keine Nachricht ohne Interface als
kanonisches Objekt entstehen.

### 2.2 Governance und Versionierung

Alle kanonischen Objekte tragen neben ID, Name und Domäne mindestens:

- `version` und unveränderliche Versions-Snapshots,
- `lifecycle_state`,
- `source` und `provenance`,
- `confidence`,
- `review_state` und `approval_state`,
- Ersteller/Änderer und Zeitstempel.

Direktes generisches CRUD akzeptiert keine Anlage mit
`source=ai_generated`. Ein KI-Ergebnis wird zuerst als `AIProposal` gespeichert,
validiert, dem Menschen zur Prüfung gezeigt und erst nach expliziter Freigabe
angewendet:

```text
Analyse / Generierung
    -> Proposal
    -> deterministische Validierung
    -> Human Review
    -> Approval
    -> Apply auf das kanonische Modell
```

Diese Grenze ist nicht nur eine Prompt-Regel, sondern wird in Services,
Berechtigungen und Persistenz erzwungen.

### 2.3 Erzeugung des Engineering-Modells

Der geführte Auftrag erzeugt zunächst eine strukturierte Spezifikation. Der
Python-Generator ruft dafür den vorhandenen TypeScript-Domänengenerator über
Node.js auf. Dieser Ablauf ist bewusst deterministisch und besteht aus:

1. Domäne und Modelltyp erkennen.
2. Hardware-, Funktions-, Kommunikations- und Mengenangaben extrahieren.
3. erkannte Systemnamen normalisieren und Domänen-Aliase kanonisieren;
   gleiche Kombinationen aus Gerätetyp und normalisiertem Namen deduplizieren.
4. Domänenkataloge ergänzen, bis die bestätigten Sollwerte erreicht sind.
5. bei ausgeschöpftem Katalog semantisch unterschiedliche Rollen wie
   `PrimaryFeedback`, `SafetyFeedback`, `PrimaryCommand` oder
   `DiagnosticsCoordinator` erzeugen – keine bloßen nummerierten Kopien.
6. den bestätigten Systemcluster-Graph auf Controller, lokale I/O-Netze und
   Backbone-Netze anwenden.
7. Signalmodell vervollständigen und Signale in Nachrichten packen.
8. ein validierbares, idempotent wiedererkennbares Proposal für die gesamte
   Objektkette erzeugen.

Die Vollständigkeitsregel des Wizards behandelt Hardware-Sollwerte bei
`completenessFirst` als Mindestumfang und nicht als fachliche Obergrenze. Ein
ausgewähltes System darf deshalb um notwendige Low-Level-Klassen, Sensoren,
Aktoren und Signale ergänzt werden. Für Fahrerassistenz ist zusätzlich ein
Mindestumfang aus Fahrerassistenz-, Kamera-, Radar- und
Ultraschallverarbeitung sowie den zugehörigen Umfeldsensoren implementiert.

Wichtig: Die allgemeine Fachvollständigkeit wird weiterhin katalog- und
regelbasiert hergestellt. Sie ist kein mathematischer Beweis, dass für jede
denkbare Domäne jeder Controller mindestens einen Sensor und Aktor besitzt.
Neue Domänen benötigen entsprechende Katalog-/Coverage-Regeln.

### 2.4 Signalebene

Ein erzeugtes Signal besteht nicht nur aus einem Namen. Die Spezifikation
liefert folgende Ebenen:

| Bereich | Inhalt |
| --- | --- |
| Semantik | `semantic_type` (`NUMERIC`, `BOOLEAN`, `STATE`, `ENUM`, `COUNTER`), Bedeutung, Größe/Kategorie, Einheit, Annahmen |
| Wertedomäne | Minimum, Maximum, Auflösung, erlaubte Werte, Enum-Codes, reservierte/ungültige Werte, Default |
| Kodierung | Rohdatentyp, signed/unsigned, Bitlänge, Startbit, Endianness, Faktor, Offset, linear/coded |
| Kommunikation | Produzent, Consumer, Zykluszeit und Update-Typ |
| Qualität | Confidence sowie Vollständigkeit von Semantik, Wertedomäne, Kodierung und Packing |
| Protokollbindung | Payload-Element, Quell-Hardware, Technologiebindung, Datentyp, Größe, Einheit und Encoding |

Für intelligente Geräte sowie Kamera-, Radar-, Lidar- und vergleichbare
Sensorik werden bis zu fünf prüfbare Signale je Grundkette erzeugt: das
fachliche Basissignal sowie `Status`, `Health`, `Quality`, `AliveCounter` und
`Mode`. Diskrete Zustände besitzen explizite Codes für Normal-, Warn-, Fehler-
und ungültige Zustände; deshalb kann die Simulation lesbare Werte wie
`STANDBY (3)` statt nur `3 code` anzeigen.

Die Packlogik:

- berechnet die notwendige Bitbreite aus Wertebereich, Faktor, Offset und
  Vorzeichen,
- sortiert Signale stabil,
- weist fortlaufende Startbits zu,
- wählt die kleinste gültige Nutzlastklasse (einschließlich CAN-FD-DLC),
- eröffnet bei überschrittener Payload eine weitere Nachricht,
- verwendet vorhandene Interface-Kapazität bis zur Zielbelegung von 60 Prozent
  und eröffnet danach einen weiteren Kanal,
- dokumentiert belegte, freie und verfügbare Bits sowie die prognostizierte
  Message- und Interfacelast.

### 2.5 Routing und physische Topologie

Nach Freigabe des Modells erzeugt ein deterministischer Generator die Routen
aus dem bestätigten Besitzgraphen. Sensoren liefern an ihren fachlichen
Controller, Controller bedienen Aktoren und kommunizieren über den gewählten
Backbone. Lokale LIN-/CAN-/andere I/O-Technologien bleiben dabei lokale Netze;
sie werden nicht künstlich als eigener Gateway-Pfad interpretiert.

Der Netzwerk-Generator übernimmt ausschließlich freigegebene, gültige Routen.
Kanten gleicher physischer Verbindung werden dedupliziert und behalten die
Liste aller beitragenden Route-IDs. Stabile Signaturen aus Prompt und
Modellstand verhindern die erneute Anlage desselben Wizard-Pakets.

Die Topologie-Synchronisierung ordnet Editor-Knoten kanonischen
`HardwareNode`-Objekten, Ports Interfaces und Leitungen `CONNECTED_TO`-Relationen
zu. Sie wird pro Topologie serialisiert und verwendet stabile IDs, damit zwei
Browser oder wiederholte Synchronisationen keine Duplikate erzeugen.

### 2.6 Capacity-gesteuerte Netzkorrektur

Capacity & Timing berechnet technologiespezifisch Average-, Peak- und
Burstlast, Reserve, Übertragungs-, Queueing-, Gateway- und
End-to-End-Latenzen. Unterstützt werden unter anderem CAN, CAN FD, LIN,
FlexRay und Ethernet; unbekannte Technologien erscheinen sichtbar als
`GENERIC_ESTIMATE`.

Bei Überlast wird nicht pauschal der Grenzwert erhöht. Der betroffene physische
Zweig wird gezielt analysiert:

1. Routen nach System-/Controller-Besitz gruppieren.
2. innerhalb der Gruppen mit First-Fit-Decreasing bis zur Zielbuslast packen.
3. Cluster gemeinsam halten; nur zu große Cluster über mehrere Segmente teilen.
4. bestätigte, projektweite Busbestände global reservieren.
5. falls weitere Segmente derselben Technik frei sind: denselben Bustyp teilen.
6. andernfalls alternative Techniken anhand Nutzlastgrenze, Framing, Bitrate,
   prognostizierter Last und freiem Bestand bewerten.
7. eine Technikmigration nur als Review-Vorschlag ausgeben, weil Interfaces,
   Gateway-Ports, Timing und Safety erneut bestätigt werden müssen.

Sichere Aufteilungen derselben Technik können als governte Topologieänderung
materialisiert werden. Nicht erfüllbare Einzelrouten, fehlende Busbestände und
bereits überprovisionierte Segmente bleiben als explizite Restbedingungen
sichtbar.

## 3. RAG und projektübergreifendes Lernen

### 3.1 Kanonisches Hybrid-RAG

Der RAG-Pfad indexiert beim Abruf bis zu 1.000 aktuelle Objekte je
Objekttabelle und bis zu 5.000 typisierte Relationen des aktuellen Projekts. Er
kombiniert:

```text
Keyword + Vektor + Metadaten + Graph
    -> Merge
    -> Deduplizierung
    -> Reranking
    -> Graph-Erweiterung bis Tiefe 3
    -> begrenzter Engineering-Kontext
```

Jeder Treffer enthält Objekt-ID/-typ, Score, Retrieval-Quellen, Begründung,
Quelle, Version und Evidenz. Freigegebene oder geprüfte Daten erhalten ein
höheres Wissensniveau als rohe oder KI-generierte Inhalte.

Der aktuelle lokale Vektorpfad nutzt ein deterministisches, gehashtes
Engineering-Embedding (`local-hashed-engineering-embedding-v2`). Eine
gewichtete deutsch/englische Fachvokabularkarte bringt beispielsweise
„Schnittstelle zuordnen“ und `HAS_INTERFACE` in denselben semantischen Raum.
Das ist lokal reproduzierbar, aber kein neuronales Embedding-Modell. Der
Providervertrag erlaubt später pgvector, Qdrant, FAISS oder gehostete
Embedding-/Reranking-Modelle, ohne die kanonische Persistenz zu ändern.

### 3.2 Lernen bestätigter Controller-Zuordnungen

Die im Wizard bestätigten oder abgelehnten Sensor-/Aktor-Zuordnungen werden
projektübergreifend wiederverwendet:

- maximal 500 zuletzt geänderte Projekte werden als Retrieval-Korpus gelesen,
- explizit bestätigtes Feedback erhält Gewicht `+4`, abgelehntes `-6`,
- bereits übernommene Wizard-Zuordnungen liefern zusätzlich Gewicht `+1`,
- Namen werden Unicode-normalisiert, von Akzenten befreit, kleingeschrieben und
  um numerische Instanzsuffixe bereinigt,
- vorgeschlagen wird nur ein im neuen Projekt tatsächlich vorhandener
  Controller,
- nur ein eindeutig bester positiver Score wird übernommen; Gleichstände
  bleiben zur manuellen Klärung offen,
- Confidence, Evidenzanzahl und Quellprojekte werden mit dem Vorschlag geliefert,
- je Projekt werden höchstens 2.000 explizite Feedback-Datensätze gehalten.

Das ist Retrieval-gestütztes Erfahrungslernen, kein Fine-Tuning der LLMs. Die
aktuelle Zuordnungswiederverwendung arbeitet nach normalisierter exakter
Endpoint-Identität. Ein vollständig neuer, nur sinngleicher Signalname benötigt
weiterhin das allgemeine semantische RAG oder eine manuelle Bestätigung.

### 3.3 Industrie-RAG für Signalgenerierung

Signalquellen werden nach Industriepartitionen getrennt, beispielsweise
`automotive`, `industrial_automation`, `aerospace`, `energy`,
`building_automation`, `embedded_systems` oder `generic`. Importierte
Signallisten werden als aggregierte Korpusprofile mit Mengen, Tag-Verteilungen
und Namensmustern gespeichert; rohe Signalnamen werden dabei nicht dauerhaft
in den RAG-Index kopiert. RAG-Evidenz bleibt beratend und kann weder Objekte
freigeben noch einen Workflow-Schritt abschließen.

## 4. Technische LLM-Umsetzung

### 4.1 Aktiver Engineering-Chatpfad

Der Server erzeugt für jeden Engineering-Chatlauf einen
`LocalEngineeringReasoner`. Er spricht Ollamas native
`POST /api/chat`-Schnittstelle über eine lokale, OpenAI-kompatibel konfigurierte
Basis-URL an. Nicht-lokale Hostnamen werden vom Reasoner abgelehnt.

Die Modellwahl ist regelbasiert:

| Anfrage | Modell | Keep-alive |
| --- | --- | --- |
| strukturierter Wizard-Auftrag mit Cluster-Graph | `llama3.1:8b` | 30 Minuten |
| semantische Klassifizierung/Zuordnung/RAG bis 16.000 Zeichen | `llama3.1:8b` | 30 Minuten |
| komplexe oder längere Engineering-Aufgabe | `qwen3.8:27b` | 10 Minuten |

Weitere tatsächliche Inferenzparameter:

- `think: false` und zusätzlich `/no_think` am Ende der letzten Nutzerfrage,
- Temperatur `0.2`,
- maximal `1.600` erzeugte Tokens,
- Standardtimeout `600 s`, technisch begrenzt auf `90–1.200 s`,
- Werkzeugdefinitionen werden als Funktionsschemas an Ollama übergeben,
- Werkzeugargumente müssen gültige JSON-Objekte sein,
- umfangreiche Toolantworten werden nur für das Promptfenster gekürzt; die
  vollständigen Daten bleiben in Audit und Modell erhalten.

Das LLM entscheidet über Dialog, Rückfragen und Werkzeugauswahl. Es berechnet
nicht selbst verbindlich Bitpositionen, DLC, Framelasten, Routinggültigkeit,
Businventar oder Workflowstatus. Diese Ergebnisse stammen aus
deterministischen Python-/TypeScript-Services. Toolerfolg allein gilt nicht als
Auftragserfüllung; Abschluss erfordert kanonische IDs und erfüllte
Workload-Ziele.

### 4.2 Startverhalten und Providerstatus

Im aktiven Modus `hybrid-demand` wird Ollama beim Serverstart im Hintergrund
vorgewärmt. Dadurch blockiert ein großer Modell-Load den HTTP-Start nicht mehr
und erzeugt nicht nach 180 Sekunden den irreführenden Browserfehler
`Failed to fetch`. In den expliziten Modi `local` und `ollama` bleibt das
Vorwärmen absichtlich synchron, weil der lokale Modelldienst dort eine harte
Startvoraussetzung ist.

Die Konfiguration enthält `cloud_escalation: on_failure`, OpenAI ist als
Provider verfügbar, aber nicht aktiv, NVIDIA/Nemotron ist deaktiviert. Im
aktuell aufgerufenen Engineering-Chatpfad gibt es trotzdem **noch keinen
automatischen Cloud-Fallback**: `agent_tools/api.py` instanziiert unmittelbar
den `LocalEngineeringReasoner`, und dieser implementiert nur den lokalen
Ollama-Aufruf. Die Konfiguration beschreibt hier eine vorgesehene Providerregel,
nicht bereits ausgeführtes Failover. Ein Ollama-Fehler beendet den aktuellen
Agentenlauf kontrolliert und verändert das kanonische Modell nicht.

## 5. Technische CPU-/GPU-Umsetzung

### 5.1 Verbindliche Compute-Regel

Die Regel in `config/networkis.resources.json` lautet:

> CPU steuert und persistiert; GPU beschleunigt ausschließlich geeignete,
> seiteneffektfreie Batch-Berechnungen und lokale KI-Inferenz.

| CPU bleibt autoritativ | GPU darf beschleunigen |
| --- | --- |
| PostgreSQL, CRUD und Transaktionen | lokale Ollama-Inferenz |
| Projekt-Locks, Workflow und Jobsteuerung | Simulationstrace-Statistiken |
| Regeln, Validierung und kanonische Modelländerungen | Capacity-/Netzlast-Aggregationen |
| kleine numerische Batches | weitere explizit seiteneffektfreie Vektor-/Matrix-Batches |
| jeder Fallback bei fehlender CUDA-Laufzeit | – |

Der Grund ist fachlich: Datenbanktransaktionen, Graphmutationen und
regelbasierte Einzelentscheidungen sind verzweigte, I/O-lastige Aufgaben. CUDA
liefert seinen Vorteil bei großen, gleichförmigen Zahlenfeldern. Deshalb hat
GPU-Code keine Schreibrechte und erzeugt keine kanonischen Seiteneffekte.

### 5.2 Numerischer CUDA-Pfad

Die numerische Beschleunigung befindet sich in
`backend/simulator/numeric_acceleration.py` und verwendet
`cupy-cuda13x`:

1. `NUMERIC_ACCELERATOR` wählt `auto`, `cuda` oder `cpu`.
2. Unter `NUMERIC_ACCELERATOR_MIN_ITEMS` – aktuell 256 – wird Python verwendet,
   da Transfer- und Kernelstartkosten sonst den Nutzen übersteigen.
3. Ab der Schwelle versucht der Dienst, CuPy zu importieren, ein CUDA-Gerät zu
   öffnen und dessen Namen auszulesen.
4. Jeder Import-, Treiber-, Speicher- oder Gerätefehler führt zu einem
   inhaltlich gleichwertigen Python-Fallback mit dokumentierter Ursache.
5. Berechnungen verwenden `float64`; vor der Rückgabe wird der aktive CUDA-Stream
   synchronisiert.
6. Jede Operation liefert `requested`, `backend`, `device`, `item_count`,
   `accelerated`, `deterministic` und `fallback_reason` als Telemetrie.

Aktuell sind genau zwei produktive Rechenpfade angebunden:

- `grouped_route_statistics`: summiert Average-, Peak- und Burstlast je
  physischem Netz und bestimmt die schlechteste End-to-End-Latenz. Der
  Batchumfang ist `Anzahl Routen × 4`.
- `trace_statistics`: berechnet veränderte Samples, RMSE, Durchschnitts-, Peak-
  und 3-Sample-Burstlast global und je Netz. Der Batchumfang ist die Summe aus
  Delta- und Lastsamples.

Die Capacity-Fachmodelle selbst – Frameaufbau, Bitrate, Protokolloverhead,
Zyklus, Retry, Gateway- und Queueing-Anteile – werden zunächst deterministisch
auf der CPU aufgebaut. Nur die großen Reduktionen laufen bei Eignung auf CUDA.

### 5.3 Ollama-GPU und numerische GPU sind getrennt

Es existieren zwei unabhängige GPU-Nutzer:

```text
Ollama-Prozess auf dem Windows-Host
    -> LLM-Gewichte, Attention und Tokeninferenz

NetworkIS-Container mit NVIDIA-Runtime und CuPy
    -> deterministische Capacity- und Trace-Reduktionen
```

NetworkIS legt für Ollama keine Layerzahl oder GPU-Auslagerung fest. Die
Platzierung der LLM-Gewichte auf CPU/GPU entscheidet Ollama. NetworkIS steuert
nur Modellname, URL, Kontextlänge und Keep-alive. Deshalb belegt ein
warmgehaltenes 27B- oder 8B-Modell VRAM auch dann, wenn gerade keine
Capacity-Berechnung läuft.

Der GPU-Compose-Override reserviert ein NVIDIA-Gerät und setzt
`NUMERIC_ACCELERATOR` standardmäßig auf `cuda`. Das Container-Image installiert
CuPy inklusive CUDA-Toolkit-Komponenten; der eigentliche NVIDIA-Treiber wird
über die NVIDIA Container Runtime des Hosts bereitgestellt.

### 5.4 CPU-Parallelität und Ressourcen

Die aktuelle Ressourcensteuerung verwendet:

- 16 Waitress-Threads für HTTP,
- einen zentralen threadbasierten Simulations-Executor,
- 12 Simulationsworker auf 32 logischen CPU-Kernen,
- ein numerisches CPU-Threadbudget von 1 für kontrollierte Fallbacks,
- 8.192 Tokens Ollama-Kontext,
- 1.024 MiB Backend-Hot-Cache-Budget,
- 1.024 MiB Frontend-Runtime-Budget,
- 2.048 MiB weiches Limit für Trace-Artefakte.

Die PostgreSQL-Projektsperre serialisiert konkurrierende kanonische Änderungen.
Optimistische Versions-/Revisions-/Tokenprüfungen liefern bei veraltetem
Browserstand HTTP 409, statt fremde Änderungen oder lokale Eingaben zu
überschreiben.

## 6. Verifizierter Laufzeitstatus

Der Health-Endpunkt meldete am 8. September 2026 für den laufenden Container:

| Komponente | Erkannter Zustand |
| --- | --- |
| Backend | `ok`, Waitress, 16 Threads |
| Job-Executor | `thread`, 12 Worker, keine aktiven Jobs zum Messzeitpunkt |
| CPU | 32 logische Kerne |
| GPU | NVIDIA GeForce RTX 3070 Ti, 8.192 MiB, CUDA verfügbar |
| numerischer Backend-Probe | `cupy-cuda`, beschleunigt, deterministisch, 256 Elemente |
| KI-Modus | `hybrid-demand` |
| Ollama | erreichbar; `qwen3.8:27b` und `llama3.1:8b` installiert |

Die dabei gemeldete GPU-Auslastung und VRAM-Belegung sind Momentaufnahmen und
kein Beweis, welcher der beiden GPU-Nutzer die Last verursacht hat. Für eine
saubere Attribution müssen Ollama-Inferenzzeiten und CuPy-Operationstelemetrie
getrennt betrachtet werden.

## 7. Persistenz, Konsistenz und Simulationsübergabe

Capacity- und Preflight-Ergebnisse werden mit Eingaben, Annahmen,
Berechnungsmodell, Findings und Quellversionen als Analysis-Snapshots
gespeichert. Eine Workflow-Simulation darf nur starten, wenn ein aktueller
Preflight ohne Fehler und ein atomar reservierbarer `READY`-Snapshot vorliegen.

Der Simulationssnapshot friert serverseitig ein:

- das freigegebene Routing,
- das kanonische Engineering-Signalmodell,
- die wirksamen Technologieparameter,
- die relevanten Quellversionen.

Damit kann ein Startaufruf keine abweichenden Browserdaten unterschieben.
Parallele Starts desselben Snapshots erzeugen genau einen Job. Ergebnisse und
Trace-Artefakte bleiben nach Prozessneustarts nachvollziehbar.

## 8. Bewusste Grenzen des aktuellen Stands

1. `hybrid-demand` bedeutet im Engineering-Chat aktuell lokalen Bedarfseinsatz,
   noch kein technisch verdrahtetes OpenAI-/NVIDIA-Failover.
2. Projektübergreifende Zuordnungswiederverwendung ist evidenzbasiertes Exact-
   Match nach Normalisierung, kein trainiertes semantisches Langzeitgedächtnis.
3. Der lokale Vektorindex ist eine reproduzierbare Entwicklungsimplementierung
   im Prozess; er ist kein persistenter pgvector-/Qdrant-Index.
4. Domänenvollständigkeit hängt von gepflegten Fachkatalogen und Coverage-Regeln
   ab. Nicht katalogisierte Branchenfunktionen müssen ergänzt oder geprüft
   werden.
5. Eine vorgeschlagene Technologieänderung behebt die Topologie nicht autonom;
   Interface-, Gateway-, Timing- und Safety-Folgen benötigen Human Review und
   erneute Validierung.
6. Hohe GPU-Auslastung darf nicht als Fortschrittsbeweis eines Workflow-Schritts
   interpretiert werden. Autoritativ sind Jobstatus, persistierte Artefakte und
   Quellversionen.

## 9. Durchgeführter Abgleich

Für diese Zusammenfassung wurden Implementierung, Konfiguration und laufender
Health-Endpunkt miteinander verglichen. Zusätzlich liefen am 8. September 2026:

- 79 TypeScript-Tests für Spezifikation, Mengenexpansion bis 250 Endpunkte,
  Deduplizierung, ADAS-Vollständigkeit, Signalpacking, semantisches Routing,
  lokale I/O-Netze, Workflowfortsetzung und Topologien erfolgreich;
- 3 Python-Tests für deterministische numerische Beschleunigung und
  CPU-Fallback erfolgreich;
- `git diff --check` ohne Whitespacefehler;
- Prüfung aller 19 lokalen Dokumentlinks erfolgreich.

Die weitergehenden Python-Tests für RAG, Assignment Learning und Agent-Chat
konnten in der lokalen Windows-`.venv` nicht gesammelt werden, weil dort die
Produktionsabhängigkeiten `psycopg` und `mcp` fehlen. Der laufende
Produktionscontainer enthält diese Abhängigkeiten, aber nicht das
Entwicklungspaket `pytest`. Diese Umgebungsabweichung wurde nicht als bestandener
Test gewertet.

## 10. Zentrale Implementierungsdateien

| Thema | Datei |
| --- | --- |
| Kanonisches Modell | [`backend/engineering/core/models.py`](../backend/engineering/core/models.py) |
| PostgreSQL-Schema | [`backend/engineering/schema.py`](../backend/engineering/schema.py) |
| Parent-/Relationslogik und CRUD | [`backend/engineering/repository.py`](../backend/engineering/repository.py) |
| Wizard-Domänenmodell und Packing | [`frontend/src/lib/agent/engineering-specification.ts`](../frontend/src/lib/agent/engineering-specification.ts) |
| Serverseitiger Wizard-Generator | [`backend/engineering/agent_tools/wizard_generation.py`](../backend/engineering/agent_tools/wizard_generation.py) |
| Netzverteilung und Capacity-Reparatur | [`backend/engineering/intelligence/network_planning.py`](../backend/engineering/intelligence/network_planning.py) |
| Capacity-Berechnung | [`backend/engineering/capacity/service.py`](../backend/engineering/capacity/service.py) |
| Modellbasierte Simulation | [`backend/simulator/model_based_simulation.py`](../backend/simulator/model_based_simulation.py) |
| Numerische CPU-/CUDA-Auswahl | [`backend/simulator/numeric_acceleration.py`](../backend/simulator/numeric_acceleration.py) |
| Lokaler LLM-Reasoner | [`backend/agent_core/orchestration/local_reasoner.py`](../backend/agent_core/orchestration/local_reasoner.py) |
| Engineering-Agent-Startpfad | [`backend/engineering/agent_tools/api.py`](../backend/engineering/agent_tools/api.py) |
| Kanonisches RAG | [`backend/engineering/knowledge.py`](../backend/engineering/knowledge.py) |
| Hybrid Retrieval | [`backend/knowledge/retrieval.py`](../backend/knowledge/retrieval.py) |
| Deutsch/englische Semantik | [`backend/knowledge/semantic_vocabulary.py`](../backend/knowledge/semantic_vocabulary.py) |
| Zuordnungslernen | [`backend/engineering/assignment_learning.py`](../backend/engineering/assignment_learning.py) |
| Ressourcen-/Providerregel | [`config/networkis.resources.json`](../config/networkis.resources.json) |
| Haupt-Compose | [`docker-compose.networkis.yml`](../docker-compose.networkis.yml) |
| NVIDIA-Override | [`docker-compose.networkis.gpu.yml`](../docker-compose.networkis.gpu.yml) |
| Serverstart und LLM-Prewarm | [`generate_realistic_communication_tool.py`](../generate_realistic_communication_tool.py) |

## 11. Kurzfazit

Die LLMs liefern sprachliches Verständnis, Rückfragen, semantische Zuordnung
und toolgestützte Vorschläge. RAG liefert nachvollziehbare Projekt-, Graph- und
Review-Evidenz. Deterministische Services erzeugen und prüfen die vollständige
Kette von Hardware über Funktion, physisches und funktionales Interface,
Nachricht und Signal bis zu Route, Buslast und Simulation. Die CPU bleibt für
Steuerung, Konsistenz und Persistenz verantwortlich; die GPU beschleunigt lokale
LLM-Inferenz und genau abgegrenzte, seiteneffektfreie Zahlenbatches.
