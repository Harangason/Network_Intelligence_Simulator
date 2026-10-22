import test from 'node:test';
import assert from 'node:assert/strict';
import { readDocumentIntakeResponse } from './engineering-agent.ts';
import { documentSourceScope, documentSystemScope } from './document-clarification.ts';

function fragmentedResponse(text) {
  const bytes = new TextEncoder().encode(text);
  return new Response(new ReadableStream({ start(controller) {
    for (let index = 0; index < bytes.length; index += 3) controller.enqueue(bytes.slice(index, index + 3));
    controller.close();
  } }), { headers: { 'Content-Type': 'application/x-ndjson' } });
}

test('document transport preserves UTF8 progress and waits for the terminal tool result', async () => {
  const progress = [];
  const proposal = { source_name: 'Äußere Sensorik', source_complete: true };
  const response = fragmentedResponse(JSON.stringify({ type: 'PROGRESS', text: 'Abschnitt prüfen: äußere Sensorik' }) + '\n'
    + JSON.stringify({ type: 'HEARTBEAT' }) + '\n'
    + JSON.stringify({ type: 'RESULT', result: { success: true, data: proposal } }));
  assert.deepEqual(await readDocumentIntakeResponse(response, text => progress.push(text)), proposal);
  assert.deepEqual(progress, ['Abschnitt prüfen: äußere Sensorik']);
});

test('heartbeat-only or failed later processing is never interpreted as a successful proposal', async () => {
  await assert.rejects(readDocumentIntakeResponse(fragmentedResponse('{"type":"HEARTBEAT"}\n'), () => {}), /fehlgeschlagen/);
  await assert.rejects(readDocumentIntakeResponse(fragmentedResponse(JSON.stringify({ type: 'RESULT', result: {
    success: false, findings: [{ message: 'Abschnitt 4 ist nicht quellenkonform.' }],
  } })), () => {}), /Abschnitt 4/);
});

for (const caption of ['Mechanische, elektrische und E/E-Architektur', 'Physical and logical Architecture',
  'Kernfunktionen', 'Core functions', 'Regulatorische Anforderungen', 'Regulatory Requirements',
  'Schnittstellen und Datenobjekte', 'Safety, SOTIF, KI-Sicherheit, Cybersecurity und Compliance']) {
  test(`shared chapter vocabulary keeps source-system boundaries: ${caption}`, () => {
    assert.deepEqual(documentSystemScope(['Facility North', `8. ${caption}`]), ['Facility North']);
    assert.deepEqual(documentSystemScope(['Facility South', `8. ${caption}`]), ['Facility South']);
  });
}

test('source-scope reduction retains named hardware and unrelated systems', () => {
  assert.deepEqual(documentSourceScope(['Medical Controller', 'Kernfunktionen']), ['Medical Controller']);
  for (const name of ['Safety PLC', 'Physical Inspection System', 'Kernfunktionenrechner']) {
    assert.deepEqual(documentSystemScope([name]), [name]);
  }
});
