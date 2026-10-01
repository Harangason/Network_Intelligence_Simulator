import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const base=process.env.SIMULATOR_TEST_URL;
if (!base) throw new Error('SIMULATOR_TEST_URL must point to an isolated test instance.');
const output=process.env.SIMULATOR_TEST_OUTPUT || fileURLToPath(new URL('../../backend/test-output',import.meta.url));
await fs.mkdir(output,{recursive:true});
const project='network-project-browser-'+Date.now();
const reports={project,browsers:[],checks:[]};
const browsers=[];
try {
  for(const channel of ['chrome','msedge']) {
    const browser=await chromium.launch({channel,headless:true});browsers.push(browser);
    reports.browsers.push({channel,version:browser.version()});
  }
  const a=await browsers[0].newPage(), b=await browsers[1].newPage();
  const errors=[];
  for(const page of [a,b])page.on('pageerror',e=>errors.push(e.message));
  await a.goto(`${base}/studio/engineering?project=${project}`);
  await a.getByRole('button',{name:'+ ECU',exact:true}).click();
  await a.locator('#name').fill('SharedController');
  for(let i=0;i<3;i++)await a.locator('form').getByRole('button',{name:'Weiter',exact:true}).click();
  assert.match(await a.locator('form').innerText(), /Objekt anlegen/);
  await a.locator('form').getByRole('button',{name:/anlegen|speichern/i}).click();
  await a.locator('#name').waitFor({state:'detached'});
  const nodes=await a.evaluate(async (project)=>(await (await fetch('/api/engineering/hardware-nodes',{headers:{'X-Project-ID':project}})).json()).items,project);
  assert.equal(nodes.length,1);const id=nodes[0].id;
  reports.checks.push('Chrome: ECU through all four wizard steps');
  const editUrl=`${base}/studio/engineering?project=${project}&object=${id}&edit=1`;
  await Promise.all([a.waitForResponse(r=>r.url().includes("/workflow/revision")), b.waitForResponse(r=>r.url().includes("/workflow/revision")), a.goto(editUrl),b.goto(editUrl)]);
  await Promise.all([a.locator('[name="edit_description"]').waitFor(),b.locator('[name="edit_description"]').waitFor()]);
  await a.locator('[name="edit_description"]').fill('Saved from Chrome');
  await b.locator('[name="edit_description"]').fill('Unsaved Edge draft');
  const saved=a.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().includes(id));
  await a.locator('form.eng-edit-form').getByRole('button',{name:/speichern/i}).click();
  assert.equal((await saved).status(),200);
  await b.getByText(/^Neuer Projektstand verf/).waitFor({timeout:16000});
  assert.equal(await b.locator('[name="edit_description"]').inputValue(),'Unsaved Edge draft');
  const rejected=b.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().includes(id));
  await b.locator('form.eng-edit-form').getByRole('button',{name:/speichern/i}).click();
  assert.equal((await rejected).status(),409);
  assert.equal(await b.locator('[name="edit_description"]').inputValue(),'Unsaved Edge draft');
  const actual=await a.evaluate(async({project,id})=>await (await fetch(`/api/engineering/hardware-nodes/${id}`,{headers:{'X-Project-ID':project}})).json(),{project,id});
  assert.equal(actual.description,'Saved from Chrome');
  reports.checks.push('Edge sees remote change; stale save returns 409 and preserves draft; Chrome data remains saved');
  await b.screenshot({path:`${output}/audit-edge-conflict.png`,fullPage:true});
  for(const path of ['/studio/routing','/studio?mode=network','/studio?mode=parameters','/studio/capacity','/studio/validation','/studio/simulation','/studio/results','/studio/intelligence','/studio/settings']) {
    const url=new URL(path,base);url.searchParams.set('project',project);
    const response=await a.goto(url.href);assert.equal(response.status(),200);
    await a.getByRole('button',{name:'Projektlink',exact:true}).waitFor();
    assert.ok((await a.locator('body').innerText()).length>200);
    reports.checks.push(path+' loads with the same project ID');
  }
  reports.pageErrors=errors;assert.deepEqual(errors,[]);
  await fs.writeFile(`${output}/audit-browser-report.json`,JSON.stringify(reports,null,2));
  console.log(JSON.stringify(reports));
} catch(e) {
  console.error(e);
  process.exitCode=1;
} finally { await Promise.all(browsers.map(browser=>Promise.race([browser.close(),new Promise(r=>setTimeout(r,3000))]))); }
process.exit(process.exitCode || 0);

