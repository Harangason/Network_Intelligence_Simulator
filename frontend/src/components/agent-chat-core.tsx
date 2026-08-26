"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import type { EngineeringAgentUIMessage } from "@/lib/agent/engineering-agent";
import { getCatalog } from "@/lib/api";
import type { TechnologyDomain } from "@/lib/types";
import { readActiveProjectId } from "@/lib/user-settings";
import { AgentToolResult } from "./agent-tool-result";

export function AgentChatCore({ compact = false }: { compact?: boolean }) {
  const transport = useMemo(
    () => new DefaultChatTransport({
      api: "/api/agent/chat",
      headers: () => ({ "X-Project-ID": readActiveProjectId() }),
    }),
    [],
  );
  const { messages, sendMessage, status, error, regenerate } = useChat<EngineeringAgentUIMessage>({
    transport,
  });
  const [input, setInput] = useState("");
  const [handledQuestionnaires, setHandledQuestionnaires] = useState<string[]>([]);
  const [forcedQuestionnaire, setForcedQuestionnaire] = useState<GuidedQuestionnaire | null>(null);
  const [projectBrief, setProjectBrief] = useState("");
  const threadRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim() || status !== "ready") return;
    const text = projectBrief
      ? `${projectBrief}\n\nKonkrete Aufgabe des Nutzers, per Senden bestaetigt:\n${input.trim()}\n\nStarte jetzt die Analyse und arbeite selbststaendig bis zum genannten Ziel. Warte nicht auf weitere Kommandos, ausser Human Review oder eine echte fachliche Entscheidung blockiert den naechsten Schritt.`
      : input.trim();
    sendMessage({ text });
    if (projectBrief) {
      setProjectBrief("");
      window.sessionStorage.removeItem("networkis:agent-project-brief");
    }
    setInput("");
  }

  const busy = status === "submitted" || status === "streaming";
  const activityEntries = useMemo(() => buildAgentActivity(messages, busy, error?.message), [messages, busy, error]);
  const confirmationRequest = useMemo(() => findPendingConfirmation(messages), [messages]);
  const guidedQuestionnaire = useMemo(() => {
    if (status !== "ready") return null;
    if (forcedQuestionnaire && !handledQuestionnaires.includes(forcedQuestionnaire.key)) {
      return forcedQuestionnaire;
    }
    const questionnaire = findGuidedQuestionnaire(messages);
    if (!questionnaire || handledQuestionnaires.includes(questionnaire.key)) return null;
    return questionnaire;
  }, [forcedQuestionnaire, messages, handledQuestionnaires, status]);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [messages, busy]);

  useEffect(() => {
    setHandledQuestionnaires(readHandledQuestionnaires());
    setForcedQuestionnaire(readForcedQuestionnaire());
    setProjectBrief(readProjectBrief());
  }, []);

  useEffect(() => {
    const ask = (event: Event) => {
      const question = String((event as CustomEvent<string>).detail ?? "").trim();
      if (question && status === "ready") void sendMessage({ text: question });
    };
    window.addEventListener("engineering-agent:ask", ask);
    return () => window.removeEventListener("engineering-agent:ask", ask);
  }, [sendMessage, status]);

  useEffect(() => {
    function resetQuestionnaireState() {
      setHandledQuestionnaires([]);
      window.sessionStorage.removeItem("networkis:handled-agent-questionnaires");
    }

    function forceStartQuestionnaire(projectId: string) {
      const next: GuidedQuestionnaire = {
        key: `full:new-project:${projectId}`,
        mode: "full",
        title: "Technische Vorgaben",
      };
      setForcedQuestionnaire(next);
      window.sessionStorage.setItem("networkis:forced-agent-questionnaire", JSON.stringify(next));
    }

    function openNewProjectQuestionnaire(projectId: string) {
      resetQuestionnaireState();
      forceStartQuestionnaire(projectId);
      return true;
    }

    const handleNewProject = (event: Event) => {
      const detail = (event as CustomEvent<{ projectId?: string }>).detail;
      const projectId = detail?.projectId ?? readActiveProjectId();
      if (openNewProjectQuestionnaire(projectId)) {
        window.sessionStorage.removeItem("networkis:pending-agent-new-project");
      }
    };

    window.addEventListener("engineering-agent:new-project", handleNewProject);
    const pending = window.sessionStorage.getItem("networkis:pending-agent-new-project");
    if (pending) {
      let projectId = readActiveProjectId();
      try {
        const detail = JSON.parse(pending) as { projectId?: string };
        projectId = detail.projectId ?? projectId;
      } catch {
        window.sessionStorage.removeItem("networkis:pending-agent-new-project");
      }
      if (openNewProjectQuestionnaire(projectId)) {
        window.sessionStorage.removeItem("networkis:pending-agent-new-project");
      }
    }
    return () => window.removeEventListener("engineering-agent:new-project", handleNewProject);
  }, []);

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

  function allowRequestedAction() {
    if (!confirmationRequest || status !== "ready") return;
    void sendMessage({ text: "Bestätigt. Bitte fahre mit dem vorgeschlagenen nächsten Schritt fort." });
  }

  function handleGuidedQuestionnaireSubmit(key: string, text: string, startAgent = false) {
    if (status !== "ready") return;
    const next = Array.from(new Set([...handledQuestionnaires, key]));
    setHandledQuestionnaires(next);
    window.sessionStorage.setItem("networkis:handled-agent-questionnaires", JSON.stringify(next));
    if (forcedQuestionnaire?.key === key) {
      setForcedQuestionnaire(null);
      window.sessionStorage.removeItem("networkis:forced-agent-questionnaire");
    }
    if (startAgent) {
      sendMessage({ text });
      setProjectBrief("");
      window.sessionStorage.removeItem("networkis:agent-project-brief");
      return;
    }
    setProjectBrief(text);
    window.sessionStorage.setItem("networkis:agent-project-brief", text);
  }

  return (
    <>
      <div className="eng-agent-thread" aria-live="polite" ref={threadRef}>
        {messages.length === 0 && (
          <div className="empty-result" style={{ minHeight: compact ? 90 : 140 }}>
            <span className="empty-icon">◇</span>
            <strong>Noch keine Nachricht</strong>
            <p>Frage nach Hardware, Interfaces, Signalen oder bitte um Vorschläge.</p>
          </div>
        )}

        {messages.map((message) => (
          <div className={`eng-agent-message ${message.role}`} key={message.id}>
            <span aria-hidden="true" className="eng-agent-avatar">{message.role === "user" ? "DU" : "AI"}</span>
            <div className="eng-agent-message-content">
              <span className="eng-agent-role">{message.role === "user" ? "Du" : "Engineering-Agent"}</span>
              <div className="eng-agent-bubble">
                {message.parts.map((part, index) => (
                  <MessagePart key={`${message.id}-${index}`} part={part} />
                ))}
              </div>
            </div>
          </div>
        ))}

        {busy && (
          <div className="eng-agent-message assistant">
            <span aria-hidden="true" className="eng-agent-avatar">AI</span>
            <div className="eng-agent-message-content">
              <span className="eng-agent-role">Engineering-Agent</span>
              <div className="eng-agent-bubble">
                <span className="spinner" /> denkt nach …
              </div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="notice error">
          Der Agent konnte nicht antworten.{" "}
          <button className="button secondary tiny" onClick={() => regenerate()} type="button">
            Erneut versuchen
          </button>
        </div>
      )}

      {activityEntries.length > 0 && <AgentActivityLog entries={activityEntries} />}

      {guidedQuestionnaire && (
        <AgentGuidedQuestionnaire
          busy={busy}
          mode={guidedQuestionnaire.mode}
          onSubmit={(text) => handleGuidedQuestionnaireSubmit(guidedQuestionnaire.key, text, true)}
          title={guidedQuestionnaire.title}
        />
      )}

      {confirmationRequest && !guidedQuestionnaire && (
        <div className="eng-agent-approval">
          <div>
            <strong>Bestätigung erforderlich</strong>
            <span>Der Agent wartet auf deine Freigabe für den vorgeschlagenen nächsten Schritt.</span>
          </div>
          <button className="button primary" disabled={busy} onClick={allowRequestedAction} type="button">
            Allow
          </button>
        </div>
      )}

      {projectBrief && !guidedQuestionnaire && (
        <div className="notice info">
          Technische Vorgaben übernommen. Bitte gib jetzt die konkrete Aufgabe ein und bestätige sie mit Senden.
        </div>
      )}

      <form className="eng-agent-form" onSubmit={submit}>
        <textarea
          aria-label="Nachricht an den Engineering-Assistenten"
          disabled={busy}
          onKeyDown={handleInputKeyDown}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Frage den Engineering-Assistenten …"
          ref={inputRef}
          rows={1}
          value={input}
        />
        <button className="button primary" disabled={busy || !input.trim()} type="submit">
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

type GuidedQuestionnaire = {
  key: string;
  messageId?: string;
  mode: "full" | "can";
  title: string;
};

type TaskAttachment = {
  name: string;
  size: number;
  kind: string;
  content?: string;
};

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

function AgentGuidedQuestionnaire({
  busy,
  mode,
  onSubmit,
  title,
}: {
  busy: boolean;
  mode: "full" | "can";
  onSubmit: (text: string) => void;
  title: string;
}) {
  const [domains, setDomains] = useState<TechnologyDomain[]>(STATIC_INDUSTRY_DOMAINS);
  const [step, setStep] = useState(0);
  const [selectedIndustry, setSelectedIndustry] = useState("automotive");
  const [selectedTechnologies, setSelectedTechnologies] = useState<string[]>([]);
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
    if (mode === "can") {
      const canIds = technologyChoices.map((technology) => technology.id);
      const preferred = ["can_fd", "can", "can_xl"].filter((id) => canIds.includes(id));
      setSelectedTechnologies(preferred.length ? preferred : canIds.slice(0, 3));
      return;
    }
    setSelectedTechnologies(defaultTechnologyIds(selectedDomain));
  }, [mode, selectedDomain, technologyChoices]);

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

  const steps = [
    ...(mode === "full" ? [{ id: "industry", label: "Industrie" }] : []),
    { id: "technologies", label: "Technologien" },
    ...(mode === "can" ? [{ id: "parameters", label: "Parameter" }] : []),
    { id: "scope", label: "Umfang" },
    { id: "process", label: "Arbeitsweise" },
    { id: "task", label: "Aufgabe" },
  ];
  const atLastStep = step === steps.length - 1;
  const taskReady = taskText.trim().length > 0 || taskFiles.length > 0;

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

  async function handleTaskFiles(files: FileList | null) {
    const selected = Array.from(files ?? []).slice(0, 3);
    const attachments = await Promise.all(selected.map(readTaskAttachment));
    setTaskFiles(attachments);
  }

  async function submitQuestionnaire() {
    if (!taskReady) return;
    const selectedTechnologyValues = technologyGroup.options
      .filter((option) => selectedTechnologies.includes(option.id))
      .map((option) => option.value);
    const selectedScopeValues = SCOPE_GROUP.options.filter((option) => scope.includes(option.id)).map((option) => option.value);
    const selectedProcessValues = PROCESS_GROUP.options.filter((option) => process.includes(option.id)).map((option) => option.value);
    const parameterLine = parameterMode === "defaults"
      ? "- Parameter: Technologie-Defaults verwenden"
      : `- Parameter: Nutzerdefiniert: Bitrate=${customParameters.bitrate || "Default"}; Payload=${customParameters.payload || "Default"}; Cycle=${customParameters.cycleMs || "Default"} ms; SamplePoint=${customParameters.samplePoint || "Default"} %`;
    const note = notes.trim() ? `\n- Weitere Hinweise: ${notes.trim()}` : "";
    const attachments = taskFiles.length
      ? `\n\nAufgaben-Anlagen:\n${taskFiles.map((file) => formatTaskAttachment(file)).join("\n")}`
      : "";
    const concreteTask = `${taskText.trim() || "Aufgabe wurde als Datei uebergeben."}${attachments}`;
    onSubmit(
      "Strukturierte Vorgaben fuer den Engineering-Agenten:\n" +
        `- Abfrage erfolgt: true\n` +
        `- Abfrage-Modus: ${mode === "can" ? "reduziert fuer CAN/CAN-FD" : "vollstaendig"}\n` +
        `- Industrie: ${mode === "can" ? "aus Projektkontext ableiten" : selectedDomain?.label ?? selectedIndustry}\n` +
        `- Netzwerktechnologien: ${selectedTechnologyValues.length ? selectedTechnologyValues.join("; ") : "nicht vorgegeben, passende Technologien aus der gewaehlten Industrie verwenden"}\n` +
        `${parameterLine}\n` +
        `- Workflowumfang: ${selectedScopeValues.length ? selectedScopeValues.join("; ") : "nicht vorgegeben, Ziel aus Nutzeranfrage ableiten"}\n` +
        `- Arbeitsweise: ${selectedProcessValues.length ? selectedProcessValues.join("; ") : "nicht vorgegeben, vorsichtig mit Review-Gate arbeiten"}${note}\n` +
        "\nKonkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:\n" +
        `${concreteTask}\n\n` +
        "Starte jetzt die Analyse und arbeite selbststaendig bis zum genannten Zielzustand. Nutze plausible Defaults, wenn Details fehlen, und frage nur bei echten fachlichen Entscheidungen oder Human Review erneut.",
    );
  }

  function handlePrimary() {
    if (atLastStep) {
      void submitQuestionnaire();
      return;
    }
    setStep((current) => Math.min(current + 1, steps.length - 1));
  }

  function selectedFor(group: ChoiceGroup) {
    if (group.id === "industry") return [selectedIndustry];
    if (group.id === "technologies") return selectedTechnologies;
    if (group.id === "scope") return scope;
    if (group.id === "process") return process;
    return [];
  }

  function activeGroupForStep() {
    const id = steps[step].id;
    if (id === "industry") return industryGroup;
    if (id === "technologies") return technologyGroup;
    if (id === "scope") return SCOPE_GROUP;
    if (id === "process") return PROCESS_GROUP;
    return null;
  }

  const activeGroup = activeGroupForStep();
  const activeStepId = steps[step].id;

  return (
    <section className="eng-agent-questionnaire" aria-label="Geführte Agent-Rückfrage">
      <div className="eng-agent-questionnaire-head">
        <div>
          <strong>{title}</strong>
          <span>{steps[step].label}: Schritt {step + 1} von {steps.length}</span>
        </div>
        <button className="button primary tiny" disabled={busy || (atLastStep && !taskReady)} onClick={handlePrimary} type="button">
          {atLastStep ? "Übernehmen" : "Weiter"}
        </button>
      </div>
      <div className="agent-questionnaire-steps" aria-label="Rückfrage-Schritte">
        {steps.map((item, index) => (
          <button
            className={index === step ? "active" : ""}
            disabled={busy}
            key={item.id}
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
              accept=".txt,.md,.csv,.json,.pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/*"
              disabled={busy}
              multiple
              onChange={(event) => void handleTaskFiles(event.target.files)}
              type="file"
            />
            <span>
              <strong>Text, Word oder PDF hinzufügen</strong>
              <small>Textdateien werden direkt gelesen. PDF/DOCX werden als Anlage referenziert.</small>
            </span>
          </label>
          {taskFiles.length > 0 && (
            <ul className="agent-file-list">
              {taskFiles.map((file) => (
                <li key={`${file.name}-${file.size}`}>
                  <strong>{file.name}</strong>
                  <span>{file.kind} · {formatFileSize(file.size)}</span>
                </li>
              ))}
            </ul>
          )}
        </fieldset>
      )}
      <div className="agent-questionnaire-nav">
        <button className="button secondary tiny" disabled={busy || step === 0} onClick={() => setStep((current) => Math.max(current - 1, 0))} type="button">
          Zurück
        </button>
        <span>{activeStepId === "task" ? taskReady ? "Aufgabe bereit" : "Aufgabe fehlt" : activeGroup ? selectedFor(activeGroup).length : parameterMode === "defaults" ? "Defaults" : "Eigene Werte"} ausgewählt</span>
      </div>
    </section>
  );
}

