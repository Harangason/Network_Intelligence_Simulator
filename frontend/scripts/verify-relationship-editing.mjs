import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-relationship-editing-ui-' + Date.now();
assert.ok(project.startsWith('network-project-relationship-editing-ui-'));
const headers = {'X-Project-ID':project, 'Content-Type':'application/json', Connection:'close'};
async function api(path, method='GET', body) {
  const r=await fetch('http://127.0.0.1:15050/api/engineering'+path,{method,headers,body:body?JSON.stringify(body):undefined});
  const data=await r.json();assert.ok(r.ok,JSON.stringify(data));return data;
}
const nodes=[];
let owner;
for (const key of ['owner', 'camera', 'radar', 'spare']) {
  const hw=await api('/hardware-nodes','POST',{name:{owner:'Fahrerassistenz',camera:'Kameraverarbeitung',radar:'Radarverarbeitung',spare:'Test'}[key],domain:'robotics',device_type:key==='owner'?'ECU':'SensorController',
    ...(owner?{identity:{system_owner_id:owner,system_owner_source:'network-editor'}}:{})});
  owner??=hw.id;
  nodes.push({id:key,name:hw.name,engineeringId:hw.id,systemOwnerId:owner,systemOwnerSource:'network-editor',kind:key==='owner'?'ecu':'sensor',x:10,y:10,
    ports:[{id:key+'-port',name:key+'_ETH',bus:'automotive_ethernet',side:key==='owner'?'bottom':'right',offset:.5,physicalNetworkId:key==='spare'?'single':'local'},
      ...(key==='owner'?[{id:'single-port',name:'Separate_ETH',bus:'automotive_ethernet',side:'bottom',offset:.8,physicalNetworkId:'single'}]:[])]});
}
let state=await api('/workflow/topology','PUT',{topology:{nodes,edges:[
  ...['radar','camera'].map(key=>({id:key,source:'owner',sourcePort:'owner-port',target:key,targetPort:key+'-port',bus:'automotive_ethernet',physicalNetworkId:'local'})),
  {id:'single',source:'owner',sourcePort:'single-port',target:'spare',targetPort:'spare-port',bus:'automotive_ethernet',physicalNetworkId:'single'}]}});
