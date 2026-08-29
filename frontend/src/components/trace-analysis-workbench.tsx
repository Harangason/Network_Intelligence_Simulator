"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getSimulation, listSimulations } from "@/lib/api";
import type { SimulationJob } from "@/lib/types";

type TraceView = "session" | "messages" | "sequence" | "signals" | "trace" | "findings" | "root-cause";
type TraceEvent = {
  id: string;
  timestamp: number;
  source: string;
  destination: string;
  technology: string;
  payload: string;
  message: string;
  signal: string;
  value: number | null;
  status: string;
  finding: string;
};

const ACCEPTED = ".blf,.asc,.trc,.pcap,.pcapng,.log,.dbc,.arxml,.fibex,.mf4,.mdf,.csv,.json,.jsonl,.xml,.yaml,.yml,.txt";
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
    note: "Erste Anomalie, betroffene Kommunikation und nachfolgende Abweichungen als überprüfbare Kausalkette darstellen.",
  },
};

function splitLine(line: string) {
  return line.includes(",") ? line.split(",").map((item) => item.trim()) : line.trim().split(/\s+/);
}

function eventFromRecord(record: Record<string, unknown>, index: number): TraceEvent {
  const timestamp = Number(record.timestamp_s ?? record.time_s ?? record.timestamp ?? record.t ?? index);
  const source = String(record.source ?? record.sender ?? record.from ?? record.node ?? "-");
  const destination = String(record.destination ?? record.receiver ?? record.to ?? record.target ?? "-");
  const technology = String(record.technology ?? record.bus ?? record.channel ?? "trace");
  const payload = String(record.payload_hex ?? record.payload ?? record.data ?? "");
  const message = String(record.message_id ?? record.message ?? record.frame_id ?? record.id ?? `event-${index + 1}`);
  const signal = String(record.signal ?? record.signal_name ?? "-");
  const rawValue = record.value ?? record.signal_value;
  const value = rawValue === undefined || rawValue === null || rawValue === "" ? null : Number(rawValue);
  const status = String(record.status ?? "observed");
  const finding = String(record.finding ?? record.warning ?? "");
  return { id: `${message}-${index}`, timestamp: Number.isFinite(timestamp) ? timestamp : index, source, destination, technology, payload, message, signal, value: Number.isFinite(value) ? value : null, status, finding };
}

function parseTraceText(text: string): TraceEvent[] {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (!lines.length) return [];
  if (lines[0].startsWith("{")) {
    return lines.flatMap((line, index) => {
      try { return [eventFromRecord(JSON.parse(line) as Record<string, unknown>, index)]; } catch { return []; }
    });
  }
  if (lines[0].includes(",")) {
    const headers = splitLine(lines[0]);
    return lines.slice(1).map((line, index) => {
      const values = splitLine(line);
      return eventFromRecord(Object.fromEntries(headers.map((header, valueIndex) => [header, values[valueIndex] ?? ""])), index);
    });
  }
  return lines.map((line, index) => {
    const values = splitLine(line);
    return eventFromRecord({ timestamp: values[0], source: values[1], message: values[2], status: values[3], payload: values.slice(4).join(" ") }, index);
  });
}

