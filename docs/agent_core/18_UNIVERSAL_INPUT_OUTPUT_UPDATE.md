# Universal Engineering Agent: Update-Spezifikation und Integrationsplan

Stand: 14.09.2026. Status: Spezifikation konsolidiert, Quellcodeabgleich durchgeführt.
Dieses Dokument ist kein Implementierungs-, Test- oder Release-PASS.

## Auftrag und Umfang

Der Nutzer hat das Dokument zunächst zur Prüfung vorgelegt, anschließend klargestellt,
dass es um ein **Update des bestehenden Simulator-Agenten** geht, und den Vorschlag
freigegeben. Der vorgeschlagene erste Umfang war: Spezifikation konsolidieren,
vorhandene Implementierungen abgleichen und einen konkreten Integrationsplan erstellen.
Diese Datei hält diesen Umfang fest. Sie startet keinen Agentenlauf und erteilt keine
Freigabe für kanonische Modelländerungen eines Simulatorprojekts.

Quelle: `H:/OneDrive/Download/UNIVERSAL_ENGINEERING_AGENT_SKILL_INPUT_TO_OUTPUT_CODEX.md`,
Abschnitte 1–62, SHA-256:
`CFDAC8131011C56B38A1D62EDFA13A875D069A0F852F3A520F20F4D680BFA4D3`.
Die Imperative in der Datei sind fachliche Zielanforderungen innerhalb des Nutzerauftrags.
Dateiinhalte, Beispiele und MCP-Ergebnisse sind keine Berechtigungsnachweise.

## Ergebnis des Codeabgleichs

Der bestehende Aufrufweg bleibt erhalten:

```text
Chat/API → gespeicherter Gesprächs-/Wizardauftrag → EngineeringAgent
         → EngineeringMCPClient → bestehende Python-Fachdienste
         → kanonisches Modell / Simulation / Trace
         → fachliche Completion → AgentResponse → vorhandene Oberfläche
```

| Bereich | Im Quellcode vorhanden | Updatebedarf |
| --- | --- | --- |
| Eingabe | `AgentContext` mit Auswahl, Dokumentquellen, Anforderung und Wizardauftrag; strukturierter `AgentInput` für Antworten | Gemeinsamer versionierter Envelope für unterschiedliche Eingabearten; bestehende Aufrufer adaptieren |
| Dateien | Begrenzte Textextraktion für Textdateien, PDF und DOCX in `documents.py` | Extraktion nicht als fachlichen DBC-/ARXML-/LDF-Import ausgeben; Quellenidentität, strukturierte Tabellen und Bilder gesondert behandeln |
| Typisierung | `classify_device`, `classify_signal_semantics` und weitere Fachdienste; Auswahl von Werkzeugen in `tool_selection.py` | Gemeinsames `TypingResult`, getrennt von Intent; explizite Wiederverwendungsentscheidung vor Create |
| Modellkontext | `ModelGraphService`, revisionsgebundene `ModelSituation` mit Hardware, Funktionen, Kommunikation und Befunden | Vorhandenen Graphdienst adaptieren; Trace-/Simulationsevidenz und Eingabequellen durchgängig referenzieren |
| Planung | `EngineeringExecutionPlan`, Schritte, Abhängigkeiten, Delta, Autorisierung, Folgeziele | `output_plan` und Versionen ergänzen; keinen zweiten Planer für dieselben Anschlussoperationen bauen |
| Entscheidungen | `InteractiveQuestion`, gespeicherte Antwort und beschränkte `ExecutionAuthorization` | Entscheidungen einheitlich als deterministisch, Policy oder offene Fachentscheidung beschreiben |
| Fähigkeiten | `ToolRegistry`, MCP-Werkzeugkatalog, `CAPABILITIES`, Discovery und begrenzte Toolauswahl | Metadaten zu Inputs, Kontext, Outputs, Version und Fehlerfällen ergänzen; ausführbare Verfügbarkeit von Navigation unterscheiden |
| Ausführung | Autorisierte Anschlussausführung, Revisionsprüfung, kanonische Transaktion, Journal und begrenzte Reparatur | Auf diese Dienste aufsetzen; weitere Eingaben nicht automatisch zu neuen ausführbaren Goal-Adaptern erklären |
| Completion | `GoalCompletionEvaluator`, explizite Evidenzbedingungen; separate Workload-Validierung | Beauftragte Outputs in den Gesamtabschluss einbeziehen, ohne fehlende technische Nachweise zu überdecken |
| Darstellung | Datenbasierter `AgentResponse`, Ergebnis-/Frage-/Vorschlagskarten, `presentation(goal)` | Typisierte Mehrfachoutputs und kanonisch belegte Visualisierungsdaten; Composer als Adapter |
| Gestaltung | Vorhandene React-Komponenten und Styles | Zugelassene Komponenten und vorhandene Tokens registrieren, kein neues Branding voraussetzen |
| Autorität | `ToolAuthority`; Backend setzt Projekt und Berechtigungen, Clientargumente ersetzen diese nicht | Envelope- und Skillmetadaten dürfen diese Grenze nicht umgehen |

