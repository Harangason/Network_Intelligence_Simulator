"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  cancelSimulation,
  createSimulation,
  createSimulationFaultProposals,
  listSimulationFaultProposals,
  reviewSimulationFaultProposal,
  saveSimulationScenario,
  type FaultProposal,
} from "@/lib/api";
import { topologyToConfig, type NetworkTopology } from "@/lib/topology";
import { createSimulationSnapshot, getWorkflow, setWorkflowContext, type SimulationSnapshot, type WorkflowState } from "@/lib/workflow-api";
import type { ModelSignalSeries, ModelSimulationTrace, RuntimeNetworkMetric, SimulationJob } from "@/lib/types";
import { SimulationResult } from "./simulation-result";
import { notifyWorkflowChanged } from "./workflow-header";
import { useWorkflowRefresh } from "@/lib/use-workflow-refresh";

type SimulationView = "network" | "signals" | "load" | "events";
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

export function ModelSimulationRunner() {
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [snapshot, setSnapshot] = useState<SimulationSnapshot | null>(null);
  const [job, setJob] = useState<SimulationJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState("GOLDEN");
  const [duration, setDuration] = useState(2);
  const [speed, setSpeed] = useState(1);
  const [seed, setSeed] = useState(42);
  const [formats, setFormats] = useState(["universal-jsonl", "universal-csv"]);
  const [faults, setFaults] = useState<ScenarioFault[]>([]);
  const [faultScope, setFaultScope] = useState<keyof typeof FAULT_TYPES>("SIGNAL");
  const [faultType, setFaultType] = useState<string>(FAULT_TYPES.SIGNAL[0]);
  const [faultTarget, setFaultTarget] = useState("");
  const [faultStart, setFaultStart] = useState(0.25);
  const [faultEnd, setFaultEnd] = useState(1.5);
  const [faultMagnitude, setFaultMagnitude] = useState(5);
  const [proposals, setProposals] = useState<FaultProposal[]>([]);
  const [proposalMagnitude, setProposalMagnitude] = useState<Record<string, number>>({});
  const [view, setView] = useState<SimulationView>("signals");
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);

  const loadWorkflow = useCallback(async () => {
    try {
      setWorkflow(await getWorkflow());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Workflow nicht verfügbar.");
    }
  }, []);
  useWorkflowRefresh(loadWorkflow);

  useEffect(() => {
    if (!workflow?.project_id) return;
    void listSimulationFaultProposals(workflow.project_id).then((response) => setProposals(response.items)).catch(() => undefined);
  }, [workflow?.project_id]);

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
  const simulationOutdated = workflow?.statuses.simulation === "OUTDATED";
  const running = Boolean(job && !["completed", "failed", "canceled"].includes(job.status));

  const handleJobChange = useCallback((nextJob: SimulationJob) => {
    setJob(nextJob);
    if (["completed", "failed", "canceled"].includes(nextJob.status)) {
      void getWorkflow().then(setWorkflow).catch(() => undefined);
      notifyWorkflowChanged();
    }
  }, []);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workflow || !valid) return;
    setBusy(true);
    setError("");
    setPlayhead(0);
    try {
      const topology = workflow.topology as NetworkTopology;
      const hasTopology = Array.isArray(topology.nodes) && topology.nodes.length >= 2 && Array.isArray(topology.edges) && topology.edges.length > 0;
      let config: Record<string, unknown> = hasTopology
        ? topologyToConfig(topology, formats).config
        : { name: "validated_workflow_simulation", industry: workflow.parameters.industry ?? "automotive", technology: workflow.parameters.technology ?? "can_fd", node_count: 2, formats };
      const scenarioMode = mode === "GOLDEN" ? "NORMAL" : mode;
      const scenario = {
        name: mode === "GOLDEN" ? "Golden / Ideal" : mode === "NORMAL" ? "Normalbetrieb" : mode === "STRESS" ? "Stresstest" : "Fehlerszenario",
        mode: scenarioMode,
        trace_type: mode,
        duration_s: duration,
        speed,
        seed,
        trace_formats: formats,
        faults,
      };
      const storedScenario = await saveSimulationScenario(workflow.project_id, scenario);
      config = { ...config, ...workflow.parameters, duration_s: duration, seed, formats, max_events: 250_000, scenario: { ...scenario, scenario_id: storedScenario.scenario_id } };
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
    setPlaying(false);
    setPlayhead(0);
    setJob(null);
    setSnapshot(null);
    setError("");
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
    const magnitude = proposalMagnitude[proposal.proposal_id];
    const reviewed = await reviewSimulationFaultProposal(
      workflow.project_id,
      proposal.proposal_id,
      action,
      action === "EDIT" && Number.isFinite(magnitude) ? { configuration: { ...proposal.configuration, magnitude } } : undefined,
    );
    setProposals((current) => current.map((item) => item.proposal_id === reviewed.proposal_id ? reviewed : item));
    if (action === "ACCEPT") {
      setFaults((current) => current.some((item) => item.proposal_id === proposal.proposal_id) ? current : [...current, {
        id: crypto.randomUUID(), scope: proposal.fault_scope, type: proposal.fault_type,
        target: proposal.target, start_s: Number(proposal.configuration.start_s ?? 0.25),
        end_s: Number(proposal.configuration.end_s ?? duration * 0.75),
        magnitude: Number(proposal.configuration.magnitude ?? 5), source: "ai", approved: true,
        proposal_id: proposal.proposal_id,
      }]);
      setMode("AI_GENERATED_FAULT");
    }
  }

  const modelTrace = job?.result?.model_simulation;
  const maximumTime = Number(modelTrace?.scenario.duration_s || duration);

  return (
    <section className="simulation-runner model-simulation-runner">
      {!valid && <div className="workflow-blocker error"><strong>Simulation blockiert</strong><span>Ein aktueller Preflight mit Status APPROVED oder WARNING ist erforderlich.</span><Link href="/studio/validation">Preflight öffnen</Link></div>}
      {simulationOutdated && <div className="workflow-blocker warning"><strong>Frühere Simulation ist OUTDATED</strong><span>{workflow?.stale_reasons.simulation}</span></div>}

      <form className="panel simulation-command-bar" onSubmit={start}>
        <label><span>Szenario</span><select value={mode} onChange={(event) => setMode(event.target.value)}><option value="GOLDEN">Golden / Ideal</option><option value="NORMAL">Normal</option><option value="USER_DEFINED_FAULT">Nutzerfehler</option><option value="AI_GENERATED_FAULT">Geprüfter KI-Fehler</option><option value="STRESS">Stresstest</option></select></label>
        <NumberInput label="Dauer" unit="s" value={duration} min={0.1} step={0.1} onChange={setDuration} />
        <NumberInput label="Geschwindigkeit" unit="x" value={speed} min={0.1} step={0.1} onChange={setSpeed} />
        <NumberInput label="Seed" value={seed} min={0} step={1} onChange={setSeed} />
        <fieldset className="trace-format-control"><legend>Trace-Formate</legend>{["universal-jsonl", "universal-csv"].map((format) => <label key={format}><input checked={formats.includes(format)} type="checkbox" onChange={(event) => setFormats((current) => event.target.checked ? [...new Set([...current, format])] : current.filter((item) => item !== format))} />{format.replace("universal-", "").toUpperCase()}</label>)}</fieldset>
        <div className="simulation-transport-controls">
          <button className="button primary" disabled={!valid || busy || Boolean(job)} type="submit">Start</button>
          <button className="button secondary" disabled={!job?.result?.model_simulation} onClick={() => setPlaying((current) => !current)} type="button">{playing ? "Pause" : "Weiter"}</button>
          <button className="button secondary" disabled={!running} onClick={() => void stop()} type="button">Stop</button>
          <button className="button secondary" disabled={!job} onClick={reset} type="button">Reset</button>
        </div>
      </form>

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

      <FaultProposalReview proposals={proposals.filter((proposal) => proposal.status !== "REJECTED" && proposal.status !== "SUPERSEDED")} magnitudes={proposalMagnitude} onMagnitude={(id, value) => setProposalMagnitude((current) => ({ ...current, [id]: value }))} onReview={reviewProposal} />
      {error && <div className="notice error">{error}</div>}

      <div className="simulation-view-tabs" role="tablist">{(["network", "signals", "load", "events"] as SimulationView[]).map((item) => <button className={view === item ? "active" : ""} key={item} onClick={() => setView(item)} role="tab" type="button">{{ network: "NETWORK / ECU", signals: "SIGNALS", load: "BUS LOAD", events: "EVENTS" }[item]}</button>)}</div>
      <section className="panel synchronized-simulation-view">
        <SimulationTimeline duration={maximumTime} playhead={playhead} playing={playing} onChange={setPlayhead} />
        {!modelTrace && <div className="simulation-empty-state"><strong>{job ? "Simulation wird verarbeitet" : "Noch kein Lauf gestartet"}</strong><span>Nach dem Start erscheinen Signalwerte, Buslast und Ereignisse auf derselben Zeitachse.</span></div>}
        {modelTrace && view === "network" && <NetworkView job={job} trace={modelTrace} playhead={playhead} />}
        {modelTrace && view === "signals" && <SignalsView trace={modelTrace} playhead={playhead} />}
        {modelTrace && view === "load" && <BusLoadView metrics={job?.result?.runtime_metrics?.networks ?? []} trace={modelTrace} playhead={playhead} />}
        {modelTrace && view === "events" && <EventsView trace={modelTrace} playhead={playhead} />}
      </section>

      {job && (
        <SimulationResult
          action={<Link className="button primary result-heading-action" href={`/trace-analysis?job=${job.id}&view=signals`}>Trace direkt analysieren</Link>}
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

function FaultProposalReview({ proposals, magnitudes, onMagnitude, onReview }: { proposals: FaultProposal[]; magnitudes: Record<string, number>; onMagnitude: (id: string, value: number) => void; onReview: (proposal: FaultProposal, action: "ACCEPT" | "EDIT" | "REJECT") => Promise<void> }) {
  if (!proposals.length) return null;
  return <section className="panel fault-proposal-review"><div className="compact-heading"><div><p className="eyebrow">Review gate</p><h2>KI-Fehlervorschläge</h2></div><span>Keine automatische Aktivierung</span></div><div className="fault-proposal-grid">{proposals.map((proposal) => <article key={proposal.proposal_id} className={proposal.status === "APPROVED" ? "approved" : ""}><div><span>{proposal.fault_scope}</span><strong>{proposal.title}</strong><p>{proposal.rationale}</p></div><label><span>Magnitude</span><input type="number" value={magnitudes[proposal.proposal_id] ?? Number(proposal.configuration.magnitude ?? 5)} onChange={(event) => onMagnitude(proposal.proposal_id, Number(event.target.value))} /></label><div className="proposal-actions"><button className="button primary" disabled={proposal.status === "APPROVED"} onClick={() => void onReview(proposal, "ACCEPT")} type="button">Übernehmen</button><button className="button secondary" onClick={() => void onReview(proposal, "EDIT")} type="button">Ändern</button><button className="button secondary" onClick={() => void onReview(proposal, "REJECT")} type="button">Ablehnen</button></div></article>)}</div></section>;
}

function NetworkView({ job, trace, playhead }: { job: SimulationJob | null; trace: ModelSimulationTrace; playhead: number }) {
  const networks = job?.result?.runtime_metrics?.networks ?? [];
  const routes = job?.result?.runtime_metrics?.routes ?? [];
  const visibleFrames = (trace.frames ?? []).filter((frame) => frame.time_s <= playhead + 0.000001);
  const activeRoutes = new Set(visibleFrames.map((frame) => frame.route_id));
  const delivered = visibleFrames.filter((frame) => frame.status !== "dropped").length;
  const currentLoads = networks.map((network) => (trace.bus_load ?? []).filter((point) => point.network_id === network.network_id && point.time_s <= playhead + 0.000001).at(-1)?.load_percent ?? 0);
  const currentLoad = currentLoads.length ? Math.max(...currentLoads) : 0;
  return <div className="network-runtime-view"><div className="network-runtime-nodes"><article><span>AKTIVE PFADE</span><strong>{activeRoutes.size}</strong><small>bis {playhead.toFixed(3)} s</small></article><div className="runtime-link-line" /><article className="gateway-runtime-node"><span>SIMULATED LOAD</span><strong>{currentLoad.toFixed(1)} %</strong><small>{visibleFrames.length} Frames · {networks.length} Netze</small></article><div className="runtime-link-line" /><article><span>ZUGESTELLT</span><strong>{delivered}</strong><small>{visibleFrames.length - delivered} verworfen</small></article></div><div className="runtime-route-list">{routes.slice(0, 12).map((route) => <div key={route.route_id}><strong>{route.route_name}</strong><span>{route.configured_cycle_ms} ms</span><span>{visibleFrames.filter((frame) => frame.route_id === route.route_id).length} / {route.event_count} Frames</span><b className={route.status === "PASS" ? "pass" : "fail"}>{route.status}</b></div>)}</div></div>;
}

function SignalsView({ trace, playhead }: { trace: ModelSimulationTrace; playhead: number }) {
  const [selected, setSelected] = useState(() => trace.signals.map((series) => series.signal_id));
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState(0);
  const windowDuration = trace.scenario.duration_s / zoom;
  const windowStart = Math.min(Math.max(0, pan), Math.max(0, trace.scenario.duration_s - windowDuration));
  const windowEnd = windowStart + windowDuration;
  return <div className="signal-plot-workbench"><div className="signal-plot-controls"><div className="signal-selector">{trace.signals.map((series) => <label key={series.signal_id}><input checked={selected.includes(series.signal_id)} type="checkbox" onChange={(event) => setSelected((current) => event.target.checked ? [...current, series.signal_id] : current.filter((id) => id !== series.signal_id))} />{series.signal}</label>)}</div><label><span>Zoom {zoom.toFixed(1)}x</span><input max="8" min="1" step="0.5" type="range" value={zoom} onChange={(event) => { setZoom(Number(event.target.value)); setPan(0); }} /></label><label><span>Pan</span><input disabled={zoom === 1} max={Math.max(0, trace.scenario.duration_s - windowDuration)} min="0" step="0.01" type="range" value={windowStart} onChange={(event) => setPan(Number(event.target.value))} /></label></div><div className="signal-lanes">{trace.signals.filter((series) => selected.includes(series.signal_id)).map((series) => <SignalLane key={series.signal_id} series={series} windowStart={windowStart} windowEnd={windowEnd} playhead={playhead} />)}{!trace.signals.length && <div className="simulation-empty-state"><strong>Keine Signalzuordnung gefunden</strong><span>Die Frames wurden simuliert, aber kein Engineering-Signal ist dem Kommunikationspfad zugeordnet.</span></div>}{trace.signals.length > 0 && selected.length === 0 && <div className="simulation-empty-state"><strong>Keine Signale ausgewählt</strong><span>Wähle oben mindestens eine Signallane.</span></div>}</div></div>;
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
  const current = [...series.points].reverse().find((item) => item.time_s <= playhead) ?? series.points[0];
  const playheadX = (playhead - windowStart) / Math.max(windowEnd - windowStart, 0.001) * width;
  return <article className="signal-lane"><header><div><strong>{series.signal}</strong><span>{series.behavior_type} · {modelLabel(series.model_label)}</span></div><b>{current?.value ?? "-"} {series.unit}</b></header><div className="signal-chart"><svg aria-label={`${series.signal} Signalverlauf`} preserveAspectRatio="none" viewBox={`0 0 ${width} ${height}`}><line className="signal-limit" x1="0" x2={width} y1="1" y2="1" /><line className="signal-limit" x1="0" x2={width} y1={height - 1} y2={height - 1} /><polyline className="signal-golden-line" points={golden} /><polyline className="signal-actual-line" points={actual} />{faultPoints.map((item, index) => { const [x, y] = point(item.time_s, item.value).split(","); return <circle className="signal-fault-marker" cx={x} cy={y} key={`${item.time_s}-${index}`} r="4" />; })}{playheadX >= 0 && playheadX <= width && <line className="signal-playhead" x1={playheadX} x2={playheadX} y1="0" y2={height} />}</svg><span className="limit max">{series.maximum}</span><span className="limit min">{series.minimum}</span></div></article>;
}

function modelLabel(label: ModelSignalSeries["model_label"]) {
  return { PHYSICS_BASED: "Physikbasiert", RULE_BASED: "Regelbasiert", EMPIRICAL: "Empirisch", SYNTHETIC: "Synthetisch", GENERIC_ESTIMATE: "Generische Schätzung" }[label];
}

function BusLoadView({ metrics, trace, playhead }: { metrics: RuntimeNetworkMetric[]; trace: ModelSimulationTrace; playhead: number }) {
  return <div className="bus-load-grid"><div className="bus-load-source"><strong>SIMULATED LOAD</strong><span>Aus tatsächlichen Frames, Protokolloverhead, Zeitstempeln und Bitrate.</span><Link href="/studio/capacity">CALCULATED LOAD im Capacity View</Link></div>{metrics.map((network) => {
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
    return <article key={network.network_id}><header><div><span>{network.technology}</span><strong>{network.network_id}</strong></div><b className={`load-status ${status.toLowerCase()}`}>{status} · t = {playhead.toFixed(3)} s</b></header>{[["Aktuell 50 ms", current], ["Ø bis Zeitzeiger", averageToNow], ["Peak bis Zeitzeiger", peakToNow], ["Burst 100 ms", burstToNow], ["Reserve", reserve]].map(([label, value]) => <div className="load-meter" key={String(label)}><span>{label}</span><div><i style={{ width: `${Math.min(100, Number(value))}%` }} /></div><strong>{Number(value).toFixed(2)} %</strong></div>)}</article>;
  })}{!metrics.length && <div className="simulation-empty-state"><strong>Keine Laufzeitlast verfügbar</strong></div>}</div>;
}

function EventsView({ trace, playhead }: { trace: ModelSimulationTrace; playhead: number }) {
  const visible = trace.events.filter((event) => event.time_s <= playhead + 0.000001);
  return <div className="simulation-event-table"><table><thead><tr><th>Zeit</th><th>Severity</th><th>Event Type</th><th>Node</th><th>Message</th><th>Signal</th><th>Network</th><th>Beschreibung</th></tr></thead><tbody>{visible.map((event, index) => <tr key={`${event.time_s}-${event.target}-${index}`}><td>{Number(event.time_s).toFixed(4)} s</td><td>{event.severity}</td><td>{event.event_type}</td><td>{event.node ?? "-"}</td><td>{event.message ?? "-"}</td><td>{event.signal ?? "-"}</td><td>{event.network ?? "-"}</td><td>{event.description || event.faults.join(", ")}</td></tr>)}</tbody></table>{!visible.length && <p>Bis zum aktuellen Zeitzeiger liegen keine Fehlerereignisse vor.</p>}</div>;
}
