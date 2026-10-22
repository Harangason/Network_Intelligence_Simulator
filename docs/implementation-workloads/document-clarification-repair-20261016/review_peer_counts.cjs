// Pure staged helper counterprobe. No browser, product API or model writes.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../../..');
const ts = require(path.join(root, 'frontend/node_modules/typescript'));
const helper = path.join(__dirname, '../robotics-document-handoff-20261016/staged/frontend/src/features/agent/lib/document-clarification.ts');
const bytes = fs.readFileSync(helper);
const js = ts.transpileModule(bytes.toString('utf8'), {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS}}).outputText;
const api = {};
new Function('exports', js)(api);
const original = fs.readFileSync('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt', 'utf8');
const facts = [{kind: 'REQUIREMENT', role: 'OTHER', name: 'Literal original source', quantity: null, source_quote: original}];
const counts = api.documentEvidenceCounts({facts});
if (counts.requirementIds !== 168 || facts[0].source_quote !== original) throw new Error('Requirement IDs or literal evidence changed');
const report = {status: 'PASSED', scope: 'staged pure frontend helper; no product Wizard evidence', at: new Date().toISOString(), helper_sha256: crypto.createHash('sha256').update(bytes).digest('hex'), counts, source_quotes_unchanged: true};
fs.writeFileSync(path.join(__dirname, 'peer-staged-counts.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report));
