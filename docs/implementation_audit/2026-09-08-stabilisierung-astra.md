# Stabilisierung und Abnahmeprotokoll – 8. September 2026

> Historischer Stand vor der anschließenden Nutzerklarstellung. Die Ressourcenfrage in Abschnitt 5 wurde inzwischen durch eine automatische Tool-Entscheidung ersetzt: siehe [Automatische Ressourcenplanung](2026-09-08-automatische-ressourcenplanung.md). Die ursprünglichen Messungen und Abnahmegrenzen dieses Protokolls bleiben als Verlauf erhalten.

## Ergebnis und Abnahmegrenze

Der reproduzierte Speicher-/Verbindungsfehler wurde behoben. Zusätzlich wurden Wizard-Fortsetzung, Proposal-Übernahme, Ressourcenprüfung, Runtime-Faults und Trace-Navigation stabilisiert. Die Anwendung läuft aus dem kanonischen Repository auf Port 13500.

Final ausgerolltes Image am 08.09.2026, 15:03 Uhr Europe/Berlin: `sha256:853b17b9c1a2cac511566b5c8c6689691e06ba758132ff19041258462811767f`. Readiness: Datenbank und Speicher verfügbar; Docker-Status `healthy`.

Dies ist **keine vollständige Produktabnahme** der Zielvereinbarung `H:\OneDrive\Download\ZIELVEREINBARUNG_NETWORK_INTELLIGENCE_SIMULATOR.md`. Alle neun Wizard-Phasen wurden in isolierten Referenzprojekten ausgeführt; das bestehende Nutzerprojekt ist weiterhin an einer fachlichen Ressourcenentscheidung blockiert. Die Pflichtszenarien A–E sind durch die neuen Engine-Tests nur teilweise abgedeckt, nicht vollständig über die Benutzeroberfläche abgenommen.

## 1. Nachgewiesene Fehler und Änderungen

### Docker-Speicher und „Failed to fetch“

Der Windows-Bind-Mount `./backend/runtime:/app/backend/runtime` lieferte im Container `Input/output error`, obwohl die Dateien auf Windows lesbar waren. Ein einfacher Healthcheck blieb dabei erfolgreich. API-Zugriffe auf Registry/Artefakte konnten hängen oder abbrechen.

- Die Runtime-Daten wurden in das native Docker-Volume `networkis-runtime-data` übertragen.
- Zum Umschaltzeitpunkt: 2.813 Dateien, 84.659.916.125 Bytes. Alle erwarteten relativen Dateipfade und Größen wurden verglichen; zusätzlich 13 SHA-256-Stichproben einschließlich Job-Registry. Das ist keine vollständige SHA-256-Prüfung jeder Datei.
- Das ursprüngliche Windows-Verzeichnis blieb erhalten. Neue Ergebnisse werden seit der Umschaltung im Docker-Volume gespeichert; das Windows-Verzeichnis ist seitdem eine historische Rückfallkopie, keine laufend synchronisierte Kopie.
- `/api/ready` prüft jetzt Datenbank und Runtime-Speicher. Docker verwendet diesen Readiness-Endpunkt statt eines reinen Prozess-Lebenszeichens.
- Registry-Lesen behandelt Speicherfehler kontrolliert, auch wenn bereits die Dateistatistik fehlschlägt.
- Prüfsystematik: `scripts/verify-runtime-copy.ps1`. Nach dem produktiven Weiterbetrieb ist die veränderliche Registry erwartungsgemäß nicht mehr identisch mit der Rückfallkopie; das Skript dient einem kontrollierten Migrationszeitpunkt.

### Wizard und Proposal-Übernahme

