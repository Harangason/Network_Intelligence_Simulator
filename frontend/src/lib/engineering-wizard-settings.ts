import { DEFAULT_BUS_PARTICIPANT_LIMITS, normalizeBusLimits } from "./bus-settings.ts";
import { WORKFLOW_STEP_DEFINITIONS } from "../features/workflow/definition.ts";
import type { TechnologyDomain } from "./types.ts";

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
  options: WORKFLOW_STEP_DEFINITIONS.map((stage) => ({
    id: stage.id,
    label: `${stage.position} ${stage.label}`,
    detail: stage.detail,
    value: stage.instruction,
  })),
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

const PREFERRED_TECHNOLOGIES_BY_DOMAIN: Record<string, string[]> = {
  automotive: ["can_fd", "automotive_ethernet", "lin", "someip"],
  industrial_automation: ["profinet", "ethercat", "modbus_tcp", "opc_ua", "io_link"],
  industrial: ["profinet", "ethercat", "modbus_tcp", "opc_ua", "io_link"],
  aerospace: ["arinc429", "mil_std_1553", "afdx"],
  iot: ["mqtt", "lorawan", "ble"],
  telecom: ["ethernet", "5g_nr"],
  energy: ["iec61850", "dnp3"],
  robotics: ["ethercat", "ros2_dds"],
  medical: ["hl7", "ble"],
};

export function defaultWizardTechnologyIds(domain?: TechnologyDomain): string[] {
  if (!domain || ["custom", "generic", "generic_networking"].includes(domain.id)) return [];
  const ids = domain.technologies
    .filter((technology) => !["PLANNED", "NOT_SUPPORTED"].includes(technology.implementation_status ?? "IMPLEMENTED"))
    .map((technology) => technology.id);
  const preferred = (PREFERRED_TECHNOLOGIES_BY_DOMAIN[domain.id] ?? []).filter((id) => ids.includes(id));
  return preferred.length ? preferred : ids.slice(0, 4);
}

export type EngineeringWizardSettings = {
  project_name: string;
  model_type: string;
  scope_ids: string[];
  process_ids: string[];
  bus_participant_limits: Record<string, number>;
};

export type WizardQuestionnaireStep = {
  id: "project" | "technologies" | "architecture" | "parameters" | "equipment";
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
    { id: "equipment", label: "Geräteumfang" },
  ];
}
