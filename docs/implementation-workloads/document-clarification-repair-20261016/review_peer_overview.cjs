// Pure adapter fixture, not a native response or product/model write.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const ts = require(path.join(path.resolve(__dirname, '../../..'), 'frontend/node_modules/typescript'));
const helper = path.join(__dirname, '../robotics-document-handoff-20261016/staged/frontend/src/features/agent/lib/document-clarification.ts');
const bytes = fs.readFileSync(helper);
const js = ts.transpileModule(bytes.toString('utf8'), {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS}}).outputText;
const api = {};
new Function('exports', js)(api);
const source = '# Anlage Nord\n## Übersicht\nDomain-Controller (Alpha, Beta)\n## Architektur\nController Alpha (A)\nController Beta (B)\n';
const fact = (name,kind,quote,context,quantity) => ({name,kind,role:'CONTROLLER',quantity,source_quote:quote,source_context:context});
const components = [
  fact('Domain-Controller (Alpha, Beta)','CATEGORY','Domain-Controller (Alpha, Beta)',['Anlage Nord','Übersicht'],null),
  fact('Controller Alpha (A)','INSTANCE','Controller Alpha (A)',['Anlage Nord','Architektur'],1),
  fact('Controller Beta (B)','INSTANCE','Controller Beta (B)',['Anlage Nord','Architektur'],1),
];
const proposal = {source_complete:true,interpretation:{components}};
const questions = api.documentDeviceQuestions(source,proposal);
const references = questions.find(q=>q.source_quote==='Domain-Controller (Alpha, Beta)')?.covered_by ?? [];
const passed = references.length===2 && references.includes('Controller Alpha (A)') && references.includes('Controller Beta (B)');
// Earlier real native inventory quotes, rebound only in this unit fixture to
// the deterministic section contexts. Never submitted to a product endpoint.
const mapped = JSON.parse(fs.readFileSync(path.join(__dirname,'peer-vehicle-inventory-contexts.json'),'utf8'));
const vehicleSource = fs.readFileSync('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt','utf8');
if(crypto.createHash('sha256').update(vehicleSource).digest('hex')!==mapped.source_sha256) throw new Error('Original vehicle file changed');
const inventory = mapped.inventory.map(row=>({...row.earlier_native_inventory_fact,source_context:row.current_deterministic_context}));
if(!inventory.every(fact=>vehicleSource.includes(fact.source_quote))) throw new Error('Inventory quote is not literal');
const vehicleQuestions = api.documentDeviceQuestions(vehicleSource,{source_complete:true,interpretation:{components:inventory}});
const controllers = inventory.filter(fact=>fact.kind==='INSTANCE' && fact.role==='CONTROLLER').map(fact=>fact.name);
const overviews = vehicleQuestions.filter(question=>question.role==='CONTROLLER' && question.source_quote.includes('Powertrain') && question.source_quote.includes('Infotainment'));
const vehiclePassed = controllers.length===5 && overviews.length===2 && overviews.every(question=>(question.covered_by??[]).length===5 && controllers.every(name=>question.covered_by.includes(name)));
const report = {status:passed&&vehiclePassed?'PASSED':'FAILED',scope:'pure typed adapter fixtures; not new Qwen, productive Wizard or model evidence',at:new Date().toISOString(),helper_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),source,components,questions,expected:'The overview references the two explicitly named instances in another section of the same Anlage Nord, requiring explicit coverage confirmation and no duplicate anonymous controllers.',original_vehicle:{status:vehiclePassed?'PASSED':'FAILED',source_sha256:mapped.source_sha256,source_chars:vehicleSource.length,controllers,overviews,fixture_provenance:'Earlier native literal inventory plus current deterministic contexts; no new inference or product writes.'}};
fs.writeFileSync(path.join(__dirname,'peer-staged-overview-coverage.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report));
if(!passed || !vehiclePassed) throw new Error('Same-profile overview cannot reference explicit instances in different document sections.');
