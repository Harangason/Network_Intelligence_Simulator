# Fachaktionen: Oberfläche und Engineering-Agent

Arbeitsinventar vom 2026-09-15. „Vorhanden“ bezeichnet einen registrierten
Backendpfad, keinen Beleg für jeden möglichen technischen Eingabefall.
Eine CAPABILITY-Karte öffnet eine Oberfläche und schreibt selbst kein Modell.

| Fachaktion | Agentenwerkzeug / Fachdienst | Ausführung und Grenze |
| --- | --- | --- |
| Objektfelder erfahren | `describe_model_object_fields` / `ENTITY_SPECS` | Reale Pflichtfelder, editierbare Felder und Enum-Werte; nur lesend |
| Modellobjekt anlegen | `create_objects_via_proposal` / Proposal-Service, Repository | CREATE-Vorschlag, keine vom Agenten gesetzte Freigabe |
| Modellobjekt ändern | `update_object_via_proposal` / Proposal-Service | Objekt-ID und Version; Review/Apply erforderlich |
| Modellobjekt entfernen | `delete_object_via_impact_analysis` / Proposal-Service, Repository | Agent darf Auswirkungsanalyse und Vorschlag erzeugen; nur menschlicher Review und autorisiertes Apply löschen. Tatsächlicher MCP-/SQL-Fall geprüft |
| Hardware klassifizieren | `classify_device`, `get_device_capabilities` | Registerauskunft; kein Ersatz für eine Geräteanlage |
| Funktionen erzeugen | `generate_functions` | Vorhandene Hardware oder explizite neue Hardware, Technologie und Statuszyklus; validierter Vorschlag |
| Funktion verschieben | `map_function_to_hardware` | Explizite Hardware-ID, Vorschlag |
| Hierarchie zuordnen | `plan_structure_assignments` / `structure.assignment_updates` | Gemeinsame Zuordnungslogik mit dem Structure Wizard; Vorschlag, Review/Apply |
| Physischer Anschluss | `generate_hardware_interfaces`, Port-/Goal-Werkzeuge | Explizite Technologie; Hardwaregrenzen/Strategieentscheidung beachten |
| Logische Schnittstelle | `generate_function_interfaces` | Funktions-ID und Technologie; Vorschlag |
| Nachricht und Signale | `generate_messages`, `generate_signals`, Packing/Encoding-Dienste | Kodierung, Payload, Producer und tatsächlicher Transport bleiben Fachbedingungen |
| Netzwerk | `create_network_proposal`, `assign_network_to_interface` | Technologie ausdrücklich angeben; persistierte Namensregeln |
| Routing | `find_route_candidates`, `generate_routing`, `validate_route` | Physische Wege, lokale Weiterleitung und Freigabe gelten weiterhin |
| Kommunikation reparieren | `prepare_communication_repair`, `continue_communication_repair` | Gespeicherte menschliche Strategie, atomare Übernahme, Nachprüfung |
| ECU-Strukturtransfer | `analyze_structure_transfer`, `plan_structure_transfer` / `structure_transfer` | Gemeinsamer Vorschlag, Review/Apply; Zuordnung und Herkunft verhindern erneute Anlage |
| System-Dubletten | `inspect_system_duplicates` | Nur Vergleich; kein automatisches Zusammenführen behaupten |
| Projektentwurf | `prepare_project_request`, `inspect_project_draft`, `update_project_draft` | Persistiert und revisionsgebunden; noch kein kanonisches Modell |
| Neues Projekt aus Entwurf | `create_project_from_draft` | Idempotente neue Projekt-ID; Ursprungsprojekt erhalten |
| Modell aus Entwurf | `plan_project_model` | Gemeinsamer Generator; menschlicher Review/Apply auch im Chat |
| Workflow aus Entwurf | `prepare_draft_workflow` + START/AMEND/CONTINUE | Vorbereitung ist kein Start; tatsächlicher Abschluss benötigt aktuelle Artefakte |
| Parameter | `generate_wizard_parameters` | Bestätigte technologieabhängige Defaults speichern |
| Kapazität / Timing | `calculate_capacity`, `plan_capacity_remediation` | Kapazität und funktionale Fristen getrennte Nachweise |
| Preflight | `validate_simulation_preflight` | Prüfung; keine automatische Freigabe fehlender Fachangaben |
| Simulation | Snapshot, Start, Status, Results | Tatsächlicher persistierter Job; keine Fortschrittskarte als Ergebnis |
| Trace / Ursachen | Trace-/Reasoning-Werkzeuge | Lauf- und Zeitbezug, Evidenz, begrenzte Schlussfolgerungen |
| Intelligence | `evaluate_architecture`, `assess_intelligence` | Gespeicherte Bewertung mit aktuellem Bezugsstand |
| Fehlerszenarien | `generate_fault_proposals`, `plan_fault_activation` | Ausgewählte aktuelle Fehlerziele als prüfbares Szenario; menschliches Review/Apply aktiviert, Lauf separat starten |
| Engineering-Dateiimport | `preview_model_import`, `plan_model_import` / `importer` | Gleicher Parser und Feldadapter wie UI; bis 5 MiB im Agenten, korrigierbarer Vorschlag mit Review/Apply und Importherkunft |
| Projektpaket exportieren | `export_project_bundle` / `ProjectBundleService.export` | Aktueller projektgebundener Paketinhalt bis 5 MiB oder Downloadadresse für aktuellen Stand; keine Modelländerung |
| Vollständiges Projektpaket wiederherstellen | `plan_project_bundle_restore` / `ProjectBundleService.import_bundle` | Menschlich geprüfter Import in ein neues Projekt, tatsächliche ID-Neuzuordnung und wiederholbares Apply. Historische Belege bleiben veraltet; gespeicherte Ausführungsfreigaben werden nicht aktiviert |
| Zoom, Scroll, lokaler Dateidialog | Oberfläche | Plattform-/Darstellungsaktionen; kein fachlicher Modellabschluss |

## Gemeinsame Autorität

MCP bekommt keine menschliche Review-Funktion. Vorschläge werden über den
geschützten Review-Endpunkt geprüft; Apply akzeptiert ausschließlich freigegebene,
aktuelle Vorschläge. Eine Änderung des Modellstands führt zu OUTDATED. Eine
Änderung eines zugrunde liegenden Drafts sperrt die alte Draftfreigabe ebenfalls.
Der Fähigkeitenkatalog berücksichtigt zusätzlich die aktuellen Werkzeugrechte.

## Nachweisgrenze

Neue tatsächliche SQL- und Browserbelege stehen in
`ENGINEERING_AGENT_IMPLEMENTATION_STATUS.md`. Dieses Inventar deckt fachliche
Aktionsgruppen ab. Es ist noch keine vollständige Zuordnung jedes einzelnen
UI-Buttons zu einem erfolgreich ausgeführten E2E-Fall. System-Dubletten sind
ausdrücklich Analyse; ausgewählte Strukturänderungen verwenden die gemeinsamen
Transfer-, Zuordnungs- und Objektvorschläge. Plattformaktionen bleiben in der UI.
