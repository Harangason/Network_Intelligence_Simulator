# KI-Einstiege und ausführbare Instandsetzung

Stand: 11.09.2026. Kanonisches Projekt: `I:\PycharmProjects\My_first_Network_Simulator`.

## Auftrag und Abgrenzung

Geprüft wurden die sichtbaren KI-/Agent-Einstiege, das gemeinsame Verzeichnis mit 20 Fähigkeiten, die aufgerufenen HTTP-/MCP-Werkzeuge und die Übernahmewege. Eine Fähigkeit im Verzeichnis allein beweist keine erfolgreiche Ausführung. Die unten genannten Laufzeitprüfungen unterscheiden echte Modellaufrufe, isolierte Datenbankausführung und Browserfixtures.

Verbindlich bleiben die räumliche Architektur, der Kommunikationsdesignvertrag, die Netzbenennung und die beiden vom Nutzer gelieferten Agent-Spezifikationen. Die ausführliche Prüfung ihrer Einzelschritte steht in `16_MODEL_AWARE_EXECUTION.md`. Dort offene allgemeine GoalTypes und Transportadapter werden durch diesen Bericht nicht pauschal für erledigt erklärt.

## Verzeichnis und Ausführungspfade

| Einstieg / Fähigkeit | Modell und Fachwerkzeug | Ergebnis / Übernahme |
|---|---|---|
| Globaler Engineering-Assistent | LocalEngineeringReasoner und registrierte MCP-Werkzeuge | Antworten, Rückfragen, Proposal, autorisierte Ausführung; Projektkontext serverseitig geprüft |
| Fähigkeiten und Wizard-Fragen | Kanonisches Fähigkeitsverzeichnis, `inspect_assistant_capabilities` | Ausführbare Kacheln und zutreffende Ablaufbeschreibung; dafür ist kein erfundener Modellaufruf erforderlich |
| Signal anlegen | Reasoner → `generate_signals`, `validate_signal` | Editierbarer Vorschlag, Kodierungsprüfung, Review-/Übernahmepfad |
| Nachricht anlegen | Reasoner → `generate_messages`, `validate_message` | Publisher, Anschluss, expliziter Payload und Übernahme |
| Funktion anlegen | Reasoner → `generate_functions`, `map_function_to_hardware` | Vorschlag mit Hardwarebezug |
| Hardware anlegen | Reasoner → `classify_device`, `get_device_capabilities` | Geräteklasse und überprüfbare Hardwareangaben |
| Physischer Anschluss | Reasoner → `inspect_port_decision`, `prepare_engineering_connection`, `continue_engineering_goal` | Gespeicherte Hardwareentscheidung, Port/Netz/Routing, technische Folgeprüfungen |
| Kommunikationsschnittstelle | Reasoner → `generate_function_interfaces` | Logische Schnittstelle mit kanonischer Zuordnung |
| Reparatur-Agent | Lokaler Fachagent, `prepare_communication_repair`, `review_communication_repair`, `continue_communication_repair` | Aktuelle Architektur prüfen, konkrete Strategie wählen, atomar instandsetzen, Routing validieren, Kapazität/Timing inklusive Entwürfen nachberechnen |
| Engineering-Wizard | Reasoner und `generate_wizard_model`, `generate_wizard_communication_contract`, `generate_wizard_routing`, `generate_wizard_network`, `generate_wizard_parameters` | Bestehender stufenweiser Proposal-/Review-Ablauf |
| Routing / „Mit KI beheben“ | Technische Kandidatenerzeugung plus echter lokaler Fachagent; MCP `generate_routing`, `validate_route` | Editierbarer Vorschlag mit Modellbegründung; abgelehnte Kandidaten bleiben kenntlich, Empfänger werden nicht still entfernt |
| KI-Strukturtransfer | `analyze_structure_transfer` und lokaler Fachagent | Zielbezogener Vorschlag und bestehende geprüfte Übernahme |
| Raumarchitektur / KI-Architekturprüfung | Projektgebundener Reasoner, `inspect_spatial_architecture` und Architekturwerkzeuge | Modellgestützte Prüfung und editierbarer Vorschlag; keine erfundenen räumlichen Identitäten |
| Parameter | Reasoner → `generate_wizard_parameters` | Modellbezogene Auslegung und Prüfung |
| Kapazität / Timing | Reasoner → `calculate_capacity`, `plan_capacity_remediation` | Rechnerische Evidenz und Abhilfekandidaten; Berechnung ist kein Nachweis funktionaler Akzeptanz |
| Preflight | Reasoner → `validate_simulation_preflight` | Konkrete Fehler und offene Nachweise |
| Simulation | Reasoner → Szenario-, Snapshot-, Start-, Status- und Ergebniswerkzeuge | Echter Simulationslauf nach den bestehenden Prüfschritten |
| Ursachenanalyse / Trace „Ask AI“ | Projektgebundener Reasoner → Root-Cause-, Deadline-, Fault- und Vergleichswerkzeuge | Ausgewählter Lauf, Befund und Zeitkontext werden übergeben |
| Intelligence „Ask AI“ / „KI prüfen lassen“ | Projektgebundener Reasoner → `evaluate_architecture`, `assess_intelligence` | Befundbegründung und überprüfbare Vorschläge |
| Structure Wizard / Abhängigkeiten | `evaluate_structure_dependencies` und lokaler Fachagent | Fachliche Bewertung der technischen Zuordnung, bestehender Übernahmepfad |
| Systemdubletten | Vergleichsalgorithmus + expliziter Auftrag „Fachagent prüfen lassen“ an den Reasoner | Unterschiede erklären, bestehende Zusammenführung nach Entscheidung |
| KI-Fehlervorschläge | `generate_fault_proposals` und lokaler Fachagent | Modell bewertet technisch begrenzte Szenarien; Auswahl/Magnitude editierbar, keine automatische Aktivierung |