- Prozessinstanz-ID zusätzlich zur PID: Ein Container-Neustart mit wiederverwendeter PID wird nicht mehr mit dem alten Agent-Lauf verwechselt.
- Persistente Übernahme und Workflow-Abgleich erfolgen gemeinsam. Ein verlorener HTTP-Response löst keinen blinden zweiten Apply-Request aus: Der Client liest den gespeicherten Status desselben Vorschlags nach.
- Kompakte Statusantworten werden nur mit passender Proposal-ID/Revision zusammengeführt. Neue Revisionen laden den vollständigen Vorschlag; konkurrierende Polling-Antworten überschreiben keine laufende Übernahme.
- Fortsetzungen laufen nach den Freigabegrenzen durch Validation, Simulation, Results und Intelligence. Bereits abgeschlossene Zielketten erzeugen bei Wiederholung keinen zusätzlichen Simulationsjob.
- Bestätigte Teilnehmernamen aus dem Cluster-Graph bleiben im generierten Engineering-Modell erhalten. Fehlende oder mehrdeutige Zuordnungen werden nicht stillschweigend als teilweise erfolgreiches Routing akzeptiert.
- Unbekannte Teilnehmerparameter werden als `GENERIC_ESTIMATE` gekennzeichnet. Es werden keine belegten physikalischen Einheiten vorgetäuscht.

### Physische Ressourcen

- Die Planung zählt physische Segmente einschließlich nicht routenbelegter Kanten.
- Ein noch nicht freigegebener Technologiewechsel erzeugt keine fiktiven freien Bussegmente.
- Sowohl Validate als auch Apply prüfen die bestätigte Ressourcenobergrenze. Auch ein alter Vorschlag kann diese Grenze nicht durch einen bereits gespeicherten Freigabestatus umgehen.

### Simulation und Trace

- Universal Trace und Capacity verwenden denselben Frame-/Bitrate-Rechner, einschließlich CAN-FD-Arbitration-/Datenphase.
- Seed `0` und explizit deaktivierter Jitter bleiben erhalten; konfigurierte Zyklusänderungen verändern die Ereignisplanung.
- Gateway-Delay/-Drop werden mit kanonischen Gateway-Hops korreliert. Ein Gateway-Anzeigename wird bei Szenariovalidierung eindeutig auf dessen ID aufgelöst; mehrdeutige Namen werden abgewiesen. Delay/Jitter verändern tatsächliche Ereigniszeitpunkte.
- Trace-Ereignisse tragen kanonische Route-Referenzen für die Navigation ins Engineering-Modell.
- Golden-Vergleich berücksichtigt zeitlich verschobene, fehlende/zusätzliche, fehlerhafte und wertveränderte Ereignisse. Root-Cause-Ausgaben bleiben Hypothesen; zeitlicher Zusammenhang wird nicht als bewiesene Kausalität ausgegeben.
- Neuer projektgebundener `trace-window`-Endpunkt: begrenztes Streaming statt vollständigem Laden großer Artefakte; maximal 2.000 Ereignisse pro Fenster und feste Scan-/Antwortbudgets.
- Lokaler CSV/JSON/JSONL-Import: maximal 5 MiB und 2.000 sichtbare Ereignisse, korrekte CSV-Quotes/JSON-Felder, keine erfundenen Zeitstempel bei ungültigen Daten. Binärformate benötigen weiterhin einen Adapter.
- Botschaften, Sequenz, Signale und Trace teilen Filter/Zeitfenster und Ereignisauswahl. Mehrere dekodierte Signale lassen sich vergleichen. Session-Schließen verwirft auch laufende Antworten und Navigation zu alten Jobs.
- Session-Auswahl verwendet die tatsächliche kompakte Job-Liste. Geladene Simulationsjobs bleiben über den URL-Parameter `job` nach einem Browser-Neuladen verfügbar.
- Der im Frontend angebotene POST-Abbruchalias `/api/simulations/{id}` ist auch auf dem kanonischen Backend verfügbar. Dadurch funktioniert er trotz der lokalen Proxy-Regel; der bestehende `/cancel`-Endpunkt bleibt erhalten. Projektbindung und wiederholter Abbruch sind regressionstestgesichert.

