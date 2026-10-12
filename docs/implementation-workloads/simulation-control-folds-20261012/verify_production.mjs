import {chromium} from '../../../frontend/node_modules/playwright/index.mjs';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true}),base='http://127.0.0.1:13500',job='33f124d0ad234c989dcbbd773e6393f9';
const file=n=>new URL(n,import.meta.url),local=n=>file(n).pathname.replace(/^\/(\w:)/,'$1');
const observations={},errors=[];let page;
try {
 page=await browser.newPage({viewport:{width:1736,height:1244}});page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{window.__openArgs=[];const original=window.open;window.open=function(...args){window.__openArgs.push(args);return original.apply(window,args);};});
 const prod=JSON.parse(await readFile(file('production-verification.json'),'utf8'));
 const patch=await(await page.request.get(base+'/frontend-patch.json')).json();assert.equal(patch.artifact_sha256,prod.artifact_sha256);
 await page.goto(`${base}/studio/simulation?project=20261009072206008-4bb505f1&job=${job}`);
 await page.locator(`.model-simulation-runner[data-job-id="${job}"]`).waitFor();
 await page.getByRole('button',{name:'Hell',exact:true}).click();
 const controls=page.locator('#simulation-controls');assert.equal(await controls.isVisible(),false);
 await page.getByRole('button',{name:'Steuerung',exact:true}).click();
 const panels=controls.locator(':scope > details.simulation-control-panel');assert.equal(await panels.count(),4);
 for(const width of [1736,390]) {
  await page.setViewportSize({width,height:1244});
  assert.equal(await panels.evaluateAll(elements=>elements.some(e=>e.open)),false);
  const boxes=await Promise.all((await panels.all()).map(e=>e.boundingBox()));
  for(const b of boxes){assert(Math.abs(b.width-boxes[0].width)<1);assert.equal(b.height,56);}
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  observations['closed_'+width]=boxes;await page.screenshot({path:local('closed-'+width+'.jpg'),type:'jpeg'});
 }
 await page.setViewportSize({width:1736,height:1244});
 const tools=controls.locator('.analysis-window-tools');await tools.locator(':scope > summary').click();
 const sim=tools.getByRole('region',{name:'Simulationsfenster',exact:true});await sim.getByLabel('Simulationsansicht',{exact:true}).selectOption('sequence');
 const origin=page.url();
 const [child]=await Promise.all([page.waitForEvent('popup'),sim.getByRole('button',{name:'Simulationsfenster öffnen',exact:true}).click()]);
 child.setDefaultTimeout(60000);await child.waitForURL(u=>u.pathname==='/studio/simulation');
 await child.locator(`.model-simulation-runner[data-job-id="${job}"]`).waitFor();
 assert.equal(await child.getByRole('tab',{name:'SEQUENCE',exact:true}).getAttribute('aria-selected'),'true');
 assert.equal(await page.getByRole('tab',{name:'SIGNALS',exact:true}).getAttribute('aria-selected'),'true');assert.equal(page.url(),origin);
 assert.equal(new URL(child.url()).searchParams.get('link'),'FOLLOW_PRIMARY');assert.equal(await child.evaluate(()=>window.opener),null);
 const args=await page.evaluate(()=>window.__openArgs.at(-1));assert.equal(args[1],'_blank');assert.equal(args.length,2);
 assert.equal(await tools.locator('.analysis-window-links').count(),0,'No duplicate replacement links after successful opening');
 await page.locator('.simulation-timeline input').fill('0.4');
 await child.waitForFunction(()=>Math.abs(Number(document.querySelector('.simulation-timeline input')?.value)-.4)<.002);
 observations.linked_views={parent:'signals',child:'sequence',source:job,tab_arguments:args,time:.4,parent_preserved:true};
 await child.close();
 // Exercise the fallback path without changing product data.
 await page.evaluate(()=>{window.__savedOpen=window.open;window.open=()=>null;});
 await sim.getByRole('button',{name:'Simulationsfenster öffnen',exact:true}).click();
 const fallback=sim.getByRole('link',{name:'Sequenz · Gekoppelt im Browser öffnen',exact:true});await fallback.waitFor();
 assert.equal(await tools.getByRole('region',{name:'Trace-Analysefenster',exact:true}).locator('.analysis-window-links').count(),0);
 await page.evaluate(()=>{window.open=window.__savedOpen;});
 const [replacement]=await Promise.all([page.waitForEvent('popup'),fallback.click()]);await replacement.waitForURL(u=>u.pathname==='/studio/simulation');assert.equal(new URL(replacement.url()).searchParams.get('view'),'sequence');assert.equal(page.url(),origin);await replacement.close();
 observations.blocked_browser_link={simulation_destination:true,parent_preserved:true};
 await tools.locator(':scope > summary').click();
 const command=controls.locator('.simulation-command-panel');await command.locator(':scope > summary').click();
 const form=command.locator('.simulation-command-bar');await form.locator('.trace-format-trigger:enabled').waitFor();
 const boxes=await Promise.all((await form.locator(':scope > label,:scope > .trace-format-control,:scope > .simulation-transport-controls').all()).map(e=>e.boundingBox()));
 const bottoms=boxes.map(b=>b.y+b.height);assert.equal(boxes.length,6);assert(Math.max(...bottoms)-Math.min(...bottoms)<3);await command.locator(':scope > summary').click();
 for(const name of ['.simulation-scope-panel','.fault-editor']){const p=controls.locator(name);await p.locator(':scope > summary').click();assert.equal(await p.evaluate(e=>e.open),true);await p.locator(':scope > summary').click();}
 assert.equal(await panels.evaluateAll(elements=>elements.some(e=>e.open)),false);assert.deepEqual(errors,[]);
 await writeFile(file('production-functional.json'),JSON.stringify({status:'PASSED',patch_id:patch.patch_id,artifact_sha256:patch.artifact_sha256,scope:'Existing job; four equal closed panels at desktop/mobile; normal tab request, real linked signal/sequence views and shared time; blocked-tab replacement link; expandable controls; no simulation execution',observations,page_errors:errors},null,2));
 console.log('Focused browser tab, coupling and collapse checks PASSED');
} catch(e) {await writeFile(file('production-functional-failed.json'),JSON.stringify({error:String(e),observations,page_errors:errors,text:await page?.locator('main').innerText()},null,2));throw e;} finally {await browser.close();}