function toggleSelection(values: string[], optionId: string) {
  return values.includes(optionId) ? values.filter((id) => id !== optionId) : [...values, optionId];
}

async function readTaskAttachment(file: File): Promise<TaskAttachment> {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const canReadAsText = file.type.startsWith("text/") || ["txt", "md", "csv", "json"].includes(extension);
  if (!canReadAsText) {
    return { name: file.name, size: file.size, kind: file.type || extension.toUpperCase() || "Datei" };
  }
  try {
    const content = await file.text();
    return {
      name: file.name,
      size: file.size,
      kind: file.type || "Text",
      content: content.slice(0, 12000),
    };
  } catch {
    return { name: file.name, size: file.size, kind: file.type || "Text" };
  }
}

function formatTaskAttachment(file: TaskAttachment) {
  const base = `- ${file.name} (${file.kind}, ${formatFileSize(file.size)})`;
  if (!file.content) return `${base}: Inhalt nicht direkt ausgelesen; Datei als Aufgabenreferenz beruecksichtigen.`;
  return `${base}:\n${file.content}`;
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

function findPendingConfirmation(messages: EngineeringAgentUIMessage[]) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === "user") return null;
    if (message.role !== "assistant") continue;
    const text = textFromParts(message.parts).toLowerCase();
    if (text.includes("bitte bestätigen") || text.includes("soll ich") || text.includes("möchtest du")) {
      return { messageId: message.id };
    }
  }
  return null;
}

