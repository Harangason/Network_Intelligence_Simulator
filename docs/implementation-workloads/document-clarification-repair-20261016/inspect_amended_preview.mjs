import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { extractEngineeringSpecification, isEngineeringControllerDevice } from '../../../frontend/src/features/agent/lib/engineering-specification.ts';
import { documentDeviceQuestions, reviewDocumentEquipment } from '../../../frontend/src/features/agent/lib/document-clarification.ts';

// Pure NIS parser diagnostic; no canonical objects, HTTP responses or writes.
const work = fileURLToPath(new URL('.', import.meta.url));
const original = fs.readFileSync('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt', 'utf8');
const amendment = fs.readFileSync(work + 'user-amendment.txt', 'utf8');
const source = amendment + '\n' + original;
const nativeOriginal = JSON.parse(fs.readFileSync(work + 'native-vehicle-parser-probe.json', 'utf8')).result;
const questions = documentDeviceQuestions(source, nativeOriginal);
const answers = Object.fromEntries(questions.filter(q => ['SENSOR', 'ACTUATOR'].includes(q.role)).map(q => [q.id, '1']));
const equipment = reviewDocumentEquipment(source, nativeOriginal, answers, true);
const spec = extractEngineeringSpecification(`${source}\n- Dokument-Geräte: ${JSON.stringify(equipment)}`);
const result = {
  scope: 'pure_parser_diagnostic_not_native_amendment_or_wizard_proof',
  controller_names: [...new Set(spec.chains.filter(c => isEngineeringControllerDevice(c.device_type)).map(c => c.hardware_name))],
  target_counts: spec.targetCounts, unresolved_groups: spec.unresolvedInventoryGroups,
};
fs.writeFileSync(work + 'amended-preview.json', JSON.stringify(result, null, 2));
console.log(JSON.stringify(result));
if (result.controller_names.length !== 5) process.exitCode = 1;
