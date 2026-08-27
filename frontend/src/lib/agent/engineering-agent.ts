import "server-only";

import { createOpenAI } from "@ai-sdk/openai";
import { ToolLoopAgent, InferAgentUIMessage, isStepCount, tool } from "ai";
import { z } from "zod";
import {
  currentAgentProjectId,
  currentAgentRequestText,
  setCurrentAgentRequestText,
} from "@/lib/agent/request-context";
import {
  extractEngineeringSpecification,
  isStructuredEngineeringSpecification,
} from "@/lib/agent/engineering-specification";
import {
  createProposal,
  deleteRoutingProposal,
  findRoutingPaths,
  generateRoutingProposal,
  getObject,
  getRoutingEntry,
  getRoutingEvidence,
  getRoutingPath,
  getRoutingSchema,
  listRoutingEntries,
  listRoutingProposals,
  listObjects,
  listRelations,
  updateRoutingProposal,
  validateRoutingEntry,
  validateRoutingTable,
  inspectWorkflowState,
  inspectCapacityAnalysis,
  calculateCapacityAnalysis,
  inspectPreflightAnalysis,
  runPreflightAnalysis,
  createWorkflowSimulationSnapshot,
  calculateCapacityScenario,
  optimizeCapacityAnalysis,
  searchEngineeringKnowledge,
  inspectIntelligenceAssessment,
  createIntelligenceProposal,
  approveAllValidEngineeringProposals,
  approveEngineeringProposal,
  listEngineeringProposals,
  validateEngineeringProposal,
} from "@/lib/engineering-server-client";

const RESOURCE_ENUM = ["hardware-nodes", "functions", "interfaces", "messages", "signals"] as const;
const OBJECT_TYPE_ENUM = ["HardwareNode", "Function", "Interface", "Message", "Signal"] as const;
type EngineeringResourceName = typeof RESOURCE_ENUM[number];

const OBJECT_TYPE_RESOURCE: Record<typeof OBJECT_TYPE_ENUM[number], EngineeringResourceName> = {
  HardwareNode: "hardware-nodes",
  Function: "functions",
  Interface: "interfaces",
  Message: "messages",
  Signal: "signals",
};

const WORKFLOW_MANIFEST = [
  {
    id: "engineering_model",
    label: "Engineering-Modell",
    goal: "Kanonische HardwareNodes, Functions, Interfaces, Messages, Signals und Relations aufbauen.",
    creates: ["HardwareNode", "Function", "Interface", "Message", "Signal", "Relation"],
    requires: [],
    relationshipRules: [
      "HardwareNode ist Elternobjekt fuer Functions und Interfaces.",
      "Function gehoert zu genau einem HardwareNode.",
      "Interface gehoert zu einem HardwareNode und optional zu einer Function.",
      "Message gehoert zu einem Interface.",
      "Signal gehoert zu einer Message.",
      "Relations verbinden fachliche Graphkanten wie HAS_FUNCTION, HAS_INTERFACE, CONTAINS_SIGNAL und CONNECTED_TO.",
    ],
    tools: ["listEngineeringObjects", "createEngineeringModelFromSpecification", "createEngineeringChain", "createRoutableEngineeringPair", "proposeEngineeringObject", "listEngineeringRelations", "proposeEngineeringRelation", "inspectEngineeringProposals", "validateEngineeringProposal", "approveEngineeringProposal", "approveAllValidEngineeringProposals"],
    doneWhen: "Alle fuer das Ziel benoetigten Objekte existieren im kanonischen Modell und ihre AIProposals bilden die Auditspur.",
  },
  {
    id: "routing",
    label: "Routing-Tabelle",
    goal: "Kommunikationspfade von Producer zu Consumer mit Message, Signal, Interfaces, Protokoll und Gateway modellieren.",
    creates: ["RoutingProposal", "RoutingEntry"],
    requires: ["engineering_model"],
    relationshipRules: [
      "Routing nutzt HardwareNodes als Producer und Consumer.",
      "Routing referenziert vorhandene Interfaces, Messages und Signals.",
      "Gateways vermitteln zwischen Netzen oder Technologien.",
      "Eine Route ist erst belastbar, wenn Pfad, Quelle, Ziel, Payload und Protokoll validiert sind.",
    ],
    tools: ["inspect_routing_table", "create_route_proposal", "inspect_routing_proposals", "validate_routing_table", "find_paths", "inspect_topology"],
    doneWhen: "Routen sind erzeugt, validiert und fuer fehlende Freigaben klar am Review-Gate benannt.",
  },
  {
    id: "network_editor",
    label: "Netzwerk-Editor",
    goal: "Physische Topologie aus Nodes, Ports, Interfaces, Gateways und Routingpfaden herstellen.",
    creates: ["TopologyNode", "TopologyEdge", "CONNECTED_TO"],
    requires: ["engineering_model", "routing"],
    relationshipRules: [
      "Topologie bildet die physische Sicht der Routingpfade ab.",
      "Edges verbinden Ports oder HardwareNodes ohne Boxen zu kreuzen.",
      "Sensoren stehen vor verarbeitenden ECUs, Gateways vermitteln, Aktoren/Consumer stehen nachgelagert.",
    ],
    tools: ["inspect_topology", "inspect_network", "find_paths", "validate_routing_table"],
    doneWhen: "Routing und Netzwerk sind synchron und der Workflow meldet keine offene Topologie-Luecke.",
  },
  {
    id: "parameters",
    label: "Parameter",
    goal: "Technologieabhaengige Timing-, Payload-, Bitrate-, Queueing- und Zuverlaessigkeitsparameter setzen.",
    creates: ["WorkflowParameters"],
    requires: ["engineering_model", "routing", "network_editor"],
    relationshipRules: [
      "Parameter haengen an Netzwerk- und Routentechnologien.",
      "Leere Felder werden mit plausiblen technologieabhaengigen Defaults gefuellt, sofern der Nutzer nichts anderes vorgibt.",
    ],
    tools: ["inspect_protocol", "inspect_network", "inspect_workflow"],
    doneWhen: "Parameter sind ausreichend fuer Capacity-Berechnung und Preflight.",
  },
  {
    id: "capacity_timing",
    label: "Capacity & Timing",
    goal: "Persistente Last-, Reserve-, Latenz-, Queueing-, Gateway-, Jitter- und Synchronisationsanalyse berechnen.",
    creates: ["CapacitySnapshot"],
    requires: ["engineering_model", "routing", "network_editor", "parameters"],
    relationshipRules: [
      "Capacity basiert auf aktuellen Workflow-Versionen.",
      "Szenarien sind nur Vergleich; fuer Workflow-Fortschritt muss persistent berechnet werden.",
    ],
    tools: ["calculate_capacity_timing", "inspect_capacity_timing", "identify_bottleneck"],
    doneWhen: "Ein aktueller Capacity-&-Timing-Snapshot existiert.",
  },
  {
    id: "validation",
    label: "Validation / Preflight",
    goal: "Technische Konsistenz vor der Simulation pruefen und blockierende Befunde sichtbar machen.",
    creates: ["PreflightSnapshot"],
    requires: ["engineering_model", "routing", "network_editor", "parameters", "capacity_timing"],
    relationshipRules: [
      "ERROR blockiert Simulation.",
      "WARNING bleibt sichtbar, ist aber zulaessig, sofern keine blockierenden Fehler vorliegen.",
    ],
    tools: ["run_preflight", "inspect_preflight"],
    doneWhen: "Preflight ist aktuell und ready_for_simulation ist true oder Befunde sind klar benannt.",
  },
  {
    id: "simulation",
    label: "Simulation",
    goal: "Simulation aus aktuellem erfolgreichem Preflight und aktueller Capacity-Konfiguration anlegen.",
    creates: ["SimulationSnapshot"],
    requires: ["engineering_model", "routing", "network_editor", "parameters", "capacity_timing", "validation"],
    relationshipRules: [
      "Simulation darf nur nach aktuellem erfolgreichem Preflight gestartet werden.",
      "Wenn Preflight blockiert, stoppt der Agent mit konkreten Reparaturschritten.",
    ],
    tools: ["create_simulation_snapshot", "inspect_workflow"],
    doneWhen: "Ein SimulationSnapshot wurde erzeugt oder ein Preflight-Blocker verhindert den Start.",
  },
  {
    id: "results_analysis",
    label: "Results / Analysis",
    goal: "Vorhandene Simulationsergebnisse und Workflow-Snapshots nachvollziehbar auswerten.",
    creates: ["AnalysisSummary"],
    requires: ["simulation"],
    relationshipRules: [
      "Results duerfen nur als aktuell gelten, wenn ihre Quellversionen zum aktuellen Workflow passen.",
      "Fehlende oder veraltete Simulationen muessen klar als Blocker benannt werden.",
    ],
    tools: ["inspect_workflow", "inspect_capacity_timing", "inspect_preflight"],
    doneWhen: "Aktuelle Simulationsergebnisse sind vorhanden oder der fehlende Simulationsstand ist klar benannt.",
  },
  {
    id: "data_science_intelligence",
    label: "Data Science & Intelligence",
    goal: "Deterministische Systembewertung, Reifegrad, Issues, Anomalien und Empfehlungen erzeugen oder auswerten.",
    creates: ["IntelligenceAssessment", "OptimizationProposal"],
    requires: ["results_analysis"],
    relationshipRules: [
      "Intelligence bewertet den Gesamtzustand anhand von Workflow-, Graph-, RAG- und Analyse-Evidence.",
      "Optimierungsvorschlaege bleiben getrennt und benoetigen Human Review.",
    ],
    tools: ["inspect_intelligence", "create_optimization_proposal", "inspect_workflow"],
    doneWhen: "Eine aktuelle Bewertung liegt vor oder fehlende Voraussetzungen sind benannt.",
  },
] as const;

const WORKFLOW_TARGET_ALIASES: Record<string, string> = {
  modell: "engineering_model",
  engineering: "engineering_model",
  routing: "routing",
  route: "routing",
  netzwerk: "network_editor",
  "netzwerk-editor": "network_editor",
  parameter: "parameters",
  capacity: "capacity_timing",
  timing: "capacity_timing",
  preflight: "validation",
  validation: "validation",
  validierung: "validation",
  simulation: "simulation",
  simulieren: "simulation",
  analyse: "results_analysis",
  results: "results_analysis",
  ende: "data_science_intelligence",
  endzustand: "data_science_intelligence",
  komplett: "data_science_intelligence",
  vollständig: "data_science_intelligence",
  vollstaendig: "data_science_intelligence",
  alles: "data_science_intelligence",
  fertig: "data_science_intelligence",
  intelligence: "data_science_intelligence",
};

const WORKFLOW_STEP_ORDER = [
  "engineering_model",
  "routing",
  "network_editor",
  "parameters",
  "capacity_timing",
  "validation",
  "simulation",
  "results_analysis",
  "data_science_intelligence",
];

function workflowStepIdsUntil(targetId: string) {
  const targetIndex = WORKFLOW_STEP_ORDER.indexOf(targetId);
  return WORKFLOW_STEP_ORDER.slice(0, targetIndex >= 0 ? targetIndex + 1 : 1);
}

function concreteRequestText(request: string) {
  const marker = "konkrete aufgabe des nutzers";
  const normalized = request.toLowerCase();
  const markerIndex = normalized.indexOf(marker);
  if (markerIndex < 0) return normalized;
  const separatorIndex = normalized.indexOf(":", markerIndex + marker.length);
  const startIndex = separatorIndex >= 0 ? separatorIndex + 1 : markerIndex + marker.length;
  const trailingInstructionIndex = normalized.indexOf("\n\nstarte jetzt", startIndex);
  return normalized.slice(startIndex, trailingInstructionIndex >= 0 ? trailingInstructionIndex : undefined);
}

function inferWorkflowTarget(request: string) {
  const normalized = concreteRequestText(request);
  const matches = Object.entries(WORKFLOW_TARGET_ALIASES)
    .filter(([alias]) => {
      const escapedAlias = alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return new RegExp(`(^|[^a-z0-9äöüß])${escapedAlias}([^a-z0-9äöüß]|$)`, "i").test(normalized);
    })
    .map(([, stepId]) => stepId)
    .sort((left, right) => WORKFLOW_STEP_ORDER.indexOf(right) - WORKFLOW_STEP_ORDER.indexOf(left));
  return matches[0] ?? "engineering_model";
}

