import {
  createAgentUIStreamResponse,
  createUIMessageStream,
  createUIMessageStreamResponse,
  UIMessage,
} from "ai";
import {
  engineeringAgent,
  engineeringAgentModel,
  engineeringAgentOrchestrator,
  engineeringAgentProvider,
  registerEngineeringSpecification,
  registerRoutingProposalForSpecification,
  runEngineeringWorkflowAutomation,
  type EngineeringWorkflowAutomationEvent,
} from "@/lib/agent/engineering-agent";
import { appendAgentDiagnostic } from "@/lib/agent/agent-diagnostics-log";
import { AGENT_OUTPUT_RECOVERY_CONTEXT, inspectAgentText } from "@/lib/agent/agent-output-safety";
import {
  extractEngineeringSpecification,
  isEngineeringReviewRequest,
  isStructuredEngineeringSpecification,
} from "@/lib/agent/engineering-specification";
import {
  extractSignalBatchRequest,
  isBulkSignalCreationRequest,
  registerEngineeringSignalBatch,
} from "@/lib/agent/engineering-workload-batch";
import { runWithAgentProject, currentAgentProjectId, currentAgentRequestText } from "@/lib/agent/request-context";
import { runExclusiveProjectBuild } from "@/lib/agent/project-execution";
import { recordAgentFeedback } from "@/lib/agent/feedback-store";
import { uniqueMessagesById } from "@/lib/agent-message-history";
import type { AgentBuildProgress, AgentRunStatus } from "@/lib/agent-run-status";
import { inspectWorkflowState, saveWorkflowContext } from "@/lib/engineering-server-client";

export const maxDuration = 300;
const MAX_AGENT_CONTEXT_MESSAGES = 16;
const MAX_SCOPE_DEVIATION_CONTINUATIONS = 1;

function audit(message: string, details: Record<string, unknown> = {}) {
  const suffix = Object.entries(details)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" ");
  console.info(`[NetworkIS Agent] ${message}${suffix ? ` ${suffix}` : ""}`);
  void appendAgentDiagnostic("agent", {
    projectId: details.projectId ?? currentAgentProjectId(),
    runId: details.runId ?? details.requestId,
    step: details.step,
    event: message,
    details,
  }).catch((error) => {
    console.warn("[NetworkIS Agent] diagnostic log failed", error);
  });
}

function publicAgentError(error: unknown) {
  const detail = error instanceof Error ? error.message : String(error);
  if (/127\.0\.0\.1:11434|ollama/i.test(detail)) {
    return "Der lokale AI-Dienst ist nicht erreichbar. Der Launcher stellt ihn automatisch wieder her; bitte in wenigen Sekunden erneut versuchen.";
  }
  if (/database|psycopg|pooltimeout|15050/i.test(detail)) {
    return "Die Engineering-Datenbank ist gerade nicht erreichbar. Der Launcher versucht die Verbindung automatisch wiederherzustellen.";
  }
  if (/timeout|timed out/i.test(detail)) return "Die Agentenanfrage hat ihr Zeitlimit überschritten.";
  return "Der Agentenlauf ist technisch fehlgeschlagen. Der Fehler wurde für die Laufzeitdiagnose gespeichert.";
}

function uiMessageText(message: UIMessage | undefined) {
  if (!message) return "";
  const parts = Array.isArray(message.parts) ? message.parts : [];
  return parts
    .map((part) => {
      if (part && typeof part === "object" && "text" in part && typeof part.text === "string") return part.text;
      return "";
    })
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .slice(0, 180);
}

function uiMessageFullText(message: UIMessage | undefined) {
  if (!message) return "";
  return message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("\n");
}

function isCanComparisonQuestion(text: string) {
  const normalized = text.toLowerCase().replace(/[_-]+/g, " ");
  return /\bcan\b/.test(normalized)
    && /\bcan\s*fd\b/.test(normalized)
    && /\b(unterschied|vergleich|vs\.?|gegenüber|differen)/.test(normalized);
}

function createDeterministicTextResponse(messages: UIMessage[], text: string) {
  const stream = createUIMessageStream({
    originalMessages: messages,
    execute: async ({ writer }) => {
      const textId = crypto.randomUUID();
      writer.write({ type: "text-start", id: textId });
      writer.write({ type: "text-delta", id: textId, delta: text });
      writer.write({ type: "text-end", id: textId });
    },
  });
  return createUIMessageStreamResponse({ stream });
}

function createSignalBatchResponse(messages: UIMessage[], requestText: string) {
  const batch = extractSignalBatchRequest(requestText);
  const stream = createUIMessageStream({
    originalMessages: messages,
    onError: (error) => error instanceof Error ? error.message : "Der Signal-Batch konnte nicht ausgefuehrt werden.",
    execute: async ({ writer }) => {
      const toolCallId = crypto.randomUUID();
      writer.write({ type: "start-step" });
      writer.write({
        type: "tool-input-available",
        toolCallId,
        toolName: "createEngineeringSignalsBatch",
        input: { requested: batch?.total ?? 0, targets: batch?.targets ?? [] },
      });
      try {
        const result = await registerEngineeringSignalBatch(requestText);
        writer.write({ type: "tool-output-available", toolCallId, output: workflowStreamOutput(result) });
        const textId = crypto.randomUUID();
        writer.write({ type: "text-start", id: textId });
        writer.write({
          type: "text-delta",
          id: textId,
          delta: result.status === "READY_FOR_REVIEW"
            ? `${result.valid} von ${result.requested} Signalen sind valide und als Proposal zur menschlichen Pruefung bereit. Es wurde nichts automatisch freigegeben.`
            : `Workload ${result.workload_id}: ${result.valid} von ${result.requested} valid, ${result.missing} fehlen. Status ${result.status}.`,
        });
        writer.write({ type: "text-end", id: textId });
      } catch (error) {
        writer.write({
          type: "tool-output-error",
          toolCallId,
          errorText: error instanceof Error ? error.message : String(error),
        });
        throw error;
      } finally {
        writer.write({ type: "finish-step" });
      }
    },
  });
  return createUIMessageStreamResponse({ stream });
}