function buildFindings(events: TraceEvent[]) {
  const findings = [];
  if (!events.length) findings.push({ severity: "info", timestamp: "-", category: "Session", object: "Trace Session", message: "-", signal: "-", finding: "No Trace Session", context: "Keine Trace-Daten geladen.", source: "-", status: "open" });
  for (const event of events) {
    if (event.finding) findings.push({ severity: "warning", timestamp: `${event.timestamp}s`, category: "Analyzer Finding", object: event.id, message: event.message, signal: event.signal, finding: event.finding, context: `${event.source} -> ${event.destination}`, source: event.technology, status: "open" });
    if (event.signal === "-" || event.value === null) findings.push({ severity: "info", timestamp: `${event.timestamp}s`, category: "Decode", object: event.message, message: event.message, signal: "-", finding: "Message without decoded Signals", context: "RAW BYTE != ENGINEERING SIGNAL. DBC/ARXML/FIBEX-Daten fehlen oder wurden nicht decodiert.", source: event.technology, status: "open" });
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

  useEffect(() => { void listSimulations().then(setJobs).catch(() => setJobs([])); }, []);
  useEffect(() => {
    const requested = search.get("view");
    if (requested === "session" || requested === "messages" || requested === "sequence" || requested === "signals" || requested === "trace" || requested === "findings" || requested === "root-cause") setView(requested);
  }, [search]);
  useEffect(() => {
    const requestedJob = search.get("job");
    if (!requestedJob || autoLoadedJobRef.current === requestedJob) return;
    autoLoadedJobRef.current = requestedJob;
    void getSimulation(requestedJob).then((selected) => {
      const artifact = selected.artifact_downloads?.find((item) => item.name === "universal_trace.jsonl")
        ?? selected.artifact_downloads?.find((item) => item.name.endsWith(".jsonl"));
      if (!artifact) throw new Error("Der Simulationslauf enthält keinen JSONL-Trace.");
      return loadArtifact(artifact.url, artifact.name, false);
    }).catch((caught) => {
      autoLoadedJobRef.current = null;
      setError(caught instanceof Error ? caught.message : "Trace-Artefakt konnte nicht geladen werden.");
    });
  }, [search]);

  async function loadArtifact(url: string, name: string, openDefaultView = true) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      const text = await response.text();
      setEvents(parseTraceText(text));
      setSourceName(name);
      if (openDefaultView) openMessagesView();
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Trace-Artefakt konnte nicht geladen werden.");
    }
  }

  async function loadFiles() {
    const files = inputRef.current?.files;
    if (!files?.length) return;
    const text = await files[0].text();
    setEvents(parseTraceText(text));
    setSourceName(files[0].name);
    openMessagesView();
    setError("");
  }

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return events;
    return events.filter((event) => Object.values(event).join(" ").toLowerCase().includes(needle));
  }, [events, query]);
  const findings = useMemo(() => buildFindings(filtered), [filtered]);
  const channels = new Set(filtered.map((event) => event.technology)).size;
  const messages = new Set(filtered.map((event) => event.message)).size;
  const signals = new Set(filtered.filter((event) => event.signal !== "-").map((event) => event.signal)).size;
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

  function openMessagesView() {
    setView("messages");
    const parameters = new URLSearchParams(search.toString());
    parameters.set("view", "messages");
    router.replace(`/trace-analysis?${parameters.toString()}`);
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
              <button className="button secondary" type="button" onClick={() => { setEvents([]); setSourceName("Keine Trace Session"); setView("session"); router.replace("/trace-analysis?view=session"); }}>Close Session</button>
            </div> : null}
            <div className="trace-toolbar">
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Globale Filter: ID, Quelle, Ziel, Payload, Finding ..." />
            </div>
            {error && <div className="notice error">{error}</div>}
            <p className="trace-view-note">{viewMeta.note}</p>
            <p className="trace-governance-note">IMPORT {"->"} ANALYSIS PROJECTION. Keine automatischen Core-, Evidence- oder TraceLink-Writes.</p>
          </div>
          {view === "session" && <div className="panel trace-table"><h3>Import Sources</h3><p>Accepted formats: {ACCEPTED}</p>{jobs.flatMap((job) => job.artifact_downloads ?? []).map((artifact) => <button className="artifact" key={artifact.url} type="button" onClick={() => void loadArtifact(artifact.url, artifact.name)}><strong>{artifact.name}</strong><small>Als Trace Session laden</small></button>)}{!jobs.flatMap((job) => job.artifact_downloads ?? []).length && <p>No Trace Session Loaded. Lade eine Trace-Datei oder starte zuerst eine Simulation mit Artefakten.</p>}</div>}
          {view === "messages" && <TraceTable events={filtered} />}
          {view === "sequence" && <SequenceView events={filtered} />}
          {view === "signals" && <SignalView events={filtered} />}
          {view === "trace" && <TraceTable events={filtered} compact />}
          {view === "findings" && <FindingsTable findings={findings} />}
          {view === "root-cause" && <RootCauseView events={filtered} />}
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

