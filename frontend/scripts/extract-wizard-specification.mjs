// Pure data adapter: reuse the wizard's domain catalogs without any HTTP or writes.
import { applyIndustryGenerationPath, applyConfirmedClusterGraph, extractEngineeringSpecification, expandEngineeringSignalModel, packEngineeringChains, reconcileConfirmedGraphDevices } from '../src/lib/agent/engineering-specification.ts';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const { prompt } = JSON.parse(input);
if (typeof prompt !== 'string' || prompt.length > 120000) throw new Error('Invalid wizard specification');
const specification = extractEngineeringSpecification(prompt);
specification.chains = applyIndustryGenerationPath(packEngineeringChains(expandEngineeringSignalModel(applyConfirmedClusterGraph(reconcileConfirmedGraphDevices(specification, prompt), prompt))), specification.domain);
process.stdout.write(JSON.stringify(specification));
