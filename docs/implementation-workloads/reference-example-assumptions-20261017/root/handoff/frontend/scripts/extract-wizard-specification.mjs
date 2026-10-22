// Pure data adapter: reuse the wizard's domain catalogs without any HTTP or writes.
import { applyIndustryGenerationPath, applyConfirmedClusterGraph, extractEngineeringSpecification, expandEngineeringSignalModel, packEngineeringChains, reconcileConfirmedGraphDevices, explicitDeviceConnections, explicitDeviceOwners, normalizeHardwareName } from '../src/features/agent/lib/engineering-specification.ts';
import { completeFunctionalDeviceDesign, usesFunctionalDeviceDesign } from '../src/features/agent/lib/functional-device-design.ts';
import { SENSOR_MEASUREMENTS, sensorMeasurementSelections } from '../src/features/agent/lib/sensor-measurements.ts';
import { ACTUATOR_COMMANDS, actuatorCommands } from '../src/features/agent/lib/actuator-commands.ts';
import { documentSourceFunctionAssignments, readReviewedDocumentEquipment } from '../src/features/agent/lib/document-clarification.ts';
import { MAX_WIZARD_DOCUMENT_CHARS } from '../src/features/agent/lib/chat-attachments.ts';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const { prompt, operation } = JSON.parse(input);
if (typeof prompt !== 'string' || Array.from(prompt).length > 4 * MAX_WIZARD_DOCUMENT_CHARS + 100000) throw new Error('Invalid wizard specification');
const specification = extractEngineeringSpecification(prompt);
if (operation === 'reference-catalog') {
  const equipment = readReviewedDocumentEquipment(prompt);
  const owners = specification.chains.filter(chain => Array.isArray(chain.configuration?.source_scoped_functions))
    .map(chain => ({ name: chain.hardware_name,
      source_context: chain.configuration.document_equipment_evidence?.source_context,
      duties: chain.configuration.source_scoped_functions }));
  const confirmed_commands = actuatorCommands(prompt);
  const confirmed_measurements = sensorMeasurementSelections(prompt);
  const confirmed_connections = explicitDeviceConnections(prompt);
  const confirmed_owners = explicitDeviceOwners(prompt);
  const names = [...new Set([...specification.chains.map(chain => chain.hardware_name),
    ...(equipment?.facts ?? []).filter(fact => ['INSTANCE', 'CATEGORY'].includes(fact.kind)).map(fact => fact.name),
    ...Object.keys(confirmed_commands), ...Object.keys(confirmed_measurements),
    ...Object.keys(confirmed_connections), ...Object.keys(confirmed_owners)])];
  process.stdout.write(JSON.stringify({
    measurements: SENSOR_MEASUREMENTS.map(({ match, ...value }) => ({ ...value, alias_pattern: match.source })),
    actuator_commands: ACTUATOR_COMMANDS,
    confirmed_commands, confirmed_measurements, confirmed_connections, confirmed_owners,
    name_aliases: Object.fromEntries(names.map(name => [name, normalizeHardwareName(name).toLocaleLowerCase('de')])),
    source_function_assignments: documentSourceFunctionAssignments(equipment?.facts ?? [], owners),
    source_devices: specification.chains.filter(chain => chain.configuration?.document_equipment_evidence)
      .map(chain => ({ name: chain.hardware_name, device_type: chain.device_type,
        evidence: chain.configuration.document_equipment_evidence })),
  }));
} else {
if (operation !== undefined) throw new Error('Unknown wizard adapter operation');
const imported = !usesFunctionalDeviceDesign(prompt);
const expanded = expandEngineeringSignalModel(completeFunctionalDeviceDesign(applyConfirmedClusterGraph(reconcileConfirmedGraphDevices(specification, prompt), prompt), prompt, false), imported);
specification.chains = imported
  ? applyIndustryGenerationPath(packEngineeringChains(expanded, undefined, prompt), specification.domain, prompt)
  : packEngineeringChains(applyIndustryGenerationPath(completeFunctionalDeviceDesign(expanded, prompt), specification.domain, prompt), undefined, prompt);
process.stdout.write(JSON.stringify(specification));
}