function canComparisonAnswer() {
  return [
    "CAN und CAN FD unterscheiden sich vor allem in drei Punkten:",
    "1. Payload: Klassisches CAN transportiert bis zu 8 Byte pro Frame, CAN FD bis zu 64 Byte.",
    "2. Bitrate: CAN verwendet eine gemeinsame Bitrate bis 1 Mbit/s. CAN FD behält die kompatible Arbitration-Phase und kann die Datenphase separat beschleunigen; im Simulator gelten 500 kbit/s für CAN und 2 Mbit/s für CAN FD als Defaults.",
    "3. Absicherung und Kompatibilität: CAN FD verwendet einen erweiterten CRC. FD-Controller verstehen klassische CAN-Frames; reine Classic-CAN-Knoten dürfen FD-Frames nur in entsprechend ausgelegten Netzen sehen.",
  ].join("\n");
}

function sanitizeAgentHistory(messages: UIMessage[]) {
  let blockedOutputs = 0;
  const uniqueMessages = uniqueMessagesById(messages);
  const recentMessages = uniqueMessages.slice(-MAX_AGENT_CONTEXT_MESSAGES);
  const firstUserIndex = recentMessages.findIndex((message) => message.role === "user");
  const contextMessages = firstUserIndex > 0 ? recentMessages.slice(firstUserIndex) : recentMessages;
  const sanitized = contextMessages.map((message) => {
    if (message.role !== "assistant") return message;
    return {
      ...message,
      parts: message.parts.map((part) => {
        if (part.type !== "text") return part;
        const safety = inspectAgentText(part.text);
        if (!safety.blocked) return part;
        blockedOutputs += 1;
        return { ...part, text: AGENT_OUTPUT_RECOVERY_CONTEXT };
      }),
    };
  });
  return {
    blockedOutputs,
    droppedMessages: uniqueMessages.length - contextMessages.length,
    duplicateMessages: messages.length - uniqueMessages.length,
    messages: sanitized,
  };
}

function specificationSummary(result: Awaited<ReturnType<typeof registerEngineeringSpecification>>) {
  const failures = Array.isArray(result.failures) ? result.failures.length : 0;
  const registered = Number(result.registered_chains ?? 0);
  const recognized = Number(result.recognized ?? 0);
  const targets = result.target_counts;
  const actual = result.actual_counts;
  const excess = result.excess_counts;
  const communication = result.communication_scope;
  const model = result.model_scope;
  const targetSummary = targets && actual
    ? `Soll/Ist: Sensoren ${targets.sensors}/${actual.sensors}, Aktoren ${targets.actuators}/${actual.actuators}, ECUs ${targets.ecus}/${actual.ecus}, Gateways ${targets.gateways}/${actual.gateways}.`
    : "";
  const excessSummary = excess && Object.values(excess).some((count) => Number(count) > 0)
    ? ` Ueberschritten: Sensoren +${excess.sensors}, Aktoren +${excess.actuators}, ECUs +${excess.ecus}, Gateways +${excess.gateways}.`
    : "";
  const communicationSummary = communication
    ? ` Kommunikation Soll/Ist: Interfaces ${communication.expected.interfaces}/${communication.actual.interfaces}, Nachrichten ${communication.expected.messages}/${communication.actual.messages}, Signale ${communication.expected.signals}/${communication.actual.signals}.`
    : "";
  const modelSummary = model
    ? ` Modell Soll/Ist: Funktionen ${model.expected.functions}/${model.actual.functions}, Hardware-Interfaces ${model.expected.hardware_interfaces}/${model.actual.hardware_interfaces}.`
    : "";
  const reviewProposals = Array.isArray(result.review_proposals) ? result.review_proposals.length : 0;
  const reviewSummary = reviewProposals > 0
    ? ` ${reviewProposals} Review-Proposal(s) fuer die Modellbereinigung vorbereitet.`
    : "";
  if (result.complete !== true) {
    const failureSummary = failures ? ` ${failures} Teilnehmer konnten nicht vollstaendig angelegt werden.` : "";
    return `${registered} von ${recognized} geplanten Teilnehmern wurden registriert. ${targetSummary}${excessSummary}${modelSummary}${communicationSummary}${reviewSummary}${failureSummary} Der Engineering-Auftrag bleibt offen.`;
  }
  return `${recognized} Teilnehmer geplant. ${registered} vollstaendige, klassengerechte Engineering-Teilnehmer wurden registriert. ${targetSummary}${modelSummary}${communicationSummary}`;
}

type ScopeCountKey = "sensors" | "actuators" | "ecus" | "gateways";

const SCOPE_COUNT_LABELS: Record<ScopeCountKey, string> = {
  sensors: "Sensoren",
  actuators: "Aktoren",
  ecus: "ECUs",
  gateways: "Gateways",
};

function countRecord(value: unknown): Partial<Record<ScopeCountKey, number>> {
  if (!value || typeof value !== "object") return {};
  const source = value as Record<string, unknown>;
  return Object.fromEntries(
    (Object.keys(SCOPE_COUNT_LABELS) as ScopeCountKey[]).map((key) => [
      key,
      Number.isFinite(Number(source[key])) ? Number(source[key]) : 0,
    ]),
  );
}

function scopeDeviationItems(result: Awaited<ReturnType<typeof registerEngineeringSpecification>>) {
  const targets = countRecord(result.target_counts);
  const actual = countRecord(result.actual_counts);
  return (Object.keys(SCOPE_COUNT_LABELS) as ScopeCountKey[]).flatMap((key) => {
    const target = targets[key] ?? 0;
    const current = actual[key] ?? 0;
    if (target === current) return [];
    return [{
      key,
      label: SCOPE_COUNT_LABELS[key],
      target,
      actual: current,
      missing: Math.max(0, target - current),
      excess: Math.max(0, current - target),
    }];
  });
}

function communicationDeviationItems(result: Awaited<ReturnType<typeof registerEngineeringSpecification>>) {
  const communication = result.communication_scope;
  if (!communication) return [];
  return (["interfaces", "messages", "signals"] as const).flatMap((key) => {
    const target = Number(communication.expected[key] ?? 0);
    const current = Number(communication.actual[key] ?? 0);
    if (target === current) return [];
    return [{
      key,
      label: key === "interfaces" ? "Interfaces" : key === "messages" ? "Nachrichten" : "Signale",
      target,
      actual: current,
      missing: Math.max(0, target - current),
      excess: Math.max(0, current - target),
    }];
  });
}

