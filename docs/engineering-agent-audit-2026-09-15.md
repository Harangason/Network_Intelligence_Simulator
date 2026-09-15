# Engineering-Agent: Befund und Ausbauplan

Stand: 15.09.2026. Kanonisches Projekt: `I:/PycharmProjects/My_first_Network_Simulator`.
Auftrag: Engineering-Agent gründlich prüfen, Sackgassen beseitigen und Projekterstellung sowie UI-Funktionen ohne verpflichtenden Wizard ermöglichen.

## Ergebnis und untersuchter Stand

Der Agent besitzt echte Fachdienste, erfüllt aber das gewünschte Arbeitsverhalten noch nicht durchgängig. Besonders neue Projekte werden in einen formularabhängigen Einstieg umgeleitet. Die Ursache ist nicht allein die Qualität des Sprachmodells: Regelparser, Vorlagenexpansion, Zustandsverwaltung und Werkzeugauswahl schränken den möglichen Ablauf ein.

Die heute per GET gelesene Anwendung meldet Build `9b599fccf321`, Source SHA `9b599fccf321ec5008eb54dcdc7a18683a6d27722aaaa001b7d9731e2e0d709e`. Parserreproduktionen und 75 Frontendtests liefen gegen dessen eingefrorene Quelle unter `backend/test-output/release-source/domain-identity-20260914`. Die 74 Backendtests liefen gegen den aktuellen Arbeitsstand, nicht gegen ein neu gebautes Releaseimage. Dieser Unterschied ist wesentlich: Der gemeinsame Arbeitsstand enthält zusätzliche Änderungen.

Im aktuellen Projekt `network-project-20260910042736034-d11591d0` meldet die gelesene Workflowübersicht null kanonische Hardwareobjekte und keinen gespeicherten Wizardauftrag im Kontext. Daher lässt sich die genaue Browser-Eingabe des Screenshots aus diesem API-Stand nicht rekonstruieren. Der sichtbare Fehlerzustand ist unabhängig davon mit dem ausgelieferten Parser reproduziert. Es wurden keine Produktdaten geändert, keine Produkt-Schreibtests ausgeführt und kein neues Release installiert.

## Belegte Fehler

### P0: Vorlagen ersetzen unbekannte Nutzervorgaben

`frontend/src/lib/agent/engineering-specification.ts`, `expandArchitectureChains` ab Zeile 1118, ergänzt fehlende Sollzahlen aus Branchenvorlagen. Das ist für einen ausdrücklich bestellten Beispielgenerator sinnvoll, für einen realen Projektauftrag jedoch eine andere Bedeutung.

Reproduktion: „Ich möchte drei Sensoren.“, Sollzahlen Sensoren=3, Controller=0, Aktoren=0, Branche `custom`. Ergebnis: Temperature, Voltage, Current, jeweils CAN. Weder diese drei Messgrößen noch CAN wurden bestellt. `industry-templates/generic.ts` liefert die zugrunde liegenden Vorlagen. `completenessFirst` darf nicht automatisch den Übergang von realen Angaben zu einem Musterprojekt erlauben.

Der vorige Fix schützt erkannte Geräte und bestimmte Anschlüsse, nicht jeden Pfad der Vorlagenexpansion. Die Aussage, unbekannte Anschlüsse blieben durchgängig offen, war deshalb zu weitgehend.

### P0: Sackgasse ohne Controller

`equipment-clustering.ts:462–465` unterscheidet nicht zwischen keinem passenden Controller und mehreren Kandidaten. Bei null Controllern lautet der Befund fälschlich „Mehrere fachlich mögliche Controller“.

`agent-chat-core.tsx:1004` ff. zeigt dafür ausschließlich Auswahl aus `controllerOptions`; das Feld wird ohne Kandidaten deaktiviert. Zeilen 1725–1726 blockieren die Übergabe bei ungeklärter Zuordnung. Um Zeile 2971 wird „Kein Controller … erkannt“ angezeigt, ohne dort einen Controller ergänzen oder die Architektur als bewusst unvollständigen Entwurf fortsetzen zu können. Die technische Freigabe zu blockieren ist richtig; die fehlende Bearbeitungsaktion ist der Fehler. Cluster abwählen darf kein Ersatz sein, wenn damit beauftragte Geräte verschwinden.

### P0: Kleine Sprachvarianten verändern die Architektur

