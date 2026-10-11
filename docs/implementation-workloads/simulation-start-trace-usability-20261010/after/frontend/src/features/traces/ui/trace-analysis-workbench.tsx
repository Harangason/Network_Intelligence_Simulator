"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { listSimulations } from "@/shared/api/api";
import type { SimulationJob } from "@/shared/api/types";
import { readActiveProjectId, withProjectParam } from "@/features/settings/lib/user-settings";
import { engineeringContextHref } from "@/features/agent/lib/assistant-context";
import { eventFromRecord, traceEventFindings, traceMessagePresentation, traceSignalInventory, MAX_IMPORT_BYTES, type TraceEvent } from "@/features/traces/lib/trace-records";
import { getWorkflowSimulationSnapshot, type SimulationSnapshot } from "@/features/workflow/lib/workflow-api";
import { simulationPage } from "@/features/simulation/lib/simulation-pagination";
import { SimulationPageControls } from "@/features/simulation/ui/simulation-page-controls";
import { ReasoningPanel } from "../../agent/ui/reasoning-panel";
import { queueEngineeringAgentTask } from '@/features/agent/lib/agent-task-events';
import { sequenceModelForEventIds, type SequenceDiagramModel } from "@/features/simulation/lib/e2e-sequence";
import { E2ESequenceDiagram } from "../../simulation/ui/e2e-sequence-diagram";

import { automaticProfile, availableColumns, displayTraceValue, TRACE_PROFILES, type TraceProfile } from "@/features/traces/lib/trace-profiles";

type TraceView = "session" | "messages" | "sequence" | "signals" | "trace" | "findings" | "root-cause" | "charts";
const ACCEPTED = ".csv,.json,.jsonl,.asc,.blf,.log,.trc,.pcap,.pcapng,.mdf,.mf4";
const VIEW_META: Record<TraceView, { eyebrow: string; title: string; note: string }> = {
  session: {
    eyebrow: "Schritt 1",
    title: "Session / Daten laden",
    note: "Trace-Dateien laden oder erzeugte Simulationsartefakte als Analyseprojektion übernehmen.",
  },
  messages: {
    eyebrow: "Schritt 2",
    title: "Botschaften analysieren",
    note: "Message IDs, Sender, Receiver, Payloads und fehlende Decodierungen in der aktuellen Auswahl prüfen.",
  },
  sequence: {
    eyebrow: "Schritt 3",
    title: "Sequenz verfolgen",
    note: "Zeitlich geordnete Kommunikation zwischen Source, Destination und Buskontext untersuchen.",
  },
  signals: {
    eyebrow: "Schritt 4",
    title: "Signale prüfen",
    note: "Decodierte Signalwerte und Raw-Byte-Fallbacks getrennt betrachten.",
  },
  trace: {
    eyebrow: "Schritt 5",
    title: "Trace untersuchen",
    note: "Eventliste und Zeitkontext für die Ursachenanalyse zusammenführen.",
  },
  findings: {
    eyebrow: "Schritt 6",
    title: "Findings / Gaps bewerten",
    note: "Auffälligkeiten, fehlende Decodierungen und fehlende Kontextbezüge sammeln.",
  },
  "root-cause": {
    eyebrow: "Schritt 7",
    title: "Ursache eingrenzen",
    note: "Erste Anomalie und ihren technischen Zeitkontext untersuchen; zeitliche Nachbarschaft allein beweist keine Ursache.",
  },
  charts: {
    eyebrow: "Schritt 8",
    title: "Diagramme und Fehlerverlauf",
    note: "Verteilungen und zeitliche Häufungen im geladenen Ausschnitt untersuchen und die zugehörigen Ereignisse, Befunde und Ursachenbelege öffnen.",
  },
};


function buildFindings(events: TraceEvent[]) {
  const findings = [];
  if (!events.length) findings.push({ severity: "info", timestamp: "-", category: "Session", object: "Trace Session", message: "-", signal: "-", finding: "No Trace Session", context: "Keine Trace-Daten geladen.", source: "-", status: "open" });
  for (const event of events) {
    for (const finding of traceEventFindings(event)) findings.push({ severity: "warning", timestamp: event.timeKnown ? `${event.timestamp}s` : "unbekannt", category: "Analyzer Finding", object: event.id, message: event.message, signal: event.signal, finding, context: `${event.source} -> ${event.destination}`, source: event.technology, status: "open" });
  }
  return findings;
}

