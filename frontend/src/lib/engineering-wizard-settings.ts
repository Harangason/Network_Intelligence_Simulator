import { DEFAULT_BUS_PARTICIPANT_LIMITS, normalizeBusLimits } from "./bus-settings.ts";

export type WizardChoiceOption = {
  id: string;
  label: string;
  detail: string;
  value: string;
};

export type WizardChoiceGroup = {
  id: "scope" | "process";
  label: string;
  multi: true;
  options: WizardChoiceOption[];
};

export const WIZARD_SCOPE_GROUP: WizardChoiceGroup = {
  id: "scope",
  label: "Workflowumfang",
  multi: true,
  options: [
    {
      id: "engineering_model",
      label: "1 Engineering-Modell",
      detail: "Hardware-Knoten, Funktionen, Interfaces, Messages, Signals und Relations.",
      value: "Workflow 1 Engineering-Modell: HardwareNodes, Functions, Interfaces, Messages, Signals und Relations anlegen",
    },
    {
      id: "routing",
      label: "2 Routing-Tabelle",
      detail: "Producer, Consumer, Payload, Signal, Gateway, Protokoll und Pfad.",
      value: "Workflow 2 Routing-Tabelle: Kommunikationspfade mit Producer, Consumer, Payload, Signal, Gateway, Protokoll und Pfad erstellen",
    },
    {
      id: "network_editor",
      label: "3 Netzwerk-Editor",
      detail: "Physische Topologie, Ports, Verbindungen, Gateway-Übergänge und Layout.",
      value: "Workflow 3 Netzwerk-Editor: physische Topologie, Ports, Verbindungen und Gateway-Uebergaenge erzeugen",
    },
    {
      id: "parameters",
      label: "4 Parameter",
      detail: "Bitrate, Payload, Zyklus, Latenz, Jitter, Queueing und Safety-Defaults.",
      value: "Workflow 4 Parameter: technologieabhaengige Bitrate, Payload, Zyklus, Latenz, Jitter, Queueing und Safety-Defaults setzen",
    },
    {
      id: "capacity_timing",
      label: "5 Capacity & Timing",
      detail: "Last, Reserve, Gateway-Load, E2E-Latenz, Bottlenecks und Timing prüfen.",
      value: "Workflow 5 Capacity & Timing: Last, Reserve, Gateway-Load, E2E-Latenz, Bottlenecks und Timing berechnen",
    },
    {
      id: "validation",
      label: "6 Validation / Preflight",
      detail: "Konsistenz, fehlende Interfaces, Payloads, Duplikate und Blocker prüfen.",
      value: "Workflow 6 Validation/Preflight: Konsistenz, fehlende Interfaces, Payloads, Duplikate und Blocker pruefen",
    },
    {
      id: "simulation",
      label: "7 Simulation",
      detail: "Simulationssnapshot mit aktuellem Preflight und berechneter Konfiguration anlegen.",
      value: "Workflow 7 Simulation: Simulationssnapshot nach aktuellem erfolgreichem Preflight anlegen",
    },
    {
      id: "results_analysis",
      label: "8 Results / Analysis",
      detail: "Simulationsergebnisse, Artefakte, Nachweise und Ergebnisvergleich auswerten.",
      value: "Workflow 8 Results/Analysis: Simulationsergebnisse, Artefakte, Nachweise und Ergebnisvergleich auswerten",
    },
    {
      id: "data_science_intelligence",
      label: "9 Data Science & Intelligence",
      detail: "Systembewertung, Reifegrad, Issues, Anomalien und Optimierungsvorschläge.",
      value: "Workflow 9 Data Science & Intelligence: Systembewertung, Reifegrad, Issues, Anomalien und Optimierungsvorschlaege erzeugen",
    },
  ],
};

export const WIZARD_PROCESS_GROUP: WizardChoiceGroup = {
  id: "process",
  label: "Arbeitsweise",
  multi: true,
  options: [
    { id: "defaults", label: "Leere Felder füllen", detail: "Technikabhängige Defaults verwenden.", value: "Leere Pflichtfelder mit technologieabhängigen Defaults füllen" },
    { id: "review_gate", label: "Bis Review-Gate arbeiten", detail: "Alle nötigen Proposals erzeugen und validieren.", value: "Selbstständig bis zum Human-Review-Gate arbeiten" },
    { id: "approve_after_allow", label: "Mit Freigabe übernehmen", detail: "Verbindlich: Eine Bestätigung gibt den Vorschlag frei und übernimmt ihn direkt.", value: "Nach einer menschlichen Freigabe valide Vorschläge direkt übernehmen" },
  ],
};

export const REQUIRED_WIZARD_PROCESS_ID = "approve_after_allow";

export type EngineeringWizardSettings = {
  project_name: string;
  model_type: string;
  scope_ids: string[];
  process_ids: string[];
  bus_participant_limits: Record<string, number>;
};

export type WizardQuestionnaireStep = {
  id: "project" | "technologies" | "architecture" | "parameters" | "task" | "equipment";
  label: string;
};

export const DEFAULT_ENGINEERING_WIZARD_SETTINGS: EngineeringWizardSettings = {
  project_name: "",
  model_type: "automotive",
  scope_ids: WIZARD_SCOPE_GROUP.options.map((option) => option.id),
  process_ids: WIZARD_PROCESS_GROUP.options.map((option) => option.id),
  bus_participant_limits: DEFAULT_BUS_PARTICIPANT_LIMITS,
};

function normalizedIds(value: unknown, options: WizardChoiceOption[], fallback: string[]): string[] {
  const allowed = new Set(options.map((option) => option.id));
  const result = Array.isArray(value)
    ? [...new Set(value.map(String).filter((id) => allowed.has(id)))]
    : [];
  return result.length ? result : [...fallback];
}

export function normalizeEngineeringWizardSettings(
  value: unknown,
  fallbackModelType = DEFAULT_ENGINEERING_WIZARD_SETTINGS.model_type,
): EngineeringWizardSettings {
  const source = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const rawModelType = String(source.model_type ?? fallbackModelType).trim();
  const modelType = /^[a-zA-Z0-9_-]{1,64}$/.test(rawModelType)
    ? rawModelType
    : DEFAULT_ENGINEERING_WIZARD_SETTINGS.model_type;
  const processIds = normalizedIds(
    source.process_ids,
    WIZARD_PROCESS_GROUP.options,
    DEFAULT_ENGINEERING_WIZARD_SETTINGS.process_ids,
  );
  if (!processIds.includes(REQUIRED_WIZARD_PROCESS_ID)) {
    processIds.push(REQUIRED_WIZARD_PROCESS_ID);
  }
  return {
    project_name: String(source.project_name ?? "").trim().slice(0, 120),
    model_type: modelType || DEFAULT_ENGINEERING_WIZARD_SETTINGS.model_type,
    scope_ids: normalizedIds(source.scope_ids, WIZARD_SCOPE_GROUP.options, DEFAULT_ENGINEERING_WIZARD_SETTINGS.scope_ids),
    process_ids: processIds,
    bus_participant_limits: normalizeBusLimits(source.bus_participant_limits),
  };
}

export function wizardQuestionnaireSteps(mode: "full" | "can"): WizardQuestionnaireStep[] {
  return [
    { id: "project", label: "Projektname" },
    { id: "technologies", label: "Technologien" },
    { id: "architecture", label: "Netzarchitektur" },
    ...(mode === "can" ? [{ id: "parameters" as const, label: "Parameter" }] : []),
    { id: "task", label: "Aufgabe" },
    { id: "equipment", label: "Geräteumfang" },
  ];
}
