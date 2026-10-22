import type { DocumentIntakeProposal } from './engineering-agent.ts';

type DeviceRole = 'CONTROLLER' | 'GATEWAY' | 'SENSOR' | 'ACTUATOR';
type DocumentFact = DocumentIntakeProposal['interpretation']['components'][number];
export type DocumentDeviceQuestion = { id: string; label: string; role: DeviceRole | 'OTHER'; source_quote: string; source_context?: string[]; covered_by?: string[] };
export type ReviewedDocumentEquipment = {
  source_sha256?: string;
  source_text?: string;
  source_name?: string;
  source_chars?: number;
  facts?: DocumentFact[];
  function_assignments?: Record<string, string>;
  technologies?: DocumentIntakeProposal['interpretation']['technologies'];
  questions: DocumentDeviceQuestion[];
  excluded_questions?: string[];
  devices: { name: string; role: DeviceRole; quantity: number; source_quote: string; source_context?: string[]; minimum: boolean }[];
  answers: (DocumentDeviceQuestion & { role: DeviceRole; quantity: number; minimum: boolean; role_confirmed?: boolean; coverage_confirmed?: boolean })[];
};

const roles = new Set(['CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR']);
const questionRoles = new Set([...roles, 'OTHER']);
function questionIdentity(role: string, quote: string, label: string, context: string[] = []) {
  return `${role}:${quote}:${label}${context.length ? ':' + JSON.stringify(context) : ''}`;
}
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
  const add = (label: string, role: DeviceRole | 'OTHER', quote: string, context: string[] = []) => {
    label = label.trim();
    if (!label || !source.includes(quote)) return;
    const id = questionIdentity(role, quote, label, context);
    if (!result.some(item => item.id === id)) result.push({ id, label, role, source_quote: quote, ...(context.length ? { source_context: context } : {}) });
  };
  for (const line of source.split(/\r?\n/)) {
    const group = line.match(/^\s*(?:[-*]\s*)?(Sensorik|Aktorik|Sensor\s+types|Sensortypen|Actuator\s+types|Aktortypen)\s*[:(]\s*(.+?)\)?\s*$/iu);
    if (group) {
      const categories = proposal?.interpretation.components.filter(item => item.kind === 'CATEGORY' && item.source_quote === line.trim()) ?? [];
      // A complete native interpretation is authoritative. Partial/legacy
      // review inputs still retain source groups not assessed in their facts.
      if (proposal && !categories.length && (proposal.source_complete || proposal.interpretation.components.some(item => ['FUNCTION', 'REQUIREMENT'].includes(item.kind) && item.source_quote.includes(line.trim())))) continue;
      const role = /^sensor/iu.test(group[1]) ? 'SENSOR' : 'ACTUATOR';
      // Only explicit list members; no one-of-each assumption and no catalog.
      for (const label of group[2].split(/\s*[,;]\s*/)) {
        for (const category of categories.length ? categories : [undefined]) add(label, role, line.trim(), category?.source_context);
      }
    }
  }
  for (const item of proposal?.interpretation.components ?? []) {
    if (item.kind !== 'CATEGORY' || !questionRoles.has(item.role)) continue;
    if (result.some(question => item.source_quote === question.source_quote && JSON.stringify(question.source_context ?? []) === JSON.stringify(item.source_context ?? []))) continue;
    add(item.name, item.role as DeviceRole | 'OTHER', item.source_quote, item.source_context);
  }
  const instances = (proposal?.interpretation.components ?? []).filter(item => item.kind === 'INSTANCE' && roles.has(item.role));
  const normalize = (label: string) => label.toLocaleLowerCase().replace(/[^\p{L}\d]/gu, '');
  for (const question of result) {
    if (question.role === 'OTHER') continue;
    const group = question.source_quote.match(/\(([^)]+)\)/)?.[1];
    if (!group || /\bz\.\s*b\.|\be\.\s*g\.|\b(?:oder|or)\b/iu.test(group)) continue;
    const references: string[] = [];
    let complete = true;
    for (const member of group.split(/\s*[,/]\s*/)) {
      const token = normalize(member);
      const named = instances.filter(item => normalize(item.name).includes(token) && sameDocumentSystem(item.source_context, question.source_context));
      if (named.length) { references.push(...named.map(item => item.name)); continue; }
      // A class overview can refer to the separately enumerated sensor/actor
      // questions; these are references, never additional anonymous devices.
      const role = /^sensor(?:ecus?|controllers?|nodes?|knoten)$/u.test(token) ? 'SENSOR'
        : /^(?:aktor|aktuator|actuator)(?:ecus?|controllers?|nodes?|knoten)$/u.test(token) ? 'ACTUATOR' : null;
      const children = role ? result.filter(item => item.role === role && item.id !== question.id && sameDocumentSystem(item.source_context, question.source_context)) : [];
      if (children.length) references.push(...children.map(item => item.id));
      else { complete = false; break; }
    }
    if (complete && references.length) question.covered_by = [...new Set(references)];
  }
  return result;
}