function usableApiKey(value: string | undefined): value is string {
  return Boolean(value && !/^(DEIN|YOUR|PLACEHOLDER|CHANGEME)/i.test(value.trim()));
}

const openAIKey = process.env.OPENAI_API_KEY;
const nvidiaKey = process.env.NVIDIA_API_KEY;
const requestedProvider = (process.env.AI_PROVIDER ?? "hybrid-demand").trim().toLowerCase();
const localAIBaseURL = (process.env.LOCAL_AI_BASE_URL ?? "http://127.0.0.1:11434/v1").replace(/\/$/, "");
const localAIModel = process.env.LOCAL_AI_MODEL ?? "qwen3.8:27b";
const cloudEscalationPolicy = (process.env.CLOUD_ESCALATION ?? "on_failure").trim().toLowerCase();
const EXPLICIT_OPENAI_PATTERN = /(?:nutze|verwende|mit|ueber|über)\s+(?:openai|gpt(?:-?5)?|cloud)\b/i;
const EXPLICIT_NVIDIA_PATTERN = /(?:nutze|verwende|mit|ueber|über)\s+(?:nvidia|nemotron|nim)\b/i;

function selectEngineeringModels() {
  const local = () => ({
    provider: "ollama" as const,
    label: localAIModel,
    model: createOpenAI({
      apiKey: process.env.LOCAL_AI_API_KEY ?? "ollama",
      baseURL: localAIBaseURL,
      name: "ollama",
    }).chat(localAIModel),
  });
  const openai = () => ({
    provider: "openai" as const,
    label: process.env.OPENAI_AI_MODEL ?? "gpt-5-mini",
    model: createOpenAI({ apiKey: openAIKey })(process.env.OPENAI_AI_MODEL ?? "gpt-5-mini"),
  });
  const nvidia = () => ({
    provider: "nvidia-nim" as const,
    label: process.env.NVIDIA_AI_MODEL ?? "nvidia/nemotron-3-nano-30b-a3b",
    model: createOpenAI({
      apiKey: nvidiaKey,
      baseURL: "https://integrate.api.nvidia.com/v1",
      name: "nvidia-nim",
    }).chat(process.env.NVIDIA_AI_MODEL ?? "nvidia/nemotron-3-nano-30b-a3b"),
  });
  const onDemandOpenAI = usableApiKey(openAIKey) ? openai() : null;
  const onDemandNvidia = usableApiKey(nvidiaKey) ? nvidia() : null;
  const selection = (
    primary: ReturnType<typeof local> | ReturnType<typeof openai> | ReturnType<typeof nvidia>,
    orchestrator: ReturnType<typeof local> | ReturnType<typeof openai> | ReturnType<typeof nvidia>,
    provider: string,
  ) => ({ primary, orchestrator, provider, onDemandOpenAI, onDemandNvidia });

  if (requestedProvider === "local" || requestedProvider === "ollama") {
    const localSelection = local();
    return selection(localSelection, localSelection, "ollama");
  }
  if (requestedProvider === "openai" && usableApiKey(openAIKey)) {
    const openAISelection = openai();
    return selection(openAISelection, openAISelection, "openai");
  }
  if ((requestedProvider === "nvidia" || requestedProvider === "nvidia-nim") && usableApiKey(nvidiaKey)) {
    const nvidiaSelection = nvidia();
    return selection(nvidiaSelection, nvidiaSelection, "nvidia-nim");
  }
  if (requestedProvider === "hybrid-demand") {
    const localSelection = local();
    return selection(localSelection, localSelection, "hybrid-demand");
  }
  if (requestedProvider === "hybrid") {
    const primary = local();
    const orchestrator = usableApiKey(openAIKey)
      ? openai()
      : usableApiKey(nvidiaKey)
        ? nvidia()
        : primary;
    return selection(primary, orchestrator, `hybrid-${orchestrator.provider}`);
  }
  if (requestedProvider === "auto") {
    const automaticSelection = usableApiKey(openAIKey) ? openai() : usableApiKey(nvidiaKey) ? nvidia() : local();
    return selection(automaticSelection, automaticSelection, automaticSelection.provider);
  }

  const unconfigured = {
    provider: "unconfigured" as const,
    label: "gpt-5-mini",
    model: createOpenAI({ apiKey: "unconfigured" })("gpt-5-mini"),
  };
  return { primary: unconfigured, orchestrator: unconfigured, provider: "unconfigured", onDemandOpenAI, onDemandNvidia };
}

const engineeringModelSelection = selectEngineeringModels();
const engineeringModel = engineeringModelSelection.primary.model;
const engineeringOrchestrationModel = engineeringModelSelection.orchestrator.model;
const engineeringOnDemandOpenAIModel = engineeringModelSelection.onDemandOpenAI?.model ?? null;
const engineeringOnDemandNvidiaModel = engineeringModelSelection.onDemandNvidia?.model ?? null;

export const engineeringAgentProvider = engineeringModelSelection.provider;
export const engineeringAgentModel = engineeringModelSelection.primary.label;
export const engineeringAgentOrchestrator =
  requestedProvider === "hybrid-demand"
    ? `local-first;openai=${engineeringModelSelection.onDemandOpenAI?.label ?? "off"};nvidia=${engineeringModelSelection.onDemandNvidia?.label ?? "off"}`
    : `${engineeringModelSelection.orchestrator.provider}/${engineeringModelSelection.orchestrator.label}`;

function demandModelForRequest(request: string, recovery: boolean, actionable: boolean) {
  if (requestedProvider !== "hybrid-demand") {
    return {
      model: actionable ? engineeringOrchestrationModel : engineeringModel,
      source: actionable ? engineeringModelSelection.orchestrator.provider : engineeringModelSelection.primary.provider,
    };
  }
  if (EXPLICIT_NVIDIA_PATTERN.test(request) && engineeringOnDemandNvidiaModel) {
    return { model: engineeringOnDemandNvidiaModel, source: "nvidia-on-demand" };
  }
  if (EXPLICIT_OPENAI_PATTERN.test(request) && engineeringOnDemandOpenAIModel) {
    return { model: engineeringOnDemandOpenAIModel, source: "openai-on-demand" };
  }
  if (recovery && cloudEscalationPolicy === "on_failure") {
    if (engineeringOnDemandOpenAIModel) return { model: engineeringOnDemandOpenAIModel, source: "openai-recovery" };
    if (engineeringOnDemandNvidiaModel) return { model: engineeringOnDemandNvidiaModel, source: "nvidia-recovery" };
  }
  return { model: engineeringModel, source: "local" };
}

function auditAgent(message: string, details: Record<string, unknown> = {}) {
  const suffix = Object.entries(details)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" ");
  console.info(`[NetworkIS Agent] ${message}${suffix ? ` ${suffix}` : ""}`);
}

const proposalQueues = new Map<string, Promise<void>>();

async function serializeProposalCreation<T>(work: () => Promise<T>): Promise<T> {
  const projectId = currentAgentProjectId();
  const previous = proposalQueues.get(projectId) ?? Promise.resolve();
  const result = previous.then(work, work);
  const settled = result.then(() => undefined, () => undefined);
  proposalQueues.set(projectId, settled);
  void settled.finally(() => {
    if (proposalQueues.get(projectId) === settled) proposalQueues.delete(projectId);
  });
  return result;
}

function usableReference(value: string | undefined) {
  const normalized = value?.trim();
  if (!normalized || /^(none|null|undefined)$/i.test(normalized)) return undefined;
  return normalized;
}

async function resolveObjectReference(value: string | undefined, resource: typeof RESOURCE_ENUM[number]) {
  const normalized = usableReference(value);
  if (!normalized) return undefined;
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(normalized)) {
    return normalized;
  }

  const canonical = await listObjects(resource);
  const canonicalMatch = canonical.items.find(
    (item) => String(item.name ?? "").localeCompare(normalized, undefined, { sensitivity: "accent" }) === 0,
  );
  if (canonicalMatch?.id) return String(canonicalMatch.id);

  const proposals = await listEngineeringProposals();
  const proposalMatch = proposals.items.find((proposal) => {
    if (["REJECTED", "SUPERSEDED"].includes(String(proposal.status ?? ""))) return false;
    const target = proposal.target_object as Record<string, unknown> | undefined;
    if (target?.resource !== resource) return false;
    const items = Array.isArray(proposal.proposed_objects) ? proposal.proposed_objects : [];
    return items.some((item) => {
      if (!item || typeof item !== "object") return false;
      return String((item as Record<string, unknown>).name ?? "").localeCompare(
        normalized,
        undefined,
        { sensitivity: "accent" },
      ) === 0;
    });
  });
  return proposalMatch?.proposal_id ? String(proposalMatch.proposal_id) : normalized;
}

async function resolveCanonicalObjectReference(
  value: string | undefined,
  resource: typeof RESOURCE_ENUM[number],
) {
  const normalized = usableReference(value);
  if (!normalized) return undefined;
  const canonical = await listObjects(resource);
  const match = canonical.items.find((item) => (
    String(item.id ?? "") === normalized
    || String(item.name ?? "").localeCompare(normalized, undefined, { sensitivity: "accent" }) === 0
  ));
  return match?.id ? String(match.id) : undefined;
}

type EngineeringObjectInput = {
  resource: EngineeringResourceName;
  name: string;
  description?: string;
  domain?: string;
  device_type?: string;
  interface_type?: string;
  hardware_node_id?: string;
  function_id?: string;
  interface_id?: string;
  message_id?: string;
  direction?: "rx" | "tx" | "bidirectional";
  message_id_hex?: string;
  cycle_ms?: number;
  dlc?: number;
  display_name?: string;
  start_bit?: number;
  length_bits?: number;
  byte_order?: "little_endian" | "big_endian";
  data_type?: string;
  factor?: number;
  offset_value?: number;
  unit?: string;
  min_value?: number;
  max_value?: number;
};

type CanonicalEngineeringObject = {
  resource: EngineeringResourceName;
  id: string;
  name: string;
};

function sameEngineeringName(value: unknown, expected: string) {
  return String(value ?? "").localeCompare(expected, undefined, { sensitivity: "accent" }) === 0;
}

const CANONICAL_DEVICE_TYPES = new Set([
  "ECU", "PLC", "RobotController", "SensorController", "ActuatorController", "Gateway",
  "EmbeddedController", "IndustrialPC", "FlightComputer", "BatteryManagementSystem",
  "EnergyController", "BuildingController", "GenericDevice", "CustomDevice",
]);

const CANONICAL_INTERFACE_TYPES = new Set([
  "CAN", "CAN_FD", "LIN", "FlexRay", "Ethernet", "EtherCAT", "ProfiNET", "ModbusTCP",
  "ModbusRTU", "RS232", "RS485", "SPI", "I2C", "USB", "MQTT", "OPCUA", "Other",
]);

function canonicalDeviceType(value: string | undefined) {
  const candidate = value?.trim() || "ECU";
  if (CANONICAL_DEVICE_TYPES.has(candidate)) return candidate;
  const normalized = candidate.toLowerCase().replace(/[^a-z0-9]+/g, "");
  if (normalized.includes("gateway")) return "Gateway";
  if (normalized.includes("sensor")) return "SensorController";
  if (normalized.includes("actuator")) return "ActuatorController";
  if (normalized.includes("plc")) return "PLC";
  if (normalized.includes("robot")) return "RobotController";
  if (normalized.includes("ecu") || normalized.includes("electroniccontrolunit")) return "ECU";
  return "GenericDevice";
}

function canonicalInterfaceType(value: string | undefined) {
  const candidate = value?.trim() || "CAN";
  if (CANONICAL_INTERFACE_TYPES.has(candidate)) return candidate;
  const normalized = candidate.toLowerCase().replace(/[^a-z0-9]+/g, "");
  if (normalized.includes("canfd") || normalized.includes("canxl")) return "CAN_FD";
  if (normalized === "can" || normalized.includes("controllerareanetwork")) return "CAN";
  if (normalized.includes("automotiveethernet") || normalized === "ethernet") return "Ethernet";
  if (normalized.includes("ethercat")) return "EtherCAT";
  if (normalized.includes("profinet")) return "ProfiNET";
  if (normalized.includes("modbustcp")) return "ModbusTCP";
  if (normalized.includes("modbusrtu")) return "ModbusRTU";
  if (normalized.includes("flexray")) return "FlexRay";
  if (normalized === "lin") return "LIN";
  if (normalized.includes("opcua")) return "OPCUA";
  if (normalized.includes("mqtt")) return "MQTT";
  return "Other";
}

