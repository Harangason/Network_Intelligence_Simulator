# Modellbewusste Ausführung: Umsetzung und Abnahme

Stand: 11.09.2026. Kanonisches Projekt: `I:\PycharmProjects\My_first_Network_Simulator`.

## Ergebnis und Geltungsbereich

Der neue Python-Ausführungspfad verbindet vorhandene Funktionen beziehungsweise Hardware anhand des kanonischen Modells. Eine konkrete Strategieentscheidung autorisiert den vollständigen abhängigen Anschlussauftrag. Port, Interface, Netzmitgliedschaft, Transportbindung, Routing, Berechnungen und Prüfungen werden tatsächlich ausgeführt. Der ParkAssist-Pflichtfall besteht bis zum bestätigten funktionalen Timing und Preflight.

**Die beiden Gesamtbeschreibungen sind noch nicht uneingeschränkt vollständig umgesetzt.** Der abgenommene Kern betrifft Verbindungsaufträge mit explizit modellierten Signalen und Nachrichten. Neue Protokollumsetzungen, frei erzeugte DataObject-/Service-/Stream-Transporte und die vereinheitlichte autonome Ausführung sämtlicher GoalTypes sind noch offen. Die Tabellen unterscheiden diese Grenzen ausdrücklich von bestandenen Prüfungen.

## Quellen und Regelregister

| Regel | Verbindliche Quelle | Auswirkung |
|---|---|---|
| R1 | Nutzerauftrag: beide Dateien ausführen und alle Schritte abschließend prüfen | Umsetzung plus nachvollziehbare Abnahmematrix; keine pauschale Vollständigkeitsbehauptung |
| R2 | `H:/OneDrive/Download/NETWORK_SIMULATOR_AGENT_PORT_INTERFACE_DECISION_FLOW_CODEX.md`, insbesondere §§5–12, 25, 33, 39 | Capability ist kein Port; bestätigte Controllergrenzen, konkrete Portentscheidung, abhängige Ausführung |
| R3 | `H:/OneDrive/Download/NETWORK_SIMULATOR_AUTONOMOUS_MODEL_AWARE_AGENT_ORCHESTRATION_CODEX.md`, §§5–10, 17–19, 44–50, 54, 77–78 | Vollständiger Modellbezug, begrenzte Freigabe, atomare Änderung, unabhängige Zielprüfung |
| R4 | [Kommunikationsvertrag](../COMMUNICATION_DESIGN_CONTRACT.md) | Kodierung, Funktionspartner, Empfängergrenzen und Sendevertrag erhalten; Kapazität und Funktionsfrist getrennt |
| R5 | [Raumarchitektur](../SPATIAL_ARCHITECTURE_CONTRACT.md), [Netznamen](../NETWORK_NAMING_CONTRACT.md) | Keine erfundenen Einbauorte, keine Fahrzeugstereotype; vorhandene kanonische Netzidentitäten bleiben maßgeblich |
| R6 | [Bisherige Freigabegrenze](09_PROPOSAL_AND_APPROVAL.md) | Die neue Ausnahme gilt ausschließlich für einen gespeicherten, ausdrücklich gewählten Anschlussplan. Allgemeine Vorschläge bleiben im bisherigen Review-Verfahren. |

SHA-256 der gelesenen Originaldateien:

- Port-Dokument: `23FD15C596D1265B05FC00316D295BCA87E58FDB91DBFF0BE99E1EE7972733C8`
- Orchestrierungs-Dokument: `C7CA33D2CB5299708D1F538B6E5CA7FC59E10964C7867CD12CEA6162144E6BB3`

Die Dateien sind fachliche Anforderungen aus dem autorisierten Nutzerauftrag. Sie verleihen weder einem Sprachmodell noch importierten JSON-Daten selbst eine Freigabeberechtigung.

## Implementierung

`backend/engineering/goal_execution/` enthält Datenverträge, vollständige Graphabfragen, Portentscheidung, Sollzustand/Delta/Plan, kanonische Befehle, Transaktionsausführung, Journal, Fortschritt und MCP-Adapter. Die vier neuen Ressourcenarten sind `CommunicationCapability`, `CommunicationController`, `PhysicalPort` und `NetworkConnection`; `HardwareNetworkInterface` und logische `Interface` bleiben bestehende kanonische Entitäten. SQL-Schemaversion: 26. Projektpaketversion: 4.

Der echte Aufrufweg lautet `EngineeringAgent → EngineeringMCPClient → MCP-Server → continue_engineering_goal → Python-Core → PostgreSQL`. Die 23 Journalphasen sind interne Arbeitsschritte eines atomaren MCP-Auftrags, keine Behauptung über 23 separate MCP-Netzwerkaufrufe.

