import {chromium} from '../../../frontend/node_modules/playwright/index.mjs';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true}),base='http://127.0.0.1:13500',job='33f124d0ad234c989dcbbd773e6393f9';
const file=n=>new URL(n,import.meta.url),local=n=>file(n).pathname.replace(/^\/(\w:)/,'$1');
const errors=[],nativeDialogs=[],requests={scenario:[],export:0,project:[]};let page,scenarioFail=true,exportFail=true;
const project='network-project-20261009072206008-4bb505f1';
try {
 page=await browser.newPage({viewport:{width:1736,height:1244}});page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));page.on('dialog',async d=>{nativeDialogs.push(d.type());await d.dismiss();});
 // These routes validate only UI request/response handling, never write product data.
 await page.route('**/api/engineering/simulation/scenarios?**',async route=>{
  assert.equal(route.request().method(),'POST');const data=route.request().postDataJSON();requests.scenario.push(data);
  await route.fulfill({status:scenarioFail?503:200,contentType:'application/json',body:JSON.stringify(scenarioFail?{error:'Speicherdienst vorübergehend nicht erreichbar'}:{...data,name:data.name})});
 });
 await page.route('**/api/engineering/projects/export*',async route=>{requests.export++;
  await route.fulfill({status:exportFail?503:200,contentType:'application/json',body:JSON.stringify(exportFail?{error:'Projektablage vorübergehend nicht erreichbar'}:{format:'network-intelligence-project',bundle_version:1,project_id:project,generated_at:new Date().toISOString(),workflow:{},source_data:{},project_data:{}})});
 });
 await page.route('**/api/engineering/projects/save',async route=>{assert.equal(route.request().method(),'POST');requests.project.push(route.request().postDataJSON());await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({path:'SAVED/UI-check.nis-project.json'})});});
 const prod=JSON.parse(await readFile(file('production-verification.json'),'utf8'));
 const patch=await(await page.request.get(base+'/frontend-patch.json')).json();assert.equal(patch.artifact_sha256,prod.artifact_sha256);
 await page.goto(`${base}/studio/simulation?project=20261009072206008-4bb505f1&job=${job}`);await page.locator(`.model-simulation-runner[data-job-id="${job}"]`).waitFor();
 await page.getByRole('button',{name:'Hell',exact:true}).click();
 const save=page.locator('header.topbar').getByRole('button',{name:'Speichern',exact:true});await save.click();
 const projectDialog=page.getByRole('dialog',{name:'Projekt speichern',exact:true});await projectDialog.waitFor();assert.equal(requests.export,0);
 assert.equal(await projectDialog.getByLabel('Projekt-ID').inputValue(),project);assert.equal(await projectDialog.getByLabel('Projekt-ID').getAttribute('readonly'),'');
 await page.screenshot({path:local('project-dialog.jpg'),type:'jpeg'});
 await page.keyboard.press('Escape');await projectDialog.waitFor({state:'hidden'});assert.equal(requests.export,0);
 await save.click();await projectDialog.getByRole('button',{name:'In SAVED speichern',exact:true}).click();
 await projectDialog.getByRole('alert').waitFor();assert.equal(await projectDialog.isVisible(),true);assert.equal(requests.project.length,0);
 exportFail=false;await projectDialog.getByRole('button',{name:'In SAVED speichern',exact:true}).click();await projectDialog.waitFor({state:'hidden'});
 assert.deepEqual(requests.project,[{project_id:project}]);
 await page.getByRole('button',{name:'Steuerung',exact:true}).click();const command=page.locator('.simulation-command-panel');await command.locator(':scope > summary').click();
 const scenarioButton=command.getByRole('button',{name:'Speichern unter',exact:true});await scenarioButton.click();
 const scenario=page.getByRole('dialog',{name:'Szenario speichern unter',exact:true});await scenario.waitFor();assert.equal(requests.scenario.length,0);
 const name=scenario.getByLabel('Szenarioname');assert((await name.inputValue()).startsWith('Golden / Ideal'));
 await name.fill('   ');assert.equal(await scenario.getByRole('button',{name:'Szenario speichern',exact:true}).isDisabled(),true);
 await name.fill('Browserprüfung Szenario');await page.screenshot({path:local('scenario-dialog.jpg'),type:'jpeg'});
 await scenario.getByRole('button',{name:'Abbrechen',exact:true}).click();assert.equal(requests.scenario.length,0);
 await scenarioButton.click();await name.fill('Browserprüfung Szenario');await scenario.getByRole('button',{name:'Szenario speichern',exact:true}).click();
 await scenario.getByRole('alert').waitFor();assert.equal(await name.inputValue(),'Browserprüfung Szenario');assert.equal(await scenario.isVisible(),true);
 scenarioFail=false;await scenario.getByRole('button',{name:'Szenario speichern',exact:true}).click();await scenario.waitFor({state:'hidden'});
 assert.equal(requests.scenario.length,2);const payload=requests.scenario.at(-1);assert.equal(payload.name,'Browserprüfung Szenario');assert.equal(payload.mode,'NORMAL');assert.equal(payload.trace_type,'GOLDEN');assert.equal(payload.duration_s,2);assert(payload.trace_formats.length>0);assert.equal(payload.source,'simulation-workbench');
 for(const width of [1736,390]){await page.setViewportSize({width,height:1244});await save.click();const box=await projectDialog.boundingBox();assert(box.x>=0&&box.x+box.width<=width);await page.keyboard.press('Escape');}
 assert.deepEqual(errors,[]);assert.deepEqual(nativeDialogs,[]);
 await writeFile(file('production-functional.json'),JSON.stringify({status:'PASSED',patch_id:patch.patch_id,artifact_sha256:patch.artifact_sha256,scope:'Actual production UI: immediate application dialogs, cancel/Escape, blank-name check, desktop/mobile fit, intercepted failure/retry/success and save payloads; persistence responses mocked and no product database writes',requests,page_errors:errors,browser_prompt_calls:nativeDialogs,backend_persistence_tested:false},null,2));
 console.log('Focused application save-dialog checks PASSED (persistence responses intercepted)');
} catch(e) {await writeFile(file('production-functional-failed.json'),JSON.stringify({error:String(e),requests,page_errors:errors,text:await page?.locator('main').innerText()},null,2));throw e;} finally {await browser.close();}
