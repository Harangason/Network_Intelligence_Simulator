import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {extractEngineeringSpecification} from '../../../frontend/src/features/agent/lib/engineering-specification.ts';

const path = new URL('../document-function-owner-cross-reference-20261017/reference-source-review/neu 9.txt', import.meta.url);
const raw = readFileSync(path);
const source = raw.toString('utf8');
const task = '\n- Aufgaben-Anlage: neu 9.txt (text/plain, 11 KB): Textinhalt als Aufgabenquelle fuer Umfang, Anforderungen und technische Vorgaben auswerten.\n' + source;
const result = extractEngineeringSpecification(task, {}, 'automotive');
const devices = [...new Map(result.chains.map(chain => [chain.hardware_name, chain])).values()];
const report = {
  scope: 'Pure current frontend extraction from preserved source; no inference or project writes',
  source: {path: path.pathname, bytes: raw.length, chars: source.length, sha256: createHash('sha256').update(raw).digest('hex')},
  browser_evidence: {project: '20261106093746010-f2585546', filename: 'neu 9.txt', chars_displayed: 11578,
    findings: 'All 13 displayed unresolved names reproduced; start disabled and canonical hardware empty.',
    limit: 'The browser file input has already been cleared. Exact browser file bytes/hash were not exposed; equality is not claimed from name/length alone.'},
  target_counts: result.targetCounts,
  device_count: devices.length,
  unresolved_connections: devices.filter(chain => chain.interface_type === 'Other').map(chain => ({name:chain.hardware_name,role:chain.device_type,source_context:chain.configuration?.source_context})),
  unresolved_inventory_groups: result.unresolvedInventoryGroups,
};
writeFileSync(new URL('reproduction.json', import.meta.url), JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));
