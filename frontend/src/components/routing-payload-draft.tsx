'use client';

import { useId, useMemo } from 'react';
import type { EngSignal } from '@/lib/types';
import type { ScopedMessage } from '@/lib/routing-payload-scope';
import { signalDomain, type PayloadDraft } from '@/lib/routing-payload-needs';

export function RoutingPayloadDraft({ draft, onChange, onApply, onDiscard, onRegenerate, messages, signals, stale, engineeringUrl }: {
  draft: PayloadDraft; onChange: (draft: PayloadDraft) => void; onApply: () => void; onDiscard: () => void; onRegenerate: () => void;
  messages: ScopedMessage[]; signals: EngSignal[]; stale: boolean; engineeringUrl: string;
}) {
  const id = useId();
  const byMessage = useMemo(() => {
    const index = new Map<string, EngSignal[]>();
    for (const signal of signals) if (signal.message_id) { const rows = index.get(signal.message_id) ?? []; rows.push(signal); index.set(signal.message_id, rows); }
    return index;
  }, [signals]);
  const selected = messages.filter(message => draft.messageIds.includes(message.id));
  return <section className="routing-payload-draft full-width" aria-label="Bearbeitbarer Payload-Entwurf">
    <header><h3>Payload-Entwurf bearbeiten</h3><span>Noch nicht in die Route übernommen</span></header>
    <ul>{draft.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
    {stale && <p role="alert">Quelle oder Empfänger wurden geändert. Bitte den Vorschlag neu erzeugen.</p>}
    <label htmlFor={id}>Datenbedarf des Entwurfs</label><textarea id={id} rows={2} value={draft.requirements.text} onChange={event => onChange({ ...draft, requirements: { ...draft.requirements, text: event.target.value } })} />
    <button type="button" className="button secondary" onClick={onRegenerate}>Vorschlag neu erzeugen</button>
    {selected.map(message => <section key={message.id} className="routing-draft-message">
      <header><strong>{message.name}</strong><button type="button" className="button secondary tiny" onClick={() => onChange({ ...draft, messageIds: draft.messageIds.filter(mid => mid !== message.id), signalIds: draft.signalIds.filter(sid => !(byMessage.get(message.id) ?? []).some(signal => signal.id === sid)) })}>Aus Entwurf entfernen</button></header>
      <p>{message.dlc ?? '?'} Byte · {message.cycle_ms ?? '?'} ms · {message.message_id_hex || 'Frame-ID offen'}</p>
      <div className="routing-draft-signals">{(byMessage.get(message.id) ?? []).map(signal => <label key={signal.id}>
        <input type="checkbox" checked={draft.signalIds.includes(signal.id)} onChange={() => onChange({ ...draft, signalIds: draft.signalIds.includes(signal.id) ? draft.signalIds.filter(sid => sid !== signal.id) : [...draft.signalIds, signal.id] })} />
        <span><strong>{signal.display_name || signal.name}</strong><small>{String(signal.semantic?.meaning || signal.description || '')}</small><small>{signalDomain(signal)} · {signal.length_bits ?? '?'} Bit · Startbit {signal.start_bit ?? '?'}</small></span>
      </label>)}</div>
    </section>)}
    <label>Weitere Nachricht ergänzen<select value="" onChange={event => { const mid = event.target.value; if (mid) onChange({ ...draft, messageIds: [...draft.messageIds, mid], signalIds: [...draft.signalIds, ...(byMessage.get(mid) ?? []).map(signal => signal.id)] }); }}>
      <option value="">Nachricht wählen …</option>{messages.filter(message => !draft.messageIds.includes(message.id) && message.direction !== 'rx').map(message => <option key={message.id} value={message.id}>{message.name} · {message.message_id_hex || message.id.slice(0, 8)} · {message.dlc ?? '?'} Byte</option>)}
    </select></label>
    <p>Die Signalmarkierung beschreibt den Datenbedarf. Die ganze Nachricht behält ihre gespeicherte Größe und Kodierung. Neue Inhalte oder eine kleinere Nachricht werden im Nachrichten-Wizard modelliert.</p>
    <a href={engineeringUrl} target="_blank" rel="noreferrer">Nachrichten-Wizard öffnen ↗</a>
    <footer><button type="button" className="button secondary" onClick={onDiscard}>Entwurf verwerfen</button><button type="button" className="button primary" disabled={stale || !selected.length} onClick={onApply}>Entwurf in Route übernehmen</button></footer>
  </section>;
}
