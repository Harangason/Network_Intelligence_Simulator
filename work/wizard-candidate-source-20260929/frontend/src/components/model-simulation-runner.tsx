"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  cancelSimulation,
  createSimulation,
  createSimulationFaultProposals,
  getCatalog,
  getSimulation,
  listSimulationFaultProposals,
  reviewSimulationFaultProposal,
  saveSimulationScenario,
  type FaultProposal,
} from "@/lib/api";
import {
  defaultSimulationFormats,
  describeSimulationFormat,
  groupSimulationFormats,
  mergeSimulationFormats,
  simulationFormatDefinitions,
} from "@/lib/simulation-formats";
import { topologyToConfig, type NetworkTopology } from "@/lib/topology";
import { createSimulationSnapshot, getWorkflow, setWorkflowContext, type SimulationSnapshot, type WorkflowState } from "@/lib/workflow-api";
import type { Catalog, ModelSignalSeries, ModelSimulationTrace, RuntimeNetworkMetric, SimulationJob } from "@/lib/types";
import { SimulationResult } from "./simulation-result";
import { notifyWorkflowChanged } from "./workflow-header";
import { useWorkflowRefresh } from "@/lib/use-workflow-refresh";
import { withProjectParam } from "@/lib/user-settings";
import { simulationScopeFrom, simulationScopeValid } from "@/lib/simulation-scope";
import {
  filterSignalSeries,
  formatSignalValue,
  initialSignalSelection,
  signalCurrentPoint,
  type SignalBehaviorFilter,
  type SignalKindFilter,
} from "@/lib/simulation-signal-view";
import { formatParticipants, runtimeNetworkPresentation, runtimeRoutePresentation, technologyLabel } from "@/lib/simulation-network-view";
import { sequenceModelForEventIds, type SequenceDiagramModel } from "@/lib/e2e-sequence";
import { E2ESequenceDiagram } from "./e2e-sequence-diagram";

type SimulationView = "network" | "sequence" | "signals" | "load" | "events";
type ScenarioFault = {
  id: string;
  scope: "SIGNAL" | "MESSAGE" | "NETWORK";
  type: string;
  target: Record<string, unknown>;
  start_s: number;
  end_s?: number;
  magnitude?: number;
  source?: "user" | "ai";
  approved?: boolean;
  proposal_id?: string;
};

const FAULT_TYPES = {
  SIGNAL: ["SIGNAL_STUCK", "SIGNAL_OFFSET", "SIGNAL_DRIFT", "SIGNAL_SPIKE", "SIGNAL_DROPOUT", "SIGNAL_NOISE", "SIGNAL_OUT_OF_RANGE", "SIGNAL_FROZEN", "SIGNAL_DELAYED", "SIGNAL_WRONG_SCALE", "SIGNAL_INVALID_VALUE"],
  MESSAGE: ["MESSAGE_LOSS", "MESSAGE_DELAY", "MESSAGE_JITTER", "MESSAGE_DUPLICATION", "MESSAGE_CORRUPTION", "MESSAGE_WRONG_CYCLE", "MESSAGE_TIMEOUT", "BURST_TRAFFIC", "FRAME_ERROR", "ROUTING_FAILURE"],
  NETWORK: ["NETWORK_OVERLOAD", "BUS_OFF", "LINK_DOWN", "GATEWAY_DELAY", "GATEWAY_DROP", "QUEUE_OVERFLOW", "CONGESTION", "TEMPORARY_DISCONNECT"],
} as const;

function simulationSessionKey(projectId: string) {
  return `nis.active-simulation.${projectId}`;
}

