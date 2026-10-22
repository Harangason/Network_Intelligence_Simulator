import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { extractEngineeringSpecification, isEngineeringControllerDevice } from '../../../frontend/src/features/agent/lib/engineering-specification.ts';
import { documentDeviceQuestions, reviewDocumentEquipment } from '../../../frontend/src/features/agent/lib/document-clarification.ts';
import { buildEquipmentClusters } from '../../../frontend/src/features/agent/lib/equipment-clustering.ts';

// A read-only NIS draft preview with the user's explicit minimum response.
// This does not apply a model, select ports, forge native facts or run a job.
const source = fs.readFileSync('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt', 'utf8');
const questions = documentDeviceQuestions(source);
const equipment = reviewDocumentEquipment(source, null, Object.fromEntries(questions.map(question => [question.id, '1'])), true);
const prompt = `${source}\n- Dokument-Geräte: ${JSON.stringify(equipment)}`;
const spec = extractEngineeringSpecification(prompt);
const clusters = buildEquipmentClusters(spec.chains, spec.communicationSystems.map(id => ({ id, label: id })), spec.domain);
const result = { scope: 'read_only_nis_preview_not_canonical_or_simulation',
  hardware_counts: spec.targetCounts, questions: equipment.questions,
  unresolved: spec.unresolvedInventoryGroups,
  devices: spec.chains.map(chain => ({ name: chain.hardware_name, type: chain.device_type, interface: chain.interface_type,
    function: chain.function_name, signal: chain.signal_name, configuration: chain.configuration })),
  clusters: clusters.map(cluster => ({ label: cluster.label, controllers: cluster.controllers,
    unassigned: cluster.unassigned, functional_routes: cluster.functionalRoutes, functional_issues: cluster.functionalIssues })),
};
fs.writeFileSync(fileURLToPath(new URL('./vehicle-preview.json', import.meta.url)), JSON.stringify(result, null, 2));
console.log(JSON.stringify({ hardware_counts: spec.targetCounts, unresolved: spec.unresolvedInventoryGroups,
  controllers: spec.chains.filter(chain => isEngineeringControllerDevice(chain.device_type)).map(chain => chain.hardware_name),
  functions: clusters.flatMap(cluster => cluster.controllers.flatMap(controller => controller.functions ?? [])),
  unassigned: clusters.flatMap(cluster => cluster.unassigned),
  routes: clusters.flatMap(cluster => cluster.functionalRoutes),
  issues: clusters.flatMap(cluster => cluster.functionalIssues) }));
