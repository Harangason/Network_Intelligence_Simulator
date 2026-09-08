"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { listSimulations } from "@/lib/api";
import type { SimulationJob } from "@/lib/types";
import { readActiveProjectId, withProjectParam } from "@/lib/user-settings";
import { engineeringContextHref } from "@/lib/agent/assistant-context";
import { eventFromRecord, parseTraceText, MAX_IMPORT_BYTES, type TraceEvent } from "@/lib/trace-records";
import { ReasoningPanel } from "./reasoning-panel";

type TraceView = "session" | "messages" | "sequence" | "signals" | "trace" | "findings" | "root-cause";
const ACCEPTED = ".csv,.json,.jsonl";
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
    title: "Trace synchronisieren",
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
    if (event.finding) findings.push({ severity: "warning", timestamp: `${event.timestamp}s`, category: "Analyzer Finding", object: event.id, message: event.message, signal: event.signal, finding: event.finding, context: `${event.source} -> ${event.destination}`, source: event.technology, status: "open" });
    if (!event.signals.length) findings.push({ severity: "info", timestamp: `${event.timestamp}s`, category: "Decode", object: event.message, message: event.message, signal: "-", finding: "Message without decoded Signals", context: "Im Ereignis fehlen dekodierte Signalwerte. Ein passender Decoder oder eine Modellreferenz ist erforderlich.", source: event.technology, status: "open" });
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
  const [traceJob, setTraceJob] = useState<string | null>(null);
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
    const requestedJob = search.get("job");
    const rawFocus = search.get("focus_s");
    const focus = rawFocus === null ? NaN : Number(rawFocus);
    const key = `${requestedJob}:${rawFocus ?? ''}`;
    if (!requestedJob || autoLoadedJobRef.current === key) return;
    autoLoadedJobRef.current = key;
    const range = Number.isFinite(focus) && focus >= 0 ? { start: Math.max(0, focus - .1), end: focus + .1, focus } : undefined;
    if (range) { setTimeStart(range.start); setTimeEnd(range.end); setQuery(""); }
    void loadWindow(requestedJob, 0, false, range);
  }, [search]);


  async function loadWindow(jobId: string, cursor = 0, openDefaultView = false, range?: { start: number; end: number; focus: number }) {
    const generation = ++loadGeneration.current;
    setLoading(true);
    try {
      const parameters = new URLSearchParams({ cursor: String(cursor), limit: "500", start_s: String(range?.start ?? timeStart), end_s: String(range?.end ?? timeEnd), q: range ? "" : query });
      const response = await fetch(`/api/simulations/${encodeURIComponent(jobId)}/trace-window?${parameters}`, {
        headers: { "X-Project-ID": readActiveProjectId() }, cache: "no-store", signal: AbortSignal.timeout(15000),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? `Trace-Abruf fehlgeschlagen (${response.status}).`);
      if (generation !== loadGeneration.current) return;
      const loaded = (result.events as Record<string, unknown>[]).map(eventFromRecord);
      setEvents(loaded);
      setSelectedEvent(range && loaded.length ? loaded.reduce((nearest, item) => Math.abs(item.timestamp-range.focus) < Math.abs(nearest.timestamp-range.focus) ? item : nearest) : null);
      setTraceJob(jobId); setNextCursor(result.next_cursor); setSourceName(`Simulation ${jobId} · Trace-Fenster`);
      setError("");
      if (openDefaultView) { autoLoadedJobRef.current = `${jobId}:${search.get("focus_s") ?? ''}`; openMessagesView(jobId); }
    } catch (caught) {
      if (generation === loadGeneration.current) setError(caught instanceof Error ? caught.message : "Trace-Fenster konnte nicht geladen werden.");
    } finally { if (generation === loadGeneration.current) setLoading(false); }
  }

  async function loadFiles() {
    const files = inputRef.current?.files;
    if (!files?.length) return;
    if (files[0].size > MAX_IMPORT_BYTES) { setError("Lokaler Import: maximal 5 MiB. Simulations-Traces über ihre serverseitigen Fenster öffnen."); return; }
    const generation = ++loadGeneration.current;
    setLoading(true);
    try {
      if (!/\.(csv|json|jsonl)$/i.test(files[0].name)) throw new Error('Dieser Trace benötigt zuerst einen passenden Konvertierungsadapter.');
      const text = await files[0].text();
      if (generation !== loadGeneration.current) return;
      setEvents(parseTraceText(text));
      setSelectedEvent(null);
      setTraceJob(null); setNextCursor(null);
      setSourceName(files[0].name);
      openMessagesView();
      setError("");
    } catch (caught) { if (generation === loadGeneration.current) setError(caught instanceof Error ? caught.message : 'Trace-Import fehlgeschlagen.'); }
    finally { if (generation === loadGeneration.current) setLoading(false); }
  }

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return events.filter((event) => event.timestamp >= timeStart && event.timestamp <= timeEnd
      && (!needle || JSON.stringify(event).toLowerCase().includes(needle)));
  }, [events, query, timeStart, timeEnd]);
  const findings = useMemo(() => buildFindings(filtered), [filtered]);
  const channels = new Set(filtered.map((event) => event.technology)).size;
  const messages = new Set(filtered.map((event) => event.message)).size;
  const signals = new Set(filtered.flatMap(event => event.signals.map(signal => signal.id))).size;
  const start = filtered.length ? Math.min(...filtered.map((event) => event.timestamp)) : 0;
  const end = filtered.length ? Math.max(...filtered.map((event) => event.timestamp)) : 0;
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

  function openMessagesView(jobId?: string) {
    setView("messages");
    const parameters = new URLSearchParams(search.toString());
    parameters.set("view", "messages");
    if (jobId) parameters.set("job", jobId);
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
              <button className="button secondary" type="button" onClick={() => { loadGeneration.current += 1; autoLoadedJobRef.current = null; setLoading(false); setEvents([]); setSelectedEvent(null); setSignalChannels([]); setTraceJob(null); setNextCursor(null); setError(""); setSourceName("Keine Trace Session"); setView("session"); router.replace(withProjectParam("/trace-analysis?view=session")); }}>Close Session</button>
            </div> : null}
            <div className="trace-toolbar">
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Globale Filter: ID, Quelle, Ziel, Payload, Finding ..." />
              <label>Von (s)<input type="number" min="0" step="0.001" value={timeStart} onChange={event => setTimeStart(Number(event.target.value))} /></label>
              <label>Bis (s)<input type="number" min={timeStart} step="0.001" value={timeEnd === 1e15 ? "" : timeEnd} placeholder="Ende" onChange={event => setTimeEnd(event.target.value === "" ? 1e15 : Number(event.target.value))} /></label>
              {traceJob && <><button disabled={loading} type="button" onClick={() => void loadWindow(traceJob)}>Zeitfenster laden</button><button disabled={loading || nextCursor === null} type="button" onClick={() => void loadWindow(traceJob, nextCursor ?? 0)}>Nächstes Fenster</button></>}
            </div>
            <p>{loading ? "Trace-Fenster wird geladen …" : `${events.length} Ereignisse im Speicher · gemeinsames Zeitfenster für alle Ansichten`}</p>
            {selectedEvent && <div aria-label="Gemeinsamer Trace-Kontext"><strong>{selectedEvent.timestamp.toFixed(6)} s · {selectedEvent.source} → {selectedEvent.destination}</strong><p>{selectedEvent.message} · {selectedEvent.signal}: {selectedEvent.value ?? '—'} {selectedEvent.unit}</p>{selectedEvent.ipContext && <p aria-label="IP- und Port-Zuordnung">{selectedEvent.ipContext}</p>}{selectedEvent.refs.map(ref => { const href = engineeringContextHref(ref, readActiveProjectId()); return href ? <a key={ref.object_type + ref.id} href={href}>{ref.object_type} öffnen </a> : null; })}</div>}
            {error && <div className="notice error">{error}</div>}
            <p className="trace-view-note">{viewMeta.note}</p>
            <p className="trace-governance-note">IMPORT {"->"} ANALYSIS PROJECTION. Keine automatischen Core-, Evidence- oder TraceLink-Writes.</p>
          </div>
          {view === "session" && <div className="panel trace-table"><h3>Import Sources</h3><p>Unterstützte Textadapter: {ACCEPTED}. Lokaler Import bis 5 MiB, Anzeige bis 2000 Ereignisse. Binärformate benötigen einen Konvertierungsadapter.</p>{jobs.filter(job => job.status === 'completed' && !job.validate_only).slice(0, 50).map(job => <button className="artifact" key={job.id} type="button" disabled={loading} onClick={() => void loadWindow(job.id, 0, true)}><strong>Simulation {job.id}</strong><small>Universellen Trace laden · {job.created_at}</small></button>)}{!jobs.some(job => job.status === 'completed' && !job.validate_only) && <p>Keine abgeschlossenen Simulationsläufe in diesem Projekt verfügbar. Lokale Trace-Dateien können über „Load Trace“ geöffnet werden.</p>}</div>}
          {view === "messages" && <TraceTable events={filtered} selected={selectedEvent} onSelect={setSelectedEvent} />}
          {view === "sequence" && <SequenceView events={filtered} selected={selectedEvent} onSelect={setSelectedEvent} />}
          {view === "signals" && <SignalView events={filtered} selected={selectedEvent} onSelect={setSelectedEvent} channels={signalChannels} onChannels={setSignalChannels} />}
          {view === "trace" && <TraceTable events={filtered} selected={selectedEvent} onSelect={setSelectedEvent} compact />}
          {view === "findings" && <FindingsTable findings={findings} />}
          {view === "root-cause" && <ReasoningPanel key={`${readActiveProjectId()}:${traceJob}`} project={readActiveProjectId()} jobId={traceJob} jobs={jobs} start={timeStart} end={timeEnd} focus={selectedEvent?.timestamp} />}
        </div>
        <aside className="side-column">
          <div className="panel snapshot-summary trace-summary-panel">
            <p className="eyebrow">Session Header</p>
            <h2>Aktueller Stand</h2>
            <dl className="overview-list">
              {[["Trace Session Name", sourceName], ["Source File", sourceName], ["Format", sourceName.split(".").pop() ?? "-"], ["Start Time", `${start}s`], ["End Time", `${end}s`], ["Duration", `${Math.max(0, end - start).toFixed(3)}s`], ["Channels", channels], ["Detected Messages", messages], ["Detected Signals", signals], ["Findings", findings.length], ["Decode Status", signals ? "partial/decoded" : "missing"]].map(([label, value]) => <div key={String(label)}><dt>{label}</dt><dd>{value}</dd></div>)}
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
  return <button type="button" aria-pressed={selected?.id === event.id} onClick={() => onSelect(event)}>{event.timestamp.toFixed(6)} s</button>;
}