function canonicalObjectsFromProposal(
  proposal: Record<string, unknown>,
  resource: EngineeringResourceName,
): CanonicalEngineeringObject[] {
  const proposedObjects = Array.isArray(proposal.proposed_objects) ? proposal.proposed_objects : [];
  return proposedObjects.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const candidate = item as Record<string, unknown>;
    const id = String(candidate.canonical_id ?? "");
    if (!id) return [];
    return [{ resource, id, name: String(candidate.name ?? candidate.relation_type ?? "Engineering-Objekt") }];
  });
}

async function findCanonicalEngineeringObject(resource: EngineeringResourceName, name: string) {
  const canonical = await listObjects(resource);
  return canonical.items.find((item) => sameEngineeringName(item.name, name));
}

async function createAndApproveEngineeringObject(input: EngineeringObjectInput) {
  const { resource, ...rest } = input;
  const existingCanonical = await findCanonicalEngineeringObject(resource, rest.name);
  if (existingCanonical?.id) {
    return {
      created: false,
      reused: true,
      resource,
      proposal: null,
      canonical_objects: [{ resource, id: String(existingCanonical.id), name: rest.name }],
      note: "Das gleichnamige Objekt war bereits im kanonischen Modell registriert.",
    };
  }

  const proposals = await listEngineeringProposals();
  const existingProposal = proposals.items.find((proposal) => {
    if (["APPROVED", "REJECTED", "SUPERSEDED"].includes(String(proposal.status ?? ""))) return false;
    const target = proposal.target_object as Record<string, unknown> | undefined;
    if (target?.resource !== resource) return false;
    const proposedObjects = Array.isArray(proposal.proposed_objects) ? proposal.proposed_objects : [];
    return proposedObjects.some((item) => item && typeof item === "object" && sameEngineeringName(
      (item as Record<string, unknown>).name,
      rest.name,
    ));
  });

  let proposal = existingProposal;
  if (!proposal) {
    const payload: Record<string, unknown> = {
      name: rest.name,
      description: rest.description ?? null,
      domain: rest.domain ?? null,
      source: "ai_generated",
      review_state: "unreviewed",
      approval_state: "pending",
      provenance: { agent: "engineering-chat-agent", reason: "user-requested object" },
    };
    if (resource === "hardware-nodes") payload.device_type = canonicalDeviceType(rest.device_type);
    if (resource === "functions") {
      payload.hardware_node_id = await resolveObjectReference(rest.hardware_node_id, "hardware-nodes") ?? null;
    }
    if (resource === "interfaces") {
      payload.interface_type = canonicalInterfaceType(rest.interface_type);
      payload.hardware_node_id = await resolveObjectReference(rest.hardware_node_id, "hardware-nodes") ?? null;
      payload.function_id = await resolveObjectReference(rest.function_id, "functions") ?? null;
    }
    if (resource === "messages") {
      payload.interface_id = await resolveObjectReference(rest.interface_id, "interfaces") ?? null;
      payload.direction = rest.direction ?? "tx";
      payload.message_id_hex = rest.message_id_hex ?? null;
      payload.cycle_ms = rest.cycle_ms ?? 10;
      payload.dlc = rest.dlc ?? 8;
    }
    if (resource === "signals") {
      payload.message_id = await resolveObjectReference(rest.message_id, "messages") ?? null;
      payload.display_name = rest.display_name ?? rest.name;
      payload.start_bit = rest.start_bit ?? 0;
      payload.length_bits = rest.length_bits ?? 16;
      payload.byte_order = rest.byte_order ?? "little_endian";
      payload.data_type = rest.data_type ?? "unsigned";
      payload.factor = rest.factor ?? 1;
      payload.offset_value = rest.offset_value ?? 0;
      payload.unit = rest.unit ?? null;
      payload.min_value = rest.min_value ?? null;
      payload.max_value = rest.max_value ?? null;
    }

    proposal = await createProposal({
      proposal_type: "OBJECT",
      target_object: { resource },
      prompt: `Erzeuge ${resource}: ${rest.name}`,
      model: engineeringAgentOrchestrator,
      proposed_objects: [payload],
      evidence: [],
      retrieved_context: [],
      validation_results: [],
      created_by: "engineering-chat-agent",
    });
  }

  const proposalId = String(proposal.proposal_id ?? "");
  if (!proposalId) throw new Error(`Proposal fuer ${rest.name} besitzt keine ID.`);
  await validateEngineeringProposal(proposalId);
  const approved = await approveEngineeringProposal(proposalId);
  const canonicalObjects = canonicalObjectsFromProposal(approved, resource);
  if (!canonicalObjects.length) {
    throw new Error(`${rest.name} konnte nicht in das kanonische Modell uebernommen werden.`);
  }
  return {
    created: true,
    reused: Boolean(existingProposal),
    resource,
    proposal: approved,
    canonical_objects: canonicalObjects,
    note: "Objekt wurde als AIProposal auditiert, validiert und sofort kanonisch registriert.",
  };
}

const listEngineeringObjects = tool({
  description:
    "Liste vorhandene Engineering-Objekte (HardwareNode, Function, Interface, Message oder Signal) " +
    "aus dem kanonischen Modell, optional gefiltert nach Domäne oder verknüpfter ID.",
  inputSchema: z.object({
    resource: z.enum(RESOURCE_ENUM).describe("Ressourcentyp im Plural, z. B. 'hardware-nodes'."),
    domain: z.string().optional().describe("Filter nach Anwendungsdomäne, z. B. 'automotive'."),
    hardware_node_id: z.string().optional().describe("Filter für Functions/Interfaces nach Hardware-Knoten-ID."),
    interface_id: z.string().optional().describe("Filter für Messages nach Interface-ID."),
    message_id: z.string().optional().describe("Filter für Signals nach Message-ID."),
  }),
  execute: async ({ resource, domain, hardware_node_id, interface_id, message_id }) => {
    const result = await listObjects(resource, {
      domain,
      hardware_node_id,
      interface_id,
      message_id,
    });
    return { count: result.count, items: result.items };
  },
});

const proposeEngineeringObject = tool({
  description:
    "Erzeuge ein Engineering-Objekt, halte den KI-Vorschlag als Auditspur fest und " +
    "registriere das valide Ergebnis sofort im kanonischen Modell.",
  inputSchema: z.object({
    resource: z.enum(RESOURCE_ENUM),
    name: z.string(),
    description: z.string().optional(),
    domain: z.string().optional(),
    device_type: z
      .string()
      .optional()
      .describe("Nur für 'hardware-nodes', z. B. 'ECU', 'PLC', 'Gateway'."),
    interface_type: z
      .string()
      .optional()
      .describe("Nur für 'interfaces', z. B. 'CAN', 'Ethernet', 'ModbusTCP'."),
    hardware_node_id: z.string().optional().describe("Für 'functions'/'interfaces': zugehöriger HardwareNode."),
    function_id: z.string().optional().describe("Für 'interfaces': zugehörige Function."),
    interface_id: z.string().optional().describe("Für 'messages': zugehöriges Interface."),
    message_id: z.string().optional().describe("Für 'signals': zugehörige Message."),
    direction: z.enum(["rx", "tx", "bidirectional"]).optional().describe("Nur für 'messages'."),
    message_id_hex: z.string().optional().describe("Nur für 'messages', z. B. 0x180."),
    cycle_ms: z.number().positive().optional().describe("Nur für 'messages'."),
    dlc: z.number().int().positive().optional().describe("Nur für 'messages'."),
    display_name: z.string().optional().describe("Nur für 'signals'."),
    start_bit: z.number().int().min(0).optional().describe("Nur für 'signals'."),
    length_bits: z.number().int().positive().optional().describe("Nur für 'signals'."),
    byte_order: z.enum(["little_endian", "big_endian"]).optional().describe("Nur für 'signals'."),
    data_type: z.string().optional().describe("Nur für 'signals'."),
    factor: z.number().optional().describe("Nur für 'signals'."),
    offset_value: z.number().optional().describe("Nur für 'signals'."),
    unit: z.string().optional().describe("Nur für 'signals'."),
    min_value: z.number().optional().describe("Nur für 'signals'."),
    max_value: z.number().optional().describe("Nur für 'signals'."),
  }),
  execute: async (input) => serializeProposalCreation(() => createAndApproveEngineeringObject(input)),
});

const engineeringChainInputSchema = z.object({
    hardware_name: z.string().describe("Name des Hardware-Knotens, z. B. ThermalECU."),
    hardware_description: z.string().optional(),
    device_type: z.string().optional().describe("Standard: ECU."),
    function_name: z.string(),
    function_description: z.string().optional(),
    interface_name: z.string(),
    interface_type: z.string().optional().describe("Standard: CAN."),
    message_name: z.string(),
    message_id_hex: z.string().optional(),
    direction: z.enum(["rx", "tx", "bidirectional"]).optional(),
    cycle_ms: z.number().positive().optional(),
    dlc: z.number().int().positive().optional(),
    signal_name: z.string(),
    signal_display_name: z.string().optional(),
    start_bit: z.number().int().min(0).optional(),
    length_bits: z.number().int().positive().optional(),
    byte_order: z.enum(["little_endian", "big_endian"]).optional(),
    data_type: z.string().optional(),
    factor: z.number().optional(),
    offset_value: z.number().optional(),
    unit: z.string().optional(),
    min_value: z.number().optional(),
    max_value: z.number().optional(),
    domain: z.string().optional(),
  });

type EngineeringChainInput = z.infer<typeof engineeringChainInputSchema>;

async function registerEngineeringChain(input: EngineeringChainInput) {
    const canonicalObjects: CanonicalEngineeringObject[] = [];
    const steps: Array<Record<string, unknown>> = [];

    const hardware = await createAndApproveEngineeringObject({
      resource: "hardware-nodes",
      name: input.hardware_name,
      description: input.hardware_description,
      domain: input.domain,
      device_type: input.device_type ?? "ECU",
    });
    canonicalObjects.push(...hardware.canonical_objects);
    steps.push(hardware);
    const hardwareId = hardware.canonical_objects[0]?.id;

    const engineeringFunction = await createAndApproveEngineeringObject({
      resource: "functions",
      name: input.function_name,
      description: input.function_description,
      domain: input.domain,
      hardware_node_id: hardwareId,
    });
    canonicalObjects.push(...engineeringFunction.canonical_objects);
    steps.push(engineeringFunction);
    const functionId = engineeringFunction.canonical_objects[0]?.id;

    const engineeringInterface = await createAndApproveEngineeringObject({
      resource: "interfaces",
      name: input.interface_name,
      domain: input.domain,
      hardware_node_id: hardwareId,
      function_id: functionId,
      interface_type: input.interface_type ?? "CAN",
    });
    canonicalObjects.push(...engineeringInterface.canonical_objects);
    steps.push(engineeringInterface);
    const interfaceId = engineeringInterface.canonical_objects[0]?.id;

    const message = await createAndApproveEngineeringObject({
      resource: "messages",
      name: input.message_name,
      domain: input.domain,
      interface_id: interfaceId,
      message_id_hex: input.message_id_hex,
      direction: input.direction ?? "tx",
      cycle_ms: input.cycle_ms ?? 10,
      dlc: input.dlc ?? 8,
    });
    canonicalObjects.push(...message.canonical_objects);
    steps.push(message);
    const messageId = message.canonical_objects[0]?.id;

    const signal = await createAndApproveEngineeringObject({
      resource: "signals",
      name: input.signal_name,
      display_name: input.signal_display_name,
      domain: input.domain,
      message_id: messageId,
      start_bit: input.start_bit ?? 0,
      length_bits: input.length_bits ?? 16,
      byte_order: input.byte_order ?? "little_endian",
      data_type: input.data_type ?? "unsigned",
      factor: input.factor ?? 1,
      offset_value: input.offset_value ?? 0,
      unit: input.unit,
      min_value: input.min_value,
      max_value: input.max_value,
    });
    canonicalObjects.push(...signal.canonical_objects);
    steps.push(signal);

    return {
      created: true,
      complete: canonicalObjects.length === RESOURCE_ENUM.length,
      canonical_objects: canonicalObjects,
      steps,
      note: "Vollstaendige Engineering-Kette wurde kanonisch registriert; die Proposals bleiben als Auditspur erhalten.",
    };
}

