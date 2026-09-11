import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';
const project='network-project-20260910042736034-d11591d0';
const base='http://127.0.0.1:15050/api/engineering';
async function api(path,body) {
  const r=await fetch(base+path,{method:body?'POST':'GET',headers:{'X-Project-ID':project,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
  assert.ok(r.ok,path+': '+r.status);return r.json();
}
const before=await api('/workflow/network-view');
const plan=await api('/workflow/communication-repair/preview',{});
assert.ok(plan.architecture.communications>0);
assert.equal(plan.architecture.flows.length,plan.architecture.communications);
assert.ok(plan.architecture.device_io>0);
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1688,height:1272}});
let failed=false,previews=0;const writes=[],errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.route('**/api/engineering/workflow/communication-repair/**',async route=>{
  if(route.request().url().endsWith('/preview')){previews++;return route.fulfill({json:plan});}
  const body=route.request().postDataJSON();writes.push(body);
  const group=plan.groups.find(g=>body.choices?.[g.id]);
  const option=group?.options.find(o=>o.id===body.choices[group.id]);
  assert.ok(option);assert.equal(body.automatic,undefined);
  return route.fulfill({json:{applied:[{id:group.id,label:option.label,routes:option.comparison.length,messages:group.messages.length}],plan:{...plan,groups:[]}}});
});
try{
  await page.goto('http://127.0.0.1:13500/studio/engineering?project='+project);
  await page.getByRole('button',{name:'Reparatur-Agent',exact:true}).waitFor();
  assert.equal(previews,0);
  const dialog=page.getByRole('dialog',{name:'Reparatur-Agent für Kommunikation'});
  await page.getByRole('button',{name:'Reparatur-Agent',exact:true}).click();
  await dialog.getByText('Aktuelle Architektur und Funktionspartner',{exact:true}).waitFor();
  assert.equal(writes.length,0);
  assert.match(await dialog.innerText(),/aktuelle Hardwarearchitektur bestimmt die neuen Wege/);
  const details=dialog.locator('.eng-repair-architecture details');
  await details.locator('summary').click();
  assert.equal(await details.locator('tbody tr').count(),plan.architecture.communications);
  assert.match(await details.innerText(),/Geräte-I\/O/);
  await page.screenshot({path:'../backend/runtime/functional-architecture-overview.png'});
  await details.locator('summary').click();
  const available=plan.groups.find(g=>g.options.some(o=>o.action==='adopt'));
  if(available){
    const option=available.options.find(o=>o.action==='adopt');
    const choice=dialog.locator('.eng-repair-option').filter({has:page.getByText(option.label,{exact:true})}).first();
    await choice.locator('tbody tr').first().waitFor();
    assert.match(await choice.innerText(),/Route \/ Funktionspartner/);
    assert.ok(option.comparison.every(r=>r.functions?.source));
    await choice.getByRole('button',{name:'Neue Führung übernehmen',exact:true}).click();
    await dialog.getByText('Verknüpfungen repariert',{exact:true}).waitFor();
    assert.equal(writes.length,1);
  }
  await dialog.getByRole('button',{name:'Schließen',exact:true}).click();
  await page.goto('http://127.0.0.1:13500/studio/routing?project='+project);
  await page.getByRole('button',{name:'Reparatur-Agent',exact:true}).click();
  await dialog.getByText('Aktuelle Architektur und Funktionspartner',{exact:true}).waitFor();
  await dialog.getByRole('button',{name:'Schließen',exact:true}).click();
  assert.deepEqual(errors,[]);
  const after=await api('/workflow/network-view');
  assert.deepEqual(after.topology,before.topology);
  assert.deepEqual(after.edit_tokens,before.edit_tokens, 'Canonical topology and parameters remain unchanged; workflow status may refresh on navigation');
  await fs.writeFile('../backend/runtime/functional-architecture-ui.json',JSON.stringify({communications:plan.architecture.communications,resolved:plan.architecture.resolved,deviceIO:plan.architecture.device_io,unresolved:plan.architecture.unresolved.length,previews,mockedChoices:writes.length,errors,userTopologyUnchanged:true},null,2));
  console.log('PASS: current architecture, explicit function partners and device I/O, both pages, reviewed choice, user topology unchanged');
}catch(e){failed=true;console.error(e);}
finally{const cdp=await browser.newBrowserCDPSession();await Promise.race([cdp.send('Browser.close').catch(()=>{}),new Promise(r=>setTimeout(r,2000))]);process.exit(failed?1:0);}
