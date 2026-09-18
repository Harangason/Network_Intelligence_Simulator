export type WorkflowStatus =
  | "EMPTY"
  | "IN_PROGRESS"
  | "COMPLETE"
  | "WARNING"
  | "ERROR"
  | "APPROVED"
  | "OUTDATED";

export const WORKFLOW_STEP_DEFINITIONS = [
  {
    id: "engineering_model",
    position: 1,
    label: "Engineering-Modell",
    route: "/studio/engineering",
    detail: "Hardware-Knoten, Funktionen, Interfaces, Messages, Signals und Relations.",
    instruction: "Workflow 1 Engineering-Modell: HardwareNodes, Functions, Interfaces, Messages, Signals und Relations anlegen",
  },
  {
    id: "routing",
    position: 2,
    label: "Routing-Tabelle",
    route: "/studio/routing",
    detail: "Producer, Consumer, Payload, Signal, Gateway, Protokoll und Pfad.",
    instruction: "Workflow 2 Routing-Tabelle: Kommunikationspfade mit Producer, Consumer, Payload, Signal, Gateway, Protokoll und Pfad erstellen",
  },
  {
    id: "network_editor",
    position: 3,
    label: "Netzwerk-Editor",
    route: "/studio?mode=network",
    detail: "Physische Topologie, Ports, Verbindungen, Gateway-Übergänge und Layout.",
    instruction: "Workflow 3 Netzwerk-Editor: physische Topologie, Ports, Verbindungen und Gateway-Uebergaenge erzeugen",
  },
  {
    id: "parameters",
    position: 4,
    label: "Parameter",
    route: "/studio?mode=parameters",
    detail: "Bitrate, Payload, Zyklus, Latenz, Jitter, Queueing und Safety-Defaults.",
    instruction: "Workflow 4 Parameter: technologieabhaengige Bitrate, Payload, Zyklus, Latenz, Jitter, Queueing und Safety-Defaults setzen",
  },
  {
    id: "capacity_timing",
    position: 5,
    label: "Capacity & Timing",
    route: "/studio/capacity",
    detail: "Last, Reserve, Gateway-Load, E2E-Latenz, Bottlenecks und Timing prüfen.",
    instruction: "Workflow 5 Capacity & Timing: Last, Reserve, Gateway-Load, E2E-Latenz, Bottlenecks und Timing berechnen",
  },
  {
    id: "validation",
    position: 6,
    label: "Validation / Preflight",
    route: "/studio/validation",
    detail: "Konsistenz, fehlende Interfaces, Payloads, Duplikate und Blocker prüfen.",
    instruction: "Workflow 6 Validation/Preflight: Konsistenz, fehlende Interfaces, Payloads, Duplikate und Blocker pruefen",
  },
  {
    id: "simulation",
    position: 7,
    label: "Simulation",
    route: "/studio/simulation",
    detail: "Simulationssnapshot mit aktuellem Preflight und berechneter Konfiguration anlegen.",
    instruction: "Workflow 7 Simulation: Simulationssnapshot nach aktuellem erfolgreichem Preflight anlegen",
  },
  {
    id: "results_analysis",
    position: 8,
    label: "Results / Analysis",
    route: "/studio/results",
    detail: "Simulationsergebnisse, Artefakte, Nachweise und Ergebnisvergleich auswerten.",
    instruction: "Workflow 8 Results/Analysis: Simulationsergebnisse, Artefakte, Nachweise und Ergebnisvergleich auswerten",
  },
  {
    id: "data_science_intelligence",
    position: 9,
    label: "Data Science & Intelligence",
    route: "/studio/intelligence",
    detail: "Systembewertung, Reifegrad, Issues, Anomalien und Optimierungsvorschläge.",
    instruction: "Workflow 9 Data Science & Intelligence: Systembewertung, Reifegrad, Issues, Anomalien und Optimierungsvorschlaege erzeugen",
  },
] as const;

export type WorkflowStepId = (typeof WORKFLOW_STEP_DEFINITIONS)[number]["id"];

export const WORKFLOW_LINKS = Object.fromEntries(
  WORKFLOW_STEP_DEFINITIONS.map((stage) => [stage.id, stage.route]),
) as Record<WorkflowStepId, string>;
