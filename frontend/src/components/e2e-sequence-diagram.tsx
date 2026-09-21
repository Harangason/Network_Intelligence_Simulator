"use client";

import { useState } from "react";
import type { SequenceDiagramModel, SequenceEvent } from "@/lib/e2e-sequence";

type DetailLevel = "FUNCTIONAL" | "COMMUNICATION" | "TECHNICAL";

function formatTime(value: number | null): string {
  return value === null ? "Zeit unbekannt" : `${value.toFixed(6)} s`;
}

export function E2ESequenceDiagram({ model, selectedId, onSelect }: {
  model: SequenceDiagramModel;
  selectedId?: string | null;
  onSelect?: (event: SequenceEvent) => void;
}) {
  const [level, setLevel] = useState<DetailLevel>("COMMUNICATION");
  const shown = model.events.slice(0, 200);
  return <section className="e2e-sequence" aria-label="E2E-Sequenzdiagramm">
    <header className="e2e-sequence-header">
      <div><span className="eyebrow">{model.source === "SIMULATED" ? "SIMULIERT" : "BEOBACHTET"}</span><h3>End-to-End-Sequenz</h3></div>
      <div className="e2e-sequence-levels" role="group" aria-label="Detailstufe">
        {(["FUNCTIONAL", "COMMUNICATION", "TECHNICAL"] as const).map(item =>
          <button key={item} type="button" aria-pressed={level === item} onClick={() => setLevel(item)}>{item === "FUNCTIONAL" ? "Funktional" : item === "COMMUNICATION" ? "Kommunikation" : "Technisch"}</button>)}
      </div>
    </header>
    <p className="e2e-sequence-context">{model.events.length} Ereignisse · {model.transactions.length} Transaktionen · {model.participants.length} Teilnehmer · {model.uncorrelatedCount} ohne Transaktions-ID. Physikalische Zustellung ist keine Empfängerakzeptanz.</p>
    <div className="e2e-sequence-scroll">
      <div className="e2e-sequence-lanes">{model.participants.map(participant => <strong key={participant}>{participant}</strong>)}</div>
      <div className="e2e-sequence-rows">{shown.map(event =>
        <button className={`e2e-sequence-row${selectedId === event.id ? " selected" : ""}`} key={event.id} type="button" onClick={() => onSelect?.(event)} aria-label={`${formatTime(event.timeS)} ${event.source} an ${event.destination}: ${event.status}`}>
          <time>{formatTime(event.timeS)}</time>
          <span className="e2e-sequence-path"><strong>{event.source}</strong><span aria-hidden="true">→</span><strong>{event.destination}</strong></span>
          <span className="e2e-sequence-detail"><b>{level === "FUNCTIONAL" ? event.route : `${event.route} · ${event.technology}`}</b>
            {level === "TECHNICAL" && <small>Hop {event.segmentIndex === null ? "?" : event.segmentIndex + 1}/{event.segmentCount ?? "?"} · Queue {event.queueDelayMs?.toFixed(3) ?? "?"} ms · {event.payloadBytes ?? "?"} B</small>}
            {level !== "FUNCTIONAL" && <small>{event.transactionId ? `Transaktion ${event.transactionId}` : "Nicht korreliert"}{event.transportLatencyMs === null ? "" : ` · Transport ${event.transportLatencyMs.toFixed(3)} ms`}</small>}</span>
          <span className={`e2e-sequence-status ${event.status.toLowerCase()}`}>{event.status}</span>
        </button>)}
        {!shown.length && <p>Keine Kommunikationsereignisse im ausgewählten Zeitfenster.</p>}
      </div>
    </div>
    {model.events.length > shown.length && <p className="e2e-sequence-context">{shown.length} von {model.events.length} Ereignissen dargestellt. Zeitfenster eingrenzen für weitere Ereignisse.</p>}
  </section>;
}
