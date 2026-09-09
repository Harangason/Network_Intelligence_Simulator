# Modell, Wizard und Simulationsumfang: umgesetzte Korrekturen

Stand: 9. September 2026. Kanonisches Repository `I:/PycharmProjects/My_first_Network_Simulator`.

## Struktur und Zuordnung

- `frontend/src/lib/engineering-ownership.ts` bildet dieselben Elternbeziehungen wie das Backend ab. Eine Kommunikationsschnittstelle hängt entweder an einer Funktion oder direkt an einem Gerät der Klassen 0–2. Fehlerhafte Referenzen bleiben als Fehler sichtbar.
- Structure Tree, Drag-and-drop, Anlegen und Structure Wizard verwenden diese Regel. Bei einfachen Sensoren und Aktoren entfällt die künstliche Funktionsstufe. Das behebt die Ursache der zuvor 199 falsch als nicht zugeordnet dargestellten Schnittstellen.
- Signale zeigen getrennt System, Quellgerät und optionale Funktion. Gültige direkte Gerätesignale erklären die fehlende Funktionsstufe. Ein fehlender Elternverweis wird nicht als zulässige Leerstelle getarnt.
- Die Oberfläche unterscheidet **physische Anschlüsse** von **Kommunikationsschnittstellen**. Letztere gruppieren Nachrichten und sind keine zusätzliche physische Buchse.
- Explizite `HardwareNode.identity.system_owner_id` bestimmt die Systemdarstellung. Die Tree-Ansicht verwendet keine Namensheuristik mehr. Die Topologie-Synchronisierung liest die kanonischen Identitäten; eine Umverdrahtung darf den fachlichen Systemeigentümer nicht verändern.
- Neue bestätigte Wizard-Modelle speichern Eigentümer als aufgelöste lokale Referenzen. Bestehende manuell gesetzte Eigentümer werden beibehalten.
- Änderungen an Funktions-/Schnittstelleneltern prüfen Nachrichten und physische Portbindung. Eine unvollständige Verschiebung auf fremde Hardware wird zurückgewiesen; gültige Änderungen aktualisieren Objektbeziehungen atomisch.

Die Migrationsfunktion `backend.engineering.system_ownership.migrate_confirmed_system_owners(project_id, apply=False)` ist standardmäßig eine Vorschau. Sie berücksichtigt nur eindeutige, zuletzt akzeptierte Wizard-Belege, respektiert explizite Zuordnungen, synchronisiert Topologiemetadaten und ist idempotent. Listen werden vollständig paginiert. Keine Live-Migration durch diesen Teilauftrag.

## Ein gemeinsamer Simulationsumfang

- Der Umfang wird im Preflight ausgewählt und über `PATCH /api/engineering/workflow/simulation-scope` gespeichert. Eine Einschränkung braucht konkrete Objekt-IDs und eine Begründung.
- Der Endpunkt erhält andere Parameter, prüft aktive IDs und invalidiert abhängige Prüfstände. Identisches erneutes Speichern löst keine neue Berechnung aus. Periodisches Nachladen überschreibt keine ungespeicherte Auswahl.
- Der Simulation Runner übernimmt den gespeicherten Umfang. Änderungen führen zurück zum Preflight.
- `simulation_scope.py` normalisiert den gemeinsamen Vertrag; `simulation_coverage.py` bestimmt benötigte IDs einheitlich. Bei Nachrichten werden alle enthaltenen Signale berücksichtigt, auch bei kombinierter Auswahl.
- Die Vorbereitung setzt den gespeicherten Umfang vor dem Filtern. Unbekannte IDs werden zurückgewiesen. Der Snapshot prüft unter der Projektsperre gegen den vollständigen kanonischen Bestand und akzeptiert keinen abweichenden Umfang. Auch Ausschlusszahlen bleiben erhalten.
- Technische Parameteränderungen ohne `simulation_scope` erhalten die vorhandene Auswahl. Das schützt den Umfang auch vor späteren Wizard-Defaults.
- Der allgemeine Parameter-Schreibpfad verlangt ebenfalls eine Begründung für explizit neue oder geänderte Teilumfänge. Unveränderte und geerbte Altwerte bleiben erhalten; die Rückkehr zu ALL braucht keine Begründung.
- Ein bereits übernommener Routing-Vorschlag wird bei verbleibender Abdeckungslücke nicht erneut zur Freigabe angeboten. Der Agent nennt fehlende Transporte und verlangt bestätigte Empfänger oder einen begründeten Umfang.

## Fehlende bestätigte Transporte im Bestand