const createEngineeringChain = tool({
  description:
    "Erzeuge eine vollstaendige kanonische Engineering-Kette in einem Lauf: HardwareNode, Function, Interface, " +
    "Message und Signal. Jedes Element wird als AIProposal auditiert, validiert und sofort registriert.",
  inputSchema: engineeringChainInputSchema,
  execute: async (input) => serializeProposalCreation(() => registerEngineeringChain(input)),
});

export async function registerEngineeringSpecification(specificationText: string) {
  return serializeProposalCreation(async () => {
    const extracted = extractEngineeringSpecification(specificationText);
    if (!extracted.chains.length) {
      return {
        created: false,
        complete: false,
        recognized: 0,
        failures: [{ name: "Spezifikation", error: "Keine benannten Hardware-Objekte erkannt." }],
        canonical_objects: [],
      };
    }

    const canonicalObjects: CanonicalEngineeringObject[] = [];
    const results: Array<Record<string, unknown>> = [];
    const failures: Array<{ name: string; error: string }> = [];
    for (const chain of extracted.chains) {
      try {
        const result = await registerEngineeringChain(chain);
        canonicalObjects.push(...result.canonical_objects);
        results.push({
          hardware_name: chain.hardware_name,
          complete: result.complete,
          canonical_count: result.canonical_objects.length,
        });
      } catch (error) {
        failures.push({
          name: chain.hardware_name,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    return {
      created: canonicalObjects.length > 0,
      complete: failures.length === 0 && results.length === extracted.chains.length,
      recognized: extracted.chains.length,
      registered_chains: results.length,
      domain: extracted.domain,
      interface_type: extracted.interfaceType,
      results,
      failures,
      canonical_objects: canonicalObjects,
      note: failures.length
        ? "Die fehlerfreien Teilnehmer wurden registriert; fehlgeschlagene Teilnehmer sind einzeln ausgewiesen."
        : "Alle aus dem Text erkannten Teilnehmer wurden als vollstaendige Engineering-Ketten registriert.",
    };
  });
}

const createEngineeringModelFromSpecification = tool({
  description:
    "Erkennt alle benannten Hardware-Objekte und technischen Parameter direkt aus der aktuellen strukturierten Nutzerspezifikation. " +
    "Registriert fuer jeden Teilnehmer eine vollstaendige kanonische Kette und verarbeitet weitere Teilnehmer auch dann, wenn eine einzelne Kette fehlschlaegt.",
  inputSchema: z.object({}),
  execute: async () => registerEngineeringSpecification(currentAgentRequestText()),
});

const listEngineeringRelationsTool = tool({
  description: "Liste Relations (Kanten des Knowledge Graphs) für ein Engineering-Objekt oder nach Typ.",
  inputSchema: z.object({
    object_type: z.enum(OBJECT_TYPE_ENUM).optional(),
    object_id: z.string().optional(),
    relation_type: z.string().optional(),
  }),
  execute: async ({ object_type, object_id, relation_type }) => {
    const result = await listRelations({ object_type, object_id, relation_type });
    return { count: result.count, items: result.items };
  },
});

const proposeEngineeringRelation = tool({
  description:
    "Erzeuge eine Relation zwischen zwei Engineering-Objekten, halte sie als AIProposal-Auditspur fest " +
    "und registriere sie nach erfolgreicher Validierung sofort.",
  inputSchema: z.object({
    source_type: z.enum(OBJECT_TYPE_ENUM),
    source_id: z.string(),
    target_type: z.enum(OBJECT_TYPE_ENUM),
    target_id: z.string(),
    relation_type: z.string().describe("z. B. HAS_INTERFACE, CONNECTED_TO, CONTAINS_SIGNAL, COMMUNICATES_WITH."),
  }),
  execute: async (input) => serializeProposalCreation(async () => {
    const [sourceId, targetId] = await Promise.all([
      resolveCanonicalObjectReference(input.source_id, OBJECT_TYPE_RESOURCE[input.source_type]),
      resolveCanonicalObjectReference(input.target_id, OBJECT_TYPE_RESOURCE[input.target_type]),
    ]);
    const missing = [
      ...(!sourceId ? [{ role: "source", type: input.source_type, reference: input.source_id }] : []),
      ...(!targetId ? [{ role: "target", type: input.target_type, reference: input.target_id }] : []),
    ];
    if (missing.length) {
      return {
        created: false,
        missing,
        note: "Relation nicht angelegt: Quelle und Ziel muessen bereits kanonisch registriert sein.",
      };
    }
    const proposal = await createProposal({
      proposal_type: "RELATION",
      target_object: { source_type: input.source_type, source_id: sourceId },
      prompt: `Erzeuge Relation ${input.relation_type}`,
      model: engineeringAgentOrchestrator,
      proposed_objects: [{ object_type: "Relation", ...input, source_id: sourceId, target_id: targetId }],
      evidence: [],
      retrieved_context: [],
      validation_results: [],
      created_by: "engineering-chat-agent",
    });
    const proposalId = String(proposal.proposal_id ?? "");
    await validateEngineeringProposal(proposalId);
    const approved = await approveEngineeringProposal(proposalId);
    const proposedObjects = Array.isArray(approved.proposed_objects) ? approved.proposed_objects : [];
    const canonicalRelations = proposedObjects.flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const candidate = item as Record<string, unknown>;
      const id = String(candidate.canonical_id ?? "");
      return id ? [{ resource: "relations", id, name: String(candidate.relation_type ?? "Relation") }] : [];
    });
    return { created: true, proposal: approved, canonical_objects: canonicalRelations };
  }),
});

const inspectEngineeringProposals = tool({
  description:
    "Liest Engineering-AIProposals fuer Hardware, Funktionen, Interfaces, Messages, Signals und Relations. " +
    "Nutze dieses Tool nach einer Bestaetigung, um offene Vorschlaege vor der Freigabe zu finden.",
  inputSchema: z.object({
    status: z.enum(["AI_GENERATED", "DRAFT", "READY_FOR_REVIEW", "PARTIALLY_APPROVED", "APPROVED", "REJECTED", "SUPERSEDED"]).optional(),
  }),
  execute: async ({ status }) => listEngineeringProposals({ status }),
});

const validateEngineeringProposalTool = tool({
  description:
    "Validiert einen Engineering-AIProposal und markiert ihn als READY_FOR_REVIEW, wenn alle Eintraege valide sind. " +
    "Es werden noch keine kanonischen Objekte angelegt.",
  inputSchema: z.object({ proposal_id: z.string() }),
  execute: async ({ proposal_id }) => validateEngineeringProposal(proposal_id),
});

const approveEngineeringProposalTool = tool({
  description:
    "Gibt einen validen Engineering-AIProposal nach ausdruecklicher Nutzerbestaetigung frei und legt die enthaltenen " +
    "Objekte oder Relations im kanonischen Simulator-Modell an.",
  inputSchema: z.object({
    proposal_id: z.string(),
    indexes: z.array(z.number().int().min(0)).optional(),
  }),
  execute: async ({ proposal_id, indexes }) => approveEngineeringProposal(proposal_id, indexes),
});

const approveAllValidEngineeringProposalsTool = tool({
  description:
    "Gibt nach ausdruecklicher Nutzerbestaetigung alle validen offenen Engineering-AIProposals frei. " +
    "Dabei werden valide Eintraege als echte Simulator-Objekte angelegt; invalide Eintraege bleiben zur Bearbeitung offen.",
  inputSchema: z.object({}),
  execute: async () => approveAllValidEngineeringProposals(),
});

const inspectRoutingTable = tool({
  description: "Liest die aktuelle Routing-Tabelle inklusive Status, Validierung und Freigabe. Reines Read Tool.",
  inputSchema: z.object({}),
  execute: async () => listRoutingEntries(),
});

const inspectRoutingObject = (resource: (typeof RESOURCE_ENUM)[number], label: string) => tool({
  description: `Liest ein vorhandenes ${label} aus dem kanonischen Engineering-Modell.`,
  inputSchema: z.object({ id: z.string() }),
  execute: async ({ id }) => getObject(resource, id),
});

const inspectTopology = tool({
  description: "Liest CONNECTED_TO-Kanten der aktuellen Topologie für graphbasierte Routinganalysen.",
  inputSchema: z.object({}),
  execute: async () => listRelations({ relation_type: "CONNECTED_TO" }),
});

const inspectNetwork = tool({
  description: "Liest die aus Interface-Konfigurationen abgeleiteten Netzwerke und Protokollbindungen.",
  inputSchema: z.object({ network_id: z.string().optional() }),
  execute: async ({ network_id }) => {
    const interfaces = await listObjects("interfaces");
    const items = interfaces.items.filter((item) => {
      if (!network_id) return true;
      const configuration = item.configuration as Record<string, unknown> | undefined;
      return configuration?.network_id === network_id || configuration?.network === network_id;
    });
    return { count: items.length, items };
  },
});

const inspectNeighbors = tool({
  description: "Liest eingehende und ausgehende Knowledge-Graph-Kanten eines Engineering-Objekts.",
  inputSchema: z.object({ object_id: z.string() }),
  execute: async ({ object_id }) => {
    const relations = await listRelations();
    return {
      outgoing: relations.items.filter((item) => item.source_id === object_id),
      incoming: relations.items.filter((item) => item.target_id === object_id),
    };
  },
});

const inspectGateway = tool({
  description: "Listet vorhandene Gateway Hardware Nodes.",
  inputSchema: z.object({}),
  execute: async () => listObjects("hardware-nodes", { device_type: "Gateway" }),
});

const inspectProtocol = tool({
  description: "Liest unterstützte Routingprotokolle und Routingarten.",
  inputSchema: z.object({ protocol: z.string().optional() }),
  execute: async ({ protocol }) => {
    const schema = await getRoutingSchema();
    return { requested: protocol, schema };
  },
});

const findPaths = tool({
  description: "Findet und bewertet graphbasierte Pfadkandidaten zwischen zwei Hardware Nodes.",
  inputSchema: z.object({ source: z.string(), target: z.string() }),
  execute: async ({ source, target }) => findRoutingPaths(source, target),
});

const inspectRoute = tool({
  description: "Liest eine RoutingEntry inklusive vollständiger Pfad- und Governance-Daten.",
  inputSchema: z.object({ route_id: z.string() }),
  execute: async ({ route_id }) => getRoutingEntry(route_id),
});

const routeProposalInputSchema = z.object({
    prompt: z.string(),
    source_node_id: z.string().describe("Kanonische ID oder exakter Name des sendenden HardwareNode."),
    destination_node_ids: z.array(z.string()).min(1).describe("Kanonische IDs oder exakte Namen anderer HardwareNodes."),
    message_id: z.string().optional().describe("Kanonische ID oder exakter Name der Message."),
    signal_ids: z.array(z.string()).optional().describe("Kanonische IDs oder exakte Namen der Signals."),
    routing_type: z.string().optional(),
  });

type RouteProposalInput = z.infer<typeof routeProposalInputSchema>;

async function createVerifiedRouteProposal(input: RouteProposalInput) {
    const hardware = await listObjects("hardware-nodes");
    const resolveFrom = (items: Record<string, unknown>[], value: string) => items.find(
      (item) => String(item.id ?? "") === value || sameEngineeringName(item.name, value),
    );
    const source = resolveFrom(hardware.items, input.source_node_id);
    const destinations = input.destination_node_ids.map((value) => resolveFrom(hardware.items, value));
    const missingDestinations = input.destination_node_ids.filter((_, index) => !destinations[index]);
    const availableNodes = hardware.items.map((item) => ({ id: item.id, name: item.name }));

    if (!source || missingDestinations.length) {
      return {
        created: false,
        blocked: true,
        reason: !source
          ? `Source HardwareNode '${input.source_node_id}' wurde nicht gefunden.`
          : `Destination HardwareNode(s) nicht gefunden: ${missingDestinations.join(", ")}.`,
        available_nodes: availableNodes,
      };
    }
    const sourceId = String(source.id);
    const destinationIds = destinations.map((item) => String(item?.id ?? ""));
    if (destinationIds.some((id) => id === sourceId)) {
      return {
        created: false,
        blocked: true,
        reason: "Source und Destination muessen verschiedene HardwareNodes sein.",
        available_nodes: availableNodes,
      };
    }
    if (hardware.items.length < 2) {
      return {
        created: false,
        blocked: true,
        reason: "Routing benoetigt mindestens zwei kanonische HardwareNodes (Producer und Consumer).",
        available_nodes: availableNodes,
      };
    }

    let messageId: string | undefined;
    if (input.message_id) {
      const messages = await listObjects("messages");
      const message = resolveFrom(messages.items, input.message_id);
      if (!message) {
        return {
          created: false,
          blocked: true,
          reason: `Message '${input.message_id}' wurde nicht im kanonischen Modell gefunden.`,
        };
      }
      messageId = String(message.id);
    }

    let signalIds: string[] | undefined;
    if (input.signal_ids?.length) {
      const signals = await listObjects("signals");
      const resolvedSignals = input.signal_ids.map((value) => resolveFrom(signals.items, value));
      const missingSignals = input.signal_ids.filter((_, index) => !resolvedSignals[index]);
      if (missingSignals.length) {
        return {
          created: false,
          blocked: true,
          reason: `Signal(s) nicht im kanonischen Modell gefunden: ${missingSignals.join(", ")}.`,
        };
      }
      signalIds = resolvedSignals.map((item) => String(item?.id ?? ""));
    }

    const proposals = await listRoutingProposals();
    const duplicate = proposals.items.find((proposal) => {
      if (["REJECTED", "SUPERSEDED"].includes(String(proposal.status ?? ""))) return false;
      const routes = Array.isArray(proposal.generated_routes) ? proposal.generated_routes : [];
      return routes.some((route) => {
        if (!route || typeof route !== "object") return false;
        const candidate = route as Record<string, unknown>;
        const routeSource = candidate.source && typeof candidate.source === "object"
          ? candidate.source as Record<string, unknown>
          : {};
        const payload = candidate.payload && typeof candidate.payload === "object"
          ? candidate.payload as Record<string, unknown>
          : {};
        const destinations = Array.isArray(candidate.destinations) ? candidate.destinations : [];
        const candidateDestinationIds = destinations.flatMap((destination) => {
          if (!destination || typeof destination !== "object") return [];
          return [String((destination as Record<string, unknown>).node_id ?? "")];
        });
        return String(routeSource.node_id ?? "") === sourceId
          && destinationIds.every((id) => candidateDestinationIds.includes(id))
          && (!messageId || String(payload.message_id ?? "") === messageId);
      });
    });
    if (duplicate) {
      return {
        created: false,
        reused: true,
        proposal: duplicate,
        note: "Ein inhaltlich gleicher aktiver RoutingProposal existiert bereits; es wurde kein Duplikat erzeugt.",
      };
    }

    try {
      return await generateRoutingProposal({
        ...input,
        source_node_id: sourceId,
        destination_node_ids: destinationIds,
        message_id: messageId,
        signal_ids: signalIds,
        actor: "engineering-chat-agent",
      });
    } catch (error) {
      return {
        created: false,
        blocked: true,
        reason: error instanceof Error ? error.message : "RoutingProposal konnte nicht erzeugt werden.",
        available_nodes: availableNodes,
      };
    }
}

const createRouteProposal = tool({
  description:
    "Erzeugt einen getrennten RoutingProposal anhand von Topologie, Nodes, Interfaces, Message und Signal-Selektion. " +
    "Akzeptiert kanonische IDs oder exakte Objektnamen, prüft alle Referenzen vorab und aktiviert oder genehmigt niemals Routen.",
  inputSchema: routeProposalInputSchema,
  execute: createVerifiedRouteProposal,
});

const routingEndpointInputSchema = z.object({
  hardware_name: z.string().describe("Eindeutiger Name des empfangenden HardwareNode."),
  hardware_description: z.string().optional(),
  device_type: z.string().optional().describe("Standard: ECU."),
  function_name: z.string().describe("Empfangende oder verarbeitende Funktion."),
  function_description: z.string().optional(),
  interface_name: z.string().describe("Eindeutiger Name des empfangenden Interface."),
  interface_type: z.string().optional().describe("Standard: CAN."),
  domain: z.string().optional(),
});

const createRoutableEngineeringPair = tool({
  description:
    "Erzeugt atomisch eine vollstaendige Producer-Kette, einen separaten Consumer-Endpunkt und danach einen " +
    "RoutingProposal mit ausschliesslich kanonischen IDs. Verwende dieses Tool, wenn fuer ein Routing-Ziel noch " +
    "Engineering-Teilnehmer oder Payload-Objekte fehlen.",
  inputSchema: z.object({
    prompt: z.string(),
    source: engineeringChainInputSchema.describe("Producer-Kette inklusive Message und Signal."),
    destination: routingEndpointInputSchema,
    routing_type: z.string().optional(),
  }),
  execute: async ({ prompt, source, destination, routing_type }) => serializeProposalCreation(async () => {
    if (sameEngineeringName(source.hardware_name, destination.hardware_name)) {
      return {
        created: false,
        blocked: true,
        reason: "Producer und Consumer muessen verschiedene HardwareNodes sein.",
      };
    }

    const sourceResult = await registerEngineeringChain(source);
    const sourceObjects = sourceResult.canonical_objects;
    const sourceNode = sourceObjects.find((item) => item.resource === "hardware-nodes");
    const message = sourceObjects.find((item) => item.resource === "messages");
    const signal = sourceObjects.find((item) => item.resource === "signals");

    const destinationHardware = await createAndApproveEngineeringObject({
      resource: "hardware-nodes",
      name: destination.hardware_name,
      description: destination.hardware_description,
      domain: destination.domain ?? source.domain,
      device_type: destination.device_type ?? "ECU",
    });
    const destinationNode = destinationHardware.canonical_objects[0];
    const destinationFunction = await createAndApproveEngineeringObject({
      resource: "functions",
      name: destination.function_name,
      description: destination.function_description,
      domain: destination.domain ?? source.domain,
      hardware_node_id: destinationNode?.id,
    });
    const destinationInterface = await createAndApproveEngineeringObject({
      resource: "interfaces",
      name: destination.interface_name,
      interface_type: destination.interface_type ?? source.interface_type ?? "CAN",
      domain: destination.domain ?? source.domain,
      hardware_node_id: destinationNode?.id,
      function_id: destinationFunction.canonical_objects[0]?.id,
    });
    const canonicalObjects = [
      ...sourceObjects,
      ...destinationHardware.canonical_objects,
      ...destinationFunction.canonical_objects,
      ...destinationInterface.canonical_objects,
    ];

    if (!sourceNode?.id || !destinationNode?.id || !message?.id || !signal?.id) {
      return {
        created: false,
        blocked: true,
        reason: "Das Routing-Paket konnte die kanonischen Producer-, Consumer- oder Payload-IDs nicht vollstaendig aufloesen.",
        canonical_objects: canonicalObjects,
      };
    }

    const routingProposal = await createVerifiedRouteProposal({
      prompt,
      source_node_id: sourceNode.id,
      destination_node_ids: [destinationNode.id],
      message_id: message.id,
      signal_ids: [signal.id],
      routing_type,
    });
    if (routingProposal && typeof routingProposal === "object" && "blocked" in routingProposal && routingProposal.blocked) {
      return { ...routingProposal, canonical_objects: canonicalObjects };
    }
    return {
      created: true,
      complete: true,
      canonical_objects: canonicalObjects,
      routing_proposal: routingProposal,
      note: "Producer, Consumer und Payload wurden kanonisch registriert; der RoutingProposal wurde mit aufgeloesten IDs erzeugt.",
    };
  }),
});

const listRouteProposals = tool({
  description: "Liest getrennt gespeicherte Routing-Proposals. Verändert keine RoutingEntry.",
  inputSchema: z.object({}),
  execute: async () => listRoutingProposals(),
});

const updateRouteProposal = tool({
  description: "Bearbeitet Inhalt oder Status eines Routing-Proposals, ohne eine Route freizugeben.",
  inputSchema: z.object({
    proposal_id: z.string(),
    status: z.enum(["AI_GENERATED", "DRAFT", "VALIDATED", "READY_FOR_REVIEW", "REJECTED", "SUPERSEDED"]).optional(),
    generated_routes: z.array(z.record(z.string(), z.unknown())).optional(),
  }),
  execute: async ({ proposal_id, ...changes }) => updateRoutingProposal(proposal_id, { ...changes, actor: "engineering-chat-agent" }),
});

const deleteRouteProposal = tool({
  description: "Löscht ein nicht übernommenes Routing-Proposal. Freigegebene Routen bleiben unberührt.",
  inputSchema: z.object({ proposal_id: z.string() }),
  execute: async ({ proposal_id }) => {
    await deleteRoutingProposal(proposal_id);
    return { deleted: true, proposal_id };
  },
});

const validateRoutingTableTool = tool({
  description: "Validiert die gesamte Routing-Tabelle und meldet Duplikate, Lücken und Konflikte.",
  inputSchema: z.object({}),
  execute: async () => validateRoutingTable(),
});

const validateRouteTool = tool({
  description: "Validiert eine gespeicherte Route technisch, ohne sie freizugeben.",
  inputSchema: z.object({ route_id: z.string() }),
  execute: async ({ route_id }) => validateRoutingEntry(route_id),
});

const inspectRoutePath = tool({
  description: "Liest Hops, Gateways, Transformationen und erkannte Routing-Loops einer Route.",
  inputSchema: z.object({ route_id: z.string() }),
  execute: async ({ route_id }) => getRoutingPath(route_id),
});

const inspectRouteEvidence = tool({
  description: "Liest technische Evidence und nachvollziehbare Begründungen einer Route, ohne Chain-of-Thought.",
  inputSchema: z.object({ route_id: z.string() }),
  execute: async ({ route_id }) => getRoutingEvidence(route_id),
});

const suggestDestination = tool({
  description: "Schlägt vorhandene Hardware Nodes als mögliche Consumer vor. Der Vorschlag benötigt weiterhin Review.",
  inputSchema: z.object({ source_node_id: z.string() }),
  execute: async ({ source_node_id }) => {
    const nodes = await listObjects("hardware-nodes");
    return { items: nodes.items.filter((item) => item.id !== source_node_id) };
  },
});

const inspectWorkflowMap = tool({
  description:
    "Liefert die verbindliche Workflow-Landkarte inklusive Schrittzielen, Beziehungen, erlaubten Tools und Done-Kriterien. " +
    "Nutze dieses Tool, bevor du Zielaufgaben wie 'arbeite bis zur Simulation' planst.",
  inputSchema: z.object({}),
  execute: async () => ({ steps: WORKFLOW_MANIFEST }),
});

const planWorkflowTarget = tool({
  description:
    "Uebersetzt eine Nutzer-Zielbeschreibung in den erforderlichen Workflowpfad. " +
    "Beispiele: 'arbeite bis zur Simulation', 'bis Preflight', 'nur Engineering-Modell'.",
  inputSchema: z.object({
    request: z.string(),
  }),
  execute: async ({ request }) => {
    const target_step = inferWorkflowTarget(request);
    const required_steps = workflowStepIdsUntil(target_step);
    return {
      target_step,
      required_steps,
      steps: WORKFLOW_MANIFEST.filter((step) => required_steps.includes(step.id)),
      autonomy: "continue_until_target",
      review_policy:
        "Bis zum genannten Ziel weiterarbeiten. Wenn Human Review noetig ist, alle Proposals vorbereiten, validieren und nach Allow uebernehmen; danach Workflow fortsetzen.",
    };
  },
});

const calculateCapacity = tool({
  description:
    "Fuehrt die persistente Capacity-&-Timing-Berechnung fuer den aktiven Workflow aus. " +
    "Nutze dies fuer Workflow-Fortschritt, nicht analyze_capacity_scenario.",
  inputSchema: z.object({
    overrides: z.record(z.string(), z.unknown()).optional(),
  }),
  execute: async ({ overrides }) => calculateCapacityAnalysis(overrides ?? {}),
});

const runPreflight = tool({
  description:
    "Fuehrt den aktuellen Validation/Preflight-Schritt persistent aus und liefert ready_for_simulation, Fehler und Warnungen.",
  inputSchema: z.object({}),
  execute: async () => runPreflightAnalysis(),
});

const createSimulationSnapshot = tool({
  description:
    "Legt nach erfolgreichem aktuellem Preflight einen SimulationSnapshot an und setzt den Workflow auf Simulation. " +
    "Stoppt mit einem Workflow-Konflikt, wenn Preflight fehlt oder veraltet ist.",
  inputSchema: z.object({
    configuration: z.record(z.string(), z.unknown()).optional(),
  }),
  execute: async ({ configuration }) => createWorkflowSimulationSnapshot(configuration ?? { mode: "agent-default", source: "engineering-chat-agent" }),
});

const inspectWorkflow = tool({
  description:
    "Liest aktives Projekt, Workflow-Schritt, Selektion, Quellversionen, Status und OUTDATED-Gruende. Reines Read Tool.",
  inputSchema: z.object({}),
  execute: async () => {
    const state = await inspectWorkflowState();
    const topology = state.topology as { nodes?: unknown[]; edges?: unknown[] } | undefined;
    const snapshots = Array.isArray(state.simulation_snapshots) ? state.simulation_snapshots : [];
    return {
      project_id: state.project_id,
      active_step: state.active_step,
      context: state.context,
      versions: state.versions,
      statuses: state.statuses,
      stale_reasons: state.stale_reasons,
      latest_analyses: state.latest_analyses,
      topology_summary: {
        nodes: topology?.nodes?.length ?? 0,
        edges: topology?.edges?.length ?? 0,
      },
      simulation_snapshots: snapshots.slice(0, 10).map((item) => {
        const snapshot = item as Record<string, unknown>;
        return {
          id: snapshot.id,
          job_id: snapshot.job_id,
          status: snapshot.status,
          is_outdated: snapshot.is_outdated,
          outdated_reason: snapshot.outdated_reason,
          source_versions: snapshot.source_versions,
          created_at: snapshot.created_at,
        };
      }),
      rule: state.rule,
    };
  },
});

const inspectCapacity = tool({
  description:
    "Liest die letzte Capacity-&-Timing-Analyse mit Last, Reserve, Latenz, Queueing, Gateway-Last und Provenance.",
  inputSchema: z.object({}),
  execute: async () => {
    const snapshot = await inspectCapacityAnalysis();
    const results = (snapshot.results ?? {}) as Record<string, unknown>;
    const list = (key: string, limit = 20) => Array.isArray(results[key]) ? results[key].slice(0, limit) : [];
    return {
      id: snapshot.id,
      status: snapshot.status,
      is_outdated: snapshot.is_outdated,
      outdated_reason: snapshot.outdated_reason,
      source_versions: snapshot.source_versions,
      overview: results.overview,
      timing: results.timing,
      reliability: results.reliability,
      synchronization: results.synchronization,
      networks: list("networks"),
      gateways: list("gateways"),
      critical_paths: list("critical_paths", 10),
      bottlenecks: list("bottlenecks"),
      findings: Array.isArray(snapshot.findings) ? snapshot.findings.slice(0, 50) : [],
      provenance: snapshot.provenance,
    };
  },
});

const inspectPreflight = tool({
  description:
    "Liest den letzten Validation/Preflight-Snapshot und seine blockierenden oder warnenden Befunde.",
  inputSchema: z.object({}),
  execute: async () => inspectPreflightAnalysis(),
});

const retrieveEngineeringKnowledge = tool({
  description:
    "Durchsucht kanonische Engineering-Objekte über Keyword-, Vektor-, Metadaten- und Multi-Hop-Graph-Retrieval " +
    "und liefert begrenzten Kontext mit Evidence. Reines Read Tool.",
  inputSchema: z.object({
    query: z.string().min(2),
    selected_object_ids: z.array(z.string()).optional(),
    domain: z.string().optional(),
    technology: z.string().optional(),
    approval_state: z.string().optional(),
    limit: z.number().int().min(1).max(30).optional(),
  }),
  execute: async ({ query, selected_object_ids, domain, technology, approval_state, limit }) =>
    searchEngineeringKnowledge({
      query,
      selected_object_ids,
      filters: { domain, technology, approval_state },
      limit,
    }),
});

const analyzeCapacityScenario = tool({
  description:
    "Berechnet ein unverbindliches What-if-Szenario. Es veraendert weder Engineering-Daten noch freigegebene Parameter.",
  inputSchema: z.object({
    bitrate: z.number().positive().optional(),
    burst_factor: z.number().min(1).optional(),
    gateway_delay_ms: z.number().min(0).optional(),
    retransmission_rate: z.number().min(0).max(1).optional(),
  }),
  execute: async (overrides) => calculateCapacityScenario(overrides),
});

const inspectCapacitySection = (section: string, description: string) => tool({
  description,
  inputSchema: z.object({}),
  execute: async () => {
    const snapshot = await inspectCapacityAnalysis();
    const results = snapshot.results as Record<string, unknown> | undefined;
    return {
      status: snapshot.status,
      is_outdated: snapshot.is_outdated,
      source_versions: snapshot.source_versions,
      data: results?.[section],
      findings: snapshot.findings,
      provenance: snapshot.provenance,
    };
  },
});

const inspectViolations = (prefixes: string[], description: string) => tool({
  description,
  inputSchema: z.object({}),
  execute: async () => {
    const [capacity, preflight] = await Promise.all([inspectCapacityAnalysis(), inspectPreflightAnalysis()]);
    const findings = [...((capacity.findings as Array<Record<string, unknown>> | undefined) ?? []), ...((preflight.findings as Array<Record<string, unknown>> | undefined) ?? [])];
    return {
      capacity_outdated: capacity.is_outdated,
      preflight_outdated: preflight.is_outdated,
      findings: findings.filter((item) => prefixes.some((prefix) => String(item.code ?? "").startsWith(prefix))),
    };
  },
});

const optimizeCapacity = tool({
  description: "Erzeugt nicht angewendete Capacity-Optimierungsvorschlaege mit erwarteter Auswirkung. Niemals autonom anwenden.",
  inputSchema: z.object({}),
  execute: async () => optimizeCapacityAnalysis(),
});

const inspectIntelligence = tool({
  description:
    "Liest die letzte deterministische Data-Science-&-Intelligence-Bewertung mit System Health, Reifegrad, " +
    "Issues, Anomalien, Graph/RAG-Evidence, Root Causes, Trends und Recommendations. Reines Read Tool.",
  inputSchema: z.object({}),
  execute: async () => {
    const snapshot = await inspectIntelligenceAssessment();
    const results = (snapshot.results ?? {}) as Record<string, unknown>;
    const list = (key: string, limit = 20) => Array.isArray(results[key]) ? results[key].slice(0, limit) : [];
    return {
      id: snapshot.id,
      status: snapshot.status,
      is_outdated: snapshot.is_outdated,
      outdated_reason: snapshot.outdated_reason,
      source_versions: snapshot.source_versions,
      system_health: results.system_health,
      maturity: results.maturity,
      critical_issues: list("critical_issues"),
      anomalies: list("anomalies"),
      root_causes: list("root_causes"),
      recommendations: list("recommendations"),
      trends: results.trends,
      graph_insights: results.graph_insights,
      rag_knowledge_insights: list("rag_knowledge_insights"),
      provenance: snapshot.provenance,
    };
  },
});

const proposeOptimization = tool({
  description:
    "Speichert eine nachvollziehbare OptimizationProposal aus einer vorhandenen Intelligence-Empfehlung. " +
    "Der Vorschlag wird nicht angewendet und benötigt Human Review und Approval.",
  inputSchema: z.object({
    category: z.string(),
    problem: z.string(),
    affected_objects: z.array(z.string()).default([]),
    recommendation: z.string(),
    expected_impact: z.record(z.string(), z.unknown()).default({}),
    evidence: z.array(z.record(z.string(), z.unknown())).default([]),
    graph_context: z.array(z.record(z.string(), z.unknown())).default([]),
    rag_context: z.array(z.record(z.string(), z.unknown())).default([]),
    confidence: z.number().min(0).max(1).optional(),
    priority: z.number().min(0).max(100).optional(),
  }),
  execute: async (payload) => createIntelligenceProposal({
    ...payload,
    provenance: { agent: "engineering-chat-agent", model: "configured-provider" },
  }),
});

const engineeringTools = {
  inspect_workflow: inspectWorkflow,
  inspect_workflow_map: inspectWorkflowMap,
  plan_workflow_target: planWorkflowTarget,
  inspect_capacity_timing: inspectCapacity,
  calculate_capacity_timing: calculateCapacity,
  inspect_preflight: inspectPreflight,
  run_preflight: runPreflight,
  create_simulation_snapshot: createSimulationSnapshot,
  inspect_intelligence: inspectIntelligence,
  create_optimization_proposal: proposeOptimization,
  retrieve_engineering_knowledge: retrieveEngineeringKnowledge,
  analyze_capacity_scenario: analyzeCapacityScenario,
  inspect_timing: inspectCapacitySection("timing", "Liest Timing, E2E-Latenz, Deadline- und Jitterstatus mit Provenance."),
  inspect_jitter: inspectCapacitySection("routes", "Liest routebezogene Jitterwerte, Budgets und Verletzungen."),
  inspect_latency: inspectCapacitySection("critical_paths", "Liest kritische Pfade mit Latenzaufschluesselung und Anforderungen."),
  inspect_queue: inspectCapacitySection("routes", "Liest Queueing-Verzoegerung, Policy, Prioritaet und Route-Bottlenecks."),
  inspect_gateway_load: inspectCapacitySection("gateways", "Liest Gateway-Durchsatz, Queue-, Processing- und Conversion-Last."),
  inspect_synchronization: inspectCapacitySection("synchronization", "Liest Clock Drift, Sync Precision und maximalen Synchronisationsfehler."),
  identify_bottleneck: inspectCapacitySection("bottlenecks", "Identifiziert berechnete Capacity- und Timing-Bottlenecks."),
  identify_deadline_violation: inspectViolations(["TIMING_DEADLINE", "TIMING_TIMEOUT", "TIMING_FRESHNESS"], "Liest Deadline-, Timeout- und Freshness-Verletzungen."),
  identify_jitter_violation: inspectViolations(["TIMING_JITTER"], "Liest Jitterverletzungen und Empfehlungen."),
  identify_reliability_violation: inspectViolations(["RELIABILITY_"], "Liest Reliability-Verletzungen und Empfehlungen."),
  optimize_capacity: optimizeCapacity,
  listEngineeringObjects,
  createEngineeringModelFromSpecification,
  createEngineeringChain,
  createRoutableEngineeringPair,
  proposeEngineeringObject,
  listEngineeringRelations: listEngineeringRelationsTool,
  proposeEngineeringRelation,
  inspectEngineeringProposals,
  validateEngineeringProposal: validateEngineeringProposalTool,
  approveEngineeringProposal: approveEngineeringProposalTool,
  approveAllValidEngineeringProposals: approveAllValidEngineeringProposalsTool,
  inspect_routing_table: inspectRoutingTable,
  inspect_route: inspectRoute,
  inspect_topology: inspectTopology,
  inspect_network: inspectNetwork,
  inspect_node: inspectRoutingObject("hardware-nodes", "Hardware Node"),
  inspect_interface: inspectRoutingObject("interfaces", "Interface"),
  inspect_message: inspectRoutingObject("messages", "Message"),
  inspect_signal: inspectRoutingObject("signals", "Signal"),
  inspect_gateway: inspectGateway,
  inspect_protocol: inspectProtocol,
  find_route: findPaths,
  find_all_routes: findPaths,
  find_paths: findPaths,
  get_neighbors: inspectNeighbors,
  get_subgraph: inspectNeighbors,
  create_route_proposal: createRouteProposal,
  create_routing_table_proposal: createRouteProposal,
  update_route_proposal: updateRouteProposal,
  delete_route_proposal: deleteRouteProposal,
  inspect_routing_proposals: listRouteProposals,
  validate_route: validateRouteTool,
  validate_routing_table: validateRoutingTableTool,
  calculate_route_latency: validateRouteTool,
  calculate_route_load: validateRouteTool,
  detect_routing_loop: inspectRoutePath,
  detect_duplicate_route: validateRouteTool,
  detect_missing_route: validateRoutingTableTool,
  detect_unreachable_consumer: validateRouteTool,
  check_protocol_compatibility: validateRouteTool,
  show_route_evidence: inspectRouteEvidence,
  suggest_destination: suggestDestination,
  suggest_gateway: inspectGateway,
  suggest_network: inspectNetwork,
  suggest_protocol: inspectProtocol,
  suggest_alternative_route: findPaths,
} as const;

type EngineeringToolName = keyof typeof engineeringTools;

const WORKFLOW_TOOL_GROUPS: Record<string, readonly EngineeringToolName[]> = {
  engineering_model: [
    "inspect_workflow",
    "listEngineeringObjects",
    "createEngineeringModelFromSpecification",
    "createEngineeringChain",
    "createRoutableEngineeringPair",
    "proposeEngineeringObject",
    "listEngineeringRelations",
    "proposeEngineeringRelation",
    "inspectEngineeringProposals",
    "validateEngineeringProposal",
    "approveEngineeringProposal",
    "approveAllValidEngineeringProposals",
  ],
  routing: [
    "inspect_workflow",
    "inspect_routing_table",
    "inspect_routing_proposals",
    "create_route_proposal",
    "validate_routing_table",
    "find_paths",
    "inspect_topology",
    "listEngineeringObjects",
  ],
  network_editor: [
    "inspect_workflow",
    "inspect_topology",
    "inspect_network",
    "get_neighbors",
    "find_paths",
    "validate_routing_table",
  ],
  parameters: ["inspect_workflow", "inspect_protocol", "inspect_network", "inspect_routing_table"],
  capacity_timing: [
    "inspect_workflow",
    "calculate_capacity_timing",
    "inspect_capacity_timing",
    "identify_bottleneck",
    "optimize_capacity",
  ],
  validation: ["inspect_workflow", "run_preflight", "inspect_preflight", "inspect_capacity_timing"],
  simulation: ["inspect_workflow", "create_simulation_snapshot", "inspect_preflight"],
  results_analysis: ["inspect_workflow", "inspect_capacity_timing", "inspect_preflight"],
  data_science_intelligence: [
    "inspect_workflow",
    "inspect_intelligence",
    "retrieve_engineering_knowledge",
    "create_optimization_proposal",
  ],
};

const WORKFLOW_FIRST_TOOL: Record<string, EngineeringToolName> = {
  engineering_model: "listEngineeringObjects",
  routing: "inspect_routing_table",
  network_editor: "inspect_topology",
  parameters: "inspect_workflow",
  capacity_timing: "calculate_capacity_timing",
  validation: "run_preflight",
  simulation: "create_simulation_snapshot",
  results_analysis: "inspect_workflow",
  data_science_intelligence: "inspect_intelligence",
};

const WORKFLOW_PROGRESS_TOOLS: Record<string, readonly EngineeringToolName[]> = {
  engineering_model: [
    "createEngineeringModelFromSpecification",
    "createEngineeringChain",
    "createRoutableEngineeringPair",
    "proposeEngineeringObject",
    "proposeEngineeringRelation",
    "approveEngineeringProposal",
    "approveAllValidEngineeringProposals",
  ],
  routing: ["create_route_proposal", "validate_routing_table"],
  network_editor: ["inspect_topology", "validate_routing_table"],
  parameters: ["inspect_workflow", "inspect_protocol"],
  capacity_timing: ["calculate_capacity_timing"],
  validation: ["run_preflight"],
  simulation: ["create_simulation_snapshot"],
  results_analysis: ["inspect_workflow"],
  data_science_intelligence: ["inspect_intelligence", "create_optimization_proposal"],
};

const COMPLETE_WORKFLOW_STATUSES = new Set(["COMPLETE", "APPROVED"]);
const CONFIRMATION_PATTERN = /\b(allow|bestaetigt|bestätigt|freigeben|uebernehmen|übernehmen|fortfahren|weiter)\b/i;
const RECOVERY_PATTERN =
  /\b(warum[\s\S]{0,40}(gestoppt|abgebrochen|aufgehoert|aufgehört)|gestoppt|abgebrochen|mach weiter|weiterarbeiten|fortsetzen|setze[\s\S]{0,50}fort|wieder aufnehmen|erneut ausfuehren|erneut ausführen)\b/i;
const MUTATION_PATTERN =
  /\b(erzeuge|generiere|erstelle|anlegen|aufbauen|ausfuehren|ausführen|starte|berechne|validiere|simuliere|optimier|reparier|verbinde|verknuepfe|verknüpfe|ordne|zuordnen|registriere)\b/i;
const FULL_ENGINEERING_CHAIN_PATTERN =
  /(hardwarenodes?[\s\S]*functions?[\s\S]*interfaces?[\s\S]*messages?[\s\S]*signals?)|(hardware[\s\S]*funktion[\s\S]*interface[\s\S]*(nachricht|message)[\s\S]*(signal))|(vollstaendige|vollständige|komplette)[\s\S]*?(kette|modell)|(bis einschliesslich signale|bis einschließlich signale)/i;
const RELATION_REQUEST_PATTERN =
  /\b(relation|has_interface|has_function|contains_signal|connected_to|communicates_with|verbinde|verknuepfe|verknüpfe|zuordnen)\b/i;

function modelContentText(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part) => {
      if (!part || typeof part !== "object") return "";
      const text = "text" in part ? part.text : undefined;
      return typeof text === "string" ? text : "";
    })
    .filter(Boolean)
    .join("\n");
}

