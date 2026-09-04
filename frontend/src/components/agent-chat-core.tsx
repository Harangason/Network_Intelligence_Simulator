"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { FormEvent, KeyboardEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EngineeringAgentUIMessage } from "@/lib/agent/engineering-agent";
import { getCatalog } from "@/lib/api";
import {
  activateEngineeringAgentWizardSession,
  clearPendingEngineeringAgentTask,
  engineeringAgentWorkflowProgress,
  ENGINEERING_AGENT_PENDING_TASK_KEY,
  ENGINEERING_AGENT_TASK_EVENT,
  finishEngineeringAgentWizardSession,
  persistEngineeringAgentTask,
  readPendingEngineeringAgentTask,
  takePendingEngineeringAgentTask,
  updatePendingEngineeringAgentTask,
  type EngineeringAgentTask,
} from "@/lib/agent-task-events";
import {
  readEngineeringAgentHistory,
  saveEngineeringAgentHistory,
} from "@/lib/agent-chat-history";
import { uniqueMessagesById } from "@/lib/agent-message-history";
import { agentBuildProgressPercent, agentRunIsActive, readAgentRunStatus } from "@/lib/agent-run-status";
import { parameterProgressTarget, symbolicProgressAt } from "@/lib/wizard-progress";
import { extractEngineeringSpecification, type EngineeringHardwareCounts } from "@/lib/agent/engineering-specification";
import {
  buildEquipmentClusters,
  equipmentClusterSummary,
  type EquipmentClusterAssignment,
} from "@/lib/agent/equipment-clustering";
import { inspectAgentText } from "@/lib/agent/agent-output-safety";
import { publishEngineeringModelChanged } from "@/lib/engineering-events";
import { listAllEngineeringObjects } from "@/lib/engineering-api";
import { approveRoutes, listRoutes } from "@/lib/routing-api";
import { routingApprovalProgress } from "@/lib/routing-approval";
import type { EngineeringObject, EngineeringResource, RoutingEntry, Technology, TechnologyDomain } from "@/lib/types";
import { readActiveProjectId, withProjectParam } from "@/lib/user-settings";
import { topologyClusterKnowledgeSummary } from "@/lib/topology-cluster-knowledge";
import {
  cancelEngineeringWorkload,
  createOptimizationProposal,
  getWorkflowSummary,
  listEngineeringWorkloads,
  setWorkflowContext,
  type IntelligenceRecommendation,
  type WorkflowState,
  type WorkflowStatus,
  type WorkflowStepId,
} from "@/lib/workflow-api";
import { WORKFLOW_CHANGED_EVENT } from "./workflow-header";
import { AgentToolResult } from "./agent-tool-result";
import { WorkloadProgress } from "./workload-progress";

const EQUIPMENT_CATEGORIES = [
  { key: "gateways", label: "Gateways", type: "Gateway" },
  { key: "ecus", label: "ECUs", type: "ECU" },
  { key: "sensors", label: "Sensoren", type: "SensorController" },
  { key: "actuators", label: "Aktoren", type: "ActuatorController" },
] as const;

const WIZARD_STATUS_INDEX = 7;

function suggestedClusterBusName(label: string, index: number, needsNumber: boolean) {
  const cluster = label
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/gi, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_+/g, "_") || "System";
  return needsNumber ? `${cluster}_${String(index).padStart(2, "0")}` : cluster;
}

function agentHistoryRevision(messages: EngineeringAgentUIMessage[]) {
  const lastMessage = messages.at(-1);
  if (!lastMessage) return "empty";
  const parts = lastMessage.parts.map((part) => {
    if (part.type === "text") return `text:${part.text.length}:${part.text.slice(-48)}`;
    const toolPart = part as { state?: string; toolCallId?: string; output?: unknown };
    const outputLength = toolPart.output === undefined ? 0 : JSON.stringify(toolPart.output).length;
    return `${part.type}:${toolPart.state ?? ""}:${toolPart.toolCallId ?? ""}:${outputLength}`;
  }).join("|");
  return `${messages.length}:${lastMessage.id}:${lastMessage.role}:${parts}`;
}

export function AgentChatCore({
  compact = false,
  projectId,
  routingApprovalComplete = false,
}: {
  compact?: boolean;
  projectId?: string;
  routingApprovalComplete?: boolean;
}) {
  const activeProjectId = projectId?.trim() || readActiveProjectId();
  const transport = useMemo(
    () => new DefaultChatTransport({
      api: "/api/agent/chat",
      headers: () => ({ "X-Project-ID": activeProjectId }),
    }),
    [activeProjectId],
  );
  const { messages, sendMessage, setMessages, status, error, regenerate } = useChat<EngineeringAgentUIMessage>({
    id: `engineering-agent-${activeProjectId}`,
    transport,
  });
  const [input, setInput] = useState("");
  const [historyReady, setHistoryReady] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const publishedToolResultsRef = useRef(new Set<string>());
  const taskRunStartingRef = useRef(false);
  const activeAutomaticTaskRef = useRef<EngineeringAgentTask | null>(null);
  const previousStatusRef = useRef(status);
  const initialPendingProjectRef = useRef("");
  const continuationTimerRef = useRef<number | null>(null);
  const persistedHistoryRevisionRef = useRef("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!historyReady || !input.trim() || status !== "ready") return;
    const text = input.trim();
    if (isInlineConfirmation(text)) {
      if (confirmationRequest) {
        allowRequestedAction(text);
      } else {
        void sendMessage({ text: buildInlineConfirmationPrompt(text, stableMessages) });
      }
      setInput("");
      return;
    }
    sendMessage({ text });
    setInput("");
  }

  const busy = status === "submitted" || status === "streaming";
  const busyLabel = status === "submitted"
    ? "bereitet den Engineering-Auftrag vor …"
    : "führt Simulator-Schritte aus …";
  const stableMessages = useMemo(() => uniqueMessagesById(messages), [messages]);
  const activityEntries = useMemo(() => buildAgentActivity(stableMessages, busy, error?.message), [stableMessages, busy, error]);
  const detectedConfirmationRequest = useMemo(() => findPendingConfirmation(stableMessages), [stableMessages]);
  const latestAssistantMessageId = useMemo(
    () => [...stableMessages].reverse().find((message) => message.role === "assistant")?.id ?? "",
    [stableMessages],
  );
  const confirmationRequest = detectedConfirmationRequest?.routingReview && routingApprovalComplete
    ? null
    : detectedConfirmationRequest;

  const runTask = useCallback(async (task: EngineeringAgentTask) => {
    if (
      !historyReady
      || !task.text.trim()
      || status !== "ready"
      || taskRunStartingRef.current
      || activeAutomaticTaskRef.current !== null
      || (task.projectId && task.projectId !== activeProjectId)
    ) return;
    if (task.gate === "routing-approval" && !routingApprovalComplete) return;

    taskRunStartingRef.current = true;
    let runnableTask = task;
    try {
      if (task.workflowTarget) {
        const workflow = await getWorkflowSummary();
        if (workflow.context.agent_wizard_status) return;
        const progress = engineeringAgentWorkflowProgress(task, workflow.statuses, workflow.versions);
        if (progress.complete) {
          clearPendingEngineeringAgentTask(activeProjectId);
          return;
        }
        if (progress.blockedStep) {
          updatePendingEngineeringAgentTask({
            ...task,
            gate: undefined,
            paused: true,
            lastWorkflowSignature: progress.signature,
          });
          return;
        }
        if (task.paused && task.lastWorkflowSignature === progress.signature) return;
        runnableTask = updatePendingEngineeringAgentTask({
          ...task,
          gate: undefined,
          paused: false,
          lastWorkflowSignature: progress.signature,
          lastDispatchAt: Date.now(),
          noProgressRuns: task.paused ? 0 : task.noProgressRuns,
        }) ?? task;
        activeAutomaticTaskRef.current = runnableTask;
      } else {
        window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
      }

      await sendMessage(
        { text: runnableTask.text },
        runnableTask.workflowTarget
          ? { body: { workflowTarget: runnableTask.workflowTarget } }
          : undefined,
      );
    } catch (error) {
      if (activeAutomaticTaskRef.current === runnableTask) activeAutomaticTaskRef.current = null;
      throw error;
    } finally {
      taskRunStartingRef.current = false;
    }
  }, [activeProjectId, historyReady, routingApprovalComplete, sendMessage, status]);

  useEffect(() => {
    let active = true;
    setHistoryReady(false);
    initialPendingProjectRef.current = "";
    activeAutomaticTaskRef.current = null;
    void readEngineeringAgentHistory<EngineeringAgentUIMessage>(activeProjectId).then((storedMessages) => {
      if (!active) return;
      persistedHistoryRevisionRef.current = agentHistoryRevision(storedMessages);
      publishedToolResultsRef.current = historicalToolResultKeys(storedMessages);
      setMessages(storedMessages);
      setHistoryReady(true);
    });
    return () => {
      active = false;
    };
  }, [activeProjectId, setMessages]);

  useEffect(() => {
    if (!historyReady || status !== "ready") return;
    if (stableMessages.length !== messages.length) {
      setMessages(stableMessages);
      return;
    }
    const revision = agentHistoryRevision(stableMessages);
    if (revision === persistedHistoryRevisionRef.current) return;
    const timeout = window.setTimeout(() => {
      void saveEngineeringAgentHistory(activeProjectId, stableMessages).then((saved) => {
        if (saved) persistedHistoryRevisionRef.current = revision;
      });
    }, 800);
    return () => window.clearTimeout(timeout);
  }, [activeProjectId, historyReady, messages.length, setMessages, stableMessages, status]);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [stableMessages, busy]);

  useEffect(() => {
    stableMessages.forEach((message) => {
      message.parts.forEach((part, index) => {
        if (!part.type.startsWith("tool-")) return;
        const toolPart = part as { state: string; output?: unknown; toolCallId?: string };
        if (toolPart.state !== "output-available") return;
        const resultKey = toolPart.toolCallId ?? `${message.id}:${index}`;
        if (publishedToolResultsRef.current.has(resultKey)) return;
        publishedToolResultsRef.current.add(resultKey);
        for (const item of canonicalObjectsFromToolOutput(toolPart.output)) {
          publishEngineeringModelChanged(item);
        }
      });
    });
  }, [stableMessages]);

  useEffect(() => {
    const ask = (event: Event) => {
      const question = String((event as CustomEvent<string>).detail ?? "").trim();
      if (historyReady && question && status === "ready") void sendMessage({ text: question });
    };
    window.addEventListener("engineering-agent:ask", ask);
    return () => window.removeEventListener("engineering-agent:ask", ask);
  }, [historyReady, sendMessage, status]);

  useEffect(() => {
    const handleTask = (event: Event) => {
      void runTask((event as CustomEvent<EngineeringAgentTask>).detail);
    };
    window.addEventListener(ENGINEERING_AGENT_TASK_EVENT, handleTask);
    return () => window.removeEventListener(ENGINEERING_AGENT_TASK_EVENT, handleTask);
  }, [runTask]);

  useEffect(() => {
    if (!historyReady || status !== "ready" || initialPendingProjectRef.current === activeProjectId) return;
    initialPendingProjectRef.current = activeProjectId;
    const pending = takePendingEngineeringAgentTask();
    if (pending) void runTask(pending);
  }, [activeProjectId, historyReady, runTask, status]);

  useEffect(() => {
    const previousStatus = previousStatusRef.current;
    previousStatusRef.current = status;
    const automaticTask = activeAutomaticTaskRef.current;
    const runFinished = status === "ready" && (previousStatus === "submitted" || previousStatus === "streaming");
    if (!historyReady || !runFinished || !automaticTask?.workflowTarget) return;
    activeAutomaticTaskRef.current = null;

    let active = true;
    const continueWorkflow = async () => {
      const pending = readPendingEngineeringAgentTask(activeProjectId);
      if (!pending?.workflowTarget) return;
      const workflow = await getWorkflowSummary();
      if (!active) return;
      const progress = engineeringAgentWorkflowProgress(pending, workflow.statuses, workflow.versions);
      if (progress.complete) {
        clearPendingEngineeringAgentTask(activeProjectId);
        return;
      }
      if (progress.blockedStep) {
        updatePendingEngineeringAgentTask({
          ...pending,
          paused: true,
          lastWorkflowSignature: progress.signature,
        });
        return;
      }

      updatePendingEngineeringAgentTask({
        ...pending,
        paused: true,
        lastWorkflowSignature: progress.signature,
        noProgressRuns: (pending.noProgressRuns ?? 0) + 1,
      });
    };
    void continueWorkflow();
    return () => {
      active = false;
      if (continuationTimerRef.current !== null) {
        window.clearTimeout(continuationTimerRef.current);
        continuationTimerRef.current = null;
      }
    };
  }, [activeProjectId, historyReady, runTask, status]);

  useEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [input]);

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  function allowRequestedAction(confirmationText = "Bestätigt") {
    if (!historyReady || !confirmationRequest || status !== "ready") return;
    if (confirmationRequest.routingReview) {
      const originalRequest = latestUserRequestBefore(stableMessages, confirmationRequest.messageId);
      persistEngineeringAgentTask(
        [
          "Setze den bestaetigten Engineering-Wizard nach der menschlichen Routing-Freigabe fort.",
          originalRequest ? `Urspruenglicher Auftrag: ${originalRequest}` : "Der urspruengliche Auftrag ist in diesem Agentenverlauf dokumentiert.",
          "Der Auftrag ist am Routing-Freigabezaehler gesperrt. Fahre erst fort, wenn inspect_routing_table.approval_progress.complete true ist. Routing-Freigaben bleiben ausschliesslich beim Menschen.",
          "Pruefe zuerst den aktuellen Workflow- und Routing-Status. Erzeuge danach mit den Simulator-Tools Netzwerk, vollstaendige Parameter, Capacity/Timing, Preflight, eine echte Simulation, Results/Analysis und die abschliessende Intelligence-Bewertung. Beende erst, wenn jede Stufe einen belegten Status besitzt oder ein weiteres menschliches Review zwingend erforderlich ist.",
        ].join("\n\n"),
        "engineering-wizard",
        "routing-approval",
        activeProjectId,
        "data_science_intelligence",
      );
      window.location.assign(withProjectParam("/studio/routing", activeProjectId));
      return;
    }
    const originalRequest = latestUserRequestBefore(stableMessages, confirmationRequest.messageId);
    void sendMessage({
      text: confirmationRequest.recovery
        ? "Setze den zuletzt begonnenen Auftrag jetzt fort. Verwende ausschließlich die bereitgestellten Simulator-Tools und arbeite bis zu einem echten Ergebnis oder einem klar sichtbaren Review-Gate."
        : [
            `Bestaetigt durch Nutzereingabe: ${confirmationText}`,
            originalRequest ? `Urspruenglicher Auftrag: ${originalRequest}` : "Der urspruengliche Auftrag steht im bisherigen Agentenverlauf.",
            "Uebernimm den zuletzt vorgeschlagenen fachlichen Stand jetzt im aktuellen Projekt. Nutze echte Simulator-Tools fuer Engineering-Modell, Routing, Parameter oder Workflow, lies danach den aktuellen Zustand erneut und melde nur tatsaechlich registrierte oder klar am Review-Gate wartende Ergebnisse.",
            "Starte keinen neuen Task und gib keine reine Zustimmung aus.",
          ].join("\n\n"),
    });
  }

  return (
    <>
      <div className="eng-agent-thread" aria-live="polite" ref={threadRef}>
        {!historyReady && (
          <div className="empty-result" style={{ minHeight: compact ? 90 : 140 }}>
            <span className="spinner" />
            <strong>Verlauf wird geladen</strong>
          </div>
        )}

        {historyReady && stableMessages.length === 0 && (
          <div className="empty-result" style={{ minHeight: compact ? 90 : 140 }}>
            <span className="empty-icon">◇</span>
            <strong>Noch keine Nachricht</strong>
            <p>Frage nach Hardware, Interfaces, Signalen oder bitte um Vorschläge.</p>
          </div>
        )}

        {stableMessages.map((message) => (
          <div className={`eng-agent-message ${message.role}`} key={message.id}>
            <span aria-hidden="true" className="eng-agent-avatar">{message.role === "user" ? "DU" : "AI"}</span>
            <div className="eng-agent-message-content">
              <span className="eng-agent-role">{message.role === "user" ? "Du" : "Engineering-Agent"}</span>
              <div className="eng-agent-bubble">
                {message.parts.map((part, index) => (
                  <MessagePart
                    hideText={message.role === "assistant" && hasCompactEngineeringResult(message.parts)}
                    key={`${message.id}-${index}`}
                    part={part}
                    projectId={activeProjectId}
                    richText={message.role === "assistant"}
                  />
                ))}
              </div>
              {message.role === "assistant" && message.id === latestAssistantMessageId && textFromParts(message.parts).trim() && (
                <AgentFeedbackControls
                  messageId={message.id}
                  projectId={activeProjectId}
                  prompt={latestUserRequestBefore(stableMessages, message.id)}
                  response={textFromParts(message.parts).trim()}
                />
              )}
            </div>
          </div>
        ))}

        {busy && (
          <div className="eng-agent-message assistant">
            <span aria-hidden="true" className="eng-agent-avatar">AI</span>
            <div className="eng-agent-message-content">
              <span className="eng-agent-role">Engineering-Agent</span>
              <div className="eng-agent-bubble">
                <span className="spinner" /> {busyLabel}
              </div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="notice error">
          {agentErrorText(error.message)}{" "}
          <button className="button secondary tiny" onClick={() => regenerate()} type="button">
            Erneut versuchen
          </button>
        </div>
      )}

      {activityEntries.length > 0 && <AgentActivityLog entries={activityEntries} />}

      {confirmationRequest && (
        <div className="eng-agent-approval">
          <div>
            <strong>Bestätigung erforderlich</strong>
            <span>
              {confirmationRequest.proposalCount > 0
                ? confirmationRequest.routingReview
                  ? confirmationRequest.routingDrafts
                    ? `${confirmationRequest.proposalCount} DRAFT-${confirmationRequest.proposalCount === 1 ? "Route wartet" : "Routen warten"} in der Routing-Tabelle auf Validierung und Freigabe.`
                    : `${confirmationRequest.proposalCount} Routing-${confirmationRequest.proposalCount === 1 ? "Vorschlag wartet" : "Vorschläge warten"} am Review-Gate auf deine Prüfung.`
                  : `${confirmationRequest.proposalCount} ${confirmationRequest.proposalCount === 1 ? "Objekt wartet" : "Objekte warten"} am Review-Gate auf Freigabe.`
                : confirmationRequest.recovery
                  ? "Die letzte Agent-Ausgabe wurde verworfen. Der ursprüngliche Auftrag ist noch offen und kann kontrolliert mit Simulator-Tools fortgesetzt werden."
                : "Der Agent wartet auf deine Freigabe für den vorgeschlagenen nächsten Schritt."}
            </span>
          </div>
          <button className="button primary" disabled={!historyReady || busy} onClick={() => allowRequestedAction()} type="button">
            {confirmationRequest.routingReview ? "Routing öffnen" : confirmationRequest.recovery ? "Fortsetzen" : "Allow"}
          </button>
        </div>
      )}

      <form className="eng-agent-form" onSubmit={submit}>
        <textarea
          aria-label="Nachricht an den Engineering-Assistenten"
          disabled={!historyReady || busy}
          onKeyDown={handleInputKeyDown}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Frage den Engineering-Assistenten …"
          ref={inputRef}
          rows={1}
          value={input}
        />
        <button className="button primary" disabled={!historyReady || busy || !input.trim()} type="submit">
          Senden
        </button>
      </form>
    </>
  );
}

type AgentActivityEntry = {
  id: string;
  kind: "request" | "goal" | "assumption" | "tool" | "decision" | "answer" | "status" | "error";
  title: string;
  detail: string;
};

type TaskAttachment = {
  name: string;
  size: number;
  kind: string;
  content?: string;
  previewDataUrl?: string;
  source: "task" | "architecture";
  analysisHint: string;
};