## 2. Automatisierte Nachweise

Die Tests verwenden eine separate PostgreSQL-Instanz auf Port 15432 und einen separaten Test-Runtime-Pfad. HTTP-Schreibtests nutzen neu angelegte `astra-e2e-*`-/`endpoint-smoke-*`-Projekte. Sie bestätigen keine Änderungen am fachlichen Nutzerprojekt.

| Prüfung | Nachweis | Aussage und Grenze |
| --- | --- | --- |
| Vollständige Backend-Suite | `verification/2026-09-08-pytest-final.xml` | 619 bestanden, 0 Fehler, 0 übersprungen; 115,33 s, nach den letzten API-/Gateway-Korrekturen. |
| Frontend-Suite | `verification/2026-09-08-frontend-tests.xml` | 175 Testfälle, 0 Fehler. Die abschließenden Session-UI-Korrekturen wurden zusätzlich per TypeScript, Produktionsbuild und Browser geprüft. |
| Produktionsbuild | Docker-/Next-Build im Arbeitsprotokoll | TypeScript und alle 23 Seiten erfolgreich gebaut. |
| Backend-Smoke | `verification/2026-09-08-all-endpoints-direct.json`, `2026-09-08-all-endpoints-proxy.json`, `2026-09-08-final-endpoints.json` | Je 214 damalige Flask-Routen-/Methodenkombinationen; direkte und Proxy-Durchläufe ohne 5xx/Timeout. |
| Erweiterter Endpunkt-Smoke | `verification/2026-09-08-endpoints-final-reviewed.json` | 215 Backend-Bindings plus 17 explizite Next.js-Handler ergeben nach Überschneidungen 226 unterschiedliche Methoden/Pfade. Zwei Durchläufe, 452 Aufrufe, keine 5xx/405/Verbindungsfehler. Einzelstatus protokolliert. Der im ersten erweiterten Lauf gefundene POST-Abbruchalias mit HTTP 405 antwortet jetzt korrekt mit 404 für die nicht vorhandene Test-ID. |
| Gleichzeitige Lesezugriffe | `verification/2026-09-08-final-stability.json` | 1.500 Requests, 12 Worker, 1.500× HTTP 200, keine Fehler; p50 34,96 ms, p95 590,41 ms, Maximum 908,61 ms; Laufzeit 17,88 s. Das ist ein Last-Burst, kein mehrstündiger Dauertest. |
| Live-Wizard dreifach | `verification/2026-09-08-final-wizard-1.json` bis `2026-09-08-final-wizard-3.json` | Reale HTTP-Requests, Review/Apply, persistiertes Modell, tatsächliche Simulation und Trace; alle neun Phasen, keine doppelte Simulation beim erneuten Fortsetzen. Parallel zum Lasttest ausgeführt. |
| Live-Wizard nach letztem Deployment | `verification/2026-09-08-wizard-final-deployed.json` | Erneut alle neun Phasen im Projekt `astra-e2e-1527e1067fae`, echter Job `36cc0e4bf31a41c2829e43c796b0012b`; Intelligence mit fachlichen Warnungen, keine zusätzliche Simulation beim Wiederholen. |

Der Endpunkt-Smoke nutzt absichtlich ungültige Eingaben und nicht vorhandene Objekt-IDs. Erwartete 400/403/404/409-Antworten belegen Dispatch und kontrollierte Fehlerbehandlung, **nicht** den vollständigen fachlichen Erfolg jeder API-Operation. HEAD/OPTIONS werden nicht als eigene Smoke-Fälle aufgezählt. LLM-Provider-/Cloud-Ausfälle und ein mehrstündiger Soak-Test sind damit nicht abgedeckt.