function readForcedQuestionnaire(): GuidedQuestionnaire | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem("networkis:forced-agent-questionnaire") ?? "null") as Partial<GuidedQuestionnaire> | null;
    if (!parsed || !parsed.key || (parsed.mode !== "full" && parsed.mode !== "can") || !parsed.title) return null;
    return {
      key: parsed.key,
      mode: parsed.mode,
      title: parsed.title,
    };
  } catch {
    window.sessionStorage.removeItem("networkis:forced-agent-questionnaire");
    return null;
  }
}

function readHandledQuestionnaires() {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem("networkis:handled-agent-questionnaires") ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    window.sessionStorage.removeItem("networkis:handled-agent-questionnaires");
    return [];
  }
}

function readProjectBrief() {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem("networkis:agent-project-brief") ?? "";
}

function findGuidedQuestionnaire(messages: EngineeringAgentUIMessage[]) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === "user") return null;
    if (message.role !== "assistant") continue;
    const text = textFromParts(message.parts).toLowerCase();
    if (text.includes("ich fahre jetzt") || text.includes("ich beginne jetzt") || text.includes("sonst werden")) {
      return null;
    }
    const asksForChoices =
      /hast du .*?\?/.test(text) ||
      /welche .*?\?/.test(text) ||
      /soll ich .*?\?/.test(text) ||
      text.includes("bitte wähle") ||
      text.includes("bitte waehle") ||
      text.includes("bitte auswählen") ||
      text.includes("bitte auswaehlen");
    const engineeringTopic =
      text.includes("sensor") ||
      text.includes("ecu") ||
      text.includes("gateway") ||
      text.includes("can") ||
      text.includes("ethernet") ||
      text.includes("schnittstelle") ||
      text.includes("bus");
    const choiceTopic =
      text.includes("spezielle wünsche") ||
      text.includes("netzwerktechnologien") ||
      text.includes("industrie") ||
      text.includes("plausible defaults") ||
      text.includes("technologien");
    if (asksForChoices && engineeringTopic && choiceTopic) {
      const previousUserText = textFromParts(findPreviousUserMessage(messages, index)?.parts ?? []).toLowerCase();
      const isNewProjectStart = previousUserText.includes("neues projekt gestartet");
      const asksForIndustry =
        text.includes("industrie") ||
        text.includes("zielbranche") ||
        text.includes("branche") ||
        text.includes("domain") ||
        text.includes("bereich");
      const asksForModelBasics =
        text.includes("sensor") &&
        text.includes("ecu") &&
        (text.includes("gateway") || text.includes("topologie") || text.includes("grundobjekte"));
      const isCanFollowUp =
        !isNewProjectStart &&
        !asksForIndustry &&
        !asksForModelBasics &&
        (/\bcan[\s-]?(fd|xl)?\b/.test(text) || text.includes("can-fd"));
      const mode = isCanFollowUp ? "can" : "full";
      return {
        key: isNewProjectStart ? `full:new-project:${stableQuestionKey(previousUserText)}` : `${mode}:${stableQuestionKey(text)}`,
        messageId: message.id,
        mode,
        title: mode === "can" ? "CAN-Vorgaben" : "Technische Vorgaben",
      } as const;
    }
  }
  return null;
}