const MAX_TASK_ATTACHMENTS = 8;
const SUPPORTED_EVIDENCE_ACCEPT = [
  ".txt",
  ".md",
  ".csv",
  ".json",
  ".svg",
  ".pdf",
  ".doc",
  ".docx",
  ".ppt",
  ".pptx",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".gif",
  ".bmp",
  "text/*",
  "image/*",
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.ms-powerpoint",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
].join(",");

type ChoiceGroup = {
  id: string;
  label: string;
  multi: boolean;
  options: Array<{ id: string; label: string; detail: string; value: string }>;
};

const STATIC_INDUSTRY_DOMAINS: TechnologyDomain[] = [
  { id: "automotive", label: "Automotive", technologies: [] },
  { id: "industrial_automation", label: "Industrial Automation", technologies: [] },
  { id: "aerospace", label: "Aerospace", technologies: [] },
  { id: "iot", label: "IoT & Sensor Networks", technologies: [] },
  { id: "telecom", label: "Telecommunication", technologies: [] },
  { id: "energy", label: "Energy & Smart Grid", technologies: [] },
  { id: "robotics", label: "Robotics", technologies: [] },
  { id: "medical", label: "Medical Devices", technologies: [] },
];

const SCOPE_GROUP: ChoiceGroup = {
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

const PROCESS_GROUP: ChoiceGroup = {
    id: "process",
    label: "Arbeitsweise",
    multi: true,
    options: [
      { id: "defaults", label: "Leere Felder füllen", detail: "Technikabhängige Defaults verwenden.", value: "Leere Pflichtfelder mit technologieabhängigen Defaults füllen" },
      { id: "review_gate", label: "Bis Review-Gate arbeiten", detail: "Alle nötigen Proposals erzeugen und validieren.", value: "Selbstständig bis zum Human-Review-Gate arbeiten" },
      { id: "approve_after_allow", label: "Nach Allow übernehmen", detail: "Valide Vorschläge nach Freigabe ins Modell schreiben.", value: "Nach Allow valide Vorschläge übernehmen" },
    ],
};

type NetworkArchitectureId = "sensor_ecu_actuator" | "eva" | "ecu_gateway" | "gateway_ecu_segments" | "gateway_direct" | "hybrid_ai";

type NetworkArchitectureOption = {
  id: NetworkArchitectureId;
  label: string;
  detail: string;
  diagram: string;
  rules: string;
};

const NETWORK_ARCHITECTURES: NetworkArchitectureOption[] = [
  {
    id: "sensor_ecu_actuator",
    label: "Variante 0 · Sensor-ECU-Aktor",
    detail: "Lokaler Regelkreis ohne Gateway/BCM-Pfad: Sensoren liefern an die ECU, die ECU steuert Aktoren.",
    diagram: "Sensor -> ECU -> Aktor",
    rules: "Lokale Funktionskette: Sensoren und Aktoren werden fachlich an die zuständige ECU gebunden. Es werden keine Gateway-/BCM-Verbindungen und keine direkten Sensor-/Aktor-Netzpfade angelegt.",
  },
  {
    id: "eva",
    label: "Variante 1 · Einfaches EVA",
    detail: "Eingabe, Verarbeitung und Ausgabe bleiben je System fachlich zusammengefasst.",
    diagram: "Sensor/Aktor → ECU → Gateway",
    rules: "EVA je Systemrahmen: Sensoren und Eingaben zur ECU, ECU-Verarbeitung zu Aktoren und Ausgaben; die Gateway-Anbindung vermittelt nur die Systemkommunikation.",
  },
  {
    id: "ecu_gateway",
    label: "Variante 2 · ECU-vermittelt",
    detail: "Sensoren und Aktoren hängen an der ECU; die ECU kommuniziert mit Gateway oder BCM.",
    diagram: "Sensor ─┐\n        ├─ ECU ─ Gateway / BCM\nAktor ──┘",
    rules: "Sensoren und Aktoren werden ihrer fachlich zuständigen ECU zugeordnet; ausschließlich die ECU bindet den Systemrahmen an Gateway oder BCM an.",
  },
  {
    id: "gateway_direct",
    label: "Variante 3 · Gateway-direkt",
    detail: "Sensoren, ECUs und Aktoren erhalten jeweils eine direkte Gateway- oder BCM-Anbindung.",
    diagram: "Sensor ─────┐\nECU ────────┼─ Gateway / BCM\nAktor ──────┘",
    rules: "Sensoren, ECUs und Aktoren werden als eigenständige Teilnehmer direkt an Gateway oder BCM angebunden.",
  },
  {
    id: "gateway_ecu_segments",
    label: "Variante 4 · Gateway-Segmente",
    detail: "Ein Gateway-Segment bündelt bis zu 6 ECUs; Sensoren und Aktoren bleiben an der fachlichen ECU.",
    diagram: "Sensor/Aktor -> ECU 1 --\\\nSensor/Aktor -> ECU 2 --- Gateway / BCM\n... bis ECU 6 ----/",
    rules: "Segmentierte Gateway-Backbone-Architektur: Sensoren und Aktoren werden fachlich an ECUs geführt; pro Gateway-Leitung werden bis zu 6 ECUs als Bussegment gebündelt. Das Gateway kennt die ECU-Segmente, legt aber keine Sensor-/Aktor-Direktanbindungen an.",
  },
  {
    id: "hybrid_ai",
    label: "KI-Kombination · Variante 2 + 3",
    detail: "Die KI entscheidet je Teilnehmer zwischen lokaler ECU-Zuordnung und direkter Gateway-Anbindung.",
    diagram: "lokal → ECU ─┐\n              ├─ Gateway / BCM\ndirekt ───────┘",
    rules: "Kombination aus Variante 2 und 3: lokale, echtzeit- oder regelungskritische Teilnehmer über die fachliche ECU; systemweite, zentrale oder hochbandbreitige Teilnehmer direkt über Gateway oder BCM.",
  },
];

function architectureOption(id: NetworkArchitectureId | "") {
  return NETWORK_ARCHITECTURES.find((option) => option.id === id);
}

type AgentWizardContext = {
  agent_prompt?: string;
  attachments: Array<{ kind: string; name: string; size: number; source?: "task" | "architecture" }>;
  confirmed_at: string;
  industry: string;
  mode: "full" | "can";
  network_architecture?: {
    ai_proposal: string;
    approved: true;
    approved_at: string;
    id: NetworkArchitectureId;
    label: string;
    rules: string;
  };
  notes: string;
  parameters: string;
  process: string[];
  project_id: string;
  run_id: string;
  scope: string[];
  scope_ids: string[];
  task: string;
  technologies: string[];
  communication_system_counts?: Array<{ id: string; label: string; recognized: number; count: number }>;
  planned_network_connections?: number;
  system_cluster_assignments?: EquipmentClusterAssignment[];
  topology_cluster_knowledge?: {
    profile: string;
    ruleSummary: string[];
    lessonSummary: string[];
  };
};

function restoredWizardContext(value: unknown, projectId: string): AgentWizardContext | null {
  if (!value || typeof value !== "object") return null;
  const context = value as Record<string, unknown>;
  if (String(context.project_id ?? "") !== projectId || !String(context.run_id ?? "").trim()) return null;
  const strings = (key: string) => Array.isArray(context[key])
    ? (context[key] as unknown[]).filter((item): item is string => typeof item === "string")
    : [];
  const attachments = Array.isArray(context.attachments)
    ? context.attachments.filter((item): item is AgentWizardContext["attachments"][number] => (
      Boolean(item)
      && typeof item === "object"
      && typeof (item as Record<string, unknown>).kind === "string"
      && typeof (item as Record<string, unknown>).name === "string"
      && typeof (item as Record<string, unknown>).size === "number"
    ))
    : [];
  const rawArchitecture = context.network_architecture && typeof context.network_architecture === "object"
    ? context.network_architecture as Record<string, unknown>
    : null;
  const architectureId = rawArchitecture && NETWORK_ARCHITECTURES.some((option) => option.id === rawArchitecture.id)
    ? rawArchitecture.id as NetworkArchitectureId
    : null;
  return {
    agent_prompt: typeof context.agent_prompt === "string" ? context.agent_prompt : undefined,
    attachments,
    confirmed_at: String(context.confirmed_at ?? ""),
    industry: String(context.industry ?? "Aus Projektkontext ableiten"),
    mode: context.mode === "can" ? "can" : "full",
    network_architecture: architectureId && rawArchitecture?.approved === true ? {
      ai_proposal: String(rawArchitecture.ai_proposal ?? ""),
      approved: true,
      approved_at: String(rawArchitecture.approved_at ?? ""),
      id: architectureId,
      label: String(rawArchitecture.label ?? architectureOption(architectureId)?.label ?? architectureId),
      rules: String(rawArchitecture.rules ?? architectureOption(architectureId)?.rules ?? ""),
    } : undefined,
    notes: String(context.notes ?? ""),
    parameters: String(context.parameters ?? "Technologie-Defaults verwenden"),
    process: strings("process"),
    project_id: projectId,
    run_id: String(context.run_id),
    scope: strings("scope"),
    scope_ids: strings("scope_ids"),
    task: String(context.task ?? "Engineering-Auftrag"),
    technologies: strings("technologies"),
    communication_system_counts: Array.isArray(context.communication_system_counts)
      ? context.communication_system_counts
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        .map((item) => ({
          id: String(item.id ?? ""),
          label: String(item.label ?? item.id ?? ""),
          recognized: Number(item.recognized ?? 0),
          count: Number(item.count ?? 0),
        }))
        .filter((item) => item.id && item.label && Number.isFinite(item.count))
      : undefined,
    planned_network_connections: Number.isFinite(Number(context.planned_network_connections))
      ? Number(context.planned_network_connections)
      : undefined,
    system_cluster_assignments: Array.isArray(context.system_cluster_assignments)
      ? context.system_cluster_assignments
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        .map((item) => ({
          cluster_id: String(item.cluster_id ?? ""),
          label: String(item.label ?? ""),
          selected: item.selected !== false,
          network_id: String(item.network_id ?? ""),
          network_label: String(item.network_label ?? item.network_id ?? ""),
          bus_name: String(item.bus_name ?? ""),
          devices: Number(item.devices ?? 0),
          counts: item.counts && typeof item.counts === "object" ? item.counts as Record<string, number> : {},
          evidence: Array.isArray(item.evidence) ? item.evidence.filter((value): value is string => typeof value === "string") : [],
        }))
        .filter((item) => item.cluster_id && item.label)
      : undefined,
    topology_cluster_knowledge: context.topology_cluster_knowledge && typeof context.topology_cluster_knowledge === "object"
      ? {
        profile: String((context.topology_cluster_knowledge as Record<string, unknown>).profile ?? "generic"),
        ruleSummary: Array.isArray((context.topology_cluster_knowledge as Record<string, unknown>).ruleSummary)
          ? ((context.topology_cluster_knowledge as Record<string, unknown>).ruleSummary as unknown[]).filter((item): item is string => typeof item === "string")
          : [],
        lessonSummary: Array.isArray((context.topology_cluster_knowledge as Record<string, unknown>).lessonSummary)
          ? ((context.topology_cluster_knowledge as Record<string, unknown>).lessonSummary as unknown[]).filter((item): item is string => typeof item === "string")
          : [],
      }
      : undefined,
  };
}

const WIZARD_CONTEXT_STORAGE_PREFIX = "networkis:engineering-wizard-status:";

function takeLegacyWizardContext(projectId: string) {
  if (typeof window === "undefined") return null;
  try {
    const storageKey = `${WIZARD_CONTEXT_STORAGE_PREFIX}${projectId}`;
    const stored = window.localStorage.getItem(storageKey);
    window.localStorage.removeItem(storageKey);
    return restoredWizardContext(
      JSON.parse(stored ?? "null"),
      projectId,
    );
  } catch {
    return null;
  }
}

type AgentPerformanceSample = {
  ai?: {
    provider: string;
    local_model: string;
    local_fast_model: string;
    local_model_loaded: boolean;
  };
  cpu_percent: number;
  frontend_rss_mb: number;
  gpu: null | { utilization_percent: number; memory_used_mb: number; memory_total_mb: number };
  memory_percent: number;
  memory_total_mb: number;
  memory_used_mb: number;
  ollama: Array<{ name: string; size_mb: number; vram_mb: number }>;
};

type DetectedAgentQuestion = { key: string; text: string };
type WizardDiagnosticCategory = "error" | "performance" | "question" | "workflow";

const WORKFLOW_PROGRESS_BY_STATUS: Record<WorkflowStatus, number> = {
  EMPTY: 0,
  IN_PROGRESS: 50,
  COMPLETE: 100,
  WARNING: 85,
  ERROR: 40,
  APPROVED: 100,
  OUTDATED: 60,
};

const WORKFLOW_STATUS_LABEL: Record<WorkflowStatus, string> = {
  EMPTY: "Leer",
  IN_PROGRESS: "In Arbeit",
  COMPLETE: "Vollständig",
  WARNING: "Warnung",
  ERROR: "Fehler",
  APPROVED: "Freigegeben",
  OUTDATED: "Veraltet",
};

type WorkflowDisplayStatus = WorkflowStatus | "BLOCKED";

const WORKFLOW_DISPLAY_STATUS_LABEL: Record<WorkflowDisplayStatus, string> = {
  ...WORKFLOW_STATUS_LABEL,
  BLOCKED: "Angehalten",
};

const WORKFLOW_STEP_HREF: Record<WorkflowStepId, string> = {
  engineering_model: "/studio/engineering",
  routing: "/studio/routing",
  network_editor: "/studio?mode=network",
  parameters: "/studio?mode=parameters",
  capacity_timing: "/studio/capacity",
  validation: "/studio/validation",
  simulation: "/studio/simulation",
  results_analysis: "/studio/results",
  data_science_intelligence: "/studio/intelligence",
};

function wizardStepProgress(status: WorkflowStatus) {
  return WORKFLOW_PROGRESS_BY_STATUS[status];
}

function useSymbolicParameterProgress(runId: string, target: number) {
  const [progress, setProgress] = useState(0);
  const current = useRef({ runId, value: 0 });

  useEffect(() => {
    if (current.current.runId !== runId) current.current = { runId, value: 0 };
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const from = current.current.value;
    const started = window.performance.now();
    let frame = 0;
    const update = (value: number) => {
      current.current.value = value;
      setProgress(value);
    };
    const tick = (now: number) => {
      update(symbolicProgressAt(from, target, now - started));
      if (now - started < 1600) frame = window.requestAnimationFrame(tick);
    };
    const finish = () => {
      if (!motion.matches) return;
      window.cancelAnimationFrame(frame);
      update(target);
    };
    if (motion.matches || from === target) update(target);
    else {
      update(from);
      frame = window.requestAnimationFrame(tick);
    }
    motion.addEventListener("change", finish);
    return () => {
      window.cancelAnimationFrame(frame);
      motion.removeEventListener("change", finish);
    };
  }, [runId, target]);

  return progress;
}

async function writeWizardDiagnostic(
  category: WizardDiagnosticCategory,
  context: { projectId: string; runId: string; step: string; event: string; details?: unknown },
) {
  const response = await fetch("/api/agent/diagnostics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, ...context }),
  });
  if (!response.ok) throw new Error(`Diagnoseprotokoll konnte nicht geschrieben werden (${response.status}).`);
}

async function readWizardPerformance(projectId: string, runId: string, step: string) {
  const query = new URLSearchParams({ projectId, runId, step });
  const response = await fetch(`/api/agent/diagnostics?${query}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Auslastung konnte nicht gelesen werden (${response.status}).`);
  return response.json() as Promise<AgentPerformanceSample>;
}

function latestWizardQuestion(messages: EngineeringAgentUIMessage[], runId: string): DetectedAgentQuestion | null {
  if (!runId) return null;
  let requestIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    const text = message.role === "user" ? textFromParts(message.parts) : "";
    if (text.includes("Strukturierte Vorgaben fuer den Engineering-Agenten:") && text.includes(`- Lauf-ID: ${runId}`)) {
      requestIndex = index;
      break;
    }
  }
  if (requestIndex < 0) return null;
  for (let index = messages.length - 1; index > requestIndex; index -= 1) {
    const message = messages[index];
    if (message.role !== "assistant") continue;
    const text = textFromParts(message.parts).trim();
    if (!text) continue;
    const blocked = text.match(/Automatische Fortsetzung bei\s+(.+?)\s+gestoppt:\s*(.+)/i);
    if (blocked) {
      const reason = blocked[2].replace(/\s+/g, " ").trim().slice(0, 420);
      if (/timeout|zeitlimit|aborted|nicht erreichbar|fetch failed/i.test(reason)) return null;
      const question = `${reason} Welche technische Vorgabe soll für ${blocked[1].trim()} verwendet werden?`;
      return { key: `${message.id}:${question}`, text: question };
    }
    const questionEnd = text.lastIndexOf("?");
    if (questionEnd >= 0) {
      const lineStart = text.lastIndexOf("\n", questionEnd);
      const sentenceStart = text.lastIndexOf(". ", questionEnd);
      const start = Math.max(lineStart, sentenceStart) + 1;
      const question = text.slice(start, questionEnd + 1).replace(/^[-*\s]+/, "").trim().slice(0, 600);
      if (question.length >= 4) return { key: `${message.id}:${question}`, text: question };
    }
    if (/bitte (?:bestaetige|bestätige|waehle|wähle)|soll ich|moechtest du|möchtest du|human.review/i.test(text)) {
      const question = text.replace(/\s+/g, " ").trim().slice(0, 600);
      return { key: `${message.id}:${question}`, text: question };
    }
  }
  return null;
}

