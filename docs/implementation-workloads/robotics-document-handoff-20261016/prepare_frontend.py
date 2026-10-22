"""Extend the existing reviewed-document contract in staged copies only."""
from pathlib import Path

OUT = Path(__file__).parent


def change(path, transform):
    original = (OUT / 'before' / path).read_text(encoding='utf-8')
    (OUT / 'staged' / path).write_text(transform(original), encoding='utf-8')


def replace(text, old, new):
    assert text.count(old) == 1, (old[:100], text.count(old))
    return text.replace(old, new)


def clarification(text):
    text = replace(text, "type DeviceRole = 'CONTROLLER' | 'GATEWAY' | 'SENSOR' | 'ACTUATOR';", "type DeviceRole = 'CONTROLLER' | 'GATEWAY' | 'SENSOR' | 'ACTUATOR';\ntype DocumentFact = DocumentIntakeProposal['interpretation']['components'][number];")
    text = replace(text, "role: DeviceRole; source_quote: string; covered_by?: string[]", "role: DeviceRole | 'OTHER'; source_quote: string; source_context?: string[]; covered_by?: string[]")
    text = replace(text, "  source_sha256?: string;\n", "  source_sha256?: string;\n  source_text?: string;\n  source_name?: string;\n  source_chars?: number;\n  facts?: DocumentFact[];\n  technologies?: DocumentIntakeProposal['interpretation']['technologies'];\n")
    text = replace(text, "  questions: DocumentDeviceQuestion[];", "  questions: DocumentDeviceQuestion[];\n  excluded_questions?: string[];")
    text = replace(text, "source_quote: string; minimum: boolean }[];", "source_quote: string; source_context?: string[]; minimum: boolean }[];")
    text = replace(text, "quantity: number; minimum: boolean; coverage_confirmed?: boolean", "quantity: number; minimum: boolean; role_confirmed?: boolean; coverage_confirmed?: boolean")
    text = replace(text, "answers: (DocumentDeviceQuestion & { quantity:", "answers: (DocumentDeviceQuestion & { role: DeviceRole; quantity:")
    text = replace(text, "const roles = new Set(['CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR']);", "const roles = new Set(['CONTROLLER', 'GATEWAY', 'SENSOR', 'ACTUATOR']);\nconst questionRoles = new Set([...roles, 'OTHER']);\nfunction questionIdentity(role: string, quote: string, label: string, context: string[] = []) {\n  return `${role}:${quote}:${label}${context.length ? ':' + JSON.stringify(context) : ''}`;\n}")
    text = replace(text, "const add = (label: string, role: DeviceRole, quote: string) =>", "const add = (label: string, role: DeviceRole | 'OTHER', quote: string, context: string[] = []) =>")
    text = replace(text, "const id = `${role}:${quote}:${label}`;", "const id = questionIdentity(role, quote, label, context);")
    text = replace(text, "result.push({ id, label, role, source_quote: quote });", "result.push({ id, label, role, source_quote: quote, ...(context.length ? { source_context: context } : {}) });")
    text = replace(text, "    if (group) {\n      const role =", "    if (group) {\n      const categories = proposal?.interpretation.components.filter(item => item.kind === 'CATEGORY' && item.source_quote === line.trim()) ?? [];\n      // A complete native interpretation is authoritative. Partial/legacy\n      // review inputs still retain source groups not assessed in their facts.\n      if (proposal && !categories.length && (proposal.source_complete || proposal.interpretation.components.some(item => ['FUNCTION', 'REQUIREMENT'].includes(item.kind) && item.source_quote.includes(line.trim())))) continue;\n      const role =")
    text = replace(text, "for (const label of group[2].split(/\\s*[,;]\\s*/)) add(label, role, line.trim());", "for (const label of group[2].split(/\\s*[,;]\\s*/)) {\n        for (const category of categories.length ? categories : [undefined]) add(label, role, line.trim(), category?.source_context);\n      }")
    text = replace(text, "    if (item.kind !== 'CATEGORY' || !roles.has(item.role)) continue;", "    if (item.kind !== 'CATEGORY' || !questionRoles.has(item.role)) continue;")
    text = replace(text, "    if (result.some(question => item.source_quote.includes(question.source_quote))) continue;\n    add(item.name, item.role as DeviceRole, item.source_quote);", "    if (result.some(question => item.source_quote.includes(question.source_quote) && JSON.stringify(question.source_context ?? []) === JSON.stringify(item.source_context ?? []))) continue;\n    add(item.name, item.role as DeviceRole | 'OTHER', item.source_quote, item.source_context);")
    text = replace(text, "    const group = question.source_quote.match", "    if (question.role === 'OTHER') continue;\n    const group = question.source_quote.match")
    text = replace(text, "instances.filter(item => normalize(item.name).includes(token))", "instances.filter(item => normalize(item.name).includes(token) && JSON.stringify(item.source_context ?? []) === JSON.stringify(question.source_context ?? []))")
    text = replace(text, "result.filter(item => item.role === role && item.id !== question.id)", "result.filter(item => item.role === role && item.id !== question.id && JSON.stringify(item.source_context ?? []) === JSON.stringify(question.source_context ?? []))")
    text = replace(text, "values: Record<string, string>, minimum: boolean): ReviewedDocumentEquipment", "values: Record<string, string>, minimum: boolean, roleAnswers: Record<string, string> = {}): ReviewedDocumentEquipment")
    text = replace(text, "documentDeviceQuestions(source, proposal).flatMap(question =>", "documentDeviceQuestions(source, proposal).flatMap<ReviewedDocumentEquipment['answers'][number]>(question =>")
    text = replace(text, "if (value === 'covered' && question.covered_by?.length)", "if (value === 'covered' && question.role !== 'OTHER' && question.covered_by?.length)")
    text = replace(text, "return [{ ...question, quantity: 0, minimum: false, coverage_confirmed: true }]", "return [{ ...question, role: question.role, quantity: 0, minimum: false, coverage_confirmed: true }]")
    text = replace(text, "    return [{ ...question, quantity: Number(value), minimum }];", "    if (question.role === 'OTHER' && value === '0') return [];\n    const role = question.role === 'OTHER' ? roleAnswers[question.id] : question.role;\n    if (!role || !roles.has(role)) throw new Error(`Geräteart für ${question.label} festlegen.`);\n    return [{ ...question, role: role as DeviceRole, quantity: Number(value), minimum, ...(question.role === 'OTHER' ? { role_confirmed: true } : {}) }];")
    text = replace(text, "return [{ name: item.name, role: item.role as DeviceRole, quantity: item.quantity, source_quote: item.source_quote, minimum: false }];", "return [{ name: item.name, role: item.role as DeviceRole, quantity: item.quantity, source_quote: item.source_quote, source_context: item.source_context, minimum: false }];")
    text = replace(text, "  return { source_sha256: proposal?.source_sha256, questions: documentDeviceQuestions(source, proposal), devices, answers };", "  return { source_sha256: proposal?.source_sha256, questions: documentDeviceQuestions(source, proposal), devices, answers,\n    excluded_questions: documentDeviceQuestions(source, proposal).filter(question => question.role === 'OTHER' && values[question.id] === '0').map(question => question.id),\n    ...(proposal ? { source_text: source, source_name: proposal.source_name, source_chars: proposal.source_chars,\n      facts: structuredClone(proposal.interpretation.components), technologies: structuredClone(proposal.interpretation.technologies ?? []) } : {}) }; ")
    text = replace(text, "  for (const question of equipment.questions) {\n    if (!roles.has(question.role)", "  if (equipment.facts !== undefined) {\n    if (!Array.isArray(equipment.facts) || typeof equipment.source_text !== 'string') throw new Error('Unvollständige Dokumentbefunde.');\n    for (const fact of equipment.facts) {\n      if (!fact || typeof fact.name !== 'string' || !fact.name.trim() || !['INSTANCE', 'CATEGORY', 'FUNCTION', 'REQUIREMENT'].includes(fact.kind)\n        || !questionRoles.has(fact.role) || typeof fact.source_quote !== 'string' || !fact.source_quote\n        || !original.includes(fact.source_quote) || !equipment.source_text.includes(fact.source_quote)\n        || (fact.source_context !== undefined && (!Array.isArray(fact.source_context) || fact.source_context.some(label => typeof label !== 'string' || !original.includes(label))))\n        || (fact.kind !== 'INSTANCE' && fact.quantity !== null)\n        || (['FUNCTION', 'REQUIREMENT'].includes(fact.kind) && fact.role !== 'OTHER')) throw new Error('Unbelegte strukturierte Dokumentbefunde.');\n    }\n    if (!Array.isArray(equipment.technologies) || equipment.technologies.some(fact => typeof fact.source_quote !== 'string' || !fact.source_quote || !original.includes(fact.source_quote))) throw new Error('Unbelegte Dokument-Technikbefunde.');\n  }\n  for (const question of equipment.questions) {\n    if (!questionRoles.has(question.role)")
    text = replace(text, "  const raw = source.match(/^- Dokument-Geräte:\\s*([^\\r\\n]+)$/m)?.[1];\n  if (!raw) return;", "  const selected = [...source.matchAll(/^- Dokument-Geräte:\\s*([^\\r\\n]+)$/gm)].at(-1);\n  if (!selected) return;\n  const raw = selected[1];")
    text = replace(text, "  const original = source.replace(/^- Dokument-Geräte:[^\\r\\n]*$/gm, '');", "  const position = selected.index ?? 0;\n  const original = source.slice(0, position) + source.slice(position + selected[0].length);")
    text = replace(text, "question.id !== `${question.role}:${question.source_quote}:${question.label}`", "question.id !== questionIdentity(question.role, question.source_quote, question.label, question.source_context)")
    text = replace(text, "  for (const answer of equipment.answers) {", "  if (equipment.excluded_questions !== undefined && (!Array.isArray(equipment.excluded_questions) || equipment.excluded_questions.some(id => !equipment.questions.some(question => question.id === id && question.role === 'OTHER')))) throw new Error('Unbelegte ausgeschlossene Dokumentangabe.');\n  for (const answer of equipment.answers) {")
    text = replace(text, "question.role === answer.role && question.source_quote === answer.source_quote", "(question.role === answer.role || (question.role === 'OTHER' && answer.role_confirmed && roles.has(answer.role))) && question.source_quote === answer.source_quote")
    # This makes the typed source payload reviewable throughout the Wizard.
    text += '''
/** Equal labels in separate source systems remain separate participants. */
export function documentParticipantName(item: { source_context?: string[] }, name: string,
  peers: { source_context?: string[]; name?: string; label?: string }[]) {
  const contexts = new Set(peers.filter(peer => (peer.name ?? peer.label) === name).map(peer => JSON.stringify(peer.source_context ?? [])));
  if (contexts.size < 2 || !item.source_context?.length) return name;
  const heading = item.source_context.at(-2) ?? item.source_context[0];
  const scope = heading.match(/^\\d+(?:\\.\\d+)*/)?.[0] ?? heading;
  return `${name} [${scope}]`;
}

/** Counts describe source facts; they never confirm hardware quantities. */
export function documentEvidenceCounts(equipment: ReviewedDocumentEquipment) {
  const facts = equipment.facts ?? [];
  const requirements = facts.filter(item => item.kind === 'REQUIREMENT');
  // Normalize only the comparison key; literal quotes remain untouched.
  const ids = new Set(requirements.flatMap(item => item.source_quote.normalize('NFKC').replace(/[\\u2010-\\u2015\\u2212\\ufe63\\uff0d]/g, '-').match(/\\bREQ[-_][\\w-]+/g) ?? []));
  return { devices: facts.filter(item => item.kind === 'INSTANCE' || item.kind === 'CATEGORY').length,
    functions: facts.filter(item => item.kind === 'FUNCTION').length,
    requirements: requirements.length, requirementIds: ids.size, total: facts.length };
}
'''
    return text


