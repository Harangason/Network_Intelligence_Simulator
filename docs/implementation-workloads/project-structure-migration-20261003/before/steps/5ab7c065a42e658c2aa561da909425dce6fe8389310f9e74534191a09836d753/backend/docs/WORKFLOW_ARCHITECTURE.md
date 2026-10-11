# Verbindlicher Network-Intelligence-Workflow

## Reihenfolge

```text
Engineering-Modell
  -> Routing-Tabelle
  -> Netzwerk-Editor
  -> Parameter
  -> Capacity & Timing
  -> Validation / Preflight
  -> Simulation
  -> Results / Analysis
  -> Data Science & Intelligence
```

Die Schritte sind keine kurzlebigen UI-Tabs. Sie teilen `project_id`,
Quellversionen und Status über `engineering_workflow_projects`.

## Status und Invalidierung

Erlaubte Status sind `EMPTY`, `IN_PROGRESS`, `COMPLETE`, `WARNING`, `ERROR`,
`APPROVED` und `OUTDATED`.

Eine Änderung erhöht die Version ihres Schritts. Bereits vorhandene abhängige
Ergebnisse werden nicht gelöscht, sondern mit Grund als `OUTDATED` markiert:

```text
Engineering -> Routing, Network, Capacity, Validation, Simulation, Results, Intelligence
Routing     -> Network, Capacity, Validation, Simulation, Results, Intelligence
Network     -> Capacity, Validation, Simulation, Results, Intelligence
Parameters  -> Capacity, Validation, Simulation, Results, Intelligence
Capacity    -> Validation, Simulation, Results, Intelligence
Validation  -> Simulation, Results, Intelligence
Simulation  -> Results, Intelligence
Results     -> Intelligence
```

Leere, noch nie erzeugte Ergebnisse bleiben `EMPTY`.
Parameter bleiben als explizite Benutzervorgaben bei vorgelagerten Änderungen erhalten.

## Gleichzeitige Browserzugriffe

Mutierende Engineering-Requests einschließlich Invalidierung verwenden eine
gemeinsame Datenbanktransaktion und eine PostgreSQL-Projektsperre. Speichern
vergleicht die geladene Objektversion, Routingrevision beziehungsweise den
Inhaltstoken von Topologie und Parametern. Veraltete Änderungen liefern HTTP
409; der Browser behält den offenen Entwurf. Die Oberfläche prüft alle fünf
Sekunden `/workflow/revision` und bietet einen ausdrücklichen Neuabgleich an.

Die Vergleichsfelder sind für bestehende API-Clients optional. Neue Editoren
müssen `expected_version`, `expected_revision` beziehungsweise `expected_token`
aus ihrem tatsächlich geladenen Ausgangsstand mitsenden.

## Snapshots

`engineering_analysis_snapshots` speichert Capacity- und Preflight-Ergebnisse
mit Eingaben, Findings, Berechnungsmodell, Annahmen, Zeitstempel und
Quellversionen. `engineering_simulation_snapshots` friert die validierte
Konfiguration und berechnete Metriken ein. Laufstatus und Ergebnis werden dort
persistiert, damit ein Prozessneustart die fachliche Evidenz nicht verliert.

Ein Simulationslauf ist im Workflow-Modus nur erlaubt, wenn:

1. ein aktueller Preflight ohne `ERROR` existiert,
2. dessen relevante Quellversionen noch aktuell sind,
3. ein `READY` SimulationSnapshot referenziert wird und atomar reserviert werden kann.

Der Snapshot übernimmt serverseitig das freigegebene Routing und friert das
Engineering-Signalmodell sowie die wirksamen Transportparameter ein. Ein
Workflow-Job verwendet diese Konfiguration auch dann, wenn der Startaufruf
abweichende Daten enthält. Parallele Startaufrufe desselben Snapshots ergeben
genau einen Job. Vollständige Snapshotresultate ergänzen die gekürzte Jobliste
in der Ergebnisansicht.

## Capacity & Timing

Der Dienst verwendet technologiespezifische Schätzer für CAN, CAN FD, LIN,
FlexRay und Ethernet-basierte Kommunikation. Unbekannte Protokolle werden
sichtbar als `GENERIC_ESTIMATE` gekennzeichnet. Ergebnisse enthalten:

- Average, Peak und Burst Load
- Kapazitätsreserve
- Transmission-, Queueing-, Gateway- und End-to-End-Latenz
- Message-, Route-, Network- und Gateway-Aufschlüsselung
- konfigurierbare Schwellen und Findings
- Berechnungsmodell, Version, Eingaben, Annahmen und Zeitstempel

What-if-Szenarien verändern keine Source-of-Truth-Daten.

## API

- `GET /api/engineering/workflow`
- `PATCH /api/engineering/workflow/context`
- `PATCH /api/engineering/workflow/parameters`
- `GET|PUT /api/engineering/workflow/topology`
- `GET /api/engineering/workflow/snapshots`
- `POST /api/engineering/workflow/simulation-snapshots`
- `GET /api/engineering/capacity`
- `POST /api/engineering/capacity/calculate`
- `POST /api/engineering/capacity/scenario`
- `GET /api/engineering/capacity/{networks|messages|routes|gateways}`
- `GET|POST /api/engineering/preflight`

## KI-Governance

Der Agent kann den Workflow, Capacity und Preflight lesen sowie isolierte
What-if-Szenarien rechnen. Änderungen bleiben Vorschläge:

```text
Analyze / Generate Proposal -> Validate -> Human Review -> Approval -> Apply
```

Der Agent besitzt keine autonome Approval-Berechtigung. Kanonische Engineering
Objects bleiben Source of Truth.

Der aktive Chat verwendet den Python EngineeringAgent und projektgebundenes MCP. Externe MCP-Clients starten Simulationen im gleichen zentralen Anwendungs-Executor. Details: [MCP As Built](../../docs/agent_core/14_MCP_IMPLEMENTATION.md).
