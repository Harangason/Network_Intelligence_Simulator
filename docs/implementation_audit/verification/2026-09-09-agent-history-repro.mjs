// Run from frontend: node --experimental-strip-types ../docs/implementation_audit/verification/2026-09-09-agent-history-repro.mjs
// Executes the actual source helpers with a mocked fetch; no network or writes.
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { refreshProposal } from '../../../frontend/src/lib/agent/proposal-client.ts';

const require = createRequire(new URL('../../../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = fs.readFileSync(new URL('../../../frontend/src/lib/agent-chat-history.ts', import.meta.url), 'utf8');
const start = source.indexOf('function compactValue(');
const end = source.indexOf('async function readServerHistory(', start);
const script = ts.transpileModule(source.slice(start, end), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
const sandbox = { uniqueMessagesById: items => items, MAX_MESSAGES: 60, MAX_TRANSPORT_BYTES: 4500000 };
vm.createContext(sandbox);
vm.runInContext(script, sandbox);
const proposal = {
  proposal_id: 'audit', proposal_type: 'MODEL', revision: 'r1', status: 'VALIDATED',
  rationale: '200 Aenderungen', assumptions: [], canonical_ids: [], validation_result: {},
  changes: Array.from({ length: 200 }, (_, i) => ({ local_ref: `node${i}`, action: 'CREATE', object_type: 'HardwareNode', data: { name: `Node${i}` } })),
};
const compact = sandbox.transportMessages([{ id: 'reply', role: 'assistant', parts: [{ type: 'data-engineering', data: { id: 'event', type: 'APPROVAL', proposal, created_at: 'now' } }] }]);
const restored = compact[0].parts[0].data.proposal;
const requests = [];
globalThis.fetch = async url => {
  requests.push(url);
  return new Response(JSON.stringify({ success: true, data: { proposal_id: 'audit', revision: 'r1', status: 'VALIDATED' } }), { status: 200 });
};
const refreshed = await refreshProposal(restored, 'audit');
console.log(JSON.stringify({ check: 'large_proposal_history_roundtrip', originalChanges: proposal.changes.length, restoredChanges: restored.changes.length, lastChange: restored.changes.at(-1), refreshedChanges: refreshed.changes.length, requests }, null, 2));
