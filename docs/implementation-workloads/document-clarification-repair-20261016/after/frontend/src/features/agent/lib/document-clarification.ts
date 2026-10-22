import type { DocumentIntakeProposal } from './engineering-agent.ts';

type DeviceRole = 'CONTROLLER' | 'GATEWAY' | 'SENSOR' | 'ACTUATOR';
export type DocumentDeviceQuestion = { id: string; label: string; role: DeviceRole; source_quote: string; covered_by?: string[] };
export type ReviewedDocumentEquipment = {
  source_sha256?: string;
  questions: DocumentDeviceQuestion[];
  devices: { name: string; role: DeviceRole; quantity: number; source_quote: string; minimum: boolean }[];
  answers: (DocumentDeviceQuestion & { quantity: number; minimum: boolean; coverage_confirmed?: boolean })[];
};

const roles = new Set(['CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR']);
export const DOCUMENT_EQUIPMENT_MARKER = '- Dokument-Geräte: ';

/** Review selections do not change the original document submitted to Qwen. */
export function documentReviewSource(source: string) {
  return source.replace(/^- (?:Sensor-Messgrößen|Aktor-Befehle|Geräteanschlüsse|Gerätezuordnungen|Geräte-Spezifikationen|Dokument-Geräte):[^\r\n]*(?:\r?\n|$)/gm, '').trim();
}

/** Strip wizard selections only from the editable description, never files. */
export function documentRequestSource(description: string, attachments: string[]) {
  return `${documentReviewSource(description)}\n${attachments.join('\n')}`;
}

export function documentDeviceQuestions(source: string, proposal?: DocumentIntakeProposal | null): DocumentDeviceQuestion[] {
  const result: DocumentDeviceQuestion[] = [];
  const add = (label: string, role: DeviceRole, quote: string) => {
    label = label.trim();
    if (!label || !source.includes(quote)) return;
    const id = `${role}:${quote}:${label}`;
    if (!result.some(item => item.id === id)) result.push({ id, label, role, source_quote: quote });
  };
  for (const line of source.split(/\r?\n/)) {
    const group = line.match(/^\s*(?:[-*]\s*)?(Sensorik|Aktorik|Sensor\s+types|Sensortypen|Actuator\s+types|Aktortypen)\s*[:(]\s*(.+?)\)?\s*$/iu);
    if (group) {
      const role = /^sensor/iu.test(group[1]) ? 'SENSOR' : 'ACTUATOR';
      // Only explicit list members; no one-of-each assumption and no catalog.
      for (const label of group[2].split(/\s*[,;]\s*/)) add(label, role, line.trim());
    }
  }
  for (const item of proposal?.interpretation.components ?? []) {
    if (item.kind !== 'CATEGORY' || !roles.has(item.role)) continue;
    if (result.some(question => item.source_quote.includes(question.source_quote))) continue;
    add(item.name, item.role as DeviceRole, item.source_quote);
  }
  const instances = (proposal?.interpretation.components ?? []).filter(item => item.kind === 'INSTANCE' && roles.has(item.role));
  const normalize = (label: string) => label.toLocaleLowerCase().replace(/[^\p{L}\d]/gu, '');
  for (const question of result) {
    const group = question.source_quote.match(/\(([^)]+)\)/)?.[1];
    if (!group || /\bz\.\s*b\.|\be\.\s*g\.|\b(?:oder|or)\b/iu.test(group)) continue;
    const references: string[] = [];
    let complete = true;
    for (const member of group.split(/\s*[,/]\s*/)) {
      const token = normalize(member);
      const named = instances.filter(item => normalize(item.name).includes(token));
      if (named.length) { references.push(...named.map(item => item.name)); continue; }
      // A class overview can refer to the separately enumerated sensor/actor
      // questions; these are references, never additional anonymous devices.
      const role = /^sensor(?:ecus?|controllers?|nodes?|knoten)$/u.test(token) ? 'SENSOR'
        : /^(?:aktor|aktuator|actuator)(?:ecus?|controllers?|nodes?|knoten)$/u.test(token) ? 'ACTUATOR' : null;
      const children = role ? result.filter(item => item.role === role && item.id !== question.id) : [];
      if (children.length) references.push(...children.map(item => item.id));
      else { complete = false; break; }
    }
    if (complete && references.length) question.covered_by = [...new Set(references)];
  }
  return result;
}

