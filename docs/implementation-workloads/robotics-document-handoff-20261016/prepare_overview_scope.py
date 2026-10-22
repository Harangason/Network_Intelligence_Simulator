"""Permit reviewed overview references within one source system only."""
from pathlib import Path

OUT = Path(__file__).parent


def replace(text, old, new):
    assert text.count(old) == 1, (old[:100], text.count(old))
    return text.replace(old, new)


path = OUT / 'staged/backend/nis/agent/orchestration/project_intake.py'
text = path.read_text(encoding='utf-8')
text = replace(text, 'Requirements|Schnittstellen|Interfaces|Anschlüsse|Connections)\', label, re.I)',
               'Requirements|Schnittstellen|Interfaces|Anschlüsse|Connections|Übersicht|Overview|Systemübersicht|System overview)\', label, re.I)')
path.write_text(text, encoding='utf-8')

path = OUT / 'staged/frontend/src/features/agent/lib/document-clarification.ts'
text = path.read_text(encoding='utf-8')
text = replace(text, 'Requirements|Schnittstellen|Interfaces|Anschlüsse|Connections)$/iu.test(label)',
               'Requirements|Schnittstellen|Interfaces|Anschlüsse|Connections|Übersicht|Overview|Systemübersicht|System overview)$/iu.test(label)')
text = replace(text, 'function documentOwnerScopeMatches(owner: string[], fact: string[]) {', '''export function documentSystemScope(context: string[]) {
  const index = context.findIndex(label => {
    if (documentSourceScope([label]).length === 0) return true;
    const title = label.normalize('NFKC').replace(/[\\u2010-\\u2015\\u2212]/g, '-').replace(/^\\d+(?:\\.\\d+)*[.)]?\\s+/u, '').replace(/:\\s*$/u, '').trim();
    return /^(?:Systemstruktur(?:\\s*\\(Top-Level-Architektur\\))?|System structure(?:\\s*\\(Top-Level Architecture\\))?|Systemgrenzen(?: und Systemkontext)?|System boundaries(?: and System context)?|Systemkontext|System context|Domain[- ]Controller[- ]Design|Controller[- ]Design|(?:Elektronische|Elektrische|Mechanische|Software)\\s*Domäne|(?:Electronic|Electrical|Mechanical|Software) domain)$/iu.test(title);
  });
  return index < 0 ? [...context] : context.slice(0, index);
}

function sameDocumentSystem(left: string[] = [], right: string[] = []) {
  return JSON.stringify(documentSystemScope(left)) === JSON.stringify(documentSystemScope(right));
}

function documentOwnerScopeMatches(owner: string[], fact: string[]) {''')
context_comparison = 'JSON.stringify(item.source_context ?? []) === JSON.stringify(question.source_context ?? [])'
assert text.count(context_comparison) == 2
text = text.replace(context_comparison, 'sameDocumentSystem(item.source_context, question.source_context)')
text = replace(text, 'equipment.devices.some(item => item.name === reference)\n        || equipment.questions.some(question => question.id === reference && question.id !== answer.id)',
               'equipment.devices.some(item => item.name === reference && sameDocumentSystem(item.source_context, answer.source_context))\n        || equipment.questions.some(question => question.id === reference && question.id !== answer.id && sameDocumentSystem(question.source_context, answer.source_context))')
path.write_text(text, encoding='utf-8')

path = OUT / 'staged/frontend/src/features/agent/lib/engineering-specification.test.mjs'
text = path.read_text(encoding='utf-8') + '''

test('overview coverage can reference confirmed devices in another section of the same source system', () => {
  const source = '# Anlage Nord\\n## Übersicht\\nDomain-Controller (Alpha, Beta)\\n## Architektur\\nController Alpha (A)\\nController Beta (B)';
  const proposal = { interpretation: { technologies: [], components: [
    { name: 'Domain-Controller (Alpha, Beta)', kind: 'CATEGORY', role: 'CONTROLLER', quantity: null, source_quote: 'Domain-Controller (Alpha, Beta)', source_context: ['Anlage Nord', 'Übersicht'] },
    ...['Controller Alpha (A)', 'Controller Beta (B)'].map(name => ({ name, kind: 'INSTANCE', role: 'CONTROLLER', quantity: 1, source_quote: name, source_context: ['Anlage Nord', 'Architektur'] })),
  ] } };
  const [question] = documentDeviceQuestions(source, proposal);
  assert.deepEqual(question.covered_by, ['Controller Alpha (A)', 'Controller Beta (B)']);
  const equipment = reviewDocumentEquipment(source, proposal, { [question.id]: 'covered' }, false);
  assert.equal(equipment.answers[0].coverage_confirmed, true);
  const spec = extractEngineeringSpecification(`${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`);
  assert.equal(spec.targetCounts.ecus, 2);
  assert.equal(spec.unresolvedInventoryGroups.length, 0);
});

test('overview coverage never borrows same-named devices from a different source system', () => {
  const source = '# Anlage Nord\\n## Übersicht\\nDomain-Controller (Alpha, Beta)\\n# Anlage Süd\\n## Architektur\\nController Alpha (A)\\nController Beta (B)';
  const proposal = { interpretation: { technologies: [], components: [
    { name: 'Domain-Controller (Alpha, Beta)', kind: 'CATEGORY', role: 'CONTROLLER', quantity: null, source_quote: 'Domain-Controller (Alpha, Beta)', source_context: ['Anlage Nord', 'Übersicht'] },
    ...['Controller Alpha (A)', 'Controller Beta (B)'].map(name => ({ name, kind: 'INSTANCE', role: 'CONTROLLER', quantity: 1, source_quote: name, source_context: ['Anlage Süd', 'Architektur'] })),
  ] } };
  const [question] = documentDeviceQuestions(source, proposal);
  assert.equal(question.covered_by, undefined);
  const equipment = reviewDocumentEquipment(source, proposal, {}, false);
  equipment.questions[0].covered_by = ['Controller Alpha (A)', 'Controller Beta (B)'];
  equipment.answers.push({ ...equipment.questions[0], quantity: 0, minimum: false, coverage_confirmed: true });
  assert.throws(() => readReviewedDocumentEquipment(`${source}\\n- Dokument-Geräte: ${JSON.stringify(equipment)}`), /Abdeckung/);
});

test('numeric structural chapters permit explicit overview coverage within the one source system', () => {
  const overview = 'Domain-Controller (Alpha, Beta)';
  const source = `3. Systemstruktur (Top‑Level‑Architektur)\\n3.3 Elektronische Domäne\\n${overview}\\n2. Domain‑Controller‑Design\\n2.1 Controller Alpha (A)\\n2.2 Controller Beta (B)`;
  const proposal = { interpretation: { technologies: [], components: [
    { name: overview, kind: 'CATEGORY', role: 'CONTROLLER', quantity: null, source_quote: overview, source_context: ['3. Systemstruktur (Top‑Level‑Architektur)', '3.3 Elektronische Domäne'] },
    ...['Controller Alpha (A)', 'Controller Beta (B)'].map((name, index) => ({ name, kind: 'INSTANCE', role: 'CONTROLLER', quantity: 1, source_quote: name,
      source_context: ['2. Domain‑Controller‑Design', `2.${index + 1} ${name}`] })),
  ] } };
  assert.deepEqual(documentDeviceQuestions(source, proposal)[0].covered_by, ['Controller Alpha (A)', 'Controller Beta (B)']);
});
'''
path.write_text(text, encoding='utf-8')
print('Overview references staged with explicit confirmation and source-system boundary checks.')
