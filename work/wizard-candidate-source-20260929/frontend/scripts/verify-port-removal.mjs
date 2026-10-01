import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-port-removal-ui-' + Date.now();
assert.ok(project.startsWith('network-project-port-removal-ui-'));
const headers = {'X-Project-ID':project, 'Content-Type':'application/json', Connection:'close'};
async function api(path, method='GET', body) {
  const r=await fetch('http://127.0.0.1:15050/api/engineering'+path,{method,headers,body:body?JSON.stringify(body):undefined});
  const data=await r.json();assert.ok(r.ok,JSON.stringify(data));return data;
}
const nodes=[];
let owner;
for(const key of ['owner','existing','test','reverse','connected','branch','wrong']) {
  const hw=await api('/hardware-nodes','POST',{name:key==='owner'?'Fahrerassistenz':key==='test'?'Test':key,domain:'robotics',device_type:key==='owner'?'ECU':'SensorController',
    ...(owner?{identity:{system_owner_id:owner,system_owner_source:'network-editor'}}:{})});
  owner??=hw.id;
  nodes.push({id:key,name:hw.name,engineeringId:hw.id,systemOwnerId:owner,systemOwnerSource:'network-editor',kind:key==='owner'?'ecu':'sensor',x:10,y:10,
    ports:[{id:key+'-port',name:key==='wrong'?'LIN':'CAN FD',bus:key==='wrong'?'lin':'can_fd',side:key==='owner'?'bottom':'right',offset:.5,physicalNetworkId:['owner','existing','test'].includes(key)?'local':key+'-spare'}]});
}
let state=await api('/workflow/topology','PUT',{topology:{nodes,edges:['existing','test'].map(key=>({id:key,source:key,sourcePort:key+'-port',target:'owner',targetPort:'owner-port',bus:'can_fd',physicalNetworkId:'local'}))}});
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1371,height:1272}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));let failed=false;
const port=id=>page.locator(`[data-port-id="${id}-port"]`);
const saved=()=>page.waitForResponse(r=>r.url().endsWith('/workflow/topology')&&r.request().method()==='PUT');
async function ready(){await page.locator('.net-editor').waitFor();await page.getByRole('button',{name:'Vollbild',exact:true}).click();await page.getByRole('button',{name:'Einpassen',exact:true}).click();}
async function persisted(response){const r=await response;assert.equal(r.status(),200,await r.text());state=await api('/workflow');}
async function clickPath(selector){const q=await page.locator(selector).evaluate(p=>{const a=p.getPointAtLength(p.getTotalLength()*.65).matrixTransform(p.getScreenCTM());return{x:a.x,y:a.y};});await page.mouse.click(q.x,q.y);}
try {
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);await ready();
  const original=structuredClone(state.topology);
  // A free connector must be selectable and deleted canonically, including failure/retry.
  await port('reverse').click();assert.equal(await port('reverse').getAttribute('aria-pressed'),'true');
  const reject=r=>r.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:'Test: stale project'})});
  await page.route('**/api/engineering/workflow/topology',reject);
  await page.getByRole('button',{name:'Vergrößern',exact:true}).focus();await page.keyboard.press('Delete');
  await page.getByRole('alert').filter({hasText:'Löschung konnte nicht gespeichert'}).waitFor();
  assert.deepEqual((await api('/workflow')).topology,original);
  assert.equal(await port('reverse').getAttribute('aria-pressed'),'true');
  await page.unroute('**/api/engineering/workflow/topology',reject);
  let response=saved();await page.keyboard.press('Delete');await persisted(response);
  assert.equal(state.topology.nodes.find(n=>n.id==='reverse').ports.length,0);
  assert.equal(state.topology.edges.length,2);assert.ok(state.topology.scene);
  await page.reload();await ready();assert.equal(await port('reverse').count(),0);
  // Right-clicking a connected port removes its lines without removing the device/other branch.
  response=saved();await port('existing').click({button:'right'});await persisted(response);
  assert.equal(state.topology.nodes.find(n=>n.id==='existing').ports.length,0);
  assert.deepEqual(state.topology.edges.map(e=>e.id),['test']);assert.ok(state.topology.scene);
  // A bus branch is selectable even though it shares a controller port with other lines.
  await clickPath('[data-branch-node-id="test"] .net-bus-branch-hit');
  response=saved();await page.keyboard.press('Delete');await persisted(response);
  assert.equal(state.topology.edges.length,0);assert.equal(state.topology.scene.buses.length,0);
  assert.equal(state.topology.nodes.find(n=>n.id==='test').ports.length,1);
  const current=state.topology.nodes.find(n=>n.id==='test').ports[0];
  assert.equal(current.hardwareInterfaceId,original.nodes.find(n=>n.id==='test').ports[0].hardwareInterfaceId);
  assert.notEqual(current.physicalNetworkId,'local');
  // The released connectors can be wired again; then Delete on the trunk removes the whole bus.
  const a=await port('test').boundingBox(),b=await port('owner').boundingBox();
  await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:12});await page.mouse.up();
  const dialog=page.getByRole('dialog',{name:'Verbindung definieren'});await dialog.waitFor();
  response=saved();await dialog.getByRole('button',{name:'Beziehung übernehmen',exact:true}).click();await persisted(response);await dialog.waitFor({state:'hidden'});
  assert.equal(state.topology.scene.buses.length,1);
  await clickPath('.net-bus-trunk-hit');
  assert.equal(await page.getByRole('button',{name:'Auswahl löschen',exact:true}).isEnabled(),true);
  response=saved();await page.getByRole('button',{name:'Auswahl löschen',exact:true}).click();await persisted(response);
  assert.equal(state.topology.scene.buses.length,0);assert.equal(state.topology.edges.length,0);
  // An old bus selection must not override subsequent device selection; dialogs protect inputs.
  const node=page.locator('.net-node[data-node-id="wrong"]');await node.dblclick();
  const rename=page.getByRole('dialog',{name:'Gerät umbenennen'});await rename.waitFor();
  const input=rename.locator('input');await input.fill('Temporary');await input.press('Home');await input.press('Delete');assert.equal(await input.inputValue(),'emporary');
  assert.ok((await api('/workflow')).topology.nodes.some(n=>n.id==='wrong'));
  await rename.getByRole('button',{name:'Abbrechen',exact:true}).click();await node.click();
  response=saved();await page.keyboard.press('Delete');await persisted(response);assert.ok(!state.topology.nodes.some(n=>n.id==='wrong'));
  await page.reload();await ready();
  assert.equal(await page.locator('.net-bus-trunk-hit').count(),0);assert.equal(await port('existing').count(),0);
  assert.equal(state.topology.nodes.length,original.nodes.length-1);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'../backend/runtime/port-removal-verified.png'});
  await fs.writeFile('../backend/runtime/port-removal-browser-result.json',JSON.stringify({project,freePortDelete:true,connectedPortRightClick:true,branchDelete:true,trunkDelete:true,nodeDelete:true,inputProtected:true,globalDeleteWithToolbarFocus:true,saveFailureRetainsSelection:true,reloadStable:true,reconnect:true,hardwareChannelPreserved:true,pageErrors:errors},null,2));
  console.log('PASS',project);
}catch(e){failed=true;console.error(e);await page.screenshot({path:'../backend/runtime/port-removal-failure.png'});}
finally{const cdp=await browser.newBrowserCDPSession();await Promise.race([cdp.send('Browser.close').catch(()=>{}),new Promise(r=>setTimeout(r,2000))]);process.exit(failed?1:0);}