Quellcodeprüfung bedeutet hier Lesen der genannten Implementierungen. Historische
Abnahmeberichte wurden nicht als aktueller Testlauf übernommen. Insbesondere ist
der bestehende ParkAssist-Nachweis kein Nachweis für die neue gesamte Pipeline.

## Verbindliche Integrationsregeln

| Kennung | Quelle | Auswirkung auf das Update |
| --- | --- | --- |
| U1 | Nutzerkorrektur „ist das nicht nur ein update?“ | Bestehenden Agenten und Dienste erweitern; keine konkurrierende Ausführungsarchitektur |
| U2 | [Wizard-Ausführung](../WIZARD_EXECUTION_CONTRACT.md), Auftrag/Steuerung | START, CONTINUE, AMEND, Operation-ID, Besitzer und unveränderliche Auftragsrevision erhalten |
| U3 | Derselbe Vertrag, Entscheidungen/Fachobjekte | Fragen und Optionen speichern; neue Vorschlagsrevision bekommt keine alte Freigabe |
| U4 | [Kommunikationsvertrag](../COMMUNICATION_DESIGN_CONTRACT.md) | Empfängerumfang, Publisher, explizite Encodings und Sendeverhalten bewahren; Kapazität, Schedule und funktionales Timing getrennt |
| U5 | [Raumarchitektur](../SPATIAL_ARCHITECTURE_CONTRACT.md) | Funktion, Einbauort und Anschluss unabhängig halten; unbekannte räumliche Identität offen lassen |
| U6 | [Netzbenennung](../NETWORK_NAMING_CONTRACT.md) | Namen kanonisch speichern und übernehmen; keine neue Namenslogik im Renderer |
| U7 | [Modellbewusste Ausführung](16_MODEL_AWARE_EXECUTION.md) | Vorhandene begrenzte Anschlussautorisierung wiederverwenden; Hardwaregrenzen und Transportgrenzen erhalten |
| U8 | [Release-Gate](../WIZARD_RELEASE_GATE.md) | SQL nur isoliert; Release nur mit vollständigem PASS und exakt zugehörigem Image |
| U9 | Eingabedokument §§24, 53, 56, 59 | Skills orchestrieren; Fachrechnung im Core; Toolerfolg und Darstellung sind keine fachliche Completion |

## Konsolidierte Datenverträge

Die folgenden Felder sind Soll-Ergänzungen, keine Behauptung bereits implementierter
Python-Klassen. Neue öffentliche Felder brauchen synchronisierte Backend-/Frontend-
Schemas und einen kompatiblen Adapter für bestehende Requests und gespeicherte Antworten.

### Eingabe und Typisierung

`AgentInputEnvelope` erhält `schema_version`, `input_id`, `input_type`, `content`,
`project_ref`, `selected_objects`, `active_view`, `files`, `user_intent`, `constraints`,
`source` und `timestamp`. `run_ref`, `operation_ref` und `request_revision` referenzieren
die bestehenden gespeicherten Identitäten; sie eröffnen keine unabhängige Zustandsmaschine.
Mehrteilige Eingaben dürfen z. B. Text und Datei gemeinsam enthalten.

`permissions` wird ausschließlich serverseitig aus der bestehenden Autorität abgeleitet.
Ein mitgeliefertes gleichnamiges Feld erteilt keine Berechtigung. Auch `USER_DECISION`
wird nur über das bestehende Frage-/Antwortkommando wirksam. Ereignisse und
Simulationsergebnisse müssen Projekt, Lauf und Quellenrevision nachweisen.

Für V1 werden TEXT, FILE, MODEL_OBJECT/SELECTION und USER_DECISION über vorhandene
Einstiege adaptiert. STRUCTURED_DATA, TABLE, IMAGE, EVENT, TRACE, SIMULATION_RESULT und
MCP_RESULT erhalten explizite Adapter mit ausgewiesener Verfügbarkeit. Ein Enum-Eintrag
allein bedeutet keine Unterstützung. Nicht unterstützte Eingaben liefern einen
konkreten Befund und führen keine Mutation aus.

