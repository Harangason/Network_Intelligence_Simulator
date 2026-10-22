// Pure operator projection using the actual NIS accepted-plan adapter.
// No requests, approvals, alternative model or technical-profile defaults.
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, acceptedFile, runId, projectId, projectName] = process.argv.slice(2);
if (!root || !acceptedFile || !runId || !projectId || !projectName) throw new Error('Explicit actual case arguments required.');
const record = JSON.parse(await readFile(acceptedFile, 'utf8'));
const moduleAt = relative => import(pathToFileURL(resolve(root, relative)).href);
const { referenceDesignMarker } = await moduleAt('frontend/src/features/agent/lib/engineering-agent.ts');
const { extractEngineeringSpecification } = await moduleAt('frontend/src/features/agent/lib/engineering-specification.ts');
const { compactProjectId } = await moduleAt('frontend/src/features/settings/lib/user-settings.ts');
if (compactProjectId(record.project_id) !== compactProjectId(projectId) || record.status !== 'ACCEPTED' || record.canonical_writes !== false
    || record.proposal.unresolved.length) throw new Error('A current accepted, resolved product plan is required.');
const sourceTask = record.request.prompt;
const marker = referenceDesignMarker(record);
const spec = extractEngineeringSpecification(sourceTask + '\n' + marker);
if (!spec.reference_design || spec.unresolvedInventoryGroups.length) throw new Error('The native adapter has unresolved inputs.');
const scope = ['engineering_model', 'routing', 'network_editor', 'parameters', 'capacity_timing',
  'validation', 'simulation', 'results_analysis', 'data_science_intelligence'];
const prompt = 'Strukturierte Vorgaben fuer den Engineering-Agenten:\n'
  + '- Generierungsmodus: EXAMPLE_PROJECT\n'
  + `- Lauf-ID: ${runId}\n- Projektname: ${projectName}\n`
  + `- Industrie: ${spec.domain}\n- Projekt-Modelltyp: ${spec.modelType}\n`
  + `- Netzwerktechnologien: ${spec.communicationSystems.map(id => `${id} (${id})`).join('; ')}\n`
  + `- Kommunikationssystem-Sollwerte: ${JSON.stringify(spec.communicationSystemCounts)}\n`
  + `- Hardware-Sollwerte: ${JSON.stringify(Object.fromEntries(['gateways', 'ecus', 'sensors', 'actuators'].map(key => [key, spec.targetCounts[key]])))}\n`
  + '- Systemcluster-Graph: []\n'
  + `- Netzarchitektur-ID: ${spec.networkArchitecture}\n`
  + '- Arbeitsweise: Review-Gate; Freigabe nach Prüfung\n'
  + '- Workflowumfang: alle neun Schritte bis data_science_intelligence\n'
  + '\nKonkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:\n'
  + sourceTask + '\n' + marker + '\n\n'
  + 'Prüfe und verwende den aktuellen serverseitig akzeptierten NIS-Referenzentwurf. '
  + 'Alle ursprünglichen Quellenbefunde und getrennten Systemkontexte bleiben erhalten. '
  + 'Erzeuge das kanonische Modell und die Verbindungen selbst über Vorschläge und den normalen Review-/Apply-Weg. '
  + 'Referenzannahmen sind keine Hardware-, Ausführungs- oder normativen Nachweise. '
  + 'Keine fehlenden Fachentscheidungen erfinden und keine Parameter-/Preflight-Gates umgehen. '
  + 'Führe nach den erforderlichen Freigaben den gesamten Workflow bis zur gespeicherten Simulation und Ergebnisprüfung aus.';
process.stdout.write(JSON.stringify({prompt, wizard_context: {
  project_id: projectId, run_id: runId, project_name: projectName,
  mode: 'full', industry: spec.domain, model_type: spec.modelType,
  task: sourceTask, scope_ids: scope, process_ids: ['review_gate', 'approve_after_allow'],
  technologies: spec.communicationSystems, hardware_counts: Object.fromEntries(
    ['gateways', 'ecus', 'sensors', 'actuators'].map(key => [key, spec.targetCounts[key]])),
  communication_system_counts: spec.communicationSystemCounts,
  system_cluster_assignments: [],
}, projection: {
  domain: spec.domain, model_type: spec.modelType, architecture: spec.networkArchitecture,
  counts: spec.targetCounts, communication_systems: spec.communicationSystemCounts,
  chain_count: spec.chains.length, design_id: record.design_id, design_revision: record.revision,
  scope: 'Unmodified accepted NIS plan through existing product extraction; orchestration header only. No operator-designed model or synthetic technical profiles.',
}}));