function modelDeviationItems(result: Awaited<ReturnType<typeof registerEngineeringSpecification>>) {
  const model = result.model_scope;
  if (!model) return [];
  return (["functions", "hardware_interfaces"] as const).flatMap((key) => {
    const target = Number(model.expected[key] ?? 0);
    const current = Number(model.actual[key] ?? 0);
    if (target === current) return [];
    return [{
      key,
      label: key === "functions" ? "Funktionen" : "Hardware-Interfaces",
      target,
      actual: current,
      missing: Math.max(0, target - current),
      excess: Math.max(0, current - target),
    }];
  });
}

function scopeDeviationSummary(result: Awaited<ReturnType<typeof registerEngineeringSpecification>>) {
  return [...scopeDeviationItems(result), ...modelDeviationItems(result), ...communicationDeviationItems(result)]
    .map((item) => `${item.label} ${item.actual}/${item.target}${item.missing ? `, ${item.missing} fehlen` : item.excess ? `, ${item.excess} zu viel` : ""}`)
    .join("; ");
}

function hasRegistrationFailures(result: Awaited<ReturnType<typeof registerEngineeringSpecification>>) {
  return Array.isArray(result.failures) && result.failures.length > 0;
}

function isExplicitScopeContinuationApproval(text: string) {
  return /\b(Fortsetzung-Freigabe|Auftrag fortsetzen|fehlende(?:n)? .*dokumentier|dokumentierte Abweichung|explizite Freigabe)\b/i.test(text);
}

const INLINE_IMPLEMENTATION_CONFIRMATION_PATTERN =
  /\b(?:passt|das passt|jetzt\s+(?:uebernehmen|übernehmen)|(?:uebernehmen|übernehmen)|anwenden|umsetzen|erstelle\s+(?:dies|das)|erzeuge\s+(?:dies|das)|lege\s+(?:dies|das)\s+an|leg\s+(?:dies|das)\s+an|mach\s+das)\b/i;

const DIRECT_ENGINEERING_MODEL_MUTATION_PATTERN =
  /(?:\b(?:lege|leg|erstelle|erstell\w*|erzeuge|generiere|registriere|anlegen|aufbauen)\b[\s\S]{0,160}(?:\b(?:hardware|knoten|konten|ecu|gateway|sensor|aktor|aktuator|funktion|schnittstelle|interface|signal)\b|[\p{L}\d_-]*(?:kamera|camera|radar|lidar)[\p{L}\d_-]*)|(?:\b(?:hardware|knoten|konten|ecu|gateway|sensor|aktor|aktuator|funktion|schnittstelle|interface|signal)\b|[\p{L}\d_-]*(?:kamera|camera|radar|lidar)[\p{L}\d_-]*)[\s\S]{0,120}\b(?:anlegen|erstellen|erzeugen|registrieren|aufbauen)\b)/iu;

function previousConcreteUserText(messages: UIMessage[]) {
  return [...messages]
    .reverse()
    .filter((message) => message.role === "user")
    .map((message) => uiMessageFullText(message).trim())
    .find((text) => text && !INLINE_IMPLEMENTATION_CONFIRMATION_PATTERN.test(text))
    ?? "";
}

function engineeringModelMutationText(requestText: string, messages: UIMessage[]) {
  const basis = INLINE_IMPLEMENTATION_CONFIRMATION_PATTERN.test(requestText)
    ? previousConcreteUserText(messages)
    : requestText;
  if (!DIRECT_ENGINEERING_MODEL_MUTATION_PATTERN.test(basis)) return null;
  const extracted = extractEngineeringSpecification(basis);
  return extracted.chains.length > 0 ? { text: basis, recognized: extracted.chains.length } : null;
}

function scopeContinuationAttempts(wizardStatus: Record<string, unknown>, runId: string) {
  const deviation = wizardStatus.scope_deviation;
  if (!deviation || typeof deviation !== "object") return 0;
  const record = deviation as Record<string, unknown>;
  if (String(record.run_id ?? "") !== runId) return 0;
  return Math.max(0, Math.floor(Number(record.continuations ?? 0) || 0));
}

function requestedWorkflowTarget(text: string) {
  const selectedSteps = [...text.matchAll(/Workflow\s+([1-9])\b/gi)]
    .map((match) => Number(match[1]))
    .filter(Number.isFinite);
  return selectedSteps.length ? Math.max(...selectedSteps) : 1;
}

function routingRequested(text: string) {
  return requestedWorkflowTarget(text) >= 2 || /Routing(?:-Vorschlag|vorschlag|-Tabelle)/i.test(text);
}

function routingSummary(result: Awaited<ReturnType<typeof registerRoutingProposalForSpecification>>) {
  const routingResult = result && typeof result === "object" ? result as Record<string, unknown> : {};
  if (routingResult.blocked === true) {
    return `Routing konnte nicht vorbereitet werden: ${String(routingResult.reason ?? "Voraussetzungen fehlen.")}`;
  }
  const failures = Array.isArray(routingResult.failures) ? routingResult.failures : [];
  if (failures.length) {
    const first = failures[0] as { reason?: string };
    return `Routing ist unvollständig: ${failures.length} Pfade fehlgeschlagen. ${first.reason ?? "Validierungsbefunde prüfen."}`;
  }
  if (routingResult.routing_table_populated === true) {
    const draftCount = Number(
      routingResult.draft_route_count ?? routingResult.accepted_route_count ?? routingResult.route_count ?? 0,
    );
    return `${draftCount} valide Pfade stehen jetzt als DRAFT-Routen in der Routing-Tabelle bereit und warten auf technische Prüfung und menschliche Freigabe.`;
  }
  if (routingResult.reused === true) {
    return `${Number(routingResult.proposal_count ?? 1)} passende Routing-Vorschläge waren bereits vorhanden und wurden wiederverwendet.`;
  }
  if (routingResult.ready_for_review === true) {
    return `${Number(routingResult.proposal_count ?? 1)} Routing-Vorschläge mit ${Number(routingResult.route_count ?? 0)} Pfaden sind technisch valide und warten am Human-Review-Gate.`;
  }
  return "Der Routing-Vorschlag wurde erzeugt; Validierungsbefunde bleiben für die Prüfung sichtbar.";
}