export function TraceAnalysisWorkbench() {
  const router = useRouter();
  const search = useSearchParams();
  const inputRef = useRef<HTMLInputElement>(null);
  const autoLoadedJobRef = useRef<string | null>(null);
  const [jobs, setJobs] = useState<SimulationJob[]>([]);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [view, setView] = useState<TraceView>("session");
  const [query, setQuery] = useState("");
  const [sourceName, setSourceName] = useState("Keine Trace Session");
  const [error, setError] = useState("");
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [sourceFormat, setSourceFormat] = useState("-");
  const [traceJob, setTraceJob] = useState<string | null>(null);
  const [currentCursor, setCurrentCursor] = useState(0);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [timeStart, setTimeStart] = useState(0);
  const [timeEnd, setTimeEnd] = useState(1e15);
  const [selectedEvent, setSelectedEvent] = useState<TraceEvent | null>(null);
  const [sessionDetailsOpen, setSessionDetailsOpen] = useState(false);
  const loadGeneration = useRef(0);
  const chartSnapshot = useRef<{ key: string; request: Promise<SimulationSnapshot> } | null>(null);
  const [signalChannels, setSignalChannels] = useState<string[]>([]);
  const [sequenceModel, setSequenceModel] = useState<SequenceDiagramModel | null>(null);
  const [modelFreshness, setModelFreshness] = useState<{ status: string; reason?: string | null } | null>(null);
  const [chartConfiguration, setChartConfiguration] = useState<SimulationSnapshot["configuration"]>(undefined);
  const [chartContextNote, setChartContextNote] = useState("Kein eingefrorener ECU-Modellbezug geladen.");

  useEffect(() => { void listSimulations().then(setJobs).catch(() => setJobs([])); }, []);
  useEffect(() => {
    const requested = search.get("view");
    if (requested && Object.hasOwn(VIEW_META, requested)) setView(requested as TraceView);
  }, [search]);
  useEffect(() => {
    const requestedJob = search.get("import") ? `import:${search.get("import")}` : search.get("job");
    const rawFocus = search.get("focus_s");
    const focus = rawFocus === null ? NaN : Number(rawFocus);
    const key = `${requestedJob}:${rawFocus ?? ''}`;
    if (!requestedJob || autoLoadedJobRef.current === key) return;
    autoLoadedJobRef.current = key;
    const savedStart = Number(search.get("start_s") ?? 0), savedEnd = Number(search.get("end_s") ?? 1e15);
    const savedWindow = search.has("event") && Number.isFinite(savedStart) && Number.isFinite(savedEnd) && savedStart >= 0 && savedEnd >= savedStart;
    const range = Number.isFinite(focus) && focus >= 0 ? { start: savedWindow ? savedStart : Math.max(0, focus - .1), end: savedWindow ? savedEnd : focus + .1, focus } : undefined;
    if (range) { setTimeStart(range.start); setTimeEnd(range.end); setQuery(search.get("q") ?? ""); }
    const cursor = Number(search.get("cursor") ?? 0);
    void loadWindow(requestedJob, Number.isSafeInteger(cursor) && cursor >= 0 ? cursor : 0, false, range);
  }, [search]);


  async function loadWindow(jobId: string, cursor = 0, openDefaultView = false, range?: { start: number; end: number; focus: number }) {
    const generation = ++loadGeneration.current;
    const projectId = readActiveProjectId();
    setLoading(true);
    try {
      const parameters = new URLSearchParams({ cursor: String(cursor), limit: "2000", start_s: String(range?.start ?? timeStart), end_s: String(range?.end ?? timeEnd), q: range ? search.get("q") ?? "" : query });
      const endpoint = jobId.startsWith("import:") ? `/api/trace-import/${encodeURIComponent(jobId.slice(7))}` : `/api/simulations/${encodeURIComponent(jobId)}/trace-window`;
      const response = await fetch(`${endpoint}?${parameters}`, {
        headers: { "X-Project-ID": projectId }, cache: "no-store", signal: AbortSignal.timeout(15000),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? `Trace-Abruf fehlgeschlagen (${response.status}).`);
      if (generation !== loadGeneration.current || readActiveProjectId() !== projectId) return;
      const loaded = (result.events as Record<string, unknown>[]).map(eventFromRecord);
      setSequenceModel(result.sequence_model ?? null);
      setModelFreshness(result.model_freshness ?? (jobId.startsWith("import:") ? null : { status: "UNVERIFIED" }));
      setEvents(loaded); setCurrentCursor(cursor);
      setChartConfiguration(undefined);
      const snapshotId = result.model_freshness?.snapshot_id;
      setChartContextNote(snapshotId ? "Eingefrorener ECU-Modellbezug wird geladen …" : "Kein zugehöriger Modell-Snapshot: ECU-Typen und Hardware-IDs sind nicht nachgewiesen.");
      if (typeof snapshotId === "string" && snapshotId) {
        const key = `${projectId}:${snapshotId}`;
        const snapshotRequest = chartSnapshot.current?.key === key ? chartSnapshot.current.request : getWorkflowSimulationSnapshot(snapshotId, projectId);
        chartSnapshot.current = { key, request: snapshotRequest };
        void snapshotRequest.then(snapshot => {
          if (generation !== loadGeneration.current || readActiveProjectId() !== projectId) return;
          if (snapshot.job_id !== jobId) { setChartContextNote("Snapshot und Trace-Lauf stimmen nicht überein; ECU-Zuordnung bleibt ungeprüft."); return; }
          setChartConfiguration(snapshot.configuration);
          setChartContextNote(snapshot.configuration ? `ECU-Modellbezug: eingefrorener Snapshot ${snapshot.id.slice(0, 8)}.` : "Snapshot enthält keine eingefrorene Hardware-Konfiguration.");
        }).catch(() => {
          if (chartSnapshot.current?.key === key) chartSnapshot.current = null;
          if (generation === loadGeneration.current && readActiveProjectId() === projectId) setChartContextNote("Der eingefrorene ECU-Modellbezug konnte nicht geladen werden; die Trace-Ereignisse bleiben verfügbar.");
        });
      }
      setSelectedEvent(search.get("event") ? loaded.find(item => item.id === search.get("event")) ?? null : range && loaded.length ? loaded.reduce((nearest, item) => Math.abs(item.timestamp-range.focus) < Math.abs(nearest.timestamp-range.focus) ? item : nearest) : null);
      setTraceJob(jobId); setNextCursor(result.next_cursor); setSourceName(`Simulation ${jobId} · Trace-Fenster`);
      setImportWarnings(result.warnings ?? []); setSourceFormat(result.format ?? "JSONL · Simulation");
      if (result.filename) setSourceName(result.filename);
      setError("");
      if (openDefaultView) { autoLoadedJobRef.current = `${jobId}:${search.get("focus_s") ?? ''}`; openMessagesView(jobId); }
    } catch (caught) {
      if (generation === loadGeneration.current) setError(caught instanceof Error ? caught.message : "Trace-Fenster konnte nicht geladen werden.");
    } finally { if (generation === loadGeneration.current) setLoading(false); }
  }

  async function loadFiles() {
    const files = inputRef.current?.files;
    if (!files?.length) return;
    if (files[0].size > MAX_IMPORT_BYTES) { setError("Lokaler Import: maximal 500 MiB. Simulations-Traces über ihre serverseitigen Fenster öffnen."); return; }
    const generation = ++loadGeneration.current;
    setLoading(true);
    try {
      const file = files[0];
      const response = await fetch(`/api/trace-import?${new URLSearchParams({ filename: file.name })}`, {
        method: "POST", body: file, headers: { "Content-Type": "application/octet-stream", "X-Project-ID": readActiveProjectId() },
        signal: AbortSignal.timeout(600000),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? `Trace-Import fehlgeschlagen (${response.status}).`);
      if (generation !== loadGeneration.current) return;
      const imported = (result.events as Record<string, unknown>[]).map(eventFromRecord);
      setEvents(imported); setCurrentCursor(0);
      setModelFreshness(null);
      setSequenceModel(result.sequence_model ?? null);
      setChartConfiguration(undefined); setChartContextNote("Import ohne Modell-Snapshot: ECU-Typen werden nicht aus Teilnehmernamen erraten.");
      setImportWarnings(result.warnings ?? []); setSourceFormat(String(result.format).toUpperCase());
      setTimeStart(0); setTimeEnd(1e15); setQuery("");
      setSelectedEvent(null);
      setTraceJob(`import:${result.session_id}`); setNextCursor(result.next_cursor);
      setSourceName(files[0].name);
      openMessagesView(`import:${result.session_id}`);
      setError("");
    } catch (caught) { if (generation === loadGeneration.current) setError(caught instanceof Error ? caught.message : 'Trace-Import fehlgeschlagen.'); }
    finally { if (generation === loadGeneration.current) { setLoading(false); if (inputRef.current) inputRef.current.value = ""; } }
  }

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return events.map(event => traceMessagePresentation(event, chartConfiguration)).filter((event) => (!event.timeKnown || event.timestamp >= timeStart && event.timestamp <= timeEnd)
      && (!needle || JSON.stringify(event).toLowerCase().includes(needle)));
  }, [events, chartConfiguration, query, timeStart, timeEnd]);
  const findings = useMemo(() => buildFindings(filtered), [filtered]);
  // Use the complete loaded window, never the filtered subset, as the slider domain.
  const timeline = useMemo(() => {
    const times = events.filter(event => event.timeKnown && Number.isFinite(event.timestamp)).map(event => event.timestamp);
    return times.length ? { min: Math.min(...times), max: Math.max(...times) } : null;
  }, [events]);
  const timelineSpan = timeline ? timeline.max - timeline.min : 0;
  const timelineStart = timeline ? Math.max(timeline.min, Math.min(timeStart, timeline.max)) : 0;
  const timelineEnd = timeline ? Math.max(timelineStart, Math.min(timeEnd, timeline.max)) : 0;
  const startPercent = timelineSpan > 0 ? (timelineStart - timeline!.min) / timelineSpan * 100 : 0;
  const endPercent = timelineSpan > 0 ? (timelineEnd - timeline!.min) / timelineSpan * 100 : 100;
  const channels = new Set(filtered.map((event) => event.technology)).size;
  const messages = new Set(filtered.map(event => JSON.stringify(event.original.message_ids ?? event.original.message_id ?? event.original.frame_id ?? event.original.message ?? event.original.route_id ?? event.message))).size;
  const signals = new Set(filtered.flatMap(event => event.signals.map(signal => signal.id))).size;
  const timed = filtered.filter(event => event.timeKnown);
  const start = timed.length ? Math.min(...timed.map(event => event.timestamp)) : 0;
  const end = timed.length ? Math.max(...timed.map(event => event.timestamp)) : 0;
  const viewMeta = VIEW_META[view];
  const viewStatus = view === "session"
    ? events.length ? "SESSION LOADED" : "NO TRACE SESSION"
    : view === "messages"
      ? messages ? `${messages} MESSAGES` : "NO MESSAGES"
      : view === "sequence"
        ? filtered.length ? `${filtered.length} EVENTS` : "NO SEQUENCE"
        : view === "signals"
          ? signals ? `${signals} SIGNALS` : "NO DECODED SIGNALS"
          : view === "trace"
            ? filtered.length ? "TRACE READY" : "NO TRACE"
            : view === "findings"
              ? findings.length ? `${findings.length} FINDINGS` : "NO FINDINGS"
              : view === "charts" ? `${filtered.length} EVENTS` : events.some(event => traceEventFindings(event).length) ? "CAUSE CANDIDATE" : "NO ANOMALY";

  function selectEvent(event: TraceEvent, targetView?: TraceView) {
    setSelectedEvent(event);
    const parameters = new URLSearchParams(search.toString());
    parameters.set("event", event.id);
    parameters.set("cursor", String(currentCursor));
    parameters.set("start_s", String(timeStart)); parameters.set("end_s", String(timeEnd));
    parameters.set("q", query);
    if (event.timeKnown) parameters.set("focus_s", String(event.timestamp));
    else parameters.delete("focus_s");
    if (targetView) { parameters.set("view", targetView); setView(targetView); }
    autoLoadedJobRef.current = `${traceJob}:${parameters.get("focus_s") ?? ''}`;
    router.replace(withProjectParam(`/trace-analysis?${parameters}`), { scroll: false });
  }

  function clearEventSelection() {
    setSelectedEvent(null);
    const parameters = new URLSearchParams(search.toString());
    parameters.delete("event");
    parameters.delete("focus_s");
    router.replace(withProjectParam(`/trace-analysis?${parameters.toString()}`), { scroll: false });
  }

  function openMessagesView(jobId?: string) {
    setView("messages");
    const parameters = new URLSearchParams(search.toString());
    parameters.set("view", "messages");
    if (jobId) autoLoadedJobRef.current = `${jobId}:`;
    parameters.delete("event"); parameters.delete("focus_s"); parameters.delete("import"); parameters.delete("cursor");
    if (jobId?.startsWith("import:")) { parameters.set("import", jobId.slice(7)); parameters.delete("job"); }
    else if (jobId) parameters.set("job", jobId);
    else { parameters.delete("job"); autoLoadedJobRef.current = null; }
    router.replace(withProjectParam(`/trace-analysis?${parameters.toString()}`));
  }

  return (
    <section className="simulation-runner trace-analysis-workbench">
      <div className={`simulation-layout trace-analysis-layout${sessionDetailsOpen ? "" : " context-collapsed"}`}>
        <div className="trace-main-column">
          <div className="panel simulation-control-panel trace-control-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">{viewMeta.eyebrow}</p><h2>{viewMeta.title}</h2></div>
              <div className="trace-panel-actions">
                <span className={`snapshot-state ${events.length || view === "findings" ? "ready" : "blocked"}`}>{viewStatus}</span>
                <button aria-expanded={sessionDetailsOpen} className="button secondary tiny" onClick={() => setSessionDetailsOpen((current) => !current)} type="button">
                  {sessionDetailsOpen ? "Sessiondetails ausblenden" : "Sessiondetails anzeigen"}
                </button>
              </div>
            </div>
            {view === "session" ? <div className="trace-actions">
              <input ref={inputRef} type="file" accept={ACCEPTED} onChange={loadFiles} className="hidden-file" />
              <button className="button primary" type="button" onClick={() => inputRef.current?.click()}>Load Trace</button>
              <button className="button secondary" type="button" onClick={() => inputRef.current?.click()}>Change Session</button>
              <button className="button secondary" type="button" onClick={() => { loadGeneration.current += 1; autoLoadedJobRef.current = null; setLoading(false); setEvents([]); setSelectedEvent(null); setSignalChannels([]); setTraceJob(null); setNextCursor(null); setChartConfiguration(undefined); setChartContextNote("Kein eingefrorener ECU-Modellbezug geladen."); setError(""); setSourceName("Keine Trace Session"); setSourceFormat("-"); setImportWarnings([]); setView("session"); router.replace(withProjectParam("/trace-analysis?view=session")); }}>Close Session</button>
            </div> : null}
            <div className="trace-filter-controls">
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Globale Filter: ID, Quelle, Ziel, Payload, Finding ..." />
              <div className="trace-time-row">
                <label>Von (s)<input type="number" min="0" max={timeEnd === 1e15 ? undefined : timeEnd} step="any" value={timeStart} onChange={event => {
                  const value = event.target.valueAsNumber;
                  if (Number.isFinite(value)) setTimeStart(Math.max(0, Math.min(value, timeEnd)));
                }} /></label>
                <label>Bis (s)<input type="number" min={timeStart} step="any" value={timeEnd === 1e15 ? "" : timeEnd} placeholder="Ende" onChange={event => {
                  if (!event.target.value) { setTimeEnd(1e15); return; }
                  const value = event.target.valueAsNumber;
                  if (Number.isFinite(value)) setTimeEnd(Math.max(timeStart, value));
                }} /></label>
              </div>
              <div className="trace-time-slider" role="group" aria-label="Zeitraum auf der Timeline" aria-describedby="trace-timeline-note">
                <div className="trace-time-track"><div className="trace-time-selection" style={{ left: `${startPercent}%`, width: `${endPercent - startPercent}%` }} /></div>
                <input type="range" aria-label="Zeitraum Anfang" min={timeline?.min ?? 0} max={timeline?.max ?? 1} step={timelineSpan > 0 ? timelineSpan / 10000 : 1} value={timelineStart} disabled={!timelineSpan}
                  aria-valuetext={`${timelineStart} Sekunden`} onChange={event => { setTimeStart(Math.min(Number(event.target.value), timelineEnd)); setTimeEnd(timelineEnd); }} />
                <input type="range" aria-label="Zeitraum Ende" min={timeline?.min ?? 0} max={timeline?.max ?? 1} step={timelineSpan > 0 ? timelineSpan / 10000 : 1} value={timelineEnd} disabled={!timelineSpan}
                  aria-valuetext={`${timelineEnd} Sekunden`} onChange={event => { setTimeEnd(Math.max(Number(event.target.value), timelineStart)); setTimeStart(timelineStart); }} />
              </div>
              <div className="trace-time-scale"><span>{timeline ? `${timeline.min.toFixed(6)} s` : '—'}</span><span>{timeline ? `${timeline.max.toFixed(6)} s` : '—'}</span></div>
              <small id="trace-timeline-note">{timelineSpan > 0 ? `${traceJob ? 'Timeline des geladenen Trace-Fensters' : 'Timeline der geladenen Session'} · beide Griffe auch mit den Pfeiltasten verschiebbar.` : 'Für die Timeline werden mindestens zwei unterschiedliche Zeitpunkte benötigt.'}</small>
              {traceJob && <div className="trace-actions"><button className="button secondary tiny" disabled={loading} type="button" onClick={() => void loadWindow(traceJob)}>Zeitfenster laden</button><button className="button secondary tiny" disabled={loading || nextCursor === null} type="button" onClick={() => void loadWindow(traceJob, nextCursor ?? 0)}>Nächstes Fenster</button></div>}
            </div>
            <p>{loading ? "Trace-Fenster wird geladen …" : `${events.length} Ereignisse im Speicher · gemeinsames Zeitfenster für alle Ansichten`}</p>
            {selectedEvent && <TraceContext event={traceMessagePresentation(selectedEvent, chartConfiguration)} />}
            {error && <div className="notice error" role="alert">{error}</div>}
            {modelFreshness?.status === "OUTDATED" && <div className="notice" role="status"><strong>Trace-Modellbezug ist OUTDATED.</strong> Historische Ereignisse bleiben lesbar; sie belegen nicht den aktuellen Modellstand. {modelFreshness.reason}</div>}
            {modelFreshness?.status === "UNVERIFIED" && <div className="notice" role="status">Der Modellbezug dieses Traces ist nicht nachgewiesen. {modelFreshness.reason}</div>}
            {importWarnings.map((warning, index) => <div className="notice" role="status" key={index}>{warning}</div>)}
            <p className="trace-view-note">{viewMeta.note}</p>
            <p className="trace-governance-note">IMPORT {"->"} ANALYSIS PROJECTION. Keine automatischen Core-, Evidence- oder TraceLink-Writes.</p>
          </div>
          {view === "session" && <div className="panel trace-table"><h3>Import Sources</h3><p>Universeller Trace-Import: {ACCEPTED}. Binärformate werden anhand ihrer Dateisignatur erkannt. Vorschau bis 500 MiB und 2000 Ereignisse. ASC/BLF: CAN und CAN FD; PCAP/PCAPNG: Rohpakete; MDF/MF4: skalare Messkanäle. PCAPNG: eine Schnittstelle pro Datei. Rohbytes benötigen für Signalwerte eine passende Decoder-Datenbank.</p>{jobs.filter(job => job.status === 'completed' && !job.validate_only).slice(0, 50).map(job => <button className="artifact" key={job.id} type="button" disabled={loading} onClick={() => void loadWindow(job.id, 0, true)}><strong>Simulation {job.id}</strong><small>Universellen Trace laden · {job.created_at}</small></button>)}{!jobs.some(job => job.status === 'completed' && !job.validate_only) && <p>Keine abgeschlossenen Simulationsläufe in diesem Projekt verfügbar. Lokale Trace-Dateien können über „Load Trace“ geöffnet werden.</p>}</div>}
          {view === "messages" && <TraceTable sessionEvents={events} events={filtered} selected={selectedEvent} onSelect={selectEvent} />}
          {view === "sequence" && <SequenceView events={filtered} model={sequenceModel} selected={selectedEvent} onSelect={selectEvent} onClearSelection={clearEventSelection} />}
          {view === "signals" && <SignalView events={filtered} selected={selectedEvent} onSelect={selectEvent} channels={signalChannels} onChannels={setSignalChannels} simulationSource={Boolean(traceJob && !traceJob.startsWith('import:'))} />}
          {view === "trace" && <TraceTable sessionEvents={events} events={filtered} selected={selectedEvent} onSelect={selectEvent} compact />}
          {view === "findings" && <FindingsTable key={selectedEvent?.id ?? "all"} focusId={selectedEvent?.id} findings={findings} jobId={traceJob} onContext={finding => { const event = events.find(item => item.id === finding.object); if (event) selectEvent(event, 'trace'); }} />}
          {view === "root-cause" && <ReasoningPanel key={`${readActiveProjectId()}:${traceJob}`} project={readActiveProjectId()} jobId={traceJob?.startsWith("import:") ? null : traceJob} jobs={jobs} start={timeStart} end={timeEnd} focus={selectedEvent?.timeKnown ? selectedEvent.timestamp : undefined} />}
          {view === "charts" && <TraceCharts key={`${traceJob}:${currentCursor}:${timeStart}:${timeEnd}:${query}`} events={filtered} loadedCount={events.length} configuration={chartConfiguration} contextNote={chartContextNote}
            simulationSource={!!traceJob && !traceJob.startsWith("import:")} hasMore={nextCursor !== null} selected={selectedEvent} onSelect={selectEvent} onOpen={selectEvent} />}
        </div>
        {sessionDetailsOpen && <aside className="side-column trace-session-details">
          <div className="panel snapshot-summary trace-summary-panel">
            <p className="eyebrow">Session Header</p>
            <h2>Aktueller Stand</h2>
            <dl className="overview-list">
              {[["Trace Session Name", sourceName], ["Source File", sourceName], ["Format", sourceFormat], ["Start Time", timed.length ? `${start}s` : "unbekannt"], ["End Time", timed.length ? `${end}s` : "unbekannt"], ["Duration", timed.length ? `${Math.max(0, end - start).toFixed(3)}s` : "unbekannt"], ["Channels", channels], ["Detected Messages", messages], ["Detected Signals", signals], ["Findings", findings.length], ["Decode Status", signals ? "partial/decoded" : "missing"]].map(([label, value]) => <div key={String(label)}><dt>{label}</dt><dd>{value}</dd></div>)}
            </dl>
          </div>
        </aside>}
      </div>
    </section>
  );
}