`prepare_engineering_connection` führt technisch mögliche Strategien zuerst vollständig in einem zurückgerollten Savepoint durch. Dabei entstehen keine dauerhaften Modelländerungen und keine Simulationsjobs. Die bestätigte Ausführung prüft die Revision erneut. Neue Controller, zusätzliche Hardwarefähigkeit, Umstecken belegter Ports, Änderungen fremder Routen und Umkodieren vorhandener Signale sind nicht von der Anschlussfreigabe gedeckt.

Die Freigabe kommt ausschließlich aus einer tatsächlich gespeicherten Nutzerentscheidung. Bei einem eindeutig formulierten Verbindungsauftrag und bereits passenden Anschlüssen reicht die ursprüngliche Nutzeranweisung. Ein bloßes LLM-Argument wie `authorization` wird abgewiesen. Projektimport entfernt sowohl Anschluss- als auch Simulations-Freigaben und setzt importierte Aufträge auf `PLAN_STALE`.

Die kanonischen Änderungen sind atomar. Ein Fehler rollt die gesamte Modelländerung zurück; das Fehlerjournal bleibt erhalten. Drei Ausführungsversuche sind die Obergrenze. Die Reparaturschleife für abgeleitete Artefakte ist zusätzlich auf zwei Durchgänge begrenzt und beendet sich bei fehlendem Fortschritt. Fehlende Hardware- oder Funktionsanforderungen werden dadurch nicht erfunden.

Eine ausdrücklich mitbeauftragte Normal-Simulation folgt nach dem Commit. Snapshot und Job werden wiederverwendet; ein Start oder ein korrumpiertes Telegramm reicht nicht als Erfolg. Die Zielprüfung verlangt kanonisch abgeschlossenen Snapshot, aktuellen Modellstand und übertragene Ereignisse für die beauftragten Routen. Dauer und Seed werden vor der Strategieentscheidung angezeigt; explizite Zeitangaben werden übernommen. Ungeklärte Fehler-/Stressszenarien werden nicht durch einen Normallauf ersetzt.

Der Hintergrunddienst setzt freigegebene Simulationen auch nach dem Chat-Wartefenster und nach einem Backend-Neustart fort. Projekttransaktionen koordinieren die Prüfungen mehrerer Prozesse. Ein Job wird nicht doppelt erzeugt. Nach spätestens 720 Hintergrundprüfungen pausiert der Auftrag sichtbar und bleibt gezielt fortsetzbar. Endergebnisse werden einmalig im Gespräch gespeichert und die laufende Chat-Karte liest ihren aktuellen Zustand. Die Ergebnisrelation `SIMULATED_IN` bleibt im Graph sichtbar, ist aber als abgeleiteter Simulationsnachweis aus dem Fingerprint der Quellarchitektur ausgeschlossen.

Fehlende Hardwarefakten können direkt im Chat erfasst werden: Technologie-Fähigkeit, Geräteobergrenzen, vorhandene Controller, reservierte Kanäle, Zuordnung bestehender Interfaces und Nachweisquelle. Die menschliche Bestätigung ist projekt-, revisions- und auftragsgebunden; sie besitzt keinen schreibenden MCP-Ersatz. Neue Angaben werden atomar gespeichert, die alte Anschlussfreigabe wird verworfen und derselbe Auftrag neu geprüft. Bestätigte Kanäle werden dabei nicht umgehängt. Ein bereits zugewiesener Kanal ohne PhysicalPort wird durch den Anschlussplan vervollständigt, ohne ein zweites Interface oder einen zweiten Kanal anzulegen.

## Abbildung aller 33 Port-Folgeschritte

„Umgesetzt“ bezieht sich auf den beschriebenen Verbindungsablauf. „Teilweise“ benennt zusätzliche Semantik aus der allgemeinen Spezifikation, die der aktuelle Adapter nicht erzeugt.