function findPreviousUserMessage(messages: EngineeringAgentUIMessage[], beforeIndex: number) {
  for (let index = beforeIndex - 1; index >= 0; index -= 1) {
    if (messages[index].role === "user") return messages[index];
  }
  return null;
}

function stableQuestionKey(text: string) {
  return text.replace(/\s+/g, " ").trim().slice(0, 220);
}

function textFromParts(parts: EngineeringAgentUIMessage["parts"]) {
  return parts.filter((part) => part.type === "text").map((part) => part.text).join(" ");
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
    proposeEngineeringObject: "Objektvorschlag erzeugt",
    proposeEngineeringRelation: "Relationsvorschlag erzeugt",
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
  if (lower.includes("vorschlag") || lower.includes("erstelle") || lower.includes("schlage")) return "Einen prüfbaren Proposal-Datensatz erzeugen, ohne das freigegebene Modell direkt zu verändern.";
  return "Nutzerfrage im aktiven Projektkontext beantworten und dafür benötigte Engineering-Daten lesen.";
}

function inferAgentAssumption(text: string, goal: string) {
  const lower = text.toLowerCase();
  if (goal.includes("Proposal") || lower.includes("neu") || lower.includes("erstelle") || lower.includes("schlage")) {
    return "Neue Inhalte werden als Vorschlag angelegt; Freigabe und Übernahme bleiben beim Menschen.";
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
    proposeEngineeringObject: "Warum: neues Objekt als überprüfbaren Vorschlag speichern.",
    proposeEngineeringRelation: "Warum: neue Beziehung als überprüfbaren Vorschlag speichern.",
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
  if (value.proposal || value.proposal_id) return "Vorschlag wurde erzeugt; menschliche Prüfung/Freigabe bleibt erforderlich.";
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

function MessagePart({ part }: { part: EngineeringAgentUIMessage["parts"][number] }) {
  if (part.type === "text") {
    return <p className="eng-agent-text">{part.text}</p>;
  }

  if (part.type === "tool-listEngineeringObjects" || part.type === "tool-listEngineeringRelations") {
    return <ToolCallCard label="Suche im Engineering-Modell" part={part} />;
  }

  if (part.type === "tool-proposeEngineeringObject") {
    return <ToolCallCard label="Vorschlag: neues Objekt" part={part} />;
  }

  if (part.type === "tool-proposeEngineeringRelation") {
    return <ToolCallCard label="Vorschlag: neue Relation" part={part} />;
  }

  if (part.type.startsWith("tool-")) {
    return <ToolCallCard
      label={`Routing · ${part.type.replace("tool-", "").replaceAll("_", " ")}`}
      part={part as { state: string; input?: unknown; output?: unknown; errorText?: string }}
    />;
  }

  return null;
}

function ToolCallCard({
  label,
  part,
}: {
  label: string;
  part: { state: string; input?: unknown; output?: unknown; errorText?: string };
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
          <details className="eng-agent-tool-details">
            <summary>Ergebnis anzeigen</summary>
            <AgentToolResult output={part.output} />
          </details>
        </>
      )}
      {part.state === "output-error" && <span className="notice error">{part.errorText}</span>}
    </div>
  );
}

function summarizeToolOutput(output: unknown): string {
  if (!output || typeof output !== "object") return "Analyse abgeschlossen.";
  const value = output as Record<string, unknown>;
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