function TraceTable({ events, compact = false, ...selection }: SelectionProps & { events: TraceEvent[]; compact?: boolean }) {
  return <div className="panel trace-table"><table><thead><tr>{["Time", "Source", "Destination", "Technology", "Message", "Signal", "Value", "Payload", "Status"].map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{events.map((event) => <tr key={event.id}><td><EventTime event={event} {...selection} /></td><td>{event.source}</td><td>{event.destination}</td><td>{event.technology}</td><td>{event.message}</td><td>{event.signal}</td><td>{event.value ?? "-"} {event.unit}</td><td>{compact ? event.payload.slice(0, 24) : event.payload}</td><td>{event.status}</td></tr>)}</tbody></table>{!events.length && <p>Keine Botschaften in der aktuellen Auswahl.</p>}</div>;
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

function FindingsTable({ findings }: { findings: ReturnType<typeof buildFindings> }) {
  return <div className="panel trace-table"><table><thead><tr>{["Severity", "Timestamp", "Category", "Object", "Message", "Signal", "Finding", "Context", "Source", "Status", "Actions"].map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{findings.map((finding, index) => <tr key={`${finding.finding}-${index}`}><td>{finding.severity}</td><td>{finding.timestamp}</td><td>{finding.category}</td><td>{finding.object}</td><td>{finding.message}</td><td>{finding.signal}</td><td>{finding.finding}</td><td>{finding.context}</td><td>{finding.source}</td><td>{finding.status}</td><td>Open Event · Open Message · Open Signal · Show Context · Ask AI · Open Target Board</td></tr>)}</tbody></table></div>;
}