Reproduzierbare Hilfen: `scripts/smoke-all-endpoints.py --include-frontend`, `scripts/stability-http-burst.py`, `scripts/verify-live-wizard.py`. Der Endpunkt-Smoke importiert die Flask-App zur Routeninventur und muss deshalb mit isoliertem `DATABASE_URL`, `ENGINEERING_TEST_DATABASE_URL` und `SIMULATOR_RUNTIME_ROOT` laufen.

## 3. Browser-Abnahme

Am bereitgestellten Referenzlauf `astra-e2e-4332f92ee668`, Job `e0592a4129af41a5830103e5dce3e77a`, wurden geprüft:

- 152 echte Trace-Ereignisse über die Session-Auswahl laden; Seite neu laden und denselben Job wiederherstellen.
- Zeitfenster 0–0,05 s, gemeinsame Ereignisauswahl beim Ansichtswechsel und mehrere dekodierte Kanäle.
- Deep Link einer Trace-Route öffnet das kanonische Routing-Objekt; keine Verwechslung von Runtime-ID und Route-ID.
- Session schließen: keine alten Ereignisse oder nachträglich eintreffenden Antworten sichtbar.
- Keine Warnungen/Fehler in der untersuchten Browser-Konsole. Ein kurzzeitiger Automations-Timeout wurde durch erneutes Lesen der UI und Wiederholung geprüft; daraus wurde kein Anwendungsfehler abgeleitet.
- Originalprojekt nach Deployment neu geladen: 260 Hardware-Knoten sichtbar, keine Meldung „Projektverbindung unterbrochen“.

Referenz-Trace: <http://127.0.0.1:13500/trace-analysis?view=messages&project=astra-e2e-4332f92ee668&job=e0592a4129af41a5830103e5dce3e77a>

## 4. Alle neun Phasen: Referenz versus Nutzerprojekt

| Phase | Drei abschließende Referenzläufe | Nutzerprojekt `20260908103453543-44dfbb43` |
| --- | --- | --- |
| Engineering-Modell | COMPLETE | COMPLETE |
| Routing | APPROVED | APPROVED |
| Netzwerk | COMPLETE | COMPLETE |
| Parameter | APPROVED | APPROVED |
| Capacity & Timing | COMPLETE | ERROR |
| Validation | APPROVED | EMPTY |
| Simulation | COMPLETE | EMPTY |
| Results | COMPLETE | EMPTY |
| Intelligence | WARNING | EMPTY |

`WARNING` in den Referenzläufen bedeutet: Analyse ausgeführt, aber fachliche Findings vorhanden, unter anderem Single Point of Failure und eine noch nicht bestätigte Einheit beim generischen Stellglied. Diese Warnungen wurden nicht verborgen. Die Referenzmodelle enthalten vier Hardware-Teilnehmer und zwei Routen; das ist kein erfolgreicher Vollsimulationsnachweis für das ursprüngliche 260-Knoten-Projekt. Ein zusätzlicher größerer Integrationstest prüft eine 251-Knoten-Modellkette mit drei Routen, ebenfalls nicht dessen volle Laststruktur.

## 5. Konkrete Entscheidung im bestehenden Projekt

Die zuerst beanstandete Übernahme war nicht vollständig wirkungslos: Vorschlag `30ec2539-a1ac-44c0-a8d7-13160d96cfde` war bereits persistiert; vier Zweige/neun Kanten wurden segmentiert. Der Verbindungsfehler verdeckte den tatsächlichen Stand.

Der danach wartende Reparaturvorschlag `81e39ff1-8aca-4307-a758-0ab91178c6f2` wurde mit der korrigierten Ressourcenprüfung erneut validiert, aber **nicht übernommen**:

| Physische Ressourcen | Im Wizard bestätigt | Im wartenden Vorschlag geplant |
| --- | ---: | ---: |
| CAN-FD | 10 | 21 |
| LIN | 25 | 68 |