/** Build inventory only from reviewed, literal facts and explicit user answers. */
export function reviewDocumentEquipment(source: string, proposal: DocumentIntakeProposal | null,
  values: Record<string, string>, minimum: boolean, roleAnswers: Record<string, string> = {}, functionAnswers: Record<string, string> = {}): ReviewedDocumentEquipment {
  const answers = documentDeviceQuestions(source, proposal).flatMap<ReviewedDocumentEquipment['answers'][number]>(question => {
    const value = values[question.id];
    if (value === undefined || value === '') return [];
    if (value === 'covered' && question.role !== 'OTHER' && question.covered_by?.length) return [{ ...question, role: question.role, quantity: 0, minimum: false, coverage_confirmed: true }];
    if (!/^\d+$/.test(value) || Number(value) > 1000) throw new Error(`Ungültige Anzahl für ${question.label}.`);
    if (question.role === 'OTHER' && value === '0') return [];
    const role = question.role === 'OTHER' ? roleAnswers[question.id] : question.role;
    if (!role || !roles.has(role)) throw new Error(`Geräteart für ${question.label} festlegen.`);
    return [{ ...question, role: role as DeviceRole, quantity: Number(value), minimum, ...(question.role === 'OTHER' ? { role_confirmed: true } : {}) }];
  });
  const devices = (proposal?.interpretation.components ?? []).flatMap(item => {
    if (item.kind !== 'INSTANCE' || !roles.has(item.role)) return [];
    if (!source.includes(item.source_quote) || !Number.isSafeInteger(item.quantity) || !item.quantity || item.quantity > 1000) {
      throw new Error('Der Gerätebefund hat keine belegte Identität oder Anzahl.');
    }
    return [{ name: item.name, role: item.role as DeviceRole, quantity: item.quantity, source_quote: item.source_quote, source_context: item.source_context, minimum: false }];
  });
  return { source_sha256: proposal?.source_sha256, questions: documentDeviceQuestions(source, proposal), devices, answers,
    excluded_questions: documentDeviceQuestions(source, proposal).filter(question => question.role === 'OTHER' && values[question.id] === '0').map(question => question.id),
    ...(proposal ? { source_text: source, source_name: proposal.source_name, source_chars: proposal.source_chars,
      function_assignments: Object.fromEntries(proposal.interpretation.components.filter(fact => fact.kind === 'FUNCTION')
        .map(fact => [documentFactIdentity(fact), functionAnswers[documentFactIdentity(fact)]?.trim() ?? '']).filter(([, host]) => host)),
      facts: structuredClone(proposal.interpretation.components), technologies: structuredClone(proposal.interpretation.technologies ?? []) } : {}) }; 
}

