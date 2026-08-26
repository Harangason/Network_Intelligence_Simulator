import "server-only";

import { createOpenAI } from "@ai-sdk/openai";
import { ToolLoopAgent, InferAgentUIMessage, isStepCount, tool } from "ai";
import { z } from "zod";
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
    tools: ["listEngineeringObjects", "proposeEngineeringObject", "listEngineeringRelations", "proposeEngineeringRelation", "inspectEngineeringProposals", "validateEngineeringProposal", "approveEngineeringProposal", "approveAllValidEngineeringProposals"],
    doneWhen: "Alle fuer das Ziel benoetigten Objekte existieren im kanonischen Modell oder liegen valide am Review-Gate.",
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
  return normalized.slice(markerIndex);
}

function inferWorkflowTarget(request: string) {
  const normalized = concreteRequestText(request);
  const matches = Object.entries(WORKFLOW_TARGET_ALIASES)
    .filter(([alias]) => normalized.includes(alias))
    .map(([, stepId]) => stepId)
    .sort((left, right) => WORKFLOW_STEP_ORDER.indexOf(right) - WORKFLOW_STEP_ORDER.indexOf(left));
  return matches[0] ?? "engineering_model";
}

function usableApiKey(value: string | undefined): value is string {
  return Boolean(value && !/^(DEIN|YOUR|PLACEHOLDER|CHANGEME)/i.test(value.trim()));
}

const openAIKey = process.env.OPENAI_API_KEY;
const nvidiaKey = process.env.NVIDIA_API_KEY;
const engineeringModel = usableApiKey(openAIKey)
  ? createOpenAI({ apiKey: openAIKey })("gpt-4.1")
  : createOpenAI({
      apiKey: nvidiaKey,
      baseURL: "https://integrate.api.nvidia.com/v1",
      name: "nvidia-nim",
    }).chat(process.env.NVIDIA_AI_MODEL ?? "nvidia/nemotron-3-nano-30b-a3b");

export const engineeringAgentProvider = usableApiKey(openAIKey)
  ? "openai"
  : usableApiKey(nvidiaKey)
    ? "nvidia-nim"
    : "unconfigured";

function auditAgent(message: string, details: Record<string, unknown> = {}) {
  const suffix = Object.entries(details)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" ");
  console.info(`[NetworkIS Agent] ${message}${suffix ? ` ${suffix}` : ""}`);
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
    "Erzeuge einen getrennt gespeicherten AIProposal für ein neues Engineering-Objekt. " +
    "Das freigegebene Modell bleibt unverändert, bis ein Mensch den Vorschlag geprüft hat.",
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
  }),
  execute: async (input) => {
    const { resource, ...rest } = input;
    const payload: Record<string, unknown> = {
      name: rest.name,
      description: rest.description ?? null,
      domain: rest.domain ?? null,
      source: "ai_generated",
      review_state: "unreviewed",
      approval_state: "pending",
      provenance: { agent: "engineering-chat-agent", reason: "user-requested proposal" },
    };
    if (resource === "hardware-nodes") payload.device_type = rest.device_type ?? "GenericDevice";
    if (resource === "interfaces") {
      payload.interface_type = rest.interface_type ?? "Other";
      payload.hardware_node_id = rest.hardware_node_id ?? null;
      payload.function_id = rest.function_id ?? null;
    }
    if (resource === "functions") payload.hardware_node_id = rest.hardware_node_id ?? null;
    if (resource === "messages") {
      payload.interface_id = rest.interface_id ?? null;
      payload.direction = rest.direction ?? "tx";
    }
    if (resource === "signals") payload.message_id = rest.message_id ?? null;

    const proposal = await createProposal({
      proposal_type: "OBJECT",
      target_object: { resource },
      prompt: `Erzeuge ${resource}: ${rest.name}`,
      model: "openai/gpt-4.1",
      proposed_objects: [payload],
      evidence: [],
      retrieved_context: [],
      validation_results: [],
      created_by: "engineering-chat-agent",
    });
    return {
      created: false,
      resource,
      proposal,
      note: "Vorschlag wurde getrennt vom freigegebenen Engineering-Modell gespeichert und muss geprüft werden.",
    };
  },
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
    "Schlage eine neue Relation zwischen zwei Engineering-Objekten vor (z. B. " +
    "HardwareNode HAS_INTERFACE Interface, oder Message CONTAINS_SIGNAL Signal).",
  inputSchema: z.object({
    source_type: z.enum(OBJECT_TYPE_ENUM),
    source_id: z.string(),
    target_type: z.enum(OBJECT_TYPE_ENUM),
    target_id: z.string(),
    relation_type: z.string().describe("z. B. HAS_INTERFACE, CONNECTED_TO, CONTAINS_SIGNAL, COMMUNICATES_WITH."),
  }),
  execute: async (input) => {
    const proposal = await createProposal({
      proposal_type: "RELATION",
      target_object: { source_type: input.source_type, source_id: input.source_id },
      prompt: `Erzeuge Relation ${input.relation_type}`,
      model: "openai/gpt-4.1",
      proposed_objects: [{ object_type: "Relation", ...input }],
      evidence: [],
      retrieved_context: [],
      validation_results: [],
      created_by: "engineering-chat-agent",
    });
    return { created: false, proposal };
  },
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

