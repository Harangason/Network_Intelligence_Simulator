"use client";

import { useId, useMemo, useState, type CSSProperties, type KeyboardEvent } from "react";
import type { SequenceDiagramModel, SequenceEvent } from "@/features/simulation/lib/e2e-sequence";

type DetailLevel = "FUNCTIONAL" | "COMMUNICATION" | "TECHNICAL";

const TIME_COLUMN = 112;
const PARTICIPANT_COLUMN = 184;
const CHART_TOP = 22;
const ROW_HEIGHT = 68;
const MAC_ADDRESS = /^(?:[\da-f]{2}:){5}[\da-f]{2}$/i;

function formatRelativeTime(value: number | null, origin: number | null): string {
  if (value === null || origin === null) return "Zeit unbekannt";
  return `+${((value - origin) * 1000).toFixed(2)} ms`;
}

function formatDelta(value: number | null, previous: number | null): string {
  if (value === null || previous === null) return "Δ unbekannt";
  return `Δ ${((value - previous) * 1000).toFixed(2)} ms`;
}

function isFailure(event: SequenceEvent): boolean {
  return /drop|reject|fail|error|corrupt|timeout|loss/i.test(event.status) || event.receiverStatus === "REJECTED";
}

export function E2ESequenceDiagram({ model, selectedId, onSelect, onClearSelection }: {
  model: SequenceDiagramModel;
  selectedId?: string | null;
  onSelect?: (event: SequenceEvent) => void;
  onClearSelection?: () => void;
}) {
  const markerId = useId().replace(/:/g, "");
  const [level, setLevel] = useState<DetailLevel>("COMMUNICATION");
  const [localSelectedId, setLocalSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [measuring, setMeasuring] = useState(false);
  const [measureIds, setMeasureIds] = useState<string[]>([]);
  const participants = useMemo(() => {
    const ordered = new Set<string>();
    for (const event of model.events) {
      ordered.add(event.source);
      ordered.add(event.destination);
    }
    model.participants.forEach(participant => ordered.add(participant));
    return [...ordered];
  }, [model.events, model.participants]);
  const origin = model.events.find(event => event.timeS !== null)?.timeS ?? null;
  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return model.events;
    return model.events.filter(event => [event.source, event.destination, event.route, event.technology, event.status, event.transactionId ?? ""]
      .some(value => value.toLocaleLowerCase().includes(normalized)));
  }, [model.events, query]);
  const shown = filtered.slice(0, 200);
  const width = TIME_COLUMN + Math.max(participants.length, 1) * PARTICIPANT_COLUMN + 96;
  const height = CHART_TOP + shown.length * ROW_HEIGHT + 16;
  const xFor = (participant: string) => TIME_COLUMN + Math.max(0, participants.indexOf(participant)) * PARTICIPANT_COLUMN + PARTICIPANT_COLUMN / 2;
  const currentSelectedId = selectedId === undefined ? localSelectedId : selectedId;
  const selected = model.events.find(event => event.id === currentSelectedId) ?? null;
  const activeId = hoveredId ?? selected?.id ?? null;
  const measured = measureIds.map(id => model.events.find(event => event.id === id)).filter((event): event is SequenceEvent => !!event);
  const measureDelta = measured.length === 2 && measured.every(event => event.timeS !== null)
    ? Math.abs((measured[1].timeS as number) - (measured[0].timeS as number)) * 1000
    : null;

  function selectEvent(event: SequenceEvent) {
    if (measuring) {
      setMeasureIds(current => current.length === 1 ? [...current, event.id] : [event.id]);
    } else {
      if (onSelect) onSelect(event);
      else setLocalSelectedId(current => current === event.id ? null : event.id);
    }
  }

  function onEventKeyDown(event: KeyboardEvent<SVGGElement>, item: SequenceEvent) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectEvent(item);
    }
  }

  function toggleMeasure() {
    setMeasuring(current => !current);
    setMeasureIds([]);
  }

  return <section className="e2e-sequence" aria-label="E2E-Sequenzdiagramm">
    <header className="e2e-sequence-header">
      <div><span className="eyebrow">{model.source === "SIMULATED" ? "SIMULIERT" : "BEOBACHTET"}</span><h3>End-to-End-Sequenz</h3></div>
      <div className="e2e-sequence-toolbar">
        <label className="e2e-sequence-search"><span className="sr-only">Sequenzereignisse suchen</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Teilnehmer, Route oder Technologie" /></label>
        <button className="e2e-sequence-tool-button" type="button" aria-pressed={measuring} onClick={toggleMeasure}>Zeit messen</button>
        <div className="e2e-sequence-levels" role="group" aria-label="Detailstufe">
          {(["FUNCTIONAL", "COMMUNICATION", "TECHNICAL"] as const).map(item =>
            <button key={item} type="button" aria-pressed={level === item} onClick={() => setLevel(item)}>{item === "FUNCTIONAL" ? "Funktional" : item === "COMMUNICATION" ? "Kommunikation" : "Technisch"}</button>)}
        </div>
      </div>
    </header>
    <p className="e2e-sequence-context">{filtered.length} Ereignisse · {model.transactions.length} Transaktionen · {participants.length} Teilnehmer · {model.uncorrelatedCount} ohne Transaktions-ID · {model.transactions.filter(item => item.receiverStatus === "ACCEPTED").length} mit belegter Empfängerakzeptanz. {measuring ? measured.length < 2 ? "Start- und Endereignis auswählen." : measureDelta === null ? "Zeitmessung nicht möglich: Zeitstempel fehlen." : `Zeitabstand: ${measureDelta.toFixed(3)} ms` : "Zeit relativ zum ersten bekannten Ereignis."}</p>
    <div className="e2e-sequence-scroll">
      <div className="e2e-sequence-chart" style={{ width, "--participant-count": participants.length } as CSSProperties}>
        <div className="e2e-sequence-lanes" style={{ gridTemplateColumns: `${TIME_COLUMN}px repeat(${Math.max(participants.length, 1)}, ${PARTICIPANT_COLUMN}px)` }}>
          <strong className="e2e-sequence-lane-time">Zeit</strong>
          {participants.map((participant, index) => <div className="e2e-sequence-participant" key={participant} title={participant}>
            <strong>{MAC_ADDRESS.test(participant) ? `Teilnehmer ${index + 1}` : participant}</strong>
            <code>{participant}</code>
            <small>{MAC_ADDRESS.test(participant) ? "Beobachteter Netzwerkteilnehmer" : "Kommunikationsteilnehmer"}</small>
          </div>)}
        </div>
        <svg className="e2e-sequence-svg" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${shown.length} zeitlich geordnete Ereignisse zwischen ${participants.length} Kommunikationsteilnehmern`}>
          <defs>
            <marker id={`${markerId}-arrow`} markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L12,6 L0,12 z" className="e2e-sequence-arrow-head" /></marker>
          </defs>
          {participants.map(participant => <g key={`lifeline:${participant}`}>
            <line x1={xFor(participant)} x2={xFor(participant)} y1={CHART_TOP - 4} y2={height - 12} className="e2e-sequence-lifeline-svg" />
            <circle cx={xFor(participant)} cy={CHART_TOP - 4} r="3" className="e2e-sequence-lifeline-dot" />
          </g>)}
          {model.transactions.flatMap(transaction => {
            const indices = shown.flatMap((event, index) => event.transactionId === transaction.id ? [index] : []);
            if (indices.length < 2) return [];
            const involved = new Set(shown.filter(event => event.transactionId === transaction.id).flatMap(event => [event.source, event.destination]));
            return [...involved].map(participant => {
              const participantIndices = indices.filter(index => shown[index].source === participant || shown[index].destination === participant);
              if (participantIndices.length < 2) return null;
              const first = Math.min(...participantIndices);
              const last = Math.max(...participantIndices);
              return <rect key={`activation:${transaction.id}:${participant}`} x={xFor(participant) - 5} y={CHART_TOP + first * ROW_HEIGHT + 4} width="10" height={Math.max(12, (last - first) * ROW_HEIGHT - 7)} className="e2e-sequence-activation-svg" />;
            });
          })}
          {shown.map((event, index) => {
            const y = CHART_TOP + index * ROW_HEIGHT + ROW_HEIGHT / 2;
            const previous = index > 0 ? shown[index - 1].timeS : event.timeS;
            const sourceX = xFor(event.source);
            const destinationX = xFor(event.destination);
            const self = sourceX === destinationX;
            const failed = isFailure(event);
            const receiver = event.eventKind === "RECEIVER";
            const label = level === "FUNCTIONAL" ? event.route : event.route === "Unbekannt" ? event.technology : `${event.route} · ${event.technology}`;
            const technical = level === "TECHNICAL"
              ? `Hop ${event.segmentIndex === null ? "?" : event.segmentIndex + 1}/${event.segmentCount ?? "?"} · Queue ${event.queueDelayMs?.toFixed(3) ?? "?"} ms · ${event.payloadBytes ?? "?"} B`
              : event.transactionId ? `Transaktion ${event.transactionId}` : "Nicht korreliert";
            const labelX = self ? sourceX + 68 : (sourceX + destinationX) / 2;
            const path = self
              ? `M ${sourceX + 5} ${y + 7} V ${y - 8} H ${sourceX + 34} V ${y + 7}`
              : `M ${sourceX} ${y} H ${destinationX}`;
            const span = Math.max(54, Math.abs(destinationX - sourceX));
            return <g key={event.id} className={`e2e-sequence-event${activeId === event.id ? " active" : ""}${selected?.id === event.id ? " selected" : ""}${failed ? " failed" : ""}${receiver ? " receiver" : ""}`} role="button" tabIndex={0} aria-label={`${formatRelativeTime(event.timeS, origin)}; ${event.source} an ${event.destination}; ${event.route}; ${event.status}`} onMouseEnter={() => setHoveredId(event.id)} onMouseLeave={() => setHoveredId(null)} onFocus={() => setHoveredId(event.id)} onBlur={() => setHoveredId(null)} onClick={() => selectEvent(event)} onKeyDown={keyboardEvent => onEventKeyDown(keyboardEvent, event)}>
              <rect x="0" y={CHART_TOP + index * ROW_HEIGHT} width={width} height={ROW_HEIGHT} className="e2e-sequence-row-background" />
              <line x1="0" x2={width} y1={CHART_TOP + (index + 1) * ROW_HEIGHT} y2={CHART_TOP + (index + 1) * ROW_HEIGHT} className="e2e-sequence-row-rule" />
              <text x="20" y={y - 3} className="e2e-sequence-time-label">{formatRelativeTime(event.timeS, origin)}</text>
              <text x="20" y={y + 12} className="e2e-sequence-delta-label">{formatDelta(event.timeS, previous)}</text>
              {measureIds.includes(event.id) && <circle cx="9" cy={y} r="5" className="e2e-sequence-measure-dot" />}
              <rect x={destinationX - 5} y={y - 9} width="10" height="18" rx="1" className="e2e-sequence-event-activation-svg" aria-hidden="true" />
              <circle cx={sourceX} cy={y} r="3" className="e2e-sequence-message-origin" aria-hidden="true" />
              <path d={path} className="e2e-sequence-message-line" markerEnd={`url(#${markerId}-arrow)`} />
              <rect x={labelX - span / 2} y={y - 20} width={span} height="17" className="e2e-sequence-message-label-bg" />
              <text x={labelX} y={y - 8} textAnchor="middle" className="e2e-sequence-message-label-text">{label.length > 64 ? `${label.slice(0, 63)}…` : label}<title>{label}</title></text>
              {level !== "FUNCTIONAL" && <text x={labelX} y={y + 16} textAnchor="middle" className="e2e-sequence-message-detail-text">{level === "TECHNICAL" ? `${technical} · ${event.status}` : event.status}</text>}
            </g>;
          })}
          {!shown.length && <text x={width / 2} y={40} textAnchor="middle" className="e2e-sequence-empty">Keine Ereignisse für diesen Filter.</text>}
        </svg>
      </div>
    </div>
    {filtered.length > shown.length && <p className="e2e-sequence-context">{shown.length} von {filtered.length} Ereignissen dargestellt. Filter oder gemeinsames Trace-Zeitfenster eingrenzen, um weitere Ereignisse anzuzeigen.</p>}
    {selected && <aside className="e2e-sequence-selection" aria-label="Ausgewähltes Ereignis">
      <div><strong>{selected.route}</strong><span>{selected.source} → {selected.destination} · {selected.technology} · {selected.status}</span></div>
      <div>{selected.transactionId && <span>Transaktion {selected.transactionId}</span>}{selected.segmentIndex !== null && <span>Hop {selected.segmentIndex + 1}/{selected.segmentCount ?? "?"}</span>}{selected.transportLatencyMs !== null && <span>Transport {selected.transportLatencyMs.toFixed(3)} ms</span>}{selected.queueDelayMs !== null && <span>Queue {selected.queueDelayMs.toFixed(3)} ms</span>}{selected.payloadBytes !== null && <span>{selected.payloadBytes} Byte</span>}{selected.receiverStatus && <span>Empfänger {selected.receiverStatus}</span>}{selected.e2eLatencyMs !== null && <span>E2E {selected.e2eLatencyMs.toFixed(3)} ms</span>}{selected.dataAgeAtAcceptMs !== null && <span>Datenalter {selected.dataAgeAtAcceptMs.toFixed(3)} ms</span>}</div>
      <button type="button" onClick={() => { setLocalSelectedId(null); onClearSelection?.(); }}>Auswahl schließen</button>
    </aside>}
  </section>;
}