| Nr. | Geforderter Schritt | Nachweis / Status |
|---|---|---|
| 1 | Modellrevision erneut prüfen | Umgesetzt: Graphrevision plus gespeicherte Freigabe; Konflikttest |
| 2 | Capability bestätigen | Umgesetzt: explizite Hardwarefakten; keine Ableitung aus Gerätenamen |
| 3 | Controller auflösen | Umgesetzt: aktive Controllerreferenz und Eigentümer |
| 4 | Channel-/Port-Limits | Umgesetzt: Controllergrenze und geräteweite Grenzen |
| 5 | Freien Channel bestimmen | Umgesetzt: vorhandene Ports, Interfaces und belegte Controllerkanäle zählen |
| 6 | HardwareInterface erstellen/wiederverwenden | Umgesetzt: fehlendes HNI oder eindeutig freies HNI |
| 7 | PhysicalPort erstellen | Umgesetzt: getrennte kanonische Portressource |
| 8 | Controller/Interface/Port verbinden | Umgesetzt: Referenzen einschließlich Quelle und Ziel persistiert |
| 9 | Zielnetz verbinden | Umgesetzt: nur freier oder bereits passend verbundener Port |
| 10 | Netzmitgliedschaft aktualisieren | Umgesetzt: HNI plus NetworkConnection |
| 11 | Topology Relations | Umgesetzt: kanonische Relation, Ports, Kanten und Route-Kanten-Bezüge |
| 12 | Function Mapping erneut prüfen | Umgesetzt: aktuelle tatsächliche Hosts, Widersprüche blockieren |
| 13 | Functional Interfaces auflösen | Umgesetzt: passende Schnittstelle wiederverwenden oder fehlenden Empfangsanschluss anlegen |
| 14 | Payload bestimmen | Umgesetzt für vorhandene, explizite Funktionsausgänge; Mehrdeutigkeit wird abgefragt |
| 15 | Bestehende TransportUnits prüfen | Umgesetzt für kanonische Nachrichten und ihre Transportmetadaten |
| 16 | TransportUnits wiederverwenden/erzeugen | Teilweise: vorhandene Nachrichten werden gebunden; fehlende Transportparameter werden abgeleitet. Beliebige neue Transportarten werden nicht erzeugt. |
| 17 | Signals/DataObjects binden | Teilweise: Signal-/Message-Bindings umgesetzt; DataObject-/Service-/Stream-Adapter offen |
| 18 | CAN-FD Payload Packing | Teilweise: explizite Belegung, gültige DLC-Klassen, Überlaufprüfung und fehlende DLC umgesetzt. Automatisches Aufteilen/Umpacken mehrerer Nachrichten offen. |
| 19 | CAN Identifier vergeben | Umgesetzt: nur fehlende IDs; Kollisionen auf beteiligten Netzen prüfen; explizite IDs nicht ändern |
| 20 | Transport auf HNI/Port binden | Umgesetzt: kanonische physische Sendebindung |
| 21 | Routing Table aktualisieren | Umgesetzt: gezielte Erzeugung beziehungsweise versionierte Änderung |
| 22 | Alte Routen ablösen | Teilweise: betroffene Einzelroute versioniert und alte Kantenbezüge entfernt. Mehrdeutige/Multicast-Deltas bleiben als konkrete offene Planung erhalten. |
| 23 | Interface Load | Umgesetzt über bestehenden Capacity-Core |
| 24 | Network Load | Umgesetzt; unzulässige Last verwirft bereits den technischen Kandidaten |
| 25 | Timing berechnen | Umgesetzt über Capacity/Timing-Core |
| 26 | LogicalNodeAddress Resolution | Umgesetzt: tatsächliche Hosts, Namespace, Reservierungen und Adresspolicy prüfen |
| 27 | Technology Binding validieren | Umgesetzt für den unterstützten Transportpfad; Wechsel ohne explizite Umsetzung blockiert |
| 28 | Routing validieren | Umgesetzt: abschließender RoutingValidator |
| 29 | Capacity validieren | Umgesetzt: Last, Sendeplan und Pfadmetriken |
| 30 | Timing validieren | Umgesetzt: technische Zeitvorgaben und bestätigte funktionale Fristen separat |
| 31 | Communication Preflight | Umgesetzt; kein Abschluss bei offenem Nachweis |
| 32 | Alte Ergebnisse als STALE markieren | Umgesetzt durch bestehenden Workflow-Invalidierungsdienst vor Neuberechnung |
| 33 | CompletionEvaluator | Umgesetzt: evidenzbasierte Zielprüfung einschließlich optionaler Simulation |

## Definition of Done: Port-Dokument

| Kriterien aus §39 | Befund |
|---|---|
| 1, 3, 4, 5, 6 | Bestanden: getrennte Ressourcen, Wiederverwendung, fehlender Port, gespeicherte Entscheidung/Freigabe |
| 2 | Im neuen Anschlussauftrag bestanden. Keine pauschale Zusicherung für alle älteren Wizard-/Repair-Schreibpfade. |
| 7 | ParkAssist vollständig bestanden; allgemeine Transport-/Multicast-Erweiterungen siehe 33-Schritte-Tabelle |
| 8, 9, 10, 11 | Bestanden: Channel-/Port-Grenzen, belegte Netze, Technologie, Bitrate und Erweiterungspolicy |
| 12, 13, 14, 15, 16 | Bestanden: Routing, Kapazität, Timing, Preflight und unabhängige Completion |
| 17, 18, 19, 20 | Bestanden: gleicher Auftrag nach Antwort, Revisionsschutz, echter MCP-Pfad und ParkAssist-E2E |