Reproduktion gegen Releasequelle:

| Eingabe und bestätigter Umfang | Beobachtung |
| --- | --- |
| Ursprünglicher Satz mit „respary pi“, drei Sensoren, fünf bestätigten Ventilen | Pi, drei Temperatursensoren, fünf Ventilaktoren; ein Controllerzweig, keine ungeklärten Owner; unbekannte Anschlüsse Other |
| „Projekt mit einem Raspberry-Pi und drei Temperatursensoren und zwei Ventilen“, Soll 1/3/2 | Pi und Sensoren erkannt; Ventile nicht als Ventile erhalten; MainControlStellglied, MainControlSchaltausgang und zusätzlicher MainControl mit UART; Sensoren bleiben ungeklärt |
| Drei Temperatursensoren ohne Controllerangabe | Drei richtige Sensoridentitäten; keine Möglichkeit der Zuordnung ohne ergänzten Controller; irreführender Mehrdeutigkeitsbefund |

`impliedHardwareNames` um Zeile 1388 erkennt `ventil/ventile`, nicht die flektierte Form `Ventilen`. Nach der Erkennungslücke füllt die Vorlagenlogik Geräte nach; die Vollständigkeitslogik ergänzt deren Owner. Die Vorlage verwandelt damit ein Sprachproblem in eine andere technische Architektur. Ein einzelnes zusätzliches Regex genügt als Gesamtlösung nicht.

### P0: Projektauftrag im Chat endet vor der Erstellung

`backend/agent_core/core/engineering_agent.py:115–149` behandelt erkannte neue Projektaufträge vor dem allgemeinen Ausführungspfad. Dem Reasoner wird hier nur `prepare_project_request` angeboten. Anschließend folgt ein früher Return mit `INCOMPLETE` und ohne Proposals.

`backend/engineering/agent_tools/capabilities.py:17–33` erzeugt Text und eine Wizard-Aktionskarte. `project_intake.py:20` ff. formuliert fehlende Angaben als Prosa. Es entsteht kein eigener strukturierter Projektentwurf mit verbindlichen Entscheidungen. Dieser Einstieg ist absichtlich ein Übergabedienst, kein autonomer Projektersteller.

Auch eine neue Projektidentität entsteht im normalen UI derzeit im Browser: `project-actions.tsx:36,61` erzeugt die ID, setzt Browsereinstellungen und navigiert. Der vorhandene Agent arbeitet projektgebunden; Projekterstellung und Projektwechsel benötigen einen serverseitigen Dienst außerhalb der bloßen Modellwerkzeuge.

### P1: Weitere implizite Automotive-Vorgaben im Chatpfad

`agent_tools/services.py:295–303` setzt für Anforderungsexpansion und verschiedene Generatoren `domain=automotive` als Default. `agent_tools/generation.py:15–51` verwendet diese Vorgabe und ergänzt bei Funktionserzeugung unter Umständen eine ECU mit vorläufigem CAN-FD-Status. Das ist unabhängig vom zuletzt korrigierten Wizard-Technologie-Fallback. Befund aus Quellprüfung; kein neuer produktiver Generierungsversuch.

Die Branchenidentität muss aus dem gespeicherten Auftrag kommen, nicht aus dem Default jedes einzelnen Tools. Eine fachlich unbekannte Branche bleibt offen oder ausdrücklich generisch.

### P1: Verfügbarkeit ist kein Abschlussnachweis

`capabilities.catalog` ab Zeile 90 und `agent_core/registry/skill_registry.py:10` bestimmen Verfügbarkeit anhand registrierter Tools und Berechtigungen. Das belegt Aufrufbarkeit, nicht die vollständige Ausführung einer Nutzeraufgabe. Beispielsweise gibt die Struktur-Fähigkeit Analysewerkzeuge an, während ihre beschriebenen Schritte auch Übernehmen nennen. Der Katalog benötigt getrennte Angaben für erklären, planen, ausführen und fachlich abschließen.

### P1: Fachplanung ist an React gebunden

`agent-chat-core.tsx` enthält Extraktion, Sollzahlbewertung, Ownerkorrekturen, Netz-/Clusterprüfung, Rückfragen, Auftragsspeicherung, Review und Fortschrittssteuerung. `engineering-specification.ts` konstruiert bereits Funktions-, Interface-, Nachrichten- und Signalangaben im Frontend, unter anderem vorläufige 10-ms-Zyklen und Identifier ab 0x180. Ein Chat ohne Wizard kann diese Regeln nicht sauber verwenden, solange die gemeinsame fachliche Eingabe und Planung fehlen.

