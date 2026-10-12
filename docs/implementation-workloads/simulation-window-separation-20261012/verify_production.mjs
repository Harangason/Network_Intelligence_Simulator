import {chromium} from '../../../frontend/node_modules/playwright/index.mjs';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const base='http://127.0.0.1:13500',project='20261009072206008-4bb505f1',job='33f124d0ad234c989dcbbd773e6393f9';
const path=n=>new URL(n,import.meta.url).pathname.replace(/^\/(\w:)/,'$1');
const browser=await chromium.launch({headless:true});let page;const errors=[],observations={};
try {
 page=await browser.newPage({viewport:{width:1736,height:1244}});page.setDefaultTimeout(180000);page.on('pageerror',e=>errors.push(e.message));
 const deployed=JSON.parse(await readFile(path('production-verification.json'),'utf8'));
 const patch=await(await page.request.get(base+'/frontend-patch.json')).json();assert.equal(patch.artifact_sha256,deployed.artifact_sha256);
 await page.goto(`${base}/studio/simulation?project=${project}&job=${job}`);
 const timeline=page.locator('.simulation-timeline');await page.locator(`.model-simulation-runner[data-job-id="${job}"]`).waitFor();await timeline.getByRole('button',{name:'Wiedergabe',exact:true}).waitFor();
 await page.getByRole('button',{name:'Steuerung',exact:true}).click();
 const form=page.locator('.simulation-command-bar');await form.locator('.trace-format-trigger:enabled').waitFor();
 const fields=await form.locator(':scope > label,:scope > .trace-format-control,:scope > .simulation-transport-controls').all();
 const boxes=await Promise.all(fields.map(f=>f.boundingBox()));assert.equal(boxes.length,6);
 const bottoms=boxes.map(b=>b.y+b.height);assert(Math.max(...bottoms)-Math.min(...bottoms)<3,'All command controls share one desktop row');
 const formBox=await form.boundingBox();assert(formBox.height<90,'One-row command panel must be compact');observations.command_row={box:formBox,fields:boxes};
 assert.equal(await form.getByLabel('Dauer (s)',{exact:true}).inputValue(),'2');assert.equal(await form.getByLabel('Seed',{exact:true}).inputValue(),'42');
 const sim=page.getByRole('region',{name:'Simulationsfenster',exact:true}),trace=page.getByRole('region',{name:'Trace-Analysefenster',exact:true});
 const simBox=await sim.boundingBox(),traceBox=await trace.boundingBox();assert(Math.abs(simBox.y-traceBox.y)<2 && traceBox.x>simBox.x+simBox.width);observations.columns={simulation:simBox,trace:traceBox};
 const origin=page.url();
 async function popup(action,board,view,mode) {
   const [child]=await Promise.all([page.waitForEvent('popup'),action()]);await child.waitForURL(url=>url.pathname===board);
   const url=new URL(child.url());assert.equal(url.searchParams.get('project').replace(/^network-project-/,''),project);assert.equal(url.searchParams.get('job'),job);assert.equal(url.searchParams.get('view'),view);assert.equal(url.searchParams.get('link'),mode);assert.equal(page.url(),origin);
   if(board==='/studio/simulation') {child.setDefaultTimeout(45000);const selected=child.getByRole('tab',{name:'SEQUENCE',exact:true});try {await selected.waitFor();assert.equal(await selected.getAttribute('aria-selected'),'true','Requested simulation view must actually be displayed');await child.locator(`.model-simulation-runner[data-job-id="${job}"]`).waitFor();await child.getByRole('button',{name:'Steuerung',exact:true}).click();assert.equal(await child.locator('.simulation-command-bar').count(),0,'Secondary simulation is read-only');assert.equal(await child.locator('.trace-analysis-workbench').count(),0);} catch(e) {await writeFile(path('child-failure.json'),JSON.stringify({url:child.url(),text:await child.locator('body').innerText()},null,2));throw e;}}
   const href=child.url();await child.close();return href;
 }
 await sim.getByLabel('Simulationsansicht',{exact:true}).selectOption('sequence');
 observations.sim_popup=await popup(()=>sim.getByRole('button',{name:'Simulationsfenster öffnen',exact:true}).click(),'/studio/simulation','sequence','FOLLOW_PRIMARY');
 observations.sim_independent=await popup(()=>sim.getByRole('button',{name:'Simulation unabhängig öffnen',exact:true}).click(),'/studio/simulation','sequence','INDEPENDENT');
 await trace.getByLabel('Trace-Ansicht',{exact:true}).selectOption('signals');
 observations.trace_popup=await popup(()=>trace.getByRole('button',{name:'Trace-Fenster öffnen',exact:true}).click(),'/trace-analysis','signals','FOLLOW_PRIMARY');
 observations.trace_compare=await popup(()=>trace.getByRole('button',{name:'Trace vergleichen',exact:true}).click(),'/trace-analysis','trace','COMPARE');
 console.log('Compact row, columns and explicit popup destinations verified');
 const tools=page.locator('.analysis-window-tools');await tools.locator('details > summary').click();
 const opened=[];page.on('popup',p=>opened.push(p));
 await tools.getByRole('button',{name:'Trace Investigation',exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.analysis-window-links a').length>=3);
 assert.equal(page.url(),origin);assert.equal(opened.length,3);
 for(const child of opened) {await child.waitForURL(url=>url.pathname==='/trace-analysis');assert.equal(new URL(child.url()).searchParams.get('job'),job);await child.close();}
 const editor=tools.locator('.analysis-profile-editor');await editor.getByLabel('Profilname').fill('Fensterprüfung');await editor.getByRole('button',{name:'Arbeitsbereich speichern',exact:true}).click();
 const workspaceProject=new URL(observations.sim_popup).searchParams.get('project');
 const profile=await page.evaluate(project=>JSON.parse(localStorage.getItem(`nis.analysis.profiles.v1.${project}`)).find(p=>p.name==='Fensterprüfung'),workspaceProject);
 assert.equal(profile.primary_board,'simulation');assert(profile.secondary_boards.every(b=>['simulation','trace'].includes(b)));observations.saved_profile=profile;
 const oldCount=opened.length;await editor.getByRole('button',{name:'Arbeitsbereich wiederherstellen',exact:true}).click();assert.equal(page.url(),origin);
 for(const child of opened.slice(oldCount))await child.close();
 // Only local browser profile metadata was saved. Remove the test profile.
 await page.evaluate(project=>{const key=`nis.analysis.profiles.v1.${project}`;localStorage.setItem(key,JSON.stringify(JSON.parse(localStorage.getItem(key)).filter(p=>p.name!=='Fensterprüfung')));},workspaceProject);
 for(const width of [1736,390]) {await page.setViewportSize({width,height:1244});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path(`simulation-${width}.jpg`),type:'jpeg'});}
 assert.deepEqual(errors,[]);
 await writeFile(path('production-functional.json'),JSON.stringify({status:'PASSED',patch_id:patch.patch_id,artifact_sha256:patch.artifact_sha256,scope:'Existing historical job, one-row controls, two columns, actual popup URLs, presets and local profile source boards; responsive UI; no simulation execution or campaign',observations,page_errors:errors,current_simulation_preserved:true},null,2));
 console.log('Focused production window verification PASSED');
} catch(error) {await writeFile(path('production-functional-failed.json'),JSON.stringify({status:'FAILED',error:String(error),observations,page_errors:errors,text:await page?.locator('main').innerText().catch(()=> '')},null,2));await page?.screenshot({path:path('failed-browser.jpg'),type:'jpeg'}).catch(()=>{});throw error;} finally {await browser.close();}
