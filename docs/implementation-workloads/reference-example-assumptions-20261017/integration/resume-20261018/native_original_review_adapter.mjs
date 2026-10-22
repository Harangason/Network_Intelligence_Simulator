// Operator evidence adapter: invoke the existing NIS Wizard's pure review
// functions. It does not design hardware, signals, connections or parameters.
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const [root, sourceFile, proposalFile] = process.argv.slice(2);
const source = await readFile(sourceFile, 'utf8');
const proposal = JSON.parse(await readFile(proposalFile, 'utf8'));
const moduleAt = relative => import(pathToFileURL(resolve(root, relative)).href);
const document = await moduleAt('frontend/src/features/agent/lib/document-clarification.ts');
const specification = await moduleAt('frontend/src/features/agent/lib/engineering-specification.ts');
let equipment = document.reviewDocumentEquipment(source, proposal, {}, false);
const prefix = source + '\n' + document.DOCUMENT_EQUIPMENT_MARKER;
const initial = specification.extractEngineeringSpecification(prefix + JSON.stringify(equipment));
const owners = initial.chains.filter(chain => specification.isEngineeringControllerDevice(chain.device_type))
  .map(chain => ({name: chain.hardware_name,
    source_context: chain.configuration?.document_equipment_evidence?.source_context,
    duties: chain.configuration?.source_scoped_functions ?? []}));
const assignments = document.documentSourceFunctionAssignments(equipment.facts ?? [], owners);
equipment = document.reviewDocumentEquipment(source, proposal, {}, false, {}, assignments);
const prompt = prefix + JSON.stringify(equipment);
document.readReviewedDocumentEquipment(prompt);
process.stdout.write(JSON.stringify({prompt, equipment,
  scope: 'Existing product review/source-assignment functions only; no operator-supplied design or technical defaults.'}));
