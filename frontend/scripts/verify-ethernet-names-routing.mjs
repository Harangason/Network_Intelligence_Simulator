import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from 'playwright';
const project='network-project-20260910042736034-d11591d0';
const headers={'X-Project-ID':project};
async function api(path){const r=await fetch('http://127.0.0.1:15050/api/engineering'+path,{headers});assert.ok(r.ok);return r.json();}
const state=await api('/workflow');
const routes=(await api('/routing?limit=500')).items;
const route=routes.find(r=>r.source.network_id==='Diagnose_09-S01')??routes.find(r=>r.source.network_id==='Infotainment_08-S01');
assert.ok(route,'An existing route on a renamed network is required');
const expected=state.parameters.networks.find(n=>n.id===route.source.network_id).name;
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1371,height:1272}});let failed=false;const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
  await page.goto('http://127.0.0.1:13500/studio/routing?project='+project+'&route='+route.id);
  await page.locator('.routing-detail').waitFor();
  const rail=page.locator('.routing-detail-rail').filter({hasText:route.route_code});await rail.waitFor();await rail.click();
  await page.getByRole('button',{name:'Wizard',exact:true}).click();
  const dialog=page.locator('.routing-wizard-dialog');await dialog.waitFor();
  await dialog.getByRole('button',{name:/02.*Quelle/i}).click();
  const select=dialog.locator('label').filter({hasText:/^Source Interface/}).locator('select');await select.waitFor();
  const labels=await select.locator('option').allTextContents();
  assert.ok(labels.some(label=>label.includes(expected)),JSON.stringify({expected,labels}));
  assert.ok(!labels.some(label=>label.includes('Netz: '+route.source.network_id)),JSON.stringify(labels));
  await page.screenshot({path:'../backend/runtime/ethernet-names-routing-verified.png'});
  await dialog.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  const after=await api('/workflow');assert.deepEqual(after.topology,state.topology);assert.deepEqual(after.parameters,state.parameters);
  assert.equal(errors.length,0,errors.join('\n'));
  await fs.writeFile('../backend/runtime/ethernet-names-routing-verified.json',JSON.stringify({project,route:route.id,expected,labels,modelUnchanged:true,pageErrors:errors},null,2));
  console.log('PASS stored network name in routing list:',expected);
}catch(e){failed=true;console.error(e);await page.screenshot({path:'../backend/runtime/ethernet-names-routing-failure.png'});}
finally{const cdp=await browser.newBrowserCDPSession();await Promise.race([cdp.send('Browser.close').catch(()=>{}),new Promise(r=>setTimeout(r,2000))]);process.exit(failed?1:0);}
