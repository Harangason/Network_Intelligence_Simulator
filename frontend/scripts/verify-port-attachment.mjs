import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-port-attachment-ui-' + Date.now();
assert.ok(project.startsWith('network-project-port-attachment-ui-'));
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
    ports:[{id:key+'-port',name:key==='wrong'?'LIN':'CAN FD',bus:key==='wrong'?'lin':'can_fd',side:key==='owner'?'bottom':'right',offset:.5,physicalNetworkId:['owner','existing'].includes(key)?'local':key+'-spare'}]});
}
let state=await api('/workflow/topology','PUT',{topology:{nodes,edges:[{id:'initial',source:'existing',sourcePort:'existing-port',target:'owner',targetPort:'owner-port',bus:'can_fd',physicalNetworkId:'local'}]}});
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1819,height:1272}});
console.log('Project prepared',project);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const port=id=>page.locator(`[data-port-id="${id}-port"]`);
const dialog=page.getByRole('dialog',{name:'Verbindung definieren'});
async function point(locator) {const r=await locator.boundingBox();assert.ok(r);return {x:r.x+r.width/2,y:r.y+r.height/2};}
async function busPoint(branch=false) {
  return page.locator('[data-physical-network-id="local"]').evaluate((g,branch)=>{
    const p=g.querySelector(branch?'.net-bus-branch-hit':'.net-bus-trunk-hit');
    const q=p.getPointAtLength(p.getTotalLength()*.65),matrix=p.getScreenCTM();
    const v=new DOMPoint(q.x,q.y).matrixTransform(matrix);return{x:v.x,y:v.y};
  },branch);
}
async function drag(from,to){await page.mouse.move(from.x,from.y);await page.mouse.down();await page.mouse.move(to.x,to.y,{steps:15});await page.mouse.up();}
async function ready(){await page.locator('.net-editor').waitFor();await page.getByRole('button',{name:'Vollbild',exact:true}).click();await page.getByRole('button',{name:'Einpassen',exact:true}).click();}
async function save(id) {
  await dialog.waitFor();
  const old=state.topology.nodes.find(n=>n.id===id).ports[0];
  const physical=await api('/hardware-interfaces/'+old.hardwareInterfaceId);
  const response=page.waitForResponse(r=>r.url().endsWith('/workflow/topology')&&r.request().method()==='PUT');
  await dialog.getByRole('button',{name:'Beziehung übernehmen',exact:true}).click();
  const r=await response;assert.equal(r.status(),200,await r.text());await dialog.waitFor({state:'hidden'});
  state=await api('/workflow');
  const current=state.topology.nodes.find(n=>n.id===id).ports[0];
  assert.equal(current.hardwareInterfaceId,old.hardwareInterfaceId);
  assert.equal(current.physicalNetworkId,'local');
  const actual=await api('/hardware-interfaces/'+old.hardwareInterfaceId);
  assert.equal(actual.network_ref,'local');assert.equal(actual.channel_index,physical.channel_index);assert.equal(actual.physical_port_ref,physical.physical_port_ref);
}
try{
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);await ready();
  // Wrong bus and cancelled connection cannot mutate the project.
  await drag(await point(port('wrong')),await busPoint());
  await page.getByRole('alert').filter({hasText:'Bustypen'}).waitFor();
  assert.equal((await api('/workflow')).topology.edges.length,1);
  await drag(await point(port('test')),await busPoint());await dialog.waitFor();
  await dialog.getByRole('button',{name:'Abbrechen',exact:true}).click();
  assert.equal((await api('/workflow')).topology.edges.length,1);
  // Exercise failed persistence and retry with the same draft.
  await drag(await point(port('test')),await busPoint());await dialog.waitFor();
  const reject=route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:'Test: gespeicherter Stand wurde geändert'})});
  await page.route('**/api/engineering/workflow/topology',reject);
  await dialog.getByRole('button',{name:'Beziehung übernehmen',exact:true}).click();
  await dialog.locator('.net-relationship-error').waitFor();
  assert.equal((await api('/workflow')).topology.edges.length,1);
  await page.unroute('**/api/engineering/workflow/topology',reject);
  await save('test');
  assert.equal(state.topology.edges.length,2);
  const layout=structuredClone(state.topology.scene.manualBusRoutes??{});
  await drag(await busPoint(),await point(port('reverse')));await save('reverse');
  assert.deepEqual(state.topology.scene.manualBusRoutes??{},layout,'Connecting from a bus must not save the provisional line move');
  await drag(await point(port('owner')),await point(port('connected')));await save('connected');
  await drag(await point(port('branch')),await busPoint(true));await save('branch');
  await drag(await point(port('test')),await point(port('owner')));
  await page.getByRole('alert').filter({hasText:'bereits'}).waitFor();
  assert.equal((await api('/workflow')).topology.edges.length,5);
  // Preserve line movement and Shift+port movement as layout-only edits.
  const edges=structuredClone(state.topology.edges);
  let position=await busPoint();
  let moved=page.waitForResponse(r=>r.url().endsWith('/workflow/network-view')&&r.request().method()==='PUT');
  await drag(position,{x:position.x+35,y:position.y});
  assert.equal((await moved).status(),200);
  state=await api('/workflow');
  assert.deepEqual(state.topology.edges,edges);
  assert.ok(Number.isFinite(state.topology.scene.manualBusRoutes.local.trunkX));
  position=await point(port('owner'));
  moved=page.waitForResponse(r=>r.url().endsWith('/workflow/network-view')&&r.request().method()==='PUT');
  await page.keyboard.down('Shift');await drag(position,{x:position.x+25,y:position.y});await page.keyboard.up('Shift');
  assert.equal((await moved).status(),200);
  assert.deepEqual((await api('/workflow')).topology.edges,edges);
  await page.screenshot({path:'../backend/runtime/port-attachment-verified.png'});
  await page.reload();await ready();
  state=await api('/workflow');
  assert.equal(state.topology.scene.buses.find(b=>b.id==='local').participantCount,6);
  assert.equal(errors.length,0,errors.join('\n'));
  await fs.writeFile('../backend/runtime/port-attachment-browser-result.json',JSON.stringify({project,edges:5,participants:6,portToBus:true,busToPort:true,connectedPortToFreePort:true,branchHit:true,wrongBusRejected:true,duplicateRejected:true,cancelPreservedState:true,failedSaveRetry:true,channelIdentityPreserved:true,lineMovementPreserved:true,shiftPortMovementPreserved:true,reload:true,pageErrors:errors},null,2));
  console.log('PASS',project);
}catch(e){console.error(e);errors.push(String(e));await page.screenshot({path:'../backend/runtime/port-attachment-failure.png'});throw e;}
finally{const cdp=await browser.newBrowserCDPSession();await Promise.race([cdp.send('Browser.close').catch(()=>{}),new Promise(r=>setTimeout(r,2000))]);process.exit(errors.length?1:0);}