Status-/Fortschrittskomponenten und die Modelldiensteinstellungen sind keine eigenen Agenten. Die bisher als „KI-Layout · EVA“ bezeichnete Anordnung ist ein deterministischer Layoutalgorithmus. Sie heißt jetzt entsprechend „EVA-Anordnung“; daneben steht die echte KI-Architekturprüfung. Die Fähigkeit wurde damit ergänzt, nicht nur umbenannt.

## Behobene Lücken

1. Reparatur war im MCP-Verzeichnis nur als Inspektion erreichbar. Ein dauerhafter Auftrag verbindet jetzt Modellbewertung, Strategieentscheidung und tatsächliche Ausführung. Das Modell kann die menschliche Architekturentscheidung nicht selbst erteilen.
2. Modellinferenz hält nicht mehr die kanonische Schreibtransaktion. Große Reparaturpläne werden in gespeicherten Abschnitten bewertet. Wiederaufnahme überspringt bereits bewertete Kandidaten; vor Veröffentlichung wird die Modellrevision erneut geprüft.
3. Kurze, serverseitig zurückübersetzte Kandidatenkennungen verhindern fehlerhafte Übernahme langer Hash-IDs. Fehlende, doppelte oder fremde Entscheidungen werden zurückgewiesen. Modellfehler sind sichtbar und werden nicht als KI-Erfolg ausgegeben.
4. Fehlende Routing-Einträge werden aus expliziten Empfängern des Nachrichten-Kommunikationsvertrags rekonstruiert, sofern Funktion, Schnittstelle und kompatibler physischer Weg eindeutig sind. Signale und Kodierungen bleiben erhalten. Ein erreichbares Nachbargerät ersetzt keinen bisherigen Partner.
5. Nach einer ausgewählten Reparatur erfolgen Routingprüfung und Kapazitäts-/Timingberechnung einschließlich der Entwurfsrouten. Fachliche Freigabe und bestätigte Funktionsfristen bleiben gesondert; der Entwurf überschreibt keine freigegebene Kapazitätsbasis.
6. Strukturtransfer, Abhängigkeitsbewertung, Routingvorschläge und Fehlerszenarien erhalten eine echte lokale Modellbewertung statt ausschließlich regelbasierter Ausgabe unter einem KI-Namen.
7. Die Trace-Aktionszeile enthält bedienbare Aktionen. Die Weiterleitung `/studio/trace-analysis` erhält jetzt `view`, `job` und `focus_s` zusätzlich zum Projekt.
8. Extern vorbereitete Agent-Aufträge werden an das aktive Projekt gebunden und öffnen den Assistenten. Verspätete Reparaturantworten können eine bereits übernommene Strategie nicht wieder anzeigen.