/** The normal wizard prompt carries the same reviewed input to its shared parser. */
export function readReviewedDocumentEquipment(source: string): ReviewedDocumentEquipment | undefined {
  const selected = [...source.matchAll(/^- Dokument-Geräte:\s*([^\r\n]+)$/gm)].at(-1);
  if (!selected) return;
  const raw = selected[1];
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object') throw new Error('Ungültige Dokument-Geräte.');
  const equipment = value as ReviewedDocumentEquipment;
  const position = selected.index ?? 0;
  const original = source.slice(0, position) + source.slice(position + selected[0].length);
  if (!Array.isArray(equipment.devices) || !Array.isArray(equipment.answers) || !Array.isArray(equipment.questions)) throw new Error('Unvollständige Dokument-Geräte.');
  if (equipment.facts !== undefined) {
    if (!Array.isArray(equipment.facts) || typeof equipment.source_text !== 'string') throw new Error('Unvollständige Dokumentbefunde.');
    for (const fact of equipment.facts) {
      if (!fact || typeof fact.name !== 'string' || !fact.name.trim() || !['INSTANCE', 'CATEGORY', 'FUNCTION', 'REQUIREMENT'].includes(fact.kind)
        || !questionRoles.has(fact.role) || typeof fact.source_quote !== 'string' || !fact.source_quote
        || !original.includes(fact.source_quote) || !equipment.source_text.includes(fact.source_quote)
        || (fact.source_context !== undefined && (!Array.isArray(fact.source_context) || fact.source_context.some(label => typeof label !== 'string' || !original.includes(label))))
        || (fact.kind !== 'INSTANCE' && fact.quantity !== null)
        || (['FUNCTION', 'REQUIREMENT'].includes(fact.kind) && fact.role !== 'OTHER')) throw new Error('Unbelegte strukturierte Dokumentbefunde.');
    }
    if (equipment.function_assignments !== undefined && (!equipment.function_assignments || typeof equipment.function_assignments !== 'object' || Array.isArray(equipment.function_assignments)
      || Object.entries(equipment.function_assignments).some(([id, host]) => typeof host !== 'string' || !host.trim() || !equipment.facts?.some(fact => fact.kind === 'FUNCTION' && documentFactIdentity(fact) === id)))) throw new Error('Unbelegte Funktionszuordnung.');
    if (!Array.isArray(equipment.technologies) || equipment.technologies.some(fact => typeof fact.source_quote !== 'string' || !fact.source_quote || !original.includes(fact.source_quote))) throw new Error('Unbelegte Dokument-Technikbefunde.');
  }
  for (const question of equipment.questions) {
    if (!questionRoles.has(question.role) || typeof question.source_quote !== 'string' || !question.source_quote
      || !original.includes(question.source_quote) || typeof question.label !== 'string' || !question.label.trim()
      || typeof question.id !== 'string' || question.id !== questionIdentity(question.role, question.source_quote, question.label, question.source_context)) {
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
  if (equipment.excluded_questions !== undefined && (!Array.isArray(equipment.excluded_questions) || equipment.excluded_questions.some(id => !equipment.questions.some(question => question.id === id && question.role === 'OTHER')))) throw new Error('Unbelegte ausgeschlossene Dokumentangabe.');
  for (const answer of equipment.answers) {
    const question = equipment.questions.find(question => question.id === answer.id && question.label === answer.label
      && (question.role === answer.role || (question.role === 'OTHER' && answer.role_confirmed && roles.has(answer.role))) && question.source_quote === answer.source_quote);
    if (!question) {
      throw new Error('Die Rückfrageantwort gehört nicht zur belegten Gerätegruppe.');
    }
    if (answer.coverage_confirmed && (!Array.isArray(answer.covered_by) || !answer.covered_by.length || answer.quantity !== 0
      || JSON.stringify([...answer.covered_by].sort()) !== JSON.stringify([...(question.covered_by ?? [])].sort())
      || !answer.covered_by.every(reference => equipment.devices.some(item => item.name === reference && sameDocumentSystem(item.source_context, answer.source_context))
        || equipment.questions.some(question => question.id === reference && question.id !== answer.id && sameDocumentSystem(question.source_context, answer.source_context))))) {
      throw new Error('Die Abdeckung der Gerätegruppe ist nicht belegt.');
    }
  }
  return equipment;
}

export function documentSourceScope(context: string[]) {
  if (!context.length) return [];
  const label = context.at(-1)!.replace(/^\d+(?:\.\d+)*[.)]?\s+/u, '').replace(/:\s*$/u, '').trim();
  return /^(?:Architektur|Architecture|Hardware(?:komponenten| components)?|Systemfunktionen|Funktionsbeschreibung|Functional description|Funktionen|Functions|Aufgaben|Responsibilities|(?:Referenz[- ]?)?Anforderungen|(?:Reference )?Requirements|Schnittstellen|Interfaces|Anschlüsse|Connections|Übersicht|Overview|Systemübersicht|System overview)$/iu.test(label) ? context.slice(0, -1) : [...context];
}

export function documentSystemScope(context: string[]) {
  const index = context.findIndex(label => {
    if (documentSourceScope([label]).length === 0) return true;
    const title = label.normalize('NFKC').replace(/[\u2010-\u2015\u2212]/g, '-').replace(/^\d+(?:\.\d+)*[.)]?\s+/u, '').replace(/:\s*$/u, '').trim();
    return /^(?:Systemstruktur(?:\s*\(Top-Level-Architektur\))?|System structure(?:\s*\(Top-Level Architecture\))?|Systemgrenzen(?: und Systemkontext)?|System boundaries(?: and System context)?|Systemkontext|System context|Zielbild der (?:E\/E[- ]?)?Architektur|Architecture (?:vision|target)|Target architecture|Domain[- ]Controller[- ]Design|Controller[- ]Design|(?:Elektronische|Elektrische|Mechanische|Software)\s*Domäne|(?:Electronic|Electrical|Mechanical|Software) domain)$/iu.test(title);
  });
  return index < 0 ? [...context] : context.slice(0, index);
}

function sameDocumentSystem(left: string[] = [], right: string[] = []) {
  return JSON.stringify(documentSystemScope(left)) === JSON.stringify(documentSystemScope(right));
}