Ergebnis: `PROPOSED`, `validation_result.valid=false`, zweimal `PHYSICAL_INVENTORY_EXCEEDED`. Im aktuellen Capacity-Snapshot `58f3701c-93ef-4ecc-b0ad-c3c8ad892cbe` sind 217 Routen, 225 Route-Segmente und 520 Signale erfasst; 22 der 64 routenbelegten LIN-Netze überschreiten 100 % Burst-Last, Spitze 157,8125 %. Der Snapshot ist nicht als veraltet markiert.

Erforderlich ist eine fachliche Auswahl:

1. Die bestätigten 25 LIN-/10 CAN-FD-Netze bleiben verbindlich: Topologie, Packung und gegebenenfalls Kommunikationsanforderungen müssen innerhalb dieser Grenzen neu geplant und ihre Machbarkeit geprüft werden.
2. Zusätzliche physische Ressourcen dürfen geplant werden: neuer konkreter Ressourcenbestand und erforderliche Interfaces/Gateways müssen bestätigt werden; das ist keine automatische Freigabe jedes Technologiewechsels.

Keine dieser Entscheidungen wurde stellvertretend getroffen. Die folgenden Nutzerprojekt-Phasen wurden nicht trotz fehlerhafter Kapazität als abgeschlossen markiert.

## 6. Offene Punkte der gesamten Zielvereinbarung

- Die vollständigen Pflichtszenarien A–E müssen mit den jeweils geforderten kanonischen Modellketten, tatsächlichen Nutzeraktionen, Fehlerfällen und persistenten Ergebnissen separat abgenommen werden. Die neuen Tests in `test_acceptance_scenarios.py` sind Transport-/Fault-/Vergleichsregressionen; insbesondere vollständige PLC/Remote-I/O- und DDS/DataObject-High-Rate-Ketten sind damit nicht belegt.
- End-to-End-Kausalitätsbeweise, lückenlose Evidence-Verknüpfung sämtlicher Findings und eine vollständig integrierte Golden-Trace-Bedienkette sind nicht als vollständig abgenommen zu bewerten. Die aktuelle Root-Cause-Ansicht kennzeichnet zeitlichen Kontext/Hypothesen ausdrücklich.
- Binäre externe Trace-Formate sind ohne Konvertierungsadapter nicht unterstützt. Begrenzte Fenster schützen große Sessions vor Voll-Downloads; ein Lastnachweis mit allen Langzeit-/Mehrnutzergrößen bleibt offen.
- Sämtliche Zustands-, physikalischen, Derived-Signal-, Constraint- und Replay-Fertigkriterien der Zielvereinbarung wurden in diesem Lauf nicht einzeln gegen eine vollständige Anforderungsmatrix abgenommen.
- Die Windows-Rückfallkopie ist erhalten. Für einen dauerhaften Betrieb bleibt eine eigenständige Backup-/Restore-Strategie des nativen Volumes und der Datenbank erforderlich.

## 7. Vorgehen und Schutz bestehender Arbeit

Die Skills Investigation Mode und Verification führten zur Prüfung der Kette Browser → API → Workflow/Persistenz → Runtime → sichtbare Ergebnisse. Die Browser-/React-Prüfung führte insbesondere zu begrenzten Trace-Ladevorgängen und Schutz vor veralteten Antworten. Die Next.js-Dokumentation zur Rewrite-Reihenfolge erklärte den verdeckten dynamischen Abbruchhandler; der Backend-Alias erhält die bisherige Streaming-/Proxy-Architektur.

Vorhandene Änderungen im Arbeitsverzeichnis wurden erhalten. Keine Commits, kein Reset und kein Löschen von Nutzerprojekten oder Runtime-Daten. Die EIP und die separate Datenbank auf Port 5432 wurden nicht verändert. Isolierte Testprojekte und Testausgaben bleiben als Nachweise erhalten. Die zusätzliche Testdatenbank `networkis-stability-test-db` wurde nach Abschluss gestoppt; ihre Daten wurden nicht gelöscht. `git diff --check` für Backend, Frontend, Skripte und Compose war erfolgreich.