`TypingResult` trennt `intent` (z. B. CONNECT_FUNCTIONS) von `engineering_type`
(z. B. Function oder Signal), `semantic_type`, `device_type`, `device_class`,
`data_complexity`, `unit` und `behavior_type`. Hinzu kommen `matched_object_ref`,
`candidate_refs`, `confidence`, `source`, `evidence_refs` und `clarification_required`.
Unbekannte Angaben bleiben leer bzw. offen; das Beispiel CLASS_3 darf keine
ungeprüfte Klassenzuordnung erzwingen.

Auflösungsreihenfolge: exakte kanonische ID/Identität → eindeutige Namen/Aliase im
Projekt → Schema-/Ontologie-/Semantikdienste → optionale Klassifikation/LLM-Vorschläge.
Ähnlichkeit ist ein Kandidatenhinweis, keine automatische Identitätsbestätigung.
Mehrdeutige Treffer dürfen weder ein beliebiges Objekt auswählen noch eine Dublette erzeugen.

### Kontext, Entscheidungen und Planung

`ModelContext` ist eine Projektion des bestehenden `ModelGraphService`/`ModelSituation`,
ergänzt um Quellen, aktuelle Simulations-/Tracereferenzen, offene Datenlücken und
veraltete Nachweise. Keine zweite Kopie des kanonischen Modells als neue Wahrheit anlegen.

`EngineeringReasoningResult` speichert kurze fachliche Beobachtungen, Alternativen,
Annahmen, belegte Entscheidungen und Abschlusskriterien. Es ist ein prüfbares Ergebnis,
kein Protokoll interner Gedanken. Quellenlose Vermutungen bleiben als Annahmen markiert.

DETERMINISTIC und POLICY_DEFINED werden innerhalb der bestehenden Autorisierung
ausgeführt. ENGINEERING_DECISION fragt nur dann neu, wenn die konkrete Entscheidung
nicht bereits durch einen aktuellen bestätigten Plan oder eine anwendbare Policy gedeckt
ist. Neue Hardwarefähigkeit oder Änderungen außerhalb des genehmigten Umfangs sind
keine implizite Folge einer Portentscheidung.

Den vorhandenen `EngineeringExecutionPlan` um `schema_version`, `capability_versions`
und `output_plan` ergänzen. Vorbedingungen, erwartete Ergebnisse und Validierung bleiben
an den vorhandenen Schritten. Revisionskonflikte verwerfen die alte Ausführungsgrundlage.
Wiederholungen verwenden dieselbe Operation-ID; geänderte Eingaben benötigen eine neue
Revision. Simulation bleibt eine kontrollierte Folgeaktion nach dem Modell-Commit.

### Fähigkeiten und Werkzeugergebnisse

Eine Skillbeschreibung ergänzt vorhandene Registry-Einträge um `skill_id`, `version`,
`purpose`, `accepted_inputs`, `required_context`, `required_capabilities`, `outputs`,
`validation` und `failure_modes`. Discovery darf nur tatsächlich registrierte,
verfügbare und autorisierte Werkzeuge als ausführbar ausweisen. Fehlende Capabilities
werden sichtbar; es gibt keine simulierte erfolgreiche Ersatzoperation.

`ToolResult` wird wiederverwendet. Bereits vorhanden sind Status, Daten, Findings,
Warnings, Evidence, betroffene Objekte, nächste Aktionen und Trace-ID. Die Begriffe
`errors`/`next_possible_actions` aus dem Eingangsdokument werden auf `findings` und
`next_actions` abgebildet; keine zweite inkonsistente Ergebnisstruktur einführen.

### Mehrfachoutputs, Visualisierung und Abschluss

`AgentOutputEnvelope` erhält Version, Output-ID/-Typ, Status, Inhalt, Projekt-/Laufbezug,
betroffene Objekte, Evidence, Validierung, Provenance sowie optionale Visualisierungs-,
Aktions- und Dateireferenzen. Die geforderten Typen CALCULATION, VALIDATION und
VISUALIZATION werden ausdrücklich ergänzt. QUESTION/PROPOSAL adaptieren bestehende
Frage-/Freigabeverträge; MODEL_CHANGE verweist auf tatsächlich übernommene Änderungen.