/** Build inventory only from reviewed, literal facts and explicit user answers. */
export function reviewDocumentEquipment(source: string, proposal: DocumentIntakeProposal | null,
  values: Record<string, string>, minimum: boolean): ReviewedDocumentEquipment {
  const answers = documentDeviceQuestions(source, proposal).flatMap(question => {
    const value = values[question.id];
    if (value === undefined || value === '') return [];
    if (value === 'covered' && question.covered_by?.length) return [{ ...question, quantity: 0, minimum: false, coverage_confirmed: true }];
    if (!/^\d+$/.test(value) || Number(value) > 1000) throw new Error(`Ungültige Anzahl für ${question.label}.`);
    return [{ ...question, quantity: Number(value), minimum }];
  });
  const devices = (proposal?.interpretation.components ?? []).flatMap(item => {
    if (item.kind !== 'INSTANCE' || !roles.has(item.role)) return [];
    if (!source.includes(item.source_quote) || !Number.isSafeInteger(item.quantity) || !item.quantity || item.quantity > 1000) {
      throw new Error('Der Gerätebefund hat keine belegte Identität oder Anzahl.');
    }
    return [{ name: item.name, role: item.role as DeviceRole, quantity: item.quantity, source_quote: item.source_quote, minimum: false }];
  });
  return { source_sha256: proposal?.source_sha256, questions: documentDeviceQuestions(source, proposal), devices, answers };
}

/** The normal wizard prompt carries the same reviewed input to its shared parser. */
export function readReviewedDocumentEquipment(source: string): ReviewedDocumentEquipment | undefined {
  const raw = source.match(/^- Dokument-Geräte:\s*([^\r\n]+)$/m)?.[1];
  if (!raw) return;
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object') throw new Error('Ungültige Dokument-Geräte.');
  const equipment = value as ReviewedDocumentEquipment;
  const original = source.replace(/^- Dokument-Geräte:[^\r\n]*$/gm, '');
  if (!Array.isArray(equipment.devices) || !Array.isArray(equipment.answers) || !Array.isArray(equipment.questions)) throw new Error('Unvollständige Dokument-Geräte.');
  for (const question of equipment.questions) {
    if (!roles.has(question.role) || typeof question.source_quote !== 'string' || !question.source_quote
      || !original.includes(question.source_quote) || typeof question.label !== 'string' || !question.label.trim()
      || typeof question.id !== 'string' || question.id !== `${question.role}:${question.source_quote}:${question.label}`) {
      throw new Error('Unbelegte Dokument-Rückfrage.');
    }
    if (question.covered_by !== undefined && (!Array.isArray(question.covered_by)
      || question.covered_by.some(reference => typeof reference !== 'string' || !reference))) {
      throw new Error('Ungültige Abdeckungsreferenzen der Gerätegruppe.');
    }
  }
  for (const item of [...equipment.devices, ...equipment.answers]) {
    if (!roles.has(item.role) || !Number.isSafeInteger(item.quantity) || item.quantity < 0 || item.quantity > 1000
      || typeof item.source_quote !== 'string' || !item.source_quote || !original.includes(item.source_quote)
      || typeof item.minimum !== 'boolean') throw new Error('Unbelegte Dokument-Geräte oder ungültige Rückfrageantwort.');
    const label = 'name' in item ? item.name : item.label;
    if (typeof label !== 'string' || !label.trim() || label.length > 120) throw new Error('Ungültiger Gerätename.');
  }
  for (const answer of equipment.answers) {
    const question = equipment.questions.find(question => question.id === answer.id && question.label === answer.label
      && question.role === answer.role && question.source_quote === answer.source_quote);
    if (!question) {
      throw new Error('Die Rückfrageantwort gehört nicht zur belegten Gerätegruppe.');
    }
    if (answer.coverage_confirmed && (!Array.isArray(answer.covered_by) || !answer.covered_by.length || answer.quantity !== 0
      || JSON.stringify([...answer.covered_by].sort()) !== JSON.stringify([...(question.covered_by ?? [])].sort())
      || !answer.covered_by.every(reference => equipment.devices.some(item => item.name === reference)
        || equipment.questions.some(question => question.id === reference && question.id !== answer.id)))) {
      throw new Error('Die Abdeckung der Gerätegruppe ist nicht belegt.');
    }
  }
  return equipment;
}