type SelectionProps = { selected: TraceEvent | null; onSelect: (event: TraceEvent) => void; onClearSelection?: () => void };

type TraceChartGroup = { id: string; label: string; events: TraceEvent[] };
type TraceTimeBucket = { start: number; end: number; events: TraceEvent[]; findings: TraceEvent[] };
const TRACE_CHART_COLORS = ["var(--accent)", "var(--danger)", "var(--warning)", "#6589b7", "#946ab6", "#548b83"];

function traceStatusColor(status: string, index: number): string {
  const value = status.trim().toLowerCase();
  if (["dropped", "corrupted", "error", "failed", "timeout", "rejected"].includes(value)) return "var(--danger)";
  if (["transmitted", "observed", "accepted"].includes(value)) return "var(--accent)";
  return TRACE_CHART_COLORS[2 + index % 4];
}

function traceChartGroups(events: TraceEvent[], labels: (event: TraceEvent) => string[]): TraceChartGroup[] {
  const groups = new Map<string, TraceChartGroup>();
  for (const event of events) for (const label of new Set(labels(event))) {
    const group = groups.get(label) ?? { id: label, label, events: [] };
    group.events.push(event); groups.set(label, group);
  }
  return [...groups.values()].sort((a, b) => b.events.length - a.events.length || a.label.localeCompare(b.label));
}

