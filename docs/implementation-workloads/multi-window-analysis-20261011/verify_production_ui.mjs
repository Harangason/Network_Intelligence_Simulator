// Read existing production data; never start a run or change the engineering model.
import {chromium} from '../../../frontend/node_modules/playwright/index.mjs';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const project='20261009072206008-4bb505f1',job='33f124d0ad234c989dcbbd773e6393f9';
const base='http://127.0.0.1:13500',headers={'X-Project-ID':project};
const evidence={status:'RUNNING',project,job,captured_at:new Date().toISOString(),scope:'Existing historical run, real browser windows, time coupling, independence/reattachment and stored bus-load projection and engine-backed fault-editor explanations. No simulation started or engineering model changed; the existing primary view may persist its selected-run context.',observations:{}};
const browser=await chromium.launch({headless:true});
try {
  const page=await browser.newPage({viewport:{width:1401,height:1244}});page.setDefaultTimeout(60000);
  await page.goto(`${base}/studio/simulation?project=${project}&job=${job}`);
  const workflow=await(await page.request.get(`${base}/api/engineering/workflow?view=summary`,{headers})).json();
  const persistedJob=await(await page.request.get(`${base}/api/simulations/${job}`,{headers})).json();
  const canonicalProject=workflow.project_id;
  // Existing compact project IDs resolve through normalize_context_project_id.
  // Bind both the workflow and original job before checking the detached URL.
  assert.equal(canonicalProject,`network-project-${project}`);
  assert.equal(persistedJob.project_id,canonicalProject);
  const before=(await(await page.request.get(`${base}/api/simulations`,{headers})).json()).jobs.map(j=>j.id).sort();
  await page.waitForFunction(()=>{const range=document.querySelector('[aria-label="Simulationszeit"]');return range&&Number(range.max)<2&&range.closest('.simulation-timeline').querySelector('span').textContent==='PAUSED';});
  const faultEditor=page.locator('.fault-editor');
  const faultType=faultEditor.getByRole('combobox',{name:'Fehlertyp',exact:true});
  const supplementary=faultEditor.getByLabel('Fehler-Zusatzwert',{exact:true});
  assert.equal(await faultEditor.getByLabel('Fehlerbeginn (s)',{exact:true}).inputValue(),'0.25');
  assert.equal(await faultEditor.getByLabel('Fehlerende (s)',{exact:true}).inputValue(),'1.5');
  assert.equal(await faultType.inputValue(),'SIGNAL_STUCK');
  assert(await supplementary.isDisabled());
  assert.match(await faultEditor.locator('#fault-type-description').innerText(),/Zusatzwert wird nicht verwendet/);
  await faultType.selectOption('SIGNAL_OFFSET');
  assert(await supplementary.isEnabled());
  assert.match(await faultEditor.locator('#fault-type-description').innerText(),/Addiert den Zusatzwert/);
  await faultEditor.locator('.fault-glossary summary').click();
  const glossaryEntries=await faultEditor.locator('.fault-glossary dt').count();assert.equal(glossaryEntries,29);
  await faultEditor.locator('.fault-glossary summary').click();await faultType.selectOption('SIGNAL_STUCK');
  const faultEditorReview={glossary_entries:glossaryEntries,absolute_start_s:.25,absolute_end_s:1.5,unused_stuck_value_disabled:true,offset_value_editable:true};
  const tools=page.getByRole('region',{name:'Analysefenster und Arbeitsbereich'});
  const open=async view=>{
    await tools.getByRole('combobox',{name:'Ansicht',exact:true}).selectOption(view);
    const popup=page.waitForEvent('popup');await tools.getByRole('button',{name:'↗ In neuem Fenster öffnen',exact:true}).click();
    const child=await popup;child.setDefaultTimeout(60000);
    await child.waitForFunction(()=>Number(document.querySelector('.trace-control-panel > p')?.textContent?.match(/^(\d+) Ereignisse/)?.[1])>0);
    assert.equal(new URL(child.url()).searchParams.get('project'),canonicalProject);assert.equal(new URL(child.url()).searchParams.get('job'),job);
    return child;
  };
  const trace=await open('trace');
  await page.bringToFront();const time=page.getByLabel('Simulationszeit',{exact:true});
  await time.press('Home');
  await page.waitForFunction(()=>Number(document.querySelector('[aria-label="Simulationszeit"]')?.value)===0);
  const advance=async(start,count)=>{
    for(let i=1;i<=count;i++){
      await time.press('ArrowRight');
      await page.waitForFunction(expected=>Number(document.querySelector('[aria-label="Simulationszeit"]')?.value)===expected,(start+i)/1000);
    }
  };
  await advance(0,20);
  await trace.waitForFunction(()=>document.querySelector('[aria-label="Gemeinsamer Zeitcursor"]')?.textContent?.includes('0.02 s'));
  assert.equal(await time.inputValue(),'0.02');
  assert.equal(await trace.locator('.simulation-command-bar').count(),0);
  await trace.getByRole('combobox',{name:'Fensterkopplung',exact:true}).selectOption('INDEPENDENT');
  await page.bringToFront();await advance(20,20);
  await page.waitForFunction(()=>document.querySelector('[aria-label="Gemeinsamer Zeitcursor"]')?.textContent?.includes('0.04 s'));
  assert.match(await trace.getByLabel('Gemeinsamer Zeitcursor').textContent(),/0\.02 s/);
  await trace.getByRole('combobox',{name:'Fensterkopplung',exact:true}).selectOption('FOLLOW_PRIMARY');
  await trace.waitForFunction(()=>document.querySelector('[aria-label="Gemeinsamer Zeitcursor"]')?.textContent?.includes('0.04 s'));
  const load=await open('load');await load.locator('.bus-load-grid article').first().waitFor();
  const networks=await load.locator('.bus-load-grid article').count();assert(networks>0&&networks<=100);
  const after=(await(await page.request.get(`${base}/api/simulations`,{headers})).json()).jobs.map(j=>j.id).sort();assert.deepEqual(after,before);
  evidence.observations={project_identity:{requested:project,canonical:canonicalProject,original_job_project:persistedJob.project_id},trace_url:trace.url(),coupled_cursor_s:.02,independent_cursor_s:.02,reattached_cursor_s:.04,stored_networks:networks,unchanged_job_ids:after,fault_editor:faultEditorReview};
  await page.screenshot({path:new URL('production-multi-window.jpg',import.meta.url).pathname.replace(/^\/(\w:)/,'$1'),type:'jpeg',quality:85});
  evidence.status='PASSED';
  await writeFile(new URL('production-functional.json',import.meta.url),JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));
}finally{await browser.close();}