export function ModelSimulationRunner({ initialProjectId = "" }: { initialProjectId?: string }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const [job, setJob] = useState<SimulationJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [savedScenarioNotice, setSavedScenarioNotice] = useState("");
  const [mode, setMode] = useState("GOLDEN");
  const [duration, setDuration] = useState(2);
  const [speed, setSpeed] = useState(1);
  const [seed, setSeed] = useState(42);
  const [formats, setFormats] = useState(defaultSimulationFormats);
  const [formatPickerOpen, setFormatPickerOpen] = useState(false);
  const [faults, setFaults] = useState<ScenarioFault[]>([]);
  const [faultScope, setFaultScope] = useState<keyof typeof FAULT_TYPES>("SIGNAL");
  const [faultType, setFaultType] = useState<string>(FAULT_TYPES.SIGNAL[0]);
  const [faultTarget, setFaultTarget] = useState("");
  const [faultStart, setFaultStart] = useState(0.25);
  const [faultEnd, setFaultEnd] = useState(1.5);
  const [faultMagnitude, setFaultMagnitude] = useState(5);
  const [proposals, setProposals] = useState<FaultProposal[]>([]);
  const [proposalMagnitude, setProposalMagnitude] = useState<Record<string, number>>({});
  const [proposalReviewState, setProposalReviewState] = useState<Record<string, { busy: boolean; message: string; error?: boolean }>>({});
  const [view, setView] = useState<SimulationView>("signals");
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [restoredProjectId, setRestoredProjectId] = useState("");
  const [restoreAttempt, setRestoreAttempt] = useState(0);
  const [restoreError, setRestoreError] = useState("");
  const [resetPromptOpen, setResetPromptOpen] = useState(false);

  useEffect(() => {
    const projectId = workflow?.project_id;
    if (!projectId) return;
    let active = true;
    setRestoredProjectId("");
    setRestoreError("");
    setJob(null);
    setSnapshot(null);
    const savedJobId = window.sessionStorage.getItem(simulationSessionKey(projectId));
    if (!savedJobId) {
      setRestoredProjectId(projectId);
      return () => { active = false; };
    }
    void getSimulation(savedJobId).then((savedJob) => {
      if (!active) return;
      setJob(savedJob);
      setRestoredProjectId(projectId);
    }).catch((caught) => {
      if (active) setRestoreError(caught instanceof Error ? caught.message : "Simulationslauf nicht erreichbar.");
    });
    return () => { active = false; };
  }, [restoreAttempt, workflow?.project_id]);

  useEffect(() => {
    const projectId = workflow?.project_id;
    if (!projectId || restoredProjectId !== projectId) return;
    const key = simulationSessionKey(projectId);
    if (job) window.sessionStorage.setItem(key, job.id);
    else window.sessionStorage.removeItem(key);
  }, [job, restoredProjectId, workflow?.project_id]);

  useEffect(() => {
    if (!job) return;
    const warnBeforeLeaving = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [job]);

  const loadWorkflow = useCallback(async () => {
    try {
      const nextWorkflow = await getWorkflow();
      setWorkflow(nextWorkflow);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Workflow nicht verfügbar.");
    }
  }, []);
  useWorkflowRefresh(loadWorkflow);

  useEffect(() => {
    void getCatalog().then(setCatalog).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!workflow?.project_id) return;
    void listSimulationFaultProposals(workflow.project_id).then((response) => setProposals(response.items)).catch(() => undefined);

  }, [workflow?.project_id, workflow?.versions.engineering_model]);

  useEffect(() => {
    void setWorkflowContext({
      selected_simulation: snapshot ? { snapshot_id: snapshot.id, job_id: job?.id ?? null } : null,
    }).catch(() => undefined);
  }, [job?.id, snapshot]);

  useEffect(() => {
    if (job?.status === "completed") setPlaying(true);
  }, [job?.status]);

  useEffect(() => {
    if (!playing || !job?.result?.model_simulation) return;
    const maximum = Number(job.result.model_simulation.scenario.duration_s || duration);
    const timer = window.setInterval(() => {
      setPlayhead((current) => {
        const next = current + 0.05 * speed;
        if (next >= maximum) {
          setPlaying(false);
          return maximum;
        }
        return next;
      });
    }, 50);
    return () => window.clearInterval(timer);
  }, [duration, job?.result?.model_simulation, playing, speed]);

  const valid = workflow?.statuses.validation === "APPROVED" || workflow?.statuses.validation === "WARNING";
  const projectIdForLinks = workflow?.project_id ?? initialProjectId;
  const simulationOutdated = workflow?.statuses.simulation === "OUTDATED";
  const running = Boolean(job && !["completed", "failed", "canceled"].includes(job.status));
  const selectedTechnology = useMemo(() => {
    const industry = String(workflow?.parameters.industry ?? "");
    const technology = String(workflow?.parameters.technology ?? "");
    const domain = catalog?.domains.find((item) => item.id === industry)
      ?? catalog?.domains.find((item) => item.technologies.some((candidate) => candidate.id === technology));
    return domain?.technologies.find((item) => item.id === technology);
  }, [catalog, workflow?.parameters.industry, workflow?.parameters.technology]);
  const availableFormats = useMemo(
    () => mergeSimulationFormats(
      simulationFormatDefinitions.map((format) => format.id),
      catalog?.formats,
      selectedTechnology?.native_formats,
      defaultSimulationFormats,
      formats,
    ),
    [catalog?.formats, formats, selectedTechnology?.native_formats],
  );
  const formatGroups = useMemo(() => groupSimulationFormats(availableFormats), [availableFormats]);
  const selectedFormatLabels = useMemo(
    () => formats.map((format) => describeSimulationFormat(format).label),
    [formats],
  );
  const simulationScope = simulationScopeFrom(workflow?.parameters.simulation_scope);
  const scopeValid = simulationScopeValid(simulationScope);

  function buildScenario(name?: string) {
    const scenarioMode = mode === "GOLDEN" ? "NORMAL" : mode;
    return {
      name: name || (mode === "GOLDEN" ? "Golden / Ideal" : mode === "NORMAL" ? "Normalbetrieb" : mode === "STRESS" ? "Stresstest" : "Fehlerszenario"),
      mode: scenarioMode,
      trace_type: mode,
      duration_s: duration,
      speed,
      seed,
      trace_formats: formats,
      simulation_scope: simulationScope,
      faults,
      source: "simulation-workbench",
    };
  }

  const handleJobChange = useCallback((nextJob: SimulationJob) => {
    setJob(nextJob);
    if (["completed", "failed", "canceled"].includes(nextJob.status)) {
      void getWorkflow().then(setWorkflow).catch(() => undefined);
      notifyWorkflowChanged();
    }
  }, []);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workflow || !valid || restoredProjectId !== workflow.project_id) return;
    setBusy(true);
    setError("");
    setPlayhead(0);
    try {
      const topology = workflow.topology as NetworkTopology;
      const hasTopology = Array.isArray(topology.nodes) && topology.nodes.length >= 2 && Array.isArray(topology.edges) && topology.edges.length > 0;
      let config: Record<string, unknown> = hasTopology
        ? topologyToConfig(topology, formats).config
        : { name: "validated_workflow_simulation", industry: workflow.parameters.industry ?? "automotive", technology: workflow.parameters.technology ?? "can_fd", node_count: 2, formats };
      const scenario = buildScenario();
      const storedScenario = await saveSimulationScenario(workflow.project_id, scenario);
      const communicationRows = Array.isArray(config.communications)
        ? config.communications.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        : [];
      const estimatedEventCount = communicationRows.reduce((sum, communication) => {
        const cycleMs = Math.max(0.001, Number(communication.cycle_ms ?? communication.period_ms ?? 100));
        return sum + Math.ceil(duration / (cycleMs / 1000));
      }, 0);
      const receiverCount = communicationRows.reduce((sum, communication) => sum + Math.max(1, Array.isArray(communication.receiver_interfaces) ? communication.receiver_interfaces.length : 1), 0);
      const heartbeatFrames = Math.floor(duration / 0.5) * 2 * receiverCount;
      const sessionFrames = estimatedEventCount + receiverCount * 3 + heartbeatFrames;
      const maxEvents = Math.min(100_000, Math.max(1, Math.ceil((estimatedEventCount + sessionFrames) * 1.1)));
      config = {
        ...config,
        ...workflow.parameters,
        duration_s: duration,
        seed,
        formats,
        max_events: maxEvents,
        model_trace_frame_limit: 25_000,
        model_trace_signal_point_limit: 300_000,
        model_trace_points_per_signal: 800,
        model_trace_event_limit: 10_000,
        golden_trace_event_limit: 10_000,
        restbus_session: {
          enabled: true,
          handshake: true,
          acknowledge_data: true,
          heartbeat_interval_s: 0.5,
          response_delay_ms: 1,
        },
        simulation_scope: simulationScope,
        scenario: { ...scenario, scenario_id: storedScenario.scenario_id },
      };
      const nextSnapshot = await createSimulationSnapshot(config);
      setSnapshot(nextSnapshot);
      const nextJob = await createSimulation({
        workflow_managed: true,
        workflow_snapshot_id: nextSnapshot.id,
        project_id: workflow.project_id,
        scenario: { ...scenario, scenario_id: storedScenario.scenario_id },
        duration_s: duration,
        seed,
        formats,
        ...(hasTopology ? { config } : config),
      }, false);
      setJob(nextJob);
      notifyWorkflowChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Simulation konnte nicht gestartet werden.");
    } finally {
      setBusy(false);
    }
  }

  async function saveScenarioAs() {
    if (!workflow || !valid || formats.length === 0 || !scopeValid) return;
    const defaultName = `${mode === "GOLDEN" ? "Golden / Ideal" : mode === "NORMAL" ? "Normalbetrieb" : mode === "STRESS" ? "Stresstest" : "Fehlerszenario"} ${new Date().toLocaleString("de-DE")}`;
    const name = window.prompt("Szenario speichern unter", defaultName)?.trim();
    if (!name) return;
    setBusy(true);
    setError("");
    setSavedScenarioNotice("");
    try {
      const saved = await saveSimulationScenario(workflow.project_id, buildScenario(name));
      setSavedScenarioNotice(`Szenario "${String(saved.name || name)}" gespeichert.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Szenario konnte nicht gespeichert werden.");
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    setPlaying(false);
    if (!job || !running) return;
    setBusy(true);
    try {
      setJob(await cancelSimulation(job.id));
      notifyWorkflowChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Simulation konnte nicht gestoppt werden.");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    if (job) {
      setResetPromptOpen(true);
      return;
    }
    clearSimulationView();
  }

  function clearSimulationView() {
    if (workflow?.project_id) window.sessionStorage.removeItem(simulationSessionKey(workflow.project_id));
    setResetPromptOpen(false);
    setPlaying(false);
    setPlayhead(0);
    setJob(null);
    setSnapshot(null);
    setError("");
  }

  function toggleFormat(format: string, checked: boolean) {
    setFormats((current) => checked
      ? mergeSimulationFormats(current, [format])
      : current.filter((item) => item !== format));
  }

  function addFault() {
    const type = faultType || FAULT_TYPES[faultScope][0];
    setFaults((current) => [...current, {
      id: crypto.randomUUID(), scope: faultScope, type,
      target: faultTarget.trim() ? { id: faultTarget.trim() } : {},
      start_s: faultStart, end_s: Math.max(faultStart + 0.001, faultEnd), magnitude: faultMagnitude, source: "user", approved: true,
    }]);
    if (mode === "NORMAL" || mode === "GOLDEN") setMode("USER_DEFINED_FAULT");
  }

  async function askAgentForFaults() {
    if (!workflow) return;
    setBusy(true);
    try {
      const response = await createSimulationFaultProposals(workflow.project_id);
      setProposals((current) => [...response.items, ...current]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Fehlervorschläge konnten nicht erstellt werden.");
    } finally {
      setBusy(false);
    }
  }

  async function reviewProposal(proposal: FaultProposal, action: "ACCEPT" | "EDIT" | "REJECT") {
    if (!workflow) return;
    const proposalId = proposal.proposal_id;
    const magnitude = proposalMagnitude[proposalId] ?? Number(proposal.configuration.magnitude ?? 5);
    if (action === "EDIT" && (!Number.isFinite(magnitude) || magnitude < 0)) {
      setProposalReviewState((current) => ({ ...current, [proposalId]: { busy: false, error: true, message: "Bitte eine gültige Magnitude ab 0 eingeben." } }));
      return;
    }
    setProposalReviewState((current) => ({ ...current, [proposalId]: { busy: true, message: "Wird gespeichert …" } }));
    try {
      const reviewed = await reviewSimulationFaultProposal(
        workflow.project_id,
        proposalId,
        action,
        action === "EDIT" ? { configuration: { ...proposal.configuration, magnitude } } : undefined,
      );
      setProposals((current) => current.map((item) => item.proposal_id === reviewed.proposal_id ? reviewed : item));
      if (action === "EDIT") {
        setProposalMagnitude((current) => ({ ...current, [proposalId]: Number(reviewed.configuration.magnitude ?? magnitude) }));
        setProposalReviewState((current) => ({ ...current, [proposalId]: { busy: false, message: `Änderung gespeichert · Magnitude ${Number(reviewed.configuration.magnitude ?? magnitude)}` } }));
      } else {
        setProposalReviewState((current) => ({ ...current, [proposalId]: { busy: false, message: action === "ACCEPT" ? "Vorschlag übernommen." : "Vorschlag abgelehnt." } }));
      }
      if (action === "ACCEPT") {
        setFaults((current) => current.some((item) => item.proposal_id === proposalId) ? current : [...current, {
          id: crypto.randomUUID(), scope: proposal.fault_scope, type: proposal.fault_type,
          target: proposal.target, start_s: Number(reviewed.configuration.start_s ?? 0.25),
          end_s: Number(reviewed.configuration.end_s ?? duration * 0.75),
          magnitude: Number(reviewed.configuration.magnitude ?? 5), source: "ai", approved: true,
          proposal_id: proposalId,
        }]);
        setMode("AI_GENERATED_FAULT");
      }
    } catch (caught) {
      setProposalReviewState((current) => ({ ...current, [proposalId]: { busy: false, error: true, message: caught instanceof Error ? caught.message : "Änderung konnte nicht gespeichert werden." } }));
    }
  }

  const modelTrace = job?.result?.model_simulation;
  const maximumTime = Number(modelTrace?.scenario.duration_s || duration);

  return (
    <section className="simulation-runner model-simulation-runner">
      {!valid && <div className="workflow-blocker error"><strong>Simulation blockiert</strong><span>Ein aktueller Preflight mit Status APPROVED oder WARNING ist erforderlich.</span><Link href={withProjectParam("/studio/validation", projectIdForLinks)}>Preflight öffnen</Link></div>}
      {simulationOutdated && <div className="workflow-blocker warning"><strong>Frühere Simulation ist OUTDATED</strong><span>{workflow?.stale_reasons.simulation}</span></div>}

      <form className="panel simulation-command-bar" onSubmit={start}>
        <label><span>Szenario</span><select value={mode} onChange={(event) => setMode(event.target.value)}><option value="GOLDEN">Golden / Ideal</option><option value="NORMAL">Normal</option><option value="USER_DEFINED_FAULT">Nutzerfehler</option><option value="AI_GENERATED_FAULT">Geprüfter KI-Fehler</option><option value="STRESS">Stresstest</option></select></label>
        <NumberInput label="Dauer" unit="s" value={duration} min={0.1} step={0.1} onChange={setDuration} />
        <NumberInput label="Geschwindigkeit" unit="x" value={speed} min={0.1} step={0.1} onChange={setSpeed} />
        <NumberInput label="Seed" value={seed} min={0} step={1} onChange={setSeed} />
        <div className="trace-format-control">
          <span>Trace-Formate</span>
          <button
            aria-expanded={formatPickerOpen}
            aria-haspopup="dialog"
            className="trace-format-trigger"
            onClick={() => setFormatPickerOpen((current) => !current)}
            type="button"
          >
            <strong>{formats.length}</strong>
            <small>{selectedFormatLabels.slice(0, 3).join(", ")}{formats.length > 3 ? ` +${formats.length - 3}` : ""}</small>
          </button>
          {formatPickerOpen && (
            <div className="trace-format-popover" role="dialog" aria-label="Trace-Formate auswählen">
              {formatGroups.map((group) => (
                <section key={group.id}>
                  <h3>{group.label}</h3>
                  <div>
                    {group.formats.map((format) => (
                      <label className={formats.includes(format.id) ? "selected" : ""} key={format.id}>
                        <input
                          checked={formats.includes(format.id)}
                          onChange={(event) => toggleFormat(format.id, event.target.checked)}
                          type="checkbox"
                        />
                        <span>{format.label}</span>
                        <small>{format.description}</small>
                      </label>
                    ))}
                  </div>
                </section>
              ))}
              <footer>
                <span>{formats.length ? `${formats.length} Formate ausgewählt` : "Mindestens ein Format wählen"}</span>
                <button className="button secondary tiny" onClick={() => setFormatPickerOpen(false)} type="button">Schließen</button>
              </footer>
            </div>
          )}
        </div>
        <div className="simulation-transport-controls">
          <button className="button secondary" disabled={!valid || busy || formats.length === 0 || !scopeValid || !workflow} onClick={() => void saveScenarioAs()} type="button">Speichern unter</button>
          <button className="button primary" disabled={!valid || busy || Boolean(job) || restoredProjectId !== workflow?.project_id || formats.length === 0 || !scopeValid} type="submit">Start</button>
          <button className="button secondary" disabled={!job?.result?.model_simulation} onClick={() => setPlaying((current) => !current)} type="button">{playing ? "Pause" : "Weiter"}</button>
          <button className="button secondary" disabled={!running} onClick={() => void stop()} type="button">Stop</button>
          <button className="button secondary" disabled={!job || running || busy} onClick={reset} type="button">Reset</button>
        </div>
      </form>
      {savedScenarioNotice && <div className="notice success">{savedScenarioNotice}</div>}
      {restoreError && <div className="notice error" role="alert">Der gespeicherte Simulationslauf konnte nicht geladen werden: {restoreError} <button className="button secondary tiny" onClick={() => setRestoreAttempt((attempt) => attempt + 1)} type="button">Erneut laden</button></div>}
      {workflow?.project_id && restoredProjectId !== workflow.project_id && !restoreError && <div className="notice" role="status">Der letzte Simulationslauf dieser Sitzung wird wiederhergestellt …</div>}
      {resetPromptOpen && job && (
        <div className="project-dialog-backdrop">
          <section aria-labelledby="simulation-reset-title" aria-modal="true" className="project-dialog simulation-reset-dialog" role="alertdialog">
            <div>
              <p className="eyebrow">Simulations-Trace</p>
              <h2 id="simulation-reset-title">Trace vor dem Zurücksetzen sichern?</h2>
              <p>Der Lauf bleibt bis zum Zurücksetzen in dieser Sitzung erhalten. Lade gewünschte Artefakte jetzt herunter. Danach wird die Ansicht geleert; du kannst den Lauf bis dahin durch Navigation oder Neuladen wieder öffnen.</p>
            </div>
            {!!job.artifact_downloads?.length && (
              <div className="simulation-reset-artifacts" aria-label="Trace-Artefakte herunterladen">
                {job.artifact_downloads.map((artifact) => (
                  <a className="button secondary" download={artifact.name} href={artifact.url} key={artifact.index}>{artifact.name} herunterladen</a>
                ))}
              </div>
            )}
            <div className="project-dialog-actions">
              <button className="button secondary" onClick={() => setResetPromptOpen(false)} type="button">Zurück zum Trace</button>
              <button className="button primary" onClick={clearSimulationView} type="button">Ansicht zurücksetzen</button>
            </div>
          </section>
        </div>
      )}

      <section className="panel simulation-scope-panel">
        <div className="compact-heading"><div><p className="eyebrow">Geprüfter Simulationsumfang</p><h2>{simulationScope.include_all ? "Gesamtes aktives Modell" : `${simulationScope.message_ids.length} Nachrichten und ${simulationScope.signal_ids.length} Signale ausgewählt`}</h2></div><Link className="button secondary" href={withProjectParam("/studio/validation", projectIdForLinks)}>Umfang im Preflight ändern</Link></div>
        <p>{simulationScope.include_all ? "Alle aktiven Modellnachrichten und Signale müssen durch bestätigte Routen abgedeckt sein." : simulationScope.reason}</p>
        <p>Die Simulation verwendet genau den gespeicherten und vorab geprüften Umfang. Ausgewählte Nachrichten schließen ihre enthaltenen Signale ein.</p>
        {!scopeValid && <p className="notice warning">Der gespeicherte Umfang braucht eine gültige Auswahl und Begründung. Bitte im Preflight ergänzen.</p>}
      </section>

      <section className="panel fault-editor">
          <div className="compact-heading"><div><p className="eyebrow">Fault scenario</p><h2>Fehler gezielt injizieren</h2></div><button className="button secondary" disabled={busy || !workflow} onClick={() => void askAgentForFaults()} type="button">KI-Vorschläge</button></div>
          <div className="fault-builder">
            <select value={faultScope} onChange={(event) => { const scope = event.target.value as keyof typeof FAULT_TYPES; setFaultScope(scope); setFaultType(FAULT_TYPES[scope][0]); }}><option value="SIGNAL">Signal</option><option value="MESSAGE">Message</option><option value="NETWORK">Network</option></select>
            <select value={faultType} onChange={(event) => setFaultType(event.target.value)}>{FAULT_TYPES[faultScope].map((type) => <option key={type}>{type}</option>)}</select>
            <input aria-label="Ziel-ID" placeholder="Ziel-ID, leer = alle" value={faultTarget} onChange={(event) => setFaultTarget(event.target.value)} />
            <input aria-label="Fault Start" min="0" placeholder="Start s" step="0.01" type="number" value={faultStart} onChange={(event) => setFaultStart(Number(event.target.value))} />
            <input aria-label="Fault Ende" min={faultStart + 0.001} placeholder="Ende s" step="0.01" type="number" value={faultEnd} onChange={(event) => setFaultEnd(Number(event.target.value))} />
            <input aria-label="Fault Wert" placeholder="Wert" step="0.1" type="number" value={faultMagnitude} onChange={(event) => setFaultMagnitude(Number(event.target.value))} />
            <button className="button primary" onClick={addFault} type="button">Hinzufügen</button>
          </div>
          <div className="fault-chip-list">{faults.map((fault) => <button className="fault-chip" key={fault.id} title="Fehler entfernen" type="button" onClick={() => setFaults((current) => current.filter((item) => item.id !== fault.id))}><strong>{fault.type}</strong><span>{fault.scope} · {fault.source === "ai" ? "KI geprüft" : "Nutzer"}</span><b>×</b></button>)}{!faults.length && <span className="empty-inline">Keine Fehler aktiv. Der Lauf bildet den Golden Trace.</span>}</div>
      </section>

      <FaultProposalReview proposals={proposals.filter((proposal) => proposal.status !== "REJECTED" && proposal.status !== "SUPERSEDED")} magnitudes={proposalMagnitude} reviewState={proposalReviewState} onMagnitude={(id, value) => { setProposalMagnitude((current) => ({ ...current, [id]: value })); setProposalReviewState((current) => ({ ...current, [id]: { busy: false, message: "Nicht gespeicherte Änderung" } })); }} onReview={reviewProposal} />
      {error && <div className="notice error">{error}</div>}

      <div className="simulation-view-tabs" role="tablist">{(["network", "sequence", "signals", "load", "events"] as SimulationView[]).map((item) => <button aria-selected={view === item} className={view === item ? "active" : ""} key={item} onClick={() => setView(item)} role="tab" type="button">{{ network: "NETWORK / ECU", sequence: "SEQUENCE", signals: "SIGNALS", load: "BUS LOAD", events: "EVENTS" }[item]}</button>)}</div>
      <section className="panel synchronized-simulation-view">
        <SimulationTimeline duration={maximumTime} playhead={playhead} playing={playing} onChange={setPlayhead} />
        {!modelTrace && <div className="simulation-empty-state"><strong>{job ? "Simulation wird verarbeitet" : "Noch kein Lauf gestartet"}</strong><span>Nach dem Start erscheinen Signalwerte, Buslast und Ereignisse auf derselben Zeitachse.</span></div>}
        {modelTrace && view === "network" && <NetworkView job={job} trace={modelTrace} playhead={playhead} topology={workflow?.topology} />}
        {modelTrace && view === "sequence" && <SequenceView trace={modelTrace} model={job?.result?.runtime_metrics?.sequence_model} playhead={playhead} />}
        {modelTrace && view === "signals" && <SignalsView trace={modelTrace} playhead={playhead} />}
        {modelTrace && view === "load" && <BusLoadView metrics={job?.result?.runtime_metrics?.networks ?? []} playhead={playhead} projectId={projectIdForLinks} topology={workflow?.topology} trace={modelTrace} />}
        {modelTrace && view === "events" && <EventsView trace={modelTrace} playhead={playhead} />}
      </section>

      {job && (
        <SimulationResult
          action={<Link className="button primary result-heading-action" href={withProjectParam(`/trace-analysis?job=${job.id}&view=signals`, workflow?.project_id)}>Trace direkt analysieren</Link>}
          jobId={job.id}
          onJobChange={handleJobChange}
        />
      )}
    </section>
  );
}

function NumberInput({ label, unit, value, min, step, onChange }: { label: string; unit?: string; value: number; min: number; step: number; onChange: (value: number) => void }) {
  return <label><span>{label}{unit ? ` (${unit})` : ""}</span><input min={min} step={step} type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function SimulationTimeline({ duration, playhead, playing, onChange }: { duration: number; playhead: number; playing: boolean; onChange: (value: number) => void }) {
  return <div className="simulation-timeline"><span>{playing ? "RUNNING" : "PAUSED"}</span><input aria-label="Simulationszeit" max={Math.max(duration, 0.001)} min="0" step="0.001" type="range" value={Math.min(playhead, duration)} onChange={(event) => onChange(Number(event.target.value))} /><strong>{playhead.toFixed(3)} / {duration.toFixed(3)} s</strong></div>;
}

function FaultProposalReview({ proposals, magnitudes, reviewState, onMagnitude, onReview }: { proposals: FaultProposal[]; magnitudes: Record<string, number>; reviewState: Record<string, { busy: boolean; message: string; error?: boolean }>; onMagnitude: (id: string, value: number) => void; onReview: (proposal: FaultProposal, action: "ACCEPT" | "EDIT" | "REJECT") => Promise<void> }) {
  if (!proposals.length) return null;
  return <section className="panel fault-proposal-review"><div className="compact-heading"><div><p className="eyebrow">Review gate</p><h2>KI-Fehlervorschläge</h2></div><span>Keine automatische Aktivierung</span></div><div className="fault-proposal-grid">{proposals.map((proposal) => { const state = reviewState[proposal.proposal_id]; return <article key={proposal.proposal_id} className={proposal.status === "APPROVED" ? "approved" : ""}><div><span>{proposal.fault_scope}</span><strong>{proposal.title}</strong><p>{proposal.rationale}</p></div><label><span>Magnitude</span><input type="number" min="0" step="any" value={magnitudes[proposal.proposal_id] ?? Number(proposal.configuration.magnitude ?? 5)} onChange={(event) => onMagnitude(proposal.proposal_id, Number(event.target.value))} /></label><div className="proposal-actions"><button className="button primary" disabled={state?.busy || proposal.status === "APPROVED"} onClick={() => void onReview(proposal, "ACCEPT")} type="button">Übernehmen</button><button className="button secondary" disabled={state?.busy} onClick={() => void onReview(proposal, "EDIT")} type="button">{state?.busy ? "Speichert …" : "Ändern"}</button><button className="button secondary" disabled={state?.busy} onClick={() => void onReview(proposal, "REJECT")} type="button">Ablehnen</button></div>{state?.message && <p className={state.error ? "proposal-feedback error" : "proposal-feedback"} role="status">{state.message}</p>}</article>; })}</div></section>;
}

function NetworkView({ job, trace, playhead, topology }: { job: SimulationJob | null; trace: ModelSimulationTrace; playhead: number; topology?: Partial<NetworkTopology> }) {
  const networks = job?.result?.runtime_metrics?.networks ?? [];
  const routes = job?.result?.runtime_metrics?.routes ?? [];
  const visibleFrames = (trace.frames ?? []).filter((frame) => frame.time_s <= playhead + 0.000001);
  const framesByRoute = useMemo(() => {
    const grouped = new Map<string, ModelSimulationTrace["frames"]>();
    for (const frame of trace.frames ?? []) {
      const existing = grouped.get(frame.route_id);
      if (existing) existing.push(frame);
      else grouped.set(frame.route_id, [frame]);
    }
    return grouped;
  }, [trace.frames]);
  const activeRoutes = new Set(visibleFrames.map((frame) => frame.route_id));
  const delivered = visibleFrames.filter((frame) => frame.status !== "dropped").length;
  const currentLoads = networks.map((network) => (trace.bus_load ?? []).filter((point) => point.network_id === network.network_id && point.time_s <= playhead + 0.000001).at(-1)?.load_percent ?? 0);
  const currentLoad = currentLoads.length ? Math.max(...currentLoads) : 0;
  return <div className="network-runtime-view"><div className="network-runtime-nodes"><article><span>AKTIVE PFADE</span><strong>{activeRoutes.size}</strong><small>bis {playhead.toFixed(3)} s</small></article><div className="runtime-link-line" /><article className="gateway-runtime-node"><span>SIMULATED LOAD</span><strong>{currentLoad.toFixed(1)} %</strong><small>{visibleFrames.length} Frames · {networks.length} Netze</small></article><div className="runtime-link-line" /><article><span>ZUGESTELLT</span><strong>{delivered}</strong><small>{visibleFrames.length - delivered} verworfen</small></article></div><div className="runtime-route-list"><div className="runtime-route-heading"><span>Route</span><span>TX</span><span>RX</span><span>Takt</span><span>Frames</span><span>Status</span></div>{routes.slice(0, 12).map((route) => { const routeFrames = framesByRoute.get(route.route_id) ?? []; const dataFrames = routeFrames.filter((frame) => (frame.traffic_type ?? "DATA") === "DATA"); const presentation = runtimeRoutePresentation(route, dataFrames, topology); return <div className="runtime-route-row" key={route.route_id}><strong>{presentation.name}<small>{route.route_id}</small></strong><span><b>TX</b>{presentation.sender}</span><span><b>RX</b>{formatParticipants(presentation.receivers, 2)}</span><span>{route.configured_cycle_ms} ms</span><span>{dataFrames.filter((frame) => frame.time_s <= playhead + 0.000001).length} / {route.event_count}</span><b className={route.status === "PASS" ? "pass" : "fail"}>{route.status}</b></div>; })}</div><div className="runtime-frame-list"><strong>Frame-Trace am Zeitzeiger</strong>{visibleFrames.slice(-20).reverse().map((frame, index) => <div key={`${frame.route_id}:${frame.time_s}:${index}`}><time>{frame.time_s.toFixed(4)} s</time><span>TX {frame.source_logical_address ?? "—"} · {frame.source_name ?? frame.sender}</span><span>RX {(frame.destination_logical_addresses ?? []).map((address, receiverIndex) => `${address ?? "—"} · ${frame.destination_names?.[receiverIndex] ?? frame.receivers?.[receiverIndex] ?? "unbekannt"}`).join(", ")}</span><span>{frame.route_name} · {frame.network}</span></div>)}</div></div>;
}

function SequenceView({ trace, model: sourceModel, playhead }: { trace: ModelSimulationTrace; model?: SequenceDiagramModel; playhead: number }) {
  const model = useMemo(() => sourceModel ? sequenceModelForEventIds(sourceModel, new Set((trace.frames ?? [])
    .filter(frame => frame.time_s <= playhead + 0.000001).map(frame => String(frame.event_id ?? "")))) : null, [sourceModel, trace.frames, playhead]);
  return model ? <E2ESequenceDiagram model={model} /> : <div className="panel trace-sequence"><p>Das gemeinsame Sequenzmodell steht für diesen Simulationslauf nicht zur Verfügung.</p></div>;
}

function SignalsView({ trace, playhead }: { trace: ModelSimulationTrace; playhead: number }) {
  const [selected, setSelected] = useState(() => initialSignalSelection(trace.signals));
  const [search, setSearch] = useState("");
  const [behavior, setBehavior] = useState<SignalBehaviorFilter>("DYNAMIC");
  const [kind, setKind] = useState<SignalKindFilter>("ALL");
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState(0);
  const signalIds = useMemo(() => trace.signals.map((series) => series.signal_id), [trace.signals]);
  const filtered = useMemo(() => filterSignalSeries(trace.signals, { search, behavior, kind }), [behavior, kind, search, trace.signals]);
  const visibleSelected = filtered.filter((series) => selected.includes(series.signal_id));
  useEffect(() => {
    setSelected(initialSignalSelection(trace.signals));
  }, [signalIds, trace.signals]);
  const windowDuration = trace.scenario.duration_s / zoom;
  const windowStart = Math.min(Math.max(0, pan), Math.max(0, trace.scenario.duration_s - windowDuration));
  const windowEnd = windowStart + windowDuration;
  const filteredIds = filtered.map((series) => series.signal_id);
  const selectFiltered = () => setSelected((current) => [...new Set([...current, ...filteredIds])]);
  const clearFiltered = () => setSelected((current) => current.filter((id) => !filteredIds.includes(id)));
  return <div className="signal-plot-workbench">
    <div className="signal-plot-controls">
      <div className="signal-filter-primary">
        <label className="signal-filter-field signal-filter-search">
          <span>Suche</span>
          <input aria-label="Signale durchsuchen" placeholder="Signal, Einheit oder Modell suchen …" value={search} onChange={(event) => setSearch(event.target.value)} />
        </label>
        <label className="signal-filter-field">
          <span>Verlauf</span>
          <select aria-label="Dynamik filtern" value={behavior} onChange={(event) => setBehavior(event.target.value as SignalBehaviorFilter)}><option value="ALL">Alle Verläufe</option><option value="DYNAMIC">Nur dynamisch</option><option value="STATIC">Nur statisch</option></select>
        </label>
        <label className="signal-filter-field">
          <span>Signaltyp</span>
          <select aria-label="Signaltyp filtern" value={kind} onChange={(event) => setKind(event.target.value as SignalKindFilter)}><option value="ALL">Alle Typen</option><option value="STATE">Zustände</option><option value="PHYSICAL">Physikalisch</option><option value="OTHER">Weitere</option></select>
        </label>
        <button className="button secondary tiny signal-selector-toggle" onClick={() => setSelectorOpen((current) => !current)} type="button">{selectorOpen ? "Auswahl schließen" : "Signale auswählen"}</button>
      </div>
      <div className="signal-filter-secondary">
        <div className="signal-selector-actions">
          <button className="button secondary tiny" onClick={selectFiltered} type="button">Treffer wählen</button>
          <button className="button secondary tiny" onClick={clearFiltered} type="button">Treffer abwählen</button>
        </div>
        <output className="signal-filter-summary">{visibleSelected.length} sichtbar <i /> {selected.length} gewählt <i /> {filtered.length} Treffer</output>
        <div className="signal-time-controls">
          <label><span>Zoom {zoom.toFixed(1)}x</span><input max="8" min="1" step="0.5" type="range" value={zoom} onChange={(event) => { setZoom(Number(event.target.value)); setPan(0); }} /></label>
          <label><span>Pan</span><input disabled={zoom === 1} max={Math.max(0, trace.scenario.duration_s - windowDuration)} min="0" step="0.01" type="range" value={windowStart} onChange={(event) => setPan(Number(event.target.value))} /></label>
        </div>
      </div>
      {selectorOpen && <div className="signal-selector">{filtered.map((series) => <label key={series.signal_id}><input checked={selected.includes(series.signal_id)} type="checkbox" onChange={(event) => setSelected((current) => event.target.checked ? [...new Set([...current, series.signal_id])] : current.filter((id) => id !== series.signal_id))} /><span>{series.signal}<small>{series.semantic_type ?? series.behavior_type} · {series.unit || "ohne Einheit"}</small></span></label>)}{!filtered.length && <p>Keine Signale für diesen Filter.</p>}</div>}
    </div>
    <div className="signal-lanes">{visibleSelected.slice(0, 60).map((series) => <SignalLane key={series.signal_id} series={series} windowStart={windowStart} windowEnd={windowEnd} playhead={playhead} />)}{visibleSelected.length > 60 && <div className="simulation-result-note">60 von {visibleSelected.length} Treffern dargestellt. Filter weiter eingrenzen.</div>}{!trace.signals.length && <div className="simulation-empty-state"><strong>Keine Signalzuordnung gefunden</strong><span>Die Frames wurden simuliert, aber kein Engineering-Signal ist dem Kommunikationspfad zugeordnet.</span></div>}{trace.signals.length > 0 && visibleSelected.length === 0 && <div className="simulation-empty-state"><strong>Keine ausgewählten Treffer</strong><span>Filter ändern oder „Treffer wählen“ verwenden.</span></div>}</div>
  </div>;
}

function SignalLane({ series, windowStart, windowEnd, playhead }: { series: ModelSignalSeries; windowStart: number; windowEnd: number; playhead: number }) {
  const width = 1000;
  const height = 92;
  const span = Math.max(1e-9, series.maximum - series.minimum);
  const visiblePoints = series.points.filter((item) => item.time_s >= windowStart && item.time_s <= windowEnd);
  const point = (time: number, value: number | null) => `${Math.max(0, Math.min(width, (time - windowStart) / Math.max(windowEnd - windowStart, 0.001) * width))},${value === null ? height / 2 : height - (value - series.minimum) / span * height}`;
  const golden = visiblePoints.map((item) => point(item.time_s, item.golden_value)).join(" ");
  const actual = visiblePoints.filter((item) => item.value !== null).map((item) => point(item.time_s, item.value)).join(" ");
  const faultPoints = visiblePoints.filter((item) => item.faults.length);
  const current = signalCurrentPoint(series, playhead);
  const playheadX = (playhead - windowStart) / Math.max(windowEnd - windowStart, 0.001) * width;
  return <article className="signal-lane"><header><div><strong>{series.signal}</strong><span>{series.behavior_type} · {modelLabel(series.model_label)}</span></div><b title={current?.value === null || current?.value === undefined ? "Kein Rohwert" : `Rohwert: ${current.value}`}>{formatSignalValue(series, current)}</b></header><div className="signal-chart"><svg aria-label={`${series.signal} Signalverlauf`} preserveAspectRatio="none" viewBox={`0 0 ${width} ${height}`}><line className="signal-limit" x1="0" x2={width} y1="1" y2="1" /><line className="signal-limit" x1="0" x2={width} y1={height - 1} y2={height - 1} /><polyline className="signal-golden-line" points={golden} /><polyline className="signal-actual-line" points={actual} />{faultPoints.map((item, index) => { const [x, y] = point(item.time_s, item.value).split(","); return <circle className="signal-fault-marker" cx={x} cy={y} key={`${item.time_s}-${index}`} r="4" />; })}{playheadX >= 0 && playheadX <= width && <line className="signal-playhead" x1={playheadX} x2={playheadX} y1="0" y2={height} />}</svg><span className="limit max">{series.maximum}</span><span className="limit min">{series.minimum}</span></div></article>;
}

function modelLabel(label: ModelSignalSeries["model_label"]) {
  return { PHYSICS_BASED: "Physikbasiert", RULE_BASED: "Regelbasiert", EMPIRICAL: "Empirisch", SYNTHETIC: "Synthetisch", GENERIC_ESTIMATE: "Generische Schätzung" }[label];
}

function BusLoadView({ metrics, projectId, trace, playhead, topology }: { metrics: RuntimeNetworkMetric[]; projectId?: string; trace: ModelSimulationTrace; playhead: number; topology?: Partial<NetworkTopology> }) {
  const framesByNetwork = useMemo(() => {
    const grouped = new Map<string, ModelSimulationTrace["frames"]>();
    for (const frame of trace.frames ?? []) {
      const existing = grouped.get(frame.network);
      if (existing) existing.push(frame);
      else grouped.set(frame.network, [frame]);
    }
    return grouped;
  }, [trace.frames]);
  return <div className="bus-load-grid"><div className="bus-load-source"><strong>SIMULATED LOAD</strong><span>Aus tatsächlichen Frames, Protokolloverhead, Zeitstempeln und Bitrate.</span><Link href={withProjectParam("/studio/capacity", projectId)}>CALCULATED LOAD im Capacity View</Link></div>{metrics.map((network) => {
    const visible = (trace.bus_load ?? []).filter((point) => point.network_id === network.network_id && point.time_s <= playhead + 0.000001);
    const current = visible.at(-1)?.load_percent ?? 0;
    const peakToNow = Math.max(0, ...visible.map((point) => point.load_percent));
    const averageToNow = visible.length ? visible.reduce((sum, point) => sum + point.load_percent, 0) / visible.length : 0;
    const burstToNow = visible.reduce((maximum, _point, index) => {
      const window = visible.slice(Math.max(0, index - 1), index + 1);
      const average = window.reduce((sum, point) => sum + point.load_percent, 0) / window.length;
      return Math.max(maximum, average);
    }, 0);
    const reserve = Math.max(0, 100 - peakToNow);
    const status = peakToNow >= 90 ? "OVERLOAD" : peakToNow >= 75 ? "WARNING" : "NOMINAL";
    const presentation = runtimeNetworkPresentation(network, framesByNetwork.get(network.network_id) ?? [], topology);
    return <article key={network.network_id}><header><div><span>{technologyLabel(network.technology)}</span><strong>{presentation.name}</strong><small>{network.network_id}</small></div><b className={`load-status ${status.toLowerCase()}`}>{status} · t = {playhead.toFixed(3)} s</b></header><div className="bus-load-participants"><span><b>TX</b>{formatParticipants(presentation.senders)}</span><span><b>RX</b>{formatParticipants(presentation.receivers)}</span></div>{[["Aktuell 50 ms", current], ["Ø bis Zeitzeiger", averageToNow], ["Peak bis Zeitzeiger", peakToNow], ["Burst 100 ms", burstToNow], ["Reserve", reserve]].map(([label, value]) => <div className="load-meter" key={String(label)}><span>{label}</span><div><i style={{ width: `${Math.min(100, Number(value))}%` }} /></div><strong>{Number(value).toFixed(2)} %</strong></div>)}</article>;
  })}{!metrics.length && <div className="simulation-empty-state"><strong>Keine Laufzeitlast verfügbar</strong></div>}</div>;
}

function EventsView({ trace, playhead }: { trace: ModelSimulationTrace; playhead: number }) {
  const visible = trace.events.filter((event) => event.time_s <= playhead + 0.000001);
  return <div className="simulation-event-table"><table><thead><tr><th>Zeit</th><th>Severity</th><th>Event Type</th><th>Node</th><th>Message</th><th>Signal</th><th>Network</th><th>Beschreibung</th></tr></thead><tbody>{visible.map((event, index) => <tr key={`${event.time_s}-${event.target}-${index}`}><td>{Number(event.time_s).toFixed(4)} s</td><td>{event.severity}</td><td>{event.event_type}</td><td>{event.node ?? "-"}</td><td>{event.message ?? "-"}</td><td>{event.signal ?? "-"}</td><td>{event.network ?? "-"}</td><td>{event.description || event.faults.join(", ")}</td></tr>)}</tbody></table>{!visible.length && <p>Bis zum aktuellen Zeitzeiger liegen keine Fehlerereignisse vor.</p>}</div>;
}