function traceObject(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function frozenTraceEcus(configuration: SimulationSnapshot["configuration"]): Map<string, string> {
  const parameters = traceObject(configuration?.parameters);
  const model = traceObject(configuration?.engineering_model ?? parameters.engineering_model);
  const rawHardware = configuration?.hardware ?? parameters.hardware;
  const hardware = traceObject(rawHardware);
  const nodes = Array.isArray(model.nodes) && model.nodes.length ? model.nodes
    : Array.isArray(rawHardware) ? rawHardware : hardware.devices ?? hardware.nodes;
  const ecus = new Map<string, string>();
  for (const raw of Array.isArray(nodes) ? nodes : []) {
    const node = traceObject(raw), kind = node.device_type ?? node.type;
    if (typeof node.id === "string" && node.id && typeof kind === "string" && kind.trim().toUpperCase() === "ECU") {
      ecus.set(node.id, typeof node.name === "string" && node.name ? node.name : node.id);
    }
  }
  return ecus;
}

function traceHardwareIds(event: TraceEvent): string[] {
  const ids = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && !!item)
    : typeof value === "string" ? value.split(",").map(item => item.trim()).filter(Boolean) : [];
  // Only explicit hardware references; display names and network addresses are not IDs.
  return [...new Set([...ids(event.original.sender_hardware), ...ids(event.original.receiver_hardware),
    ...event.refs.filter(ref => ref.object_type === "HardwareNode").map(ref => ref.id)])];
}

function traceTimeBasis(event: TraceEvent, simulationSource: boolean): string | null {
  if (!event.timeKnown || !Number.isFinite(event.timestamp)) return null;
  const value = event.original.time_basis;
  if (typeof value === "string" && value.trim() && !["unknown", "unavailable", "unsynchronized"].includes(value.trim().toLowerCase())) return value.trim();
  return value == null && simulationSource ? "simulation_relative" : null;
}

