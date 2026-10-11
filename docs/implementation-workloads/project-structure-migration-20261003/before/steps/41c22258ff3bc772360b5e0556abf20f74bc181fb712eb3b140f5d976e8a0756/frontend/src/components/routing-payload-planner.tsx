'use client';

import { useId, useMemo } from 'react';
import type { EngSignal } from '@/lib/types';
import type { ScopedMessage } from '@/lib/routing-payload-scope';
import { PAYLOAD_NEEDS, payloadCandidates, signalDomain, type PayloadNeedKind, type PayloadRequirements } from '@/lib/routing-payload-needs';

export function RoutingPayloadPlanner({ source, targets, messages, signals, requirements, onRequirements, messageIds, signalIds, onUse, onRemove, onSignal, onPropose, engineeringUrl }: {
  source: string; targets: string; messages: ScopedMessage[]; signals: EngSignal[]; requirements: PayloadRequirements;
  onRequirements: (next: PayloadRequirements) => void; messageIds: string[]; signalIds: string[];
  onUse: (messageId: string, signalIds: string[]) => void; onRemove: (id: string) => void; onSignal: (id: string) => void; onPropose: () => void; engineeringUrl: string;
}) {
  const id = useId();
  const candidates = useMemo(() => payloadCandidates(messages, signals, requirements), [messages, signals, requirements]);
  const selected = messages.filter(m => messageIds.includes(m.id) || signals.some(s => s.message_id === m.id && signalIds.includes(s.id)));
  return <section className="routing-payload-planner full-width" aria-label="Payload gemeinsam festlegen">
    <header><h3>Welche Daten benötigt {targets || 'der Empfänger'} von {source}?</h3><p>Beschreibe den Datenbedarf oder wähle eine Informationsart. Die Vorschläge zeigen vorhandene Nachrichten und ihre modellierten Signale.</p></header>
    <label htmlFor={id}>Benötigte Informationen</label>
    <textarea id={id} value={requirements.text} onChange={e => onRequirements({ ...requirements, text: e.target.value })} placeholder="Zum Beispiel: an, aus und Fehler — oder Temperatur" rows={2} />
    <fieldset><legend>Informationsarten</legend>{(Object.entries(PAYLOAD_NEEDS) as [PayloadNeedKind, string][]).map(([key, label]) => <label key={key}>
      <input type="checkbox" checked={requirements.categories.includes(key)} onChange={() => onRequirements({ ...requirements, categories: requirements.categories.includes(key) ? requirements.categories.filter(k => k !== key) : [...requirements.categories, key] })} />{label}
    </label>)}</fieldset>
    <button type="button" className="button primary routing-payload-propose" onClick={onPropose}>Payload-Entwurf erzeugen</button>
    <div className="routing-payload-results-heading"><strong>Vorschläge aus dem Modell · {candidates.length}</strong><button className="button secondary tiny" type="button" onClick={() => onRequirements({ text: '', categories: [] })}>Alle geeigneten Nachrichten zeigen</button></div>
    <p className="routing-payload-help">Die Suche verwendet Bedeutung, Signalnamen und hinterlegte Werte. Prüfe, ob diese Informationen den Bedarf erfüllen. Lokale Sensor-/Aktordaten anderer Empfänger sind ausgeschlossen.</p>
    <div className="routing-payload-candidates">
      {candidates.map(({ message, allSignals, matchedSignals, missingCategories }) => <article key={message.id} className={messageIds.includes(message.id) ? 'selected' : ''} aria-label={`Payload-Vorschlag ${message.name}`}>
        <header><div><h4>{message.name}</h4><span>{message.dlc ?? '?'} Byte · {message.cycle_ms != null ? `${message.cycle_ms} ms` : 'Zyklus offen'} · {allSignals.length} modellierte Signale</span></div><button className="button primary tiny" type="button" onClick={() => onUse(message.id, matchedSignals.map(s => s.id))}>Vorschlag übernehmen</button></header>
        {!allSignals.length && <p>Zu dieser Nachricht sind noch keine Signale modelliert. Inhalt im Engineering klären.</p>}
        {missingCategories.length > 0 && <p>Teilvorschlag. Zusätzlich benötigt: {missingCategories.map(k => PAYLOAD_NEEDS[k]).join(', ')}.</p>}
        <ul>{allSignals.map(signal => <li key={signal.id} className={matchedSignals.includes(signal) ? 'matches' : ''}>
          <div><strong>{signal.display_name || signal.name}</strong><span>{String(signal.semantic?.meaning || signal.description || 'Bedeutung noch nicht beschrieben')}</span></div>
          <small>{signalDomain(signal)}</small><small>{signal.length_bits ?? '?'} Bit · Startbit {signal.start_bit ?? '?'}{matchedSignals.includes(signal) ? ' · Suchtreffer' : ' · Weiterer Inhalt der Nachricht'}</small>
        </li>)}</ul>
      </article>)}
    </div>
    {!candidates.length && <div className="notice warning" role="status"><strong>Kein passender Inhalt im vorhandenen Modell gefunden.</strong><p>Beschreibe die fehlende Information im Nachrichten-Wizard, einschließlich Bedeutung, Wertebereich und benötigter Aktualisierung. Vorhandene Nachrichten werden durch die Suche nicht verändert.</p><a className="button secondary" href={engineeringUrl} target="_blank" rel="noreferrer">Nachrichten-Wizard öffnen ↗</a></div>}
    <section className="routing-payload-selection" aria-label="Gewählter Payload"><h4>Gewählter Payload · {selected.length} Nachrichten</h4>
      {!selected.length && <p>Noch kein Vorschlag übernommen. Wähle zuerst den benötigten Inhalt.</p>}
      {selected.map(message => <div key={message.id}><header><strong>{message.name}</strong><button className="button secondary tiny" type="button" onClick={() => onRemove(message.id)}>Nachricht entfernen</button></header>
        <div className="routing-payload-signals">{signals.filter(s => s.message_id === message.id).map(signal => <label key={signal.id}><input type="checkbox" checked={signalIds.includes(signal.id)} onChange={() => onSignal(signal.id)} /><span>{signal.display_name || signal.name}<small>{String(signal.semantic?.meaning || signal.description || '')} · {signalDomain(signal)}</small></span></label>)}</div>
      </div>)}
      <p className="routing-payload-help">Die Signalmarkierung beschreibt den Bedarf. Übertragen und bei der Buslast gezählt wird die ganze Nachricht mit ihrer gespeicherten Größe. Für weniger übertragene Daten muss eine eigene Nachricht modelliert werden.</p>
    </section>
  </section>;
}