`scripts/repair-confirmed-routes.py --project-id ID --output REPORT.json` erstellt eine Vorschau. Erst `--apply` führt technisch valide Änderungen atomisch durch den vorhandenen Review-/Apply-Pfad.

Belege sind explizite Message-Consumer, bestätigte Systemeigentümer für Sensor-/Aktorfeedback und bereits genehmigte Controller-/HMI-Verbindungen derselben logischen Schnittstelle. Der Schlüssel `(Quelle, Ziel, Nachricht)` verhindert Dubletten, einschließlich vorhandener Routen mit ausschließlich Signal-IDs. Ohne bestätigten Empfänger entsteht keine neue Route.

Auf dem isolierten Klon `nis-correction-large-0909` an PostgreSQL-Port 15439:

| Befund | Vorher | Nachher |
|---|---:|---:|
| Aktive Routen | 217 | 317 |
| Gedeckte Nachrichten | 162/309 | 262/309 |
| Nachrichten ohne bestätigten Transport | 147 | 47 |
| Technisch ungültige neue Kandidaten | — | 0 |
| Änderungen beim unmittelbaren zweiten Lauf | — | 0 |

Die 47 verbleibenden Nachrichten sind im JSON-Bericht mit IDs, Namen und Quellgerät aufgeführt. Ihre Empfänger sind fachlich offen. Bestehende Grenzwerte werden nicht angehoben, um eine Freigabe vorzutäuschen. Nach dem Backfill müssen die invalidierten Topologie-/Capacity-/Preflight-Stände geprüft werden.

Mit `--apply --refresh-topology` wurde anschließend auch die Folgeprüfung am Klon ausgeführt: 260 Hardwareknoten, 216 Kanten, alle 317 Routen eingebunden und keine neuen Hardwarekanäle. Prüfungen sichern kanonische Eigentümer, vorhandene Hardwarekanal-IDs und den gespeicherten ALL-Umfang. Capacity, Preflight und Intelligence melden wegen der 47 unbestätigten Nachrichten mit 235 Signalen weiterhin ERROR; zusätzliche Port-/Modellfehler wurden nicht gemeldet. Zehn bestehende Timeout-Budgets erzeugen Warnungen. Diese offene fachliche Grenze bleibt erhalten.

Belege: `verification/2026-09-09-confirmed-routes-preview.json`, `verification/2026-09-09-confirmed-routes-applied-clone.json`, `verification/2026-09-09-confirmed-routes-repeat-clone.json`.

Folgeprüfung: `verification/2026-09-09-confirmed-routes-refreshed-clone.json`.

## Verifikation und Zuständigkeit

- 21 zielgerichtete Backendtests für Struktur, CRUD-Beziehungen, Eigentümermigration und Wizard-Erzeugung bestanden.
- 10 zusätzliche Scope-/Agent-Tests bestanden: Persistenz, unbekannte IDs, Begründung einschließlich generischer Parameteränderungen und Altbestand, Wiederholung, gemischte Auswahl und Snapshot-Abgleich gegen den vollständigen SQL-Bestand einschließlich manipulierter Coverage-Metadaten.
- 2 Backfilltests bestanden: belegte Kandidaten/Dubletten sowie Vorschau, Apply und Wiederholung auf isolierter Datenbank.
- 5 Frontendtests für Eigentümer und Scope bestanden; TypeScript-Prüfung ohne Fehler.
- Die zusammengefassten 26 Modell-/Scope-/Backfill-/Strukturtests bestanden nach den letzten Änderungen erneut.
- Nach dem abschließenden Begründungsvertrag bestanden 40 Scope-/Workflowtests erneut.
- Der große Wizard-Integrationstest mit 251 Geräten bestand in 101,38 Sekunden: Modell, Review, Routing, Topologie, Parameter, Capacity, Preflight, tatsächliche Simulation, Ergebnisse und Intelligence. Der positive Test vereinbart konkrete Timingbudgets für seine drei Transportquellen; echte Deadlineverletzungen bleiben in separaten Negativtests abgedeckt. Die Wiederholung erzeugt keinen zweiten Simulationsjob. Ein bei der Untersuchung entdecktes Ignorieren der konfigurierten Jitteramplitude wurde im separaten Simulationspaket korrigiert.

Physische Kanalmaterialisierung und Portmigration liegen im separaten Agent-/Portpaket. Globale Workflow-Abdeckung und Snapshot-Sperrprüfung wurden mit dem Hauptauftrag integriert. Deployment und Anwendung auf dem Liveprojekt bleiben beim Hauptauftrag.