function userRequestContext(messages: Array<{ role: string; content: unknown }>) {
  const requests = messages
    .filter((message) => message.role === "user")
    .map((message) => modelContentText(message.content))
    .filter(Boolean);
  const latest = requests.at(-1) ?? "";
  const previousTask = [...requests.slice(0, -1)].reverse().find(
    (request) => !RECOVERY_PATTERN.test(concreteRequestText(request)),
  ) ?? latest;
  return {
    latest,
    previousTask,
    conversation: requests.join("\n\n"),
  };
}

function isActionableRequest(request: string) {
  const concrete = concreteRequestText(request);
  return MUTATION_PATTERN.test(concrete) || CONFIRMATION_PATTERN.test(concrete);
}

function isConfirmationRequest(request: string) {
  const concrete = concreteRequestText(request);
  return CONFIRMATION_PATTERN.test(concrete) && !MUTATION_PATTERN.test(concrete);
}

function isRecoveryRequest(request: string) {
  return RECOVERY_PATTERN.test(concreteRequestText(request));
}

function requestsFullEngineeringChain(request: string) {
  return FULL_ENGINEERING_CHAIN_PATTERN.test(concreteRequestText(request));
}

async function engineeringHierarchyStatus() {
  const results = await Promise.all(RESOURCE_ENUM.map(async (resource) => {
    const result = await listObjects(resource);
    return [resource, result.count] as const;
  }));
  const counts = Object.fromEntries(results) as Record<EngineeringResourceName, number>;
  return {
    complete: RESOURCE_ENUM.every((resource) => counts[resource] > 0),
    routingReady: counts["hardware-nodes"] >= 2 && RESOURCE_ENUM.slice(1).every((resource) => counts[resource] > 0),
    counts,
  };
}