// Exercise aliases of the same canonical channel as well as shared edge endpoints.
let withAlias=structuredClone(state.topology);
const controller=withAlias.nodes.find(n=>n.id==='owner');
controller.ports.push({...controller.ports.find(p=>p.id==='owner-port'),id:'owner-alias',offset:.2});
withAlias.edges.find(e=>e.id==='radar').sourcePort='owner-alias';
state=await api('/workflow/topology','PUT',{topology:withAlias,expected_token:state.edit_tokens.topology});
const initial=structuredClone(state);
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1371,height:1272}});
const errors=[];let failed=false;page.on('pageerror',e=>errors.push(e.message));
const dialog=page.getByRole('dialog',{name:'Verbindung definieren',exact:true});
const choices=page.getByRole('dialog',{name:'Verbindung auswählen',exact:true});
const bus=id=>page.locator(`.net-physical-bus[data-physical-network-id="${id}"]`);
async function ready(){await page.locator('.net-editor').waitFor();await page.getByRole('button',{name:'Vollbild',exact:true}).click();await page.getByRole('button',{name:'Einpassen',exact:true}).click();}
async function pathPoint(locator) {
  return locator.evaluate(p=>{
    const matrix=p.getScreenCTM();
    for (const fraction of [.45,.65,.25,.8,.15,.9]) {
      const q=p.getPointAtLength(p.getTotalLength()*fraction).matrixTransform(matrix);
      const hit=document.elementFromPoint(q.x,q.y);
      if(hit && (hit===p || hit.parentElement===p.parentElement) && q.x>20 && q.y>20 && q.x<innerWidth-20 && q.y<innerHeight-20) return {x:q.x,y:q.y};
    }
    throw Error('No usable point on '+p.outerHTML);
  });
}
async function openPath(locator) {const q=await pathPoint(locator);await page.mouse.dblclick(q.x,q.y);}
async function selectCamera() {
  await choices.waitFor();
  const buttons=choices.locator('.net-connection-choices button');
  assert.equal(await buttons.count(),2);
  assert.match(await buttons.first().innerText(),/Kameraverarbeitung/);
  await buttons.first().click();await dialog.waitFor();
}
async function cancel(){await dialog.getByRole('button',{name:'Abbrechen',exact:true}).click();}
try {
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);await ready();
  await openPath(bus('local').locator('.net-bus-trunk-hit'));await selectCamera();
  await dialog.getByLabel('Name',{exact:true}).fill('Kameraverbindung');
  await dialog.getByLabel('Quell-Interface',{exact:true}).fill('ETH_Master');
  await dialog.getByLabel('Ziel-Interface',{exact:true}).fill('ETH_Kamera');
  await dialog.getByLabel('Beschreibung',{exact:true}).fill('Benannter Anschluss');
  const reject=route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:'Test: parallele Änderung'})});
  await page.route('**/api/engineering/workflow/topology',reject);
  await dialog.getByRole('button',{name:'Beziehung übernehmen',exact:true}).click();await dialog.locator('.net-relationship-error').waitFor();
  assert.deepEqual((await api('/workflow')).topology,initial.topology);
  assert.equal(await dialog.getByLabel('Ziel-Interface',{exact:true}).inputValue(),'ETH_Kamera');
  await page.unroute('**/api/engineering/workflow/topology',reject);
  const response=page.waitForResponse(r=>r.url().endsWith('/workflow/topology')&&r.request().method()==='PUT');
  await dialog.getByRole('button',{name:'Beziehung übernehmen',exact:true}).click();const saved=await response;
  assert.equal(saved.status(),200,await saved.text());await dialog.waitFor({state:'hidden'});
  state=await api('/workflow');
  assert.deepEqual(state.parameters.networks,initial.parameters.networks);
  for(const node of state.topology.nodes) for(const port of node.ports) {
    const before=initial.topology.nodes.flatMap(n=>n.ports).find(p=>p.id===port.id);
    for(const key of ['engineeringId','hardwareInterfaceId','physicalNetworkId']) assert.equal(port[key],before[key]);
    const channel=await api('/hardware-interfaces/'+port.hardwareInterfaceId);
    assert.equal(channel.name,port.name);
    const expected=port.id==='camera-port'?'ETH_Kamera':['owner-port','owner-alias'].includes(port.id)?'ETH_Master':before.name;
    assert.equal(port.name,expected);
  }
  assert.ok(state.topology.edges.filter(e=>e.physicalNetworkId==='local').every(e=>e.sourceInterfaceName==='ETH_Master'));
  // Every actual trunk and branch opens its own connection or a choice on shared endpoints.
  let checked=0;
  for(const id of ['local','single']) {
    await openPath(bus(id).locator('.net-bus-trunk-hit'));
    if(id==='local') await selectCamera();else await dialog.waitFor();await cancel();checked++;
    const branches=bus(id).locator('.net-bus-branch-hit');
    for(let i=0;i<await branches.count();i++) {
      await openPath(branches.nth(i));
      if(await choices.isVisible()) await choices.locator('.net-connection-choices button').first().click();
      await dialog.waitFor();await cancel();checked++;
    }
  }
  await bus('local').locator('.net-bus-label').dblclick();
  await page.getByRole('dialog',{name:'Bus umbenennen',exact:true}).getByRole('button',{name:'Abbrechen',exact:true}).click();
  const q=await pathPoint(bus('local').locator('.net-bus-trunk-hit'));await page.mouse.click(q.x,q.y);
  await page.getByRole('button',{name:'Verbindung bearbeiten',exact:true}).click();await selectCamera();await cancel();
  await page.reload();await ready();
  await openPath(bus('local').locator('.net-bus-trunk-hit'));await selectCamera();
  assert.equal(await dialog.getByLabel('Ziel-Interface',{exact:true}).inputValue(),'ETH_Kamera');
  assert.equal(await dialog.getByLabel('Quell-Interface',{exact:true}).inputValue(),'ETH_Master');
  assert.equal(await dialog.getByLabel('Name',{exact:true}).inputValue(),'Kameraverbindung');
  await page.screenshot({path:'../backend/runtime/relationship-editing-verified.png'});await cancel();
  assert.equal(errors.length,0,errors.join('\n'));
  await fs.writeFile('../backend/runtime/relationship-editing-browser-result.json',JSON.stringify({project,checkedPaths:checked,trunk:true,branches:true,label:true,toolbar:true,alphabeticalChoices:true,sourceAndTargetNamesPersisted:true,aliasesRenamed:true,relationshipNamePersisted:true,reload:true,failedSaveRetry:true,channelAndNetworkIdentityPreserved:true,pageErrors:errors},null,2));
  console.log('PASS',project,checked+' paths');
}catch(e){failed=true;console.error(e);await page.screenshot({path:'../backend/runtime/relationship-editing-failure.png'});}
finally{const cdp=await browser.newBrowserCDPSession();await Promise.race([cdp.send('Browser.close').catch(()=>{}),new Promise(r=>setTimeout(r,2000))]);process.exit(failed?1:0);}