const AUTOMATIC_WORKFLOW_TARGETS = [
  "engineering_model",
  "routing",
  "network_editor",
  "parameters",
  "capacity_timing",
  "validation",
  "simulation",
  "results_analysis",
  "data_science_intelligence",
] as const;
type AutomaticWorkflowTarget = typeof AUTOMATIC_WORKFLOW_TARGETS[number];

function isAutomaticWorkflowTarget(value: unknown): value is AutomaticWorkflowTarget {
  return typeof value === "string" && AUTOMATIC_WORKFLOW_TARGETS.includes(value as AutomaticWorkflowTarget);
}

function automaticWorkflowTargetFromRequest(text: string): AutomaticWorkflowTarget | null {
  if (!/\b(setze|fahre|arbeite|baue|erzeuge|erstelle|fuehre|führe|starte)\b/i.test(text)) return null;
  if (!/\b(fort|weiter|workflow|bis|vollstaendig|vollständig|komplett)\b/i.test(text)) return null;
  const numbered = [...text.matchAll(/Workflow\s+([3-9])\b/gi)]
    .map((match) => Number(match[1]))
    .filter(Number.isFinite);
  const numberedTarget = numbered.length ? Math.max(...numbered) : 0;
  if (numberedTarget >= 9 || /\b(intelligence|assess)\b/i.test(text)) return "data_science_intelligence";
  if (numberedTarget >= 8 || /\b(results?|ergebnisanalyse)\b/i.test(text)) return "results_analysis";
  if (numberedTarget >= 7 || /\b(simulation|simulieren)\b/i.test(text)) return "simulation";
  if (numberedTarget >= 6 || /\b(preflight|validation|validierung)\b/i.test(text)) return "validation";
  if (numberedTarget >= 5 || /\b(capacity|timing)\b/i.test(text)) return "capacity_timing";
  if (numberedTarget >= 4 || /\b(parameter)\b/i.test(text)) return "parameters";
  if (numberedTarget >= 3 || /\b(netzwerk(?:-editor)?|topologie)\b/i.test(text)) return "network_editor";
  return null;
}

const MAX_WORKFLOW_STREAM_BYTES = 12_000;
const LOCAL_BACKEND_BASE = "http://127.0.0.1:15050/api/engineering";

function compactWorkflowStreamValue(value: unknown, depth = 0): unknown {
  if (typeof value === "string") {
    return value.length > 2_000 ? `${value.slice(0, 2_000)}...` : value;
  }
  if (value == null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    const sampleLimit = depth === 0 ? 8 : depth === 1 ? 5 : 3;
    const sample = value.slice(0, sampleLimit).map((item) => compactWorkflowStreamValue(item, depth + 1));
    return value.length > sampleLimit ? { count: value.length, sample } : sample;
  }

  const entries = Object.entries(value as Record<string, unknown>);
  if (depth >= 3) {
    const scalarEntries = entries
      .filter(([, item]) => item == null || typeof item !== "object")
      .slice(0, 18);
    const nestedFields = entries
      .filter(([, item]) => item != null && typeof item === "object")
      .map(([key]) => key);
    return {
      ...Object.fromEntries(scalarEntries.map(([key, item]) => [key, compactWorkflowStreamValue(item, depth + 1)])),
      ...(nestedFields.length ? { data_fields: nestedFields } : {}),
    };
  }

  return Object.fromEntries(
    entries.map(([key, item]) => [key, compactWorkflowStreamValue(item, depth + 1)]),
  );
}

function workflowStreamOutput(output: unknown) {
  try {
    if (JSON.stringify(output).length <= MAX_WORKFLOW_STREAM_BYTES) return output;
  } catch {
    // Non-serializable values are normalized by the compact projection below.
  }
  return compactWorkflowStreamValue(output);
}

function isIntelligenceIssueDiagnostic(text: string) {
  return text.includes("Befund-Code:") && text.includes("Objekt:") && text.includes("Erkannte Ursache:");
}

function promptField(text: string, label: string) {
  const match = text.match(new RegExp(`^${label}:\\s*(.+)$`, "mi"));
  return match?.[1]?.trim() ?? "";
}

function recordValue(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return value == null ? "" : String(value);
}

function buildIssueDiagnosticText(issue: Record<string, unknown>, fallback: Record<string, string>) {
  const code = recordValue(issue, "code") || fallback.code;
  const objectType = recordValue(issue, "object_type") || fallback.objectType;
  const objectId = recordValue(issue, "object_id") || fallback.objectId;
  const problem = recordValue(issue, "problem") || fallback.problem;
  const cause = recordValue(issue, "detected_cause") || fallback.cause;
  const recommendation = recordValue(issue, "recommendation") || fallback.recommendation;
  const affected = Array.isArray(issue.affected_objects) ? issue.affected_objects.length : 0;

  return [
    `Analyse für ${code}: ${problem}`,
    "",
    `Bedeutung: Der ${objectType} ist im Modell vorhanden, aber in der aktuellen Topologie fehlt ein belastbarer physischer Netzwerkpfad. Ursache: ${cause}`,
    "",
    "Wahrscheinliche Entstehung:",
    "- Hardware, Funktionen, Interfaces, Messages und Signale wurden angelegt, aber die physische Topologie wurde nicht vollständig mitgezogen.",
    "- Ein Netzwerk-/Port-/Gateway-Link fehlt oder wurde nachträglich nicht synchronisiert.",
    "- Der Knoten ist absichtlich isoliert, wurde aber nicht als bewusste Ausnahme modelliert.",
    "",
    "Nächste Schritte:",
    `- ${recommendation}`,
    "- Den Knoten im Netzwerk-Editor mit dem passenden Bus, Switch, Gateway oder Peer verbinden und die Interface-Zuordnung prüfen.",
    "- Danach Routing, Capacity/Timing, Validation und Intelligence neu bewerten, damit der Befund verschwindet oder als bewusst isoliert dokumentiert ist.",
    affected > 0
      ? `- Zusätzlich ${affected} betroffene abhängige Objekte prüfen.`
      : "- Keine Folgeobjekte erkannt; die Lücke liegt am Knoten selbst.",
  ].join("\n");
}