async function currentWorkflowPhase(target: string) {
  try {
    const state = await inspectWorkflowState();
    const statuses = (state.statuses ?? {}) as Record<string, unknown>;
    const phase = workflowStepIdsUntil(target).find(
      (stepId) => !COMPLETE_WORKFLOW_STATUSES.has(String(statuses[stepId] ?? "EMPTY").toUpperCase()),
    );
    return phase ?? target;
  } catch (error) {
    auditAgent("workflow phase lookup failed", {
      target,
      error: error instanceof Error ? error.message : String(error),
    });
    return target;
  }
}

export const engineeringAgent = new ToolLoopAgent({
  model: engineeringModel,
  providerOptions: {
    openai: {
      parallelToolCalls: false,
    },
  },
  onStart: (event) => {
    auditAgent("model run started", {
      callId: event.callId,
      provider: event.provider,
      model: event.modelId,
      tools: Object.keys(event.tools ?? {}).length,
    });
  },
  onStepStart: (event) => {
    auditAgent("step started", {
      callId: event.callId,
      step: event.stepNumber + 1,
      previousSteps: event.steps.length,
    });
  },
  onToolExecutionStart: (event) => {
    auditAgent("tool started", {
      callId: event.callId,
      tool: event.toolCall.toolName,
      toolCallId: event.toolCall.toolCallId,
    });
  },
  onToolExecutionEnd: (event) => {
    auditAgent("tool finished", {
      callId: event.callId,
      tool: event.toolCall.toolName,
      toolCallId: event.toolCall.toolCallId,
      ms: event.toolExecutionMs,
      result: event.toolOutput.type,
    });
  },
  onEnd: (event) => {
    auditAgent("model run completed", {
      callId: event.callId,
      finishReason: event.finishReason,
      steps: event.steps.length,
      toolCalls: event.toolCalls.length,
    });
  },
  prepareStep: async ({ steps, initialMessages }) => {
    const request = userRequestContext(initialMessages);
    const confirmation = isConfirmationRequest(request.latest);
    const recovery = isRecoveryRequest(request.latest);
    const continuation = confirmation || recovery;
    const requestBasis = continuation ? request.previousTask : request.latest;
    setCurrentAgentRequestText(requestBasis);
    const structuredSpecification = isStructuredEngineeringSpecification(requestBasis);
    const target = inferWorkflowTarget(requestBasis);
    const workflowSteps = workflowStepIdsUntil(target);
    const targetNeedsRouting = target !== "engineering_model" && workflowSteps.includes("engineering_model");
    const hierarchy = targetNeedsRouting ? await engineeringHierarchyStatus() : null;
    let phase = await currentWorkflowPhase(target);
    if (structuredSpecification) phase = "engineering_model";
    if (targetNeedsRouting && hierarchy && !hierarchy.routingReady) phase = "engineering_model";
    const fullEngineeringChainRequested = requestsFullEngineeringChain(
      requestBasis,
    );
    const relationOnlyRequest = phase === "engineering_model"
      && RELATION_REQUEST_PATTERN.test(concreteRequestText(requestBasis))
      && !fullEngineeringChainRequested;
    const activeTools = structuredSpecification
      ? ["createEngineeringModelFromSpecification"] satisfies EngineeringToolName[]
      : relationOnlyRequest
      ? ["listEngineeringObjects", "listEngineeringRelations", "proposeEngineeringRelation"] satisfies EngineeringToolName[]
      : [...(WORKFLOW_TOOL_GROUPS[phase] ?? WORKFLOW_TOOL_GROUPS.engineering_model)];
    const calledTools = steps.flatMap((step) => step.toolCalls.map((call) => call.toolName));
    const firstTool = confirmation && phase === "engineering_model" && !relationOnlyRequest
      ? "inspectEngineeringProposals"
      : WORKFLOW_FIRST_TOOL[phase] ?? "inspect_workflow";
    const progressTools = WORKFLOW_PROGRESS_TOOLS[phase] ?? [];
    const progressCalls = calledTools.filter((toolName) => progressTools.includes(toolName as EngineeringToolName)).length;
    const minimumProgressCalls = 1;
    const relationLookupCalls = calledTools.filter((toolName) => toolName === "listEngineeringObjects").length;
    const relationProposalCalls = calledTools.filter((toolName) => toolName === "proposeEngineeringRelation").length;
    const specificationCalls = calledTools.filter((toolName) => toolName === "createEngineeringModelFromSpecification").length;
    const resumedMutation = isActionableRequest(requestBasis) || fullEngineeringChainRequested || structuredSpecification;
    const actionable = isActionableRequest(request.latest) || fullEngineeringChainRequested || structuredSpecification || recovery;
    const routingPackageCalls = calledTools.filter((toolName) => toolName === "createRoutableEngineeringPair").length;
    const routingPackageCompleted = routingPackageCalls > 0;
    const routingProposalInspected = calledTools.includes("inspect_routing_proposals");
    const routingProposalCreated = calledTools.includes("create_route_proposal");
    const fullEngineeringChain = phase === "engineering_model" && (
      structuredSpecification
      ||
      fullEngineeringChainRequested
      || Boolean(targetNeedsRouting && hierarchy && !hierarchy.routingReady)
    );
    const toolChoice = structuredSpecification
      ? specificationCalls < 1
        ? { type: "tool" as const, toolName: "createEngineeringModelFromSpecification" as const }
        : "none" as const
      : relationOnlyRequest
      ? relationLookupCalls < 2
        ? { type: "tool" as const, toolName: "listEngineeringObjects" as const }
        : relationProposalCalls < 1
          ? { type: "tool" as const, toolName: "proposeEngineeringRelation" as const }
          : "none" as const
      : !actionable
      ? "auto" as const
      : !calledTools.includes(firstTool)
        ? { type: "tool" as const, toolName: firstTool }
        : recovery && !resumedMutation
          ? "none" as const
        : phase === "routing" && routingProposalCreated
          ? "none" as const
        : phase === "routing" && routingPackageCompleted && !routingProposalInspected
          ? { type: "tool" as const, toolName: "inspect_routing_proposals" as const }
          : phase === "routing" && routingPackageCompleted
            ? "none" as const
        : targetNeedsRouting && hierarchy && !hierarchy.routingReady && routingPackageCalls < 1
          ? { type: "tool" as const, toolName: "createRoutableEngineeringPair" as const }
          : fullEngineeringChain && !calledTools.includes("createEngineeringChain")
            ? { type: "tool" as const, toolName: "createEngineeringChain" as const }
          : progressCalls < minimumProgressCalls
            ? "required" as const
            : "auto" as const;
    const demandModel = demandModelForRequest(request.latest, recovery, actionable);

    auditAgent("step orchestration", {
      step: steps.length + 1,
      target,
      phase,
      activeTools: activeTools.length,
      toolChoice: typeof toolChoice === "string" ? toolChoice : toolChoice.toolName,
      progressCalls,
      fullEngineeringChain,
      relationOnlyRequest,
      structuredSpecification,
      specificationCalls,
      recovery,
      resumedMutation,
      relationLookupCalls,
      relationProposalCalls,
      routingPackageCalls,
      routingProposalInspected,
      routingProposalCreated,
      modelSource: demandModel.source,
      hierarchy: hierarchy ? JSON.stringify(hierarchy.counts) : undefined,
    });

    return {
      activeTools,
      toolChoice,
      model: demandModel.model,
    };
  },
  instructions: `Du bist der Network-Engineering-Assistent des Communication Simulators.

Du hilfst dabei, das kanonische Engineering-Modell zu verstehen und zu erweitern:
HardwareNode (Geräte wie ECU, PLC, Gateway), Function (Funktionen auf einem
Gerät), Interface (Kommunikationsschnittstelle wie CAN, Ethernet), Message
(Nachricht auf einem Interface) und Signal (Feld innerhalb einer Message).
Relations verbinden diese Objekte zu einem Knowledge Graph (z. B.
HAS_INTERFACE, CONTAINS_SIGNAL, COMMUNICATES_WITH).
Die fachliche Anlage folgt der Elternkette:
HardwareNode -> Function -> Interface -> Message -> Signal. Erzeuge keine
untergeordneten Objekte ohne das benoetigte Elternobjekt oder einen passenden
Elternvorschlag.

Der Routing Manager beschreibt technologieunabhängig, welche Information von
welchem Producer über welche Interfaces, Netzwerke und Gateways zu welchen
Consumern gelangt. Nutze Graphpfade, technische Evidence und vorhandene
Engineering-Objekte, bevor du Routingvorschläge erzeugst.

Der verbindliche Workflow lautet:
Engineering-Modell -> Routing-Tabelle -> Netzwerk-Editor -> Parameter ->
Capacity & Timing -> Validation / Preflight -> Simulation -> Results / Analysis ->
Data Science & Intelligence. Schritt 9 bewertet das Gesamtsystem deterministisch,
verbindet Graph/RAG-Evidence und erzeugt ausschliesslich getrennte OptimizationProposals.
Die detaillierte Workflow-Landkarte mit Relationships, Done-Kriterien und
erlaubten Tools ist ueber inspect_workflow_map abrufbar. Bei Zielangaben wie
"arbeite bis zur Simulation", "bis Preflight", "mach ein valides Beispiel" oder
"bis Results" musst du zuerst inspect_workflow und plan_workflow_target nutzen.
Lies bei kontextabhaengigen Fragen zuerst inspect_workflow. Beachte active_project,
active_workflow_step, selected_object, selected_route, selected_network,
selected_signal und selected_simulation. Veraltete Snapshots duerfen analysiert,
aber nicht als aktuell oder simulationsbereit bezeichnet werden.

Regeln:
- Arbeite zielorientiert: Wenn der Nutzer einen Zielzustand nennt, fuehre alle
  dafuer noetigen Tool-Schritte selbststaendig aus, bis dieser Zielzustand
  erreicht ist, ein Tool-Fehler blockiert oder eine fachliche Entscheidung fehlt.
- Wenn die Nachricht den Abschnitt "Konkrete Aufgabe des Nutzers, per Senden
  bestaetigt" enthaelt, gilt der Start als bestaetigt. Frage dann nicht erneut
  nach Kommandos, Ziel oder Startfreigabe, sondern nutze den Projektbrief als
  Rahmen und die konkrete Aufgabe als auszufuehrenden Auftrag.
- Fuer Zielzustand "Simulation" ist die Mindestfolge:
  1) Engineering-Objekte und Relations vorbereiten oder bestaetigen,
  2) Routingvorschlaege/Routen vorbereiten oder bestaetigen,
  3) Topologie/Netzwerk-Synchronitaet pruefen,
  4) Parameter pruefen,
  5) calculate_capacity_timing persistent ausfuehren,
  6) run_preflight ausfuehren,
  7) nur bei ready_for_simulation create_simulation_snapshot ausfuehren.
  Engineering-Objekte werden dabei sofort validiert und kanonisch registriert.
- Bevor du create_route_proposal aufrufst, muessen mindestens zwei verschiedene
  kanonische HardwareNodes sowie die referenzierte Message und ihre Signals
  existieren. Nutze nur IDs oder exakte Namen aus den Lese-Tools. Wenn Producer
  oder Consumer fehlen, vervollstaendige zuerst das Engineering-Modell oder
  melde den fehlenden Teilnehmer klar; wiederhole keinen identischen Fehlerlauf.
- Eine Routing-Tabelle mit null Eintraegen ist nicht valide und darf niemals als
  "technische Pruefung bestanden" zusammengefasst werden.
- Beende deine Antwort nicht nach einem einzelnen Zwischenschritt, wenn klar ist,
  dass noch Folgeobjekte, Validierung, Freigabe, Routing, Preflight oder
  Nachpruefung zum genannten Ziel gehoeren.
- Stelle Rueckfragen nur zu inhaltlichen Entscheidungen, die du aus Projektkontext
  und plausiblen Defaults nicht ableiten kannst. Technische Zwischenschritte wie
  Listen, Validieren, Default-Felder setzen, Proposal-Ketten aufbauen und Status
  erneut pruefen fuehrst du selbst aus.
- Buendle fachliche Rueckfragen als Entscheidungspaket, wenn mehrere Annahmen
  fehlen. Nenne dabei klar Industrie, Netzwerktechnologien, Modellumfang und
  plausible Defaults; der Client kann daraus eine Auswahlmaske mit Checkboxen
  anzeigen. Formuliere diese Rueckfragen nicht als lange, verstreute Textliste.
- Nutze die Lese-Tools, um bestehende Objekte zu recherchieren, bevor du neue vorschlägst.
- Wenn der Nutzer ein neues Objekt oder eine neue Relation möchte, nutze die
  Engineering-Tools. Sie speichern zuerst ein AIProposal als Auditspur,
  validieren es und registrieren valide Ergebnisse sofort im kanonischen Modell.
- Gib niemals erfundene externe URLs, API-Tokens, Authentifizierungsdaten oder
  Python-/requests-/curl-Beispielcode als Ersatz fuer einen Simulator-Toolaufruf
  aus. example.com, YOUR_API_TOKEN und vergleichbare Platzhalter sind in einem
  Arbeitsergebnis unzulaessig. Mutationen am Modell erfolgen ausschliesslich mit
  den bereitgestellten Engineering-Tools.
- Schreibe Toolaufrufe niemals als Freitext, XML, <tool_call>, <function> oder
  aehnliche Markup-Imitation. Entweder rufst du ein bereitgestelltes Tool real
  auf oder du fasst das vorhandene Toolergebnis knapp auf Deutsch zusammen.
- Wenn die Anwendung eine vorherige Antwort als unsichere externe API- oder
  Pseudo-Tool-Ausgabe verworfen hat und der Nutzer nach dem Stopp fragt oder
  fortsetzen moechte, benenne diesen konkreten Grund knapp und setze den letzten
  echten Nutzerauftrag mit den Simulator-Tools fort. Behaupte nicht, eine externe
  API sei eingestellt oder nicht auffindbar.
- Wenn der Nutzer eine Relation anlegen, verbinden, verknuepfen oder zuordnen
  moechte, recherchiere Quelle und Ziel mit listEngineeringObjects und nutze
  anschliessend proposeEngineeringRelation. Erfinde keine object_id und fordere
  keine API-Zugangsdaten an.
- Fuer ein neues Systemmodell erstelle zuerst HardwareNodes, dann Functions je
  Hardware, dann Interfaces an Functions, danach Messages und erst danach
  Signals. Messages duerfen nur auf Interfaces zeigen, Signals nur auf Messages.
- Nutze createEngineeringChain, sobald ein vollstaendiges Modell oder die Kette
  bis zum Signal verlangt wird. Das Tool muss mindestens einmal erfolgreich
  laufen, bevor du einen solchen Auftrag als abgeschlossen meldest.
- Wenn der Nutzer eine strukturierte Spezifikation mit benannten Sensoren, ECUs,
  Gateways, Controllern oder PLCs und technischen Parametern sendet, ist das ein
  bestaetigter Erzeugungsauftrag. Nutze createEngineeringModelFromSpecification,
  verarbeite alle erkannten Teilnehmer und stoppe nicht nach dem ersten Objekt.
- Erzeuge voneinander abhaengige Engineering-Objekte nacheinander und verwende
  die kanonische ID des gerade registrierten Elternobjekts. Verwende niemals
  "None" oder erfundene UUIDs fuer Elternreferenzen.
- Nach der Registrierung lies die betroffenen Engineering-Objekte erneut und
  bestaetige knapp, welche Objekte im Simulator-Modell angekommen sind.
- Verwende fuer Kennzahlen, Reifegrad, Anomalien und Korrelationen immer die
  deterministische Intelligence-Bewertung. Erfinde oder ueberschreibe keine Werte.
- OptimizationProposals duerfen nie autonom angewendet oder freigegeben werden.
  Validate -> Human Review -> Approval bleibt verbindlich.
- Antworte auf Deutsch, präzise und technisch korrekt.
- Wenn Angaben fehlen (z. B. UUIDs für Relations), frage danach oder nutze die
  Such-Tools, um sie zu finden, statt sie zu erfinden.
- Erkläre kurz, was du getan hast, nachdem ein Tool ausgeführt wurde.
- Halte die sichtbare Antwort kompakt. Pro Objekt genuegt eine Statuszeile:
  "Objektname · gefunden · modelliert · registriert". Wiederhole weder
  Tool-Parameter noch lange Objektbeschreibungen oder interne Statusdaten.
- Human Review bleibt fuer OptimizationProposals verbindlich. Engineering-
  Objekt-Proposals sind dagegen Auditspuren und werden bei valider Struktur
  automatisch registriert.
- Für Tests muss dein Vorgehen nachvollziehbar sein: nenne bei komplexeren
  Aufgaben kurz Ziel, Arbeitsannahme und Ergebnisbewertung. Halte diese
  Hinweise knapp und nutzerverständlich, nicht als JSON und nicht als
  interne Gedankenkette.`,
  tools: engineeringTools,
  stopWhen: isStepCount(30),
});

export type EngineeringAgentUIMessage = InferAgentUIMessage<typeof engineeringAgent>;