## Verifikation

- Isolierter PostgreSQL-Lauf: **142 Tests bestanden**, darunter tatsächliche Neuanlage einer Route aus bestehenden Empfängerreferenzen, Originalpayload, Entwurfskapazität, atomarer Rollback, Idempotenz, Projektgrenzen, MCP-Ausführung und gespeicherte Teilprüfungen. Testdatenbank: `/nis_bus_naming_tests`; keine Produktreparatur ausgeführt.
- **17 Frontend-Vertragstests bestanden**. TypeScript im vollständigen Produktionsbuild erfolgreich.
- Browserprüfung: Reparaturvorschau vor Modellantwort, 390×844-Dialog, ausdrückliche Strategieauswahl, verspätete Antwort verworfen, Trace-Auftrag mit korrektem Projekt und Lauf. Dabei werden Modellschreibzugriffe abgefangen; dieser Test ersetzt keinen echten Modelltest.
- Echter lokaler Modelltest mit `llama3.1:8b`: korrekte Funktionspartner akzeptiert, falsche Partner/lokale I/O-Weiterleitung abgelehnt.
- Echter Modelllauf am Projekt `network-project-20260910042736034-d11591d0`: **102 Reparaturgruppen bewertet**, kanonische Kommunikationsressourcen vor/nach der Prüfung unverändert. Die Prüfung erzeugt ausschließlich Auftrags-/Auditdaten und ist keine stillschweigende Strategieübernahme.
- Der abschließende Live-Lauf prüft dieselben 102 Gruppen in neun gespeicherten Abschnitten bis `REVIEWED`. Arbeitsauftrag: `repair-e53448a187644030925c976d3ee585e9`.
- Zusätzlicher echter Chat-/MCP-Lauf beantwortet eine Modellfrage mit Status `ANSWERED`. Der Fähigkeits-Browsertest bestätigt alle 20 registrierten Einträge, Reparatur-Agent-Antwort, Kacheln, Signal-Wizard, die vier Agent-/Wizard-Dialoge, denselben Projektnamen wie im Header und Ablehnung widersprüchlicher Projektkontexte mit HTTP 409. Die Topologie des Nutzerprojekts bleibt unverändert.
- Laufprotokolle: `backend/runtime/specialist-execution-tests.log`, `specialist-build.log`, `specialist-live.json`, `specialist-project.json`, `specialist-ui.json`.

## Verbleibende konkrete Grenzen

Im geprüften Produktstand sind 102 Gruppen offen und keine aktuell eindeutig ausführbare Strategie verfügbar. Bei 99 Gruppen waren die Empfängergeräte bereits im Kommunikationsvertrag vorhanden; nach deren Berücksichtigung werden fehlende oder mehrdeutige Partnerfunktionen/Schnittstellen sichtbar. Andere Gruppen haben keinen durchgängigen kompatiblen Weg. Die Reparatur zeigt diese gespeicherten Partner und bietet den Anschlussplanungsagenten an. Sie darf weder fremde Empfänger einsetzen noch nicht belegte Hardwarefähigkeiten erfinden.

Die technische Wiederherstellung ist durch die isolierten Ausführungstests belegt, nicht durch Änderungen dieser ungeklärten Produktdaten. Die allgemeine automatische Konstruktion neuer Gateway-Protokollumsetzungen, beliebiger Stream-/Service-Transporte sowie alle noch offenen universellen GoalType-Adapter aus Bericht 16 bleiben getrennte Implementierungslücken. Eine Aussage „alle Schritte beider Spezifikationen vollständig umgesetzt“ wäre deshalb weiterhin unzutreffend.
