import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { extractEngineeringSpecification } from '../../../../../../../../frontend/src/features/agent/lib/engineering-specification.ts';

const sourcePath = 'C:/Users/marti/PycharmProjects/Benchmark_Modelle/INDUSTRIEPORTFOLIO_100_KATEGORIENPAKET/A_AUTOMOTIVE_001_035.md';
const raw = readFileSync(sourcePath);
const spec = extractEngineeringSpecification(raw.toString('utf8'));
const finding = {
  sourcePath, sourceBytes: raw.length, sourceSha256: createHash('sha256').update(raw).digest('hex'),
  browserFileIdentityVerified: false,
  scope: 'Pure current-checkout raw preview reproduction; not canonical model or exact production/browser file proof',
  chains: spec.chains.filter(chain => /Medizin|Dispatch|Einsatzfunk|Aufbau/.test(chain.hardware_name)).map(chain => ({
    name: chain.hardware_name, type: chain.device_type, connection: chain.interface_type,
    source_context: chain.configuration?.source_context ?? null,
    description: chain.hardware_description,
  })),
};
writeFileSync(new URL(process.argv[2] || 'raw-preview-before.json', import.meta.url), JSON.stringify(finding, null, 2) + '\n');
console.log(JSON.stringify(finding));
