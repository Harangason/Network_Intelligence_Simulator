"use client";
import type { AgentInput } from "@/lib/agent/agent-response";
import { readConversation, type ConversationSnapshot } from '@/lib/agent/conversation-client';
import { wizardContextForRequest, wizardConversationMatches, wizardQuestionFromConversation, wizardReceipt, wizardRequestRevision, wizardTargets, type WizardCommand } from '@/lib/agent/wizard-protocol';
import { readAssistantContext } from "@/lib/agent/assistant-context";
import type { AssistantGraphState } from "@/lib/assistant-graph";
import type { ChatAttachment } from "@/lib/agent/chat-attachments";
import { AgentChatComposer } from "./agent-chat-composer";
import { ProjectDraftEditor, type ProjectDraftStatus } from './project-draft-editor';

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { FormEvent, KeyboardEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EngineeringAgentUIMessage, EngineeringProposal } from "@/lib/agent/engineering-agent";
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
  updatePendingEngineeringAgentTask,
  type EngineeringAgentTask,
} from "@/lib/agent-task-events";
import {
  readEngineeringAgentHistory,
  saveEngineeringAgentHistory,
} from "@/lib/agent-chat-history";
import { uniqueMessagesById } from "@/lib/agent-message-history";
import { agentBuildProgressPercent, agentRunHasDurableOutcome, agentRunIsActive, agentReviewStep, readAgentRunStatus, resolveAgentRunStep, wizardRunCanRetry, wizardRunNeedsAutomaticRecovery } from "@/lib/agent-run-status";
import { requestWizardCancellation } from "@/lib/wizard-cancellation";
import { parameterProgressTarget, parametersAreWorking, symbolicProgressAt, wizardAnalysisHeading } from "@/lib/wizard-progress";
import { engineeringDomainEvidence, engineeringGenerationMode, extractEngineeringSpecification, isEngineeringControllerDevice, type EngineeringHardwareCounts } from "@/lib/agent/engineering-specification";
import { SENSOR_MEASUREMENTS, sensorMeasurement, selectSensorMeasurement } from '@/lib/agent/sensor-measurements';
import { parseProjectIntake, projectIntakeKey } from '@/lib/agent/project-intake';
import {
  buildEquipmentClusters,
  equipmentClusterBusWarnings,
  equipmentClusterBusIssues,
  hmiSignalKey,
  selectHmiSignals,
  reviewedEquipmentCluster,
  equipmentClusterGraphPrompt,
  equipmentClusterSummary,
  equipmentTermMeaning,
  type EquipmentClusterAssignment,
} from "@/lib/agent/equipment-clustering";
import { inspectAgentText } from "@/lib/agent/agent-output-safety";
import { publishEngineeringModelChanged } from "@/lib/engineering-events";
import {
  listAllEngineeringObjects,
  recordEquipmentAssignmentLearning,
  retrieveEquipmentAssignmentLearning,
  type EquipmentAssignmentLearningSuggestion,
} from "@/lib/engineering-api";
import { approveRoutes, listRoutes } from "@/lib/routing-api";
import { routingApprovalProgress } from "@/lib/routing-approval";
import type { EngineeringObject, EngineeringResource, RoutingEntry, Technology, TechnologyDomain } from "@/lib/types";
import { DEFAULT_BUS_PARTICIPANT_LIMITS, busBranchCapacity } from "@/lib/bus-settings";
import { readActiveProjectId, withProjectParam } from "@/lib/user-settings";
import {
  normalizeEngineeringWizardSettings,
  wizardQuestionnaireSteps,
  WIZARD_PROCESS_GROUP as PROCESS_GROUP,
  WIZARD_SCOPE_GROUP as SCOPE_GROUP,
} from "@/lib/engineering-wizard-settings";
import { topologyClusterKnowledgeSummary } from "@/lib/topology-cluster-knowledge";
import {
  createOptimizationProposal,
  getWorkflow,
  getWorkflowSummary,
  setWorkflowContext,
  type IntelligenceRecommendation,
  type WorkflowState,
  type WorkflowStatus,
  type WorkflowStepId,
} from "@/lib/workflow-api";
import { WORKFLOW_CHANGED_EVENT } from "./workflow-header";
import { AgentToolResult } from "./agent-tool-result";
import { WorkloadProgress } from "./workload-progress";
import { EngineeringAgentEventCard } from "./engineering-agent-event";

