import {chromium} from '../../../frontend/node_modules/playwright/index.mjs';
import {writeFile,readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const job='33f124d0ad234c989dcbbd773e6393f9',base='http://127.0.0.1:13500';
const browser=await chromium.launch({headless:true});
try {
 const page=await browser.newPage({viewport:{width:1736,height:1244}});page.setDefaultTimeout(60000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const prod=JSON.parse(await readFile(new URL('production-verification.json',import.meta.url),'utf8'));
 const patch=await(await page.request.get(base+'/frontend-patch.json')).json();assert.equal(patch.artifact_sha256,prod.artifact_sha256);
 await page.goto(`${base}/studio/simulation?project=20261009072206008-4bb505f1&job=${job}`);
 await page.locator(`.model-simulation-runner[data-job-id="${job}"]`).waitFor();
 await page.getByRole('button',{name:'Steuerung',exact:true}).click();
 const controls=page.locator('#simulation-controls');await controls.locator('.simulation-command-bar').waitFor();
 assert.equal(await controls.getByText(/^Gespeicherter Simulationslauf/).count(),0);
 assert.equal(await controls.getByRole('link',{name:'Ergebnis und Bewertung öffnen →',exact:true}).count(),0);
 assert.equal(await page.getByRole('tab',{name:'SIGNALS',exact:true}).getAttribute('aria-selected'),'true');
 assert(await page.locator('.signal-lane').count()>0);assert.deepEqual(errors,[]);
 await page.screenshot({path:new URL('simulation.jpg',import.meta.url).pathname.replace(/^\/(\w:)/,'$1'),type:'jpeg'});
 await writeFile(new URL('production-functional.json',import.meta.url),JSON.stringify({status:'PASSED',artifact_sha256:patch.artifact_sha256,patch_id:patch.patch_id,job,notice_absent:true,stored_signal_view_present:true,page_errors:errors,scope:'Focused existing-job browser check, no simulation execution'},null,2));
 console.log('Focused production UI verification PASSED');
} finally {await browser.close();}