function TraceCharts({ events, loadedCount, configuration, contextNote, simulationSource, hasMore, selected, onSelect, onOpen }: SelectionProps & {
  loadedCount: number; events: TraceEvent[]; configuration: SimulationSnapshot["configuration"]; contextNote: string;
  simulationSource: boolean; hasMore: boolean; onOpen: (event: TraceEvent, view: TraceView) => void;
}) {
  const [selection, setSelection] = useState<TraceChartGroup | null>(null);
  const [basis, setBasis] = useState(() => selected ? traceTimeBasis(selected, simulationSource) ?? "" : "");
  const [binCount, setBinCount] = useState(20);
  const [heatPage, setHeatPage] = useState(0);
  const [dataPage, setDataPage] = useState(0);
  const evidenceRef = useRef<HTMLElement | null>(null);
  const faultLabels = useMemo(() => new Map(events.map(event => [event.id, traceEventFindings(event)])), [events]);
  const faultGroups = useMemo(() => traceChartGroups(events, event => faultLabels.get(event.id) ?? []), [events, faultLabels]);
  const statusGroups = useMemo(() => traceChartGroups(events, event => [typeof event.original.status === "string" && event.original.status.trim() ? event.original.status.trim() : "Status nicht dokumentiert"]), [events]);
  const ecuInventory = useMemo(() => frozenTraceEcus(configuration), [configuration]);
  const ecuGroups = useMemo(() => {
    const rows = traceChartGroups(events, event => faultLabels.get(event.id)?.length ? traceHardwareIds(event).filter(id => ecuInventory.has(id)) : []);
    return rows.map(row => ({ ...row, label: ecuInventory.get(row.id)! }));
  }, [events, faultLabels, ecuInventory]);
  const unassignedEcu = events.filter(event => faultLabels.get(event.id)?.length && !traceHardwareIds(event).some(id => ecuInventory.has(id))).length;
  const bases = useMemo(() => [...new Set(events.map(event => traceTimeBasis(event, simulationSource)).filter((value): value is string => value !== null))].sort(), [events, simulationSource]);
  const chosenBasis = bases.includes(basis) ? basis : bases[0] ?? "";
  const timed = useMemo(() => events.filter(event => traceTimeBasis(event, simulationSource) === chosenBasis).toSorted((a, b) => a.timestamp - b.timestamp), [events, simulationSource, chosenBasis]);
  const buckets = useMemo((): TraceTimeBucket[] => {
    if (!timed.length) return [];
    const min = timed[0].timestamp, max = timed[timed.length - 1].timestamp;
    const count = max > min ? binCount : 1, width = (max - min) / count;
    const rows = Array.from({ length: count }, (_, index) => ({ start: min + width * index, end: min + width * (index + 1), events: [] as TraceEvent[], findings: [] as TraceEvent[] }));
    for (const event of timed) {
      const index = width > 0 ? Math.min(count - 1, Math.floor((event.timestamp - min) / width)) : 0;
      rows[index].events.push(event);
      if (faultLabels.get(event.id)?.length) rows[index].findings.push(event);
    }
    return rows;
  }, [timed, binCount, faultLabels]);
  const heatRows = useMemo(() => faultGroups.map(group => ({ group, cells: buckets.map(bucket => bucket.events.filter(event => faultLabels.get(event.id)?.includes(group.id))) })), [faultGroups, buckets, faultLabels]);
  const heatMaximum = heatRows.reduce((maximum, row) => row.cells.reduce((current, cell) => Math.max(current, cell.length), maximum), 1);
  const heatValues = simulationPage(heatRows, heatPage, 12);
  const active = selection ?? { id: "all", label: "Alle Ereignisse im aktuellen Ausschnitt", events };
  const dataValues = simulationPage(active.events, dataPage, 100);
  const select = (group: TraceChartGroup) => { setSelection(group); setDataPage(0); evidenceRef.current?.scrollIntoView({ block: "start" }); };
  const selectedFindingEvents = events.filter(event => faultLabels.get(event.id)?.length).length;
  const unknownTime = events.filter(event => traceTimeBasis(event, simulationSource) === null).length;
  let circleOffset = 0;
  return <section className="panel trace-charts" aria-label="Trace-Diagramme mit Daten- und Ursachenbezug">
    <div className="panel-heading"><div><p className="eyebrow">Trace-Diagramme</p><h3>Verteilung, Verlauf und Fehlerhäufung</h3></div><strong>{events.length} Ereignisse · {selectedFindingEvents} mit Fehlern / Befunden</strong></div>
    <p className="trace-chart-scope">{events.length} von {loadedCount} geladenen Ereignissen nach globalem Filter und Zeitfenster. {hasMore ? "Weitere Trace-Seiten sind vorhanden; dies ist eine Teilauswertung." : "Auswertung des geladenen Ausschnitts, keine Volltrace- oder Funktionsfreigabe."} Zähler erfassen Ereignisse, keine bewiesenen Ursachen. Ein Ereignis kann mehrere Befundarten und ECUs betreffen.</p>
    <div className="trace-chart-grid">
      <section className="trace-chart-card"><header><p className="eyebrow">Balken</p><h4>Fehler- und Befundarten</h4><p>Ereignisse je ausdrücklich dokumentierter Kategorie.</p></header>
        <TraceGroupBars groups={faultGroups} label="Befundarten" empty="Keine ausdrücklichen Fehler oder Befunde im Ausschnitt dokumentiert." onSelect={select} />
      </section>
      <section className="trace-chart-card"><header><p className="eyebrow">Kreis</p><h4>Ereignisstatus</h4><p>Anteile an allen {events.length} gefilterten Ereignissen; Originalstatus aus der Quelle.</p></header>
        {events.length ? <div className="trace-status-distribution"><svg viewBox="0 0 140 140" role="group" aria-label={`Statusverteilung von ${events.length} Ereignissen; Segmente und Legende öffnen die Originaldaten`}>
          <title>Ereignisse nach Originalstatus</title>{statusGroups.map((group, index) => {
            const share = group.events.length / events.length, start = circleOffset - Math.PI / 2;
            circleOffset += share * Math.PI * 2;
            const end = circleOffset - Math.PI / 2;
            const arc = share === 1 ? "M 70 22 A 48 48 0 1 1 70 118 A 48 48 0 1 1 70 22"
              : `M ${70 + 48 * Math.cos(start)} ${70 + 48 * Math.sin(start)} A 48 48 0 ${share > .5 ? 1 : 0} 1 ${70 + 48 * Math.cos(end)} ${70 + 48 * Math.sin(end)}`;
            return <path key={group.id} d={arc} fill="none" stroke={traceStatusColor(group.id, index)} strokeWidth="18" className="trace-status-slice" role="button" tabIndex={0} aria-label={`${group.label}: ${group.events.length} Ereignisse; Daten öffnen`} onClick={() => select(group)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(group); } }}><title>{group.label}: {group.events.length} ({(share * 100).toFixed(1)} %)</title></path>;
          })}<text x="70" y="68" textAnchor="middle" className="trace-chart-total">{events.length}</text><text x="70" y="85" textAnchor="middle">Ereignisse</text>
        </svg><div className="trace-chart-legend">{statusGroups.map((group, index) => <button key={group.id} type="button" onClick={() => select(group)} title={`${group.label}: Originalereignisse öffnen`}><i aria-hidden="true" style={{ background: traceStatusColor(group.id, index) }} /><span>{group.label}</span><strong>{group.events.length} · {(group.events.length / events.length * 100).toFixed(1)} %</strong></button>)}</div></div> : <p className="trace-chart-empty">Keine Trace-Ereignisse geladen.</p>}
        <p className="trace-chart-note">Ein Transportstatus belegt allein keine funktionale Anforderungserfüllung.</p>
      </section>
      <section className="trace-chart-card"><header><p className="eyebrow">ECU-Häufung</p><h4>Fehler / Befunde bei beteiligten ECUs</h4><p>{contextNote}</p></header>
        <TraceGroupBars groups={ecuGroups} label="ECUs" empty={ecuInventory.size ? "Keine belegte ECU-Beteiligung an Fehlern / Befunden im Ausschnitt." : "ECU-Auswertung benötigt dokumentierte Hardware-IDs und ECU-Typen im zugehörigen Modell-Snapshot."} onSelect={select} />
        {!!unassignedEcu && <p className="trace-chart-note">{unassignedEcu} Ereignisse mit Fehlern / Befunden ohne belegte ECU-Zuordnung. Sie werden keiner ECU zugerechnet.</p>}
        <p className="trace-chart-note">Jedes Ereignis zählt pro beteiligter ECU einmal. Beteiligung ist keine bewiesene Fehlerursache im Steuergerät.</p>
      </section>
      <section className="trace-chart-card"><header><p className="eyebrow">Trend</p><h4>Ereignisse und Befunde über der Zeit</h4><p>Anzahl pro gleich langem Teilfenster, keine interpolierten Signalwerte.</p></header>
        <div className="trace-chart-controls"><label>Zeitbasis<select value={chosenBasis} onChange={event => { setBasis(event.target.value); setHeatPage(0); }} disabled={!bases.length}><option value="" disabled>Keine belegte Zeitbasis</option>{bases.map(value => <option key={value}>{value}</option>)}</select></label>
          <label>Teilfenster<select value={binCount} onChange={event => { setBinCount(Number(event.target.value)); setHeatPage(0); }}>{[5, 10, 20, 40].map(count => <option key={count} value={count}>{count}</option>)}</select></label></div>
        <TraceFrequencyTrend buckets={buckets} onSelect={select} />
        <p className="trace-chart-note">{timed.length} Ereignisse in Zeitbasis {chosenBasis || "unbekannt"}. {unknownTime} Ereignisse ohne belegte Zeit oder Zeitbasis bleiben außerhalb der Zeitdiagramme. Unterschiedliche Zeitbasen werden getrennt ausgewertet.</p>
      </section>
      <section className="trace-chart-card trace-chart-wide"><header><p className="eyebrow">Zeitliche Fehlerhäufigkeit</p><h4>Wann treten welche Fehler / Befunde wie häufig auf?</h4><p>Zeilen: dokumentierte Befundart. Spalten: Teilfenster der oben gewählten Zeitbasis. Jede Zelle öffnet ihre Originalereignisse.</p></header>
        {buckets.length && heatRows.length ? <>
          <SimulationPageControls label="Befundarten im Zeitverlauf" {...heatValues} onPage={setHeatPage} />
          <div className="trace-chart-table-scroll" tabIndex={0} aria-label="Zeitliche Fehlerhäufigkeit, horizontal scrollbar"><table className="trace-frequency-matrix"><thead><tr><th scope="col">Befundart</th>{buckets.map((bucket, index) => <th key={index} scope="col" title={`${bucket.start.toFixed(6)}–${bucket.end.toFixed(6)} s; ${chosenBasis}`}>+{(bucket.start - buckets[0].start).toPrecision(3)} s</th>)}</tr></thead><tbody>
            {heatValues.items.map(({ group, cells }) => <tr key={group.id}><th scope="row"><button type="button" onClick={() => select(group)}>{group.label}</button></th>{cells.map((items, index) => <td key={index}><button type="button" disabled={!items.length} style={{ "--trace-heat": `${items.length ? 8 + items.length / heatMaximum * 25 : 0}%` } as CSSProperties}
              aria-label={`${group.label}; ${buckets[index].start.toFixed(6)} bis ${buckets[index].end.toFixed(6)} Sekunden; ${items.length} Ereignisse; Daten öffnen`}
              title={`${group.label}\n${buckets[index].start.toFixed(6)}–${buckets[index].end.toFixed(6)} s\n${items.length} Ereignisse im Ausschnitt`}
              onClick={() => select({ id: `${group.id}:${index}`, label: `${group.label} · ${buckets[index].start.toFixed(6)}–${buckets[index].end.toFixed(6)} s (${chosenBasis})`, events: items })}>{items.length}</button></td>)}</tr>)}
          </tbody></table></div>
          <p className="trace-chart-note">Zeitachse relativ zu {buckets[0].start.toFixed(6)} s ({chosenBasis}). Fenster sind links geschlossen und rechts offen; das letzte schließt den Endzeitpunkt ein. Dunklere Zellen zeigen mehr Ereignisse; 0 bedeutet keine passenden Ereignisse im geladenen Ausschnitt.</p>
        </> : <p className="trace-chart-empty">{!buckets.length ? "Ohne belegte Zeitbasis kann keine zeitliche Fehlerhäufigkeit berechnet werden." : "Keine ausdrücklichen Fehler / Befunde in den gefilterten Ereignissen."}</p>}
      </section>
    </div>
    <section ref={evidenceRef} className="trace-chart-evidence" aria-label="Daten und Ursachen zur Diagrammauswahl">
      <div className="panel-heading"><div><p className="eyebrow">Verknüpfte Originaldaten</p><h4>{active.label}</h4></div>{selection && <button type="button" className="button secondary tiny" onClick={() => { setSelection(null); setDataPage(0); }}>Diagrammauswahl zurücksetzen</button>}</div>
      <p role="status">{active.events.length} zugehörige Ereignisse. Diagramm oder Tabellenzeile auswählen, um Daten und Ursachen-Kontext zu verfolgen.</p>
      <SimulationPageControls label="Diagrammereignisse" {...dataValues} onPage={setDataPage} />
      <div className="trace-chart-table-scroll" tabIndex={0} aria-label="Originalereignisse zur Diagrammauswahl"><table><thead><tr><th scope="col">Zeit / ID</th><th scope="col">Kommunikation</th><th scope="col">Status / Befunde</th><th scope="col">Daten / Ursachen</th></tr></thead><tbody>{dataValues.items.map(event => <tr key={event.id} className={selected?.id === event.id ? "trace-chart-selected" : ""}>
        <td><EventTime event={event} selected={selected} onSelect={onSelect} /><small>{event.id}</small></td><td>{event.source} → {event.destination}<small>{event.message} · {event.technology}</small></td>
        <td>{typeof event.original.status === "string" && event.original.status.trim() ? event.original.status : "Status nicht dokumentiert"}<small>{(faultLabels.get(event.id) ?? []).join(" · ") || "Kein ausdrücklicher Befund"}</small></td><td><div className="trace-chart-event-actions"><button type="button" className="button secondary tiny" onClick={() => onOpen(event, "trace")}>Originaldaten</button><button type="button" className="button secondary tiny" onClick={() => onOpen(event, "findings")}>Befunde</button><button type="button" className="button secondary tiny" onClick={() => onOpen(event, "sequence")}>Sequenz</button><button type="button" className="button secondary tiny" disabled={!simulationSource || !event.timeKnown} title={!simulationSource ? "Import ohne Run-/Snapshot-Bezug liefert keine bestätigte Ursachenanalyse" : !event.timeKnown ? "Ereignis ohne belegten Zeitstempel" : "Bestehende Ursachenanalyse mit diesem Ereignis als Fokus öffnen"} onClick={() => onOpen(event, "root-cause")}>Ursachen-Kontext</button></div></td>
      </tr>)}</tbody></table></div>
      {!active.events.length && <p className="trace-chart-empty">Zuerst einen Trace laden oder das Filterfenster erweitern.</p>}
      {selected && <details className="trace-chart-original"><summary>Originaldaten der gemeinsamen Auswahl · {selected.id}</summary><pre>{JSON.stringify(selected.original, null, 2)}</pre>{selected.refs.map(ref => { const href = engineeringContextHref(ref, readActiveProjectId()); return href ? <a key={ref.object_type + ref.id} href={href}>{ref.object_type} im Engineering öffnen </a> : null; })}</details>}
      <p className="trace-chart-note">Ursachen-Kontext öffnet die bestehende Analyse mit Ereignis-ID, Lauf und Zeitfenster. Neue Ursachenprüfungen werden dort ausdrücklich gestartet. Bei lokalen Importen ohne Modell-/Laufbezug stehen Rohdaten und Befunde zur Verfügung; eine bestätigte technische Ursache bleibt offen.</p>
    </section>
  </section>;
}

