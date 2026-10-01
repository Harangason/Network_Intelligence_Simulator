import type { EngSignal } from './types';
import type { ScopedMessage } from './routing-payload-scope';

export const PAYLOAD_NEEDS = {
  state: 'Betriebszustand / Betriebsart',
  health: 'Fehler / Gesundheit / Qualität',
  measurement: 'Messwerte',
  command: 'Sollwerte / Befehle',
} as const;
export type PayloadNeedKind = keyof typeof PAYLOAD_NEEDS;
export type PayloadRequirements = { text: string; categories: PayloadNeedKind[] };
export type PayloadDraft = { messageIds: string[]; signalIds: string[]; requirements: PayloadRequirements; reasons: string[]; contextKey: string };
const normalize = (text: string) => text.toLocaleLowerCase('de').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ß/g, 'ss');
const record = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};

export function readPayloadRequirements(value: unknown): PayloadRequirements {
  const data = record(value);
  return { text: typeof data.text === 'string' ? data.text : '', categories: Array.isArray(data.categories)
    ? [...new Set(data.categories.filter((k): k is PayloadNeedKind => typeof k === 'string' && Object.hasOwn(PAYLOAD_NEEDS, k)))] : [] };
}

export function signalPurpose(signal: EngSignal): PayloadNeedKind | null {
  const role = String(signal.configuration?.generation_role ?? '').toUpperCase();
  const meaning = normalize(String(signal.semantic?.meaning ?? ''));
  const type = String(signal.semantic?.semantic_type ?? '').toUpperCase();
  const unit = normalize(signal.unit ?? '');
  if (role === 'COMMAND' || /sollwert|stellbefehl/.test(meaning)) return 'command';
  // A physical value remains a measurement even if its display name contains Status.
  if (unit && !['code', 'count', '%', 'bool', 'boolean', '1', '-'].includes(unit)) return 'measurement';
  if (['HEALTH', 'QUALITY'].includes(role) || /diagnosezustand|datenqualit|gesundheit|fehlerzustand/.test(meaning)) return 'health';
  if (['MODE', 'STATUS', 'STATE', 'DEVICE_STATUS'].includes(role) || type === 'STATE' || /betriebszustand|betriebsart/.test(meaning)) return 'state';
  if (['MEASUREMENT', 'FEEDBACK', 'EXECUTION_FEEDBACK'].includes(role) || type === 'NUMERIC') return 'measurement';
  return null;
}

export function signalDomain(signal: EngSignal) {
  const data = signal.data ?? {}, config = signal.configuration ?? {};
  const values = record(data.enum_values ?? config.enum_values);
  const enums = Object.entries(values).map(([label, code]) => `${label} = ${String(code)}`).join(' · ');
  const min = signal.min_value ?? data.minimum, max = signal.max_value ?? data.maximum;
  const range = min != null && max != null ? `${String(min)} … ${String(max)}${signal.unit ? ` ${signal.unit}` : ''}` : signal.unit || 'Wertebereich nicht angegeben';
  return enums || range;
}

const aliases: Record<string, string[]> = {
  an: ['an', 'on', 'active', 'aktiv'], aus: ['aus', 'off', 'inaktiv'],
  fehler: ['fehler', 'error', 'failed', 'health', 'diagnose'], error: ['error', 'fehler', 'failed'],
  zustand: ['zustand', 'status', 'state'], betriebsart: ['betriebsart', 'mode'],
  temperatur: ['temperatur', 'temperature', 'temp'], gesund: ['gesund', 'health', 'ok'],
};
const stopwords = new Set(['ich', 'wir', 'brauche', 'benotige', 'benotigt', 'soll', 'nur', 'bitte', 'daten', 'signal', 'signale', 'der', 'die', 'das', 'den', 'dem', 'ein', 'eine', 'und', 'oder', 'von', 'fur', 'mit', 'zum', 'zur', 'ubertragen']);
const searchableSignal = (s: EngSignal) => normalize([s.name, s.display_name, s.description, s.semantic?.meaning, s.semantic?.semantic_type, s.unit, signalDomain(s)].filter(Boolean).join(' '));

