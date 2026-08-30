import {
  createAgentUIStreamResponse,
  createUIMessageStream,
  createUIMessageStreamResponse,
  toUIMessageStream,
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
import { AGENT_OUTPUT_RECOVERY_CONTEXT, inspectAgentText } from "@/lib/agent/agent-output-safety";
import { isStructuredEngineeringSpecification } from "@/lib/agent/engineering-specification";
import {
  extractSignalBatchRequest,
  isBulkSignalCreationRequest,
  registerEngineeringSignalBatch,
} from "@/lib/agent/engineering-workload-batch";
import { runWithAgentProject } from "@/lib/agent/request-context";
import { recordAgentFeedback } from "@/lib/agent/feedback-store";
import { uniqueMessagesById } from "@/lib/agent-message-history";

export const maxDuration = 300;
const MAX_AGENT_CONTEXT_MESSAGES = 16;

function audit(message: string, details: Record<string, unknown> = {}) {
  const suffix = Object.entries(details)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" ");
  console.info(`[NetworkIS Agent] ${message}${suffix ? ` ${suffix}` : ""}`);
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
  const targetSummary = targets && actual
    ? `Soll/Ist: Sensoren ${targets.sensors}/${actual.sensors}, ECUs ${targets.ecus}/${actual.ecus}, Gateways ${targets.gateways}/${actual.gateways}.`
    : "";
  const excessSummary = excess && Object.values(excess).some((count) => Number(count) > 0)
    ? ` Ueberschritten: Sensoren +${excess.sensors}, ECUs +${excess.ecus}, Gateways +${excess.gateways}.`
    : "";
  if (result.complete !== true) {
    const failureSummary = failures ? ` ${failures} Teilnehmer konnten nicht vollstaendig angelegt werden.` : "";
    return `${registered} von ${recognized} geplanten Teilnehmern wurden registriert. ${targetSummary}${excessSummary}${failureSummary} Der Engineering-Auftrag bleibt offen; Folgeschritte werden nicht gestartet.`;
  }
  return `${recognized} Teilnehmer geplant. ${registered} vollstaendige Engineering-Ketten mit Hardware, Funktion, Interface, Nachricht und Signal wurden registriert. ${targetSummary}`;
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

function continuationPrompt(text: string) {
  const selectedSteps = text.match(/Workflow\s+[3-9][^;\n]*/gi) ?? [];
  return [
    "Setze den bereits begonnenen und bestaetigten Wizard-Auftrag jetzt fort.",
    "Engineering-Modell und Routing-Vorschlag wurden deterministisch mit kanonischen IDs vorbereitet.",
    `Führe die verbleibenden ausgewählten Workflow-Schritte selbstständig aus: ${selectedSteps.join("; ")}.`,
    "Verwende ausschließlich die Simulator-Tools und stoppe nur an einem echten Human-Review-Gate oder bei einem klar benannten Blocker.",
  ].join("\n");
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
    execute: async ({ writer }) => {
      let activeToolCallId = "";
      const writeEvent = (event: EngineeringWorkflowAutomationEvent) => {
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

      const result = await runEngineeringWorkflowAutomation(target, writeEvent);
      const textId = crypto.randomUUID();
      const summary = result.complete
        ? `Automatischer Build abgeschlossen: ${result.completedSteps.length} Folgeschritte wurden ausgeführt; der Zielstatus ${target} ist erreicht.`
        : `Automatische Fortsetzung bei ${result.blockedStep ?? "Workflow"} gestoppt: ${result.reason ?? "Der nächste Schritt benötigt eine technische Entscheidung."}`;
      writer.write({ type: "text-start", id: textId });
      writer.write({ type: "text-delta", id: textId, delta: summary });
      writer.write({ type: "text-end", id: textId });
    },
  });
  return createUIMessageStreamResponse({ stream });
}

function createSpecificationResponse(messages: UIMessage[], specificationText: string) {
  const stream = createUIMessageStream({
    originalMessages: messages,
    onError: (error) => error instanceof Error ? error.message : "Die Spezifikation konnte nicht verarbeitet werden.",
    execute: async ({ writer }) => {
      let reviewGateReached = false;
      let engineeringModelComplete = false;
      const toolCallId = crypto.randomUUID();
      writer.write({ type: "start-step" });
      writer.write({
        type: "tool-input-available",
        toolCallId,
        toolName: "createEngineeringModelFromSpecification",
        input: {},
      });
      try {
        const result = await registerEngineeringSpecification(specificationText);
        engineeringModelComplete = result.complete === true;
        writer.write({ type: "tool-output-available", toolCallId, output: result });
        let summary = specificationSummary(result);

        if (engineeringModelComplete && routingRequested(specificationText) && Number(result.registered_chains ?? 0) >= 2) {
          const routingToolCallId = crypto.randomUUID();
          writer.write({
            type: "tool-input-available",
            toolCallId: routingToolCallId,
            toolName: "create_route_proposal",
            input: {},
          });
          const routing = await registerRoutingProposalForSpecification(specificationText);
          writer.write({ type: "tool-output-available", toolCallId: routingToolCallId, output: routing });
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

        const textId = crypto.randomUUID();
        writer.write({ type: "text-start", id: textId });
        writer.write({ type: "text-delta", id: textId, delta: summary });
        writer.write({ type: "text-end", id: textId });
      } catch (error) {
        const errorText = error instanceof Error ? error.message : String(error);
        writer.write({ type: "tool-output-error", toolCallId, errorText });
        throw error;
      } finally {
        writer.write({ type: "finish-step" });
      }

      if (requestedWorkflowTarget(specificationText) >= 3 && engineeringModelComplete && !reviewGateReached) {
        const continuation = await engineeringAgent.stream({ prompt: continuationPrompt(specificationText) });
        writer.merge(toUIMessageStream({ stream: continuation.stream }));
      }
    },
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
  const structuredSpecification = isStructuredEngineeringSpecification(requestText);
  const automaticTarget = !structuredSpecification
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

  if (!structuredSpecification && isCanComparisonQuestion(requestText)) {
    audit("deterministic protocol answer", { requestId, projectId, topic: "CAN-vs-CAN-FD" });
    return createDeterministicTextResponse(sanitizedHistory.messages, canComparisonAnswer());
  }

  if (!structuredSpecification && isBulkSignalCreationRequest(requestText)) {
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