export function EngineeringAgentWizard({
  busy,
  mode,
  onFinish,
  title,
}: {
  busy: boolean;
  mode: "full" | "can";
  onFinish?: () => void;
  title: string;
}) {
  const [domains, setDomains] = useState<TechnologyDomain[]>(STATIC_INDUSTRY_DOMAINS);
  const [step, setStep] = useState(0);
  const [selectedIndustry, setSelectedIndustry] = useState("automotive");
  const [selectedTechnologies, setSelectedTechnologies] = useState<string[]>([]);
  const [networkArchitecture, setNetworkArchitecture] = useState<NetworkArchitectureId | "">("gateway_direct");
  const [architectureApproved, setArchitectureApproved] = useState(false);
  const [architectureAiProposal, setArchitectureAiProposal] = useState("");
  const [scope, setScope] = useState<string[]>(SCOPE_GROUP.options.map((option) => option.id));
  const [process, setProcess] = useState<string[]>(PROCESS_GROUP.options.map((option) => option.id));
  const [parameterMode, setParameterMode] = useState<"defaults" | "custom">("defaults");
  const [customParameters, setCustomParameters] = useState({
    bitrate: "",
    payload: "",
    cycleMs: "",
    samplePoint: "",
  });
  const [notes, setNotes] = useState("");
  const [taskText, setTaskText] = useState("");
  const [taskFiles, setTaskFiles] = useState<TaskAttachment[]>([]);
  const [equipmentEdits, setEquipmentEdits] = useState<{ source: string; values: Partial<Record<keyof EngineeringHardwareCounts, string>> }>({ source: "", values: {} });
  const [communicationSystemEdits, setCommunicationSystemEdits] = useState<{ source: string; values: Record<string, string> }>({ source: "", values: {} });
  const [equipmentClusterEdits, setEquipmentClusterEdits] = useState<{
    source: string;
    values: Record<string, { selected?: boolean; networkId?: string; busName?: string }>;
  }>({ source: "", values: {} });
  const taskSource = `${taskText}\n${taskFiles.map(formatTaskAttachment).join("\n")}`;
  const recognizedEquipment = useMemo(() => extractEngineeringSpecification(taskSource), [taskSource]);
  const equipmentValues = Object.fromEntries(EQUIPMENT_CATEGORIES.map(({ key }) => [key,
    equipmentEdits.source === taskSource && equipmentEdits.values[key] !== undefined
      ? equipmentEdits.values[key] : String(recognizedEquipment.targetCounts[key]),
  ])) as Record<keyof EngineeringHardwareCounts, string>;
  const equipmentReady = Object.values(equipmentValues).every((value) => /^\d+$/.test(value)
    && Number(value) <= 1000) && Object.values(equipmentValues).some((value) => Number(value) > 0);
  const equipmentCounts = Object.fromEntries(EQUIPMENT_CATEGORIES.map(({ key }) => [key, Number(equipmentValues[key])])) as EngineeringHardwareCounts;
  const [projectId] = useState(() => readActiveProjectId());
  const wizardTransport = useMemo(
    () => new DefaultChatTransport({
      api: "/api/agent/chat",
      headers: () => ({ "X-Project-ID": projectId }),
    }),
    [projectId],
  );
  const {
    messages: wizardMessages,
    sendMessage: sendWizardMessage,
    stop: stopWizardMessage,
    status: wizardAgentStatus,
    error: wizardAgentError,
  } = useChat<EngineeringAgentUIMessage>({
    id: `engineering-new-project-${projectId}`,
    transport: wizardTransport,
  });
  const [phase, setPhase] = useState<"questionnaire" | "status">("questionnaire");
  const [submitting, setSubmitting] = useState(false);
  const [submittedAt, setSubmittedAt] = useState(0);
  const [runId, setRunId] = useState("");
  const [submittedContext, setSubmittedContext] = useState<AgentWizardContext | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [routingEntries, setRoutingEntries] = useState<RoutingEntry[]>([]);
  const [hardwareItems, setHardwareItems] = useState<EngineeringObject[]>([]);
  const [routingReviewBusy, setRoutingReviewBusy] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [supplementOpen, setSupplementOpen] = useState(false);
  const [supplementText, setSupplementText] = useState("");
  const [supplementBusy, setSupplementBusy] = useState(false);
  const [performance, setPerformance] = useState<AgentPerformanceSample | null>(null);
  const [statusError, setStatusError] = useState("");
  const [statusRefreshError, setStatusRefreshError] = useState("");
  const [inlineAnswer, setInlineAnswer] = useState("");
  const [answeredQuestionKey, setAnsweredQuestionKey] = useState("");
  const workflowSignatureRef = useRef("");
  const loggedQuestionRef = useRef("");
  const missingResponseLogRef = useRef(false);
  const missingQuestionSignatureRef = useRef("");
  const wizardErrorRef = useRef("");
  const selectedDomain = useMemo(
    () => domains.find((domain) => domain.id === selectedIndustry) ?? domains[0],
    [domains, selectedIndustry],
  );
  const allTechnologies = useMemo(() => domains.flatMap((domain) => domain.technologies), [domains]);
  const technologyChoices = useMemo(() => {
    if (mode === "can") return allTechnologies.filter((technology) => isCanTechnology(technology.id, technology.family));
    return selectedDomain?.technologies ?? [];
  }, [allTechnologies, mode, selectedDomain]);

  useEffect(() => {
    let active = true;
    getCatalog()
      .then((catalog) => {
        if (!active) return;
        const nextDomains = catalog.domains.length ? catalog.domains : STATIC_INDUSTRY_DOMAINS;
        setDomains(nextDomains);
        setSelectedIndustry((current) => nextDomains.some((domain) => domain.id === current) ? current : nextDomains[0]?.id ?? "automotive");
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    void getWorkflowSummary().then((nextWorkflow) => {
      if (!active) return;
      setWorkflow(nextWorkflow);
      const legacyContext = takeLegacyWizardContext(projectId);
      const restored = restoredWizardContext(nextWorkflow.context.agent_wizard_status, projectId)
        ?? legacyContext;
      if (!restored) return;
      setSubmittedContext(restored);
      setRunId(restored.run_id);
      setScope(restored.scope_ids);
      setTaskText(restored.task);
      setSubmittedAt(0);
      setPhase("status");
      setStep(WIZARD_STATUS_INDEX);
      void writeWizardDiagnostic("workflow", {
        projectId,
        runId: restored.run_id,
        step: "status-overview",
        event: "popup-status-restored",
        details: "Die Statusübersicht wurde aus dem gespeicherten Projektkontext wiederhergestellt.",
      }).catch(() => undefined);
    }).catch(() => undefined);
    return () => {
      active = false;
    };
  }, [projectId]);

  useEffect(() => {
    if (mode === "can") {
      const canIds = technologyChoices.map((technology) => technology.id);
      const preferred = ["can_fd", "can", "can_xl"].filter((id) => canIds.includes(id));
      setSelectedTechnologies(preferred.length ? preferred : canIds.slice(0, 3));
      return;
    }
    setSelectedTechnologies(defaultTechnologyIds(selectedDomain));
  }, [mode, selectedDomain, technologyChoices]);

  useEffect(() => {
    if (phase !== "status" || !runId) return;
    let active = true;
    let refreshing = false;
    const refreshStatus = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        const [nextWorkflow, nextRoutes] = await Promise.all([getWorkflowSummary(), listRoutes()]);
        if (!active) return;
        setWorkflow(nextWorkflow);
        setRoutingEntries(nextRoutes);
        setStatusRefreshError("");
      } catch (error) {
        if (!active) return;
        const message = error instanceof Error ? error.message : "Status konnte nicht geladen werden.";
        setStatusRefreshError(message);
        void writeWizardDiagnostic("error", {
          projectId,
          runId,
          step: "status-overview",
          event: "status-refresh-failed",
          details: message,
        }).catch(() => undefined);
      } finally {
        refreshing = false;
      }
    };
    const handleWorkflowChanged = () => void refreshStatus();
    void refreshStatus();
    const interval = window.setInterval(refreshStatus, 2000);
    window.addEventListener(WORKFLOW_CHANGED_EVENT, handleWorkflowChanged);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener(WORKFLOW_CHANGED_EVENT, handleWorkflowChanged);
    };
  }, [phase, projectId, runId]);

  useEffect(() => {
    if (phase !== "status" || !runId || !wizardAgentError) return;
    const rawMessage = wizardAgentError.message || "Der Popup-Agent konnte nicht antworten.";
    const signature = `${runId}:${rawMessage}`;
    if (wizardErrorRef.current === signature) return;
    wizardErrorRef.current = signature;
    const message = agentErrorText(rawMessage);
    setStatusError(message);
    void writeWizardDiagnostic("error", {
      projectId,
      runId,
      step: "popup-agent",
      event: "popup-agent-failed",
      details: rawMessage,
    }).catch(() => undefined);
  }, [phase, projectId, runId, wizardAgentError]);

  useEffect(() => {
    if (phase !== "status" || !runId) return;
    let active = true;
    const refreshPerformance = async () => {
      try {
        const sample = await readWizardPerformance(projectId, runId, "status-overview");
        if (active) setPerformance(sample);
      } catch (error) {
        if (!active) return;
        const message = error instanceof Error ? error.message : "Auslastung konnte nicht gelesen werden.";
        setStatusError((current) => current || message);
      }
    };
    void refreshPerformance();
    const interval = window.setInterval(refreshPerformance, 5000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [phase, projectId, runId]);

  const currentQuestion = useMemo(
    () => latestWizardQuestion(wizardMessages, runId),
    [runId, wizardMessages],
  );
  const currentRunMessages = useMemo(() => {
    if (!runId) return [];
    const requestIndex = wizardMessages.findLastIndex((message) => (
      message.role === "user" && textFromParts(message.parts).includes(`- Lauf-ID: ${runId}`)
    ));
    return requestIndex >= 0 ? wizardMessages.slice(requestIndex) : [];
  }, [runId, wizardMessages]);
  const execution = readAgentRunStatus(workflow?.context?.agent_execution, runId);
  const transportPending = wizardAgentStatus === "submitted" || wizardAgentStatus === "streaming";
  const agentPending = transportPending || agentRunIsActive(execution);
  const executionStopped = !agentPending && (execution?.state === "BLOCKED" || execution?.state === "RUNNING");
  const displayedStatusError = statusError || statusRefreshError;
  const parameterTool = currentRunMessages.flatMap((message) => message.parts).findLast((part) => (
    part.type === "tool-configure_workflow_parameters"
    || (part.type === "dynamic-tool" && part.toolName === "configure_workflow_parameters")
  ));
  const parameterToolState = parameterTool && "state" in parameterTool ? parameterTool.state : undefined;
  const parametersConfigured = Object.keys(workflow?.parameters ?? {}).length > 0;
  const parameterStatus = workflow?.steps.find((item) => item.id === "parameters")?.status ?? "EMPTY";
  const parameterProgress = useSymbolicParameterProgress(runId, parameterProgressTarget(
    parametersConfigured,
    parameterToolState,
    wizardStepProgress(parameterStatus),
  ));
  const parametersWorking = transportPending
    && (parameterToolState === "input-streaming" || parameterToolState === "input-available");

  useEffect(() => {
    if (phase !== "status" || !workflow || !runId) return;
    const signature = workflow.steps
      .map((item) => `${item.id}:${item.status}:${item.version}`)
      .join("|");
    if (workflowSignatureRef.current === signature) return;
    workflowSignatureRef.current = signature;
    void writeWizardDiagnostic("workflow", {
      projectId,
      runId,
      step: workflow.steps.find((item) => WORKFLOW_PROGRESS_BY_STATUS[item.status] < 100)?.id ?? "complete",
      event: "workflow-status-changed",
      details: Object.fromEntries(workflow.steps.map((item) => [item.id, {
        status: item.status,
        version: item.version,
        progress: wizardStepProgress(item.status),
      }])),
    }).catch(() => undefined);
  }, [phase, projectId, runId, workflow]);

  useEffect(() => {
    if (phase !== "status" || !currentQuestion || currentQuestion.key === answeredQuestionKey || !runId) return;
    if (loggedQuestionRef.current === currentQuestion.key) return;
    loggedQuestionRef.current = currentQuestion.key;
    void writeWizardDiagnostic("question", {
      projectId,
      runId,
      step: workflow?.steps.find((item) => WORKFLOW_PROGRESS_BY_STATUS[item.status] < 100)?.id ?? "agent",
      event: "question-detected",
      details: currentQuestion.text,
    }).catch(() => undefined);
  }, [answeredQuestionKey, currentQuestion, phase, projectId, runId, workflow]);

  useEffect(() => {
    if (phase !== "status" || !submittedAt || currentRunMessages.length || missingResponseLogRef.current || !runId) return;
    const remaining = Math.max(0, 15000 - (Date.now() - submittedAt));
    const timer = window.setTimeout(() => {
      missingResponseLogRef.current = true;
      void writeWizardDiagnostic("question", {
        projectId,
        runId,
        step: "agent-start",
        event: "agent-response-missing",
        details: "15 Sekunden nach der Übernahme war noch keine Agentennachricht im Projektverlauf sichtbar.",
      }).catch(() => undefined);
    }, remaining);
    return () => window.clearTimeout(timer);
  }, [currentRunMessages.length, phase, projectId, runId, submittedAt]);

  useEffect(() => {
    if (phase !== "status" || !workflow || !runId || currentQuestion) return;
    const blocking = workflow.steps.find((item) => item.status === "ERROR");
    if (!blocking) return;
    const signature = `${blocking.id}:${blocking.version}`;
    if (missingQuestionSignatureRef.current === signature) return;
    const timer = window.setTimeout(() => {
      missingQuestionSignatureRef.current = signature;
      void writeWizardDiagnostic("question", {
        projectId,
        runId,
        step: blocking.id,
        event: "required-question-missing",
        details: `Workflow-Schritt ${blocking.label} steht auf ERROR, aber es wurde keine reduzierte Agentenrückfrage erkannt.`,
      }).catch(() => undefined);
    }, 8000);
    return () => window.clearTimeout(timer);
  }, [currentQuestion, phase, projectId, runId, workflow]);

  const industryGroup: ChoiceGroup = useMemo(() => ({
    id: "industry",
    label: "Industrie",
    multi: false,
    options: domains.map((domain) => ({
      id: domain.id,
      label: domain.label,
      detail: `${domain.technologies.length || "?"} definierte Technologien`,
      value: domain.label,
    })),
  }), [domains]);

  const technologyGroup: ChoiceGroup = useMemo(() => ({
    id: "technologies",
    label: "Netzwerktechnologien",
    multi: true,
    options: technologyChoices.map((technology) => ({
      id: technology.id,
      label: technologyLabel(technology.id, technology.family),
      detail: `${technology.medium} · ${technology.topology}${technology.max_payload_bytes ? ` · max. ${technology.max_payload_bytes} B` : ""}`,
      value: `${technologyLabel(technology.id, technology.family)} (${technology.id})`,
    })),
  }), [technologyChoices]);
  const communicationSystemSource = [
    taskSource,
    selectedIndustry,
    selectedTechnologies.join("|"),
    recognizedEquipment.communicationSystems.join("|"),
    Object.entries(recognizedEquipment.communicationSystemCounts).map(([key, value]) => `${key}:${value}`).join("|"),
  ].join("\n");
  const communicationSystemRows = useMemo(() => communicationSystemInputRows({
    edits: communicationSystemEdits.source === communicationSystemSource ? communicationSystemEdits.values : {},
    recognizedSystemCounts: recognizedEquipment.communicationSystemCounts,
    recognizedSystems: recognizedEquipment.communicationSystems,
    selectedTechnologyIds: selectedTechnologies,
    technologies: technologyChoices,
  }), [communicationSystemEdits, communicationSystemSource, recognizedEquipment.communicationSystemCounts, recognizedEquipment.communicationSystems, selectedTechnologies, technologyChoices]);
  const communicationSystemReady = communicationSystemRows.every((row) => /^\d+$/.test(row.value) && Number(row.value) <= 1000);
  const communicationSystemCounts = communicationSystemRows.map((row) => ({
    id: row.id,
    label: row.label,
    recognized: row.recognized,
    count: Number(row.value),
  }));
  const equipmentClusterSource = [
    taskSource,
    selectedIndustry,
    selectedTechnologies.join("|"),
    communicationSystemCounts.map((item) => `${item.id}:${item.label}:${item.count}`).join("|"),
    recognizedEquipment.chains.map((chain) => `${chain.device_type}:${chain.hardware_name}:${chain.interface_type}`).join("|"),
  ].join("\n");
  const equipmentClusters = useMemo(() => buildEquipmentClusters(
    recognizedEquipment.chains,
    communicationSystemCounts.map((item) => ({ id: item.id, label: item.label, count: item.count })),
  ), [communicationSystemCounts, recognizedEquipment.chains]);
  const clusterEditValues = equipmentClusterEdits.source === equipmentClusterSource ? equipmentClusterEdits.values : {};
  const equipmentClusterAssignments: EquipmentClusterAssignment[] = equipmentClusters.map((cluster, index) => {
    const edit = clusterEditValues[cluster.id];
    const selected = edit?.selected ?? true;
    const requestedNetworkId = edit?.networkId || cluster.recommendedNetworkId;
    const network = communicationSystemCounts.find((item) => item.id === requestedNetworkId)
      ?? communicationSystemCounts.find((item) => item.id === cluster.recommendedNetworkId)
      ?? communicationSystemCounts[0]
      ?? { id: "", label: "Noch kein Netz", count: 0 };
    const busName = edit?.busName?.trim()
      || suggestedClusterBusName(cluster.label, index + 1, network.count > 1);
    return {
      cluster_id: cluster.id,
      bus_name: busName,
      counts: cluster.counts,
      devices: cluster.devices.length,
      evidence: cluster.evidence,
      label: cluster.label,
      network_id: network.id,
      network_label: network.label,
      selected,
    };
  });
  const questionnaireSteps = [
    ...(mode === "full" ? [{ id: "industry", label: "Industrie" }] : []),
    { id: "technologies", label: "Technologien" },
    { id: "architecture", label: "Netzarchitektur" },
    ...(mode === "can" ? [{ id: "parameters", label: "Parameter" }] : []),
    { id: "scope", label: "Umfang" },
    { id: "process", label: "Arbeitsweise" },
    { id: "task", label: "Aufgabe" },
    { id: "equipment", label: "Geräteumfang" },
  ];
  const visibleSteps = [...questionnaireSteps, { id: "status", label: "Statusübersicht" }];
  const atLastStep = phase === "questionnaire" && step === questionnaireSteps.length - 1;
  const taskReady = taskText.trim().length > 0 || taskFiles.length > 0;
  const effectiveBusy = busy || submitting;
  const selectedArchitecture = architectureOption(networkArchitecture);
  const plannedNetworkConnections = plannedNetworkConnectionCount({
    architectureId: selectedArchitecture?.id,
    clusterAssignments: equipmentClusterAssignments,
    equipmentCounts,
  });
  const architectureReady = Boolean(
    selectedArchitecture
    && architectureApproved
    && (networkArchitecture !== "hybrid_ai" || architectureAiProposal.trim()),
  );
  const architectureStepIndex = questionnaireSteps.findIndex((item) => item.id === "architecture");

  function toggle(group: ChoiceGroup, optionId: string) {
    if (group.id === "industry") {
      setSelectedIndustry(optionId);
      return;
    }
    if (group.id === "technologies") {
      setSelectedTechnologies((current) => toggleSelection(current, optionId));
      return;
    }
    if (group.id === "scope") {
      setScope((current) => toggleSelection(current, optionId));
      return;
    }
    if (group.id === "process") {
      setProcess((current) => toggleSelection(current, optionId));
    }
  }

  async function handleTaskFiles(files: FileList | null, source: TaskAttachment["source"] = "task") {
    const selected = Array.from(files ?? []).slice(0, MAX_TASK_ATTACHMENTS);
    const attachments = await Promise.all(selected.map((file) => readTaskAttachment(file, source)));
    setTaskFiles((current) => mergeTaskAttachments(current, attachments));
  }

  function selectNetworkArchitecture(id: NetworkArchitectureId) {
    setNetworkArchitecture(id);
    setArchitectureApproved(false);
    if (id !== "hybrid_ai") setArchitectureAiProposal("");
  }

  function generateHybridArchitecture() {
    const technologies = technologyGroup.options
      .filter((option) => selectedTechnologies.includes(option.id))
      .map((option) => option.label)
      .join(", ");
    setNetworkArchitecture("hybrid_ai");
    setArchitectureApproved(false);
    setArchitectureAiProposal(
      `Kombiniere Variante 2 und 3. Ordne lokale, echtzeit- und regelungskritische Sensoren/Aktoren der fachlich zuständigen ECU zu. ` +
      `Binde zentrale, diagnoseorientierte oder hochbandbreitige Teilnehmer direkt an Gateway/BCM an. ` +
      `Begründe jede Direktanbindung anhand von Semantik, Safety, Latenz und Bandbreite${technologies ? ` für ${technologies}` : ""}. ` +
      `Beruecksichtige angehaengte Architektur-Evidence wie PDF, PowerPoint, Bilder, Diagramme und Textauszuege als Quelle fuer Cluster, Knoten und Verbindungen.`,
    );
  }

  async function submitQuestionnaire() {
    if (!taskReady || !equipmentReady || !architectureReady || !selectedArchitecture || submitting) return;
    setSubmitting(true);
    setStatusError("");
    const selectedTechnologyValues = technologyGroup.options
      .filter((option) => selectedTechnologies.includes(option.id))
      .map((option) => option.value);
    const selectedScopeValues = SCOPE_GROUP.options.filter((option) => scope.includes(option.id)).map((option) => option.value);
    const selectedProcessValues = PROCESS_GROUP.options.filter((option) => process.includes(option.id)).map((option) => option.value);
    const parameterSummary = parameterMode === "defaults"
      ? "Technologie-Defaults verwenden"
      : `Nutzerdefiniert: Bitrate=${customParameters.bitrate || "Default"}; Payload=${customParameters.payload || "Default"}; Cycle=${customParameters.cycleMs || "Default"} ms; SamplePoint=${customParameters.samplePoint || "Default"} %`;
    const note = notes.trim() ? `\n- Weitere Hinweise: ${notes.trim()}` : "";
    const attachments = taskFiles.length
      ? `\n\nAufgaben-Anlagen:\n${taskFiles.map((file) => formatTaskAttachment(file)).join("\n")}`
      : "";
    const concreteTask = `${taskText.trim() || "Aufgabe wurde als Datei uebergeben."}${attachments}`;
    const nextRunId = crypto.randomUUID();
    const confirmedAt = new Date().toISOString();
    const topologyKnowledge = topologyClusterKnowledgeSummary(projectId, mode === "can" ? selectedIndustry : selectedDomain?.id ?? selectedIndustry);
    const nextContext: AgentWizardContext = {
      attachments: taskFiles.map((file) => ({ kind: file.kind, name: file.name, size: file.size, source: file.source })),
      confirmed_at: confirmedAt,
      industry: mode === "can" ? "Aus Projektkontext ableiten" : selectedDomain?.label ?? selectedIndustry,
      mode,
      network_architecture: {
        ai_proposal: architectureAiProposal.trim(),
        approved: true,
        approved_at: confirmedAt,
        id: selectedArchitecture.id,
        label: selectedArchitecture.label,
        rules: selectedArchitecture.rules,
      },
      notes: notes.trim(),
      parameters: parameterSummary,
      process: selectedProcessValues,
      project_id: projectId,
      run_id: nextRunId,
      scope: selectedScopeValues,
      scope_ids: scope,
      task: taskText.trim() || "Aufgabe wurde als Datei übergeben.",
      technologies: selectedTechnologyValues,
      communication_system_counts: communicationSystemCounts,
      planned_network_connections: plannedNetworkConnections,
      system_cluster_assignments: equipmentClusterAssignments,
      topology_cluster_knowledge: topologyKnowledge,
    };
    const clusterSummary = equipmentClusterSummary(equipmentClusterAssignments);
    const prompt =
      "Strukturierte Vorgaben fuer den Engineering-Agenten:\n" +
        `- Lauf-ID: ${nextRunId}\n` +
        `- Abfrage erfolgt: true\n` +
        `- Abfrage-Modus: ${mode === "can" ? "reduziert fuer CAN/CAN-FD" : "vollstaendig"}\n` +
        `- Industrie: ${mode === "can" ? "aus Projektkontext ableiten" : selectedDomain?.label ?? selectedIndustry}\n` +
        `- Netzwerktechnologien: ${selectedTechnologyValues.length ? selectedTechnologyValues.join("; ") : "nicht vorgegeben, passende Technologien aus der gewaehlten Industrie verwenden"}\n` +
        `- Kommunikationssystem-Sollwerte: ${JSON.stringify(communicationSystemCounts)}\n` +
        `- Geplante Netzwerkverbindungen: ${plannedNetworkConnections}\n` +
        `- Systemcluster-Netzvorgaben: ${clusterSummary || "keine explizite Clusterbindung"}\n` +
        `- Systemcluster-Details: ${JSON.stringify(equipmentClusterAssignments)}\n` +
        `- Topologie-Cluster-Profil: ${topologyKnowledge.profile}\n` +
        `- Topologie-Cluster-Regeln: ${topologyKnowledge.ruleSummary.join("; ") || "generische Systemnaehe verwenden"}\n` +
        `- Gelernte Topologie-Nachbarschaften: ${topologyKnowledge.lessonSummary.join("; ") || "noch keine Projektkorrekturen gelernt"}\n` +
        `- Netzarchitektur-ID: ${selectedArchitecture.id}\n` +
        `- Netzarchitektur: ${selectedArchitecture.label}\n` +
        `- Netzarchitektur-Regeln: ${selectedArchitecture.rules}\n` +
        `- Netzarchitektur-Freigabe: explizit durch den Nutzer erteilt am ${confirmedAt}\n` +
        `- Hardware-Sollwerte: ${JSON.stringify(equipmentCounts)}\n` +
        `${architectureAiProposal.trim() ? `- KI-Architekturvorgabe: ${architectureAiProposal.trim()}\n` : ""}` +
        `- Parameter: ${parameterSummary}\n` +
        `- Workflowumfang: ${selectedScopeValues.length ? selectedScopeValues.join("; ") : "nicht vorgegeben, Ziel aus Nutzeranfrage ableiten"}\n` +
        `- Arbeitsweise: ${selectedProcessValues.length ? selectedProcessValues.join("; ") : "nicht vorgegeben, vorsichtig mit Review-Gate arbeiten"}${note}\n` +
        "\nKonkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:\n" +
        `${concreteTask}\n\n` +
        "Verbindliche Kanonisierung bei der Projektanlage: Pruefe vor jeder Hardware-Anlage vorhandene Systeme und verwende fachlich gleichwertige Hardware wieder. ADAS, Fahrerassistenz und Driver Assistance sind kontrollierte Synonyme desselben Systems. Eine gemeinsame Endung wie ECU ist kein Dublettenkriterium; fachlich verschiedene Systeme wie Abgasnachbehandlung und Airbag bleiben getrennt. Unterobjekte muessen an der wiederverwendeten kanonischen Hardware-ID angelegt werden.\n\n" +
        "Verbindliche Systemcluster-Regel: Ausgewaehlte Cluster bilden fachliche Systemrahmen. Sensoren, Aktoren, Steuerungen, Interfaces, Nachrichten und Signale desselben Clusters muessen zusammen bewertet, auf das gewaehlte Netz abgebildet und bei Kapazitaetsproblemen als zusammenhaengendes System verteilt werden.\n\n" +
        "Verbindliche Topologie-Regel: Systemrahmen sind kompakte Nachbarschaftsgruppen, keine ueber den ganzen View gezogenen Container. Ordne fachlich verwandte Rahmen nebeneinander an, fuehre Leitungen innerhalb und zwischen benachbarten Rahmen lokal, und gib Korrekturen des Nutzers als abstrakte Cluster-Nachbarschaften an den RAG-Kontext zurueck.\n\n" +
        "Starte jetzt die Analyse und arbeite selbststaendig bis zum genannten Zielzustand. Nutze plausible Defaults, wenn Details fehlen, und frage nur bei echten fachlichen Entscheidungen oder Human Review erneut.";
    nextContext.agent_prompt = prompt;
    setRunId(nextRunId);
    setSubmittedAt(Date.now());
    setSubmittedContext(nextContext);
    activateEngineeringAgentWizardSession(projectId);
    setPhase("status");
    setStep(questionnaireSteps.length);
    workflowSignatureRef.current = "";
    loggedQuestionRef.current = "";
    missingResponseLogRef.current = false;
    missingQuestionSignatureRef.current = "";

    try {
      await setWorkflowContext({
        agent_wizard_status: {
          ...nextContext,
          status: "RUNNING",
        },
      });
      await Promise.all([
        writeWizardDiagnostic("workflow", {
          projectId,
          runId: nextRunId,
          step: "status-overview",
          event: "context-accepted",
          details: nextContext,
        }),
        writeWizardDiagnostic("question", {
          projectId,
          runId: nextRunId,
          step: "agent-start",
          event: "question-monitor-started",
          details: "Rückfragen werden im Statusschritt reduziert dargestellt; fehlende Rückfragen bei Blockern werden protokolliert.",
        }),
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Statuskontext konnte nicht gespeichert werden.";
      setStatusError(message);
      void writeWizardDiagnostic("error", {
        projectId,
        runId: nextRunId,
        step: "status-overview",
        event: "context-persistence-failed",
        details: message,
      }).catch(() => undefined);
    }
    try {
      await sendWizardMessage({ text: prompt });
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Der Popup-Agent konnte nicht gestartet werden.";
      setStatusError(agentErrorText(rawMessage));
      await writeWizardDiagnostic("error", {
        projectId,
        runId: nextRunId,
        step: "popup-agent",
        event: "popup-agent-start-failed",
        details: rawMessage,
      }).catch(() => undefined);
    } finally {
      setSubmitting(false);
    }
  }

  function handlePrimary() {
    if (atLastStep) {
      void submitQuestionnaire();
      return;
    }
    setStep((current) => {
      if (questionnaireSteps[current]?.id === "architecture" && !architectureReady) return current;
      return Math.min(current + 1, questionnaireSteps.length - 1);
    });
  }

  async function finishWizard() {
    if (agentPending || routingReviewBusy || supplementBusy || routingReviewPending || runPaused) return;
    try {
      await setWorkflowContext({ agent_wizard_status: null });
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : "Der Agent-Auftrag konnte nicht abgeschlossen werden.");
      return;
    }
    finishEngineeringAgentWizardSession(projectId);
    void writeWizardDiagnostic("workflow", {
      projectId,
      runId: runId || submittedContext?.run_id || "without-run-id",
      step: "status-overview",
      event: "popup-finished-by-user",
      details: "Die temporäre Rückkehr zum Engineering-Auftrag wurde beendet.",
    }).catch(() => undefined);
    onFinish?.();
  }

  async function cancelWizardRun() {
    if (cancelBusy) return;
    const activeRunId = runId || submittedContext?.run_id || "without-run-id";
    setCancelBusy(true);
    setStatusError("");
    try {
      stopWizardMessage();
      const workloadIds = collectWorkloadIds(currentRunMessages);
      if (!workloadIds.length) {
        const workloads = await listEngineeringWorkloads({ limit: 50 });
        workloads.items
          .filter((item) => ["QUEUED", "IN_PROGRESS", "PAUSED"].includes(String(item.status).toUpperCase()))
          .forEach((item) => {
            if (item.workload_id) workloadIds.push(item.workload_id);
          });
      }
      await Promise.all([...new Set(workloadIds)].map((workloadId) => (
        cancelEngineeringWorkload(workloadId).catch((error) => {
          void writeWizardDiagnostic("error", {
            projectId,
            runId: activeRunId,
            step: "status-overview",
            event: "workload-cancel-failed",
            details: error instanceof Error ? error.message : `Workload ${workloadId} konnte nicht abgebrochen werden.`,
          }).catch(() => undefined);
        })
      )));
      const canceledWorkflow = await setWorkflowContext({
        agent_wizard_status: submittedContext ? {
          ...submittedContext,
          status: "CANCELED",
          canceled_at: new Date().toISOString(),
        } : null,
        agent_execution: {
          run_id: activeRunId,
          state: "CANCELED",
          step: execution?.step ?? "engineering_model",
          completed: execution?.completed ?? 0,
          total: execution?.total ?? 0,
          message: "Der Engineering-Auftrag wurde durch den Nutzer abgebrochen.",
          updated_at: new Date().toISOString(),
        },
      });
      setWorkflow(canceledWorkflow);
      finishEngineeringAgentWizardSession(projectId);
      void writeWizardDiagnostic("workflow", {
        projectId,
        runId: activeRunId,
        step: "status-overview",
        event: "popup-canceled-by-user",
        details: "Der laufende Engineering-Agent und zugehoerige Workloads wurden abgebrochen.",
      }).catch(() => undefined);
      setStatusError("Auftrag abgebrochen.");
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : "Der Auftrag konnte nicht abgebrochen werden.");
    } finally {
      setCancelBusy(false);
    }
  }

  function selectedFor(group: ChoiceGroup) {
    if (group.id === "industry") return [selectedIndustry];
    if (group.id === "technologies") return selectedTechnologies;
    if (group.id === "scope") return scope;
    if (group.id === "process") return process;
    return [];
  }

  function activeGroupForStep() {
    if (phase === "status") return null;
    const id = questionnaireSteps[step]?.id;
    if (id === "industry") return industryGroup;
    if (id === "technologies") return technologyGroup;
    if (id === "scope") return SCOPE_GROUP;
    if (id === "process") return PROCESS_GROUP;
    return null;
  }

  async function answerInlineQuestion() {
    if (!currentQuestion || currentQuestion.key === answeredQuestionKey || !inlineAnswer.trim() || !runId) return;
    const answer = inlineAnswer.trim();
    setAnsweredQuestionKey(currentQuestion.key);
    setInlineAnswer("");
    await writeWizardDiagnostic("question", {
      projectId,
      runId,
      step: workflow?.steps.find((item) => WORKFLOW_PROGRESS_BY_STATUS[item.status] < 100)?.id ?? "agent",
      event: "question-answered",
      details: { question: currentQuestion.text, answer },
    }).catch((error) => {
      setStatusError(error instanceof Error ? error.message : "Antwortprotokoll konnte nicht geschrieben werden.");
    });
    try {
      await sendWizardMessage({ text: [
        `Antwort auf die reduzierte Rückfrage im Statusdialog. Lauf-ID: ${runId}`,
        `Rückfrage: ${currentQuestion.text}`,
        `Antwort des Nutzers: ${answer}`,
        "Aktualisiere den Projektkontext und setze den bestätigten Engineering-Auftrag ohne Ansichtswechsel fort.",
      ].join("\n") });
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Die Antwort konnte nicht an den Popup-Agenten gesendet werden.";
      setStatusError(agentErrorText(rawMessage));
      setAnsweredQuestionKey("");
      setInlineAnswer(answer);
      await writeWizardDiagnostic("error", {
        projectId,
        runId,
        step: "popup-agent",
        event: "popup-answer-failed",
        details: rawMessage,
      }).catch(() => undefined);
    }
  }

  async function retryPopupRun() {
    if (agentPending || !runId) return;
    const originalPrompt = currentRunMessages
      .find((message) => message.role === "user" && textFromParts(message.parts).includes(`- Lauf-ID: ${runId}`));
    const originalText = originalPrompt ? textFromParts(originalPrompt.parts).trim() : submittedContext?.agent_prompt?.trim() ?? "";
    const modelComplete = ["COMPLETE", "APPROVED", "WARNING"].includes(workflow?.statuses.engineering_model ?? "EMPTY");
    const workflowTarget = modelComplete && routingReview.complete
      ? [...(submittedContext?.scope_ids ?? [])].reverse().find((id) => SCOPE_GROUP.options.some((option) => option.id === id)) as WorkflowStepId | undefined
      : undefined;
    const prompt = workflowTarget
      ? `Setze den bestaetigten Engineering-Auftrag am letzten erreichten Schritt fort. Lauf-ID: ${runId}. Ziel: ${workflowTarget}.`
      : [
        "Fortsetzung-Freigabe: Der Nutzer hat im Popup ausdrücklich Auftrag fortsetzen gewählt.",
        `Lauf-ID: ${runId}.`,
        "Wenn nach der Nachbearbeitung weiterhin reine Soll/Ist-Abweichungen im Geräteumfang bestehen, dokumentiere die fehlenden Teilnehmer im Wizard-Kontext und arbeite genau einmal weiter. Bei technischen Anlagefehlern stoppen. Keine automatische Endlosschleife.",
        "",
        originalText,
      ].join("\n");
    if (!prompt) return;
    setStatusError("");
    await writeWizardDiagnostic("workflow", {
      projectId,
      runId,
      step: "agent-start",
      event: "popup-agent-resumed",
      details: workflowTarget ? `Fortsetzung bis ${workflowTarget}; vorhandenes Modell und Routing bleiben erhalten.` : "Fehlende Engineering-Ketten werden vervollstaendigt.",
    }).catch(() => undefined);
    try {
      await sendWizardMessage({ text: prompt }, workflowTarget ? { body: { workflowTarget } } : undefined);
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Der Popup-Agent konnte nicht erneut gestartet werden.";
      setStatusError(agentErrorText(rawMessage));
      await writeWizardDiagnostic("error", {
        projectId,
        runId,
        step: "popup-agent",
        event: "popup-agent-restart-failed",
        details: rawMessage,
      }).catch(() => undefined);
    }
  }

  async function approveRoutingAndContinue() {
    const approval = routingApprovalProgress(routingEntries);
    const routeIds = approval.routes
      .filter((route) => route.validation?.valid === true && String(route.approval_state).toUpperCase() !== "APPROVED")
      .map((route) => route.id);
    if (!routeIds.length || routingReviewBusy || agentPending || !runId) return;
    setRoutingReviewBusy(true);
    setStatusError("");
    try {
      await approveRoutes(routeIds);
      const [nextWorkflow, nextRoutes] = await Promise.all([getWorkflowSummary(), listRoutes()]);
      setWorkflow(nextWorkflow);
      setRoutingEntries(nextRoutes);
      await writeWizardDiagnostic("question", {
        projectId,
        runId,
        step: "routing",
        event: "routing-review-approved",
        details: { approved_routes: routeIds.length },
      });

      const workflowTarget = [...(submittedContext?.scope_ids ?? [])]
        .reverse()
        .find((stepId) => SCOPE_GROUP.options.some((option) => option.id === stepId)) as WorkflowStepId | undefined;
      if (workflowTarget && workflowTarget !== "routing") {
        await sendWizardMessage(
          { text: [
            `Routing-Freigabe im Popup erteilt. Lauf-ID: ${runId}`,
            `${routeIds.length} valide Routing-Einträge wurden durch den Nutzer freigegeben.`,
            `Setze den bestätigten Engineering-Auftrag jetzt innerhalb des Popups bis zum Ziel ${workflowTarget} fort.`,
          ].join("\n") },
          { body: { workflowTarget } },
        );
      }
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Das Routing-Review konnte nicht abgeschlossen werden.";
      setStatusError(agentErrorText(rawMessage));
      await writeWizardDiagnostic("error", {
        projectId,
        runId,
        step: "routing",
        event: "routing-review-failed",
        details: rawMessage,
      }).catch(() => undefined);
    } finally {
      setRoutingReviewBusy(false);
    }
  }

  async function submitSupplement() {
    const addition = supplementText.trim();
    if (!addition || supplementBusy || agentPending || !runId) return;
    setSupplementBusy(true);
    setStatusError("");
    try {
      await writeWizardDiagnostic("question", {
        projectId,
        runId,
        step: workflow?.active_step ?? "engineering_model",
        event: "analysis-supplement-submitted",
        details: addition,
      });
      await sendWizardMessage({ text: [
        `Ergänzung zum Engineering-Auftrag. Lauf-ID: ${runId}`,
        `Ergänzung des Nutzers: ${addition}`,
        "Analysiere diese Ergänzung im bestehenden Projekt. Erzeuge notwendige Änderungen als prüfbare Vorschläge und führe keine menschliche Freigabe selbst aus. Stelle das Ergebnis anschließend wieder reduziert im Popup bereit.",
      ].join("\n") });
      setSupplementText("");
      setSupplementOpen(false);
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Die Ergänzung konnte nicht verarbeitet werden.";
      setStatusError(agentErrorText(rawMessage));
      await writeWizardDiagnostic("error", {
        projectId,
        runId,
        step: workflow?.active_step ?? "engineering_model",
        event: "analysis-supplement-failed",
        details: rawMessage,
      }).catch(() => undefined);
    } finally {
      setSupplementBusy(false);
    }
  }

  const activeGroup = activeGroupForStep();
  const activeStepId = visibleSteps[step]?.id ?? "status";
  const primaryDisabled = effectiveBusy
    || (atLastStep && (!taskReady || !equipmentReady || !communicationSystemReady))
    || (activeStepId === "task" && !taskReady)
    || (activeStepId === "architecture" && !architectureReady);
  const visibleQuestion = currentQuestion?.key === answeredQuestionKey ? null : currentQuestion;
  const persistedStatusRows = SCOPE_GROUP.options.map((option, index) => {
    const workflowStepId = option.id as WorkflowStepId;
    const workflowStep = workflow?.steps.find((item) => item.id === workflowStepId);
    const blocked = execution?.step === workflowStepId && execution.state === "BLOCKED";
    const staleRunning = execution?.step === workflowStepId && execution.state === "RUNNING" && executionStopped;
    const building = execution?.step === workflowStepId && (execution.state === "RUNNING" || blocked);
    const awaitingReview = execution?.step === workflowStepId && execution.state === "REVIEW_REQUIRED"
      && workflowStep?.status === "IN_PROGRESS";
    const workflowStatus: WorkflowStatus = staleRunning
      ? "ERROR"
      : workflowStep?.status ?? "EMPTY";
    const displayStatus: WorkflowDisplayStatus = blocked ? "BLOCKED" : workflowStatus;
    return {
      displayStatus,
      id: workflowStepId,
      label: option.label.replace(/^\d+\s+/, ""),
      position: index + 1,
      progress: building ? Math.min(99, agentBuildProgressPercent(execution)) : awaitingReview ? 99 : wizardStepProgress(workflowStatus),
      selected: submittedContext?.scope_ids.includes(workflowStepId) ?? scope.includes(workflowStepId),
      status: workflowStatus,
    };
  });
  const activeStatusIndex = agentPending
    ? persistedStatusRows.findIndex((item) => parametersWorking ? item.id === "parameters"
      : execution?.state === "RUNNING" ? item.id === execution.step : item.selected && item.progress < 100)
    : -1;
  const statusRows = persistedStatusRows.map((item, index) => {
    const active = index === activeStatusIndex;
    const workflowProgress = active && execution?.state !== "RUNNING" ? Math.max(15, item.progress) : item.progress;
    return {
      ...item,
      active,
      progress: item.id === "parameters" ? parameterProgress : workflowProgress,
    };
  });
  const overallProgress = Math.round(statusRows.reduce((sum, item) => sum + item.progress, 0) / statusRows.length);
  const workflowHasProgress = persistedStatusRows.some((item) => item.progress > 0);
  const currentStatusStep = statusRows.find((item) => item.active || (executionStopped && item.id === execution?.step))?.label
    ?? persistedStatusRows.find((item) => item.selected && !["COMPLETE", "APPROVED", "WARNING"].includes(item.status))?.label ?? "Abgeschlossen";
  const activeAnalysis = performance?.ai?.provider
    ? performance.ai.provider === "hybrid-demand"
      ? "Regelwerk + KI bei Bedarf"
      : performance.ai.provider
    : "Regelwerk";
  const activeModel = performance?.ai
    ? performance.ai.local_model_loaded
      ? performance.ai.local_model
      : `Standby: ${performance.ai.local_model}`
    : performance?.ollama[0]?.name ?? "Standby";
  const hasResumablePrompt = currentRunMessages.some((message) => (
    message.role === "user" && textFromParts(message.parts).includes(`- Lauf-ID: ${runId}`)
  )) || Boolean(submittedContext?.agent_prompt?.trim());
  const routingReview = routingApprovalProgress(routingEntries);
  const routingReviewPending = !agentPending
    && !executionStopped && !routingReview.complete
    && (routingReview.total > 0 || execution?.state === "REVIEW_REQUIRED");
  const runPaused = !agentPending && !routingReviewPending
    && (executionStopped || persistedStatusRows.some((item) => item.selected && !["COMPLETE", "APPROVED", "WARNING"].includes(item.status)));
  const canRetryPopupRun = runPaused && hasResumablePrompt;
  const lastAssistantText = [...currentRunMessages].reverse()
    .find((message) => message.role === "assistant" && textFromParts(message.parts).trim());
  const runMessage = execution?.state === "RUNNING" && executionStopped
    ? `Seit mehr als zwei Minuten liegt kein Laufstatus vor. Letzter Stand: ${execution.message}`
    : execution?.message || (lastAssistantText ? textFromParts(lastAssistantText.parts) : "");
  const approvableRoutingCount = routingReview.routes.filter(
    (route) => route.validation?.valid === true && String(route.approval_state).toUpperCase() !== "APPROVED",
  ).length;
  const engineeringCounts = workflow?.artifact_checks?.engineering_model?.counts ?? {};
  const hardwareRevision = workflow?.versions?.engineering_model;
  useEffect(() => {
    if (phase !== "status") return;
    let active = true;
    void listAllEngineeringObjects("hardware-nodes").then((items) => {
      if (active) setHardwareItems(items);
    }).catch(() => undefined);
    return () => { active = false; };
  }, [phase, hardwareRevision]);
  const hardwareByType = workflow?.artifact_checks?.engineering_model?.hardware_by_type ?? {};
  const hardwareNodes = Array.isArray(workflow?.topology?.nodes) ? workflow.topology.nodes : [];
  const hardwareDetails = {
    ecus: Number(hardwareByType.ECU ?? hardwareNodes.filter((node) => String(node.kind).toLowerCase() === "ecu").length),
    gateways: Number(hardwareByType.Gateway ?? hardwareNodes.filter((node) => String(node.kind).toLowerCase() === "gateway").length),
    sensors: Number(hardwareByType.SensorController ?? hardwareNodes.filter((node) => String(node.kind).toLowerCase() === "sensor").length),
    actuators: Number(hardwareByType.ActuatorController ?? hardwareNodes.filter((node) => String(node.kind).toLowerCase() === "actuator").length),
  };
  const displayedPlannedNetworkConnections = submittedContext?.planned_network_connections ?? plannedNetworkConnectionCount({
    architectureId: submittedContext?.network_architecture?.id ?? selectedArchitecture?.id,
    clusterAssignments: submittedContext?.system_cluster_assignments ?? equipmentClusterAssignments,
    equipmentCounts: hardwareDetails,
  });
  const blockerDetails = workflow?.active_step === "engineering_model"
    ? scopeMismatchSummaries(workflow.artifact_checks?.engineering_model?.scope_mismatches)
    : [];
  const blockerSummary = blockerDetails.join(" · ");
  const documentedDeviationSummary = documentedScopeDeviationSummary(workflow?.context?.agent_wizard_status);
  const blockedTitle = blockerSummary
    ? `Auftrag angehalten: ${blockerSummary}`
    : documentedDeviationSummary ? `Dokumentierte Abweichung: ${documentedDeviationSummary}` : "Auftrag angehalten";
  const analysisCounts = [
    ...EQUIPMENT_CATEGORIES.map(({ key, label }) => ({
      label,
      value: hardwareDetails[key],
      detail: `${hardwareDetails[key]} erkannte Hardware-Teilnehmer. Die Device Class entscheidet, ob daraus eine eigene Funktion wird.`,
    })),
    {
      label: "Funktionen",
      value: Number(engineeringCounts.functions ?? 0),
      detail: "Soll nach Class-Modell nur fuer Class 3/4 automatisch entstehen. Basic/Passive Sensoren und Aktoren bleiben ohne kuenstliche Function.",
    },
    {
      label: "Interfaces",
      value: Number(engineeringCounts.interfaces ?? 0),
      detail: "Logische Interfaces werden je Teilnehmer oder Subsystem erzeugt. Direkte Hardware-Interfaces zaehlen separat im Hardware-Interface-Modell.",
    },
    {
      label: "Nachrichten",
      value: Number(engineeringCounts.messages ?? 0),
      detail: "Gepackte Kommunikationsobjekte. Mehrere Signale koennen eine Nachricht teilen, wenn Bus, Zyklus und Producer passen.",
    },
    {
      label: "Signale",
      value: Number(engineeringCounts.signals ?? 0),
      detail: "Einzelne Werte, Statuscodes, Commands oder Datenindikatoren innerhalb der Nachrichten.",
    },
    {
      label: "Netzverbindungen",
      value: displayedPlannedNetworkConnections,
      detail: "Geplante physische oder logische Netzpfade aus Architektur, Clustern und Teilnehmerumfang.",
    },
    {
      label: "Routen",
      value: routingReview.total,
      detail: "Vorbereitete Routing-Pfade, die vor der Uebernahme validiert und freigegeben werden muessen.",
    },
  ];
  const analysisHeading = agentPending
    ? "Erste Analyse läuft"
    : routingReviewPending
      ? "Analyse bereit zur Freigabe"
      : runPaused ? "Auftrag angehalten" : "Analyseübersicht";

  return (
    <section className="eng-agent-questionnaire" aria-label="Geführte Agent-Rückfrage">
      <div className="eng-agent-questionnaire-head">
        <div>
          <strong>{title}</strong>
          <span>{visibleSteps[step]?.label}: Schritt {step + 1} von {visibleSteps.length}</span>
        </div>
        {phase === "status" ? (
          <span className={`agent-wizard-live ${displayedStatusError || runPaused ? "error" : ""}`}><i aria-hidden="true" /> {displayedStatusError ? "Diagnosehinweis" : agentPending ? "Agent arbeitet" : runPaused ? "Angehalten" : routingReviewPending ? "Freigabe erforderlich" : "Live"}</span>
        ) : (
          <button className="button primary tiny" disabled={primaryDisabled} onClick={handlePrimary} type="button">
            {submitting ? "Wird übernommen ..." : atLastStep ? "Übernehmen" : "Weiter"}
          </button>
        )}
      </div>
      <div className="agent-questionnaire-steps" aria-label="Rückfrage-Schritte">
        {visibleSteps.map((item, index) => (
          <button
            className={index === step ? "active" : ""}
            disabled={
              effectiveBusy
              || phase === "status"
              || item.id === "status"
              || (item.id === "equipment" && !taskReady)
              || (index > architectureStepIndex && !architectureReady)
            }
            key={item.id}
            title={item.label}
            onClick={() => setStep(index)}
            type="button"
          >
            {index + 1}
          </button>
        ))}
      </div>
      {activeGroup && (
        <fieldset className="agent-choice-group">
          <legend>{activeGroup.label}</legend>
          <div className="agent-choice-grid">
            {activeGroup.options.map((option) => {
              const checked = selectedFor(activeGroup).includes(option.id);
              return (
                <label className={`agent-choice ${checked ? "selected" : ""}`} key={option.id}>
                  <input
                    checked={checked}
                    disabled={busy}
                    onChange={() => toggle(activeGroup, option.id)}
                    type="checkbox"
                  />
                  <span>
                    <strong>{option.label}</strong>
                    <small>{option.detail}</small>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
      )}
      {activeStepId === "parameters" && (
        <fieldset className="agent-choice-group">
          <legend>Parameter</legend>
          <div className="agent-choice-grid">
            <label className={`agent-choice ${parameterMode === "defaults" ? "selected" : ""}`}>
              <input checked={parameterMode === "defaults"} disabled={busy} onChange={() => setParameterMode("defaults")} type="checkbox" />
              <span>
                <strong>Defaults verwenden</strong>
                <small>Bitrate, Payload und Timing aus dem Technologieprofil übernehmen.</small>
              </span>
            </label>
            <label className={`agent-choice ${parameterMode === "custom" ? "selected" : ""}`}>
              <input checked={parameterMode === "custom"} disabled={busy} onChange={() => setParameterMode("custom")} type="checkbox" />
              <span>
                <strong>Nutzerdefiniert</strong>
                <small>CAN-Parameter manuell vorgeben, leere Felder bleiben Default.</small>
              </span>
            </label>
          </div>
          {parameterMode === "custom" && (
            <div className="agent-parameter-grid">
              <label>
                <span>Bitrate</span>
                <input disabled={busy} inputMode="numeric" onChange={(event) => setCustomParameters((current) => ({ ...current, bitrate: event.target.value }))} placeholder="z. B. 500000" value={customParameters.bitrate} />
              </label>
              <label>
                <span>Payload Byte</span>
                <input disabled={busy} inputMode="numeric" onChange={(event) => setCustomParameters((current) => ({ ...current, payload: event.target.value }))} placeholder="z. B. 64" value={customParameters.payload} />
              </label>
              <label>
                <span>Cycle ms</span>
                <input disabled={busy} inputMode="decimal" onChange={(event) => setCustomParameters((current) => ({ ...current, cycleMs: event.target.value }))} placeholder="z. B. 10" value={customParameters.cycleMs} />
              </label>
              <label>
                <span>Sample Point %</span>
                <input disabled={busy} inputMode="decimal" onChange={(event) => setCustomParameters((current) => ({ ...current, samplePoint: event.target.value }))} placeholder="z. B. 80" value={customParameters.samplePoint} />
              </label>
            </div>
          )}
        </fieldset>
      )}
      {activeStepId === "architecture" && (
        <fieldset className="agent-choice-group agent-architecture-group">
          <legend>Verbindliche Netzarchitektur</legend>
          <div className="agent-architecture-grid">
            {NETWORK_ARCHITECTURES.map((option) => {
              const checked = option.id === networkArchitecture;
              return (
                <label className={`agent-architecture-choice ${checked ? "selected" : ""}`} key={option.id}>
                  <input
                    checked={checked}
                    disabled={effectiveBusy}
                    name="network-architecture"
                    onChange={() => selectNetworkArchitecture(option.id)}
                    type="radio"
                  />
                  <span className="agent-architecture-copy">
                    <strong>{option.label}</strong>
                    <small>{option.detail}</small>
                    <code aria-label={`Schema ${option.label}`}>{option.diagram}</code>
                  </span>
                </label>
              );
            })}
          </div>
          <div className="agent-architecture-ai">
            <div>
              <strong>KI-Architekturentwurf</strong>
              <small>Erstellt eine prüfbare Kombination aus Architekturvarianten. PDF, PowerPoint, Bilder, SVG und Text können als Evidence einfließen.</small>
            </div>
            <div className="agent-architecture-ai-actions">
              <label className="button secondary tiny agent-file-button">
                <input
                  accept={SUPPORTED_EVIDENCE_ACCEPT}
                  disabled={effectiveBusy}
                  multiple
                  onChange={(event) => {
                    void handleTaskFiles(event.target.files, "architecture");
                    event.currentTarget.value = "";
                  }}
                  type="file"
                />
                Evidence hinzufügen
              </label>
              <button className="button secondary tiny" disabled={effectiveBusy} onClick={generateHybridArchitecture} type="button">
                KI-Entwurf erstellen
              </button>
            </div>
          </div>
          {taskFiles.some((file) => file.source === "architecture") && (
            <ul className="agent-file-list agent-architecture-files">
              {taskFiles.filter((file) => file.source === "architecture").map((file) => (
                <li key={`architecture-${file.name}-${file.size}`}>
                  {file.previewDataUrl && <img alt="" className="agent-attachment-thumb" src={file.previewDataUrl} />}
                  <span>
                    <strong>{file.name}</strong>
                    <span>{file.kind} · {formatFileSize(file.size)}</span>
                    <small>{file.analysisHint}</small>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {networkArchitecture === "hybrid_ai" && (
            <label className="agent-questionnaire-note">
              <span>KI-Leitplanke</span>
              <textarea
                disabled={effectiveBusy}
                onChange={(event) => {
                  setArchitectureAiProposal(event.target.value);
                  setArchitectureApproved(false);
                }}
                placeholder="Beschreibe, welche Teilnehmer lokal über eine ECU oder direkt über Gateway/BCM geführt werden sollen."
                rows={3}
                value={architectureAiProposal}
              />
            </label>
          )}
          <label className={`agent-architecture-approval ${architectureApproved ? "approved" : ""}`}>
            <input
              checked={architectureApproved}
              disabled={
                effectiveBusy
                || !selectedArchitecture
                || (networkArchitecture === "hybrid_ai" && !architectureAiProposal.trim())
              }
              onChange={(event) => setArchitectureApproved(event.target.checked)}
              type="checkbox"
            />
            <span>
              <strong>Netzarchitektur verbindlich freigeben</strong>
              <small>Der Schritt kann erst nach Auswahl und ausdrücklicher Freigabe verlassen werden.</small>
            </span>
          </label>
        </fieldset>
      )}
      {activeStepId === "process" && (
        <label className="agent-questionnaire-note">
          <span>Weitere Hinweise</span>
          <textarea
            disabled={busy}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Optional: besondere Protokolle, Safety, Timing, Herstellerlogik ..."
            rows={2}
            value={notes}
          />
        </label>
      )}
      {activeStepId === "task" && (
        <fieldset className="agent-choice-group">
          <legend>Aufgabe</legend>
          <label className="agent-questionnaire-note">
            <span>Aufgabentext</span>
            <textarea
              disabled={busy}
              onChange={(event) => setTaskText(event.target.value)}
              placeholder="Beschreibe das konkrete Ziel, z. B. arbeite bis zur Simulation ..."
              rows={4}
              value={taskText}
            />
          </label>
          <label className="agent-file-drop">
            <input
              accept={SUPPORTED_EVIDENCE_ACCEPT}
              disabled={busy}
              multiple
              onChange={(event) => {
                void handleTaskFiles(event.target.files, "task");
                event.currentTarget.value = "";
              }}
              type="file"
            />
            <span>
              <strong>Text, PDF, PowerPoint oder Bild hinzufügen</strong>
              <small>Text/SVG wird direkt gelesen. PDF, Office und Bilder werden als Evidence in den Auftrag aufgenommen.</small>
            </span>
          </label>
          {taskFiles.length > 0 && (
            <ul className="agent-file-list">
              {taskFiles.map((file) => (
                <li key={`${file.name}-${file.size}`}>
                  {file.previewDataUrl && <img alt="" className="agent-attachment-thumb" src={file.previewDataUrl} />}
                  <span>
                    <strong>{file.name}</strong>
                    <span>{file.kind} · {formatFileSize(file.size)}</span>
                    <small>{file.source === "architecture" ? "Architektur-Evidence" : "Aufgaben-Anlage"}</small>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </fieldset>
      )}
      {activeStepId === "equipment" && (
        <fieldset className="agent-choice-group">
          <legend>Geräteumfang prüfen</legend>
          <table className="agent-equipment-table">
            <thead><tr><th>Gerätetyp</th><th>Anzahl</th></tr></thead>
            <tbody>{EQUIPMENT_CATEGORIES.map(({ key, label }) => (
              <tr key={key}>
                <th scope="row">{label}</th>
                <td>
                  <div className="agent-count-stack">
                    <span><small>Erkannt</small><b>{recognizedEquipment.targetCounts[key]}</b></span>
                    <label>
                      <small>Verbindlich</small>
                      <input aria-label={`${label}: verbindliche Anzahl`} type="number" min="0" max="1000" step="1"
                        value={equipmentValues[key]} disabled={effectiveBusy}
                        onChange={(event) => setEquipmentEdits({ source: taskSource, values: { ...equipmentValues, [key]: event.target.value } })} />
                    </label>
                  </div>
                </td>
              </tr>
            ))}</tbody>
          </table>
          <table className="agent-equipment-table" aria-label="Kommunikationssysteme prüfen">
            <thead><tr><th>Kommunikationssystem</th><th>Anzahl</th></tr></thead>
            <tbody>{communicationSystemRows.map((row) => (
              <tr key={row.id}>
                <th scope="row">
                  {row.label}
                  <small>{row.detail}</small>
                </th>
                <td>
                  <div className="agent-count-stack">
                    <span><small>Erkannt</small><b>{row.recognized}</b></span>
                    <label>
                      <small>Verbindlich</small>
                      <input aria-label={`${row.label}: verbindliche Anzahl`} type="number" min="0" max="1000" step="1"
                        value={row.value} disabled={effectiveBusy}
                        onChange={(event) => setCommunicationSystemEdits({
                          source: communicationSystemSource,
                          values: { ...Object.fromEntries(communicationSystemRows.map((item) => [item.id, item.value])), [row.id]: event.target.value },
                        })} />
                    </label>
                  </div>
                </td>
              </tr>
            ))}</tbody>
          </table>
          {!equipmentReady && <p role="alert">Die Anzahl muss je Gerätetyp zwischen 0 und 1000 liegen. Mindestens ein Gerät ist erforderlich.</p>}
          {!communicationSystemReady && <p role="alert">Die Anzahl der Kommunikationssysteme muss je Technologie zwischen 0 und 1000 liegen.</p>}
          <dl className="agent-equipment-facts">
            <div><dt>Architektur</dt><dd>{selectedArchitecture?.label}</dd></div>
            <div><dt>Kommunikationssysteme im Auftrag</dt><dd>{communicationSystemCounts.map((item) => `${item.label}: ${item.count}`).join(", ") || "Keine vorgegeben"}</dd></div>
            <div><dt>Netzverbindungen geplant</dt><dd>{plannedNetworkConnections}</dd></div>
            <div><dt>Parameter</dt><dd>{parameterMode === "defaults" ? "Technologie-Defaults" : "Nutzerdefiniert"}</dd></div>
          </dl>
          {equipmentClusters.length > 0 && (
            <section className="agent-equipment-clusters" aria-label="Intelligente Systemcluster">
              <div className="agent-equipment-clusters-head">
                <div>
                  <strong>Systemcluster</strong>
                  <span>Fachlich zusammenhaengende Teilnehmer als Vorgabe fuer Netz und Systemrahmen.</span>
                </div>
                <small>{equipmentClusterAssignments.filter((item) => item.selected).length}/{equipmentClusterAssignments.length} aktiv</small>
              </div>
              <table className="agent-equipment-cluster-table">
                <thead>
                  <tr>
                    <th>Cluster</th>
                    <th>Bustechnik</th>
                    <th>Busname</th>
                  </tr>
                </thead>
                <tbody>
                {equipmentClusters.map((cluster) => {
                  const assignment = equipmentClusterAssignments.find((item) => item.cluster_id === cluster.id);
                  const selected = assignment?.selected ?? true;
                  const networkId = assignment?.network_id ?? cluster.recommendedNetworkId;
                  const assignedNetwork = communicationSystemCounts.find((item) => item.id === networkId);
                  const busName = assignment?.bus_name ?? suggestedClusterBusName(cluster.label, 1, (assignedNetwork?.count ?? 0) > 1);
                  const countText = EQUIPMENT_CATEGORIES
                    .map(({ label, type }) => {
                      const count = cluster.counts[type] ?? 0;
                      return count ? `${label}: ${count}` : "";
                    })
                    .filter(Boolean)
                    .join(" · ");
                  return (
                    <tr className={selected ? "selected" : ""} key={cluster.id}>
                      <th scope="row">
                        <label>
                          <input
                            checked={selected}
                            disabled={effectiveBusy}
                            onChange={(event) => {
                              const currentValues = equipmentClusterEdits.source === equipmentClusterSource ? equipmentClusterEdits.values : {};
                              setEquipmentClusterEdits({
                                source: equipmentClusterSource,
                                values: {
                                  ...currentValues,
                                  [cluster.id]: {
                                    ...currentValues[cluster.id],
                                    busName,
                                    selected: event.target.checked,
                                    networkId,
                                  },
                                },
                              });
                            }}
                            type="checkbox"
                          />
                          <span>
                            <strong>{cluster.label}</strong>
                            <small>{countText || `${cluster.devices.length} Teilnehmer`}</small>
                          </span>
                        </label>
                        <p>{cluster.recommendation}</p>
                        <ul aria-label={`${cluster.label}: erkannte Teilnehmer`}>
                          {cluster.evidence.map((name) => <li key={`${cluster.id}:${name}`}>{name}</li>)}
                        </ul>
                      </th>
                      <td>
                        <select
                          aria-label={`${cluster.label}: Bustechnik`}
                          disabled={effectiveBusy || !communicationSystemCounts.length}
                          onChange={(event) => {
                            const currentValues = equipmentClusterEdits.source === equipmentClusterSource ? equipmentClusterEdits.values : {};
                            setEquipmentClusterEdits({
                              source: equipmentClusterSource,
                              values: {
                                ...currentValues,
                                [cluster.id]: {
                                  ...currentValues[cluster.id],
                                  networkId: event.target.value,
                                  selected,
                                },
                              },
                            });
                          }}
                          value={networkId}
                        >
                          {communicationSystemCounts.length
                            ? communicationSystemCounts.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)
                            : <option value="">Noch kein Netz</option>}
                        </select>
                      </td>
                      <td>
                        <input
                          aria-label={`${cluster.label}: vorgeschlagener Busname`}
                          disabled={effectiveBusy}
                          onChange={(event) => {
                            const currentValues = equipmentClusterEdits.source === equipmentClusterSource ? equipmentClusterEdits.values : {};
                            setEquipmentClusterEdits({
                              source: equipmentClusterSource,
                              values: {
                                ...currentValues,
                                [cluster.id]: {
                                  ...currentValues[cluster.id],
                                  busName: event.target.value,
                                  networkId,
                                  selected,
                                },
                              },
                            });
                          }}
                          value={busName}
                        />
                      </td>
                    </tr>
                  );
                })}
                </tbody>
              </table>
            </section>
          )}
          <div className="agent-equipment-list">
            {EQUIPMENT_CATEGORIES.map(({ key, label, type }) => (
              <details key={key}><summary>{label} · {recognizedEquipment.targetCounts[key]}</summary>
                <ul>{recognizedEquipment.chains.filter((chain) => chain.device_type === type)
                  .sort((a, b) => a.hardware_name.localeCompare(b.hardware_name, "de"))
                  .map((chain, index) => <li key={`${chain.device_type}:${chain.hardware_name}:${index}`}>{chain.hardware_name}</li>)}</ul>
              </details>
            ))}
          </div>
        </fieldset>
      )}
      {activeStepId === "status" && submittedContext && (
        <section className="agent-wizard-status" aria-label="Statusübersicht des Engineering-Auftrags">
          <div className="agent-wizard-status-summary">
            <div className="agent-wizard-analysis-summary">
              <span className="eyebrow">Erste Analyse</span>
              <strong>{analysisHeading}</strong>
              <div className="agent-wizard-analysis-counts" aria-label="Gefundene Engineering-Objekte">
                {analysisCounts.map((item) => (
                  <span key={item.label} tabIndex={0}>
                    <small>{item.label}</small>
                    <b>{item.value}</b>
                    <em className="agent-wizard-count-popover">{item.detail}</em>
                  </span>
                ))}
              </div>
              <div className="agent-equipment-list" aria-label="Angelegte Geräte">
                {EQUIPMENT_CATEGORIES.map(({ key, label, type }) => (
                  <details key={key}><summary>{label} · {hardwareDetails[key]}</summary>
                    <ul>{hardwareItems.filter((item) => "device_type" in item && item.device_type === type)
                      .sort((a, b) => String(a.name).localeCompare(String(b.name), "de"))
                      .map((item) => <li key={item.id}>{item.name}</li>)}</ul>
                  </details>
                ))}
              </div>
              <div className="agent-wizard-analysis-actions">
                {routingReviewPending && approvableRoutingCount > 0 && (
                  <button className="button primary tiny" disabled={routingReviewBusy} onClick={() => void approveRoutingAndContinue()} type="button">
                    {routingReviewBusy ? "Freigabe läuft ..." : "Freigeben & fortfahren"}
                  </button>
                )}
                <button className="button secondary tiny" disabled={agentPending || supplementBusy} onClick={() => setSupplementOpen((current) => !current)} type="button">
                  Ergänzen
                </button>
              </div>
            </div>
            <div className="agent-wizard-overall">
              <strong>{overallProgress} %</strong>
              <span>Gesamtfortschritt</span>
              <progress aria-label={`Gesamtfortschritt ${overallProgress} Prozent`} max="100" value={overallProgress} />
            </div>
          </div>

          {supplementOpen && (
            <section className="agent-wizard-supplement" aria-label="Engineering-Auftrag ergänzen">
              <label>
                <span>Ergänzung zur Analyse</span>
                <textarea
                  autoFocus
                  onChange={(event) => setSupplementText(event.target.value)}
                  placeholder="Fehlende Hardware, Funktionen, Signale oder technische Vorgaben ergänzen ..."
                  rows={3}
                  value={supplementText}
                />
              </label>
              <button className="button primary tiny" disabled={!supplementText.trim() || supplementBusy} onClick={() => void submitSupplement()} type="button">
                {supplementBusy ? "Wird analysiert ..." : "Ergänzung analysieren"}
              </button>
            </section>
          )}

          <dl className="agent-wizard-context">
            <div><dt>Aktueller Schritt</dt><dd>{currentStatusStep}</dd></div>
            <div><dt>Parameter</dt><dd>{submittedContext.parameters}</dd></div>
            <div><dt>Arbeitsweise</dt><dd>{submittedContext.process.join(" · ") || "Review-Gate"}</dd></div>
            <div><dt>Lauf-ID</dt><dd className="mono">{submittedContext.run_id}</dd></div>
          </dl>

          <div className="agent-wizard-progress-grid" aria-label="Fortschritt der neun Workflow-Ansichten">
            {statusRows.map((item) => (
              <a
                aria-label={`${item.label} öffnen, Status ${WORKFLOW_DISPLAY_STATUS_LABEL[item.displayStatus]}, ${item.progress} Prozent`}
                className={`agent-wizard-progress-card ${item.selected ? "selected" : ""} status-${item.displayStatus.toLowerCase()}`}
                href={withProjectParam(WORKFLOW_STEP_HREF[item.id], projectId)}
                key={item.id}
                onClick={() => activateEngineeringAgentWizardSession(projectId)}
                title={item.displayStatus === "BLOCKED" ? blockedTitle : `${item.label} öffnen`}
              >
                <div>
                  <span className="agent-wizard-progress-number">{item.position}</span>
                  <strong>{item.label}</strong>
                  <b>{item.progress} %</b>
                </div>
                <progress aria-label={`${item.label}: ${item.progress} Prozent`} max="100" value={item.progress} />
                <small>{item.active ? "Agent arbeitet" : WORKFLOW_DISPLAY_STATUS_LABEL[item.displayStatus]}{item.selected ? " · im Auftrag" : " · nicht gewählt"}</small>
              </a>
            ))}
          </div>

          <section className={`agent-wizard-inline-question ${visibleQuestion ? "required" : ""}`} aria-live="polite">
            {visibleQuestion ? (
              <>
                <div>
                  <span className="eyebrow">Rückfrage erforderlich</span>
                  <strong>{visibleQuestion.text}</strong>
                </div>
                <div className="agent-wizard-inline-answer">
                  <textarea
                    aria-label="Antwort auf die Agentenrückfrage"
                    onChange={(event) => setInlineAnswer(event.target.value)}
                    placeholder="Kurze technische Antwort"
                    rows={2}
                    value={inlineAnswer}
                  />
                  <button className="button primary" disabled={!inlineAnswer.trim() || agentPending} onClick={() => void answerInlineQuestion()} type="button">
                    Antworten
                  </button>
                </div>
              </>
            ) : (
              <div>
                <span className="eyebrow">Rückfragen</span>
                <strong>{routingReviewPending ? "Routing-Review ausstehend" : runPaused ? blockedTitle : "Keine Rückfrage offen"}</strong>
                <small>{routingReviewPending
                  ? `${routingReview.total} Routing-Einträge vorbereitet · ${routingReview.awaitingValidation} noch zu validieren · ${approvableRoutingCount} valide und freigabebereit.`
                  : agentPending
                    ? execution?.state === "RUNNING" ? runMessage : "Der Agent verarbeitet den bestätigten Auftrag."
                    : runPaused
                      ? [
                        runMessage || "Der Lauf wurde beendet, bevor alle ausgewählten Schritte abgeschlossen waren.",
                        documentedDeviationSummary ? `Dokumentiert: ${documentedDeviationSummary}` : "",
                      ].filter(Boolean).join(" ")
                      : currentRunMessages.length || workflowHasProgress
                        ? "Die ausgewählten Arbeitsschritte sind abgeschlossen."
                        : "Der Auftrag wird an den Agenten übergeben."}</small>
                {canRetryPopupRun && (
                  <button className="button primary tiny" onClick={() => void retryPopupRun()} type="button">
                    Auftrag fortsetzen
                  </button>
                )}
              </div>
            )}
          </section>

          <div className="agent-wizard-runtime" aria-label="Lokale Laufzeitauslastung">
            <span><small>CPU</small><strong>{performance ? `${performance.cpu_percent} %` : "..."}</strong></span>
            <span><small>RAM</small><strong>{performance ? `${performance.memory_percent} %` : "..."}</strong></span>
            <span><small>GPU</small><strong>{performance?.gpu ? `${performance.gpu.utilization_percent} %` : "n/a"}</strong></span>
            <span><small>VRAM</small><strong>{performance?.gpu ? `${performance.gpu.memory_used_mb}/${performance.gpu.memory_total_mb} MB` : "n/a"}</strong></span>
            <span><small>Analyse</small><strong>{activeAnalysis}</strong></span>
            <span><small>LLM</small><strong>{activeModel}</strong></span>
          </div>

          {displayedStatusError && <p className="notice error" role="alert">{displayedStatusError}</p>}
          <footer className="agent-wizard-status-footer">
            <small className="agent-wizard-log-status">TXT-Protokolle aktiv: Workflow · Rückfragen · Performance · Fehler</small>
            <div className="agent-wizard-status-actions">
              <button className="button secondary" disabled={cancelBusy || (!agentPending && execution?.state !== "RUNNING")} onClick={() => void cancelWizardRun()} type="button">
                {cancelBusy ? "Breche ab..." : "Abbrechen"}
              </button>
              <button className="button primary" disabled={agentPending || routingReviewBusy || supplementBusy || routingReviewPending || runPaused || cancelBusy} onClick={() => void finishWizard()} type="button">
                Fertig stellen
              </button>
            </div>
          </footer>
        </section>
      )}
      {phase === "questionnaire" && (
        <div className="agent-questionnaire-nav">
          <button className="button secondary tiny" disabled={effectiveBusy || step === 0} onClick={() => setStep((current) => Math.max(current - 1, 0))} type="button">
            Zurück
          </button>
          <span>{activeStepId === "task"
            ? taskReady ? "Aufgabe bereit" : "Aufgabe fehlt"
            : activeStepId === "equipment"
              ? equipmentReady && communicationSystemReady ? "Sollzahlen bereit" : "Anzahlen prüfen"
            : activeStepId === "architecture"
              ? architectureReady ? "Verbindlich freigegeben" : selectedArchitecture ? "Freigabe fehlt" : "Auswahl erforderlich"
              : activeGroup
                ? `${selectedFor(activeGroup).length} ausgewählt`
                : parameterMode === "defaults" ? "Defaults ausgewählt" : "Eigene Werte ausgewählt"}</span>
        </div>
      )}
    </section>
  );
}

function toggleSelection(values: string[], optionId: string) {
  return values.includes(optionId) ? values.filter((id) => id !== optionId) : [...values, optionId];
}

function mergeTaskAttachments(current: TaskAttachment[], incoming: TaskAttachment[]) {
  const merged = [...current];
  incoming.forEach((attachment) => {
    const index = merged.findIndex((item) => item.name === attachment.name && item.size === attachment.size);
    if (index >= 0) {
      merged[index] = attachment;
    } else {
      merged.push(attachment);
    }
  });
  return merged.slice(-MAX_TASK_ATTACHMENTS);
}

async function readTaskAttachment(file: File, source: TaskAttachment["source"]): Promise<TaskAttachment> {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const kind = attachmentKind(file, extension);
  const analysisHint = attachmentAnalysisHint(kind, extension, source);
  const canReadAsText = file.type.startsWith("text/") || ["txt", "md", "csv", "json", "svg"].includes(extension);
  const previewDataUrl = file.type.startsWith("image/") && extension !== "svg" && file.size <= 2 * 1024 * 1024
    ? await readAttachmentPreview(file)
    : undefined;
  if (!canReadAsText) {
    return { analysisHint, kind, name: file.name, previewDataUrl, size: file.size, source };
  }
  try {
    const content = await file.text();
    return {
      analysisHint,
      content: content.slice(0, 12000),
      kind,
      name: file.name,
      previewDataUrl,
      size: file.size,
      source,
    };
  } catch {
    return { analysisHint, kind, name: file.name, previewDataUrl, size: file.size, source };
  }
}

function formatTaskAttachment(file: TaskAttachment) {
  const source = file.source === "architecture" ? "Architektur-Evidence" : "Aufgaben-Anlage";
  const base = `- ${source}: ${file.name} (${file.kind}, ${formatFileSize(file.size)})`;
  if (!file.content) return `${base}: ${file.analysisHint}`;
  return `${base}: ${file.analysisHint}\n${file.content}`;
}

function attachmentKind(file: File, extension: string) {
  if (file.type) return file.type;
  const knownKinds: Record<string, string> = {
    bmp: "image/bmp",
    csv: "text/csv",
    doc: "application/msword",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    gif: "image/gif",
    jpeg: "image/jpeg",
    jpg: "image/jpeg",
    json: "application/json",
    md: "text/markdown",
    pdf: "application/pdf",
    png: "image/png",
    ppt: "application/vnd.ms-powerpoint",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    svg: "image/svg+xml",
    txt: "text/plain",
    webp: "image/webp",
  };
  return knownKinds[extension] ?? (extension.toUpperCase() || "Datei");
}

function attachmentAnalysisHint(kind: string, extension: string, source: TaskAttachment["source"]) {
  const scope = source === "architecture"
    ? "als Architektur-Evidence fuer Netzvarianten, Cluster, Knoten, Interfaces und Verbindungen auswerten"
    : "als Aufgabenquelle fuer Umfang, Anforderungen und technische Vorgaben auswerten";
  if (kind.startsWith("image/")) {
    return `Bild/Screenshot/Diagramm ${scope}; erkennbare Beschriftungen, Topologie und Gruppierungen beruecksichtigen.`;
  }
  if (/pdf/i.test(kind) || extension === "pdf") {
    return `PDF ${scope}; Diagramme, Tabellen und Begleittext als fachliche Vorgabe behandeln.`;
  }
  if (/presentation|powerpoint/i.test(kind) || ["ppt", "pptx"].includes(extension)) {
    return `PowerPoint ${scope}; Folien, Architektur-Skizzen und Tabellen als fachliche Vorgabe behandeln.`;
  }
  if (/word/i.test(kind) || ["doc", "docx"].includes(extension)) {
    return `Word-Dokument ${scope}; Anforderungen und Tabellen als fachliche Vorgabe behandeln.`;
  }
  return `Textinhalt ${scope}.`;
}

function readAttachmentPreview(file: File) {
  return new Promise<string | undefined>((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : undefined);
    reader.onerror = () => resolve(undefined);
    reader.readAsDataURL(file);
  });
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function defaultTechnologyIds(domain?: TechnologyDomain) {
  if (!domain) return [];
  const ids = domain.technologies.map((technology) => technology.id);
  const preferredByDomain: Record<string, string[]> = {
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
  const preferred = (preferredByDomain[domain.id] ?? []).filter((id) => ids.includes(id));
  return preferred.length ? preferred : ids.slice(0, 4);
}

function technologyLabel(id: string, family: string) {
  return family && family.toLowerCase() !== id.replaceAll("_", " ").toLowerCase()
    ? `${family} · ${id}`
    : id.replaceAll("_", " ").toUpperCase();
}

function isCanTechnology(id: string, family: string) {
  const raw = `${id} ${family}`.toLowerCase();
  return /\bcan\b/.test(raw) || raw.includes("can_") || raw.includes("can-") || raw.includes("canfd");
}

type CommunicationSystemInputRow = {
  detail: string;
  id: string;
  label: string;
  recognized: number;
  value: string;
};

function normalizedCommunicationSystem(value: string) {
  const normalized = value
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const compact = normalized.replace(/\s+/g, "");
  if (compact === "canfd" || compact === "automotivecanfd") return "can fd";
  if (compact === "automotiveethernet") return "ethernet";
  if (compact === "modbustcp") return "modbus tcp";
  if (compact === "opcua") return "opc ua";
  if (compact === "ros2dds") return "ros2 dds";
  return normalized;
}

function communicationSystemSlug(value: string) {
  return normalizedCommunicationSystem(value).replace(/\s+/g, "-") || "system";
}

function communicationAliases(value: string) {
  const base = normalizedCommunicationSystem(value);
  const compact = base.replace(/\s+/g, "");
  const aliases = new Set([base, compact]);
  if (compact === "canfd") aliases.add("can fd");
  if (compact === "can") aliases.add("automotive can");
  if (compact === "lin") aliases.add("automotive lin");
  if (compact === "ethernet") aliases.add("automotive ethernet");
  if (compact === "someip") aliases.add("some ip");
  if (compact === "opcua") aliases.add("opc ua");
  if (compact === "ros2dds") aliases.add("ros2 dds");
  return aliases;
}

function technologyMatchesRecognizedSystem(technology: Technology, recognized: string) {
  const recognizedAliases = communicationAliases(recognized);
  const candidates = [technology.id, technology.family, technologyLabel(technology.id, technology.family)];
  return candidates.some((candidate) => (
    [...communicationAliases(candidate)].some((alias) => recognizedAliases.has(alias))
  ));
}

function communicationSystemInputRows(args: {
  edits: Record<string, string>;
  recognizedSystemCounts: Record<string, number>;
  recognizedSystems: string[];
  selectedTechnologyIds: string[];
  technologies: Technology[];
}): CommunicationSystemInputRow[] {
  const selected = new Set(args.selectedTechnologyIds);
  const selectedTechnologies = args.technologies.filter((technology) => selected.has(technology.id));
  const technologies = selectedTechnologies.length ? selectedTechnologies : args.technologies.slice(0, 4);
  const representedRecognized = new Set<string>();
  const rows = technologies.map((technology) => {
    const matches = args.recognizedSystems.filter((system) => technologyMatchesRecognizedSystem(technology, system));
    matches.forEach((system) => representedRecognized.add(system));
    const recognized = matches.reduce((sum, system) => sum + (args.recognizedSystemCounts[system] ?? 1), 0);
    const label = technologyLabel(technology.id, technology.family);
    return {
      detail: `${technology.medium} · ${technology.topology}`,
      id: technology.id,
      label,
      recognized,
      value: args.edits[technology.id] ?? String(Math.max(1, recognized)),
    };
  });

  args.recognizedSystems.forEach((system) => {
    if (representedRecognized.has(system)) return;
    const id = `detected:${communicationSystemSlug(system)}`;
    const recognized = args.recognizedSystemCounts[system] ?? 1;
    const existing = rows.find((row) => row.id === id);
    if (existing) {
      existing.recognized += recognized;
      if (args.edits[id] === undefined) existing.value = String(existing.recognized);
      return;
    }
    rows.push({
      detail: "Aus Aufgaben-/Dateitext erkannt",
      id,
      label: system,
      recognized,
      value: args.edits[id] ?? String(recognized),
    });
  });

  return rows;
}

function plannedNetworkConnectionCount(args: {
  architectureId?: NetworkArchitectureId;
  clusterAssignments: EquipmentClusterAssignment[];
  equipmentCounts: EngineeringHardwareCounts;
}) {
  const participantConnections = args.equipmentCounts.ecus + args.equipmentCounts.sensors + args.equipmentCounts.actuators;
  const selectedClusterDevices = args.clusterAssignments
    .filter((assignment) => assignment.selected)
    .reduce((sum, assignment) => sum + Math.max(0, Number(assignment.devices) || 0), 0);
  if (args.architectureId === "hybrid_ai") return Math.max(selectedClusterDevices, participantConnections);
  if (args.architectureId === "gateway_ecu_segments") {
    const ecuSegments = Math.ceil(Math.max(0, args.equipmentCounts.ecus) / 6);
    return args.equipmentCounts.sensors + args.equipmentCounts.actuators + ecuSegments;
  }
  if (args.architectureId === "sensor_ecu_actuator") return args.equipmentCounts.sensors + args.equipmentCounts.actuators;
  if (args.architectureId === "ecu_gateway") return args.equipmentCounts.sensors + args.equipmentCounts.actuators + args.equipmentCounts.ecus;
  return participantConnections;
}

function scopeMismatchSummaries(value: unknown) {
  if (!value || typeof value !== "object") return [];
  const labels: Record<string, string> = {
    actuators: "Aktoren",
    ecus: "ECUs",
    gateways: "Gateways",
    sensors: "Sensoren",
    hardware_nodes: "Hardware-Knoten",
    functions: "Funktionen",
    hardware_interfaces: "Hardware-Interfaces",
    interfaces: "Logische Interfaces",
    messages: "Nachrichten",
    signals: "Signale",
  };
  return Object.entries(value as Record<string, { actual?: number; target?: number }>).flatMap(([key, item]) => {
    const actual = Number(item?.actual);
    const target = Number(item?.target);
    if (!Number.isFinite(actual) || !Number.isFinite(target) || actual === target) return [];
    const missing = Math.max(0, target - actual);
    const surplus = Math.max(0, actual - target);
    const delta = missing > 0 ? `${missing} fehlen` : `${surplus} zu viel`;
    return [`${labels[key] ?? key}: ${actual}/${target}, ${delta}`];
  });
}

function documentedScopeDeviationSummary(value: unknown) {
  if (!value || typeof value !== "object") return "";
  const deviation = (value as Record<string, unknown>).scope_deviation;
  if (!deviation || typeof deviation !== "object") return "";
  const record = deviation as Record<string, unknown>;
  const summary = typeof record.summary === "string" ? record.summary.trim() : "";
  if (summary) return summary;
  const deviations = Array.isArray(record.deviations) ? record.deviations : [];
  return deviations.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const entry = item as Record<string, unknown>;
    const label = String(entry.label ?? entry.key ?? "").trim();
    const actual = Number(entry.actual);
    const target = Number(entry.target);
    if (!label || !Number.isFinite(actual) || !Number.isFinite(target)) return [];
    return [`${label} ${actual}/${target}`];
  }).join("; ");
}

function AgentActivityLog({ entries }: { entries: AgentActivityEntry[] }) {
  return (
    <details className="eng-agent-activity" aria-label="Agent Aktivitätsprotokoll">
      <summary>
        <span>Aktivitätsprotokoll</span>
        <small>{entries.length} Schritte</small>
      </summary>
      <ol>
        {entries.map((entry) => (
          <li className={`activity-${entry.kind}`} key={entry.id}>
            <strong>{entry.title}</strong>
            <span>{entry.detail}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

function buildAgentActivity(messages: EngineeringAgentUIMessage[], busy: boolean, error?: string): AgentActivityEntry[] {
  const entries: AgentActivityEntry[] = [];
  messages.forEach((message, messageIndex) => {
    if (message.role === "user") {
      const text = textFromParts(message.parts);
      entries.push({
        id: `${message.id}-request`,
        kind: "request",
        title: "Anfrage empfangen",
        detail: text ? trimActivityText(text) : "Benutzeranfrage wurde an den Engineering-Agenten gesendet.",
      });
      if (text) {
        const goal = inferAgentGoal(text);
        entries.push({
          id: `${message.id}-goal`,
          kind: "goal",
          title: "Ziel erkannt",
          detail: goal,
        });
        entries.push({
          id: `${message.id}-assumption`,
          kind: "assumption",
          title: "Arbeitsannahme",
          detail: inferAgentAssumption(text, goal),
        });
      }
      return;
    }

    message.parts.forEach((part, partIndex) => {
      if (part.type === "text") {
        const text = trimActivityText(part.text);
        if (text) entries.push({ id: `${message.id}-answer-${partIndex}`, kind: "answer", title: "Antwort formuliert", detail: text });
        return;
      }
      if (part.type.startsWith("tool-")) {
        const toolPart = part as { type: string; state: string; input?: unknown; output?: unknown; errorText?: string };
        const detail = toolActivityDetail(toolPart);
        entries.push({
          id: `${message.id}-tool-${partIndex}`,
          kind: toolPart.state === "output-error" ? "error" : "tool",
          title: toolLabel(toolPart.type),
          detail: `${toolPurpose(toolPart.type)} ${detail}`,
        });
        if (toolPart.state === "output-available") {
          entries.push({
            id: `${message.id}-decision-${partIndex}`,
            kind: "decision",
            title: "Ergebnis bewertet",
            detail: toolOutcomeDecision(toolPart.type, toolPart.output),
          });
        }
      }
    });

    if (message.parts.length === 0) {
      entries.push({ id: `${message.id}-empty-${messageIndex}`, kind: "status", title: "Agent gestartet", detail: "Der Agent bereitet die Antwort vor." });
    }
  });
  if (busy) entries.push({ id: "current-status", kind: "status", title: "In Arbeit", detail: "Der Agent liest Kontext, ruft Werkzeuge auf oder formuliert die Antwort." });
  if (error) entries.push({ id: "current-error", kind: "error", title: "Fehler", detail: error });
  return entries.slice(-18);
}

function historicalToolResultKeys(messages: EngineeringAgentUIMessage[]) {
  const keys = new Set<string>();
  messages.forEach((message) => {
    message.parts.forEach((part, index) => {
      if (!part.type.startsWith("tool-")) return;
      const toolPart = part as { state: string; toolCallId?: string };
      if (toolPart.state !== "output-available") return;
      keys.add(toolPart.toolCallId ?? `${message.id}:${index}`);
    });
  });
  return keys;
}

function findPendingConfirmation(messages: EngineeringAgentUIMessage[]) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === "user") return null;
    if (message.role !== "assistant") continue;
    const text = textFromParts(message.parts);
    if (inspectAgentText(text).blocked) {
      return { messageId: message.id, proposalCount: 0, recovery: true };
    }
    let proposalCount = 0;
    let routingProposalCount = 0;
    let routingDraftCount = 0;
    let approvedInMessage = false;
    for (const part of message.parts) {
      if (!part.type.startsWith("tool-")) continue;
      const toolPart = part as { type: string; state: string; output?: unknown };
      if (toolPart.state !== "output-available") continue;
      if (toolPart.type.includes("approveEngineeringProposal") || toolPart.type.includes("approveAllValidEngineeringProposals")) {
        approvedInMessage = true;
      }
      if (toolPart.type === "tool-proposeEngineeringObject" || toolPart.type === "tool-proposeEngineeringRelation") {
        const output = toolPart.output && typeof toolPart.output === "object"
          ? toolPart.output as Record<string, unknown>
          : {};
        const canonicalObjects = Array.isArray(output.canonical_objects) ? output.canonical_objects : [];
        const proposal = output.proposal && typeof output.proposal === "object"
          ? output.proposal as Record<string, unknown>
          : {};
        if (!canonicalObjects.length && proposal.status !== "APPROVED") proposalCount += 1;
      }
      if (toolPart.type === "tool-inspectEngineeringProposals" && toolPart.output && typeof toolPart.output === "object") {
        const items = (toolPart.output as { items?: unknown[] }).items ?? [];
        proposalCount += items.filter((item) => {
          if (!item || typeof item !== "object") return false;
          return !["APPROVED", "REJECTED", "SUPERSEDED"].includes(
            String((item as Record<string, unknown>).status ?? ""),
          );
        }).length;
      }
      if (toolPart.type === "tool-create_route_proposal" && toolPart.output && typeof toolPart.output === "object") {
        const output = toolPart.output as Record<string, unknown>;
        if (output.routing_table_populated === true) {
          routingDraftCount += Number(output.draft_route_count ?? output.accepted_route_count ?? output.route_count ?? 0);
        } else if (output.ready_for_review === true) {
          routingProposalCount += Number(output.proposal_count ?? 1);
        }
      }
    }
    if (approvedInMessage) return null;
    if (routingDraftCount > 0) {
      return { messageId: message.id, proposalCount: routingDraftCount, routingReview: true, routingDrafts: true };
    }
    if (routingProposalCount > 0) {
      return { messageId: message.id, proposalCount: routingProposalCount, routingReview: true };
    }
    if (proposalCount > 0) return { messageId: message.id, proposalCount };
    const normalizedText = text.toLowerCase();
    if (normalizedText.includes("bitte bestätigen") || normalizedText.includes("soll ich") || normalizedText.includes("möchtest du")) {
      return { messageId: message.id, proposalCount: 0 };
    }
  }
  return null;
}

function textFromParts(parts: EngineeringAgentUIMessage["parts"]) {
  return parts.filter((part) => part.type === "text").map((part) => part.text).join(" ");
}

function agentErrorText(value: string) {
  if (/11434|ollama|lokale ai-dienst/i.test(value)) return "Der lokale AI-Dienst ist vorübergehend nicht erreichbar.";
  if (/database|datenbank|pooltimeout|psycopg/i.test(value)) return "Die Engineering-Datenbank ist vorübergehend nicht erreichbar.";
  if (/timeout|zeitlimit/i.test(value)) return "Die Agentenanfrage hat ihr Zeitlimit überschritten.";
  return value.trim() || "Der Agent konnte nicht antworten.";
}

function AgentFeedbackControls({
  messageId,
  projectId,
  prompt,
  response,
}: {
  messageId: string;
  projectId: string;
  prompt: string;
  response: string;
}) {
  const [mode, setMode] = useState<"idle" | "incorrect" | "saved">("idle");
  const [correction, setCorrection] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");

  async function save(rating: "helpful" | "incorrect") {
    setBusy(true);
    setFeedbackError("");
    try {
      const result = await fetch("/api/agent/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Project-ID": projectId },
        body: JSON.stringify({ messageId, prompt, response, rating, correction }),
      });
      if (!result.ok) throw new Error("Feedback konnte nicht gespeichert werden.");
      setMode("saved");
    } catch (error) {
      setFeedbackError(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  if (mode === "saved") return <small className="eng-agent-feedback-saved">Feedback gespeichert und lokal gelernt.</small>;

  return (
    <div className="eng-agent-feedback">
      {mode === "idle" ? (
        <>
          <span>Antwort bewerten</span>
          <button className="button secondary tiny" disabled={busy} onClick={() => void save("helpful")} type="button">Hilfreich</button>
          <button className="button secondary tiny" disabled={busy} onClick={() => setMode("incorrect")} type="button">Falsch</button>
        </>
      ) : (
        <>
          <input
            aria-label="Korrektur für den Agenten"
            onChange={(event) => setCorrection(event.target.value)}
            placeholder="Korrektur (optional)"
            value={correction}
          />
          <button className="button secondary tiny" disabled={busy} onClick={() => void save("incorrect")} type="button">Speichern</button>
        </>
      )}
      {feedbackError && <small className="notice error">{feedbackError}</small>}
    </div>
  );
}

function latestUserRequestBefore(messages: EngineeringAgentUIMessage[], messageId: string) {
  const confirmationIndex = messages.findIndex((message) => message.id === messageId);
  const end = confirmationIndex >= 0 ? confirmationIndex : messages.length;
  for (let index = end - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "user") continue;
    const text = textFromParts(message.parts).trim();
    if (text) return text;
  }
  return "";
}

function isInlineConfirmation(text: string) {
  return /^(?:ok|okay|passt|das passt|so passt|passt so|ja|jawohl|bitte|mach das|mach es|erstelle dies|erstelle das|leg das an|lege das an|lege dies an|umsetzen|anwenden|freigeben|uebernehmen|übernehmen|jetzt uebernehmen|jetzt übernehmen|so uebernehmen|so übernehmen)(?:[.! ]*)$/i.test(text.trim());
}

function buildInlineConfirmationPrompt(text: string, messages: EngineeringAgentUIMessage[]) {
  const latestAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  const originalRequest = latestAssistant ? latestUserRequestBefore(messages, latestAssistant.id) : "";
  return [
    `Der Nutzer bestaetigt die vorherige Analyse mit: ${text}`,
    originalRequest ? `Vorheriger Auftrag: ${originalRequest}` : "Der vorherige Auftrag steht im Agentenverlauf.",
    "Arbeite jetzt an der Loesung im aktuellen Simulatorprojekt. Lies den aktuellen Workflow- und Engineering-Kontext, uebernimm ableitbare Modell-, Routing-, Parameter- oder Workflow-Aenderungen mit den bereitgestellten Simulator-Tools, validiere danach erneut und melde registrierte Ergebnisse. Wenn aus dem Verlauf keine belastbare umsetzbare Aenderung ableitbar ist, benenne genau diesen Blocker knapp.",
    "Starte keinen neuen Task.",
  ].join("\n\n");
}

function hasCompactEngineeringResult(parts: EngineeringAgentUIMessage["parts"]) {
  return parts.some((part) => (
    part.type === "tool-createEngineeringChain"
    || part.type === "tool-createEngineeringModelFromSpecification"
    || part.type === "tool-createRoutableEngineeringPair"
    || part.type === "tool-proposeEngineeringObject"
    || part.type === "tool-proposeEngineeringRelation"
  ));
}

function canonicalObjectsFromToolOutput(output: unknown) {
  if (!output || typeof output !== "object") return [];
  const items = (output as { canonical_objects?: unknown[] }).canonical_objects;
  if (!Array.isArray(items)) return [];
  const resources = new Set<EngineeringResource | "relations">([
    "hardware-nodes",
    "functions",
    "interfaces",
    "messages",
    "signals",
    "relations",
  ]);
  const canonicalObjects = items.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const value = item as Record<string, unknown>;
    const resource = String(value.resource ?? "") as EngineeringResource | "relations";
    const id = String(value.id ?? "");
    if (!resources.has(resource) || !id) return [];
    return [{ resource, id, name: String(value.name ?? "Engineering-Objekt") }];
  });
  return [...new Map(canonicalObjects.map((item) => [`${item.resource}:${item.id}`, item])).values()];
}

function trimActivityText(text: string) {
  const normalized = text.replace(/\s+/g, " ").trim();
  return normalized.length > 150 ? `${normalized.slice(0, 147)}...` : normalized;
}

function toolLabel(type: string) {
  const name = type.replace("tool-", "");
  const labels: Record<string, string> = {
    listEngineeringObjects: "Engineering-Objekte gelesen",
    listEngineeringRelations: "Engineering-Relationen gelesen",
    createEngineeringChain: "Engineering-Kette registriert",
    createEngineeringModelFromSpecification: "Spezifikation ins Engineering-Modell übernommen",
    createEngineeringSignalsBatch: "Signal-Batch registriert",
    createRoutableEngineeringPair: "Routing-Paket registriert",
    proposeEngineeringObject: "Engineering-Objekt registriert",
    proposeEngineeringRelation: "Engineering-Relation registriert",
    inspectEngineeringProposals: "Engineering-Vorschläge gelesen",
    validateEngineeringProposal: "Engineering-Vorschlag validiert",
    approveEngineeringProposal: "Engineering-Vorschlag übernommen",
    approveAllValidEngineeringProposals: "Valide Vorschläge übernommen",
    inspectRoutingTable: "Routing-Tabelle geprüft",
    inspectRoute: "Route inspiziert",
    createRouteProposal: "Routingvorschlag erzeugt",
    validateRoutingTable: "Routing-Tabelle validiert",
    validateRoute: "Route validiert",
    inspectRoutePath: "Routingpfad geprüft",
    inspectRouteEvidence: "Nachweise geprüft",
    inspectWorkflow: "Workflow-Status gelesen",
    inspectCapacity: "Kapazität geprüft",
    inspectPreflight: "Preflight geprüft",
    inspectTopology: "Topologie gelesen",
    inspectNetwork: "Netzwerk geprüft",
  };
  return labels[name] ?? name.replaceAll("_", " ");
}

function inferAgentGoal(text: string) {
  const lower = text.toLowerCase();
  if (lower.includes("routing") || lower.includes("route") || lower.includes("pfad")) return "Routing-Kontext prüfen und eine fachlich valide Kommunikationsroute oder Diagnose liefern.";
  if (lower.includes("hardware") || lower.includes("knoten") || lower.includes("ecu") || lower.includes("sensor")) return "Engineering-Hardware im aktiven Projekt lesen und verständlich zusammenfassen.";
  if (lower.includes("interface") || lower.includes("schnittstelle") || lower.includes("can") || lower.includes("ethernet")) return "Schnittstellen und Bus-Technik im Engineering-Modell prüfen.";
  if (lower.includes("valid") || lower.includes("fehler") || lower.includes("konflikt") || lower.includes("preflight")) return "Technische Befunde finden, Ursache benennen und nächste Reparaturentscheidung ableiten.";
  if (lower.includes("kapaz") || lower.includes("latenz") || lower.includes("jitter") || lower.includes("timing")) return "Capacity- und Timing-Daten auswerten und Engpässe erklären.";
  if (lower.includes("vorschlag") || lower.includes("erstelle") || lower.includes("schlage")) return "Engineering-Inhalte mit Auditspur erzeugen und valide Ergebnisse direkt im kanonischen Modell registrieren.";
  return "Nutzerfrage im aktiven Projektkontext beantworten und dafür benötigte Engineering-Daten lesen.";
}

function inferAgentAssumption(text: string, goal: string) {
  const lower = text.toLowerCase();
  if (goal.includes("Proposal") || lower.includes("neu") || lower.includes("erstelle") || lower.includes("schlage")) {
    return "Neue Engineering-Inhalte werden als Proposal auditiert, validiert und unmittelbar kanonisch registriert.";
  }
  if (lower.includes("aktuell") || lower.includes("jetzt") || lower.includes("status")) {
    return "Der Agent nutzt den aktiven Projekt- und Workflow-Kontext als maßgebliche Quelle.";
  }
  if (lower.includes("warum") || lower.includes("fehler") || lower.includes("konflikt")) {
    return "Der Agent soll zuerst vorhandene Befunde und Nachweise lesen, bevor er eine Ursache behauptet.";
  }
  return "Bestehende Projektobjekte haben Vorrang vor Vermutungen; fehlende IDs sollen über Lese-Tools gesucht werden.";
}

function toolPurpose(type: string) {
  const name = type.replace("tool-", "");
  const purposes: Record<string, string> = {
    inspect_workflow: "Warum: aktiven Workflow, Projekt und Selektion feststellen.",
    listEngineeringObjects: "Warum: vorhandene Modellobjekte prüfen, bevor neue Vorschläge entstehen.",
    listEngineeringRelations: "Warum: Beziehungen im Engineering-Graphen nachvollziehen.",
    createEngineeringChain: "Warum: die vollständige Elternkette bis zum Signal in einem konsistenten Lauf registrieren.",
    createEngineeringSignalsBatch: "Warum: eine große, bestätigte Signalmenge deterministisch, kollisionsfrei und mit gemeinsamer Auditspur registrieren.",
    createRoutableEngineeringPair: "Warum: Producer, Consumer, Payload und Routingvorschlag in einem konsistenten Lauf registrieren.",
    proposeEngineeringObject: "Warum: neues Objekt auditieren, validieren und kanonisch registrieren.",
    proposeEngineeringRelation: "Warum: neue Beziehung auditieren, validieren und kanonisch registrieren.",
    inspectEngineeringProposals: "Warum: offene Vorschläge für die Übernahme ins Modell prüfen.",
    validateEngineeringProposal: "Warum: Vorschlag technisch prüfen, bevor echte Objekte angelegt werden.",
    approveEngineeringProposal: "Warum: bestätigten Vorschlag ins kanonische Modell übernehmen.",
    approveAllValidEngineeringProposals: "Warum: bestätigte valide Vorschläge gesammelt ins Modell übernehmen.",
    inspect_routing_table: "Warum: Routen, Status und Konflikte als Grundlage lesen.",
    inspect_route: "Warum: Details der ausgewählten Route prüfen.",
    validate_route: "Warum: technische Konsistenz der Route bewerten.",
    validate_routing_table: "Warum: Routing-Tabelle gesamthaft auf Befunde prüfen.",
    inspect_route_path: "Warum: physischen/logischen Pfad und Nachweise prüfen.",
    show_route_evidence: "Warum: technische Evidenz für die Route sichtbar machen.",
    create_route_proposal: "Warum: Routingänderung als Proposal erzeugen, nicht direkt freigeben.",
    inspect_capacity_timing: "Warum: Last, Latenz und Timing aus dem berechneten Snapshot lesen.",
    inspect_preflight: "Warum: Preflight-Befunde vor Simulation prüfen.",
    inspect_intelligence: "Warum: deterministische Systembewertung und Empfehlungen lesen.",
  };
  return purposes[name] ?? "Warum: benötigten Projektkontext lesen oder einen prüfbaren Vorschlag erzeugen.";
}

function toolOutcomeDecision(type: string, output: unknown) {
  if (!output || typeof output !== "object") return "Ergebnis ist unstrukturiert; der Agent muss es vorsichtig zusammenfassen.";
  const value = output as Record<string, unknown>;
  if (value.blocked === true) {
    return `Schritt ist blockiert: ${String(value.reason ?? "Voraussetzungen fehlen.")}`;
  }
  if (Array.isArray(value.canonical_objects)) {
    return `${value.canonical_objects.length} Engineering-${value.canonical_objects.length === 1 ? "Eintrag wurde" : "Einträge wurden"} kanonisch registriert.`;
  }
  if (typeof value.valid === "boolean") {
    return value.valid ? "Validierung bestanden; Freigabe oder nächster Workflow-Schritt ist möglich." : "Validierung hat Befunde; Ursache und Reparaturschritt müssen benannt werden.";
  }
  if (typeof value.count === "number") {
    return value.count > 0 ? "Datenbasis vorhanden; der Agent kann darauf weiterarbeiten." : "Keine Treffer; der Agent sollte fehlende Angaben erfragen oder breiter suchen.";
  }
  if (type.includes("approve") && Array.isArray(value.items)) {
    return `${value.items.length} Vorschlag/Vorschläge wurden ins Modell übernommen.`;
  }
  if (Array.isArray(value.items)) {
    return value.items.length > 0 ? "Objekte gefunden; Auswahl oder Zusammenfassung kann erfolgen." : "Keine Objekte gefunden; Annahmen müssen vermieden werden.";
  }
  if (value.proposal || value.proposal_id) return "Proposal-Auditspur wurde gespeichert; der Registrierungsstatus muss aus dem Ergebnis gelesen werden.";
  if (typeof value.status === "string") return `Status '${value.status}' gelesen; nächste Antwort muss diesen Status berücksichtigen.`;
  const name = type.replace("tool-", "");
  if (name.includes("inspect")) return "Kontext wurde gelesen; der Agent sollte daraus eine konkrete Aussage ableiten.";
  return "Werkzeuglauf abgeschlossen; der Agent entscheidet daraus den nächsten Schritt.";
}

function toolActivityDetail(part: { state: string; input?: unknown; output?: unknown; errorText?: string }) {
  if (part.state === "input-streaming" || part.state === "input-available") return `läuft${summarizeToolInput(part.input)}`;
  if (part.state === "output-available") return summarizeToolOutput(part.output);
  if (part.state === "output-error") return part.errorText ?? "Werkzeugaufruf fehlgeschlagen.";
  return `Status: ${part.state}.`;
}

function summarizeToolInput(input: unknown) {
  if (!input || typeof input !== "object") return ".";
  const value = input as Record<string, unknown>;
  const hints = [
    typeof value.resource === "string" ? value.resource : "",
    typeof value.route_id === "string" ? `Route ${value.route_id}` : "",
    typeof value.section === "string" ? value.section : "",
    typeof value.query === "string" ? trimActivityText(value.query) : "",
  ].filter(Boolean);
  return hints.length ? `: ${hints.join(" · ")}.` : ".";
}

function MessagePart({
  hideText = false,
  part,
  projectId,
  richText = false,
}: {
  hideText?: boolean;
  part: EngineeringAgentUIMessage["parts"][number];
  projectId: string;
  richText?: boolean;
}) {
  const runtimePart = part as unknown as {
    errorText?: string;
    input?: unknown;
    output?: unknown;
    state?: string;
    toolName?: string;
    type: string;
  };
  if (part.type === "text") {
    const text = inspectAgentText(part.text).displayText;
    if (hideText || !text) return null;
    return richText ? <AgentMessageText text={text} /> : <p className="eng-agent-text">{text}</p>;
  }

  if (part.type === "tool-listEngineeringObjects" || part.type === "tool-listEngineeringRelations") {
    return null;
  }

  if (part.type === "tool-proposeEngineeringObject") {
    return <ObjectStatusRow part={part} />;
  }

  if (part.type === "tool-createEngineeringChain" || part.type === "tool-createRoutableEngineeringPair") {
    return <EngineeringChainStatusRows part={part} />;
  }

  if (part.type === "tool-proposeEngineeringRelation") {
    return <ToolCallCard details={false} label="Relation modelliert" part={part} projectId={projectId} />;
  }

  if (
    (runtimePart.type === "tool-createEngineeringSignalsBatch"
      || (runtimePart.type === "dynamic-tool" && runtimePart.toolName === "createEngineeringSignalsBatch"))
  ) {
    if (runtimePart.state === "output-available") {
      const output = runtimePart.output && typeof runtimePart.output === "object"
        ? runtimePart.output as Record<string, unknown>
        : {};
      const workloadId = String(output.workload_id ?? "");
      if (workloadId) return <WorkloadProgress initial={output} projectId={projectId} workloadId={workloadId} />;
    }
    return <ToolCallCard label="Signal-Workload" part={runtimePart as { state: string; input?: unknown; output?: unknown; errorText?: string }} projectId={projectId} />;
  }

  if (
    part.type === "tool-inspectEngineeringProposals"
    || part.type === "tool-validateEngineeringProposal"
    || part.type === "tool-approveEngineeringProposal"
    || part.type === "tool-approveAllValidEngineeringProposals"
  ) {
    return null;
  }

  if (part.type.startsWith("tool-")) {
    return <ToolCallCard
      label={`Routing · ${part.type.replace("tool-", "").replaceAll("_", " ")}`}
      part={part as { state: string; input?: unknown; output?: unknown; errorText?: string }}
      projectId={projectId}
    />;
  }

  return null;
}

function collectWorkloadIds(messages: EngineeringAgentUIMessage[]) {
  const ids: string[] = [];
  const visit = (value: unknown) => {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    const item = value as Record<string, unknown>;
    if (typeof item.workload_id === "string" && item.workload_id) ids.push(item.workload_id);
    Object.values(item).forEach(visit);
  };
  messages.forEach(visit);
  return ids;
}

function AgentMessageText({ text }: { text: string }) {
  const lines = text.split(/\r?\n/);
  const blocks: ReactNode[] = [];
  let bulletItems: { key: string; text: string }[] = [];

  function flushBullets() {
    if (!bulletItems.length) return;
    blocks.push(
      <ul className="eng-agent-list" key={`list-${blocks.length}`}>
        {bulletItems.map((item) => <li key={item.key}>{renderInlineMarkup(item.text)}</li>)}
      </ul>,
    );
    bulletItems = [];
  }

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushBullets();
      return;
    }

    const structuredLine = parseAgentStructuredLine(trimmed);
    if (structuredLine) {
      flushBullets();
      blocks.push(
        <AgentStructuredLine
          key={`structured-${index}`}
          label={structuredLine.label}
          raw={structuredLine.raw}
          value={structuredLine.value}
        />,
      );
      return;
    }

    const factLine = parseAgentFactLine(trimmed);
    if (factLine) {
      flushBullets();
      blocks.push(
        <div className="eng-agent-fact-line" key={`fact-${index}`}>
          <span>{factLine.label}</span>
          <strong>{renderInlineMarkup(factLine.value)}</strong>
        </div>,
      );
      return;
    }

    const bullet = trimmed.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      bulletItems.push({ key: `bullet-${index}`, text: bullet[1] });
      return;
    }

    flushBullets();
    blocks.push(<p key={`paragraph-${index}`}>{renderInlineMarkup(trimmed)}</p>);
  });

  flushBullets();
  return <div className="eng-agent-text">{blocks}</div>;
}

function parseAgentStructuredLine(line: string) {
  const normalized = normalizeAgentLinePrefix(line);
  const match = normalized.match(/^([^:]{2,44}):\s*([\[{].*[\]}])$/);
  if (!match) return null;
  try {
    return {
      label: cleanAgentLabel(match[1]),
      raw: match[2],
      value: JSON.parse(match[2]) as unknown,
    };
  } catch {
    return null;
  }
}

function parseAgentFactLine(line: string) {
  const normalized = normalizeAgentLinePrefix(line);
  const match = normalized.match(/^([^:]{2,34}):\s*(.+)$/);
  if (!match) return null;
  const label = cleanAgentLabel(match[1]);
  const value = match[2].replace(/^\*\*|\*\*$/g, "").trim();
  if (!label || !value || value.startsWith("{") || value.startsWith("[")) return null;
  return { label, value };
}

function normalizeAgentLinePrefix(line: string) {
  return line.replace(/^[-*]\s+/, "").replace(/^\*\*|\*\*$/g, "").trim();
}

function cleanAgentLabel(value: string) {
  return value.replace(/\*\*/g, "").trim();
}

function AgentStructuredLine({ label, raw, value }: { label: string; raw: string; value: unknown }) {
  const summary = summarizeStructuredAgentValue(value);
  return (
    <details className="eng-agent-structured-line">
      <summary>
        <span>{label}</span>
        <code>{summary}</code>
      </summary>
      <pre>{raw}</pre>
    </details>
  );
}

function summarizeStructuredAgentValue(value: unknown) {
  if (Array.isArray(value)) return `${value.length} ${value.length === 1 ? "Eintrag" : "Einträge"}`;
  if (value && typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    return `${keys.length} ${keys.length === 1 ? "Feld" : "Felder"}`;
  }
  return "Details";
}

function renderInlineMarkup(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <span key={index}>{part}</span>;
  });
}

function ToolCallCard({
  details = true,
  label,
  part,
  projectId,
}: {
  details?: boolean;
  label: string;
  part: { state: string; input?: unknown; output?: unknown; errorText?: string };
  projectId: string;
}) {
  const outputSummary = part.state === "output-available" ? summarizeToolOutput(part.output) : "";
  return (
    <div className="eng-agent-tool">
      <span className="tag">{label}</span>
      {(part.state === "input-streaming" || part.state === "input-available") && (
        <span className="muted"> läuft …</span>
      )}
      {part.state === "output-available" && (
        <>
          <p className="eng-agent-tool-summary">{outputSummary}</p>
          {details && (
            <details className="eng-agent-tool-details">
              <summary>Details</summary>
              <AgentToolResult output={part.output} />
            </details>
          )}
          <IntelligenceActionButtons output={part.output} projectId={projectId} />
        </>
      )}
      {part.state === "output-error" && <span className="notice error">{part.errorText}</span>}
    </div>
  );
}

type IntelligenceActionSuggestion = {
  href?: string;
  id: string;
  kind: "navigate" | "create_optimization_proposal";
  label: string;
  proposal?: Record<string, unknown>;
};

function intelligenceActionSuggestions(output: unknown): IntelligenceActionSuggestion[] {
  if (!output || typeof output !== "object") return [];
  const candidates = (output as { action_suggestions?: unknown }).action_suggestions;
  if (!Array.isArray(candidates)) return [];
  return candidates.flatMap((candidate) => {
    if (!candidate || typeof candidate !== "object") return [];
    const value = candidate as Record<string, unknown>;
    const id = String(value.id ?? "");
    const label = String(value.label ?? "");
    const kind = String(value.kind ?? "");
    if (!id || !label || !["navigate", "create_optimization_proposal"].includes(kind)) return [];
    const href = typeof value.href === "string" && value.href.startsWith("/") ? value.href : undefined;
    const proposal = value.proposal && typeof value.proposal === "object"
      ? value.proposal as Record<string, unknown>
      : undefined;
    if (kind === "navigate" && !href) return [];
    if (kind === "create_optimization_proposal" && !proposal) return [];
    return [{ id, label, kind: kind as IntelligenceActionSuggestion["kind"], href, proposal }];
  });
}

function IntelligenceActionButtons({ output, projectId }: { output: unknown; projectId: string }) {
  const actions = intelligenceActionSuggestions(output);
  const [busyAction, setBusyAction] = useState("");
  const [result, setResult] = useState("");
  const [actionError, setActionError] = useState("");

  if (!actions.length) return null;

  async function run(action: IntelligenceActionSuggestion) {
    if (action.kind === "navigate" && action.href) {
      window.location.assign(withProjectParam(action.href, projectId));
      return;
    }
    if (!action.proposal) return;
    setBusyAction(action.id);
    setResult("");
    setActionError("");
    try {
      const proposal = await createOptimizationProposal(
        action.proposal as unknown as IntelligenceRecommendation,
        projectId,
      );
      setResult(`Proposal ${proposal.proposal_id} wurde zur Human-Review angelegt.`);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Proposal konnte nicht angelegt werden.");
    } finally {
      setBusyAction("");
    }
  }

  return (
    <div className="eng-agent-actions">
      {actions.map((action) => (
        <button
          className={action.kind === "create_optimization_proposal" ? "button primary tiny" : "button secondary tiny"}
          disabled={Boolean(busyAction)}
          key={action.id}
          onClick={() => void run(action)}
          type="button"
        >
          {busyAction === action.id ? "Wird angelegt ..." : action.label}
        </button>
      ))}
      {result && <small className="notice success" role="status">{result}</small>}
      {actionError && <small className="notice error" role="alert">{actionError}</small>}
    </div>
  );
}

function ObjectStatusRow({
  part,
}: {
  part: { state: string; input?: unknown; output?: unknown; errorText?: string };
}) {
  const input = part.input && typeof part.input === "object" ? part.input as Record<string, unknown> : {};
  const output = part.output && typeof part.output === "object" ? part.output as Record<string, unknown> : {};
  const proposal = output.proposal && typeof output.proposal === "object"
    ? output.proposal as Record<string, unknown>
    : {};
  const proposedObjects = Array.isArray(proposal.proposed_objects) ? proposal.proposed_objects : [];
  const proposedObject = proposedObjects.find((item) => item && typeof item === "object") as Record<string, unknown> | undefined;
  const name = String(proposedObject?.name ?? input.name ?? "Engineering-Objekt");
  const canonicalObjects = canonicalObjectsFromToolOutput(part.output);
  const statuses = part.state === "output-error"
    ? ["Fehler"]
    : part.state === "output-available"
      ? canonicalObjects.length
        ? ["gefunden", "modelliert", "registriert"]
        : ["gefunden", "modelliert", "Registrierung offen"]
      : ["gefunden", "wird modelliert"];

  return (
    <div className={`eng-agent-object-status ${part.state === "output-error" ? "error" : ""}`}>
      <strong>{name}</strong>
      <span>{statuses.join(" · ")}</span>
      {part.state === "output-error" && <small>{part.errorText ?? "Objekt konnte nicht registriert werden."}</small>}
    </div>
  );
}

function EngineeringChainStatusRows({
  part,
}: {
  part: { state: string; input?: unknown; output?: unknown; errorText?: string };
}) {
  const input = part.input && typeof part.input === "object" ? part.input as Record<string, unknown> : {};
  const pendingNames = [
    input.hardware_name,
    input.function_name,
    input.interface_name,
    input.message_name,
    input.signal_name,
  ].filter((name): name is string => typeof name === "string" && Boolean(name));
  const source = input.source && typeof input.source === "object" ? input.source as Record<string, unknown> : {};
  const destination = input.destination && typeof input.destination === "object"
    ? input.destination as Record<string, unknown>
    : {};
  const pairNames = [
    source.hardware_name,
    source.function_name,
    source.interface_name,
    source.message_name,
    source.signal_name,
    destination.hardware_name,
    destination.function_name,
    destination.interface_name,
  ].filter((name): name is string => typeof name === "string" && Boolean(name));
  const canonicalObjects = canonicalObjectsFromToolOutput(part.output);
  const items = canonicalObjects.length
    ? canonicalObjects.map((item) => ({ key: `${item.resource}:${item.id}`, name: item.name }))
    : (pendingNames.length ? pendingNames : pairNames).map((name, index) => ({ key: `${index}:${name}`, name }));

  return (
    <div className="eng-agent-chain-status" aria-live="polite">
      {items.map((item) => (
        <div className={`eng-agent-object-status ${part.state === "output-error" ? "error" : ""}`} key={item.key}>
          <strong>{item.name}</strong>
          <span>
            {part.state === "output-error"
              ? "Fehler"
              : part.state === "output-available"
                ? "gefunden · modelliert · registriert"
                : "gefunden · wird modelliert"}
          </span>
        </div>
      ))}
      {part.state === "output-error" && <small className="notice error">{part.errorText ?? "Engineering-Kette konnte nicht registriert werden."}</small>}
    </div>
  );
}

function summarizeToolOutput(output: unknown): string {
  if (!output || typeof output !== "object") return "Analyse abgeschlossen.";
  const value = output as Record<string, unknown>;
  if (value.blocked === true) return String(value.reason ?? "Voraussetzungen fehlen; Schritt wurde nicht ausgeführt.");
  if (typeof value.count === "number") {
    return `${value.count} ${value.count === 1 ? "Eintrag" : "Einträge"} gefunden.`;
  }
  if (Array.isArray(value.items)) {
    return `${value.items.length} ${value.items.length === 1 ? "Eintrag" : "Einträge"} gefunden.`;
  }
  if (typeof value.status === "string") return `Status: ${value.status}.`;
  if (typeof value.valid === "boolean") return value.valid ? "Technische Prüfung bestanden." : "Technische Prüfung mit Befunden abgeschlossen.";
  if (value.proposal || value.proposal_id) return "Ein prüfbarer Vorschlag wurde erstellt.";
  return "Analyse abgeschlossen. Details sind bei Bedarf einsehbar.";
}