function issueDiagnosticActions(issue: Record<string, unknown>, fallback: Record<string, string>) {
  const code = recordValue(issue, "code") || fallback.code;
  const objectType = recordValue(issue, "object_type") || fallback.objectType;
  const objectId = recordValue(issue, "object_id") || fallback.objectId;
  const problem = recordValue(issue, "problem") || fallback.problem;
  const cause = recordValue(issue, "detected_cause") || fallback.cause;
  const recommendation = recordValue(issue, "recommendation") || fallback.recommendation;
  const severity = recordValue(issue, "severity") || "WARNING";
  const category = recordValue(issue, "category") || "Network";
  const evidence = Array.isArray(issue.evidence) ? issue.evidence.filter((item) => item && typeof item === "object") : [];
  const affectedObjects = Array.isArray(issue.affected_objects) && issue.affected_objects.length
    ? issue.affected_objects.map(String)
    : [objectId].filter(Boolean);

  return [
    {
      id: "open-network",
      label: "Netzwerk öffnen",
      kind: "navigate",
      href: "/studio?mode=network",
    },
    {
      id: "show-graph",
      label: "Graph anzeigen",
      kind: "navigate",
      href: `/studio/engineering?graph=${encodeURIComponent(objectId)}`,
    },
    {
      id: "create-proposal",
      label: "Proposal anlegen",
      kind: "create_optimization_proposal",
      proposal: {
        candidate_id: `REC-${code}-${objectId.slice(0, 8)}`,
        category,
        problem,
        affected_objects: affectedObjects,
        recommendation,
        expected_impact: {
          risk_reduction: severity === "ERROR" ? "HIGH" : "MEDIUM",
          requires_revalidation: true,
          detected_cause: cause,
        },
        evidence,
        graph_context: [{ object_type: objectType, object_id: objectId }],
        rag_context: [],
        confidence: evidence.length ? 0.9 : 0.75,
        priority: severity === "ERROR" ? 85 : 60,
        priority_factors: { severity, isolated_node: true },
        implementation_effort: "MEDIUM",
        status: "CANDIDATE",
        governance: "Validate -> Human Review -> Approval",
      },
    },
  ];
}

async function createIntelligenceIssueDiagnosticResponse(messages: UIMessage[], requestText: string, projectId: string) {
  const stream = createUIMessageStream({
    originalMessages: messages,
    onError: (error) => error instanceof Error ? error.message : "Der Intelligence-Befund konnte nicht diagnostiziert werden.",
    execute: async ({ writer }) => {
      const code = promptField(requestText, "Befund-Code");
      const objectLine = promptField(requestText, "Objekt");
      const [objectType, ...objectParts] = objectLine.split(/\s+/).filter(Boolean);
      const objectId = objectParts.join(" ");
      const fallback = {
        code,
        objectType,
        objectId,
        problem: promptField(requestText, "Problem"),
        cause: promptField(requestText, "Erkannte Ursache"),
        recommendation: promptField(requestText, "Empfehlung der deterministischen Analyse"),
      };
      const toolCallId = crypto.randomUUID();
      writer.write({ type: "start-step" });
      writer.write({
        type: "tool-input-available",
        toolCallId,
        toolName: "inspect_intelligence",
        input: { code, object_id: objectId },
      });
      let issue: Record<string, unknown> = {};
      try {
        const response = await fetch(`${LOCAL_BACKEND_BASE}/intelligence`, {
          headers: { "Content-Type": "application/json", "X-Project-ID": projectId },
          cache: "no-store",
          signal: AbortSignal.timeout(10000),
        });
        const snapshot = await response.json().catch(() => ({})) as Record<string, unknown>;
        if (!response.ok) throw new Error(recordValue(snapshot, "error") || `Workflow-Fehler ${response.status}`);
        const results = (snapshot.results ?? {}) as Record<string, unknown>;
        const issues = Array.isArray(results.critical_issues) ? results.critical_issues : [];
        issue = issues.find((item): item is Record<string, unknown> =>
          Boolean(item)
          && typeof item === "object"
          && recordValue(item as Record<string, unknown>, "code") === code
          && recordValue(item as Record<string, unknown>, "object_id") === objectId,
        ) ?? {};
        writer.write({
          type: "tool-output-available",
          toolCallId,
          output: workflowStreamOutput({
            snapshot_id: snapshot.id,
            matched: Boolean(Object.keys(issue).length),
            issue: Object.keys(issue).length ? issue : fallback,
            action_suggestions: issueDiagnosticActions(
              Object.keys(issue).length ? issue : fallback,
              fallback,
            ),
          }),
        });
      } catch (error) {
        writer.write({
          type: "tool-output-error",
          toolCallId,
          errorText: error instanceof Error ? error.message : String(error),
        });
        issue = fallback;
      } finally {
        writer.write({ type: "finish-step" });
      }
      const textId = crypto.randomUUID();
      writer.write({ type: "text-start", id: textId });
      writer.write({ type: "text-delta", id: textId, delta: buildIssueDiagnosticText(issue, fallback) });
      writer.write({ type: "text-end", id: textId });
    },
  });
  return createUIMessageStreamResponse({ stream });
}

