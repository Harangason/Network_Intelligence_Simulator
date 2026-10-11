import assert from 'node:assert/strict';
import fs from 'node:fs';
import { communicationWarnings } from '../../../frontend/src/features/communication/lib/communication-warnings.ts';

const folder = new URL('./', import.meta.url);
const capture = JSON.parse(fs.readFileSync(new URL('canonical-after-reconciliation.json', folder), 'utf8'));
const snapshot = capture.snapshot;
const objects = ['hardware', 'functions', 'interfaces', 'hardware-interfaces', 'messages', 'signals']
  .flatMap(key => snapshot[key]);
const warnings = communicationWarnings(objects, snapshot.routing, snapshot.parameters.networks ?? [], snapshot.topology);
const lichtId = '17c07ffe-22a5-4a6a-a071-e91169ede1c4';
assert.equal(warnings.get(lichtId)?.length ?? 0, 0, 'Licht still has a communication warning.');
const disconnected = [...warnings].flatMap(([id, rows]) => rows.filter(row => row.code === 'PORT_DISCONNECTED').map(row => ({ id, ...row })));
assert.equal(disconnected.length, 0, 'There are still active disconnected channel warnings.');
const retired = [...warnings].flatMap(([id, rows]) => rows.filter(row => row.code === 'PORT_RETIRED').map(row => ({ id, ...row })));
assert.equal(retired.length, 0, 'A live consumer still references a retired duplicate.');
const report = { status: 'VERIFIED', project: snapshot.project_id, licht_warning_count: 0,
  disconnected_warning_count: 0, active_retired_reference_warning_count: 0,
  all_remaining_warnings: [...warnings].map(([id, rows]) => ({ id, warnings: rows })),
  scope: 'Actual canonical production snapshot evaluated by the same delivered UI warning derivation; production source identity is checked separately.' };
fs.writeFileSync(new URL('production-warning-verification.json', folder), JSON.stringify(report, null, 2));
console.log(JSON.stringify({ status: report.status, licht_warning_count: 0, remaining_warned_objects: warnings.size }));
