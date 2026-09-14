import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const host='http://127.0.0.1:13500';
const project='assistant-ui-'+Date.now();
const live='network-project-20260910042736034-d11591d0';
async function api(path,projectId=project,body,method='POST') {
  const r=await fetch(host+'/api/engineering'+path,{method:body?method:'GET',headers:{'X-Project-ID':projectId,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
  assert.ok(r.ok,`${path}: ${r.status}`);return r.json();
}
await api('/workflow/context',project,{engineering_wizard_settings:{project_name:'Assistent UI-Test'}},'PATCH');
const before=await api('/workflow/network-view',live);
const directory=(await api('/agent/capabilities')).data;
assert.equal(directory.capabilities.length,20);
assert.ok(directory.capabilities.every(c=>c.available));
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1688,height:1272}});
const errors=[];const calls=[];let previews=0;const mutations=[];let failed=false;
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{
  if(r.url().includes('/api/agent/chat'))calls.push(r.headers()['x-project-id']);
  if(r.url().endsWith('/communication-repair/preview'))previews++;
  if(r.url().includes('/api/engineering/')&&['POST','PUT','PATCH','DELETE'].includes(r.method())&&!/\/agent\/|\/preview$/.test(r.url()))mutations.push(r.url().replace(host, ""));
});
try {
  await page.goto(host+'/studio/engineering?project='+project);
  await page.getByRole('button',{name:'AI Assistant öffnen',exact:true}).click();
  await page.getByRole('button',{name:'Fähigkeiten und Wizards',exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.agent-widget-context')?.textContent.includes('Assistent UI-Test'));
  assert.equal(calls.length,0,'Opening must not start an analysis');
  const chat=page.locator('.agent-widget');
  const input=chat.getByRole('textbox',{name:'Nachricht an den Engineering-Assistenten'});
  async function ask(text) {
    await input.fill(text);await chat.getByRole('button',{name:'Senden',exact:true}).click();
  }
  await ask('kennst du den reparatur agenten');
  await chat.locator('.assistant-capability-cards button').filter({hasText:'Reparatur-Agent'}).waitFor();
  assert.match(await chat.innerText(),/bisherigen Funktionspartner/);
  await chat.getByRole('button',{name:'Fähigkeiten und Wizards',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.agent-widget .assistant-capability-cards button').length===21);
  await page.screenshot({path:'../backend/runtime/assistant-capabilities-ui.png'});
  assert.ok(calls.every(p=>p===project));
  await chat.locator('.assistant-capability-cards button').filter({has:page.getByText('Signal anlegen',{exact:true})}).click();
  await page.locator('.eng-object-wizard').waitFor();
  assert.match(await page.locator('.eng-object-wizard').innerText(),/Signale anlegen/);
  assert.equal(new URL(page.url()).searchParams.get('project'),project);
  await page.locator('.eng-object-wizard').getByRole('button',{name:'Abbrechen',exact:true}).click();
  // Existing real dialogs, with no automatic apply, in the isolated UI project.
  for(const launch of ['repair','project','dependencies','structure']) {
    await page.goto(host+'/studio/engineering?project='+project+'&assistant='+launch);
    const dialog=launch==='repair'?page.getByRole('dialog',{name:'Reparatur-Agent für Kommunikation'}):
      launch==='project'?page.locator('.engineering-agent-wizard-dialog'):
      launch==='dependencies'?page.getByRole('dialog').filter({hasText:'Abhängigkeiten geführt aufbauen'}):page.getByRole('dialog').filter({hasText:'KI-Strukturtransfer'});
    await dialog.waitFor({timeout:25000});
  }
  assert.equal(previews,1);
  // A model review writes only durable job/audit metadata, not model resources.
  assert.deepEqual(mutations.filter(url=>!url.includes('/workflow/context') && !url.endsWith('/communication-repair/review')),[]);
  // The widget uses exactly the same saved project name as the workflow header.
  await page.goto(host+'/studio/engineering?project='+live);
  await page.getByRole('button',{name:'AI Assistant öffnen',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.agent-widget-context')?.textContent.includes('NIS Projekt 1'));
  // A stale transport with a different context is rejected before backend execution.
  const mismatch=await fetch(host+'/api/agent/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Project-ID':project},body:JSON.stringify({messages:[{id:'m',role:'user',parts:[{type:'text',text:'Zeige Fähigkeiten'}]}],context:{active_project_id:live}})});
  assert.equal(mismatch.status,409);
  const after=await api('/workflow/network-view',live);
  assert.deepEqual(after.topology,before.topology);assert.deepEqual(after.edit_tokens,before.edit_tokens);
  assert.deepEqual(errors,[]);
  await fs.writeFile('../backend/runtime/assistant-capabilities-ui.json',JSON.stringify({project,catalog:directory.capabilities.length,chatCalls:calls.length,previews,mutations,projectName:true,scopeConflict:409,userModelUnchanged:true,errors},null,2));
  console.log('PASS: real chat/MCP capability answers, tiles, signal and agent wizards, project name, scope checks, no user-model writes');
} catch(error) { failed=true;console.error(error);await page.screenshot({path:'../backend/runtime/assistant-capabilities-failure.png'}); }
finally { const cdp=await browser.newBrowserCDPSession();await Promise.race([cdp.send('Browser.close').catch(()=>{}),new Promise(r=>setTimeout(r,2000))]);process.exit(failed?1:0); }
