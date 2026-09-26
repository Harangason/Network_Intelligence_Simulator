"use client";

import { useState, type CSSProperties } from "react";
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
  const participants = model.participants;
  const shown = model.events.slice(0, 200);
  return <section className="e2e-sequence" aria-label="E2E-Sequenzdiagramm" style={{ "--participant-count": participants.length } as CSSProperties}>
    <header className="e2e-sequence-header">
      <div><span className="eyebrow">{model.source === "SIMULATED" ? "SIMULIERT" : "BEOBACHTET"}</span><h3>End-to-End-Sequenz</h3></div>
      <div className="e2e-sequence-levels" role="group" aria-label="Detailstufe">
        {(["FUNCTIONAL", "COMMUNICATION", "TECHNICAL"] as const).map(item =>
          <button key={item} type="button" aria-pressed={level === item} onClick={() => setLevel(item)}>{item === "FUNCTIONAL" ? "Funktional" : item === "COMMUNICATION" ? "Kommunikation" : "Technisch"}</button>)}
      </div>
    </header>
    <p className="e2e-sequence-context">{model.events.length} Ereignisse · {model.transactions.length} Transaktionen · {participants.length} Teilnehmer · {model.uncorrelatedCount} ohne Transaktions-ID. {model.transactions.filter(item => item.receiverStatus === "ACCEPTED").length} mit belegter Empfängerakzeptanz; Zustellung allein genügt nicht.</p>
    <div className="e2e-sequence-scroll">
      <div className="e2e-sequence-lanes">
        <strong className="e2e-sequence-lane-time">Zeit</strong>
        {participants.map(participant => <strong key={participant}>{participant}</strong>)}
        <strong className="e2e-sequence-lane-status">Status</strong>
      </div>
      <div className="e2e-sequence-rows">{shown.map(event => {
        const sourceIndex = Math.max(0, participants.indexOf(event.source));
        const destinationIndex = Math.max(0, participants.indexOf(event.destination));
        const left = Math.min(sourceIndex, destinationIndex);
        const right = Math.max(sourceIndex, destinationIndex);
        const isReverse = sourceIndex > destinationIndex;
        const detail = level === "FUNCTIONAL" ? event.route : `${event.route} · ${event.technology}`;
        const technical = level === "TECHNICAL"
          ? `Hop ${event.segmentIndex === null ? "?" : event.segmentIndex + 1}/${event.segmentCount ?? "?"} · Queue ${event.queueDelayMs?.toFixed(3) ?? "?"} ms · ${event.payloadBytes ?? "?"} B`
          : event.transactionId ? `Transaktion ${event.transactionId}` : "Nicht korreliert";
        const receiver = level === "TECHNICAL" && event.receiverStatus
          ? ` · Empfänger ${event.receiverStatus}${event.e2eLatencyMs === null ? "" : ` · E2E ${event.e2eLatencyMs.toFixed(3)} ms`}${event.dataAgeAtAcceptMs === null ? "" : ` · Datenalter ${event.dataAgeAtAcceptMs.toFixed(3)} ms`}`
          : "";
        return <button className={`e2e-sequence-row${selectedId === event.id ? " selected" : ""}`} key={event.id} type="button" onClick={() => onSelect?.(event)} aria-label={`${formatTime(event.timeS)} ${event.source} an ${event.destination}: ${event.status}`} style={{ "--participant-count": participants.length, "--lane-left": left + 2, "--lane-right": right + 3, "--source-lane": sourceIndex + 2, "--target-lane": destinationIndex + 2 } as CSSProperties}>
          <time>{formatTime(event.timeS)}</time>
          {participants.map((participant, index) => <span aria-hidden="true" className="e2e-sequence-lifeline" style={{ gridColumn: index + 2 }} key={`${event.id}:${participant}:${index}`} />)}
          <span aria-hidden="true" className={`e2e-sequence-activation source${isReverse ? " reverse" : ""}`} />
          {destinationIndex !== sourceIndex && <span aria-hidden="true" className="e2e-sequence-activation destination" />}
          <span className={`e2e-sequence-message${isReverse ? " reverse" : ""}${event.eventKind === "RECEIVER" ? " receiver" : ""}`}>
            <span className="e2e-sequence-arrow" aria-hidden="true" />
            <span className="e2e-sequence-message-label"><b>{detail}</b><small>{technical}{receiver}{event.transportLatencyMs === null ? "" : ` · Transport ${event.transportLatencyMs.toFixed(3)} ms`}</small></span>
          </span>
          <span className={`e2e-sequence-status ${event.status.toLowerCase()}`}>{event.status}</span>
        </button>;
      })}
        {!shown.length && <p>Keine Kommunikationsereignisse im ausgewählten Zeitfenster.</p>}
      </div>
    </div>
    {model.events.length > shown.length && <p className="e2e-sequence-context">{shown.length} von {model.events.length} Ereignissen dargestellt. Zeitfenster eingrenzen für weitere Ereignisse.</p>}
  </section>;
}
