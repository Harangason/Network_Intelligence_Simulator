// Compare real frontend scope resolution with backend output over original headings.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { documentSystemScope, documentSourceScope } from '../../../frontend/src/features/agent/lib/document-clarification.ts';

const cases = JSON.parse(readFileSync(new URL('./scope-parity-input.json', import.meta.url), 'utf8'));
const failures = [];
for (const item of cases) {
  const actual = { system: documentSystemScope(item.context), source: documentSourceScope(item.context) };
  if (JSON.stringify(actual) !== JSON.stringify(item.expected)) failures.push({ ...item, actual });
}
const result = { scope: 'Backend/frontend semantic scope parity on original source headings and named-system counterexamples',
  cases: cases.length, failures, status: failures.length ? 'FAILED' : 'PASSED', inference_calls: 0, canonical_model_writes: false };
writeFileSync(new URL('./scope-parity-result.json', import.meta.url), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result));
process.exitCode = failures.length ? 1 : 0;
