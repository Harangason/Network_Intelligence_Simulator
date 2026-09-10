import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';

// Exercise the actual Next POST handler, with only the upstream agent stubbed.
const source = await fs.readFile(new URL('../src/app/api/agent/chat/route.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
  .replace(/from "@\/([^"\n]+)"/g, 'from "../src/$1.ts"');
const temporary = new URL('./.agent-chat-route-test.mjs', import.meta.url);
await fs.writeFile(temporary, js);
const originalFetch = globalThis.fetch;
let captured, calls = 0;
try {
  const { POST } = await import(temporary.href);
  globalThis.fetch = async (url, options) => {
    assert.match(String(url), /\/agent\/chat$/);
    calls++; captured = JSON.parse(options.body);
    return new Response(JSON.stringify({ type: 'TEXT', id: 'response-1', created_at: new Date().toISOString(), text: 'Quelle gelesen.' }) + '\n', { headers: { 'Content-Type': 'application/x-ndjson' } });
  };
  const document = { name: 'Vorgabe.dbc', format: 'DBC', size: 22, text: 'SG_ Federweg 12 Bit; LIN 50 ms', truncated: false };
  const message = { id: 'user-1', role: 'user', parts: [{ type: 'text', text: 'Prüfe dieses Signal.' }, { type: 'data-attachment', data: document }] };
  const request = messages => new Request('http://localhost/api/agent/chat', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Project-ID': 'transport-test' }, body: JSON.stringify({ messages }) });
  const result = await POST(request([message]));
  assert.equal(result.status, 200); assert.match(await result.text(), /Quelle gelesen/);
  assert.equal(captured.prompt, 'Prüfe dieses Signal.');
  assert.deepEqual(captured.context.document_sources, [document]);
  assert.equal(captured.context.active_project_id, 'transport-test');
  const followup = await POST(request([message, { id: 'user-2', role: 'user', parts: [{ type: 'text', text: 'Welcher Zyklus steht darin?' }] }]));
  await followup.text();
  assert.deepEqual(captured.context.document_sources, [document], 'Follow-up must keep the document source');
  const invalid = await POST(request([{ ...message, parts: [{ type: 'data-attachment', data: { ...document, text: '' } }] }]));
  assert.equal(invalid.status, 400); assert.equal(calls, 2);
  console.log('Chat transport: extracted sources, follow-up context and invalid attachment rejection passed.');
} finally {
  globalThis.fetch = originalFetch;
  await fs.unlink(temporary);
}