### P1: Bestehende Tests prüfen nicht das gewünschte Ergebnis

`frontend/e2e/project-intake.spec.ts` prüft Textübernahme, Wizardöffnung, fehlende Aktorzahl und Reload. Am Ende verlangt der Test ausdrücklich ein noch leeres Modell. Er beweist keine Erstellung des kleinen Projekts.

`backend/tests/test_project_intake.py` verlangt für den Einstieg `INCOMPLETE` und keine Vorschläge. Die vorhandenen Neun-Stufen-Fälle sichern andere, weitgehend strukturierte Vorgaben. Ein PASS dieser Tests widerspricht dem heutigen Fehler nicht. Sprachvariation, unbekannte Geräte, null Controller und Projektanlage ausschließlich im Chat fehlen als zusammenhängende Abnahme.

## Vorhandene Bausteine wiederverwenden

| Aufgabe | Vorhandener Einstieg / Dienst | Lücke für durchgängigen Chat |
| --- | --- | --- |
| Neues Projekt | Browser `project-actions`; `prepare_project_request` | Server-Projektanlage, persistierter Entwurf, Fortsetzung im Gespräch |
| Hardware und Funktionen | Klassifikation, `generate_functions`, Proposals | Exakte Geräteidentität und explizite Ownerklärung; keine fremden Defaults |
| Ports / Interfaces | Portentscheidung, `prepare_engineering_connection`, `continue_engineering_goal` | Gleiche Befehle für manuelle und agentische Anlage; Hardwaregrenzen bleiben verbindlich |
| Nachrichten / Signale | Workloads, Packing, Encodingvalidierung, Proposals | Eingaben in ein gemeinsames Schema, gezielte Korrektur statt Formularverweis |
| Routing / lokale Kommunikation | Routengenerator, Repair- und Goal-Ausführung | Funktionsgrenzen, lokale I/O, HMI-Auswahl und aktuelle Ports einheitlich berücksichtigen |
| Strukturtransfer / Dubletten | Analysewerkzeuge und UI-Übernahmewege | Übernahme als nachvollziehbarer gemeinsamer Befehl; bewusstes Merge-Review |
| Parameter / Kapazität / Timing | Python-Workflowdienste und Snapshots | Nach Änderungen automatisch betroffene Schritte aktualisieren |
| Preflight / Simulation / Analyse | Echte Jobs, Traceanalyse, Completion-Prüfungen | Zielumfang speichern, Ausfall/Wiederaufnahme und tatsächliche Artefakte sichern |
| Import / Export / Dateiauswahl | UI-Projektbundle- und Dokumentwege | Fachbefehle für Import/Export; Browser-Dateidialog bleibt sichtbare Plattforminteraktion |
| Grafische Positionierung / Auswahl | Netzwerkeditor und UI-Kontext | Auswahl/Anordnung als übertragbare Datenoperation, keine heimliche Mausautomation |

Die Matrix ist eine Prüfung der genannten Einstiegspfade, kein Vollbeleg aller Schaltflächen im gesamten Simulator. Ein vollständiges UI-Aktionsinventar ist ein eigenes Umsetzungsergebnis.

Positiv: `ToolAuthority` bindet Projekt und Berechtigungen serverseitig; der Agent darf diese nicht per Toolargument ersetzen. Vorschläge, Reviews, Revisionen und echte Goal-Folgearbeiten existieren. `WizardCommand` besitzt START/CONTINUE/AMEND, Operations-ID, Revision und Ziel. Diese Absicherungen erhalten und erweitern, nicht durch einen zweiten informellen Chatworkflow umgehen.

## Zielarchitektur

Chat, Wizard und einzelne Editoren verwenden dieselbe fachliche Befehls- und Abfrageschicht im Python-Core. Der Wizard ist eine alternative Darstellung des gespeicherten Entwurfs; seine React-Komponenten werden nicht im Hintergrund bedient.

Vorgeschlagener gemeinsamer `EngineeringDraft`:

- draft_id, project_id, revision, Originalanforderung und Herkunft jeder Ergänzung;
- Branchenidentität und Modus REAL_PROJECT oder ausdrücklich EXAMPLE_PROJECT;
- Geräte mit stabilen IDs, Typ, Anzahl, Quelle, Bestätigungsstatus und offenen Eigenschaften;
- Funktionen, Owner, physische Anschlüsse, Räume, lokale/externe Kommunikationsverträge;
- offene Entscheidungen mit stabiler ID, betroffenen Objekten und auswählbarer Korrektur;
- Zielumfang, genehmigte Annahmen, Vorschläge und Ergebnisse der Prüfung.

Fakten, abgeleitete Werte, vorgeschlagene Annahmen und unbekannte Werte bleiben unterscheidbar. Eine Konfidenzzahl ersetzt keine Bestätigung. Insbesondere sind unbekannt und null Geräte unterschiedliche Zustände.

Zustandsübergänge: DRAFT → NEEDS_DECISION oder READY_TO_PLAN → PLANNED → REVIEW_REQUIRED → APPLYING → VALIDATING → COMPLETED. Technische Fehler erhalten einen wiederholbaren Fehlerzustand mit konkreter Aktion; geänderte Quellrevisionen machen den Plan veraltet. Entwürfe dürfen unvollständig gespeichert werden, Simulation und technische Freigabe verlangen die passenden Nachweise. Bestehende persistierte Wizard-/Goalzustände werden durch Adapter migriert, nicht blind umbenannt.

Der Agent liest den Projektstand, ergänzt nur belegte Fakten, fragt zu echten Entscheidungen, plant die nötigen Abhängigkeiten und führt sie über dieselben Dienste aus. Nach einer Antwort setzt er denselben Auftrag fort. Er darf einen prüfbaren Modellvorschlag mit kompaktem Review im Chat präsentieren. Der technische Ablauf bleibt im Hintergrund; Projektwechsel, zusätzliche Hardware, unklare Anschlüsse oder Modellfreigaben werden nicht vor dem Nutzer versteckt.

Die vorhandenen Reviewregeln bleiben bestehen. „Ohne Wizard“ bedeutet keine Umgehung von Review oder Berechtigungen. Ein bestätigter Auftrag deckt seine freigegebenen Folgeschritte ab; Änderungen außerhalb dieses Umfangs benötigen eine gezielte neue Entscheidung. Links dienen der Nachkontrolle, nicht dem Ersatz einer noch ausstehenden Operation.

## Umsetzung in sechs überprüfbaren Paketen

### 1. Sofortige Integrität und Entsperrung

Betroffen: Parser, Vorlagen, Clustering, `agent-chat-core.tsx`.

- REAL_PROJECT darf fehlende Angaben nicht mit Beispielgeräten oder Protokollen auffüllen.
- Mengen- und Typauslegung mit flektierten deutschen/englischen Formen; bei Nichterkennung Rückfrage mit Originaltext.
- Null Controller, unklarer Owner und mehrere Kandidaten getrennt melden.
- Im betroffenen Bereich „Controller ergänzen“, „Vorhandenen zuordnen“, „Anforderung korrigieren“ und „Entwurf speichern“ anbieten. Ergänzen bleibt Teil desselben Auftrags.
- Kein automatisches Abwählen beauftragter Geräte; notwendige technische Prüfungen bleiben aktiv.
- Alle impliziten Branchen-/Technologie-Defaults der Aufrufkette erfassen und aus dem Auftrag ableiten.

Abnahme: Screenshotfall durch Ergänzung eines Controllers lösbar; Temperature/Voltage/Current werden bei drei nicht näher bezeichneten Sensoren nicht als bestätigte Geräte erfunden; Formulierung „zwei Ventilen“ erhält die Ventile und fügt keinen weiteren Controller hinzu.

### 2. Gemeinsamer persistierter Entwurf

Betroffen: Python-Auftrags-/Kontextdienste, `wizard_commands.py`, Frontend-Parseradapter und Einstellungen.

- Schema, Validierung, Herkunft und Versionsmigration des EngineeringDraft einführen.
- Draft-Anlage und AMEND serverseitig idempotent; Revisionkonflikte mit Wiederherstellung der Eingabe.
- Fachliche Extraktion schrittweise aus dem Formular lösen. Alte strukturierte Texte über einen versionierten Adapter lesen.
- Chat und Wizard zeigen dieselben offenen Entscheidungen; Antwort, Reload und Projektwechsel behalten deren Identität.