function createWorkflowAutomationResponse(messages: UIMessage[], target: AutomaticWorkflowTarget) {
  const stream = createUIMessageStream({
    originalMessages: messages,
    onError: (error) => error instanceof Error ? error.message : "Der automatische Workflow konnte nicht ausgeführt werden.",
    execute: async ({ writer }) => runExclusiveProjectBuild(currentAgentProjectId(), async () => {
      const workflow = await inspectWorkflowState();
      const context = (workflow.context ?? {}) as Record<string, unknown>;
      const wizard = (context.agent_wizard_status ?? {}) as Record<string, unknown>;
      const runId = currentAgentRequestText().match(/Lauf-ID:\s*([\w-]+)/)?.[1] ?? String(wizard.run_id ?? "");
      let currentStep: AgentBuildProgress["step"] = "network_editor";
      let state: AgentRunStatus["state"] = "RUNNING";
      let statusMessage = "Der freigegebene Workflow wird fortgesetzt.";
      let statusWrite: Promise<unknown> = Promise.resolve();
      const persistRun = () => {
        const next: AgentRunStatus = { run_id: runId, step: currentStep, state, message: statusMessage,
          completed: state === "COMPLETED" ? 1 : 0, total: 1, updated_at: new Date().toISOString() };
        statusWrite = statusWrite.catch(() => undefined).then(() => runId ? saveWorkflowContext({ agent_execution: next }) : undefined);
        return statusWrite;
      };
      await persistRun();
      const heartbeat = setInterval(() => { void persistRun().catch((error) => audit("workflow heartbeat failed", { runId, error: String(error) })); }, 30_000);
      let activeToolCallId = "";
      const writeEvent = (event: EngineeringWorkflowAutomationEvent) => {
        audit("workflow step", { runId, ...event, output: undefined });
        currentStep = event.step as AgentBuildProgress["step"];
        statusMessage = event.phase === "error" ? event.error ?? "Workflow-Schritt fehlgeschlagen."
          : `${event.step}: ${event.phase === "start" ? "wird ausgefuehrt" : "abgeschlossen"}.`;
        void persistRun().catch((error) => audit("workflow status failed", { runId, error: String(error) }));
        if (event.phase === "start") {
          activeToolCallId = crypto.randomUUID();
          writer.write({ type: "start-step" });
          writer.write({
            type: "tool-input-available",
            toolCallId: activeToolCallId,
            toolName: event.toolName,
            input: { workflow_step: event.step },
          });
          return;
        }
        if (event.phase === "complete") {
          writer.write({
            type: "tool-output-available",
            toolCallId: activeToolCallId,
            output: workflowStreamOutput(event.output),
          });
        } else {
          writer.write({
            type: "tool-output-error",
            toolCallId: activeToolCallId,
            errorText: event.error ?? "Workflow-Schritt fehlgeschlagen.",
          });
        }
        writer.write({ type: "finish-step" });
        activeToolCallId = "";
      };

      try {
        const result = await runEngineeringWorkflowAutomation(target, writeEvent);
        const textId = crypto.randomUUID();
        const summary = result.complete
          ? `Automatischer Build abgeschlossen: ${result.completedSteps.length} Folgeschritte wurden ausgeführt; der Zielstatus ${target} ist erreicht.`
          : `Automatische Fortsetzung bei ${result.blockedStep ?? "Workflow"} gestoppt: ${result.reason ?? "Der nächste Schritt benötigt eine technische Entscheidung."}`;
        clearInterval(heartbeat);
        state = result.complete ? "COMPLETED" : "BLOCKED";
        if (result.blockedStep) currentStep = result.blockedStep as AgentBuildProgress["step"];
        statusMessage = summary;
        await persistRun();
        writer.write({ type: "text-start", id: textId });
        writer.write({ type: "text-delta", id: textId, delta: summary });
        writer.write({ type: "text-end", id: textId });
      } catch (error) {
        clearInterval(heartbeat);
        state = "BLOCKED";
        statusMessage = error instanceof Error ? error.message : String(error);
        await persistRun().catch(() => undefined);
        throw error;
      } finally { clearInterval(heartbeat); }
    }),
  });
  return createUIMessageStreamResponse({ stream });
}

class WizardRunCanceledError extends Error {
  constructor() {
    super("Der Engineering-Auftrag wurde abgebrochen. Es werden keine weiteren Modellobjekte geschrieben.");
    this.name = "WizardRunCanceledError";
  }
}

async function ensureWizardRunActive(runId: string) {
  if (!runId) return;
  const workflow = await inspectWorkflowState();
  const context = workflow && typeof workflow === "object"
    ? (workflow.context as Record<string, unknown> | undefined) ?? {}
    : {};
  const execution = context.agent_execution && typeof context.agent_execution === "object"
    ? context.agent_execution as Record<string, unknown>
    : {};
  const wizard = context.agent_wizard_status && typeof context.agent_wizard_status === "object"
    ? context.agent_wizard_status as Record<string, unknown>
    : {};
  const executionCanceled = String(execution.run_id ?? "") === runId && String(execution.state ?? "") === "CANCELED";
  const wizardCanceled = String(wizard.run_id ?? "") === runId && String(wizard.status ?? "") === "CANCELED";
  if (executionCanceled || wizardCanceled) throw new WizardRunCanceledError();
}