change('frontend/src/features/agent/lib/document-clarification.ts', clarification)
change('frontend/src/features/agent/lib/engineering-agent.ts', lambda text: replace(text,
    'quantity: number | null; source_quote: string }[];',
    'quantity: number | null; source_quote: string; source_context?: string[] }[];'))


def specification(text):
    text = replace(text, "import { documentDeviceQuestions, readReviewedDocumentEquipment }", "import { documentDeviceQuestions, documentParticipantName, readReviewedDocumentEquipment }")
    text = replace(text, "  const originalLines = text.split(/\\r?\\n/);\n  const documentEquipment = readReviewedDocumentEquipment(text);", "  const documentEquipment = readReviewedDocumentEquipment(text);\n  text = text.replace(/^- Dokument-Geräte:[^\\r\\n]*$/gm, '');\n  const originalLines = text.split(/\\r?\\n/);")
    text = replace(text, "  const occurrences = [...lines.flatMap((line, index): HardwareOccurrence[] => {", "  const occurrences = documentEquipment?.facts ? [] : [...lines.flatMap((line, index): HardwareOccurrence[] => {")
    text = replace(text, "  const requestedTargets = extractEngineeringTargetCounts(text);", "  const requestedTargets = documentEquipment?.facts ? { ...chainCounts(recognizedChains), explicit: true } : extractEngineeringTargetCounts(text);")
    text = replace(text, "  for (const item of [...(documentEquipment?.devices ?? []), ...(documentEquipment?.answers ?? [])]) {\n    const baseName = ('name' in item ? item.name : item.label).replace", "  const reviewedParticipants = [...(documentEquipment?.devices ?? []), ...(documentEquipment?.answers ?? [])];\n  const documentIdentityPeers = [...(documentEquipment?.devices ?? []), ...(documentEquipment?.questions ?? [])];\n  for (const item of reviewedParticipants) {\n    const baseName = documentParticipantName(item, 'name' in item ? item.name : item.label, documentIdentityPeers).replace")
    text = replace(text, "quantity: item.quantity, device_role: item.role", "quantity: item.quantity, device_role: item.role, source_context: item.source_context ?? []")
    text = replace(text, "      ...documentDeviceQuestions(lines.join('\\n')),", "      ...(documentEquipment?.facts ? [] : documentDeviceQuestions(lines.join('\\n'))),")
    text = replace(text, "      const type = question.role === 'SENSOR' ? 'SensorController'", "      if (question.role === 'OTHER') return [`Gerätegruppe (${question.label}): Geräteart und Stückzahl fehlen. Bitte die Dokument-Rückfrage beantworten.`];\n      const type = question.role === 'SENSOR' ? 'SensorController'")
    text = replace(text, "      const answer = documentEquipment?.answers.find", "      if (documentEquipment?.excluded_questions?.includes(question.id)) return [];\n      const answer = documentEquipment?.answers.find")
    return text


change('frontend/src/features/agent/lib/engineering-specification.ts', specification)
print('Staged typed evidence and authoritative inventory prepared; live files unchanged.')