`OutputComposer` erzeugt eine geordnete Sammlung solcher Outputs und adaptiert sie auf
`AgentResponse`. Fachstatus wird aus den gespeicherten Ergebnissen übernommen.
`VisualizationRequest` referenziert kanonische Objekte, Beziehungen, Messwerte und
Quellenrevision. Layoutpositionen sind Darstellungsdaten, keine Hardware-Einbauorte.

V1 stellt die betroffene Verbindung als Netzwerkdiagramm plus Prüftabelle dar.
Weitere Diagrammarten werden einzeln mit ihren Adaptern abgenommen. Die bestehende UI
wird über eine begrenzte Komponenten-/Tokenregistrierung komponiert; sie führt kein
generiertes JavaScript, HTML oder CSS aus. Großgraphen brauchen Ausschnitt/Filter und
sichtbare Umfangsangaben, keine still abgeschnittene angeblich vollständige Architektur.

Der Gesamtauftrag ist erst vollständig, wenn sowohl die fachlichen Bedingungen als
auch die ausdrücklich beauftragten Outputs vorliegen. Dazu den bestehenden Evaluator
um Outputkriterien ergänzen und dieselbe Auswertung im Resume-/Hintergrundpfad verwenden.
Ein Darstellungsfehler nach erfolgreichem Commit wiederholt nur die Ausgabeerzeugung,
nicht die Modellmutation. Veraltete Ergebnisse bleiben nachvollziehbar gekennzeichnet.

## Integrationsplan

| Schritt | Ergebnis und betroffene Bereiche | Voraussetzung / Nachweis |
| --- | --- | --- |
| 1 | Versionierter Input-/Typing-Adapter in `backend/agent_core/api/` und `context/`, angebunden über `backend/engineering/agent_tools/api.py` und `conversation.py` | Bestehende Text-, Dokument-, Auswahl- und Antwortrequests bleiben kompatibel; manipulierte Autorität, falsches Projekt und Mehrdeutigkeit werden geprüft |
| 2 | Bestehende Fachklassifikation, Graphauflösung und Capabilitykatalog um gemeinsame Metadaten ergänzen | Exakter Match wird wiederverwendet; unbekannte Fähigkeiten werden nicht als ausführbar gelistet; keine zweite Fachrechnung |
| 3 | Vorhandenen Plan und persistierten Auftrag um Input-/Outputreferenzen erweitern | Reload, CONTINUE, AMEND, doppelte Operation und veraltete Freigabe bleiben korrekt; kein zusätzlicher Ausführungsbesitzer |
| 4 | Composer und Netzwerk-/Tabellenoutput integrieren: `goal_execution/service.py`, `api/agent_response.py`, Frontendvertrag und `engineering-agent-event.tsx` | Graph und Tabelle stammen aus der ausgeführten Revision; bestehende Karten und Fragen bleiben verwendbar |
| 5 | Completion und Resume auf fehlende Outputs erweitern; Fehlerbehandlung getrennt von erneuter Mutation | Darstellungsausfall nach Commit, Wiederaufnahme und Nullfortschritt testen; fehlendes Timing bleibt offen |
| 6 | Weitere Input-/Visualisierungsadapter anschließend einzeln ergänzen und vollständigen Releasekandidaten prüfen | Reale Adaptertests plus vollständiges isoliertes Release-Gate; ausgeliefertes Image entspricht PASS-Receipt |

Vor Frontendänderungen ist zusätzlich `frontend/AGENTS.md` zu lesen. Der aktuelle
Arbeitsbaum enthält umfangreiche vorbestehende Änderungen; diese dürfen durch das
Update weder zurückgesetzt noch pauschal als eigene Änderungen übernommen werden.

## Abnahmematrix für das Eingangsdokument (§61)

„Basis vorhanden“ bedeutet Quellcodebeleg für Teilfunktionen, keinen neuen Laufzeittest.