const createRouteProposal = tool({
  description:
    "Erzeugt einen getrennten RoutingProposal anhand von Topologie, Nodes, Interfaces, Message und Signal-Selektion. " +
    "Aktiviert oder genehmigt niemals Routen.",
  inputSchema: z.object({
    prompt: z.string(),
    source_node_id: z.string(),
    destination_node_ids: z.array(z.string()).min(1),
    message_id: z.string().optional(),
    signal_ids: z.array(z.string()).optional(),
    routing_type: z.string().optional(),
  }),
  execute: async (input) => generateRoutingProposal({ ...input, actor: "engineering-chat-agent" }),
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

export const engineeringAgent = new ToolLoopAgent({
  model: engineeringModel,
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
  Wenn Human Review blockiert, bleibst du nicht still stehen: validiere offene
  Proposals, fordere einmal klar Allow an und setze nach Allow mit der Folge fort.
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
- Wenn eine Aufgabe wegen Human Review nicht vollstaendig bis ins kanonische
  Modell geschrieben werden darf, erstelle trotzdem alle notwendigen Proposals
  bis zum naechsten Review-Gate und benenne genau, was danach noch freigegeben
  werden muss.
- Nutze die Lese-Tools, um bestehende Objekte zu recherchieren, bevor du neue vorschlägst.
- Wenn der Nutzer ein neues Objekt oder eine neue Relation möchte, nutze die
  "propose"-Tools. Sie speichern Ergebnisse IMMER getrennt als AIProposal.
  Das freigegebene Engineering-Modell wird dadurch nicht verändert.
- Fuer ein neues Systemmodell erstelle zuerst HardwareNodes, dann Functions je
  Hardware, dann Interfaces an Functions, danach Messages und erst danach
  Signals. Messages duerfen nur auf Interfaces zeigen, Signals nur auf Messages.
- Wenn der Nutzer danach ausdruecklich bestaetigt, z. B. mit "Allow",
  "bestaetigt", "ja", "freigeben" oder "uebernehmen", validiere die offenen
  Engineering-Proposals und nutze die approve-Tools. Nur dann werden valide
  Vorschlaege als echte Simulator-Objekte oder Relations angelegt.
- Nach einer Freigabe lies die betroffenen Engineering-Objekte erneut und
  bestaetige knapp, welche Objekte im Simulator-Modell angekommen sind.
- Verwende fuer Kennzahlen, Reifegrad, Anomalien und Korrelationen immer die
  deterministische Intelligence-Bewertung. Erfinde oder ueberschreibe keine Werte.
- OptimizationProposals duerfen nie autonom angewendet oder freigegeben werden.
  Validate -> Human Review -> Approval bleibt verbindlich.
- Antworte auf Deutsch, präzise und technisch korrekt.
- Wenn Angaben fehlen (z. B. UUIDs für Relations), frage danach oder nutze die
  Such-Tools, um sie zu finden, statt sie zu erfinden.
- Erkläre kurz, was du getan hast, nachdem ein Tool ausgeführt wurde.
- Für Tests muss dein Vorgehen nachvollziehbar sein: nenne bei komplexeren
  Aufgaben kurz Ziel, Arbeitsannahme und Ergebnisbewertung. Halte diese
  Hinweise knapp und nutzerverständlich, nicht als JSON und nicht als
  interne Gedankenkette.`,
  tools: {
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
  },
  stopWhen: isStepCount(30),
});

export type EngineeringAgentUIMessage = InferAgentUIMessage<typeof engineeringAgent>;