const EQUIPMENT_CATEGORIES = [
  { key: "gateways", label: "Gateways", type: "Gateway" },
  { key: "ecus", label: "Controller", type: "Controller" },
  { key: "sensors", label: "Sensoren", type: "SensorController" },
  { key: "actuators", label: "Aktoren", type: "ActuatorController" },
] as const;

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
  draftRequest,
  onStateChange,
}: {
  compact?: boolean;
  projectId?: string;
  routingApprovalComplete?: boolean;
  draftRequest?: { id: number; text: string } | null;
  onStateChange?: (state: AssistantGraphState) => void;
}) {
  const activeProjectId = projectId?.trim() || readActiveProjectId();
  const transport = useMemo(
    () => new DefaultChatTransport({
      api: "/api/agent/chat",
      headers: () => ({ "X-Project-ID": activeProjectId }),
      body: () => ({ context: { ...readAssistantContext(), active_project_id: readActiveProjectId() } }),
    }),
    [activeProjectId],
  );
  const { messages, sendMessage, setMessages, status, error, regenerate, clearError } = useChat<EngineeringAgentUIMessage>({
    id: `engineering-agent-${activeProjectId}`,
    transport,
  });
  const [input, setInput] = useState("");
  const [historyReady, setHistoryReady] = useState(false);
  const [pendingTask, setPendingTask] = useState<EngineeringAgentTask | null>(null);
  const [taskNotice, setTaskNotice] = useState('');
  const consumedDraftRef = useRef<number | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const followBottomRef = useRef(true);
  const [newAnswer, setNewAnswer] = useState(false);
  const [visibleCount, setVisibleCount] = useState(20);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const publishedToolResultsRef = useRef(new Set<string>());
  const taskRunStartingRef = useRef(false);
  const activeAutomaticTaskRef = useRef<EngineeringAgentTask | null>(null);
  const previousStatusRef = useRef(status);
  const persistedHistoryRevisionRef = useRef("");

  function submit(text: string, attachments: ChatAttachment[]) {
    if (readActiveProjectId() !== activeProjectId) { setTaskNotice('Das Projekt wurde gewechselt. Bitte den Assistenten im aktuellen Projekt öffnen.'); return; }
    if (!historyReady || !text.trim() || (status !== "ready" && status !== "error")) return;
    clearError();
    followBottomRef.current = true;
    if (!attachments.length && isInlineConfirmation(text) && status === 'ready') {
      if (confirmationRequest) {
        allowRequestedAction(text);
      } else {
        void sendMessage({ text: buildInlineConfirmationPrompt(text, stableMessages) });
      }
      setInput("");
      return;
    }
    void sendMessage({ parts: [{ type: 'text', text }, ...attachments.map(data => ({ type: 'data-attachment' as const, data }))] });
    setInput("");
  }

  const busy = status === "submitted" || status === "streaming";
  useEffect(() => { onStateChange?.(error ? 'error' : status === 'submitted' ? 'thinking' : status === 'streaming' ? 'responding' : 'idle'); }, [error, onStateChange, status]);
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
    setTaskNotice('');
    let runnableTask = task;
    try {
      if (task.workflowTarget) {
        const workflow = await getWorkflowSummary();
        if (workflow.context.agent_wizard_status) { setTaskNotice('Dieser Auftrag gehört zum Engineering-Wizard. Bitte dort fortsetzen.'); return; }
        const progress = engineeringAgentWorkflowProgress(task, workflow.statuses, workflow.versions);
        if (progress.complete) {
          clearPendingEngineeringAgentTask(activeProjectId);
          setPendingTask(null);
          setTaskNotice('Der vorbereitete Auftrag ist bereits abgeschlossen.');
          return;
        }
        if (progress.blockedStep) {
          setTaskNotice(`Zuerst den Fehler im Workflow-Schritt ${progress.blockedStep} prüfen.`);
          updatePendingEngineeringAgentTask({
            ...task,
            gate: undefined,
            paused: true,
            lastWorkflowSignature: progress.signature,
          });
          return;
        }
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

      setPendingTask(null);
      await sendMessage(
        { text: runnableTask.text },
        runnableTask.workflowTarget
          ? { body: { workflowTarget: runnableTask.workflowTarget } }
          : undefined,
      );
    } catch (error) {
      if (activeAutomaticTaskRef.current === runnableTask) activeAutomaticTaskRef.current = null;
      setPendingTask(task);
      setTaskNotice(error instanceof Error ? error.message : 'Der Auftrag konnte nicht gestartet werden.');
    } finally {
      taskRunStartingRef.current = false;
    }
  }, [activeProjectId, historyReady, routingApprovalComplete, sendMessage, status]);

  useEffect(() => {
    let active = true;
    setHistoryReady(false);
    setPendingTask(readPendingEngineeringAgentTask(activeProjectId));
    setTaskNotice('');
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
    if (!historyReady || (status !== 'ready' && status !== 'error')) return;
    let active = true;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      void readEngineeringAgentHistory<EngineeringAgentUIMessage>(activeProjectId).then(remote => {
        if (!active) return;
        setMessages(current => {
          const merged = new Map(remote.map(message => [message.id, message]));
          current.forEach(message => { const saved = merged.get(message.id); if (!saved || message.parts.length > saved.parts.length) merged.set(message.id, message); });
          const next = [...merged.values()].slice(-60);
          return agentHistoryRevision(next) === agentHistoryRevision(current) ? current : next;
        });
      });
    }, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [activeProjectId, historyReady, setMessages, status]);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread && followBottomRef.current) thread.scrollTop = thread.scrollHeight;
    else if (thread) setNewAnswer(true);
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
    // The widget captures this before lazy-mounting the chat. Opening a question
    // prepares an editable draft; it never submits or replaces an existing one.
    if (!draftRequest || consumedDraftRef.current === draftRequest.id) return;
    consumedDraftRef.current = draftRequest.id;
    setInput(current => current.trim() ? `${current}\n\n${draftRequest.text}` : draftRequest.text);
    inputRef.current?.focus();
  }, [draftRequest]);

  useEffect(() => {
    const handleTask = (event: Event) => {
      const task = (event as CustomEvent<EngineeringAgentTask>).detail;
      if (task?.text?.trim() && (!task.projectId || task.projectId === activeProjectId)) {
        setPendingTask(task);
        setTaskNotice('');
      }
    };
    window.addEventListener(ENGINEERING_AGENT_TASK_EVENT, handleTask);
    return () => window.removeEventListener(ENGINEERING_AGENT_TASK_EVENT, handleTask);
  }, [activeProjectId]);

  useEffect(() => {
    const previousStatus = previousStatusRef.current;
    previousStatusRef.current = status;
    const automaticTask = activeAutomaticTaskRef.current;
    const runFinished = (status === "ready" || status === "error") && (previousStatus === "submitted" || previousStatus === "streaming");
    if (!historyReady || !runFinished || !automaticTask?.workflowTarget) return;
    activeAutomaticTaskRef.current = null;
    if (status === 'error') {
      setPendingTask(readPendingEngineeringAgentTask(activeProjectId));
      return;
    }

    let active = true;
    const continueWorkflow = async () => {
      const pending = readPendingEngineeringAgentTask(activeProjectId);
      if (!pending?.workflowTarget) return;
      const workflow = await getWorkflowSummary();
      if (!active) return;
      const progress = engineeringAgentWorkflowProgress(pending, workflow.statuses, workflow.versions);
      if (progress.complete) {
        clearPendingEngineeringAgentTask(activeProjectId);
        setPendingTask(null);
        return;
      }
      if (progress.blockedStep) {
        setPendingTask(updatePendingEngineeringAgentTask({
          ...pending,
          paused: true,
          lastWorkflowSignature: progress.signature,
        }));
        return;
      }

      setPendingTask(updatePendingEngineeringAgentTask({
        ...pending,
        paused: true,
        lastWorkflowSignature: progress.signature,
        noProgressRuns: (pending.noProgressRuns ?? 0) + 1,
      }));
    };
    void continueWorkflow().catch(() => {
      if (!active) return;
      setPendingTask(readPendingEngineeringAgentTask(activeProjectId));
      setTaskNotice('Der Workflow-Status konnte nicht gelesen werden. Der Auftrag wartet weiterhin auf deinen Start.');
    });
    return () => {
      active = false;
    };
  }, [activeProjectId, historyReady, runTask, status]);

  useEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [input]);

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
    <div className="eng-agent-chat">
      <button className="button secondary tiny" type="button" disabled={!historyReady || busy}
        onClick={() => submit('Zeige mir deine Fähigkeiten.', [])}>Fähigkeiten und Wizards</button>
      <div className="eng-agent-thread" aria-label="Gesprächsverlauf" ref={threadRef} onScroll={() => {
        const thread = threadRef.current;
        if (!thread) return;
        followBottomRef.current = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 72;
        if (followBottomRef.current) setNewAnswer(false);
      }}>
        {!historyReady && (
          <div className="empty-result" style={{ minHeight: compact ? 90 : 140 }}>
            <span className="spinner" />
            <strong>Verlauf wird geladen</strong>
          </div>
        )}

        {historyReady && stableMessages.length === 0 && (
          <div className="empty-result" style={{ minHeight: compact ? 90 : 140 }}>
            <span className="empty-icon">◇</span>
            <strong>Woran möchtest du arbeiten?</strong>
            <p>Wähle einen Einstieg oder stelle deine eigene Frage. Erst mit „Senden“ beginnt der Assistent.</p>
            <div className="engineering-quick-prompts">{['Architektur erstellen', 'Signal prüfen', 'Trace analysieren', 'Finding bewerten'].map(label => <button key={label} type="button" onClick={() => { setInput(label); inputRef.current?.focus(); }}>{label}</button>)}</div>
          </div>
        )}

        {historyReady && stableMessages.length > 0 && <details className="eng-agent-examples">
          <summary>Frage vorbereiten</summary>
          <div className="engineering-quick-prompts">{['Architektur erstellen', 'Signal prüfen', 'Trace analysieren', 'Finding bewerten'].map(label => <button key={label} type="button" onClick={() => { setInput(current => current.trim() ? `${current}\n${label}` : label); inputRef.current?.focus(); }}>{label}</button>)}</div>
        </details>}

        {pendingTask && <section className="eng-agent-pending-task" aria-label="Vorbereiteter Auftrag">
          <strong>Vorbereiteter Auftrag</strong>
          <p>Dieser gespeicherte Auftrag wartet auf deinen Start.</p>
          <details><summary>Auftrag ansehen</summary><p>{pendingTask.text}</p></details>
          {pendingTask.gate === 'routing-approval' && !routingApprovalComplete && <p>Die Routing-Freigaben stehen noch aus.</p>}
          <div className="eng-agent-composer-actions">
            <button className="button primary" type="button" disabled={!historyReady || busy || status === 'error' || (pendingTask.gate === 'routing-approval' && !routingApprovalComplete)} onClick={() => { void runTask(pendingTask); }}>Auftrag starten</button>
            <button className="button secondary" type="button" disabled={busy} onClick={() => { clearPendingEngineeringAgentTask(activeProjectId); setPendingTask(null); setTaskNotice(''); }}>Verwerfen</button>
          </div>
        </section>}
        {taskNotice && <p className="notice" role="status">{taskNotice}</p>}

        {stableMessages.length > visibleCount && <button type="button" onClick={() => setVisibleCount(count => count + 20)}>Ältere Nachrichten laden</button>}
        {stableMessages.slice(-visibleCount).map((message) => (
          <div className={`eng-agent-message ${message.role}`} key={message.id}>
            <span aria-hidden="true" className="eng-agent-avatar">{message.role === "user" ? "DU" : "AI"}</span>
            <div className="eng-agent-message-content">
              <span className="eng-agent-role">{message.role === "user" ? "Du" : "Engineering-Agent"}</span>
              <div className="eng-agent-bubble">
                {message.parts.filter((part, index, parts) => part.type !== 'data-engineering' || part.data.type !== 'PROGRESS' ||
                  (!parts.some(item => item.type === 'data-engineering' && !['PROGRESS', 'CONTEXT'].includes(item.data.type)) &&
                  index === parts.findLastIndex(item => item.type === 'data-engineering' && item.data.type === 'PROGRESS'))).map((part, index) => (
                  <MessagePart
                    hideText={message.role === "assistant" && hasCompactEngineeringResult(message.parts)}
                    key={`${message.id}-${index}`}
                    part={part}
                    projectId={activeProjectId}
                    richText={message.role === "assistant"}
                    onAnswer={status === "ready" ? answer => { followBottomRef.current = true; void sendMessage({ text: answer.type === 'SKIP_QUESTION' ? 'Optionale Frage übersprungen.' : answer.type === 'FINDING_ACTION' ? 'Maßnahme zum Finding angefordert.' : 'Auswahl bestätigt.' }, { body: { input: answer } }); } : undefined}
                    onRetry={status === 'ready' ? () => { void regenerate({ body: { input: { type: 'RESUME' } } }); } : undefined}
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
      {error && (
        <div className="notice error">
          {agentErrorText(error.message)}{" "}
          <button className="button secondary tiny" onClick={() => regenerate({ body: { input: { type: 'RESUME' } } })} type="button">
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

      </div>
      {newAnswer && <button type="button" className="engineering-new-answer" onClick={() => { const thread = threadRef.current; if (thread) thread.scrollTop = thread.scrollHeight; followBottomRef.current = true; setNewAnswer(false); }}>Neue Antwort anzeigen ↓</button>}
      <AgentChatComposer input={input} setInput={setInput} inputRef={inputRef} ready={historyReady}
        busy={busy} projectId={activeProjectId} onSubmit={submit} />
    </div>
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
  { id: "robotics_ros", label: "Robotics / ROS 2", technologies: [] },
  { id: "aerospace", label: "Aerospace", technologies: [] },
  { id: "rail", label: "Rail", technologies: [] },
  { id: "marine", label: "Marine / Off-Highway", technologies: [] },
  { id: "building_automation", label: "Building Automation", technologies: [] },
  { id: "energy", label: "Energy & Smart Grid", technologies: [] },
  { id: "process_industry", label: "Process Industry", technologies: [] },
  { id: "embedded_systems", label: "Embedded / Electronics", technologies: [] },
  { id: "iot_wireless", label: "IoT / Edge / Wireless", technologies: [] },
  { id: "generic_networking", label: "Generische Kommunikationsarchitektur", technologies: [] },
  { id: "custom", label: "Custom / Proprietary", technologies: [] },
];

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
    label: "Variante 0 · Sensor-Controller-Aktor",
    detail: "Lokaler Regelkreis ohne Gateway-Pfad: Sensoren liefern an die zuständige Steuerung, die Steuerung bedient Aktoren. Controllerstatus bleibt intern; ausdrücklich gewählte Ausgaben bleiben erhalten.",
    diagram: "Sensor -> Controller -> Aktor",
    rules: "Lokale Funktionskette: Sensoren und Aktoren werden fachlich an den zuständigen Controller gebunden. Es werden keine Gateway-Verbindungen und keine direkten Sensor-/Aktor-Netzpfade angelegt.",
  },
  {
    id: "eva",
    label: "Variante 1 · Einfaches EVA",
    detail: "Eingabe, Verarbeitung und Ausgabe bleiben je System und Controller fachlich zusammengefasst.",
    diagram: "Sensor/Aktor → Controller → Gateway",
    rules: "EVA je Systemrahmen: Sensoren und Eingaben zur Steuerung, Controller-Verarbeitung zu Aktoren und Ausgaben; die Gateway-Anbindung vermittelt nur die Systemkommunikation.",
  },
  {
    id: "ecu_gateway",
    label: "Variante 2 · Controller-vermittelt",
    detail: "Sensoren und Aktoren hängen am zuständigen Controller; der Controller kommuniziert mit dem Gateway.",
    diagram: "Sensor ─┐\n        ├─ Controller ─ Gateway\nAktor ──┘",
    rules: "Sensoren und Aktoren werden ihrem fachlich zuständigen Controller zugeordnet; ausschließlich der Controller bindet den Systemrahmen an das Gateway an.",
  },
  {
    id: "gateway_direct",
    label: "Variante 3 · Gateway-direkt",
    detail: "Sensoren, Controller und Aktoren erhalten jeweils eine direkte Gateway-Anbindung.",
    diagram: "Sensor ─────┐\nController ─┼─ Gateway\nAktor ──────┘",
    rules: "Sensoren, Controller und Aktoren werden als eigenständige Teilnehmer direkt an das Gateway angebunden.",
  },
  {
    id: "gateway_ecu_segments",
    label: "Variante 4 · Gateway-Segmente",
    detail: "Gemeinsame Gateway-Busse gemäß den Teilnehmergrenzen je Bustyp; Sensoren und Aktoren bleiben an der fachlichen Steuerung.",
    diagram: "Sensor/Aktor -> Controller 1 --\\\nSensor/Aktor -> Controller 2 --- Gateway\n... weitere Controller ----/",
    rules: "Segmentierte Gateway-Backbone-Architektur: Sensoren und Aktoren werden fachlich an Controller geführt; pro Gateway-Leitung werden Controller entsprechend der einstellbaren Bus-Teilnehmergrenze als Bussegment gebündelt (Gateway mitgezählt). Das Gateway kennt die Controller-Segmente, legt aber keine Sensor-/Aktor-Direktanbindungen an.",
  },
  {
    id: "hybrid_ai",
    label: "KI-Kombination · Variante 2 + 3",
    detail: "Die KI entscheidet je Teilnehmer zwischen lokaler Controller-Zuordnung und direkter Gateway-Anbindung.",
    diagram: "lokal → Controller ─┐\n                    ├─ Gateway\ndirekt ─────────────┘",
    rules: "Kombination aus Variante 2 und 3: lokale, echtzeit- oder regelungskritische Teilnehmer über den fachlichen Controller; systemweite, zentrale oder hochbandbreitige Teilnehmer direkt über das Gateway.",
  },
];

function architectureOption(id: NetworkArchitectureId | "") {
  return NETWORK_ARCHITECTURES.find((option) => option.id === id);
}

type AgentWizardContext = {
  engineering_draft_ref?: { draft_id: string; revision: number };
  structured_draft_ref?: { draft_id: string; revision: number };
  agent_prompt?: string;
  attachments: Array<{ kind: string; name: string; size: number; source?: "task" | "architecture" }>;
  confirmed_at: string;
  industry: string;
  model_type: string;
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
  process_ids: string[];
  project_id: string;
  project_name: string;
  resume_count?: number;
  automatic_resume_count?: number;
  run_id: string;
  scope: string[];
  scope_ids: string[];
  task: string;
  technologies: string[];
  hardware_counts?: EngineeringHardwareCounts;
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
  const draftRef = context.engineering_draft_ref && typeof context.engineering_draft_ref === 'object'
    ? context.engineering_draft_ref as Record<string, unknown> : null;
  const structuredRef = context.structured_draft_ref && typeof context.structured_draft_ref === 'object'
    ? context.structured_draft_ref as Record<string, unknown> : null;
  return {
    structured_draft_ref: structuredRef && typeof structuredRef.draft_id === 'string'
      && typeof structuredRef.revision === 'number' && Number.isSafeInteger(structuredRef.revision) && structuredRef.revision > 0
      ? { draft_id: structuredRef.draft_id, revision: structuredRef.revision } : undefined,
    engineering_draft_ref: draftRef && typeof draftRef.draft_id === 'string' && draftRef.draft_id.trim()
      && typeof draftRef.revision === 'number' && Number.isSafeInteger(draftRef.revision) && draftRef.revision > 0
      ? { draft_id: draftRef.draft_id, revision: draftRef.revision } : undefined,
    agent_prompt: typeof context.agent_prompt === "string" ? context.agent_prompt : undefined,
    attachments,
    confirmed_at: String(context.confirmed_at ?? ""),
    industry: String(context.industry ?? "Aus Projektkontext ableiten"),
    model_type: String(context.model_type ?? context.industry ?? "generic_networking"),
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
    process_ids: strings("process_ids"),
    project_id: projectId,
    project_name: String(context.project_name ?? "").trim(),
    resume_count: Number.isFinite(Number(context.resume_count)) ? Math.max(0, Number(context.resume_count)) : 0,
    automatic_resume_count: Number.isFinite(Number(context.automatic_resume_count)) ? Math.max(0, Number(context.automatic_resume_count)) : 0,
    run_id: String(context.run_id),
    scope: strings("scope"),
    scope_ids: strings("scope_ids"),
    task: String(context.task ?? "Engineering-Auftrag"),
    technologies: strings("technologies"),
    hardware_counts: context.hardware_counts && typeof context.hardware_counts === "object"
      ? {
          gateways: Number((context.hardware_counts as Record<string, unknown>).gateways ?? 0),
          ecus: Number((context.hardware_counts as Record<string, unknown>).ecus ?? 0),
          sensors: Number((context.hardware_counts as Record<string, unknown>).sensors ?? 0),
          actuators: Number((context.hardware_counts as Record<string, unknown>).actuators ?? 0),
        }
      : undefined,
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
          tree: Array.isArray(item.tree) ? item.tree as EquipmentClusterAssignment["tree"] : undefined,
          unassigned: Array.isArray(item.unassigned) ? item.unassigned as EquipmentClusterAssignment["unassigned"] : undefined,
          hmi_routes: Array.isArray(item.hmi_routes) ? item.hmi_routes as EquipmentClusterAssignment["hmi_routes"] : undefined,
          validation: item.validation && typeof item.validation === "object"
            ? item.validation as EquipmentClusterAssignment["validation"]
            : undefined,
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
  host_metrics_available: boolean;
  gpu: null | { utilization_percent: number; memory_used_mb: number; memory_total_mb: number };
  memory_percent: number;
  memory_total_mb: number;
  memory_used_mb: number;
  ollama: Array<{ name: string; size_mb: number; vram_mb: number }>;
  sampled_at: string;
  source: "windows-host" | "container-runtime";
};

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

type WorkflowDisplayStatus = WorkflowStatus | "BLOCKED" | "REVIEW_REQUIRED";

const WORKFLOW_DISPLAY_STATUS_LABEL: Record<WorkflowDisplayStatus, string> = {
  REVIEW_REQUIRED: "Vorschlag geprüft · Freigabe offen",
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

function useSymbolicParameterProgress(runId: string, target: number, animate: boolean) {
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
    if (!animate || motion.matches || from === target) update(target);
    else {
      update(from);
      frame = window.requestAnimationFrame(tick);
    }
    motion.addEventListener("change", finish);
    return () => {
      window.cancelAnimationFrame(frame);
      motion.removeEventListener("change", finish);
    };
  }, [runId, target, animate]);

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

function ClusterUnassignedReview({
  busy,
  clusterId,
  clusterLabel,
  controllerOptions,
  leaves,
  onAssign,
  onOpenLeaf,
  ownerSelections,
  warningFor,
}: {
  busy: boolean;
  clusterId: string;
  clusterLabel: string;
  controllerOptions: Array<{ hardware_name: string }>;
  leaves: NonNullable<EquipmentClusterAssignment["unassigned"]>;
  onAssign: (owners: Record<string, string>) => void;
  onOpenLeaf: (name: string, target: string) => void;
  ownerSelections: Record<string, string>;
  warningFor: (name: string) => string;
}) {
  const [selections, setSelections] = useState<string[]>([]);
  const [target, setTarget] = useState("");
  const allSelected = leaves.length > 0 && leaves.every((leaf) => selections.includes(leaf.name));

  return (
    <details className="agent-cluster-unassigned" open>
      <summary>Ungeklärte Controller-Zuordnung · {leaves.length}</summary>
      <div className="agent-cluster-batch-toolbar">
        <label className="agent-cluster-select-all">
          <input
            aria-label={`${clusterLabel}: alle ungeklärten Teilnehmer auswählen`}
            checked={allSelected}
            disabled={busy}
            onChange={(event) => setSelections(event.target.checked ? leaves.map((leaf) => leaf.name) : [])}
            type="checkbox"
          />
          <span>{allSelected ? "Alle ausgewählt" : "Alle auswählen"}</span>
        </label>
        <strong>{selections.length} ausgewählt</strong>
        <select
          aria-label={`${clusterLabel}: Controller für Mehrfachauswahl`}
          disabled={busy || !controllerOptions.length}
          onChange={(event) => setTarget(event.target.value)}
          value={target}
        >
          <option value="">Controller auswählen …</option>
          {controllerOptions.map((ecu) => <option key={ecu.hardware_name} value={ecu.hardware_name}>{ecu.hardware_name}</option>)}
        </select>
        <button
          disabled={busy || !target || selections.length === 0}
          onClick={() => {
            onAssign(Object.fromEntries(selections.map((name) => [name, target])));
            setSelections([]);
            setTarget("");
          }}
          type="button"
        >Auswahl zuordnen</button>
      </div>
      <ul>{leaves.map((leaf) => (
        <li id={`cluster-participant-${encodeURIComponent(clusterId)}-${encodeURIComponent(leaf.name)}`} tabIndex={-1} data-warning={Boolean(warningFor(leaf.name)) || undefined} className={selections.includes(leaf.name) ? "selected" : ""} key={`${clusterId}:${leaf.deviceType}:${leaf.name}`}>
          <input
            aria-label={`${leaf.name} für Mehrfachzuordnung auswählen`}
            checked={selections.includes(leaf.name)}
            disabled={busy}
            onChange={(event) => setSelections((current) => event.target.checked ? [...current, leaf.name] : current.filter((name) => name !== leaf.name))}
            type="checkbox"
          />
          <span title={`${equipmentTermMeaning(leaf.name).english} / ${equipmentTermMeaning(leaf.name).german}`}>{leaf.name}<small>{leaf.reason}</small><small>EN: {equipmentTermMeaning(leaf.name).english} · DE: {equipmentTermMeaning(leaf.name).german}</small>{warningFor(leaf.name) && <small className="agent-participant-warning">⚠ {warningFor(leaf.name)}</small>}</span>
          <button
            aria-label={`${leaf.name}: Controller-Zuordnung öffnen`}
            className="agent-unassigned-owner-button"
            disabled={busy || !controllerOptions.length}
            onClick={() => onOpenLeaf(leaf.name, ownerSelections[leaf.name] ?? "")}
            type="button"
          >{ownerSelections[leaf.name] || "Einzeln zuordnen …"}</button>
        </li>
      ))}</ul>
    </details>
  );
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
  const [projectName, setProjectName] = useState("");
  const [selectedIndustry, setSelectedIndustry] = useState("automotive");
  const [selectedTechnologies, setSelectedTechnologies] = useState<string[]>([]);
  const manualTechnologyScopeRef = useRef('');
  const [networkArchitecture, setNetworkArchitecture] = useState<NetworkArchitectureId | "">("gateway_direct");
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
  const [intakeRequirement, setIntakeRequirement] = useState<string | null>(null);
  const [linkedDraftId, setLinkedDraftId] = useState('');
  const [linkedDraftStatus, setLinkedDraftStatus] = useState<ProjectDraftStatus | null>(null);
  const draftStartRef = useRef(false);
  const [taskFiles, setTaskFiles] = useState<TaskAttachment[]>([]);
  const [equipmentEdits, setEquipmentEdits] = useState<{ source: string; values: Partial<Record<keyof EngineeringHardwareCounts, string>> }>({ source: "", values: {} });
  const [communicationSystemEdits, setCommunicationSystemEdits] = useState<{ source: string; values: Record<string, string> }>({ source: "", values: {} });
  const [equipmentClusterEdits, setEquipmentClusterEdits] = useState<{
    source: string;
    values: Record<string, {
      selected?: boolean;
      networkId?: string;
      busName?: string;
      owners?: Record<string, string>;
      verdicts?: Record<string, boolean>;
      branchTargets?: Record<string, string>;
      hmiSignals?: Record<string, boolean>;
    }>;
  }>({ source: "", values: {} });
  const [clusterReviewDialog, setClusterReviewDialog] = useState<null | {
    kind: "leaf" | "branch";
    clusterId: string;
    name: string;
    target: string;
  }>(null);
  const [activeEquipmentClusterId, setActiveEquipmentClusterId] = useState("");
  const [acceptedDomainMismatch, setAcceptedDomainMismatch] = useState("");
  const taskSource = `${taskText}\n${taskFiles.map(formatTaskAttachment).join("\n")}`;
  const detectedDomain = useMemo(() => engineeringDomainEvidence(taskSource), [taskSource]);
  const selectedDomainId = canonicalWizardDomain(selectedIndustry);
  const domainMismatch = detectedDomain.domain !== "generic"
    && detectedDomain.domain !== selectedDomainId
    && detectedDomain.confidence >= 0.65;
  const domainMismatchSignature = domainMismatch ? `${selectedDomainId}->${detectedDomain.domain}:${detectedDomain.markers.join("|")}` : "";
  const domainMismatchAccepted = Boolean(domainMismatchSignature && acceptedDomainMismatch === domainMismatchSignature);
  const previewDomain = domainMismatch && !domainMismatchAccepted ? detectedDomain.domain : selectedDomainId;
  const recognizedEquipment = useMemo(
    () => extractEngineeringSpecification(taskSource, {}, previewDomain),
    [previewDomain, taskSource],
  );
  const equipmentValues = Object.fromEntries(EQUIPMENT_CATEGORIES.map(({ key }) => [key,
    equipmentEdits.source === taskSource && equipmentEdits.values[key] !== undefined
      ? equipmentEdits.values[key]
      : key === 'actuators' && intakeRequirement && /\b(?:aktoren|actuators|ventile|valves)\b/i.test(taskText)
        && recognizedEquipment.targetCounts.actuators === 0 ? '' : String(recognizedEquipment.targetCounts[key]),
  ])) as Record<keyof EngineeringHardwareCounts, string>;
  const equipmentReady = Object.values(equipmentValues).every((value) => /^\d+$/.test(value)
    && Number(value) <= 1000) && Object.values(equipmentValues).some((value) => Number(value) > 0);
  const equipmentCounts = Object.fromEntries(EQUIPMENT_CATEGORIES.map(({ key }) => [key, Number(equipmentValues[key])])) as EngineeringHardwareCounts;
  const plannedEquipment = useMemo(
    () => extractEngineeringSpecification(taskSource, equipmentCounts, previewDomain, true),
    [equipmentCounts.actuators, equipmentCounts.ecus, equipmentCounts.gateways, equipmentCounts.sensors, previewDomain, taskSource],
  );
  const plannedInventory = new Map(plannedEquipment.chains.map(chain => [chain.hardware_name, chain.device_type]));
  const identifiedCounts = { sensors: 0, actuators: 0, gateways: 0, ecus: 0 };
  for (const type of plannedInventory.values()) {
    if (type === 'SensorController') identifiedCounts.sensors += 1;
    else if (type === 'ActuatorController') identifiedCounts.actuators += 1;
    else if (type === 'Gateway') identifiedCounts.gateways += 1;
    else if (isEngineeringControllerDevice(type)) identifiedCounts.ecus += 1;
  }
  const equipmentIdentityReady = EQUIPMENT_CATEGORIES.every(({ key }) => identifiedCounts[key] === equipmentCounts[key]);
  const connectionInventory = [...new Map(plannedEquipment.chains.map(chain => [chain.hardware_name, chain])).values()];
  const sensorInventory = connectionInventory.filter(chain => chain.device_type === 'SensorController');
  const namedSensors = sensorInventory.filter(chain => !/^Sensor\d+$/.test(chain.hardware_name));
  const sensorRows = Array.from({ length: Math.min(1000, Math.max(equipmentCounts.sensors || 0, sensorInventory.length)) }, (_, index) => {
    const chain = namedSensors[index] ?? sensorInventory.find(item => item.hardware_name === `Sensor${index + 1}`);
    return { name: chain?.hardware_name ?? `Sensor${index + 1}`, label: `Sensor ${index + 1}`, chain };
  });
  const deviceRows = [
    ...connectionInventory.filter(chain => !['SensorController', 'ActuatorController'].includes(chain.device_type)).map(chain => ({ name: chain.hardware_name, label: chain.hardware_name, chain, sensor: false })),
    ...sensorRows.map(row => ({ ...row, sensor: true })),
    ...connectionInventory.filter(chain => chain.device_type === 'ActuatorController').map(chain => ({ name: chain.hardware_name, label: chain.hardware_name, chain, sensor: false })),
  ];
  const unresolvedConnections = connectionInventory.filter(chain => !chain.interface_type || chain.interface_type === 'Other');
  function selectDeviceConnection(name: string, technology: string) {
    const marker = taskText.match(/^- Geräteanschlüsse:\s*(\{[^\r\n]*\})\s*$/m)?.[1];
    let connections: Record<string, string> = {};
    try {
      const parsed: unknown = marker ? JSON.parse(marker) : {};
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) connections = parsed as Record<string, string>;
    } catch { /* Incomplete manual input is replaced by this explicit selection. */ }
    if (technology) connections[name] = technology; else delete connections[name];
    setTaskText(`${taskText.replace(/\n?^- Geräteanschlüsse:[^\r\n]*$/gm, '').trim()}\n- Geräteanschlüsse: ${JSON.stringify(connections)}`);
  }
  const [newControllerName, setNewControllerName] = useState('');
  const [controllerAdditionError, setControllerAdditionError] = useState('');
  const controllerExtensionRef = useRef<string | null>(null);
  const extendingController = controllerExtensionRef.current === taskSource;
  function addRequestedController() {
    const name = newControllerName.trim();
    if (!/^[\p{L}\d][\p{L}\d _-]{0,79}$/u.test(name)) {
      setControllerAdditionError('Bitte einen eindeutigen Controllernamen ohne Sonderzeichen eingeben.');
      return;
    }
    if ([...plannedInventory.keys()].some(existing => existing.toLocaleLowerCase() === name.toLocaleLowerCase())) {
      setControllerAdditionError('Dieses Gerät ist bereits vorhanden. Bitte in der Zuordnung auswählen.');
      return;
    }
    const nextText = `${taskText}\nController namens "${name}".`;
    const nextSource = `${nextText}\n${taskFiles.map(formatTaskAttachment).join("\n")}`;
    controllerExtensionRef.current = nextSource;
    setEquipmentEdits({ source: nextSource, values: { ...equipmentValues, ecus: String(Math.max(equipmentCounts.ecus, identifiedCounts.ecus + 1)) } });
    setTaskText(nextText);
    setNewControllerName('');
    setControllerAdditionError('');
  }
  const [projectId] = useState(() => readActiveProjectId());
  const wizardRunRef = useRef('');
  const requestRevisionRef = useRef<string | undefined>(undefined);
  const pendingCommandRef = useRef<{ signature: string; command: WizardCommand } | null>(null);
  const acceptedOperationsRef = useRef(new Set<string>());
  const workflowEpochRef = useRef(0);
  const commandInFlightRef = useRef(false);
  const [learnedEquipmentAssignments, setLearnedEquipmentAssignments] = useState<EquipmentAssignmentLearningSuggestion[]>([]);
  const [assignmentLearningCorpusSize, setAssignmentLearningCorpusSize] = useState(0);
  const wizardTransport = useMemo(
    () => new DefaultChatTransport({
      api: "/api/agent/chat",
      headers: () => ({ "X-Project-ID": projectId }),
      body: () => ({ context: { ...readAssistantContext(), active_project_id: projectId } }),
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
    onData: part => {
      if (part.type !== 'data-engineering') return;
      const receipt = wizardReceipt(part.data, wizardRunRef.current);
      const pending = pendingCommandRef.current?.command;
      if (!receipt || pending?.operation_id !== receipt.operation_id) return;
      acceptedOperationsRef.current.add(receipt.operation_id);
      if (pending.action === 'START') window.sessionStorage.removeItem(projectIntakeKey(projectId));
      workflowEpochRef.current += 1;
      if (!requestRevisionRef.current || requestRevisionRef.current === pending.request_revision || requestRevisionRef.current === receipt.request_revision)
        requestRevisionRef.current = receipt.request_revision;
    },
  });
  const [phase, setPhase] = useState<"questionnaire" | "status">("questionnaire");
  const [wizardPreferencesReady, setWizardPreferencesReady] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submittedAt, setSubmittedAt] = useState(0);
  const [runId, setRunId] = useState("");
  const [submittedContext, setSubmittedContext] = useState<AgentWizardContext | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [routingEntries, setRoutingEntries] = useState<RoutingEntry[]>([]);
  const [hardwareItems, setHardwareItems] = useState<EngineeringObject[]>([]);
  const [reviewProposal, setReviewProposal] = useState<EngineeringProposal | null>(null);
  const [routingReviewBusy, setRoutingReviewBusy] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [supplementOpen, setSupplementOpen] = useState(false);
  const [supplementText, setSupplementText] = useState("");
  const [supplementBusy, setSupplementBusy] = useState(false);
  const [performance, setPerformance] = useState<AgentPerformanceSample | null>(null);
  const [statusError, setStatusError] = useState("");
  const [statusRefreshError, setStatusRefreshError] = useState("");
  const [wizardConversation, setWizardConversation] = useState<ConversationSnapshot['data'] | null>(null);
  const [answeredQuestionKey, setAnsweredQuestionKey] = useState("");
  const questionnaireSteps = useMemo(() => wizardQuestionnaireSteps(mode), [mode]);
  const workflowSignatureRef = useRef("");
  const loggedQuestionRef = useRef("");
  const missingResponseLogRef = useRef(false);
  const missingQuestionSignatureRef = useRef("");
  const wizardErrorRef = useRef("");
  const statusRefreshErrorRef = useRef("");
  const clusterDiagnosticRef = useRef("");
  const automaticRecoveryRef = useRef("");
  const readyContinuationRef = useRef("");
  const selectedDomain = useMemo(
    () => domains.find((domain) => domain.id === selectedIndustry) ?? domains[0],
    [domains, selectedIndustry],
  );
  const allTechnologies = useMemo(() => domains.flatMap((domain) => domain.technologies), [domains]);
  const technologyChoices = useMemo(() => {
    const executable = (technology: Technology) => !["PLANNED", "NOT_SUPPORTED"].includes(technology.implementation_status ?? "IMPLEMENTED");
    if (mode === "can") return allTechnologies.filter((technology) => executable(technology) && isCanTechnology(technology.id, technology.family));
    const choices = [...(selectedDomain?.technologies ?? []), ...allTechnologies.filter(technology =>
      recognizedEquipment.communicationSystems.some(system => technologyMatchesRecognizedSystem(technology, system)))];
    return [...new Map(choices.filter(executable).map(technology => [technology.id, technology])).values()];
  }, [allTechnologies, mode, selectedDomain, recognizedEquipment.communicationSystems]);

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
    void getWorkflowSummary(projectId).then((nextWorkflow) => {
      if (!active) return;
      setLinkedDraftId(new URL(window.location.href).searchParams.get('draft') ?? '');
      setWorkflow(nextWorkflow);
      const fallbackModelType = typeof nextWorkflow.parameters?.industry === "string"
        ? nextWorkflow.parameters.industry
        : undefined;
      const preferences = normalizeEngineeringWizardSettings(
        nextWorkflow.context.engineering_wizard_settings,
        fallbackModelType,
      );
      setProjectName(preferences.project_name);
      setSelectedIndustry(preferences.model_type);
      setScope(preferences.scope_ids);
      setProcess(preferences.process_ids);
      const legacyContext = takeLegacyWizardContext(projectId);
      const restored = restoredWizardContext(nextWorkflow.context.agent_wizard_status, projectId)
        ?? legacyContext;
      const intake = parseProjectIntake(window.sessionStorage.getItem(projectIntakeKey(projectId)), projectId);
      if (!restored) {
        if (intake) {
          setTaskText(intake);
          setIntakeRequirement(intake);
          // The new requirement must not inherit automotive defaults from another task.
          const evidence = engineeringDomainEvidence(intake);
          setSelectedIndustry(evidence.domain === 'generic'
            ? /\b(?:raspberry|rasberry|rasperry|respary)[\s-]*pi\b|\braspi\b/i.test(intake) ? 'embedded_systems' : 'custom'
            : evidence.domain);
        }
        return;
      }
      if (intake) setStatusError('Ein gespeicherter Auftrag ist bereits vorhanden. Deine neue Projektanforderung bleibt als Entwurf erhalten; der laufende Auftrag wurde nicht ersetzt.');
      setSubmittedContext(restored);
      setRunId(restored.run_id);
      wizardRunRef.current = restored.run_id;
      requestRevisionRef.current = wizardRequestRevision(nextWorkflow.context, restored.run_id);
      setScope(restored.scope_ids);
      setProcess(restored.process_ids.length ? restored.process_ids : preferences.process_ids);
      setProjectName(restored.project_name || preferences.project_name);
      setSelectedIndustry(restored.model_type || preferences.model_type);
      setTaskText(restored.task);
      setSubmittedAt(0);
      setPhase("status");
      setStep(wizardQuestionnaireSteps(restored.mode).length);
      void writeWizardDiagnostic("workflow", {
        projectId,
        runId: restored.run_id,
        step: "status-overview",
        event: "popup-status-restored",
        details: "Die Statusübersicht wurde aus dem gespeicherten Projektkontext wiederhergestellt.",
      }).catch(() => undefined);
    }).catch(() => undefined).finally(() => {
      if (active) setWizardPreferencesReady(true);
    });
    return () => {
      active = false;
    };
  }, [projectId]);

  useEffect(() => {
    if (phase !== 'questionnaire' || manualTechnologyScopeRef.current === `${mode}:${selectedDomain?.id}`) return;
    const requested = technologyChoices.filter(technology => recognizedEquipment.communicationSystems
      .some(system => technologyMatchesRecognizedSystem(technology, system))).map(technology => technology.id);
    if (requested.length) {
      setSelectedTechnologies(requested);
      return;
    }
    if (mode === "can") {
      const canIds = technologyChoices.map((technology) => technology.id);
      const preferred = ["can_fd", "can", "can_xl"].filter((id) => canIds.includes(id));
      setSelectedTechnologies(preferred.length ? preferred : canIds.slice(0, 3));
      return;
    }
    setSelectedTechnologies(defaultTechnologyIds(selectedDomain));
  }, [mode, phase, recognizedEquipment.communicationSystems, selectedDomain, technologyChoices]);

  useEffect(() => {
    if (phase !== "status" || !runId) return;
    let active = true;
    let refreshing = false;
    let routingSignature = "";
    const refreshStatus = async () => {
      if (refreshing) return;
      refreshing = true;
      const epoch = workflowEpochRef.current;
      try {
        const [nextWorkflow, conversation] = await Promise.all([getWorkflowSummary(projectId), readConversation(projectId)]);
        if (!active || epoch !== workflowEpochRef.current) return;
        setWorkflow(nextWorkflow);
        requestRevisionRef.current = wizardRequestRevision(nextWorkflow.context, runId) ?? requestRevisionRef.current;
        setWizardConversation(conversation.data);
        const nextSignature = JSON.stringify({
          versions: nextWorkflow.versions,
          routing: nextWorkflow.artifact_checks?.routing,
        });
        if (nextSignature !== routingSignature) {
          const nextRoutes = await listRoutes(projectId);
          if (!active || epoch !== workflowEpochRef.current) return;
          setRoutingEntries(nextRoutes);
          routingSignature = nextSignature;
        }
        setStatusRefreshError("");
        statusRefreshErrorRef.current = "";
      } catch (error) {
        if (!active) return;
        const message = error instanceof Error ? error.message : "Status konnte nicht geladen werden.";
        setStatusRefreshError(message);
        if (statusRefreshErrorRef.current !== message) {
          statusRefreshErrorRef.current = message;
          void writeWizardDiagnostic("error", {
            projectId,
            runId,
            step: "status-overview",
            event: "status-refresh-failed",
            details: message,
          }).catch(() => undefined);
        }
      } finally {
        refreshing = false;
      }
    };
    const handleWorkflowChanged = () => void refreshStatus();
    void refreshStatus();
    const interval = window.setInterval(refreshStatus, 5000);
    window.addEventListener(WORKFLOW_CHANGED_EVENT, handleWorkflowChanged);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener(WORKFLOW_CHANGED_EVENT, handleWorkflowChanged);
    };
  }, [phase, projectId, runId]);

  useEffect(() => {
    if (phase !== 'status' || readActiveProjectId() !== projectId) return;
    const current = wizardContextForRequest(workflow, projectId, runId, requestRevisionRef.current);
    const next = restoredWizardContext(current, projectId);
    if (!next) return;
    // Only the submitted status view follows the accepted request. Draft task,
    // questionnaire choices and an unsent supplement stay under user control.
    const request = workflow?.context.wizard_request as Record<string, unknown> | undefined;
    if (request?.parent_revision && next.hardware_counts && next.system_cluster_assignments) {
      next.planned_network_connections = plannedNetworkConnectionCount({
        architectureId: next.network_architecture?.id,
        participantLimits: normalizeEngineeringWizardSettings(workflow?.context.engineering_wizard_settings).bus_participant_limits,
        clusterAssignments: next.system_cluster_assignments,
        equipmentCounts: next.hardware_counts,
      });
    }
    setSubmittedContext(previous => JSON.stringify(previous) === JSON.stringify(next) ? previous : next);
  }, [phase, projectId, runId, workflow]);

  useEffect(() => {
    if (phase !== "status" || !runId || !wizardAgentError) return;
    const persistedExecution = readAgentRunStatus(workflow?.context?.agent_execution, runId);
    if (agentRunHasDurableOutcome(persistedExecution)) {
      setStatusError("");
      return;
    }
    if (agentRunIsActive(persistedExecution)) {
      void writeWizardDiagnostic("workflow", {
        projectId,
        runId,
        step: persistedExecution?.step ?? "popup-agent",
        event: "popup-stream-disconnected-background-continues",
        details: wizardAgentError.message || "Der Browserstream wurde getrennt; der Serverlauf arbeitet weiter.",
      }).catch(() => undefined);
      return;
    }
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
  }, [phase, projectId, runId, wizardAgentError, workflow]);

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
    const interval = window.setInterval(refreshPerformance, 10000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [phase, projectId, runId]);

  const currentQuestion = useMemo(
    () => wizardQuestionFromConversation(wizardConversation, runId),
    [runId, wizardConversation],
  );
  const currentRunMessages = useMemo(() => {
    if (!runId) return [];
    const requestIndex = wizardMessages.findLastIndex((message) => (
      message.role === "user" && textFromParts(message.parts).includes(`- Lauf-ID: ${runId}`)
    ));
    return requestIndex >= 0 ? wizardMessages.slice(requestIndex) : [];
  }, [runId, wizardMessages]);
  const execution = resolveAgentRunStep(readAgentRunStatus(workflow?.context?.agent_execution, runId), workflow?.statuses ?? {});
  const rawWizardStatus = workflow?.context?.agent_wizard_status;
  const automaticResumeCount = rawWizardStatus && typeof rawWizardStatus === "object"
    ? Math.max(0, Number((rawWizardStatus as Record<string, unknown>).automatic_resume_count) || 0)
    : submittedContext?.automatic_resume_count ?? 0;
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
  const parametersWorking = parametersAreWorking(
    agentPending,
    readAgentRunStatus(workflow?.context?.agent_execution, runId),
    parameterToolState,
  );
  const parameterProgress = useSymbolicParameterProgress(runId, parameterProgressTarget(
    parametersConfigured,
    parametersWorking ? "input-available" : undefined,
    wizardStepProgress(parameterStatus),
  ), phase === "status" && parametersWorking);

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
    if (phase !== "status" || !currentQuestion || currentQuestion.id === answeredQuestionKey || !runId) return;
    if (loggedQuestionRef.current === currentQuestion.id) return;
    loggedQuestionRef.current = currentQuestion.id;
    void writeWizardDiagnostic("question", {
      projectId,
      runId,
      step: workflow?.steps.find((item) => WORKFLOW_PROGRESS_BY_STATUS[item.status] < 100)?.id ?? "agent",
      event: "question-detected",
      details: { question_id: currentQuestion.id, question: currentQuestion.question },
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

  const technologyGroup: ChoiceGroup = useMemo(() => ({
    id: "technologies",
    label: "Netzwerktechnologien",
    multi: true,
    options: technologyChoices.map((technology) => {
      const label = technology.label ?? technologyLabel(technology.id, technology.family);
      return {
        id: technology.id,
        label,
        detail: `${technology.implementation_status ?? "IMPLEMENTED"} · ${technology.layer ?? technology.medium} · ${technology.hardware_interface ?? technology.topology}${technology.max_payload_bytes ? ` · max. ${technology.max_payload_bytes} B` : ""}`,
        value: `${label} (${technology.id})`,
      };
    }),
  }), [technologyChoices]);
  const communicationSystemSource = [
    taskSource,
    selectedIndustry,
    selectedTechnologies.join("|"),
    recognizedEquipment.communicationSystems.join("|"),
    Object.entries(recognizedEquipment.communicationSystemCounts).map(([key, value]) => `${key}:${value}`).join("|"),
  ].join("\n");
  const communicationSystemRows = useMemo(() => communicationSystemInputRows({
    edits: communicationSystemEdits.source === communicationSystemSource || extendingController ? communicationSystemEdits.values : {},
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
    plannedEquipment.chains.map((chain) => `${chain.device_type}:${chain.hardware_name}:${chain.interface_type}`).join("|"),
  ].join("\n");
  useEffect(() => {
    const controller = new AbortController();
    const endpoints = plannedEquipment.chains
      .filter((chain) => chain.device_type === "SensorController" || chain.device_type === "ActuatorController")
      .map((chain) => ({ name: chain.hardware_name, device_type: chain.device_type, interface_type: chain.interface_type }));
    const candidateControllers = plannedEquipment.chains
      .filter((chain) => isEngineeringControllerDevice(chain.device_type))
      .map((chain) => chain.hardware_name);
    if (!endpoints.length || !candidateControllers.length) {
      setLearnedEquipmentAssignments([]);
      setAssignmentLearningCorpusSize(0);
      return () => controller.abort();
    }
    void retrieveEquipmentAssignmentLearning({
      domain: previewDomain,
      endpoints,
      candidate_controllers: candidateControllers,
    }, controller.signal, projectId).then((result) => {
      setLearnedEquipmentAssignments(result.suggestions);
      setAssignmentLearningCorpusSize(result.corpus_projects);
    }).catch((error) => {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setLearnedEquipmentAssignments([]);
      }
    });
    return () => controller.abort();
  }, [plannedEquipment.chains, previewDomain]);
  const equipmentClusters = useMemo(() => buildEquipmentClusters(
    plannedEquipment.chains,
    communicationSystemCounts.map((item) => ({ id: item.id, label: item.label, count: item.count })),
    previewDomain,
    learnedEquipmentAssignments,
  ), [communicationSystemCounts, learnedEquipmentAssignments, plannedEquipment.chains, previewDomain]);
  const ecuOwnerOptions = useMemo(() => [...new Map(
    plannedEquipment.chains
      .filter((chain) => isEngineeringControllerDevice(chain.device_type))
      .map((chain) => [chain.hardware_name, chain]),
  ).values()].sort((left, right) => left.hardware_name.localeCompare(right.hardware_name, "de")), [plannedEquipment.chains]);
  const clusterEditValues = equipmentClusterEdits.source === equipmentClusterSource || extendingController ? equipmentClusterEdits.values : {};
  useEffect(() => {
    if (!extendingController) return;
    setCommunicationSystemEdits(current => ({ ...current, source: communicationSystemSource }));
    setEquipmentClusterEdits(current => ({ ...current, source: equipmentClusterSource }));
    controllerExtensionRef.current = null;
  }, [extendingController, communicationSystemSource, equipmentClusterSource]);
  const equipmentClusterAssignments: EquipmentClusterAssignment[] = useMemo(() => {
    const assignments: EquipmentClusterAssignment[] = equipmentClusters.map((cluster, index) => {
    const edit = clusterEditValues[cluster.id];
    const selected = edit?.selected ?? true;
    const requestedNetworkId = edit?.networkId || cluster.recommendedNetworkId;
    const network = communicationSystemCounts.find((item) => item.id === requestedNetworkId)
      ?? communicationSystemCounts.find((item) => item.id === cluster.recommendedNetworkId)
      ?? communicationSystemCounts[0]
      ?? { id: "", label: "Noch kein Netz", count: 0 };
    const busName = edit?.busName?.trim()
      || suggestedClusterBusName(cluster.label, index + 1, network.count > 1);
    const controllers = cluster.controllers.map((controller) => ({
      ...controller,
      sensors: [...controller.sensors],
      actuators: [...controller.actuators],
    }));
    const unassigned = cluster.unassigned.filter((leaf) => {
      const ownerName = edit?.owners?.[leaf.name] || edit?.owners?.["*"];
      if (!ownerName) return true;
      let owner = controllers.find((controller) => controller.name === ownerName);
      if (!owner) {
        const source = plannedEquipment.chains.find((chain) => isEngineeringControllerDevice(chain.device_type) && chain.hardware_name === ownerName);
        if (!source) return true;
        owner = { name: source.hardware_name, interfaceType: source.interface_type, sensors: [], actuators: [] };
        controllers.push(owner);
      }
      const assigned = { ...leaf, confidence: 1, reason: "Im Wizard bestätigte Controller-Zuordnung." };
      if (leaf.deviceType === "SensorController") owner.sensors.push(assigned);
      else owner.actuators.push(assigned);
      return false;
    });
    const reviewedCluster = { ...cluster, controllers, unassigned };
    const warnings = equipmentClusterBusWarnings(reviewedCluster, network.id, network.label);
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
      tree: controllers,
      unassigned,
      hmi_routes: selectHmiSignals(cluster.hmiRoutes, edit?.hmiSignals).map((route) => ({
        ...route,
        path: [route.source, network.label, "Gateway", route.target],
      })),
      validation: { valid: warnings.length === 0, warnings },
    };
    });
    // Apply explicit review corrections after the deterministic first pass. This
    // permits moving a leaf to a controller in another cluster and moving a whole
    // controller branch, while keeping the generated catalog itself immutable.
    for (const assignment of assignments) {
    const edit = clusterEditValues[assignment.cluster_id];
    for (const [leafName, ownerName] of Object.entries(edit?.owners ?? {})) {
      if (leafName === "*" || !ownerName) continue;
      let moved: NonNullable<EquipmentClusterAssignment["unassigned"]>[number] | undefined;
      for (const controller of assignment.tree ?? []) {
        const sensorIndex = controller.sensors.findIndex((leaf) => leaf.name === leafName);
        if (sensorIndex >= 0) moved = controller.sensors.splice(sensorIndex, 1)[0];
        const actuatorIndex = controller.actuators.findIndex((leaf) => leaf.name === leafName);
        if (actuatorIndex >= 0) moved = controller.actuators.splice(actuatorIndex, 1)[0];
      }
      const unresolvedIndex = assignment.unassigned?.findIndex((leaf) => leaf.name === leafName) ?? -1;
      if (!moved && unresolvedIndex >= 0) moved = assignment.unassigned?.splice(unresolvedIndex, 1)[0];
      if (!moved) continue;
      const targetAssignment = assignments.find((candidate) => candidate.tree?.some((controller) => controller.name === ownerName)) ?? assignment;
      let targetController = targetAssignment.tree?.find((controller) => controller.name === ownerName);
      if (!targetController) {
        const source = plannedEquipment.chains.find((chain) => isEngineeringControllerDevice(chain.device_type) && chain.hardware_name === ownerName);
        if (!source) continue;
        targetController = { name: source.hardware_name, interfaceType: source.interface_type, sensors: [], actuators: [] };
        (targetAssignment.tree ??= []).push(targetController);
      }
      const corrected = { ...moved, confidence: 1, reason: "Im Wizard als unzutreffend markiert und neu zugeordnet." };
      if (moved.deviceType === "SensorController") targetController.sensors.push(corrected);
      else targetController.actuators.push(corrected);
    }
    }
    for (const sourceAssignment of assignments) {
    const branchTargets = clusterEditValues[sourceAssignment.cluster_id]?.branchTargets ?? {};
    for (const [controllerName, targetClusterId] of Object.entries(branchTargets)) {
      if (!targetClusterId || targetClusterId === sourceAssignment.cluster_id) continue;
      const branchIndex = sourceAssignment.tree?.findIndex((branch) => branch.name === controllerName) ?? -1;
      if (branchIndex < 0) continue;
      const [branch] = sourceAssignment.tree!.splice(branchIndex, 1);
      const target = assignments.find((candidate) => candidate.cluster_id === targetClusterId);
      if (target && !target.tree?.some((candidate) => candidate.name === controllerName)) (target.tree ??= []).push(branch);
    }
    }
    for (const assignment of assignments) {
      const cluster = equipmentClusters.find(item => item.id === assignment.cluster_id)!;
      const warnings = equipmentClusterBusWarnings(reviewedEquipmentCluster(cluster, assignment, plannedEquipment.chains), assignment.network_id, assignment.network_label);
      assignment.validation = { valid: warnings.length === 0, warnings };
    }
    return assignments;
  }, [clusterEditValues, communicationSystemCounts, equipmentClusters, plannedEquipment.chains]);
  const equipmentOwnershipReady = equipmentClusterAssignments.every((assignment) => !assignment.selected || !(assignment.unassigned?.length));
  const equipmentClusterValidationReady = equipmentClusterAssignments.every((assignment) => !assignment.selected || assignment.validation?.valid !== false);
  const activeEquipmentCluster = equipmentClusters.find((cluster) => cluster.id === activeEquipmentClusterId)
    ?? equipmentClusters[0];
  const detectedDomainOption = domains.find((domain) => canonicalWizardDomain(domain.id) === detectedDomain.domain);
  const visibleSteps = [...questionnaireSteps, { id: "status", label: "Statusübersicht" }];
  const atLastStep = phase === "questionnaire" && step === questionnaireSteps.length - 1;
  const projectReady = projectName.trim().length > 0;
  const taskReady = taskText.trim().length > 0 || taskFiles.length > 0;
  const effectiveBusy = busy || submitting || !wizardPreferencesReady;
  const selectedArchitecture = architectureOption(networkArchitecture);
  const plannedNetworkConnections = plannedNetworkConnectionCount({
    architectureId: selectedArchitecture?.id,
    clusterAssignments: equipmentClusterAssignments,
    equipmentCounts,
  });
  const architectureReady = Boolean(
    selectedArchitecture
    && (networkArchitecture !== "hybrid_ai" || architectureAiProposal.trim()),
  );
  const architectureStepIndex = questionnaireSteps.findIndex((item) => item.id === "architecture");
  const clusterDiagnosticSignature = JSON.stringify({
    domain: previewDomain,
    mismatch: domainMismatch && !domainMismatchAccepted,
    clusters: equipmentClusterAssignments.map((assignment) => [
      assignment.cluster_id,
      assignment.network_id,
      assignment.devices,
      assignment.unassigned?.length ?? 0,
      assignment.validation?.warnings.length ?? 0,
    ]),
  });

  useEffect(() => {
    if (!plannedEquipment.chains.length || clusterDiagnosticRef.current === clusterDiagnosticSignature) return;
    clusterDiagnosticRef.current = clusterDiagnosticSignature;
    void writeWizardDiagnostic(domainMismatch && !domainMismatchAccepted ? "error" : "workflow", {
      projectId,
      runId,
      step: "equipment-clustering",
      event: domainMismatch && !domainMismatchAccepted ? "domain-evidence-conflict" : "cluster-preview-built",
      details: {
        selected_domain: selectedDomainId,
        effective_domain: previewDomain,
        evidence: detectedDomain,
        clusters: equipmentClusterGraphPrompt(equipmentClusterAssignments),
      },
    }).catch(() => {
      // Preview diagnostics must never interrupt the user's questionnaire.
    });
  }, [clusterDiagnosticSignature, detectedDomain, domainMismatch, domainMismatchAccepted, equipmentClusterAssignments, plannedEquipment.chains.length, previewDomain, projectId, runId, selectedDomainId]);

  function toggle(group: ChoiceGroup, optionId: string) {
    if (group.id === "technologies") {
      setSelectedTechnologies((current) => toggleSelection(current, optionId));
      manualTechnologyScopeRef.current = `${mode}:${selectedDomain?.id}`;
    }
  }

  function updateEquipmentCluster(clusterId: string, changes: {
    selected?: boolean;
    networkId?: string;
    busName?: string;
    owners?: Record<string, string>;
    verdicts?: Record<string, boolean>;
    branchTargets?: Record<string, string>;
    hmiSignals?: Record<string, boolean>;
  }) {
    setEquipmentClusterEdits((current) => {
      const values = current.source === equipmentClusterSource ? current.values : {};
      return {
        source: equipmentClusterSource,
        values: {
          ...values,
          [clusterId]: { ...values[clusterId], ...changes },
        },
      };
    });
  }

  function persistEquipmentLearning(
    records: Array<{ endpoint_name: string; controller_name: string; device_type?: string; accepted: boolean }>,
    source: string,
  ) {
    if (!records.length) return;
    void recordEquipmentAssignmentLearning({ domain: previewDomain, source, records }, projectId).catch((error) => {
      void writeWizardDiagnostic("error", {
        projectId,
        runId,
        step: "equipment-clustering",
        event: "assignment-learning-persistence-failed",
        details: error instanceof Error ? error.message : String(error),
      }).catch(() => undefined);
    });
  }

  async function handleTaskFiles(files: FileList | null, source: TaskAttachment["source"] = "task") {
    const selected = Array.from(files ?? []).slice(0, MAX_TASK_ATTACHMENTS);
    const attachments = await Promise.all(selected.map((file) => readTaskAttachment(file, source)));
    setTaskFiles((current) => mergeTaskAttachments(current, attachments));
  }

  function selectNetworkArchitecture(id: NetworkArchitectureId) {
    setNetworkArchitecture(id);
    if (id !== "hybrid_ai") setArchitectureAiProposal("");
  }

  function generateHybridArchitecture() {
    const technologies = technologyGroup.options
      .filter((option) => selectedTechnologies.includes(option.id))
      .map((option) => option.label)
      .join(", ");
    setNetworkArchitecture("hybrid_ai");
    setArchitectureAiProposal(
      `Kombiniere Variante 2 und 3. Ordne lokale, echtzeit- und regelungskritische Sensoren/Aktoren dem fachlich zuständigen Controller zu. ` +
      `Binde zentrale, diagnoseorientierte oder hochbandbreitige Teilnehmer direkt an ein System-Gateway an. ` +
      `Begründe jede Direktanbindung anhand von Semantik, Safety, Latenz und Bandbreite${technologies ? ` für ${technologies}` : ""}. ` +
      `Beruecksichtige angehaengte Architektur-Evidence wie PDF, PowerPoint, Bilder, Diagramme und Textauszuege als Quelle fuer Cluster, Knoten und Verbindungen.`,
    );
  }

  async function sendWizardOperation(
    action: WizardCommand['action'], text: string, input?: AgentInput,
    start?: { runId: string; context: AgentWizardContext; target: typeof wizardTargets[number] },
    automatic = false,
  ) {
    if (commandInFlightRef.current) return false;
    if (readActiveProjectId() !== projectId) throw new Error('Das Projekt wurde gewechselt. Diesen Auftrag im zugehörigen Projekt öffnen.');
    const activeRunId = start?.runId ?? runId;
    const revision = requestRevisionRef.current ?? wizardRequestRevision(workflow?.context, activeRunId);
    // A response may be lost after commit. Retrying the same intent retains its
    // original operation and revision even if a status poll saw the new revision.
    const signature = JSON.stringify({ action, run: activeRunId, input, text: action !== 'CONTINUE' ? text : undefined, automatic });
    const command = pendingCommandRef.current?.signature === signature ? pendingCommandRef.current.command : {
      action, run_id: activeRunId, operation_id: crypto.randomUUID(),
      ...(action !== 'START' && revision ? { request_revision: revision } : {}),
      ...(start ? { target: start.target, wizard_context: { ...start.context, engineering_wizard_settings: {
        project_name: start.context.project_name, model_type: start.context.model_type,
        scope_ids: start.context.scope_ids, process_ids: start.context.process_ids,
        bus_participant_limits: normalizeEngineeringWizardSettings(workflow?.context.engineering_wizard_settings).bus_participant_limits,
      } } } : {}),
      ...(automatic ? { automatic: true } : {}),
    } satisfies WizardCommand;
    pendingCommandRef.current = { signature, command };
    commandInFlightRef.current = true;
    workflowEpochRef.current += 1;
    try {
      await sendWizardMessage({ text }, { body: { wizard_command: command, ...(input ? { input } : {}) } });
      if (!acceptedOperationsRef.current.has(command.operation_id)) {
        // The SDK reports transport errors in state instead of rejecting its
        // promise. A lost response may still have committed this operation.
        const saved = await readConversation(projectId, undefined, undefined, { fresh: true });
        const receipt = wizardReceipt({ type: 'CONTEXT', wizard_receipt: saved.data.wizard_operations?.[command.operation_id] }, activeRunId);
        if (receipt?.operation_id === command.operation_id) {
          acceptedOperationsRef.current.add(command.operation_id);
          workflowEpochRef.current += 1;
          if (!requestRevisionRef.current || requestRevisionRef.current === command.request_revision || requestRevisionRef.current === receipt.request_revision)
            requestRevisionRef.current = receipt.request_revision;
        } else if (command.action !== 'START' && saved.data.wizard_request?.run_id === activeRunId
          && typeof saved.data.wizard_request.revision === 'string'
          && saved.data.wizard_request.revision !== command.request_revision) {
          // Another tab changed the request. With no committed receipt for this
          // operation, the old revision cannot be retried successfully. Keep
          // the user's input and let the next deliberate attempt use the new one.
          if (pendingCommandRef.current?.command.operation_id === command.operation_id) pendingCommandRef.current = null;
          requestRevisionRef.current = saved.data.wizard_request.revision;
          workflowEpochRef.current += 1;
          throw new Error('Der Auftrag wurde inzwischen geändert. Ihre Eingabe bleibt erhalten. Prüfen Sie den aktuellen Stand und versuchen Sie es erneut.');
        }
      }
      if (!acceptedOperationsRef.current.has(command.operation_id)) throw new Error('Der Server hat diese Änderung nicht bestätigt. Ihre Eingabe bleibt erhalten; aktuellen Stand prüfen und erneut versuchen.');
      if (pendingCommandRef.current?.command.operation_id === command.operation_id) pendingCommandRef.current = null;
      return true;
    } finally {
      commandInFlightRef.current = false;
      const epoch = workflowEpochRef.current;
      // The server receipt, not an attempted send, acknowledges the operation.
      void getWorkflowSummary(projectId, { fresh: true }).then(nextWorkflow => {
        if (wizardRunRef.current !== activeRunId || epoch !== workflowEpochRef.current) return;
        setWorkflow(nextWorkflow);
        requestRevisionRef.current = wizardRequestRevision(nextWorkflow.context, activeRunId) ?? requestRevisionRef.current;
        window.dispatchEvent(new Event(WORKFLOW_CHANGED_EVENT));
      }).catch(() => undefined);
    }
  }

  async function submitQuestionnaire() {
    if (effectiveBusy || startBlockers.length || !selectedArchitecture) return;
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
    const note = notes.trim() ? `- Weitere Hinweise: ${notes.trim()}\n` : "";
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
      model_type: mode === "can" ? selectedIndustry : selectedDomain?.id ?? selectedIndustry,
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
      process_ids: process,
      project_id: projectId,
      project_name: projectName.trim(),
      run_id: nextRunId,
      scope: selectedScopeValues,
      scope_ids: scope,
      task: taskText.trim() || "Aufgabe wurde als Datei übergeben.",
      technologies: selectedTechnologyValues,
      hardware_counts: equipmentCounts,
      communication_system_counts: communicationSystemCounts,
      planned_network_connections: plannedNetworkConnections,
      system_cluster_assignments: equipmentClusterAssignments,
      topology_cluster_knowledge: topologyKnowledge,
    };
    const clusterSummary = equipmentClusterSummary(equipmentClusterAssignments);
    const prompt =
      "Strukturierte Vorgaben fuer den Engineering-Agenten:\n" +
        `- Generierungsmodus: ${engineeringGenerationMode(taskSource)}\n` +
        `- Lauf-ID: ${nextRunId}\n` +
        `- Projektname: ${projectName.trim()}\n` +
        `- Abfrage erfolgt: true\n` +
        `- Abfrage-Modus: ${mode === "can" ? "reduziert fuer CAN/CAN-FD" : "vollstaendig"}\n` +
        `- Industrie: ${mode === "can" ? "aus Projektkontext ableiten" : selectedDomain?.label ?? selectedIndustry}\n` +
        `- Projekt-Modelltyp: ${mode === "can" ? selectedIndustry : selectedDomain?.id ?? selectedIndustry}\n` +
        `- Core-Modellkette: HardwareNode -> HardwareInterface -> FunctionalInterface -> TechnologyBinding -> TransportUnit -> PayloadElement\n` +
        `- Netzwerktechnologien: ${selectedTechnologyValues.length ? selectedTechnologyValues.join("; ") : "nicht vorgegeben, passende Technologien aus der gewaehlten Industrie verwenden"}\n` +
        `- Kommunikationssystem-Sollwerte: ${JSON.stringify(communicationSystemCounts)}\n` +
        `- Geplante Netzwerkverbindungen: ${plannedNetworkConnections}\n` +
        `- Systemcluster-Netzvorgaben: ${clusterSummary || "keine explizite Clusterbindung"}\n` +
        `- Bus-Teilnehmergrenzen: ${JSON.stringify(normalizeEngineeringWizardSettings(workflow?.context.engineering_wizard_settings).bus_participant_limits)}\n` +
        `- Systemcluster-Graph: ${JSON.stringify(equipmentClusterGraphPrompt(equipmentClusterAssignments, networkArchitecture))}\n` +
        `- Topologie-Cluster-Profil: ${topologyKnowledge.profile}\n` +
        `- Topologie-Cluster-Regeln: ${topologyKnowledge.ruleSummary.join("; ") || "generische Systemnaehe verwenden"}\n` +
        `- Gelernte Topologie-Nachbarschaften: ${topologyKnowledge.lessonSummary.join("; ") || "noch keine Projektkorrekturen gelernt"}\n` +
        `- RAG-Controller-Zuordnungen: ${learnedEquipmentAssignments.length} wiederverwendet aus ${assignmentLearningCorpusSize} Projekt(en)\n` +
        `- Netzarchitektur-ID: ${selectedArchitecture.id}\n` +
        `- Netzarchitektur: ${selectedArchitecture.label}\n` +
        `- Netzarchitektur-Regeln: ${selectedArchitecture.rules}\n` +
        `- Netzarchitektur-Freigabe: gemeinsam mit dem Engineering-Auftrag durch den Nutzer bestätigt am ${confirmedAt}\n` +
        `- Hardware-Sollwerte: ${JSON.stringify(equipmentCounts)}\n` +
        `- Vollstaendigkeitsprinzip: Nur benannte und bestätigte Geräte verwenden. Fehlende Geräte, Anschlüsse und funktionale Anforderungen als offene Entscheidungen behandeln; keine Beispielgeräte ergänzen.\n` +
        `${architectureAiProposal.trim() ? `- KI-Architekturvorgabe: ${architectureAiProposal.trim()}\n` : ""}` +
        `- Parameter: ${parameterSummary}\n` +
        `- Workflowumfang: ${selectedScopeValues.length ? selectedScopeValues.join("; ") : "nicht vorgegeben, Ziel aus Nutzeranfrage ableiten"}\n` +
        `- Arbeitsweise: ${selectedProcessValues.length ? selectedProcessValues.join("; ") : "nicht vorgegeben, vorsichtig mit Review-Gate arbeiten"}\n` +
        note +
        "\nKonkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:\n" +
        `${concreteTask}\n\n` +
        "Verbindliche Kanonisierung bei der Projektanlage: Pruefe vor jeder Hardware-Anlage vorhandene Systeme und verwende fachlich gleichwertige Hardware wieder. ADAS, Fahrerassistenz und Driver Assistance sind kontrollierte Synonyme desselben Systems. Eine gemeinsame Endung wie ECU ist kein Dublettenkriterium; fachlich verschiedene Systeme wie Abgasnachbehandlung und Airbag bleiben getrennt. Unterobjekte muessen an der wiederverwendeten kanonischen Hardware-ID angelegt werden.\n\n" +
        "Verbindliche Systemcluster-Regel: Ausgewaehlte Cluster bilden fachliche Systemrahmen. Sensoren, Aktoren, Steuerungen, Interfaces, Nachrichten und Signale desselben Clusters muessen zusammen bewertet, auf das gewaehlte Netz abgebildet und bei Kapazitaetsproblemen als zusammenhaengendes System verteilt werden.\n\n" +
        "Verbindlicher Kommunikationsplan: Jede Nachricht bekommt vor der Modellfreigabe ihren Zweck und ihre Empfaenger. Sensorwerte und Aktorrueckmeldungen gehen an den zugeordneten Controller, Befehle an den Aktor. Externe Empfaenger und Diagnosewege nur bei bestaetigtem Bedarf vorsehen; lokale Werte bleiben lokal. Ungeklaerte Empfaenger sind offene Entscheidungen.\n\n" +
        "Verbindliche Anzeige-Routing-Regel: Nur in hmi_routes.signals eingeschaltete Funktionsausgaenge werden zur jeweiligen Anzeige geroutet. excluded_signals sind ausgeschaltet und duerfen nicht durch automatische Empfaengerdefaults wieder hinzugefuegt werden. Lokale Berechnungen, Sensor-/Aktor-Kommunikation und andere bestaetigte Funktionsempfaenger bleiben erhalten. Bei gemeinsamer Nachricht ist eine abweichende Signalteilmenge nur mit eigenem expliziten Payload zulaessig; keine DLC-Verkleinerung ohne neue Kodierung.\n\n" +
        "Verbindliche Topologie-Regel: Systemrahmen sind kompakte Nachbarschaftsgruppen, keine ueber den ganzen View gezogenen Container. Ordne fachlich verwandte Rahmen nebeneinander an, fuehre Leitungen innerhalb und zwischen benachbarten Rahmen lokal, und gib Korrekturen des Nutzers als abstrakte Cluster-Nachbarschaften an den RAG-Kontext zurueck.\n\n" +
        "Starte jetzt die Analyse und arbeite selbststaendig bis zum genannten Zielzustand. Verwende nur ausdruecklich gewaehlte Defaults. Fehlende Geraeteidentitaeten, Anschluesse, Empfaenger und Kodierungen bleiben offene Entscheidungen. Frage bei fachlichen Entscheidungen oder Human Review erneut.";
    nextContext.agent_prompt = prompt;
    setRunId(nextRunId);
    wizardRunRef.current = nextRunId;
    requestRevisionRef.current = undefined;
    workflowEpochRef.current += 1;
    pendingCommandRef.current = null;
    acceptedOperationsRef.current.clear();
    setWizardConversation(null);
    setReviewProposal(null);
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
      const acceptedAssignments = equipmentClusterAssignments.flatMap((assignment) => (assignment.selected ? (assignment.tree ?? []).flatMap((controller) => [
        ...controller.sensors.map((leaf) => ({ endpoint_name: leaf.name, controller_name: controller.name, device_type: leaf.deviceType, accepted: true })),
        ...controller.actuators.map((leaf) => ({ endpoint_name: leaf.name, controller_name: controller.name, device_type: leaf.deviceType, accepted: true })),
      ]) : []));
      if (acceptedAssignments.length) {
        await recordEquipmentAssignmentLearning({
          domain: previewDomain,
          source: "wizard-submission",
          records: acceptedAssignments,
        }, projectId);
      }
      await Promise.all([
        writeWizardDiagnostic("workflow", {
          projectId,
          runId: nextRunId,
          step: "status-overview",
          event: "context-submitted",
          details: nextContext,
        }),
        writeWizardDiagnostic("question", {
          projectId,
          runId: nextRunId,
          step: "agent-start",
          event: "question-monitor-started",
          details: "Strukturierte Rückfragen werden mit gespeicherter Frage-ID im Statusschritt angezeigt.",
        }),
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Begleitprotokoll konnte nicht gespeichert werden.";
      void writeWizardDiagnostic("error", {
        projectId,
        runId: nextRunId,
        step: "status-overview",
        event: "submission-diagnostic-failed",
        details: message,
      }).catch(() => undefined);
    }
    try {
      const target = [...wizardTargets].reverse().find(id => scope.includes(id)) ?? 'engineering_model';
      await sendWizardOperation('START', prompt, undefined, { runId: nextRunId, context: nextContext, target });
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

  async function submitLinkedDraft() {
    if (draftStartRef.current || effectiveBusy || !linkedDraftStatus?.ready || !projectName.trim() || !scope.length) return;
    draftStartRef.current = true;
    setSubmitting(true); setStatusError('');
    const nextRunId = crypto.randomUUID();
    try {
      const response = await fetch('/api/engineering/agent/project-draft/workflow-request', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Project-ID': projectId },
        body: JSON.stringify({ draft_id: linkedDraftId, revision: linkedDraftStatus.revision,
          run_id: nextRunId, project_name: projectName.trim(), scope_ids: scope }),
      });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.findings?.[0]?.message ?? 'Der Entwurf kann noch nicht gestartet werden.');
      if (readActiveProjectId() !== projectId) throw new Error('Das aktive Projekt wurde gewechselt.');
      const nextContext = result.data.context as AgentWizardContext;
      if (nextContext.project_id !== projectId || nextContext.run_id !== nextRunId) throw new Error('Der vorbereitete Auftrag gehört nicht zu diesem Projekt.');
      const target = wizardTargets.find(value => value === result.data.target);
      if (!target) throw new Error('Ungültiges Workflowziel.');
      setRunId(nextRunId); wizardRunRef.current = nextRunId; requestRevisionRef.current = undefined;
      workflowEpochRef.current += 1; pendingCommandRef.current = null; acceptedOperationsRef.current.clear();
      setWizardConversation(null); setReviewProposal(null); setSubmittedAt(Date.now()); setSubmittedContext(nextContext);
      activateEngineeringAgentWizardSession(projectId); setPhase('status'); setStep(questionnaireSteps.length);
      workflowSignatureRef.current = ''; loggedQuestionRef.current = ''; missingResponseLogRef.current = false;
      missingQuestionSignatureRef.current = '';
      await sendWizardOperation('START', result.data.prompt, undefined, { runId: nextRunId, context: nextContext, target });
    } catch (error) {
      setStatusError(agentErrorText(error instanceof Error ? error.message : 'Der Workflow konnte nicht gestartet werden.'));
    } finally { draftStartRef.current = false; setSubmitting(false); }
  }

  function handlePrimary() {
    if (atLastStep || (phase === 'questionnaire' && step === questionnaireSteps.length)) {
      void submitQuestionnaire();
      return;
    }
    setStep((current) => {
      if (questionnaireSteps[current]?.id === "project" && !projectReady) return current;
      if (questionnaireSteps[current]?.id === "architecture" && !architectureReady) return current;
      return Math.min(current + 1, questionnaireSteps.length - 1);
    });
  }

  async function finishWizard() {
    if (agentPending || routingReviewBusy || supplementBusy || routingReviewPending || runPaused) return;
    try {
      const response = await fetch(`/api/engineering/agent/runs/${encodeURIComponent(runId)}/finish`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Project-ID': projectId },
        body: JSON.stringify({ request_revision: requestRevisionRef.current ?? wizardRequestRevision(workflow?.context, runId) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? result.findings?.[0]?.message ?? 'Der Auftrag ist noch nicht vollständig abgeschlossen.');
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
    try {
      const canceledWorkflow = await requestWizardCancellation(projectId, activeRunId, {
        requestRevision: requestRevisionRef.current ?? wizardRequestRevision(workflow?.context, activeRunId),
        onConfirmed: () => {
          setCancelBusy(true);
          setStatusError("");
          stopWizardMessage();
        },
      });
      if (!canceledWorkflow) return;
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
    if (group.id === "technologies") return selectedTechnologies;
    return [];
  }

  function activeGroupForStep() {
    if (phase === "status") return null;
    const id = questionnaireSteps[step]?.id;
    if (id === "technologies") return technologyGroup;
    return null;
  }

  async function answerInlineQuestion(answer: AgentInput) {
    if (!currentQuestion || currentQuestion.id === answeredQuestionKey || agentPending || !runId) return;
    if (!('question_id' in answer) || answer.question_id !== currentQuestion.id) return;
    await writeWizardDiagnostic("question", {
      projectId,
      runId,
      step: workflow?.steps.find((item) => WORKFLOW_PROGRESS_BY_STATUS[item.status] < 100)?.id ?? "agent",
      event: "question-answered",
      details: { question_id: currentQuestion.id, answer },
    }).catch((error) => {
      setStatusError(error instanceof Error ? error.message : "Antwortprotokoll konnte nicht geschrieben werden.");
    });
    try {
      if (!await sendWizardOperation('CONTINUE', answer.type === 'SKIP_QUESTION' ? 'Optionale Rückfrage überspringen.' : 'Auswahl zur Agentenrückfrage übernehmen.', answer)) return;
      const conversation = await readConversation(projectId, undefined, undefined, { fresh: true });
      setWizardConversation(conversation.data);
      if (conversation.data.questions[answer.question_id]?.status !== 'OPEN') setAnsweredQuestionKey(answer.question_id);
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Die Antwort konnte nicht an den Popup-Agenten gesendet werden.";
      setStatusError(agentErrorText(rawMessage));
      setAnsweredQuestionKey("");
      await writeWizardDiagnostic("error", {
        projectId,
        runId,
        step: "popup-agent",
        event: "popup-answer-failed",
        details: rawMessage,
      }).catch(() => undefined);
    }
  }

  async function retryPopupRun(automatic = false, reason: "recovery" | "review" = "recovery") {
    if (agentPending || !runId) return;
    setStatusError("");
    try {
      const savedWizard = workflow?.context.agent_wizard_status as Record<string, unknown> | undefined;
      if (savedWizard?.run_id !== runId && submittedContext?.agent_prompt) {
        const target = [...wizardTargets].reverse().find(id => submittedContext.scope_ids.includes(id)) ?? 'engineering_model';
        await sendWizardOperation('START', submittedContext.agent_prompt, undefined, { runId, context: submittedContext, target });
        return;
      }
      await writeWizardDiagnostic("workflow", {
        projectId,
        runId,
        step: "agent-start",
        event: reason === "review" ? "popup-agent-review-continued" : automatic ? "popup-agent-auto-recovered" : "popup-agent-resumed",
        details: 'Fortsetzung des gespeicherten Auftrags mit seiner aktuellen Revision und seinem bestätigten Ziel.',
      }).catch(() => undefined);
      await sendWizardOperation('CONTINUE', reason === 'review' ? 'Nach der Freigabe fortfahren.' : 'Gespeicherten Auftrag fortsetzen.', { type: 'RESUME' }, undefined, automatic && reason === 'recovery');
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
      await approveRoutes(routeIds, projectId);
      const [nextWorkflow, nextRoutes] = await Promise.all([getWorkflowSummary(projectId, { fresh: true }), listRoutes(projectId)]);
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
        await sendWizardOperation('CONTINUE', `${routeIds.length} Routing-Einträge freigegeben. Auftrag fortsetzen.`, { type: 'RESUME' });
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
      if (!await sendWizardOperation('AMEND', addition)) return;
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

  async function adoptLinkedDraftRevision() {
    if (supplementBusy || agentPending || !runId || !submittedContext || !linkedDraftStatus?.ready) return;
    setSupplementBusy(true); setStatusError('');
    try {
      if (readActiveProjectId() !== projectId) throw new Error('Das aktive Projekt wurde gewechselt.');
      const response = await fetch('/api/engineering/agent/project-draft/workflow-request', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Project-ID': projectId },
        body: JSON.stringify({ draft_id: linkedDraftStatus.draftId, revision: linkedDraftStatus.revision,
          run_id: runId, project_name: submittedContext.project_name, scope_ids: submittedContext.scope_ids }),
      });
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.findings?.[0]?.message ?? 'Entwurf benötigt weitere Angaben.');
      if (readActiveProjectId() !== projectId) throw new Error('Das aktive Projekt wurde gewechselt.');
      const nextContext = result.data.context as AgentWizardContext;
      const target = wizardTargets.find(value => value === result.data.target);
      if (nextContext.project_id !== projectId || nextContext.run_id !== runId || !target) throw new Error('Ungültiger aktualisierter Auftrag.');
      if (!await sendWizardOperation('AMEND', result.data.prompt, undefined, { runId, context: nextContext, target })) return;
      setSubmittedContext(nextContext); setReviewProposal(null); setSupplementOpen(false);
    } catch (error) {
      setStatusError(agentErrorText(error instanceof Error ? error.message : 'Entwurfsrevision konnte nicht übernommen werden.'));
    } finally { setSupplementBusy(false); }
  }

  const activeGroup = activeGroupForStep();
  const activeStepId = visibleSteps[step]?.id ?? "status";
  const startBlockers = [
    ...(!projectReady ? [{ step: 'project', text: 'Bitte einen Projektnamen eingeben.' }] : []),
    ...(!taskReady ? [{ step: 'task', text: 'Bitte die Projektbeschreibung ergänzen.' }] : []),
    ...(!architectureReady ? [{ step: 'architecture', text: 'Bitte die Architektur auswählen und vervollständigen.' }] : []),
    ...(!equipmentReady ? [{ step: 'equipment', text: intakeRequirement && equipmentValues.actuators === ''
      ? 'Die Anzahl der Ventile bzw. Aktoren ist noch offen.' : 'Die verbindlichen Geräteanzahlen fehlen oder sind ungültig.' }] : []),
    ...(!equipmentOwnershipReady ? [{ step: 'equipment', text: 'Die Zuordnung der Teilnehmer zu ihren Controllern ist noch offen.' }] : []),
    ...(!equipmentIdentityReady ? [{ step: 'equipment', text: 'Geräteanzahl und konkret benannte Geräte stimmen noch nicht überein. Bitte Geräte in der Anforderung benennen; fehlende Geräte werden nicht erfunden.' }] : []),
    ...(unresolvedConnections.length ? [{ step: 'equipment', text: `Anschlüsse festlegen: ${unresolvedConnections.map(chain => chain.hardware_name).join(', ')}. Eine Auswahl für den Controller ersetzt nicht die Anschlüsse seiner Sensoren und Aktoren.` }] : []),
    ...(!equipmentClusterValidationReady ? [{ step: 'equipment', text: 'Die markierten Cluster benötigen eine zulässige Buswahl.' }] : []),
    ...(!communicationSystemReady ? [{ step: 'equipment', text: 'Bitte die Anzahl der Kommunikationssysteme korrigieren.' }] : []),
    ...(domainMismatch && !domainMismatchAccepted ? [{ step: 'equipment', text: 'Industrieangabe und Geräte passen noch nicht zusammen.' }] : []),
  ];
  const primaryDisabled = effectiveBusy
    || ((atLastStep || activeStepId === 'status') && startBlockers.length > 0)
    || (activeStepId === "project" && !projectReady)
    || (activeStepId === "task" && !taskReady)
    || (activeStepId === "architecture" && !architectureReady);
  const visibleQuestion = currentQuestion?.id === answeredQuestionKey ? null : currentQuestion;
  const persistedStatusRows = SCOPE_GROUP.options.map((option, index) => {
    const workflowStepId = option.id as WorkflowStepId;
    const workflowStep = workflow?.steps.find((item) => item.id === workflowStepId);
    const revisedModelPending = workflowStepId === 'engineering_model' && execution?.model_review_required === true;
    const artifactComplete = !revisedModelPending && ["COMPLETE", "APPROVED", "WARNING"].includes(workflowStep?.status ?? "EMPTY");
    const blocked = !artifactComplete && execution?.step === workflowStepId && execution.state === "BLOCKED";
    const staleRunning = !artifactComplete && execution?.step === workflowStepId && execution.state === "RUNNING" && executionStopped;
    const building = !artifactComplete && execution?.step === workflowStepId && (execution.state === "RUNNING" || blocked);
    const awaitingReview = !artifactComplete && agentReviewStep(execution) === workflowStepId;
    const workflowStatus: WorkflowStatus = staleRunning
      ? "ERROR"
      : revisedModelPending ? 'IN_PROGRESS' : workflowStep?.status ?? "EMPTY";
    const displayStatus: WorkflowDisplayStatus = blocked ? "BLOCKED" : awaitingReview ? "REVIEW_REQUIRED" : workflowStatus;
    return {
      displayStatus,
      id: workflowStepId,
      label: option.label.replace(/^\d+\s+/, ""),
      position: index + 1,
      progress: building
        ? Math.min(99, agentBuildProgressPercent(execution))
        : awaitingReview ? 99 : wizardStepProgress(workflowStatus),
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
  const modelReviewPending = !agentPending && agentReviewStep(execution) === "engineering_model"
    && (execution?.model_review_required || !["COMPLETE", "APPROVED", "WARNING"].includes(workflow?.statuses.engineering_model ?? "EMPTY"));
  const routingReviewPending = !agentPending
    && !executionStopped && !routingReview.complete
    && !modelReviewPending && (routingReview.total > 0 || agentReviewStep(execution) === "routing");
  const workflowReviewPending = !agentPending && execution?.state === "REVIEW_REQUIRED";
  const runPaused = !agentPending && !workflowReviewPending && !routingReviewPending && !modelReviewPending
    && (executionStopped || persistedStatusRows.some((item) => item.selected && !["COMPLETE", "APPROVED", "WARNING"].includes(item.status)));
  const canRetryPopupRun = wizardRunCanRetry(runPaused, hasResumablePrompt, execution);
  const needsAutomaticRecovery = wizardRunNeedsAutomaticRecovery({
    runPaused,
    hasResumablePrompt,
    run: execution,
    automaticResumeCount,
    restoredSession: submittedAt === 0,
  });
  useEffect(() => {
    const recoveryKey = `${runId}:${execution?.updated_at ?? 'restored'}`;
    if (!needsAutomaticRecovery || !runId || automaticRecoveryRef.current === recoveryKey) return;
    automaticRecoveryRef.current = recoveryKey;
    void retryPopupRun(true);
  }, [needsAutomaticRecovery, runId, execution?.updated_at]);
  useEffect(() => {
    const key = execution?.state === "READY_TO_CONTINUE"
      ? `${execution.run_id}:${execution.step}:${execution.updated_at}`
      : "";
    if (!key || agentPending || !hasResumablePrompt || readyContinuationRef.current === key) return;
    readyContinuationRef.current = key;
    void retryPopupRun(true, "review");
  }, [agentPending, execution?.run_id, execution?.state, execution?.step, execution?.updated_at, hasResumablePrompt]);
  const lastAssistantText = [...currentRunMessages].reverse()
    .find((message) => message.role === "assistant" && textFromParts(message.parts).trim());
  const runMessage = execution?.state === "RUNNING" && executionStopped
    ? `Seit mehr als zwei Minuten liegt kein Laufstatus vor. Letzter Stand: ${execution.message}`
    : execution?.message || (lastAssistantText ? textFromParts(lastAssistantText.parts) : "");
  const approvableRoutingCount = routingReview.routes.filter(
    (route) => route.validation?.valid === true && String(route.approval_state).toUpperCase() !== "APPROVED",
  ).length;
  const engineeringCounts = workflow?.artifact_checks?.engineering_model?.counts ?? {};
  const proposalChanges = reviewProposal?.changes ?? [];
  const proposalCount = (objectType: string) => proposalChanges.filter((change) => change.object_type === objectType).length;
  const proposedRoutingCount = proposalCount("RoutingEntry");
  const displayedRoutingTotal = routingReview.total || proposedRoutingCount;
  const displayedRoutingValid = routingReview.total > 0 ? approvableRoutingCount
    : proposedRoutingCount > 0 ? reviewProposal?.validation_result.valid_count
      ?? (["VALIDATED", "APPROVED", "APPLIED"].includes(String(reviewProposal?.status)) ? proposedRoutingCount : 0) : 0;
  const submittedEquipment = useMemo(() => submittedContext?.agent_prompt
    ? extractEngineeringSpecification(
        submittedContext.agent_prompt,
        submittedContext.hardware_counts ?? {},
        submittedContext.model_type,
      )
    : null, [submittedContext]);
  const hardwareRevision = workflow?.versions?.engineering_model;
  useEffect(() => {
    if (phase !== "status") return;
    let active = true;
    void listAllEngineeringObjects("hardware-nodes", projectId).then((items) => {
      if (active) setHardwareItems(items);
    }).catch(() => undefined);
    return () => { active = false; };
  }, [phase, hardwareRevision]);
  const hardwareByType = workflow?.artifact_checks?.engineering_model?.hardware_by_type ?? {};
  const hardwareNodes = Array.isArray(workflow?.topology?.nodes) ? workflow.topology.nodes : [];
  const proposalHardware = proposalChanges
    .filter((change) => change.object_type === "HardwareNode")
    .map((change, index) => ({
      id: change.local_ref ?? `proposal-hardware-${index}`,
      name: String(change.data?.name ?? change.object_name ?? change.local_ref ?? "HardwareNode"),
      device_type: String(change.data?.device_type ?? ""),
    }));
  const controllerCount = Object.entries(hardwareByType)
    .filter(([deviceType]) => isEngineeringControllerDevice(deviceType))
    .reduce((total, [, count]) => total + Number(count), 0);
  const hardwareDetails = {
    ecus: controllerCount || hardwareNodes.filter((node) => String(node.kind).toLowerCase() === "ecu").length || proposalHardware.filter((item) => isEngineeringControllerDevice(item.device_type)).length || submittedEquipment?.targetCounts.ecus || 0,
    gateways: Number(hardwareByType.Gateway ?? hardwareNodes.filter((node) => String(node.kind).toLowerCase() === "gateway").length) || proposalHardware.filter((item) => item.device_type === "Gateway").length || submittedEquipment?.targetCounts.gateways || 0,
    sensors: Number(hardwareByType.SensorController ?? hardwareNodes.filter((node) => String(node.kind).toLowerCase() === "sensor").length) || proposalHardware.filter((item) => item.device_type === "SensorController").length || submittedEquipment?.targetCounts.sensors || 0,
    actuators: Number(hardwareByType.ActuatorController ?? hardwareNodes.filter((node) => String(node.kind).toLowerCase() === "actuator").length) || proposalHardware.filter((item) => item.device_type === "ActuatorController").length || submittedEquipment?.targetCounts.actuators || 0,
  };
  const displayedHardwareItems = hardwareItems.length > 0
    ? hardwareItems.map((item) => ({
        id: item.id,
        name: String(item.name),
        device_type: "device_type" in item ? String(item.device_type) : "",
      }))
    : proposalHardware.length > 0 ? proposalHardware : (submittedEquipment?.chains ?? []).map((item, index) => ({
        id: `proposal-${item.device_type}-${item.hardware_name}-${index}`,
        name: item.hardware_name,
        device_type: item.device_type,
      }));
  const displayedPlannedNetworkConnections = submittedContext?.planned_network_connections ?? plannedNetworkConnectionCount({
    architectureId: submittedContext?.network_architecture?.id ?? selectedArchitecture?.id,
    participantLimits: normalizeEngineeringWizardSettings(workflow?.context.engineering_wizard_settings).bus_participant_limits,
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
      value: Number(engineeringCounts.functions ?? 0) || proposalCount("Function"),
      detail: "Soll nach Class-Modell nur fuer Class 3/4 automatisch entstehen. Basic/Passive Sensoren und Aktoren bleiben ohne kuenstliche Function.",
    },
    {
      label: "Interfaces",
      value: Number(engineeringCounts.interfaces ?? 0) || proposalCount("Interface"),
      detail: "Logische Interfaces werden je Teilnehmer oder Subsystem erzeugt. Direkte Hardware-Interfaces zaehlen separat im Hardware-Interface-Modell.",
    },
    {
      label: "Nachrichten",
      value: Number(engineeringCounts.messages ?? 0) || proposalCount("Message"),
      detail: "Gepackte Kommunikationsobjekte. Mehrere Signale koennen eine Nachricht teilen, wenn Bus, Zyklus und Producer passen.",
    },
    {
      label: "Signale",
      value: Number(engineeringCounts.signals ?? 0) || proposalCount("Signal"),
      detail: "Einzelne Werte, Statuscodes, Commands oder Datenindikatoren innerhalb der Nachrichten.",
    },
    {
      label: "Netzverbindungen",
      value: displayedPlannedNetworkConnections,
      detail: "Geplante physische oder logische Netzpfade aus Architektur, Clustern und Teilnehmerumfang.",
    },
    {
      label: "Routen",
      value: displayedRoutingTotal,
      detail: "Vorbereitete Routing-Pfade, die vor der Uebernahme validiert und freigegeben werden muessen.",
    },
  ];
  const analysisHeading = wizardAnalysisHeading({
    agentPending,
    currentStep: currentStatusStep,
    executionState: execution?.state,
    modelReviewPending,
    routingReviewPending,
    runPaused,
  });

  if (linkedDraftId && phase === 'questionnaire') return <section className="eng-agent-questionnaire" aria-label="Geführte Agent-Rückfrage">
    <h3>Gespeicherten Projektentwurf ausführen</h3>
    <p>Chat und Wizard verwenden denselben Entwurf. Speichere die Angaben, bevor du den gewünschten Workflow startest.</p>
    <label>Projektname<input value={projectName} maxLength={120} disabled={effectiveBusy} onChange={event => setProjectName(event.target.value)} /></label>
    <ProjectDraftEditor projectId={projectId} draftId={linkedDraftId} onStateChange={setLinkedDraftStatus} />
    <fieldset disabled={effectiveBusy}><legend>Workflowumfang</legend>
      {SCOPE_GROUP.options.map(option => <label key={option.id}><input type="checkbox" checked={scope.includes(option.id)}
        onChange={() => setScope(current => current.includes(option.id) ? current.filter(id => id !== option.id) : [...current, option.id])} />{option.label}</label>)}
    </fieldset>
    {statusError && <p role="alert">{statusError}</p>}
    <button type="button" className="button primary" disabled={effectiveBusy || !linkedDraftStatus?.ready || !projectName.trim() || !scope.length}
      onClick={() => void submitLinkedDraft()}>{submitting ? 'Wird übernommen …' : 'Auftrag starten'}</button>
  </section>;

  return (
    <section className="eng-agent-questionnaire" aria-label="Geführte Agent-Rückfrage">
      <div className="eng-agent-questionnaire-head">
        <div>
          <strong>{title}</strong>
          <span>{visibleSteps[step]?.label}: Schritt {step + 1} von {visibleSteps.length}</span>
        </div>
        {phase === "status" ? (
          <span className={`agent-wizard-live ${displayedStatusError || runPaused ? "error" : ""}`}><i aria-hidden="true" /> {displayedStatusError ? "Diagnosehinweis" : agentPending ? "Agent arbeitet" : runPaused ? "Angehalten" : workflowReviewPending || routingReviewPending ? "Freigabe erforderlich" : "Live"}</span>
        ) : (
          <button className="button primary tiny" disabled={primaryDisabled} onClick={handlePrimary} type="button">
            {submitting ? "Wird übernommen ..." : activeStepId === 'status' ? 'Auftrag starten' : atLastStep ? "Übernehmen" : "Weiter"}
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
              || (item.id !== 'status' && index > 0 && !projectReady)
              || (item.id === "equipment" && !taskReady)
              || (item.id !== 'status' && index > architectureStepIndex && !architectureReady)
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
      {activeStepId === "project" && (
        <fieldset className="agent-choice-group agent-project-name-step">
          <legend>Projekt benennen</legend>
          <label htmlFor="engineering-project-name">
            <span>Projektname</span>
            <input
              autoFocus
              disabled={effectiveBusy}
              id="engineering-project-name"
              maxLength={120}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="z. B. NIS Restbussimulation"
              value={projectName}
            />
            <small>Die lesbare Bezeichnung wird im Projektkontext gespeichert. Die technische Projekt-ID bleibt unverändert.</small>
          </label>
          <label className="agent-questionnaire-note">
            <span>Projektbeschreibung</span>
            <textarea disabled={effectiveBusy} rows={5} value={taskText}
              maxLength={intakeRequirement !== null ? 16000 : undefined}
              placeholder="Was soll dieses Projekt leisten?"
              onChange={(event) => {
                const requirement = event.target.value;
                setTaskText(requirement);
                if (intakeRequirement !== null) {
                  setIntakeRequirement(requirement);
                  window.sessionStorage.setItem(projectIntakeKey(projectId), JSON.stringify({ projectId, requirement }));
                }
              }} />
            <small>Diese Beschreibung ist zugleich der Aufgabentext für den Agenten. Änderungen auf beiden Seiten werden gemeinsam übernommen.</small>
          </label>
        </fieldset>
      )}
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
                onChange={(event) => setArchitectureAiProposal(event.target.value)}
                placeholder="Beschreibe, welche Teilnehmer lokal über einen Controller oder direkt über ein System-Gateway geführt werden sollen."
                rows={3}
                value={architectureAiProposal}
              />
            </label>
          )}
        </fieldset>
      )}
      {activeStepId === "task" && (
        <fieldset className="agent-choice-group">
          <legend>Aufgabe</legend>
          <label className="agent-questionnaire-note">
            <span>Aufgabentext</span>
            <textarea
              disabled={busy}
              onChange={(event) => {
                const requirement = event.target.value;
                setTaskText(requirement);
                if (intakeRequirement !== null) {
                  setIntakeRequirement(requirement);
                  window.sessionStorage.setItem(projectIntakeKey(projectId), JSON.stringify({ projectId, requirement }));
                }
              }}
              maxLength={intakeRequirement !== null ? 16000 : undefined}
              placeholder="Beschreibe das konkrete Ziel, z. B. arbeite bis zur Simulation ..."
              rows={4}
              value={taskText}
            />
          </label>
          <label className="agent-questionnaire-note">
            <span>Weitere Hinweise</span>
            <textarea
              disabled={busy}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Optional: besondere Protokolle, Safety, Timing oder Herstellerlogik …"
              rows={2}
              value={notes}
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
            <svg aria-hidden="true" className="agent-file-drop-icon" viewBox="0 0 24 24">
              <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 14v4.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V14" />
            </svg>
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
          {domainMismatch && !domainMismatchAccepted && (
            <section className="agent-domain-conflict" role="alert">
              <div>
                <strong>Industrieangabe und Anlage widersprechen sich</strong>
                <p>
                  Aus der Anlage wird <b>{detectedDomainOption?.label ?? detectedDomain.domain}</b> erkannt,
                  ausgewählt ist <b>{selectedDomain?.label ?? selectedIndustry}</b>.
                  Ohne Klärung würden Vorschau, Clusterung und Agent unterschiedliche Vorlagen verwenden.
                </p>
                <small>Evidence: {detectedDomain.markers.join(", ")}</small>
              </div>
              <div className="agent-domain-conflict-actions">
                {detectedDomainOption && (
                  <button className="button primary tiny" disabled={effectiveBusy} onClick={() => {
                    setSelectedIndustry(detectedDomainOption.id);
                    setAcceptedDomainMismatch("");
                  }} type="button">
                    {detectedDomainOption.label} übernehmen
                  </button>
                )}
                <button className="button secondary tiny" disabled={effectiveBusy} onClick={() => setAcceptedDomainMismatch(domainMismatchSignature)} type="button">
                  {selectedDomain?.label ?? selectedIndustry} bewusst beibehalten
                </button>
              </div>
            </section>
          )}
          {domainMismatchAccepted && (
            <p className="agent-domain-override"><strong>Bewusste Abweichung:</strong> {selectedDomain?.label ?? selectedIndustry} wird trotz erkannter {detectedDomainOption?.label ?? detectedDomain.domain}-Evidence verwendet.</p>
          )}
          <table className="agent-equipment-table">
            <thead><tr><th>Gerätetyp</th><th>Anzahl</th></tr></thead>
            <tbody>{EQUIPMENT_CATEGORIES.map(({ key, label }) => (
              <tr key={key}>
                <th scope="row">{label}</th>
                <td>
                  <div className="agent-count-stack">
                    <span><small>Erkannt</small><b>{identifiedCounts[key]}</b></span>
                    {recognizedEquipment.targetCounts[key] !== identifiedCounts[key] && <span><small>Im Text genannt</small><b>{recognizedEquipment.targetCounts[key]}</b></span>}
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
          {!equipmentIdentityReady && <p role="alert">Geräteumfang noch unvollständig: {EQUIPMENT_CATEGORIES.filter(({ key }) => identifiedCounts[key] !== equipmentCounts[key]).map(({ key, label }) => `${label}: ${identifiedCounts[key]} erkannt, ${equipmentCounts[key]} vorgegeben`).join('; ')}. Eine Anzahl allein beschreibt noch keine Gerätefunktion. Ergänze in der Anforderung, was die Sensoren messen und was die Aktoren steuern, zum Beispiel „3 Temperatursensoren und 4 Ventilaktoren“.{networkArchitecture === 'sensor_ecu_actuator' && equipmentCounts.gateways === 0 && ' Für diesen lokalen Regelkreis ist kein Gateway erforderlich.'}</p>}
          {identifiedCounts.ecus < equipmentCounts.ecus && <section aria-label="Controller ergänzen" className="agent-cluster-review">
            <label>Controller im Auftrag ergänzen<input aria-label="Name des zusätzlichen Controllers" value={newControllerName} disabled={effectiveBusy} onChange={event => setNewControllerName(event.target.value)} placeholder="z. B. RaspberryPi" /></label>
            <button type="button" disabled={effectiveBusy || !newControllerName.trim()} onClick={addRequestedController}>Controller ergänzen</button>
            {controllerAdditionError && <p role="alert">{controllerAdditionError}</p>}
          </section>}
          {!equipmentIdentityReady && <button className="button secondary" type="button" disabled={effectiveBusy} onClick={() => setStep(questionnaireSteps.findIndex(item => item.id === 'task'))}>Anforderung korrigieren</button>}
          {(sensorRows.length > 0 || unresolvedConnections.length > 0 || /^- Geräteanschlüsse:/m.test(taskText)) && <section className="agent-cluster-review" aria-label="Geräteanschlüsse festlegen">
            <h3>Geräteanschlüsse festlegen</h3>
            <p>Wähle für jeden Sensor zuerst die Messgröße und dann den Verbindungstyp. Bereits erkannte Messgrößen sind vorausgewählt. Die Verbindung wird unabhängig davon festgelegt. Für einen Entwurf gilt deine Auswahl als Modellannahme, nicht als Nachweis realer Hardware.</p>
            {deviceRows.map(({ name, label, chain, sensor }) => <div className="agent-device-connection" key={name}><span>{label}</span>
              {sensor && <label className="agent-device-choice"><span>Messgröße</span><select aria-label={`${label}: Messgröße`} disabled={effectiveBusy} value={String(chain?.configuration?.sensor_measurement ?? sensorMeasurement(name, chain?.signal_name)?.id ?? '')} onChange={event => setTaskText(selectSensorMeasurement(taskText, name, event.target.value))}>
                <option value="" disabled>Bitte auswählen</option>
                {SENSOR_MEASUREMENTS.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select></label>}
              <label className="agent-device-choice"><span>Verbindungstyp</span><select aria-label={`${name}: Anschluss`} disabled={effectiveBusy || (sensor && !chain)} value={!chain || chain.interface_type === 'Other' ? '' : chain.interface_type} onChange={event => selectDeviceConnection(name, event.target.value)}>
                <option value="">Bitte auswählen</option>
                {[...new Set(['I2C', 'SPI', 'UART', 'ModbusRTU', 'ModbusTCP', 'GPIO', 'PWM', 'ADC', 'DAC', ...(chain?.interface_type && chain.interface_type !== 'Other' ? [chain.interface_type] : [])])].map(technology => <option key={technology} value={technology}>{technology}</option>)}
              </select></label>
            </div>)}
            {unresolvedConnections.length > 0 && <p role="alert">Noch offen: {unresolvedConnections.map(chain => chain.hardware_name).join(', ')}</p>}
          </section>}
          {intakeRequirement && equipmentValues.actuators === '' && <p role="alert">Ventile oder Aktoren sind genannt, ihre Anzahl ist noch offen. Bitte die verbindliche Anzahl ergänzen.</p>}
          {!communicationSystemReady && <p role="alert">Die Anzahl der Kommunikationssysteme muss je Technologie zwischen 0 und 1000 liegen.</p>}
          {!equipmentOwnershipReady && <p role="alert">Vor der Übergabe müssen alle Teilnehmer aktiver Cluster einem Controller zugeordnet oder der betreffende Cluster abgewählt werden.</p>}
          {equipmentOwnershipReady && !equipmentClusterValidationReady && <p role="alert">Mindestens ein aktiver Cluster besitzt noch eine fachlich unzulässige Buswahl. Öffne den markierten Cluster und wähle ein geeignetes Netz.</p>}
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
                  <strong>Systemcluster schrittweise prüfen</strong>
                  <span>Je Cluster zuerst Controller-Besitz und Teilnehmer, danach Bus und HMI-Routing bestätigen.</span>
                </div>
                <small>{equipmentClusterAssignments.filter((item) => item.selected).length}/{equipmentClusterAssignments.length} aktiv</small>
              </div>
              <p className="agent-cluster-valid">
                RAG: {learnedEquipmentAssignments.length} bestätigte Zuordnung(en) aus {assignmentLearningCorpusSize} früheren Projekt(en) wiederverwendet.
              </p>
              <label className="agent-cluster-selector">
                <span>Cluster</span>
                <select disabled={effectiveBusy} onChange={(event) => setActiveEquipmentClusterId(event.target.value)} value={activeEquipmentCluster?.id ?? ""}>
                  {equipmentClusters.map((cluster, index) => {
                    const assignment = equipmentClusterAssignments.find((item) => item.cluster_id === cluster.id);
                    return <option key={cluster.id} value={cluster.id}>{assignment?.validation?.valid === false ? "⚠ " : ""}{index + 1}. {cluster.label} · {cluster.devices.length} Teilnehmer</option>;
                  })}
                </select>
              </label>
              {activeEquipmentCluster && (() => {
                const cluster = activeEquipmentCluster;
                const assignment = equipmentClusterAssignments.find((item) => item.cluster_id === cluster.id);
                const selected = assignment?.selected ?? true;
                const networkId = assignment?.network_id ?? cluster.recommendedNetworkId;
                const assignedNetwork = communicationSystemCounts.find((item) => item.id === networkId);
                const busName = assignment?.bus_name ?? suggestedClusterBusName(cluster.label, 1, (assignedNetwork?.count ?? 0) > 1);
                const issues = equipmentClusterBusIssues(assignment ? reviewedEquipmentCluster(cluster, assignment, plannedEquipment.chains) : cluster, networkId, assignedNetwork?.label);
                const warningFor = (name: string) => issues.flatMap(issue => issue.affected.filter(item => item.name === name).map(item => item.detail)).join("; ");
                const participantId = (name: string) => `cluster-participant-${encodeURIComponent(cluster.id)}-${encodeURIComponent(name)}`;
                const showParticipant = (name: string) => {
                  const element = document.getElementById(participantId(name));
                  const branch = element?.closest("details");
                  if (branch) branch.open = true;
                  element?.scrollIntoView({ block: "center", behavior: "smooth" });
                  element?.focus({ preventScroll: true });
                };
                const controllerTree = assignment?.tree ?? cluster.controllers;
                const unresolved = assignment?.unassigned ?? cluster.unassigned;
                const ownerSelections = clusterEditValues[cluster.id]?.owners ?? {};
                const verdicts = clusterEditValues[cluster.id]?.verdicts ?? {};
                const branchTargets = clusterEditValues[cluster.id]?.branchTargets ?? {};
                return (
                  <article className={`agent-cluster-review ${selected ? "selected" : ""}`}>
                    <header>
                      <label>
                        <input checked={selected} disabled={effectiveBusy} onChange={(event) => updateEquipmentCluster(cluster.id, { busName, networkId, selected: event.target.checked })} type="checkbox" />
                        <span><strong>{cluster.label}</strong><small>{cluster.devices.length} Teilnehmer · {controllerTree.length} Controller</small></span>
                      </label>
                      <p>{cluster.recommendation}</p>
                    </header>
                    <div className="agent-cluster-bus-grid">
                      <label>Bustechnik
                        <select aria-label={`${cluster.label}: Bustechnik`} disabled={effectiveBusy || !communicationSystemCounts.length} onChange={(event) => updateEquipmentCluster(cluster.id, { networkId: event.target.value, selected })} value={networkId}>
                          {communicationSystemCounts.length
                            ? communicationSystemCounts.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)
                            : <option value="">Noch kein Netz</option>}
                        </select>
                      </label>
                      <label>Busname
                        <input aria-label={`${cluster.label}: vorgeschlagener Busname`} disabled={effectiveBusy} onChange={(event) => updateEquipmentCluster(cluster.id, { busName: event.target.value, networkId, selected })} value={busName} />
                      </label>
                    </div>
                    {issues.length > 0 ? (
                      <ul className="agent-cluster-warnings" aria-label={`${cluster.label}: Validierung`}>
                        {issues.map(issue => <li key={issue.code}>
                          <strong>{issue.message}</strong><p>{issue.action}</p>
                          {issue.affected.length > 0 && <details><summary>Betroffene Teilnehmer und Werte anzeigen ({new Set(issue.affected.map(item => item.name)).size})</summary>
                            <ul>{issue.affected.map((item, index) => <li key={`${item.name}-${index}`}>
                              <button type="button" className="agent-warning-location" onClick={() => showParticipant(item.name)}>{item.name} ↗</button>
                              <span>{item.detail}</span>
                            </li>)}</ul>
                          </details>}
                        </li>)}
                      </ul>
                    ) : <p className="agent-cluster-valid">Controller-Zuordnung und Bustechnik sind für diesen Vorschlag konsistent.</p>}
                    <div className="agent-cluster-tree" role="tree" aria-label={`${cluster.label}: Controller-Struktur`}>
                      {controllerTree.length ? controllerTree.map((controller) => (
                        <details key={`${cluster.id}:${controller.name}`} open>
                          <summary id={participantId(controller.name)}><strong>{controller.name}</strong><span>Controller · {controller.interfaceType}</span>{warningFor(controller.name) && <small className="agent-participant-warning">⚠ {warningFor(controller.name)}</small>}</summary>
                          <div className="agent-assignment-review agent-assignment-review-group">
                            <span><strong>Gruppenzuordnung</strong><small>Controller mit allen Teilnehmern</small></span>
                            <div className="agent-assignment-segmented" role="group" aria-label={`${controller.name}: Gruppenzuordnung bewerten`}>
                              <button aria-pressed={!branchTargets[controller.name]} className={!branchTargets[controller.name] ? "active" : ""} disabled={effectiveBusy} onClick={() => updateEquipmentCluster(cluster.id, { branchTargets: { ...branchTargets, [controller.name]: "" } })} type="button">✓ Passt</button>
                              <button aria-pressed={Boolean(branchTargets[controller.name])} className={branchTargets[controller.name] ? "rejected" : ""} disabled={effectiveBusy} onClick={() => setClusterReviewDialog({ kind: "branch", clusterId: cluster.id, name: controller.name, target: branchTargets[controller.name] || "" })} type="button">↗ Neu zuordnen</button>
                            </div>
                          </div>
                          {!!controller.functions?.length && <section className="agent-controller-functions"><strong>Funktionen · {controller.functions.length}</strong><small>Editierbare Entwurfsvorgaben; Anzeigeziele unten einzeln aktivieren.</small><ul>{controller.functions.map(fn => <li key={fn.name}><span>{fn.name}<small>{fn.signals.join(" · ")}</small></span></li>)}</ul></section>}
                          <div>
                            <section><strong>Sensoren · {controller.sensors.length}</strong><ul>{controller.sensors.map((leaf) => <li key={leaf.name} id={participantId(leaf.name)} tabIndex={-1} data-warning={Boolean(warningFor(leaf.name)) || undefined} title={leaf.reason}><span>{leaf.name}<small>{leaf.interfaceType} · {Math.round(leaf.confidence * 100)} %</small>{warningFor(leaf.name) && <small className="agent-participant-warning">⚠ {warningFor(leaf.name)}</small>}</span><span className="agent-assignment-review"><button className={verdicts[leaf.name] !== false ? "active" : ""} disabled={effectiveBusy} onClick={() => updateEquipmentCluster(cluster.id, { verdicts: { ...verdicts, [leaf.name]: true } })} type="button">Trifft zu</button><button className={verdicts[leaf.name] === false ? "rejected" : ""} disabled={effectiveBusy} onClick={() => setClusterReviewDialog({ kind: "leaf", clusterId: cluster.id, name: leaf.name, target: ownerSelections[leaf.name] || controller.name })} type="button">Trifft nicht zu</button></span></li>)}</ul></section>
                            <section><strong>Aktoren · {controller.actuators.length}</strong><ul>{controller.actuators.map((leaf) => <li key={leaf.name} id={participantId(leaf.name)} tabIndex={-1} data-warning={Boolean(warningFor(leaf.name)) || undefined} title={leaf.reason}><span>{leaf.name}<small>{leaf.interfaceType} · {Math.round(leaf.confidence * 100)} %</small>{warningFor(leaf.name) && <small className="agent-participant-warning">⚠ {warningFor(leaf.name)}</small>}</span><span className="agent-assignment-review"><button className={verdicts[leaf.name] !== false ? "active" : ""} disabled={effectiveBusy} onClick={() => updateEquipmentCluster(cluster.id, { verdicts: { ...verdicts, [leaf.name]: true } })} type="button">Trifft zu</button><button className={verdicts[leaf.name] === false ? "rejected" : ""} disabled={effectiveBusy} onClick={() => setClusterReviewDialog({ kind: "leaf", clusterId: cluster.id, name: leaf.name, target: ownerSelections[leaf.name] || controller.name })} type="button">Trifft nicht zu</button></span></li>)}</ul></section>
                          </div>
                        </details>
                      )) : <p>Kein Controller in diesem Systemzweig erkannt.</p>}
                    </div>
                    {unresolved.length > 0 && (
                      <ClusterUnassignedReview
                        busy={effectiveBusy}
                        clusterId={cluster.id}
                        clusterLabel={cluster.label}
                        controllerOptions={ecuOwnerOptions}
                        key={cluster.id}
                        leaves={unresolved}
                        warningFor={warningFor}
                        onAssign={(batchOwners) => {
                          updateEquipmentCluster(cluster.id, { owners: { ...ownerSelections, ...batchOwners } });
                          persistEquipmentLearning(Object.entries(batchOwners).map(([endpointName, controllerName]) => ({
                            endpoint_name: endpointName,
                            controller_name: controllerName,
                            device_type: plannedEquipment.chains.find((chain) => chain.hardware_name === endpointName)?.device_type,
                            accepted: true,
                          })), "wizard-batch-review");
                        }}
                        onOpenLeaf={(name, target) => setClusterReviewDialog({ kind: "leaf", clusterId: cluster.id, name, target })}
                        ownerSelections={ownerSelections}
                      />
                    )}
                    {(assignment?.hmi_routes?.length ?? 0) > 0 && (
                      <section className="agent-cluster-hmi" aria-label={`${cluster.label}: HMI-Routing`}>
                        <strong>Nutzeranzeige über Routing</strong>
                        <p>Nur benötigte Funktionsausgänge einschalten. Aus bedeutet: keine zusätzliche Übertragung an dieses Anzeigeziel. Berechnungen in der Funktion und die Kommunikation mit anderen Empfängern bleiben erhalten.</p>
                        {assignment?.hmi_routes?.map((route) => (
                          <div key={`${route.source}:${route.target}`}>
                            <span>{route.path.join(" → ")}</span>
                            {[...route.signals, ...(route.excluded_signals ?? [])].sort((a, b) => a.localeCompare(b, "de")).map(signal => <label className="agent-hmi-switch" key={signal}>
                              <input type="checkbox" role="switch" aria-label={`${signal} → ${route.target}`} checked={route.signals.includes(signal)} disabled={effectiveBusy} onChange={event => updateEquipmentCluster(cluster.id, { hmiSignals: { ...clusterEditValues[cluster.id]?.hmiSignals, [hmiSignalKey(route, signal)]: event.target.checked } })} />
                              <span className="agent-hmi-switch-track" aria-hidden="true" />
                              <span>{signal}</span><small>{route.signals.includes(signal) ? "Ein · anzeigen" : "Aus"}</small>
                            </label>)}
                          </div>
                        ))}
                      </section>
                    )}
                    {clusterReviewDialog?.clusterId === cluster.id && (() => {
                      const meaning = equipmentTermMeaning(clusterReviewDialog.name);
                      return <div className="agent-cluster-correction-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) setClusterReviewDialog(null); }}>
                        <section aria-label="Zuordnung korrigieren" aria-modal="true" className="agent-cluster-correction-dialog" role="dialog">
                          <header><div><strong>Zuordnung korrigieren</strong><small>{clusterReviewDialog.name}</small></div><button aria-label="Dialog schließen" onClick={() => setClusterReviewDialog(null)} type="button">×</button></header>
                          <dl><div><dt>English</dt><dd>{meaning.english}</dd></div><div><dt>Deutsch</dt><dd>{meaning.german}</dd></div><div><dt>Fachgebiet</dt><dd>{meaning.system}</dd></div></dl>
                          <label>{clusterReviewDialog.kind === "leaf" ? "Neuen Controller auswählen" : "Neue Systemgruppe auswählen"}
                            <select autoFocus onChange={(event) => setClusterReviewDialog((current) => current ? { ...current, target: event.target.value } : current)} value={clusterReviewDialog.target}>
                              <option value="">Bitte auswählen …</option>
                              {clusterReviewDialog.kind === "leaf"
                                ? ecuOwnerOptions.filter((ecu) => ecu.hardware_name !== clusterReviewDialog.name).map((ecu) => <option key={ecu.hardware_name} value={ecu.hardware_name}>{ecu.hardware_name}</option>)
                                : equipmentClusters.filter((candidate) => candidate.id !== cluster.id).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.label}</option>)}
                            </select>
                          </label>
                          <footer><button onClick={() => setClusterReviewDialog(null)} type="button">Abbrechen</button><button disabled={!clusterReviewDialog.target} onClick={() => {
                            if (clusterReviewDialog.kind === "leaf") {
                              const previousOwner = controllerTree.find((candidate) => [...candidate.sensors, ...candidate.actuators].some((leaf) => leaf.name === clusterReviewDialog.name))?.name;
                              updateEquipmentCluster(cluster.id, { owners: { ...ownerSelections, [clusterReviewDialog.name]: clusterReviewDialog.target }, verdicts: { ...verdicts, [clusterReviewDialog.name]: false } });
                              persistEquipmentLearning([
                                ...(previousOwner && previousOwner !== clusterReviewDialog.target ? [{ endpoint_name: clusterReviewDialog.name, controller_name: previousOwner, accepted: false }] : []),
                                { endpoint_name: clusterReviewDialog.name, controller_name: clusterReviewDialog.target, accepted: true },
                              ], "wizard-manual-correction");
                            }
                            else updateEquipmentCluster(cluster.id, { branchTargets: { ...branchTargets, [clusterReviewDialog.name]: clusterReviewDialog.target } });
                            setClusterReviewDialog(null);
                          }} type="button">Neue Zuordnung übernehmen</button></footer>
                        </section>
                      </div>;
                    })()}
                  </article>
                );
              })()}
            </section>
          )}
          <div className="agent-equipment-list">
            {EQUIPMENT_CATEGORIES.map(({ key, label, type }) => (
              <details key={key}><summary>{label} · {identifiedCounts[key]} erkannt / {equipmentCounts[key]} vorgegeben</summary>
                <ul>{plannedEquipment.chains.filter((chain) => type === "Controller" ? isEngineeringControllerDevice(chain.device_type) : chain.device_type === type)
                  .sort((a, b) => a.hardware_name.localeCompare(b.hardware_name, "de"))
                  .map((chain, index) => <li key={`${chain.device_type}:${chain.hardware_name}:${index}`}>{chain.hardware_name}</li>)}</ul>
              </details>
            ))}
          </div>
        </fieldset>
      )}
      {phase === 'questionnaire' && activeStepId === 'status' && !submittedContext && (
        <section className="agent-wizard-status" aria-label="Auftrag vor dem Start prüfen">
          <h3>Projektentwurf prüfen</h3>
          <p>Es wurde noch kein Auftrag gestartet. Prüfe die Beschreibung und ergänze offene Angaben.</p>
          <h4>{projectName || 'Projektname fehlt'}</h4>
          <p style={{ whiteSpace: 'pre-wrap' }}>{taskText || 'Projektbeschreibung fehlt'}</p>
          {startBlockers.length ? <ul>{startBlockers.map((blocker) => <li key={blocker.text}>
            <span>{blocker.text} </span><button type="button" className="button secondary tiny"
              onClick={() => setStep(questionnaireSteps.findIndex((item) => item.id === blocker.step))}>Angabe ergänzen</button>
          </li>)}</ul> : <p>Die Pflichtangaben sind vollständig. Mit „Auftrag starten“ übergibst du den Entwurf an den Agenten.</p>}
        </section>
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
              <div className="agent-equipment-list" aria-label={hardwareItems.length > 0 ? "Angelegte Geräte" : "Vorgeschlagene Geräte"}>
                {EQUIPMENT_CATEGORIES.map(({ key, label, type }) => (
                  <details key={key}><summary>{label} · {hardwareDetails[key]}</summary>
                    <ul>{displayedHardwareItems.filter((item) => type === "Controller" ? isEngineeringControllerDevice(item.device_type) : item.device_type === type)
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
              {submittedContext?.engineering_draft_ref ? <>
                <ProjectDraftEditor projectId={projectId} draftId={submittedContext.engineering_draft_ref.draft_id} onStateChange={setLinkedDraftStatus} />
                <button type="button" className="button primary" disabled={supplementBusy || agentPending || !linkedDraftStatus?.ready
                  || linkedDraftStatus.revision === submittedContext.engineering_draft_ref.revision}
                  onClick={() => void adoptLinkedDraftRevision()}>Gespeicherten Entwurf im Auftrag übernehmen</button>
              </> : <>
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
              {submittedContext?.structured_draft_ref && <details><summary>Gemeinsamen Projektentwurf bearbeiten</summary>
                <ProjectDraftEditor projectId={projectId} draftId={submittedContext.structured_draft_ref.draft_id} onStateChange={setLinkedDraftStatus} />
                <button type="button" className="button primary" disabled={supplementBusy || agentPending || !linkedDraftStatus?.ready
                  || linkedDraftStatus.revision === submittedContext.structured_draft_ref.revision}
                  onClick={() => void adoptLinkedDraftRevision()}>Gespeicherten Entwurf im Auftrag übernehmen</button>
              </details>}
              </>}
            </section>
          )}

          <dl className="agent-wizard-context">
            <div><dt>Aktueller Schritt</dt><dd>{currentStatusStep}</dd></div>
            <div><dt>Projektname</dt><dd>{submittedContext.project_name || projectId}</dd></div>
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
              <EngineeringAgentEventCard key={visibleQuestion.id} event={{ type: 'QUESTION', question: visibleQuestion }} projectId={projectId}
                onAnswer={agentPending ? undefined : answer => void answerInlineQuestion(answer)} wizardReview />
            ) : (
              <div>
                <span className="eyebrow">Rückfragen</span>
                <strong>{modelReviewPending ? "Modellfreigabe ausstehend" : routingReviewPending ? "Routing-Review ausstehend" : workflowReviewPending ? "Freigabe ausstehend" : runPaused ? blockedTitle : "Keine Rückfrage offen"}</strong>
                <small>{modelReviewPending ? runMessage : routingReviewPending
                  ? `${displayedRoutingTotal} Routing-Einträge vorbereitet · ${proposedRoutingCount ? 0 : routingReview.awaitingValidation} noch zu validieren · ${displayedRoutingValid} valide und freigabebereit.`
                  : workflowReviewPending
                    ? runMessage
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
                {runPaused && /Anschlusstechnik.*nicht eindeutig unterstützt/.test(runMessage || '') ? (
                  <button className="button primary tiny" onClick={() => setSupplementOpen(true)} type="button">
                    Anschlüsse ergänzen
                  </button>
                ) : canRetryPopupRun && (
                  <button className="button primary tiny" onClick={() => void retryPopupRun(false)} type="button">
                    Auftrag fortsetzen
                  </button>
                )}
              </div>
            )}
          </section>

          {(execution?.state === "REVIEW_REQUIRED" || execution?.state === "BLOCKED") && <WizardModelReview key={`${runId}:${execution.step}`} onProposalLoaded={setReviewProposal} projectId={projectId} runId={runId} />}

          <div
            className="agent-wizard-runtime"
            aria-label={performance ? (performance.host_metrics_available ? "Aktuelle Rechnerauslastung" : "Aktuelle Containerauslastung") : "Laufzeitauslastung wird geladen"}
            title={performance ? `${performance.host_metrics_available ? "Windows-Rechner" : "Simulator-Container"} · Messung ${new Date(performance.sampled_at).toLocaleTimeString("de-DE")}` : undefined}
          >
            <span><small>CPU · {performance ? (performance.host_metrics_available ? "PC" : "Container") : "…"}</small><strong>{performance ? `${performance.cpu_percent} %` : "..."}</strong></span>
            <span><small>RAM · {performance ? (performance.host_metrics_available ? "PC" : "Container") : "…"}</small><strong>{performance ? `${performance.memory_percent} %` : "..."}</strong></span>
            <span><small>GPU · PC</small><strong>{performance?.gpu ? `${performance.gpu.utilization_percent} %` : "nicht verfügbar"}</strong></span>
            <span><small>VRAM · PC</small><strong>{performance?.gpu ? `${performance.gpu.memory_used_mb}/${performance.gpu.memory_total_mb} MB` : "nicht verfügbar"}</strong></span>
            <span><small>Analyse</small><strong>{activeAnalysis}</strong></span>
            <span><small>LLM</small><strong>{activeModel}</strong></span>
          </div>

          {displayedStatusError && <p className="notice error" role="alert">{displayedStatusError}</p>}
          <footer className="agent-wizard-status-footer">
            <small className="agent-wizard-log-status">TXT-Protokolle aktiv: Workflow · Rückfragen · Performance · Fehler</small>
            <div className="agent-wizard-status-actions">
              <button className="button secondary" disabled={cancelBusy} onClick={() => void cancelWizardRun()} type="button">
                {cancelBusy ? "Breche ab..." : "Abbrechen"}
              </button>
              <button className="button primary" disabled={agentPending || routingReviewBusy || supplementBusy || workflowReviewPending || routingReviewPending || modelReviewPending || runPaused || cancelBusy} onClick={() => void finishWizard()} type="button">
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
            : activeStepId === "project"
              ? projectReady ? "Projektname bereit" : "Projektname fehlt"
            : activeStepId === "equipment"
              ? equipmentReady && equipmentIdentityReady && !unresolvedConnections.length && equipmentOwnershipReady && equipmentClusterValidationReady && communicationSystemReady ? "Sollzahlen, Busse und Controller-Zuordnung bereit" : "Anzahlen, erkannte Geräte, Anschlüsse, Busse und Controller-Zuordnung prüfen"
            : activeStepId === "architecture"
              ? architectureReady ? "Architektur gewählt" : "Auswahl erforderlich"
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
  const ids = domain.technologies
    .filter((technology) => !["PLANNED", "NOT_SUPPORTED"].includes(technology.implementation_status ?? "IMPLEMENTED"))
    .map((technology) => technology.id);
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
  participantLimits?: Record<string, number>;
  clusterAssignments: EquipmentClusterAssignment[];
  equipmentCounts: EngineeringHardwareCounts;
}) {
  const participantConnections = args.equipmentCounts.ecus + args.equipmentCounts.sensors + args.equipmentCounts.actuators;
  const selectedClusterDevices = args.clusterAssignments
    .filter((assignment) => assignment.selected)
    .reduce((sum, assignment) => sum + Math.max(0, Number(assignment.devices) || 0), 0);
  if (args.architectureId === "hybrid_ai") return Math.max(selectedClusterDevices, participantConnections);
  if (args.architectureId === "gateway_ecu_segments") {
    const ecuSegments = args.clusterAssignments.filter(cluster => cluster.selected).reduce((sum, cluster) => sum + Math.ceil((cluster.tree?.length ?? cluster.counts.ecus ?? 0) / busBranchCapacity(args.participantLimits ?? DEFAULT_BUS_PARTICIPANT_LIMITS, cluster.network_id)), 0);
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
    ecus: "Controller",
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
  if (lower.includes("vorschlag") || lower.includes("erstelle") || lower.includes("schlage")) return "Engineering-Inhalte mit Auditspur erzeugen und zur menschlichen Freigabe vorlegen.";
  return "Nutzerfrage im aktiven Projektkontext beantworten und dafür benötigte Engineering-Daten lesen.";
}

function inferAgentAssumption(text: string, goal: string) {
  const lower = text.toLowerCase();
  if (goal.includes("Proposal") || lower.includes("neu") || lower.includes("erstelle") || lower.includes("schlage")) {
    return "Neue Engineering-Inhalte werden als Vorschlag geprüft und nach deiner Freigabe ins Modell übernommen.";
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

function WizardModelReview({ onProposalLoaded, projectId, runId }: { onProposalLoaded?: (proposal: EngineeringProposal) => void; projectId: string; runId: string }) {
  const [proposal, setProposal] = useState<EngineeringProposal | null>(null);
  const [error, setError] = useState("");
  const revisionRef = useRef('');
  useEffect(() => {
    const controller = new AbortController();
    const options = { headers: { "X-Project-ID": projectId }, signal: controller.signal, cache: "no-store" as const };
    let refreshing = false;
    const refresh = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        const conversation = await readConversation(projectId, controller.signal);
        if (!wizardConversationMatches(conversation.data, runId)) throw new Error('Der gespeicherte Vorschlag gehört zu einem anderen Auftrag.');
        if (!conversation.data.active_proposal) { setProposal(null); setError(''); return; }
        const result = await fetch(`/api/engineering/agent/proposals/${encodeURIComponent(conversation.data.active_proposal)}`, options);
        const value = await result.json();
        if (!result.ok || !value.success) throw new Error('Vorschlag konnte nicht geladen werden.');
        if (controller.signal.aborted) return;
        const signature = JSON.stringify([value.data.proposal_id, value.data.revision, value.data.status, value.data.validation_result]);
        if (revisionRef.current !== signature) {
          revisionRef.current = signature;
          setProposal(value.data);
          onProposalLoaded?.(value.data);
        }
        setError('');
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Vorschlag konnte nicht geladen werden.');
      } finally { refreshing = false; }
    };
    void refresh();
    const timer = window.setInterval(() => { if (document.visibilityState === 'visible') void refresh(); }, 5000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [onProposalLoaded, projectId, runId]);
  if (error) return <p role="alert">{error}</p>;
  return proposal ? <EngineeringAgentEventCard key={`${proposal.proposal_id}:${proposal.revision}`} event={{ type: "APPROVAL", proposal }} projectId={projectId} wizardReview /> : null;
}

function canonicalWizardDomain(value: string) {
  const compact = value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  if (compact === "robotics") return "robotics_ros";
  if (compact === "building") return "building_automation";
  return compact;
}

function MessagePart({
  hideText = false,
  part,
  projectId,
  richText = false,
  onAnswer,
  onRetry,
}: {
  hideText?: boolean;
  part: EngineeringAgentUIMessage["parts"][number];
  projectId: string;
  richText?: boolean;
  onAnswer?: (answer: AgentInput) => void;
  onRetry?: () => void;
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
  if (part.type === "data-engineering") {
    return <EngineeringAgentEventCard event={part.data} projectId={projectId} onAnswer={onAnswer} onRetry={onRetry} />;
  }
  if (part.type === 'data-attachment') {
    return <details className="eng-agent-attachment-source"><summary>Dokument: {part.data.name}{part.data.truncated ? ' · Auszug' : ''}</summary><pre>{part.data.text}</pre></details>;
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
