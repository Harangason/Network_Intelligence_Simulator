// Pure data adapter: reuse the wizard's domain catalogs without any HTTP or writes.
import { extractEngineeringSpecification, expandEngineeringSignalModel, packEngineeringChains } from '../src/lib/agent/engineering-specification.ts';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const { prompt } = JSON.parse(input);
if (typeof prompt !== 'string' || prompt.length > 30000) throw new Error('Invalid wizard specification');
const specification = extractEngineeringSpecification(prompt);
specification.chains = packEngineeringChains(expandEngineeringSignalModel(specification.chains));
process.stdout.write(JSON.stringify(specification));
