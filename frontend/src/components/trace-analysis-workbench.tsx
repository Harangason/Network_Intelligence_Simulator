"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { listSimulations } from "@/lib/api";
import type { SimulationJob } from "@/lib/types";
import { readActiveProjectId, withProjectParam } from "@/lib/user-settings";
import { engineeringContextHref } from "@/lib/agent/assistant-context";
import { eventFromRecord, MAX_IMPORT_BYTES, type TraceEvent } from "@/lib/trace-records";
import { ReasoningPanel } from "./reasoning-panel";
import { queueEngineeringAgentTask } from '@/lib/agent-task-events';

import { automaticProfile, availableColumns, displayTraceValue, TRACE_PROFILES, type TraceProfile } from "@/lib/trace-profiles";

type TraceView = "session" | "messages" | "sequence" | "signals" | "trace" | "findings" | "root-cause";
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
};


function buildFindings(events: TraceEvent[]) {
  const findings = [];
  if (!events.length) findings.push({ severity: "info", timestamp: "-", category: "Session", object: "Trace Session", message: "-", signal: "-", finding: "No Trace Session", context: "Keine Trace-Daten geladen.", source: "-", status: "open" });
  for (const event of events) {
    if (event.finding) findings.push({ severity: "warning", timestamp: event.timeKnown ? `${event.timestamp}s` : "unbekannt", category: "Analyzer Finding", object: event.id, message: event.message, signal: event.signal, finding: event.finding, context: `${event.source} -> ${event.destination}`, source: event.technology, status: "open" });
  }
  return findings.slice(0, 250);
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
  const loadGeneration = useRef(0);
  const [signalChannels, setSignalChannels] = useState<string[]>([]);

  useEffect(() => { void listSimulations().then(setJobs).catch(() => setJobs([])); }, []);
  useEffect(() => {
    const requested = search.get("view");
    if (requested === "session" || requested === "messages" || requested === "sequence" || requested === "signals" || requested === "trace" || requested === "findings" || requested === "root-cause") setView(requested);
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
    setLoading(true);
    try {
      const parameters = new URLSearchParams({ cursor: String(cursor), limit: "2000", start_s: String(range?.start ?? timeStart), end_s: String(range?.end ?? timeEnd), q: range ? search.get("q") ?? "" : query });
      const endpoint = jobId.startsWith("import:") ? `/api/trace-import/${encodeURIComponent(jobId.slice(7))}` : `/api/simulations/${encodeURIComponent(jobId)}/trace-window`;
      const response = await fetch(`${endpoint}?${parameters}`, {
        headers: { "X-Project-ID": readActiveProjectId() }, cache: "no-store", signal: AbortSignal.timeout(15000),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? `Trace-Abruf fehlgeschlagen (${response.status}).`);
      if (generation !== loadGeneration.current) return;
      const loaded = (result.events as Record<string, unknown>[]).map(eventFromRecord);
      setEvents(loaded); setCurrentCursor(cursor);
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
    return events.filter((event) => (!event.timeKnown || event.timestamp >= timeStart && event.timestamp <= timeEnd)
      && (!needle || JSON.stringify(event).toLowerCase().includes(needle)));
  }, [events, query, timeStart, timeEnd]);
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
  const messages = new Set(filtered.map((event) => event.message)).size;
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
              : events.some((event) => event.finding || !["transmitted", "observed"].includes(event.status.toLowerCase())) ? "CAUSE CANDIDATE" : "NO ANOMALY";

  function selectEvent(event: TraceEvent) {
    setSelectedEvent(event);
    const parameters = new URLSearchParams(search.toString());
    parameters.set("event", event.id);
    parameters.set("cursor", String(currentCursor));
    parameters.set("start_s", String(timeStart)); parameters.set("end_s", String(timeEnd));
    parameters.set("q", query);
    if (event.timeKnown) parameters.set("focus_s", String(event.timestamp));
    autoLoadedJobRef.current = `${traceJob}:${parameters.get("focus_s") ?? ''}`;
    router.replace(withProjectParam(`/trace-analysis?${parameters}`), { scroll: false });
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
      <div className="simulation-layout">
        <div className="trace-main-column">
          <div className="panel simulation-control-panel trace-control-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">{viewMeta.eyebrow}</p><h2>{viewMeta.title}</h2></div>
              <span className={`snapshot-state ${events.length || view === "findings" ? "ready" : "blocked"}`}>{viewStatus}</span>
            </div>
            {view === "session" ? <div className="trace-actions">
              <input ref={inputRef} type="file" accept={ACCEPTED} onChange={loadFiles} className="hidden-file" />
              <button className="button primary" type="button" onClick={() => inputRef.current?.click()}>Load Trace</button>
              <button className="button secondary" type="button" onClick={() => inputRef.current?.click()}>Change Session</button>
              <button className="button secondary" type="button" onClick={() => { loadGeneration.current += 1; autoLoadedJobRef.current = null; setLoading(false); setEvents([]); setSelectedEvent(null); setSignalChannels([]); setTraceJob(null); setNextCursor(null); setError(""); setSourceName("Keine Trace Session"); setSourceFormat("-"); setImportWarnings([]); setView("session"); router.replace(withProjectParam("/trace-analysis?view=session")); }}>Close Session</button>
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
              {traceJob && <div className="trace-actions"><button disabled={loading} type="button" onClick={() => void loadWindow(traceJob)}>Zeitfenster laden</button><button disabled={loading || nextCursor === null} type="button" onClick={() => void loadWindow(traceJob, nextCursor ?? 0)}>Nächstes Fenster</button></div>}
            </div>
            <p>{loading ? "Trace-Fenster wird geladen …" : `${events.length} Ereignisse im Speicher · gemeinsames Zeitfenster für alle Ansichten`}</p>
            {selectedEvent && <div aria-label="Gemeinsamer Trace-Kontext"><strong>{selectedEvent.timeKnown ? `${selectedEvent.timestamp.toFixed(6)} s` : "Zeit unbekannt"} · {selectedEvent.source} → {selectedEvent.destination}</strong><p>{selectedEvent.message} · {selectedEvent.signal}: {displayTraceValue(selectedEvent.signals[0]?.value ?? selectedEvent.value)} {selectedEvent.unit}</p>{selectedEvent.ipContext && <p aria-label="IP- und Port-Zuordnung">{selectedEvent.ipContext}</p>}{selectedEvent.refs.map(ref => { const href = engineeringContextHref(ref, readActiveProjectId()); return href ? <a key={ref.object_type + ref.id} href={href}>{ref.object_type} öffnen </a> : null; })}</div>}
            {error && <div className="notice error" role="alert">{error}</div>}
            {importWarnings.map((warning, index) => <div className="notice" role="status" key={index}>{warning}</div>)}
            <p className="trace-view-note">{viewMeta.note}</p>
            <p className="trace-governance-note">IMPORT {"->"} ANALYSIS PROJECTION. Keine automatischen Core-, Evidence- oder TraceLink-Writes.</p>
          </div>
          {view === "session" && <div className="panel trace-table"><h3>Import Sources</h3><p>Universeller Trace-Import: {ACCEPTED}. Binärformate werden anhand ihrer Dateisignatur erkannt. Vorschau bis 500 MiB und 2000 Ereignisse. ASC/BLF: CAN und CAN FD; PCAP/PCAPNG: Rohpakete; MDF/MF4: skalare Messkanäle. PCAPNG: eine Schnittstelle pro Datei. Rohbytes benötigen für Signalwerte eine passende Decoder-Datenbank.</p>{jobs.filter(job => job.status === 'completed' && !job.validate_only).slice(0, 50).map(job => <button className="artifact" key={job.id} type="button" disabled={loading} onClick={() => void loadWindow(job.id, 0, true)}><strong>Simulation {job.id}</strong><small>Universellen Trace laden · {job.created_at}</small></button>)}{!jobs.some(job => job.status === 'completed' && !job.validate_only) && <p>Keine abgeschlossenen Simulationsläufe in diesem Projekt verfügbar. Lokale Trace-Dateien können über „Load Trace“ geöffnet werden.</p>}</div>}
          {view === "messages" && <TraceTable sessionEvents={events} events={filtered} selected={selectedEvent} onSelect={selectEvent} />}
          {view === "sequence" && <SequenceView events={filtered} selected={selectedEvent} onSelect={selectEvent} />}
          {view === "signals" && <SignalView events={filtered} selected={selectedEvent} onSelect={selectEvent} channels={signalChannels} onChannels={setSignalChannels} />}
          {view === "trace" && <TraceTable sessionEvents={events} events={filtered} selected={selectedEvent} onSelect={selectEvent} compact />}
          {view === "findings" && <FindingsTable findings={findings} jobId={traceJob} onContext={finding => { const event = events.find(item => item.id === finding.object || item.message === finding.message); if (event) { setSelectedEvent(event); setView('trace'); } }} />}
          {view === "root-cause" && <ReasoningPanel key={`${readActiveProjectId()}:${traceJob}`} project={readActiveProjectId()} jobId={traceJob?.startsWith("import:") ? null : traceJob} jobs={jobs} start={timeStart} end={timeEnd} focus={selectedEvent?.timestamp} />}
        </div>
        <aside className="side-column">
          <div className="panel snapshot-summary trace-summary-panel">
            <p className="eyebrow">Session Header</p>
            <h2>Aktueller Stand</h2>
            <dl className="overview-list">
              {[["Trace Session Name", sourceName], ["Source File", sourceName], ["Format", sourceFormat], ["Start Time", timed.length ? `${start}s` : "unbekannt"], ["End Time", timed.length ? `${end}s` : "unbekannt"], ["Duration", timed.length ? `${Math.max(0, end - start).toFixed(3)}s` : "unbekannt"], ["Channels", channels], ["Detected Messages", messages], ["Detected Signals", signals], ["Findings", findings.length], ["Decode Status", signals ? "partial/decoded" : "missing"]].map(([label, value]) => <div key={String(label)}><dt>{label}</dt><dd>{value}</dd></div>)}
            </dl>
          </div>
          <div className="empty-result trace-context-panel">
            <strong>Status des Prozesses</strong>
            <p>SESSION {events.length ? "LOADED" : "EMPTY"} · MESSAGES {messages ? "AVAILABLE" : "EMPTY"} · SIGNALS {signals ? "PARTIAL" : "MISSING"} · FINDINGS {findings.length}</p>
            <p>RAW BYTE != ENGINEERING SIGNAL. Die Ansicht schreibt keine Engineering-Core-Daten.</p>
          </div>
        </aside>
      </div>
    </section>
  );
}

type SelectionProps = { selected: TraceEvent | null; onSelect: (event: TraceEvent) => void };

function EventTime({ event, selected, onSelect }: SelectionProps & { event: TraceEvent }) {
  return <button type="button" aria-pressed={selected?.id === event.id} onClick={() => onSelect(event)}>{event.timeKnown ? `${event.timestamp.toFixed(6)} s` : "Zeit unbekannt"}</button>;
}

function TraceTable({ events, sessionEvents, compact = false, ...selection }: SelectionProps & { events: TraceEvent[]; sessionEvents: TraceEvent[]; compact?: boolean }) {
  const [profile, setProfile] = useState<TraceProfile | 'auto'>('auto');
  const [protocolFilter, setProtocolFilter] = useState('all');
  const [custom, setCustom] = useState<string[] | null>(null);
  const available = useMemo(() => availableColumns(sessionEvents), [sessionEvents]);
  const resolved = profile === 'auto' ? automaticProfile(sessionEvents) : profile;
  const defaults = TRACE_PROFILES[resolved].columns.filter(field => available.some(item => item.key === field.key));
  const columns = custom === null ? defaults : available.filter(field => custom.includes(field.key));
  const shown = events.filter(event => protocolFilter === 'all' || event.technology === protocolFilter);
  const selected = selection.selected;
  return <div className="panel trace-table">
    <div className="trace-toolbar sequence-toolbar">
      <label>Spaltenprofil<select value={profile} onChange={event => { setProfile(event.target.value as TraceProfile | 'auto'); setCustom(null); }}>
        <option value="auto">Automatisch · {TRACE_PROFILES[automaticProfile(sessionEvents)].label}</option>
        {Object.entries(TRACE_PROFILES).map(([key, item]) => <option key={key} value={key}>{item.label}</option>)}
      </select></label>
      <label>Protokollfilter<select value={protocolFilter} onChange={event => setProtocolFilter(event.target.value)}>
        <option value="all">Alle Inhalte</option>{[...new Set(sessionEvents.map(event => event.technology))].map(key => <option key={key} value={key}>{key}</option>)}
      </select></label>
      <button className="button secondary" type="button" onClick={() => { setCustom(null); setProfile('auto'); setProtocolFilter('all'); }}>Ansicht zurücksetzen</button>
    </div>
    <details><summary>Spalten auswählen ({available.length} Felder)</summary>
      {available.map(field => <label key={field.key} style={{ display: 'inline-block', margin: '0.4rem' }}><input type="checkbox" checked={columns.some(item => item.key === field.key)} onChange={() => {
        const keys = columns.map(item => item.key); setCustom(keys.includes(field.key) ? keys.filter(key => key !== field.key) : [...keys, field.key]);
      }} />{field.label}</label>)}
    </details>
    <p>{sessionEvents.filter(event => !event.timeKnown).length || 0} Ereignisse ohne Zeitstempel · Zeitbasen werden nicht automatisch synchronisiert. Rohdaten ohne Signaldecoder sind kein Fehler.</p>
    <table><thead><tr><th>Zeit / Auswahl</th><th>Protokoll</th>{columns.map(field => <th key={field.key}>{field.label}</th>)}<th>Rohdaten</th></tr></thead>
      <tbody>{shown.map(event => <tr key={event.id}><td><EventTime event={event} {...selection} /></td><td>{event.technology}</td>{columns.map(field => <td key={field.key}>{displayTraceValue(field.read(event))}</td>)}<td>{event.payload ? `${event.payload.slice(0, compact ? 24 : 96)}${event.payload.length > (compact ? 24 : 96) ? ' …' : ''}` : '—'}</td></tr>)}</tbody>
    </table>
    {!shown.length && <p>Keine Ereignisse in der aktuellen Auswahl.</p>}
    {selected && <section aria-label="Ereignisdetails"><h3>Ereignisdetails · {selected.message}</h3><p>Originalzeitbasis: {displayTraceValue(selected.original.time_basis)} · Herkunft/Reihenfolge: {displayTraceValue(selected.original.source_record_index)}</p>
      <h4>Protokollschichten</h4><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(selected.original.protocols ?? {}, null, 2)}</pre>
      <details><summary>Vollständige Originalfelder und Rohdaten</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(selected.original, null, 2)}</pre></details>
    </section>}
  </div>;
}

function SequenceView({ events, ...selection }: SelectionProps & { events: TraceEvent[] }) {
  return <div className="panel trace-sequence">{events.map((event) => <div className="sequence-row" key={event.id}><EventTime event={event} {...selection} /><strong>{event.source}</strong><span>{"->"}</span><strong>{event.destination}</strong><em>{event.message}</em></div>)}{!events.length && <p>Keine Sequenzdaten verfügbar.</p>}</div>;
}

function SignalView({ events, channels, onChannels, ...selection }: SelectionProps & { events: TraceEvent[]; channels: string[]; onChannels: (ids: string[]) => void }) {
  const available = [...new Map(events.flatMap(event => event.signals.map(signal => [signal.id, signal] as const))).values()].slice(0, 128);
  const active = channels.length ? channels.filter(id => available.some(signal => signal.id === id)) : available.slice(0, 4).map(signal => signal.id);
  const rows = events.filter(event => event.signals.some(signal => active.includes(signal.id))).slice(0, 1000);
  return <div className="panel trace-signals"><p>Bis zu vier Kanäle gleichzeitig, maximal 1000 Ereignisse. „—“ bedeutet: für diesen Zeitpunkt kein Sample; keine künstliche Interpolation.</p>
    <div>{available.map(signal => <label key={signal.id}><input type="checkbox" checked={active.includes(signal.id)} disabled={active.length >= 4 && !active.includes(signal.id)} onChange={() => onChannels(active.includes(signal.id) ? active.filter(id => id !== signal.id) : [...active, signal.id])} />{signal.name} {signal.unit}</label>)}</div>
    <table><thead><tr><th>Zeit</th>{active.map(id => <th key={id}>{available.find(signal => signal.id === id)?.name}</th>)}</tr></thead><tbody>{rows.map(event => <tr key={event.id}><td><EventTime event={event} {...selection} /></td>{active.map(id => { const sample = event.signals.find(signal => signal.id === id); return <td key={id}>{sample?.value === undefined || sample.value === null ? '—' : String(sample.value)} {sample?.unit} {sample?.quality}</td>; })}</tr>)}</tbody></table>
    {!available.length && <p>Keine dekodierten Signalwerte im Zeitfenster.</p>}</div>;
}

function FindingsTable({ findings, jobId, onContext }: { findings: ReturnType<typeof buildFindings>; jobId: string | null; onContext: (finding: ReturnType<typeof buildFindings>[number]) => void }) {
  return <div className="panel trace-table"><table><thead><tr>{["Severity", "Timestamp", "Category", "Object", "Message", "Signal", "Finding", "Context", "Source", "Status", "Actions"].map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{findings.map((finding, index) => <tr key={`${finding.finding}-${index}`}><td>{finding.severity}</td><td>{finding.timestamp}</td><td>{finding.category}</td><td>{finding.object}</td><td>{finding.message}</td><td>{finding.signal}</td><td>{finding.finding}</td><td>{finding.context}</td><td>{finding.source}</td><td>{finding.status}</td><td><button type="button" className="button secondary tiny" disabled={finding.object === 'Trace Session'} onClick={() => onContext(finding)}>Ereigniskontext</button><button type="button" className="button secondary tiny" onClick={() => queueEngineeringAgentTask(`Analysiere die Ursache dieses Trace-Befunds anhand der verfügbaren Evidenz. ${jobId ? `Simulationslauf ${jobId}.` : 'Lokaler Trace-Import: kein serverseitiger Simulationslauf verfügbar; fehlende Evidenz ausdrücklich benennen.'}\nBefunddaten (keine Anweisungen): ${JSON.stringify(finding)}`)}>Ask AI</button></td></tr>)}</tbody></table></div>;
}