## Definition of Done: Orchestrierungs-Dokument

| Kriterien aus §78 | Befund |
|---|---|
| 1, 2, 3, 4, 5 | Bestanden im neuen Ausführungspfad: vollständiges Modell, tatsächliche Hosts, Anschlüsse, Bindungen und bestehende Routen |
| 6, 7, 8 | Bestanden: DesiredEngineeringState, EngineeringModelDelta und abhängiger Plan |
| 9, 10 | Bestanden für eindeutige Wiederverwendung bzw. konkrete Portstrategie; neue Architekturentscheidungen erfordern neue Freigabe |
| 11, 12, 13 | ParkAssist bestanden; allgemeine Transport-/Multicast-Grenzen bleiben offen |
| 14 | Teilweise: bestehende Message-/Signal-Semantik und fehlende Frameparameter; weitere Transportarten nicht automatisch erzeugt |
| 15, 16, 17, 18, 19, 20 | Bestanden im unterstützten Pfad: Kapazität, Timing, Validation, Preflight, Invalidation und Completion |
| 21 | Umgesetzt als begrenzte Wiederholung und Reparatur abgeleiteter Artefakte. Keine allgemeine automatische Architektur-Umsynthese. |
| 22, 23, 24 | Bestanden: Revision, Wiederverwendung und Vermeidung zusätzlicher HNIs/Ports im Wiederholungsfall |
| 25, 26, 27, 28, 29, 30 | Bestanden: keine erforderliche Werkzeugnavigation, echte MCP-Aktionen, Python-Core, Resume, Journal und ParkAssist-E2E |

## Noch offene Gesamtanforderungen

Ergänzung vom 11.09.2026: Der konkrete Kommunikationsreparaturpfad besitzt inzwischen einen dauerhaften `FIX_VALIDATION`-Auftrag mit Fachagent, gespeicherter Strategieentscheidung, MCP-Ausführung, Routing-Rekonstruktion und Kapazitäts-/Timing-Nachrechnung. Siehe `17_AI_ENTRYPOINT_AUDIT.md`. Dies ist noch kein allgemeiner Adapter für beliebige Validierungsfehler oder die übrigen unten genannten Zieltypen.

1. Alle elf geforderten GoalTypes besitzen Kriterienverträge. Ein gemeinsamer autorisierter Ausführungsadapter für `CREATE_ARCHITECTURE`, `ADD_NETWORK`, `OPTIMIZE_NETWORK`, `FIX_VALIDATION`, `FIX_TRACE_ROOT_CAUSE` und `COMPARE_ARCHITECTURES` ist damit noch nicht implementiert. Vorhandene Fachwerkzeuge und ihre bisherigen Review-Abläufe bleiben verfügbar.
2. Neue Gateway-Protokollumsetzungen samt transportbezogener Queue-/Latenz- und Bandbreitensemantik werden nicht automatisch konstruiert. Ein solcher Kandidat wird mit `GATEWAY_CONVERSION_REQUIRED` verworfen. Bestehende gleichartige Pfade nutzen die vorhandene Weiterleitungsprüfung und zusätzlich die bestätigten Ressourcen aller beteiligten Ports.
3. Neue DataObject-, Stream- oder Service-Transporte, freies Mehrnachrichten-Packing und mehrdeutige Multicast-Umbauten sind noch keine ausführbaren Strategien dieses Adapters. Sie werden weder als erfolgreich gemeldet noch als CAN-Signale erfunden.
4. Die automatische Simulationsfortsetzung umfasst die vor der Entscheidung sichtbare Normalprüfung. Die automatische Übernahme eines frei beschriebenen Fehler-/Stressszenarios in diesen gemeinsamen Auftrag ist noch offen. Solche Anforderungen benötigen die vorhandene explizite Szenariodefinition; sie werden nicht als bestandene Normalprüfung ausgegeben.

Diese Punkte sind nicht durch den bestandenen ParkAssist-Test abgedeckt und nicht als abgeschlossen zu behandeln.

## Prüfungen und Betriebsnachweis

