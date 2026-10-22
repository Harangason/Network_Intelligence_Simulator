// Pure data adapter: reuse the wizard's domain catalogs without any HTTP or writes.
import { applyIndustryGenerationPath, applyConfirmedClusterGraph, extractEngineeringSpecification, expandEngineeringSignalModel, packEngineeringChains, reconcileConfirmedGraphDevices } from '../src/features/agent/lib/engineering-specification.ts';
import { completeFunctionalDeviceDesign, usesFunctionalDeviceDesign } from '../src/features/agent/lib/functional-device-design.ts';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const { prompt } = JSON.parse(input);
if (typeof prompt !== 'string' || prompt.length > 120000) throw new Error('Invalid wizard specification');
const specification = extractEngineeringSpecification(prompt);
const imported = !usesFunctionalDeviceDesign(prompt);
const expanded = expandEngineeringSignalModel(completeFunctionalDeviceDesign(applyConfirmedClusterGraph(reconcileConfirmedGraphDevices(specification, prompt), prompt), prompt, false), imported);
specification.chains = imported
  ? applyIndustryGenerationPath(packEngineeringChains(expanded, undefined, prompt), specification.domain, prompt)
  : packEngineeringChains(applyIndustryGenerationPath(completeFunctionalDeviceDesign(expanded, prompt), specification.domain, prompt), undefined, prompt);
process.stdout.write(JSON.stringify(specification));