function createSpecificationResponse(messages: UIMessage[], specificationText: string) {
  const runId = specificationText.match(/- Lauf-ID:\s*([^\s]+)/)?.[1] ?? "";
  const stream = createUIMessageStream({
    originalMessages: messages,
    onError: (error) => error instanceof Error ? error.message : "Die Spezifikation konnte nicht verarbeitet werden.",
    execute: async ({ writer }) => runExclusiveProjectBuild(currentAgentProjectId(), async () => {
      let reviewGateReached = false;
      let engineeringModelComplete = false;
      const toolCallId = crypto.randomUUID();
      let activeToolCallId = toolCallId;
      let progress: AgentBuildProgress = { step: "engineering_model", completed: 0, total: 0 };
      let statusWrite: Promise<unknown> = Promise.resolve();
      let runningMessage = "Engineering-Modell wird geprüft und aufgebaut.";
      let heartbeat: ReturnType<typeof setInterval> | undefined;
      const persistRun = (state: AgentRunStatus["state"], message: string) => {
        audit("specification build status", { runId, state, ...progress, message });
        if (state === "RUNNING") runningMessage = message;
        const next: AgentRunStatus = { ...progress, run_id: runId, state, message, updated_at: new Date().toISOString() };
        // Serialize heartbeats and final results so a late heartbeat cannot replace the outcome.
        statusWrite = statusWrite.catch(() => undefined).then(async () => {
          if (!runId) return undefined;
          if (state === "RUNNING") await ensureWizardRunActive(runId);
          return saveWorkflowContext({ agent_execution: next });
        });
        return statusWrite;
      };
      const reportProgress = async (next: AgentBuildProgress) => {
        progress = next;
        await persistRun("RUNNING", next.step === "engineering_model"
          ? `${next.completed} von ${next.total} Engineering-Ketten registriert.`
          : `${next.completed} von ${next.total} Routing-Pfaden vorbereitet.`);
      };
      writer.write({ type: "start-step" });
      writer.write({
        type: "tool-input-available",
        toolCallId,
        toolName: "createEngineeringModelFromSpecification",
        input: {},
      });
      try {
        const workflowBefore = await inspectWorkflowState().catch(() => null);
        const wizardStatus = workflowBefore && typeof workflowBefore === "object"
          ? ((workflowBefore.context as Record<string, unknown> | undefined)?.agent_wizard_status as Record<string, unknown> | undefined) ?? {}
          : {};
        const approvedScopeContinuation = isExplicitScopeContinuationApproval(specificationText);
        const previousScopeContinuations = scopeContinuationAttempts(wizardStatus, runId);
        await persistRun("RUNNING", runningMessage);
        heartbeat = setInterval(() => {
          void persistRun("RUNNING", runningMessage).catch((error) => audit("build heartbeat failed", { runId, error: String(error) }));
        }, 30_000);
        const result = await registerEngineeringSpecification(specificationText, reportProgress, () => ensureWizardRunActive(runId));
        engineeringModelComplete = result.complete === true;
        writer.write({ type: "tool-output-available", toolCallId, output: workflowStreamOutput(result) });
        let summary = specificationSummary(result);
        const deviationItems = scopeDeviationItems(result);
        const communicationDeviations = communicationDeviationItems(result);
        const modelDeviations = modelDeviationItems(result);
        const deviationSummary = scopeDeviationSummary(result);
        const reviewProposalCount = Array.isArray(result.review_proposals) ? result.review_proposals.length : 0;
        const communicationReviewGate =
          !engineeringModelComplete
          && Number(result.registered_chains ?? 0) === Number(result.recognized ?? 0)
          && deviationItems.length === 0
          && (communicationDeviations.length > 0 || modelDeviations.length > 0)
          && reviewProposalCount > 0
          && !hasRegistrationFailures(result);
        const scopeContinuationAllowed = !engineeringModelComplete
          && approvedScopeContinuation
          && deviationItems.length > 0
          && !hasRegistrationFailures(result)
          && previousScopeContinuations < MAX_SCOPE_DEVIATION_CONTINUATIONS;
        if (communicationReviewGate) {
          const workflowBeforeContext = wizardStatus && typeof wizardStatus === "object" ? wizardStatus : {};
          await saveWorkflowContext({
            active_workflow_step: "routing",
            agent_wizard_status: {
              ...workflowBeforeContext,
              communication_review: {
                run_id: runId,
                ready_for_review: true,
                created_at: new Date().toISOString(),
                deviations: [...modelDeviations, ...communicationDeviations],
                proposals: reviewProposalCount,
                summary: deviationSummary,
                decision: "Kommunikationsabweichung als Review-Proposal vorbereitet; Folgeschritte duerfen weiterlaufen.",
              },
            },
          }).catch((error) => audit("communication review persistence failed", { runId, error: String(error) }));
          summary += ` Kommunikations-Review-Gate vorbereitet: ${deviationSummary}. Die Folgeschritte laufen weiter; die Bereinigung bleibt als Proposal zur Freigabe sichtbar.`;
        }
        if (scopeContinuationAllowed) {
          const nextContinuations = previousScopeContinuations + 1;
          await saveWorkflowContext({
            agent_wizard_status: {
              ...wizardStatus,
              scope_deviation: {
                run_id: runId,
                approved: true,
                approved_at: new Date().toISOString(),
                continuations: nextContinuations,
                max_continuations: MAX_SCOPE_DEVIATION_CONTINUATIONS,
                deviations: deviationItems,
                summary: deviationSummary,
                decision: "Fortsetzung mit dokumentierter Soll/Ist-Abweichung",
              },
            },
          }).catch((error) => audit("scope deviation persistence failed", { runId, error: String(error) }));
          summary += ` Fortsetzung nach Freigabe: Die Scope-Abweichung (${deviationSummary}) wurde dokumentiert; der Auftrag laeuft ohne weitere automatische Wiederholung weiter.`;
        } else if (!engineeringModelComplete && approvedScopeContinuation && deviationItems.length > 0 && !hasRegistrationFailures(result)) {
          summary += ` Keine weitere automatische Fortsetzung: Die dokumentierte Scope-Abweichung (${deviationSummary}) wurde fuer diese Lauf-ID bereits freigegeben. Damit wird eine Endlosschleife verhindert.`;
        }
        const engineeringModelUsable = engineeringModelComplete || scopeContinuationAllowed || communicationReviewGate;

        if (engineeringModelUsable && routingRequested(specificationText) && Number(result.registered_chains ?? 0) >= 2) {
          const routingToolCallId = crypto.randomUUID();
          activeToolCallId = routingToolCallId;
          writer.write({
            type: "tool-input-available",
            toolCallId: routingToolCallId,
            toolName: "create_route_proposal",
            input: {},
          });
          const routing = await registerRoutingProposalForSpecification(specificationText, reportProgress, () => ensureWizardRunActive(runId));
          writer.write({ type: "tool-output-available", toolCallId: routingToolCallId, output: workflowStreamOutput(routing) });
          summary += ` ${routingSummary(routing)}`;
          reviewGateReached = Boolean(
            routing
            && typeof routing === "object"
            && "ready_for_review" in routing
            && routing.ready_for_review === true,
          );
          if (reviewGateReached && requestedWorkflowTarget(specificationText) >= 3) {
            const routingTablePopulated = routing
              && typeof routing === "object"
              && "routing_table_populated" in routing
              && routing.routing_table_populated === true;
            summary += routingTablePopulated
              ? " Prüfe die DRAFT-Routen unter Routing → Table. Die ausgewählten Folgeschritte starten erst nach ihrer menschlichen Freigabe."
              : " Bitte bestätige zuerst die Vorschläge unter Routing → AI Proposals. Die ausgewählten Folgeschritte starten erst nach dieser menschlichen Freigabe.";
          }
        }

        clearInterval(heartbeat);
        await persistRun(!engineeringModelUsable ? "BLOCKED"
          : reviewGateReached ? "REVIEW_REQUIRED"
            : routingRequested(specificationText) ? "BLOCKED" : "COMPLETED", summary);

        const textId = crypto.randomUUID();
        writer.write({ type: "text-start", id: textId });
        writer.write({ type: "text-delta", id: textId, delta: summary });
        writer.write({ type: "text-end", id: textId });
      } catch (error) {
        clearInterval(heartbeat);
        const errorText = error instanceof Error ? error.message : String(error);
        const terminalState = error instanceof WizardRunCanceledError ? "CANCELED" : "BLOCKED";
        await persistRun(terminalState, errorText).catch((statusError) => {
          audit("build status persistence failed", { runId, error: String(statusError) });
        });
        writer.write({ type: "tool-output-error", toolCallId: activeToolCallId, errorText });
        throw error;
      } finally {
        clearInterval(heartbeat);
        writer.write({ type: "finish-step" });
      }

    }),
  });
  return createUIMessageStreamResponse({ stream });
}