function TraceGroupBars({ groups, label, empty, onSelect }: { groups: TraceChartGroup[]; label: string; empty: string; onSelect: (group: TraceChartGroup) => void }) {
  const [page, setPage] = useState(0);
  const values = simulationPage(groups, page, 10);
  const maximum = groups.reduce((value, group) => Math.max(value, group.events.length), 1);
  return groups.length ? <><SimulationPageControls label={label} {...values} onPage={setPage} /><div className="trace-group-bars">{values.items.map(group => <button type="button" key={group.id} title={`${group.label}\n${group.events.length} Ereignisse; Originaldaten öffnen`} aria-label={`${group.label}: ${group.events.length} Ereignisse; Daten öffnen`} onClick={() => onSelect(group)}>
    <span>{group.label}</span><i aria-hidden="true"><b style={{ width: `${group.events.length / maximum * 100}%` }} /></i><strong>{group.events.length}</strong>
  </button>)}</div><p className="trace-chart-note">Skala 0–{maximum} Ereignisse; {values.first}–{values.last} von {groups.length} {label}. Balken öffnen ihre Daten.</p></> : <p className="trace-chart-empty">{empty}</p>;
}

function TraceFrequencyTrend({ buckets, onSelect }: { buckets: TraceTimeBucket[]; onSelect: (group: TraceChartGroup) => void }) {
  if (!buckets.length) return <p className="trace-chart-empty">Keine Ereignisse mit einer belegten gemeinsamen Zeitbasis.</p>;
  const width = 600, height = 230, left = 48, top = 18, right = 18, bottom = 40;
  const maximum = buckets.reduce((value, bucket) => Math.max(value, bucket.events.length), 1);
  const domain = buckets[buckets.length - 1].end - buckets[0].start;
  const x = (index: number) => left + (index + .5) / buckets.length * (width - left - right);
  const y = (value: number) => top + (1 - value / maximum) * (height - top - bottom);
  const series = [{ key: "events" as const, label: "Alle Ereignisse", color: "var(--accent)" }, { key: "findings" as const, label: "Mit Fehlern / Befunden", color: "var(--danger)" }];
  return <><div className="trace-chart-plot-scroll" tabIndex={0} aria-label="Ereignishäufigkeit im Zeitverlauf, horizontal scrollbar"><svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Anzahl je Teilfenster; Punkte öffnen ihre Originalereignisse">
    <title>Ereignisse und dokumentierte Fehler / Befunde pro Teilfenster</title>
    {[...new Set([0, Math.ceil(maximum / 2), maximum])].map(value => <g key={value}><line className="trace-chart-gridline" x1={left} x2={width - right} y1={y(value)} y2={y(value)} /><text x={left - 8} y={y(value) + 4} textAnchor="end">{value}</text></g>)}
    <line className="trace-chart-axis" x1={left} x2={left} y1={top} y2={height - bottom} /><line className="trace-chart-axis" x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} />
    <text x={left} y="12">Ereignisse / Teilfenster</text>{domain > 0 ? [0, domain / 2, domain].map(value => <text key={value} x={left + value / domain * (width - left - right)} y={height - 15} textAnchor="middle">+{value.toPrecision(3)} s</text>) : <text x={width / 2} y={height - 15} textAnchor="middle">Ein Zeitpunkt</text>}
    {series.map(item => <g key={item.key}>{buckets.length > 1 && <polyline fill="none" stroke={item.color} strokeWidth="2" points={buckets.map((bucket, index) => `${x(index)},${y(bucket[item.key].length)}`).join(" ")} />}{buckets.map((bucket, index) => {
      const group = { id: `${item.key}:${index}`, label: `${item.label} · ${bucket.start.toFixed(6)}–${bucket.end.toFixed(6)} s`, events: bucket[item.key] };
      const activate = () => { if (group.events.length) onSelect(group); };
      return <g key={index} role="button" tabIndex={group.events.length ? 0 : -1} aria-disabled={!group.events.length} aria-label={`${group.label}: ${group.events.length}; Originalereignisse öffnen`} onClick={activate} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(); } }} className="trace-trend-point">
        <title>{group.label}: {group.events.length} Ereignisse</title><circle cx={x(index)} cy={y(group.events.length)} r="8" fill="transparent" /><circle cx={x(index)} cy={y(group.events.length)} r="3.5" fill={item.color} />
      </g>;
    })}</g>)}
  </svg></div><div className="trace-chart-series">{series.map(item => <span key={item.key}><i style={{ background: item.color }} />{item.label}</span>)}</div>
    <p className="trace-chart-note">Beginn {buckets[0].start.toFixed(6)} s. {domain > 0 ? `${buckets.length} Teilfenster à ${(domain / buckets.length).toPrecision(3)} s. Punkte öffnen die zugehörigen Daten.` : "Nur ein belegter Zeitpunkt: daraus folgt kein zeitlicher Trend."}</p>
    <details><summary>Trendwerte und Datenlinks</summary><div className="trace-chart-table-scroll"><table><thead><tr><th scope="col">Von / bis (s)</th><th scope="col">Alle Ereignisse</th><th scope="col">Mit Fehlern / Befunden</th></tr></thead><tbody>{buckets.map((bucket, index) => <tr key={index}><th scope="row">{bucket.start.toFixed(6)}–{bucket.end.toFixed(6)}</th>{series.map(item => <td key={item.key}><button type="button" disabled={!bucket[item.key].length} onClick={() => onSelect({ id: `${item.key}:${index}`, label: `${item.label} · ${bucket.start.toFixed(6)}–${bucket.end.toFixed(6)} s`, events: bucket[item.key] })}>{bucket[item.key].length}</button></td>)}</tr>)}</tbody></table></div></details>
  </>;
}

function EventTime({ event, selected, onSelect }: SelectionProps & { event: TraceEvent }) {
  return <button type="button" aria-pressed={selected?.id === event.id} onClick={() => onSelect(event)}>{event.timeKnown ? `${event.timestamp.toFixed(6)} s` : "Zeit unbekannt"}</button>;
}

