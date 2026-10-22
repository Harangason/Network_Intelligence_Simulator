"""Extend semantic architecture chapter recognition, preserving system roots."""
from pathlib import Path

OUT = Path(__file__).parent
path = OUT / 'staged/frontend/src/features/agent/lib/document-clarification.ts'
text = path.read_text(encoding='utf-8')
old = 'Systemkontext|System context|Domain[- ]Controller[- ]Design'
new = r'Systemkontext|System context|Zielbild der (?:E\/E[- ]?)?Architektur|Architecture (?:vision|target)|Target architecture|Domain[- ]Controller[- ]Design'
assert text.count(old) == 1
path.write_text(text.replace(old, new), encoding='utf-8')
path = OUT / 'staged/frontend/src/features/agent/lib/engineering-specification.test.mjs'
text = path.read_text(encoding='utf-8')
text += '''

test('architecture vision overview references explicit controllers while retaining named system roots', () => {
  const overview = 'Zentrale Domain-Controller (Alpha, Beta)';
  const source = `1. Zielbild der E/E‑Architektur\\n${overview}\\n2. Domain‑Controller‑Design\\n2.1 Controller Alpha (A)\\n2.2 Controller Beta (B)`;
  const makeProposal = root => ({ interpretation: { technologies: [], components: [
    { name: overview, kind: 'CATEGORY', role: 'CONTROLLER', quantity: null, source_quote: overview, source_context: [...root, '1. Zielbild der E/E‑Architektur'] },
    ...['Controller Alpha (A)', 'Controller Beta (B)'].map((name, index) => ({ name, kind: 'INSTANCE', role: 'CONTROLLER', quantity: 1, source_quote: name,
      source_context: [...root, '2. Domain‑Controller‑Design', `2.${index + 1} ${name}`] })),
  ] } });
  assert.deepEqual(documentDeviceQuestions(source, makeProposal([]))[0].covered_by, ['Controller Alpha (A)', 'Controller Beta (B)']);
  const rooted = makeProposal(['Anlage Nord']);
  assert.deepEqual(documentDeviceQuestions(source, rooted)[0].covered_by, ['Controller Alpha (A)', 'Controller Beta (B)']);
  rooted.interpretation.components[0].source_context[0] = 'Anlage Süd';
  assert.equal(documentDeviceQuestions(source, rooted)[0].covered_by, undefined);
});
'''
path.write_text(text, encoding='utf-8')
print('Architecture vision chapter regression staged.')
