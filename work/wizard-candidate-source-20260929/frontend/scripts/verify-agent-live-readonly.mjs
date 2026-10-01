import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const output=fileURLToPath(new URL('../../backend/test-output/',import.meta.url));
const url=process.env.SIMULATOR_TEST_URL;
const prefix=process.env.SIMULATOR_TEST_REPORT_PREFIX ?? 'mcp-live';
if(!url) throw new Error('Explicit application URL required.');
const report={url,project:'default',browsers:[],errors:[]};
const browsers=[];
try {
 for(const channel of ['chrome','msedge']) {
  const browser=await chromium.launch({channel,headless:true}); browsers.push(browser);
  const page=await browser.newPage(); page.on('pageerror',error=>report.errors.push(error.message));
  await page.goto(url+'/studio/engineering?project=default');
  const health=await page.evaluate(async()=>await(await fetch('/api/engineering/health')).json());
  assert.equal(health.schema_version,Number(process.env.SIMULATOR_EXPECTED_SCHEMA ?? 23));
  await page.getByRole('button',{name:'AI Assistant öffnen'}).click();
  report.browsers.push({channel,version:browser.version(),health});
  if(channel==='chrome') {
   await page.getByRole('textbox',{name:'Nachricht an den Engineering-Assistenten'}).fill('Wie viele Hardwareobjekte sind im aktiven Projekt? Lies den Projektstand. Antworte in einem Satz ohne Rückfrage.');
   const responsePromise=page.waitForResponse(response=>response.url().endsWith('/api/agent/chat'),{timeout:300000});
   await page.getByRole('button',{name:'Senden',exact:true}).click();
   const response=await responsePromise;
   assert(response.ok());
   const stream=await response.text();
   assert(stream.includes('ANSWERED'),stream);
   assert(!stream.includes('Der Agentenlauf konnte nicht fortgesetzt werden'),stream);
   await page.waitForFunction(()=>!document.querySelector('textarea[aria-label="Nachricht an den Engineering-Assistenten"]').disabled);
   await page.screenshot({path:output+prefix+'.png',fullPage:true});
   report.chatCompleted=true;
  }
 }
 assert.deepEqual(report.errors,[]);
 await fs.writeFile(output+prefix+'-report.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
} catch(error) { console.error(error); process.exitCode=1; } finally {
 for(const browser of browsers) await Promise.race([browser.close(), new Promise(resolve=>setTimeout(resolve,5000))]);
 process.exit(process.exitCode ?? 0);
}