function TraceTable({ events, sessionEvents, compact = false, ...selection }: SelectionProps & { events: TraceEvent[]; sessionEvents: TraceEvent[]; compact?: boolean }) {
  const [page, setPage] = useState(0);
  const [profile, setProfile] = useState<TraceProfile | 'auto'>('auto');
  const [protocolFilter, setProtocolFilter] = useState('all');
  const [tableQuery, setTableQuery] = useState('');
  const [columnQuery, setColumnQuery] = useState('');
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  const [custom, setCustom] = useState<string[] | null>(null);
  const available = useMemo(() => availableColumns(sessionEvents), [sessionEvents]);
  const resolved = profile === 'auto' ? automaticProfile(sessionEvents) : profile;
  const defaults = TRACE_PROFILES[resolved].columns.filter(field => available.some(item => item.key === field.key));
  const columns = custom === null ? defaults : available.filter(field => custom.includes(field.key));
  const valueForColumn = (event: TraceEvent, key: string) => {
    if (key === '__time') return event.timeKnown ? `${event.timestamp}` : 'Zeit unbekannt';
    if (key === '__protocol') return event.technology;
    if (key === '__payload') return event.payload ?? '';
    const field = available.find(item => item.key === key);
    return field ? String(displayTraceValue(field.read(event))) : '';
  };
  const matchesColumnFilter = (event: TraceEvent, key: string) => {
    const query = columnFilters[key]?.trim().toLowerCase();
    return !query || valueForColumn(event, key).toLowerCase().includes(query);
  };
  const shown = events.filter(event => (protocolFilter === 'all' || event.technology === protocolFilter)
    && (!tableQuery.trim() || JSON.stringify(event).toLowerCase().includes(tableQuery.trim().toLowerCase()))
    && matchesColumnFilter(event, '__time')
    && matchesColumnFilter(event, '__protocol')
    && columns.every(field => matchesColumnFilter(event, field.key))
    && matchesColumnFilter(event, '__payload'));
  const rows = simulationPage(shown, page, 100);
  useEffect(() => { setPage(0); }, [events, protocolFilter, tableQuery, columnFilters]);
  useEffect(() => { const index = shown.findIndex(event => event.id === selection.selected?.id); if (index >= 0) setPage(Math.floor(index / 100)); }, [selection.selected?.id]);
  const selectableColumns = available.filter(field => !columnQuery.trim() || field.label.toLowerCase().includes(columnQuery.trim().toLowerCase()) || field.key.toLowerCase().includes(columnQuery.trim().toLowerCase()));
  const selected = selection.selected;
  const setColumnFilter = (key: string, value: string) => setColumnFilters(current => ({ ...current, [key]: value }));
  return <div className="panel trace-table">
     <div className="trace-toolbar sequence-toolbar">
       <label className="trace-table-search">Tabelle durchsuchen<input value={tableQuery} onChange={event => setTableQuery(event.target.value)} placeholder="ID, Quelle, Ziel, Payload …" /></label>
      <label>Spaltenprofil<select value={profile} onChange={event => { setProfile(event.target.value as TraceProfile | 'auto'); setCustom(null); }}>
        <option value="auto">Automatisch · {TRACE_PROFILES[automaticProfile(sessionEvents)].label}</option>
        {Object.entries(TRACE_PROFILES).map(([key, item]) => <option key={key} value={key}>{item.label}</option>)}
      </select></label>
      <label>Protokollfilter<select value={protocolFilter} onChange={event => setProtocolFilter(event.target.value)}>
        <option value="all">Alle Inhalte</option>{[...new Set(sessionEvents.map(event => event.technology))].map(key => <option key={key} value={key}>{key}</option>)}
      </select></label>
       <button className="button secondary" type="button" onClick={() => { setCustom(null); setProfile('auto'); setProtocolFilter('all'); setTableQuery(''); setColumnQuery(''); setColumnFilters({}); }}>Ansicht zurücksetzen</button>
    </div>
     <details className="trace-column-picker"><summary>Spalten auswählen ({available.length} Felder)</summary>
       <input aria-label="Spalten suchen" value={columnQuery} onChange={event => setColumnQuery(event.target.value)} placeholder="Spalten suchen …" />
       <div className="trace-column-options">{selectableColumns.map(field => <label key={field.key}><input type="checkbox" checked={columns.some(item => item.key === field.key)} onChange={() => {
         const keys = columns.map(item => item.key); setCustom(keys.includes(field.key) ? keys.filter(key => key !== field.key) : [...keys, field.key]);
       }} />{field.label}</label>)}</div>
    </details>
    <p>{sessionEvents.filter(event => !event.timeKnown).length || 0} Ereignisse ohne Zeitstempel · Zeitbasen werden nicht automatisch synchronisiert. Rohdaten ohne Signaldecoder sind kein Fehler.</p>
    <SimulationPageControls label="Trace-Nachrichten" {...rows} onPage={setPage} />
    <table><thead>
      <tr><th>Zeit / Auswahl</th><th>Protokoll</th>{columns.map(field => <th key={field.key}>{field.label}</th>)}<th>Rohdaten</th></tr>
      <tr className="trace-column-filters">
        <th><input aria-label="Filter Zeit / Auswahl" value={columnFilters.__time ?? ''} onChange={event => setColumnFilter('__time', event.target.value)} placeholder="Filtern …" /></th>
        <th><input aria-label="Filter Protokoll" value={columnFilters.__protocol ?? ''} onChange={event => setColumnFilter('__protocol', event.target.value)} placeholder="Filtern …" /></th>
        {columns.map(field => <th key={`filter-${field.key}`}><input aria-label={`Filter ${field.label}`} value={columnFilters[field.key] ?? ''} onChange={event => setColumnFilter(field.key, event.target.value)} placeholder="Filtern …" /></th>)}
        <th><input aria-label="Filter Rohdaten" value={columnFilters.__payload ?? ''} onChange={event => setColumnFilter('__payload', event.target.value)} placeholder="Filtern …" /></th>
      </tr>
    </thead>
      <tbody>{rows.items.map(event => <tr key={event.id}><td><EventTime event={event} {...selection} /></td><td>{event.technology}</td>{columns.map(field => <td key={field.key}>{displayTraceValue(field.read(event))}{field.key === 'generic.message' && <TraceProperties event={event} />}</td>)}<td>{event.payload ? `${event.payload.slice(0, compact ? 24 : 96)}${event.payload.length > (compact ? 24 : 96) ? ' …' : ''}` : '—'}</td></tr>)}</tbody>
    </table>
    {!shown.length && <p>Keine Ereignisse in der aktuellen Auswahl.</p>}
    {selected && <section aria-label="Ereignisdetails"><h3>Ereignisdetails · {selected.message}</h3><p>Originalzeitbasis: {displayTraceValue(selected.original.time_basis)} · Herkunft/Reihenfolge: {displayTraceValue(selected.original.source_record_index)}</p>
      <h4>Protokollschichten</h4><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(selected.original.protocols ?? {}, null, 2)}</pre>
      <details><summary>Vollständige Originalfelder und Rohdaten</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(selected.original, null, 2)}</pre></details>
    </section>}
  </div>;
}

function SequenceView({ events, model: sourceModel, ...selection }: SelectionProps & { events: TraceEvent[]; model: SequenceDiagramModel | null }) {
  const model = sourceModel ? sequenceModelForEventIds(sourceModel, new Set(events.map(event => event.id))) : null;
  const byId = new Map(events.map(event => [event.id, event]));
  if (!model) return <div className="panel trace-sequence"><p>Das gemeinsame Sequenzmodell ist für dieses Trace-Fenster nicht verfügbar.</p></div>;
  return <div className="panel trace-sequence"><E2ESequenceDiagram model={model} selectedId={selection.selected?.id ?? null} onClearSelection={selection.onClearSelection} timeBasisForEvent={item => { const event = byId.get(item.id); return event ? traceTimeBasis(event, model.source === 'SIMULATED') : null; }} onSelect={item => {
    const event = byId.get(item.id);
    if (event) selection.onSelect(event);
  }} /></div>;
}

function TraceProperties({ event }: { event: TraceEvent }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { if (open && !dialog.current?.open) dialog.current?.showModal(); }, [open]);
  return <><button className="button secondary tiny" type="button" aria-label={`Eigenschaften: ${event.message}`} onClick={() => setOpen(true)}>Eigenschaften</button>
    {open && <dialog className="trace-properties-dialog" ref={dialog} onClose={() => setOpen(false)} aria-label={`Trace-Eigenschaften: ${event.message}`}>
      <header><h3>{event.message}</h3><button className="button secondary tiny" type="button" onClick={() => dialog.current?.close()}>Schließen</button></header>
      <dl><dt>Ereignis-ID</dt><dd>{event.id}</dd><dt>Nachrichten-ID</dt><dd>{displayTraceValue(event.original.message_ids ?? event.original.message_id ?? event.original.message)}</dd>
        <dt>Sender</dt><dd>{event.source}</dd><dt>Empfänger</dt><dd>{event.destination}</dd><dt>IP- und Port-Zuordnung</dt><dd>{event.ipContext || 'Nicht dokumentiert'}</dd></dl>
      <div className="trace-context-links">{event.refs.map(ref => { const href = engineeringContextHref(ref, readActiveProjectId()); return href ? <a key={ref.object_type + ref.id} href={href}>{ref.object_type} öffnen</a> : null; })}</div>
      <details><summary>Vollständige Originalfelder</summary><pre>{JSON.stringify(event.original, null, 2)}</pre></details>
    </dialog>}</>;
}

function TraceContext({ event }: { event: TraceEvent }) {
  const rawEthernet = event.original.ethernet;
  let ethernet: Record<string, unknown> = {};
  try { ethernet = traceObject(typeof rawEthernet === 'string' ? JSON.parse(rawEthernet) : rawEthernet); } catch { /* Original remains available in properties. */ }
  const tx = traceObject(ethernet.source), rx = Array.isArray(ethernet.destinations) ? ethernet.destinations.map(traceObject) : [];
  const endpoint = (ip: unknown, port: unknown) => ip == null ? 'Nicht dokumentiert' : `${String(ip).includes(':') ? `[${ip}]` : ip}${port == null ? '' : `:${port}`}`;
  return <section className="trace-selected-context" aria-label="Gemeinsamer Trace-Kontext">
    <header><strong>{event.timeKnown ? `${event.timestamp.toFixed(6)} s` : 'Zeit unbekannt'} · {event.message}</strong><TraceProperties event={event} /></header>
    <table><thead><tr><th>Sender</th><th>Empfänger</th></tr></thead><tbody><tr><td>{event.source}</td><td>{event.destination}</td></tr>
      {!!Object.keys(ethernet).length && <tr><td>{endpoint(tx.ip, ethernet.source_port)}</td><td>{rx.map((target, index) => endpoint(target.ip, Array.isArray(ethernet.destination_ports) ? ethernet.destination_ports[index] : undefined)).join(', ') || 'Nicht dokumentiert'}</td></tr>}
    </tbody></table>
    <p>{event.technology} · {event.status}{tx.ip_provenance === 'simulation_derived' || rx.some(target => target.ip_provenance === 'simulation_derived') ? ' · Simulationsadressen (abgeleitet)' : ''}</p>
    {event.signals.length > 0 && <details><summary>{event.signals.length} Signalwerte</summary><table><thead><tr><th>Signal</th><th>Wert</th><th>Einheit</th><th>Qualität</th></tr></thead><tbody>{event.signals.map(signal => <tr key={signal.id}><td>{signal.name}</td><td>{displayTraceValue(signal.value)}</td><td>{signal.unit}</td><td>{signal.quality || '—'}</td></tr>)}</tbody></table></details>}
  </section>;
}