function TraceTable({ events, compact = false }: { events: TraceEvent[]; compact?: boolean }) {
  return <div className="panel trace-table"><table><thead><tr>{["Time", "Source", "Destination", "Technology", "Message", "Signal", "Value", "Payload", "Status"].map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{events.map((event) => <tr key={event.id}><td>{event.timestamp}</td><td>{event.source}</td><td>{event.destination}</td><td>{event.technology}</td><td>{event.message}</td><td>{event.signal}</td><td>{event.value ?? "-"}</td><td>{compact ? event.payload.slice(0, 24) : event.payload}</td><td>{event.status}</td></tr>)}</tbody></table>{!events.length && <p>Keine Botschaften in der aktuellen Auswahl.</p>}</div>;
}

function SequenceView({ events }: { events: TraceEvent[] }) {
  return <div className="panel trace-sequence">{events.map((event) => <div className="sequence-row" key={event.id}><span>{event.timestamp}s</span><strong>{event.source}</strong><span>{"->"}</span><strong>{event.destination}</strong><em>{event.message}</em></div>)}{!events.length && <p>Keine Sequenzdaten verfügbar.</p>}</div>;
}

function SignalView({ events }: { events: TraceEvent[] }) {
  const signalEvents = events.filter((event) => event.value !== null);
  return <div className="panel trace-signals">{signalEvents.map((event) => <div className="signal-row" key={event.id}><span>{event.signal}</span><meter min="0" max="100" value={Math.max(0, Math.min(100, event.value ?? 0))} /><strong>{event.value}</strong></div>)}{!signalEvents.length && <p>EMPTY</p>}</div>;
}

function FindingsTable({ findings }: { findings: ReturnType<typeof buildFindings> }) {
  return <div className="panel trace-table"><table><thead><tr>{["Severity", "Timestamp", "Category", "Object", "Message", "Signal", "Finding", "Context", "Source", "Status", "Actions"].map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody>{findings.map((finding, index) => <tr key={`${finding.finding}-${index}`}><td>{finding.severity}</td><td>{finding.timestamp}</td><td>{finding.category}</td><td>{finding.object}</td><td>{finding.message}</td><td>{finding.signal}</td><td>{finding.finding}</td><td>{finding.context}</td><td>{finding.source}</td><td>{finding.status}</td><td>Open Event · Open Message · Open Signal · Show Context · Ask AI · Open Target Board</td></tr>)}</tbody></table></div>;
}

function RootCauseView({ events }: { events: TraceEvent[] }) {
  const anomalyIndex = events.findIndex((event) => event.finding || !["transmitted", "observed"].includes(event.status.toLowerCase()));
  if (anomalyIndex < 0) return <div className="panel trace-sequence"><strong>Keine Anomalie im geladenen Trace.</strong><p>Der Golden Trace enthält keine injizierte Abweichung, aus der eine Ursache abgeleitet werden könnte.</p></div>;
  const chain = events.slice(Math.max(0, anomalyIndex - 1), Math.min(events.length, anomalyIndex + 4));
  return <div className="panel trace-sequence"><h3>Erste Anomalie und Kausalkette</h3>{chain.map((event, index) => <div className="sequence-row" key={event.id}><span>{event.timestamp}s</span><strong>{index === Math.min(1, anomalyIndex) ? "FIRST ANOMALY" : event.status}</strong><span>{event.source} {"->"} {event.destination}</span><em>{event.signal !== "-" ? event.signal : event.message}</em></div>)}</div>;
}
