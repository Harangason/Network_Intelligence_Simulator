import test from 'node:test';
import assert from 'node:assert/strict';
import { readDocumentIntakeResponse, documentRequestErrorMessage } from './engineering-agent.ts';
import { documentSourceScope, documentSystemScope } from './document-clarification.ts';

function fragmentedResponse(text) {
  const bytes = new TextEncoder().encode(text);
  return new Response(new ReadableStream({ start(controller) {
    for (let index = 0; index < bytes.length; index += 3) controller.enqueue(bytes.slice(index, index + 3));
    controller.close();
  } }), { headers: { 'Content-Type': 'application/x-ndjson' } });
}

test('document transport failures explain incomplete evidence and deliberate retry', () => {
  for (const text of ['network error', 'Failed to fetch', 'Load failed', 'NetworkError when attempting to fetch resource.']) {
    const message = documentRequestErrorMessage(new TypeError(text));
    assert.match(message, /Verbindung zur lokalen Dokumentauswertung wurde unterbrochen/);
    assert.match(message, /kein vollständiges Prüfergebnis empfangen/);
    assert.match(message, /Datei und Eingaben bleiben erhalten/);
    assert.match(message, /erneut/);
    assert.equal(message.includes(text), false);
  }
  assert.match(documentRequestErrorMessage(new Error('fetch failed'), 'reference'), /lokalen Referenzplanung/);
});

test('document error display preserves specific validation findings', () => {
  const message = 'Abschnitt 4 ist nicht quellenkonform.';
  assert.equal(documentRequestErrorMessage(new Error(message)), message);
  assert.match(documentRequestErrorMessage(null), /Dokumentauswertung/);
});

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

test('abandoning a pending document response cancels its reader without a successful proposal', async () => {
  let canceled = false;
  const progress = [];
  const response = new Response(new ReadableStream({
    start(controller) { controller.enqueue(new TextEncoder().encode('{"type":"PROGRESS","text":"Abschnitt 1"}\n')); },
    cancel() { canceled = true; },
  }), { headers: { 'Content-Type': 'application/x-ndjson' } });
  const controller = new AbortController();
  const pending = readDocumentIntakeResponse(response, text => progress.push(text), 2_000_000, controller.signal);
  await new Promise(resolve => setImmediate(resolve));
  controller.abort();
  await assert.rejects(pending, error => error.name === 'AbortError');
  assert.equal(canceled, true);
  assert.deepEqual(progress, ['Abschnitt 1']);
});

test('a rejected oversized document response releases the stream before returning its error', async () => {
  let canceled = false;
  const response = new Response(new ReadableStream({
    start(controller) { controller.enqueue(new Uint8Array(32)); },
    cancel() { canceled = true; },
  }), { headers: { 'Content-Type': 'application/x-ndjson' } });
  await assert.rejects(readDocumentIntakeResponse(response, () => assert.fail('No partial proposal'), 16), /zu groß/);
  assert.equal(canceled, true);
});

test('failed transport cleanup cannot replace an explicit size finding with network error', async () => {
  const response = new Response(new ReadableStream({
    start(controller) { controller.enqueue(new Uint8Array(32)); },
    cancel() { throw new TypeError('network error'); },
  }), { headers: { 'Content-Type': 'application/x-ndjson' } });
  await assert.rejects(readDocumentIntakeResponse(response, () => assert.fail('No partial proposal'), 16), error => {
    assert.match(documentRequestErrorMessage(error), /Die lokale Dokumentantwort ist zu groß/);
    return true;
  });
  assert.equal(response.body.locked, false);
});

test('an aborted response does not cancel an independent completed response', async () => {
  const canceled = new AbortController(); canceled.abort();
  await assert.rejects(readDocumentIntakeResponse(fragmentedResponse('{"type":"HEARTBEAT"}\n'), () => {}, 2_000_000, canceled.signal), error => error.name === 'AbortError');
  const independent = new AbortController();
  const data = { source_complete: true, source_name: 'other.txt' };
  assert.deepEqual(await readDocumentIntakeResponse(fragmentedResponse(JSON.stringify({ type: 'RESULT', result: { success: true, data } })), () => {}, 2_000_000, independent.signal), data);
  assert.equal(independent.signal.aborted, false);
});

test('an aborted failed transport releases the reader and preserves its original error', async () => {
  let streamController;
  const response = new Response(new ReadableStream({ start(controller) { streamController = controller; } }),
    { headers: { 'Content-Type': 'application/x-ndjson' } });
  const controller = new AbortController();
  const pending = readDocumentIntakeResponse(response, () => assert.fail('No progress from failed transport'), 2_000_000, controller.signal);
  await new Promise(resolve => setImmediate(resolve));
  const failure = new Error('socket closed');
  streamController.error(failure);
  controller.abort();
  await assert.rejects(pending, error => error === failure);
  assert.equal(response.body.locked, false);
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