function SignalView({ events, channels, onChannels, simulationSource, ...selection }: SelectionProps & { events: TraceEvent[]; channels: string[]; onChannels: (ids: string[]) => void; simulationSource: boolean }) {
  const [signalQuery, setSignalQuery] = useState('');
  const [channelPage, setChannelPage] = useState(0);
  const [plotPage, setPlotPage] = useState(0);
  const [tablePage, setTablePage] = useState(0);
  const [initialized, setInitialized] = useState(false);
  const available = useMemo(() => traceSignalInventory(events), [events]);
  const active = initialized || channels.length ? channels.filter(id => available.some(signal => signal.id === id)) : available.slice(0, 4).map(signal => signal.id);
  const changeChannels = (ids: string[]) => { setInitialized(true); onChannels(ids); setPlotPage(0); setTablePage(0); };
  const matching = available.filter(signal => `${signal.name} ${signal.id} ${signal.unit}`.toLowerCase().includes(signalQuery.trim().toLowerCase()));
  const picker = simulationPage(matching, channelPage, 50);
  const plots = simulationPage(available.filter(signal => active.includes(signal.id)), plotPage, 12);
  const values = simulationPage(events.filter(event => event.signals.some(signal => active.includes(signal.id))), tablePage, 100);
  return <section className="panel trace-signals" aria-label="Signal-Analyse">
    <header className="trace-signal-heading"><div><h3>Signalverläufe</h3><p>{available.length} Kanäle im geladenen Zeitfenster · {active.length} ausgewählt</p></div>
      <button className="button secondary" type="button" onClick={() => changeChannels(available.map(signal => signal.id))}>Alle Signale auswählen</button>
      <button className="button secondary" type="button" onClick={() => changeChannels([])}>Auswahl leeren</button></header>
    <details className="trace-signal-picker"><summary>Signale auswählen und suchen ({active.length} gewählt)</summary>
      <label className="trace-table-search">Signal suchen<input aria-label="Trace-Signale suchen" value={signalQuery} onChange={event => { setSignalQuery(event.target.value); setChannelPage(0); }} placeholder="Name, Einheit oder ID …" /></label>
      <SimulationPageControls label="Verfügbare Trace-Signale" {...picker} onPage={setChannelPage} />
      <div className="trace-signal-options">{picker.items.map(signal => <label key={signal.id}><input type="checkbox" checked={active.includes(signal.id)} onChange={() => changeChannels(active.includes(signal.id) ? active.filter(id => id !== signal.id) : [...active, signal.id])} /><span>{signal.name}</span><small>{signal.unit}</small></label>)}</div>
    </details>
    <p className="trace-view-note">Originalsamples im gemeinsamen Zeitfenster. Fehlende Werte bleiben „—“. Zeitbasen werden getrennt dargestellt; es werden keine Werte interpoliert.</p>
    <SimulationPageControls label="Trace-Signalverläufe" {...plots} onPage={setPlotPage} />
    {plots.items.map(signal => <TraceSignalPlot key={signal.id} signalId={signal.id} name={signal.name} unit={signal.unit} events={events} simulationSource={simulationSource} {...selection} />)}
    <details className="trace-signal-values" open><summary>Wertetabelle · {values.total} Ereignisse</summary>
      <SimulationPageControls label="Trace-Signalwerte" {...values} onPage={setTablePage} />
      <div className="trace-table-scroll"><table><thead><tr><th>Zeit / Ereignis</th>{active.map(id => <th key={id}>{available.find(signal => signal.id === id)?.name}</th>)}</tr></thead><tbody>{values.items.map(event => <tr key={event.id}><td><EventTime event={event} {...selection} /></td>{active.map(id => { const sample = event.signals.find(signal => signal.id === id); return <td key={id}>{displayTraceValue(sample?.value)} {sample?.unit}<small>{sample?.quality}</small></td>; })}</tr>)}</tbody></table></div>
    </details>
    {!available.length && <p>Keine dekodierten Signalwerte im Zeitfenster. Für Rohbytes wird eine passende Decoder-Datenbank benötigt.</p>}
  </section>;
}

function TraceSignalPlot({ signalId, name, unit, events, simulationSource, ...selection }: SelectionProps & { signalId: string; name: string; unit: string; events: TraceEvent[]; simulationSource: boolean }) {
  const samples = events.flatMap(event => { const signal = event.signals.find(item => item.id === signalId); return signal && signal.value !== null ? [{ event, signal }] : []; });
  const bases = [...new Set(samples.map(sample => traceTimeBasis(sample.event, simulationSource)).filter((basis): basis is string => basis !== null))];
  const unknown = samples.filter(sample => traceTimeBasis(sample.event, simulationSource) === null).length;
  return <section className="trace-signal-plot" aria-label={`Signalverlauf: ${name}`}><header><strong>{name}</strong><span>{unit || 'ohne Einheit'} · {samples.length} Samples</span></header>
    {bases.map(basis => {
      const points = samples.filter(sample => traceTimeBasis(sample.event, simulationSource) === basis);
      const numeric = points.every(sample => typeof sample.signal.value === 'number' && Number.isFinite(sample.signal.value));
      const categories = numeric ? [] : [...new Set(points.map(sample => String(sample.signal.value)))];
      const times = points.map(sample => sample.event.timestamp), ys = points.map(sample => numeric ? Number(sample.signal.value) : categories.indexOf(String(sample.signal.value)));
      const minT = Math.min(...times), maxT = Math.max(...times), minV = Math.min(...ys), maxV = Math.max(...ys);
      return <div key={basis}><small>Zeitbasis: {basis} · {minT.toFixed(6)} bis {maxT.toFixed(6)} s · Werte {numeric ? `${minV} bis ${maxV} ${unit}` : categories.join(', ')}</small>
        <svg viewBox="0 0 900 120" role="img" aria-label={`${name}: ${points.length} Originalsamples; ${basis}`}>
          <line x1="35" y1="100" x2="875" y2="100" className="trace-signal-axis" />
          {points.map((sample, index) => <circle key={sample.event.id} cx={minT === maxT ? 455 : 35 + (times[index] - minT) / (maxT - minT) * 840} cy={minV === maxV ? 60 : 100 - (ys[index] - minV) / (maxV - minV) * 80} r={selection.selected?.id === sample.event.id ? 5 : 3} role="button" tabIndex={0}
            aria-label={`${name}: ${displayTraceValue(sample.signal.value)} ${unit}; ${sample.event.timestamp.toFixed(6)} s; ${sample.signal.quality || 'Qualität unbekannt'}`} onClick={() => selection.onSelect(sample.event)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selection.onSelect(sample.event); } }}><title>{sample.event.timestamp.toFixed(6)} s · {displayTraceValue(sample.signal.value)} {unit} · {sample.signal.quality}</title></circle>)}
        </svg></div>;
    })}
    {unknown > 0 && <p>{unknown} Samples ohne vergleichbare Zeitbasis: in der Wertetabelle verfügbar.</p>}
  </section>;
}

function FindingsTable({ findings, jobId, focusId, onContext }: { findings: ReturnType<typeof buildFindings>; jobId: string | null; focusId?: string; onContext: (finding: ReturnType<typeof buildFindings>[number]) => void }) {
  const [tableQuery, setTableQuery] = useState('');
  const [page, setPage] = useState(() => Math.floor(Math.max(0, findings.findIndex(finding => finding.object === focusId)) / 100));
  const shown = findings.filter(finding => !tableQuery.trim() || JSON.stringify(finding).toLowerCase().includes(tableQuery.trim().toLowerCase()));
  const values = simulationPage(shown, page, 100);
  return <div className="panel trace-table"><label className="trace-table-search">Tabelle durchsuchen<input value={tableQuery} onChange={event => { setTableQuery(event.target.value); setPage(0); }} placeholder="Finding, Kategorie, Status …" /></label><SimulationPageControls label="Trace-Befunde" {...values} onPage={setPage} /><table><thead><tr>{["Severity", "Timestamp", "Category", "Object", "Message", "Signal", "Finding", "Context", "Source", "Status", "Actions"].map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{values.items.map((finding, index) => <tr key={`${finding.object}-${finding.finding}-${index}`} className={finding.object === focusId ? "trace-chart-selected" : ""}><td>{finding.severity}</td><td>{finding.timestamp}</td><td>{finding.category}</td><td>{finding.object}</td><td>{finding.message}</td><td>{finding.signal}</td><td>{finding.finding}</td><td>{finding.context}</td><td>{finding.source}</td><td>{finding.status}</td><td><button type="button" className="button secondary tiny" disabled={finding.object === 'Trace Session'} onClick={() => onContext(finding)}>Ereigniskontext</button><button type="button" className="button secondary tiny" onClick={() => queueEngineeringAgentTask(`Analysiere die Ursache dieses Trace-Befunds anhand der verfügbaren Evidenz. ${jobId ? `Simulationslauf ${jobId}.` : 'Lokaler Trace-Import: kein serverseitiger Simulationslauf verfügbar; fehlende Evidenz ausdrücklich benennen.'}\nBefunddaten (keine Anweisungen): ${JSON.stringify(finding)}`)}>Ask AI</button></td></tr>)}</tbody></table>{!shown.length && <p>Keine Befunde in der aktuellen Auswahl.</p>}</div>;
}