| DoD | Befund / noch zu erbringender Nachweis |
| --- | --- |
| 1–3 | Mehrere heutige Eingabewege vorhanden; gemeinsamer Envelope und Typingdurchlauf ergänzen |
| 4–5 | Graph-/Matchbasis vorhanden; Wiederverwendung über die neuen Adapter prüfen |
| 6–7 | Fachplanung vorhanden; einheitliches Reasoning-/Entscheidungsergebnis ergänzen |
| 8 | Strukturierte Fragen vorhanden; Fortsetzung über neue Envelopeadapter testen |
| 9–10 | Plan und Dependencies vorhanden; Erweiterung kompatibel testen |
| 11–13 | Capability-/Toolbasis und ToolResult vorhanden; Registrymetadaten und Mapping ergänzen |
| 14–16 | Validierung, Evaluator und begrenzte Repairbasis vorhanden; Outputkriterien integrieren |
| 17–21 | Allgemeiner Visualisierungsvertrag und Designregistry noch zu integrieren |
| 22–25 | Mehrere Antwortkarten vorhanden; OutputEnvelope und Composer noch zu integrieren |
| 26–27 | Persistenter Gesprächs-/Auftragszustand vorhanden; neue Referenzen und Resume testen |
| 28–30 | Registries und zentrale Fachdienste vorhanden; gemeinsame Skillmetadaten ergänzen |
| 31–33 | Trace-/Audit-/Autoritätsbasis vorhanden; vollständige Input-to-Output-Provenance prüfen |
| 34 | Fachlicher Evaluator vorhanden; Tool-/Render-Erfolg darf auch nach Update nicht reichen |
| 35 | ParkAssist als neuer gesamter Input-to-Output-Abnahmefall ausführen; historischen Test nicht übernehmen |

Pflichtfall: bestehende Funktionen ParkAssist und DriverAssistance anhand ihrer
kanonischen Zuordnungen verbinden; expliziten Funktionsoutput, vorhandene Hardwaregrenzen
und bestätigte funktionale Anforderungen im isolierten Testmodell verwenden. Strategie
regulär auswählen, denselben Auftrag nach Reload fortsetzen, tatsächliche Port-/Netz-/
Routingänderungen nachweisen und anschließend das Diagramm der aktuellen Revision samt
getrennten Kapazitäts-/Schedule-/Timingbefunden darstellen. Wiederholung darf keine
weiteren Ports, Routen oder Jobs erzeugen.

Negativfälle: gleichnamige Objekte, fehlende Hardwarefähigkeit, ausgeschlossene lokale
Signale, explizite Kodierung, veraltete Revision, abgelehnte Entscheidung, Commitfehler,
Outputfehler nach Commit, fehlender Timingnachweis und nicht unterstützte Eingabe.
Ein Graph oder Fortschrittsbild allein erfüllt keinen dieser Fachnachweise.

SQL-Tests ausschließlich über `scripts/run-isolated-tests.py`. Ein Release erfordert
`scripts/run-release-gate.py`; Bereitstellung ausschließlich über die zugehörige
PASS-Receipt gemäß bestehendem Vertrag. Für diese reine Spezifikationsänderung wurden
weder Datenbanktests noch Release-Gate oder Produktdeployment ausgeführt.

## Verwendete Quellcodeanker

- `backend/agent_core/context/agent_context.py`: AgentContext, DocumentSource.
- `backend/agent_core/api/agent_response.py`: AgentInput, AgentResponse, InteractiveQuestion.
- `backend/agent_core/api/tool_contract.py`: ToolResult, Permission, ToolStatus.
- `backend/agent_core/core/engineering_agent.py`: bestehender Agent und MCP-Orchestrierung.
- `backend/agent_core/orchestration/tool_selection.py`: begrenzte Toolauswahl.
- `backend/agent_core/registry/tool_registry.py`: bestehende Toolregistry.
- `backend/engineering/agent_tools/api.py`: chat, serverseitiger Projekt-/Berechtigungskontext.
- `backend/engineering/agent_tools/documents.py`: begrenzte Dokumentextraktion.
- `backend/engineering/agent_tools/capabilities.py`: Capabilitykatalog und Verfügbarkeitsprüfung.
- `backend/engineering/agent_tools/runtime.py`: ToolAuthority und transaktionale Ausführung.
- `backend/engineering/goal_execution/models.py`: Modell-, Plan-, Autorisierungs- und Completionverträge.
- `backend/engineering/goal_execution/graph.py`: kanonischer ModelGraphService und Revision.
- `backend/engineering/goal_execution/executor.py`: Ausführung, Repair und Completion.
- `backend/engineering/goal_execution/service.py`: Entscheidungen, Resume und presentation.
- `frontend/src/components/engineering-agent-event.tsx`: vorhandene Daten-/Frage-/Vorschlagsdarstellung.

Die Aussagen zu ergänzenden Adaptern sind Anforderungen an das Update. Nicht jeder
vorhandene Fachbereich wurde vollständig auditiert; nicht gefundene gemeinsame
Verträge bedeuten nicht, dass sämtliche zugehörigen Einzelfunktionen fehlen.