function documentOwnerScopeMatches(owner: string[], fact: string[]) {
  const hostScope = documentSourceScope(owner), factScope = documentSourceScope(fact);
  return JSON.stringify(hostScope) === JSON.stringify(factScope)
    || (hostScope.length > 0 && hostScope.length < factScope.length && hostScope.every((label, index) => factScope[index] === label));
}

export function documentFactIdentity(fact: DocumentFact) {
  return JSON.stringify([fact.kind, fact.source_context ?? [], fact.source_quote, fact.name]);
}

/** Reuse only unique, literal responsibilities already scoped to real hosts. */
export function documentSourceFunctionAssignments(facts: DocumentFact[], owners: {
  name: string; source_context?: string[]; duties: { source_quote: string }[];
}[]) {
  const result: Record<string, string> = {};
  const functions = facts.filter(fact => fact.kind === 'FUNCTION');
  const scopedOwners = (fact: DocumentFact, requireContext = false) => {
    const sharedCitation = functions.some(other => other.name !== fact.name && other.source_quote === fact.source_quote && JSON.stringify(other.source_context ?? []) === JSON.stringify(fact.source_context ?? []));
    return owners.filter(owner => (!requireContext || Boolean(owner.source_context?.length))
      && documentOwnerScopeMatches(owner.source_context ?? [], fact.source_context ?? [])
      && owner.duties.some(duty => duty.source_quote.length >= 3 && fact.source_quote.includes(duty.source_quote) && (!sharedCitation || duty.source_quote.includes(fact.name))));
  };
  for (const fact of functions) {
    let names = [...new Set(scopedOwners(fact).map(owner => owner.name))];
    if (!names.length && fact.source_context?.length && fact.role === 'OTHER' && fact.quantity === null && fact.source_quote.includes(fact.name)) {
      // A chapter overview may repeat an individually declared responsibility.
      // Require an exact source subject and its scoped witness in this system;
      // never infer ownership from a substring, a sole host, or another profile.
      const witnesses = functions.filter(other => other.source_context?.length && other.name === fact.name && other.role === 'OTHER'
        && other.quantity === null && other.source_quote.includes(other.name)
        && sameDocumentSystem(other.source_context, fact.source_context));
      names = [...new Set(witnesses.flatMap(witness => scopedOwners(witness, true).map(owner => owner.name)))];
    }
    if (names.length === 1) result[documentFactIdentity(fact)] = names[0];
  }
  return result;
}

/** Equal labels in separate source systems remain separate participants. */
export function documentParticipantName(item: { source_context?: string[] }, name: string,
  peers: { source_context?: string[]; name?: string; label?: string }[]) {
  const contexts = [...new Map(peers.filter(peer => (peer.name ?? peer.label) === name)
    .map(peer => [JSON.stringify(peer.source_context ?? []), peer.source_context ?? []])).values()];
  const own = item.source_context ?? [];
  if (contexts.length < 2 || !own.length) return name;
  const identityPath = (context: string[]) => {
    const scope = documentSourceScope(context);
    return contexts.some(other => JSON.stringify(other) !== JSON.stringify(context)
      && JSON.stringify(documentSourceScope(other)) === JSON.stringify(scope)) ? context : scope;
  };
  const path = identityPath(own);
  const tokens = (context: string[]) => identityPath(context).map(label => label.match(/^\d+(?:\.\d+)*/)?.[0] ?? label);
  const ownTokens = tokens(own);
  for (let width = 1; width <= ownTokens.length; width += 1) {
    const suffix = ownTokens.slice(-width).join('/');
    if (!contexts.some(other => JSON.stringify(other) !== JSON.stringify(own) && tokens(other).slice(-width).join('/') === suffix)) return `${name} [${suffix}]`;
  }
  return `${name} [${JSON.stringify(path)}]`;
}

/** Counts describe source facts; they never confirm hardware quantities. */
export function documentEvidenceCounts(equipment: ReviewedDocumentEquipment) {
  const facts = equipment.facts ?? [];
  const requirements = facts.filter(item => item.kind === 'REQUIREMENT');
  // Normalize only the comparison key; literal quotes remain untouched.
  const ids = new Set(requirements.flatMap(item => item.source_quote.normalize('NFKC').replace(/[\u2010-\u2015\u2212\ufe63\uff0d]/g, '-').match(/\bREQ[-_][\w-]+/g) ?? []));
  return { devices: facts.filter(item => item.kind === 'INSTANCE' || item.kind === 'CATEGORY').length,
    functions: facts.filter(item => item.kind === 'FUNCTION').length,
    requirements: requirements.length, requirementIds: ids.size, total: facts.length };
}
