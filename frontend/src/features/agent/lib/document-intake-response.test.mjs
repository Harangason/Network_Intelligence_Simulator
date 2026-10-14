import test from 'node:test';
import assert from 'node:assert/strict';
import { readDocumentIntakeResponse } from './engineering-agent.ts';

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
