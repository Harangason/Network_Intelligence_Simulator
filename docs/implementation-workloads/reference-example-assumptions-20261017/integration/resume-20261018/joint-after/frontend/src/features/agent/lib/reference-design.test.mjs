import test from 'node:test';
import assert from 'node:assert/strict';
import { readDocumentIntakeResponse, referenceDesignMarker } from './engineering-agent.ts';

function record(status = 'ACCEPTED') {
  return { schema_version: 1, status, canonical_writes: false, project_id: 'fixture',
    design_id: 'reference-fixture', revision: 2, request_sha256: '1'.repeat(64), source_sha256: '2'.repeat(64),
    proposal: { devices: [], unresolved: [] }, fact_id_map: { F123: 'original source identity' },
    decision_evidence: [{ source: 'REFERENCE_ASSUMPTION', field: 'ports', rationale: 'Reviewable design' }],
    protected_fields: { commands: { Antrieb: { unit: 'N m', factor: 0.1 } } },
  };
}

test('normal wizard marker keeps reference authority, exact choices and original bindings', () => {
  const source = record();
  const before = JSON.stringify(source);
  const line = referenceDesignMarker(source);
  assert.ok(line.startsWith('- Dokument-Referenzentwurf: '));
  const metadata = JSON.parse(line.slice('- Dokument-Referenzentwurf: '.length));
  assert.deepEqual(metadata.proposal, source.proposal);
  assert.deepEqual(metadata.fact_id_map, source.fact_id_map);
  assert.deepEqual(metadata.decision_evidence, source.decision_evidence);
  assert.deepEqual(metadata.protected_fields, source.protected_fields);
  assert.equal(metadata.decision_evidence[0].source, 'REFERENCE_ASSUMPTION');
  assert.equal(JSON.stringify(source), before);
});

test('unreviewed or canonical-write response cannot be adopted through a source marker', () => {
  assert.throws(() => referenceDesignMarker(record('REVIEW_REQUIRED')), /prüfen/);
  assert.throws(() => referenceDesignMarker({ ...record(), canonical_writes: true }), /prüfen/);
});

test('native streaming reader keeps complete multi-byte reference data through chunk boundaries', async () => {
  const source = record();
  source.decision_evidence.push({ rationale: 'Größe, Wärme, Maß und geprüfte äußere Geräte' });
  const bytes = new TextEncoder().encode(JSON.stringify({ type: 'PROGRESS', text: 'Vollständig prüfen' }) + '\n'
    + JSON.stringify({ type: 'RESULT', result: { success: true, data: source } }) + '\n');
  const body = new ReadableStream({ start(controller) { for (let n = 0; n < bytes.length; n += 3) controller.enqueue(bytes.slice(n, n + 3)); controller.close(); } });
  const progress = [];
  const result = await readDocumentIntakeResponse(new Response(body, { headers: { 'Content-Type': 'application/x-ndjson' } }), text => progress.push(text));
  assert.deepEqual(result, source);
  assert.deepEqual(progress, ['Vollständig prüfen']);
});

test('incomplete streaming result reports failure instead of treating progress as completion', async () => {
  const response = new Response('{"type":"PROGRESS","text":"Arbeitet"}\n', { headers: { 'Content-Type': 'application/x-ndjson' } });
  await assert.rejects(() => readDocumentIntakeResponse(response, () => {}), /fehlgeschlagen/);
});

test('stream size bounds remain enforced for reference responses', async () => {
  const data = JSON.stringify({ type: 'RESULT', result: { success: true, data: record() } });
  const response = new Response(data, { headers: { 'Content-Type': 'application/x-ndjson' } });
  await assert.rejects(() => readDocumentIntakeResponse(response, () => {}, 30), /groß/);
});
