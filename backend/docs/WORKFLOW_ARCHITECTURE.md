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
```

Die Schritte sind keine kurzlebigen UI-Tabs. Sie teilen `project_id`,
Quellversionen und Status über `engineering_workflow_projects`.

## Status und Invalidierung

Erlaubte Status sind `EMPTY`, `IN_PROGRESS`, `COMPLETE`, `WARNING`, `ERROR`,
`APPROVED` und `OUTDATED`.

Eine Änderung erhöht die Version ihres Schritts. Bereits vorhandene abhängige
Ergebnisse werden nicht gelöscht, sondern mit Grund als `OUTDATED` markiert:

```text
Engineering -> Routing, Network, Parameters, Capacity, Validation, Simulation, Results
Routing     -> Network, Parameters, Capacity, Validation, Simulation, Results
Network     -> Parameters, Capacity, Validation, Simulation, Results
Parameters  -> Capacity, Validation, Simulation, Results
Capacity    -> Validation, Simulation, Results
Validation  -> Simulation, Results
```

Leere, noch nie erzeugte Ergebnisse bleiben `EMPTY`.

## Snapshots

`engineering_analysis_snapshots` speichert Capacity- und Preflight-Ergebnisse
mit Eingaben, Findings, Berechnungsmodell, Annahmen, Zeitstempel und
Quellversionen. `engineering_simulation_snapshots` friert die validierte
Konfiguration und berechnete Metriken ein. Laufstatus und Ergebnis werden dort
persistiert, damit ein Prozessneustart die fachliche Evidenz nicht verliert.

Ein Simulationslauf ist im Workflow-Modus nur erlaubt, wenn:

1. ein aktueller Preflight ohne `ERROR` existiert,
2. dessen relevante Quellversionen noch aktuell sind,
3. ein `READY` SimulationSnapshot referenziert wird.

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
Analyze / Generate Proposal -> Validate -> Human Review -> Approval
```

Der Agent besitzt keine autonome Approval-Berechtigung. Kanonische Engineering
Objects bleiben Source of Truth.