- Isolierter PostgreSQL-Testlauf über `scripts/run_repair_sql_isolated.py verify_goal_execution_sql.py`. Der Runner verweigert die Produktdatenbank und verwendet ausschließlich `/nis_bus_naming_tests`.
- `backend/tests/test_goal_execution.py` prüft Fakten, Limits, Kanal 2, inkompatible Netze, Wiederverwendung, tatsächliche Hosts und fehlende Completion-Evidenz.
- `backend/tests/test_goal_execution_sql.py` prüft kanonische Port-/Routing-Schreibvorgänge, vollständiges ParkAssist-Preflight/Timing, technische Vorprüfung ohne Persistenz, Rollback, menschliche Antwort im selben Chat, echten MCP-Protokollaufruf, Projektisolation, Revision, Import ohne Freigabe, Ereignisvertrag, begrenzte Reparatur und Simulationsdispatch nach Commit.
- Ergänzende Regressionen: `test_engineering_mcp.py`, `test_agent_chat_ux.py`, `test_agent_core.py`, `test_project_bundle.py`, `test_workflow.py`.
- Neben kontrollierten Job-Service-Ersatztests läuft `test_connection_to_real_simulation_engine_and_trace_artifact` durch die echte Flask-Simulations-API, den echten JobService, die echte Simulationsengine und die erzeugte `universal_trace.jsonl`. Nur der HTTP-Transport wird auf den lokalen Flask-Testclient umgeleitet. Der Trace weist die beauftragten kanonischen Routen nach. Datenbank und Artefakte bleiben isolierte Testdaten.
- Die Hintergrundtests prüfen identischen Snapshot/Job, gesperrte Doppelprüfung, spätere Completion, einmalige Rückmeldung, gespeicherte Freigabe und begrenzte Wiederaufnahme. Die Hardwarefaktentests prüfen den Ablauf von vollständig fehlenden Fähigkeiten bis zur Completion, Revisionskonflikte, Limits, Verbot stillen Umhängens und atomaren Rollback.
- Die bereits vorher umgesetzte Netzwerksuche bestand den Browserlauf `frontend/scripts/verify-network-search.mjs`: kleine Ansichten, Vollbild, Tastatur, sichtbare Treffer und unveränderte Topologie; keine Modellschreibvorgänge.
- Nach dem ersten neuen Build: Health `ok`, Portfähigkeit verfügbar, Projektname `NIS Projekt 1`, 381 kanonische/übernommene Ports. Im aktiven Projekt sind noch **0 explizite CommunicationCapability-Ressourcen** erfasst; die Testfixture ersetzt diese fehlenden Produktdaten nicht.

Letzter vollständiger Lauf: **162 Tests bestanden**, 59,77 Sekunden. Eine Pydantic-Namenswarnung bleibt: Das fachliche Delta-Feld `validate` überschattet eine geerbte, hier nicht aufgerufene BaseModel-Methode; daraus entstand kein Test- oder Serialisierungsfehler.

Zusätzlich bestanden die **15 Frontend-Tests des AgentResponse-Vertrags** und TypeScript `tsc --noEmit`. Anschlussfortschritt wird aus den bereits gelieferten Ereignissen angezeigt; die Detailansicht versucht nicht mehr, eine `goal-…`-Kennung über die alte Signal-Workload-API zu laden.

Der Browserlauf `frontend/scripts/verify-goal-chat-view.mjs` besteht ebenfalls: Fortschrittsdetails bei 1440×1000 und 390×844, ausdrückliche Controller-/Kanalangaben im Hardwareformular und Ersetzung einer laufenden Anzeige durch das dauerhafte Endergebnis. Chat-/Hardwareantworten sind im Browsertest Fixtures; alle Modellschreibzugriffe werden abgefangen. Keine JavaScript-Fehler und keine Aufrufe der falschen Workload-API. Ergebnisse: `backend/runtime/goal-execution-chat.json`.

Die Live-Inventarprüfung umfasste alle 262 Hardware-Knoten und fand auch in deren eingebetteten Hardwareinformationen keine CommunicationCapability-/Controllerlisten. Es wurden dabei keine Hardwarefakten ergänzt.

Aktuelle Test- und Buildprotokolle: `backend/runtime/goal-execution-tests.log` und `backend/runtime/goal-execution-build.log`. Der Docker-Produktionsbuild ist erfolgreich; die laufende API meldet `ok`. Die Produktionsprüfung ist lesend. Der Live-Nachweis steht in `backend/runtime/goal-execution-live.json`. Die Fingerprint-Korrektur für abgeleitete Simulationsrelationen kann den Revisionswert ändern, ohne die Hardwaredaten zu verändern; deshalb werden Ressourcen und Ports zusätzlich direkt mit der Bestandsaufnahme verglichen.
