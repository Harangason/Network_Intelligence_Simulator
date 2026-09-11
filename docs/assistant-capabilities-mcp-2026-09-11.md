# Engineering-Assistent und MCP

Nutzerauftrag: KI-Einstiege müssen an die vorhandenen Fachwerkzeuge angeschlossen
sein. Der Assistent kennt Wizards und andere Agenten, bietet ausführbare Kacheln
an und arbeitet im angezeigten Projekt.

## Gemeinsamer Katalog

`backend/engineering/agent_tools/capabilities.py` beschreibt 20 vorhandene Abläufe:
die sechs Objekt-Wizards, Engineering-Wizard, Kommunikationsreparatur, Routing,
Strukturtransfer, Structure Wizard, System-Dubletten, Raumarchitektur, Parameter,
Kapazität, Preflight, Simulation, Fehlerszenarien, Ursachenanalyse und Intelligence.
Jeder Eintrag benennt seine Fachwerkzeuge und Schritte. Fehlende Werkzeuge werden
als nicht verfügbar gemeldet; die Oberfläche prüft die Verfügbarkeit beim Öffnen
erneut. Die Aktionen öffnen bestehende Arbeitsabläufe, keine separaten Attrappen.

MCP-Erweiterungen: `inspect_assistant_capabilities`, `prepare_assistant_action`,
`describe_engineering_concepts`, `inspect_communication_repair`,
`analyze_structure_transfer`, `evaluate_structure_dependencies`,
`inspect_system_duplicates` und `generate_fault_proposals`.
Der Katalog ist auch als projektgebundene MCP-Ressource
`simulator://project/{project_id}/capabilities` verfügbar.

Die Reparaturvorschau verwendet denselben Planer wie der Reparaturdialog: aktuelle
Hardware, etablierte Funktionspartner, alte/neue Signalwege und betroffene Routen.
Übernahme bzw. Wiederherstellung bleibt die ausdrückliche Auswahl im bestehenden
Dialog. Struktur- und Fehlervorschläge verwenden ihre vorhandenen Fachdienste und
Review-Abläufe. Fachliche Berechnungen und bestätigte Lernbeispiele bleiben
getrennt von der freien Formulierung und Werkzeugwahl des Sprachmodells.

## Antworten und Projektbindung

Die beanstandeten Fragen nach Fähigkeiten und Reparatur-Agent werden aus dem
MCP-Katalog beantwortet und starten keinen alten Auftrag. Dafür wird keine
Sprachmodell-Inferenz benötigt. Freie Fragen erhalten den vollständigen Katalog
und die kanonischen Modellbegriffe im Reasoning-Kontext. Allgemeine Begriffsfragen
verwenden das Definitionswerkzeug; konkrete Objektfragen verwenden Suche und
exakte technische Typen/UUIDs. Werkzeugfehler bleiben sichtbar und können keine
erfolgreiche Durchführung begründen.

Widget und Workflow-Header lesen denselben gespeicherten Projektnamen.
Chattransport, Kontext, Kacheln und ausgewählte Objekte werden projektgebunden
geprüft. Ein Wechsel während eines Aufrufs führt zu einem sichtbaren Abbruch bzw.
HTTP 409. Modelltext kann weder eine fremde Projekt-ID noch eine beliebige URL
als ausführbare Aktion festlegen.

Ollama war installiert, aber der Host-Dienst lief nicht. Er wurde im Hintergrund
gestartet; der NIS-Container erreicht wieder die konfigurierten lokalen Modelle.
Der bestehende `start-networkis.ps1` startet diesen Host-Dienst ebenfalls.
Kein API-Schlüssel wurde ersetzt. Verbindungsfehler, Zeitlimits und abgelehnte
Modellanfragen erhalten unterscheidbare Fehlermeldungen.

## Nachweise

Aktiv: Build `f2eaea545df5`. 115 Backend-/MCP-Prüfungen in der separaten
SQL-Testdatenbank bestanden. Die echte freie Modellprobe endet mit `ANSWERED`
und beschreibt Geräte, Aufgaben, Anschlüsse, Nachrichten und Signalwerte korrekt.
Die beiden beanstandeten Produktfragen wurden zusätzlich durch den Browser über
den echten Chat-/MCP-Dienst geprüft.

- `scripts/verify_assistant_sql.py`: Agent-/MCP-Tests in der separaten Datenbank
  `nis_bus_naming_tests`; Protokoll `backend/runtime/assistant-isolated-sql.txt`.
- 28 Frontend-Prüfungen für Antwortvertrag, Verlauf/Navigation, Aufgaben und
  Ausgabesicherheit; TypeScript und Produktionsbuild.
- `frontend/scripts/verify-assistant-capabilities.mjs`: echter Chat/MCP,
  Kacheln, Signal-Wizard, Engineering-Wizard, Reparatur, Strukturtransfer und
  Structure Wizard. Der Name des bestehenden Projekts wird geprüft; seine
  Topologie und Parameter bleiben unverändert. Wizard-Einstellungen im eigenen
  Testprojekt werden separat von Modelländerungen gezählt.
- `scripts/verify_assistant_inference.py`: reale freie Modellantwort über den
  laufenden Chat-/MCP-Dienst in einem eigenen Testprojekt. Kein Inferenz-Dummy.

Die Prüfungen belegen die Integration und die genannten Abläufe. Sie sind kein
pauschaler Qualitätsnachweis für beliebige generierte Architekturen oder eine
vollständige Neugenerierung des Nutzerprojekts.