export async function POST(request: Request) {
  let payload: { messages?: UIMessage[]; workflowTarget?: string };
  try {
    payload = await request.json();
  } catch {
    audit("request rejected", { reason: "invalid-json" });
    return Response.json({ error: "Ein gültiger JSON-Body wird erwartet." }, { status: 400 });
  }
  if (!Array.isArray(payload.messages) || payload.messages.length === 0) {
    audit("request rejected", { reason: "missing-messages" });
    return Response.json({ error: "Mindestens eine Nachricht wird erwartet." }, { status: 400 });
  }

  const requestId = crypto.randomUUID();
  const projectId = request.headers.get("X-Project-ID") ?? "default";
  const sanitizedHistory = sanitizeAgentHistory(payload.messages);
  const lastUserMessage = [...payload.messages].reverse().find((message) => message.role === "user");
  const requestText = uiMessageFullText(lastUserMessage);
  const reviewRequested = isEngineeringReviewRequest(requestText);
  const structuredSpecification = isStructuredEngineeringSpecification(requestText);
  const deterministicEngineeringMutation = !reviewRequested && !structuredSpecification
    ? engineeringModelMutationText(requestText, payload.messages)
    : null;
  const automaticTarget = !reviewRequested && !structuredSpecification
    ? isAutomaticWorkflowTarget(payload.workflowTarget)
      ? payload.workflowTarget
      : automaticWorkflowTargetFromRequest(requestText)
    : null;
  audit("request started", {
    requestId,
    projectId,
    provider: engineeringAgentProvider,
    model: engineeringAgentModel,
    orchestrator: engineeringAgentOrchestrator,
    messages: payload.messages.length,
    contextMessages: sanitizedHistory.messages.length,
    droppedMessages: sanitizedHistory.droppedMessages,
    duplicateMessages: sanitizedHistory.duplicateMessages,
    blockedOutputs: sanitizedHistory.blockedOutputs,
    prompt: uiMessageText(lastUserMessage),
  });

  if (isIntelligenceIssueDiagnostic(requestText)) {
    audit("intelligence issue diagnostic started", { requestId, projectId });
    return runWithAgentProject(
      request.headers.get("X-Project-ID"),
      () => createIntelligenceIssueDiagnosticResponse(sanitizedHistory.messages, requestText, projectId),
      requestText,
    );
  }

  if (!reviewRequested && !structuredSpecification && isCanComparisonQuestion(requestText)) {
    audit("deterministic protocol answer", { requestId, projectId, topic: "CAN-vs-CAN-FD" });
    return createDeterministicTextResponse(sanitizedHistory.messages, canComparisonAnswer());
  }

  if (!reviewRequested && !structuredSpecification && isBulkSignalCreationRequest(requestText)) {
    const batch = extractSignalBatchRequest(requestText);
    audit("deterministic signal batch started", {
      requestId,
      projectId,
      requested: batch?.total,
      targets: batch?.targets.map((target) => `${target.domain}:${target.count}`).join(","),
    });
    return runWithAgentProject(
      request.headers.get("X-Project-ID"),
      () => createSignalBatchResponse(sanitizedHistory.messages, requestText),
      requestText,
    );
  }

  if (deterministicEngineeringMutation) {
    audit("deterministic engineering mutation started", {
      requestId,
      projectId,
      recognized: deterministicEngineeringMutation.recognized,
      confirmation: deterministicEngineeringMutation.text !== requestText,
    });
    return runWithAgentProject(
      request.headers.get("X-Project-ID"),
      () => createSpecificationResponse(sanitizedHistory.messages, deterministicEngineeringMutation.text),
      deterministicEngineeringMutation.text,
    );
  }

  if (automaticTarget) {
    audit("deterministic workflow execution started", { requestId, projectId, target: automaticTarget });
    return runWithAgentProject(
      request.headers.get("X-Project-ID"),
      () => createWorkflowAutomationResponse(sanitizedHistory.messages, automaticTarget),
      requestText,
    );
  }

  if (engineeringAgentProvider === "unconfigured") {
    audit("request failed", { requestId, reason: "missing-api-key" });
    return Response.json(
      {
        error:
          "Der Engineering-Agent ist nicht konfiguriert. Setze AI_PROVIDER auf local, openai oder nvidia und konfiguriere den gewählten Provider.",
      },
      { status: 503 },
    );
  }

  if (structuredSpecification) {
    audit("structured specification execution started", { requestId, projectId });
    return runWithAgentProject(
      request.headers.get("X-Project-ID"),
      () => createSpecificationResponse(sanitizedHistory.messages, requestText),
      requestText,
    );
  }

  return runWithAgentProject(request.headers.get("X-Project-ID"), () =>
    createAgentUIStreamResponse({
      agent: engineeringAgent,
      uiMessages: sanitizedHistory.messages,
      onError: (error) => {
        const errorText = error instanceof Error ? error.message : String(error);
        audit("request failed", { requestId, projectId, error: errorText });
        void recordAgentFeedback({
          projectId,
          prompt: requestText,
          rating: "failed",
          error: errorText,
        }).catch((feedbackError) => {
          audit("failure feedback write failed", {
            requestId,
            error: feedbackError instanceof Error ? feedbackError.message : String(feedbackError),
          });
        });
        return publicAgentError(error);
      },
      onStepEnd: (step) => {
        audit("step finished", {
          requestId,
          finishReason: step.finishReason,
          toolCalls: step.toolCalls.length,
          toolResults: step.toolResults.length,
        });
      },
    }), requestText,
  );
}