/** Search hints only; never synthesizes a signal, encoding, recipient or smaller frame. */
export function payloadCandidates(messages: ScopedMessage[], signals: EngSignal[], requirements: PayloadRequirements) {
  const terms = normalize(requirements.text).split(/[^a-z0-9_%]+/).filter(t => t && !stopwords.has(t));
  const groups = terms.map(t => aliases[t] ?? [t]);
  const byMessage = new Map<string, EngSignal[]>();
  for (const signal of signals) if (signal.message_id) {
    const rows = byMessage.get(signal.message_id) ?? []; rows.push(signal); byMessage.set(signal.message_id, rows);
  }
  return messages.map(message => {
    const allSignals = byMessage.get(message.id) ?? [];
    const signalTexts = allSignals.map(searchableSignal);
    const messageText = normalize(`${message.name} ${message.description ?? ''}`);
    const matchesText = groups.every(group => group.some(term => [messageText, ...signalTexts].some(text => text.includes(term))));
    const missingCategories = requirements.categories.filter(kind => !allSignals.some(s => signalPurpose(s) === kind));
    const matchedSignals = allSignals.filter((s, index) => {
      const purpose = signalPurpose(s);
      return (!requirements.categories.length || (purpose && requirements.categories.includes(purpose)))
        && (!groups.length || groups.some(group => group.some(term => signalTexts[index].includes(term))) || groups.every(group => group.some(term => messageText.includes(term))));
    });
    return { message, allSignals, matchedSignals, missingCategories, matches: matchesText && (!requirements.categories.length || missingCategories.length < requirements.categories.length) };
  }).filter(c => c.matches).sort((a, b) => b.matchedSignals.length - a.matchedSignals.length || a.message.name.localeCompare(b.message.name, 'de'));
}

export function proposePayload(messages: ScopedMessage[], signals: EngSignal[], requirements: PayloadRequirements, sourceInterfaceId: string, selectedIds: string[], contextKey: string): PayloadDraft {
  const candidates = payloadCandidates(messages.filter(m => m.direction !== 'rx'), signals, requirements)
    .filter(candidate => candidate.allSignals.length > 0)
    .sort((a, b) => Number(selectedIds.includes(b.message.id)) - Number(selectedIds.includes(a.message.id))
      || Number(b.message.interface_id === sourceInterfaceId) - Number(a.message.interface_id === sourceInterfaceId)
      || Number(b.message.routingScope?.scope === 'FUNCTION_OUTPUT') - Number(a.message.routingScope?.scope === 'FUNCTION_OUTPUT')
      || b.matchedSignals.length - a.matchedSignals.length || a.message.id.localeCompare(b.message.id));
  const chosen: typeof candidates = [];
  const uncovered = new Set(requirements.categories);
  for (const candidate of candidates) {
    if (chosen.length && (!uncovered.size || !candidate.matchedSignals.some(s => { const kind = signalPurpose(s); return kind && uncovered.has(kind); }))) continue;
    chosen.push(candidate);
    for (const signal of candidate.matchedSignals) { const kind = signalPurpose(signal); if (kind) uncovered.delete(kind); }
  }
  const signalIds = chosen.flatMap(candidate => {
    if (requirements.text.trim() || requirements.categories.length) return candidate.matchedSignals.map(s => s.id);
    const outputs = candidate.message.routingScope?.scope === 'FUNCTION_OUTPUT'
      ? candidate.allSignals.filter(s => ['state', 'health'].includes(signalPurpose(s) ?? '')) : [];
    return (outputs.length ? outputs : candidate.allSignals).map(s => s.id);
  });
  return { messageIds: chosen.map(candidate => candidate.message.id), signalIds,
    requirements: { text: requirements.text, categories: [...requirements.categories] }, contextKey,
    reasons: chosen.length ? [
      'Vorhandene Nachrichten des Senders, passend zur aktuellen Empfängerauswahl.',
      requirements.text.trim() || requirements.categories.length ? 'Signalauswahl aus dem beschriebenen Datenbedarf.' : 'Startentwurf: vorhandene Zustands- und Gesundheitsdaten bei Funktionsausgängen; Datenbedarf bitte prüfen.',
      ...(uncovered.size ? [`Noch offen: ${[...uncovered].map(kind => PAYLOAD_NEEDS[kind]).join(', ')}.`] : []),
    ] : ['Für diesen Bedarf ist noch kein passender modellierter Signalinhaltsvorschlag verfügbar. Nachricht im Engineering anlegen oder den Datenbedarf präzisieren.'] };
}