Abnahme: Derselbe Auftrag erzeugt über Chat und Wizard semantisch gleiche Entwürfe; keine schleichende Änderung von Anzahl, Branche, Scope oder Technologie beim Wechsel.

### 3. Projekterstellung ohne Wizard

Betroffen: Projektservice, MCP-Katalog, EngineeringAgent, Projektaktionen, Chatdarstellung.

- Projektanlage als serverseitiger idempotenter Dienst; ursprüngliches Projekt unverändert lassen und neue ID ausdrücklich zuordnen.
- `prepare_project_request` zu einem echten Intake mit gespeichertem Entwurf erweitern; das frühe Ende nicht einfach entfernen, sondern durch einen gespeicherten Folgeauftrag ersetzen.
- Fehlende Stückzahl, Anschlusstyp oder Regelungsart gezielt im Chat beantworten lassen; bekannte Antworten wiederverwenden.
- Bestätigte Eingaben durch gemeinsame Planung, Proposal, Review und Apply ausführen.
- Ergebnis nennt angelegte Objekte und offene technische Punkte, nicht bloß eine Wizard-Aktion.

Abnahme: Leeres neues Projekt ausschließlich über Chat bis zum gültigen Modell erstellen; Popup bleibt geschlossen. Ursprung, Draft, Projekt-ID und Resultat müssen nach Reload erhalten bleiben.

### 4. UI-/Agent-Funktionsgleichheit

Betroffen: Fähigkeitenkatalog, MCP-Adapter, Fachservices und betroffene Editoren.

- Inventar jeder fachlichen UI-Aktion mit Eingabeschema, Fachdienst, Berechtigung, Revision, Rückgabe und Prüfnachweis erstellen.
- Fehlende Wrapper für erstellen, ändern, zuordnen, verschieben, entfernen, importieren und exportieren ergänzen; vorhandene Dienste wiederverwenden.
- Fähigkeiten getrennt als erklärbar, planbar, ausführbar und abschließbar kennzeichnen.
- UI-only-Plattformaktionen wie lokaler Dateidialog oder rein optischer Zoom ausdrücklich ausweisen.

Abnahme: Jede als ausführbar angezeigte Fähigkeit bewirkt über echten Backendaufruf das gleiche gespeicherte Ergebnis wie die entsprechende UI-Aktion. Keine Linkkarte gilt als Ausführung.

### 5. Ausführung, Reparatur und Wiederaufnahme

Betroffen: Goal-/Workloadausführung, Vorschlagsdienste, Workflow-Abhängigkeiten, Chatstatus.

- Plan je Auftrag mit Abhängigkeiten, erwarteten Artefakten und Freigabeumfang speichern.
- Modell-/Routingänderungen invalidieren und aktualisieren nur die betroffenen Folgeschritte.
- Reparierbare Datenlücken in konkrete Draftkorrekturen umsetzen; fachlich unklare Architektur nicht erfinden.
- Retry begrenzen, identische Operationen entdoppeln, Antworten erst nach bestätigter Persistenz als angenommen darstellen.
- Abschluss hängt an aktuellen kanonischen Artefakten und Zielbedingungen. Ein Projektmodell kann fertig sein, während Simulation noch nicht beauftragt oder technisch offen ist.

Abnahme: Restart, verlorene Antwort, veraltetes Review und Teilfehler führen weder zu Duplikaten noch zu falschem COMPLETE. Lokale Sensorwerte bleiben lokal; tatsächlicher lokaler Transport wird weiter in Last und Zeitplan berücksichtigt.

### 6. Abnahme und Auslieferung

Neue Pflichtfälle zusätzlich zum bestehenden Gate:

1. Raspberry Pi, drei Temperatursensoren, zwei/fünf Ventile über mehrere Formulierungen und über mehrere Chatantworten.
2. Drei unbestimmte Sensoren; fehlender Controller; Controller wird im Chat und alternativ im betroffenen Wizardbereich ergänzt.
3. Branchentreue Embedded, Gebäude, Industrie und Automotive; Technologie bleibt unabhängig von Branche.
4. Chat-only-Erstellung mit echtem Review/Apply, anschließend Modellinventar und Beziehungen prüfen.
5. Gleicher Auftrag über Wizard: semantischer Vergleich der IDs/Beziehungen, Counts, Technologien, Signale und Grenzen.
6. Bekannte/fehlende Ports, Grenzen und ungültige Technologie: konkrete Korrektur statt Ersatzbus.
7. Lokaler Sensor und bewusst freigegebener externer Funktionswert: Routing, DLC, lokale Buslast und externe Last getrennt prüfen.
8. Neun Stufen nur mit technisch unterstützter vollständig spezifizierter Fixture; tatsächliche Jobs und Traceabdeckung. Unvollständige Embedded-Elektrik darf kein künstliches PASS erhalten.
9. Entwurf-Reload, Projektwechsel, Doppelstart, AMEND, Restart während Ausführung, veraltete Freigabe und verlorene Antwort.
10. KI-Ausfall: vorhandene Fakten und Entwurf bleiben bearbeitbar, keine erfundenen Ausführungserfolge. Ergänzend kleiner echter Modelllauf zur Sprach-/Toolqualität; Mocktests allein genügen dafür nicht.

SQL ausschließlich über `scripts/run-isolated-tests.py`. Release über vollständiges `scripts/run-release-gate.py`, exaktes PASS-Image, Backup und Prüfung des unveränderten Produktbestands. Temporäre Testcontainer nach Ende entfernen; Belege außerhalb ihrer Wegwerfvolumes sichern.

## Heute tatsächlich geprüfter Umfang

- Automatischer Project-Scanner: Inventar erstellt, 18.434 Dateien erfasst. Das ist keine semantische Vollprüfung aller Dateien. Runtime, Test-output, Abhängigkeiten und Junctions wurden nach Ausschlussregeln behandelt.
- PEP 8 NICHT geprüft: `pycodestyle` fehlt. Fehlende DE/EN-Marker aus dem Scanner sind Dokumentationsbefunde, keine Ursachen der Wizardblockade.
- Fünf Parser-/Clusterreproduktionen gegen Releasequelle; beobachtete Resultate in `backend/test-output/engineering-agent-audit-20260915-reproduction.json`.
- 75 bestehende Frontendtests gegen Releasequelle bestanden. Log: `backend/test-output/release-source/engineering-agent-audit-frontend-20260915.log`.
- 74 bestehende Backendtests gegen aktuellen Arbeitsstand bestanden, eine bekannte Pydantic-Warnung. Isolierte DB `nis_test_18daefe22ad9`; Container danach entfernt. Log: `backend/test-output/engineering-agent-audit-backend-20260915.log`.
- Keine neue Browser-E2E-Ausführung und kein neuer Release-PASS in diesem Audit. Kein echter LLM-Qualitätslauf; Tool-/Reasonertests verwenden teilweise kontrollierte Testdoubles.
- Gelesene Schwerpunkte: Intake, EngineeringAgent-Dispatch, Tools/Capabilities, Parser/Clustering, Wizard-Gates/Restoration, Projektanlage, Proposalautorität, Goal-Folgearbeiten und aktuelle E2E-Definitionen. Nicht jede Fachformel, Exportvariante oder UI-Aktion ist abschließend geprüft.

## Regelbezug

`WIZARD_EXECUTION_CONTRACT.md`: Projekt-/Revisionsbindung, nachvollziehbare Blocker, kein erfundenes Modell und Releasebelege. `WIZARD_RELEASE_GATE.md`: isolierte Tests und unveränderlicher Kandidat. `COMMUNICATION_DESIGN_CONTRACT.md`: lokale Kommunikation, Encoding und getrennte Zeit-/Kapazitätsnachweise. `SPATIAL_ARCHITECTURE_CONTRACT.md`: Owner, Raum und Transport getrennt. `NETWORK_NAMING_CONTRACT.md`: persistierte Netzidentität.

Zusätzlich wurden die einschlägigen Ziel- und Data-Gap-/Python-First-Abschnitte des zuvor beauftragten Dokuments `H:/OneDrive/Download/NETWORK_SIMULATOR_AUTONOMOUS_MODEL_AWARE_AGENT_ORCHESTRATION_CODEX.md` sowie die Modelltrennung im Port-/Interface-Entscheidungsdokument gelesen. Nicht alle Abschnitte dieser umfangreichen Dokumente wurden in diesem Audit erneut vollständig geprüft. Der heutige Ausbauplan konkretisiert den bereits formulierten Anspruch an tatsächliche Zielerfüllung.
