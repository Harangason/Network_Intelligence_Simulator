import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const base=process.env.SIMULATOR_TEST_URL;
if (!base) throw new Error('SIMULATOR_TEST_URL must point to an isolated test instance.');
const output=fileURLToPath(new URL('../../backend/test-output/',import.meta.url));
const project='network-project-mcp-browser-'+Date.now();
const browsers=[], errors=[];
const report={project,checks:[],browsers:[]};
try {
  for(const channel of ['chrome','msedge']) {
    const browser=await chromium.launch({channel,headless:true});
    browsers.push(browser); report.browsers.push({channel,version:browser.version()});
  }
  const a=await browsers[0].newPage(),b=await browsers[1].newPage();
  for(const page of [a,b]) page.on('pageerror',e=>errors.push(e.message));
  const url=`${base}/studio/engineering?project=${project}`;
  await a.goto(url);
  await a.getByRole('button',{name:'AI Assistant öffnen'}).click();
  await a.getByRole('textbox',{name:'Nachricht an den Engineering-Assistenten'}).fill('Erzeuge 2 Funktionen für eine 360 Grad Kamera.');
  await a.getByRole('button',{name:'Senden',exact:true}).click();
  await a.getByRole('button',{name:'Vorschlag freigeben',exact:true}).waitFor({timeout:90000});
  const before=await a.evaluate(async(project)=>(await (await fetch('/api/engineering/functions',{headers:{'X-Project-ID':project}})).json()).items,project);
  assert.equal(before.length,0);
  report.checks.push('Chat -> Python Agent -> MCP -> validated proposal, no canonical mutation before review');
  await a.locator('.engineering-proposal-review summary').first().click();
  await a.screenshot({path:output+'mcp-proposal-review.png',fullPage:true});
  await a.getByRole('button',{name:'Vorschlag freigeben',exact:true}).click();
  await a.getByRole('button',{name:'Ins Modell übernehmen',exact:true}).waitFor();
  const approved=await a.evaluate(async(project)=>(await (await fetch('/api/engineering/functions',{headers:{'X-Project-ID':project}})).json()).items,project);
  assert.equal(approved.length,0);
  report.checks.push('Human approval is separate from apply');
  await a.getByRole('button',{name:'Ins Modell übernehmen',exact:true}).click();
  await a.getByText('3 Modellobjekte bestätigt.',{exact:true}).waitFor();
  const functions=await a.evaluate(async(project)=>(await (await fetch('/api/engineering/functions',{headers:{'X-Project-ID':project}})).json()).items,project);
  assert.equal(functions.length,2);
  assert.equal(new Set(functions.map(item=>item.id)).size,2);
  await b.goto(url);
  const other=await b.evaluate(async(project)=>(await (await fetch('/api/engineering/functions',{headers:{'X-Project-ID':project}})).json()).items,project);
  assert.deepEqual(other.map(item=>item.id).sort(),functions.map(item=>item.id).sort());
  report.checks.push('Chrome and Edge share the same project and canonical function IDs');
  await a.screenshot({path:output+'mcp-applied.png',fullPage:true});
  assert.deepEqual(errors,[]);
  report.pageErrors=errors;
  await fs.writeFile(output+'mcp-browser-report.json',JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
} catch(error) {
  console.error(error);process.exitCode=1;
} finally {
  for(const browser of browsers) await Promise.race([browser.close(), new Promise(resolve => setTimeout(resolve, 5000))]);
  process.exit(process.exitCode ?? 0);
}
