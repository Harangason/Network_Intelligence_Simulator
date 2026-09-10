import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const inherited = process.env.VERIFY_INHERITED_NAMES === '1';
const project = 'network-project-bus-naming-ui-' + Date.now();
assert.ok(project.startsWith('network-project-bus-naming-ui-'));
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
    ports:[{id:key+'-port',name:inherited && key!=='spare'?'local':key+'_ETH',bus:'automotive_ethernet',side:key==='owner'?'bottom':'right',offset:.5,physicalNetworkId:key==='spare'?'single':'local'},
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
const page=await browser.newPage({viewport:{width:1371,height:1272}});let failed=false;const errors=[];page.on('pageerror',e=>errors.push(e.message));
const dialog=page.getByRole('dialog',{name:'Bus umbenennen',exact:true});
const bus=page.locator('.net-physical-bus[data-physical-network-id="local"]');
async function ready(){await page.locator('.net-editor').waitFor();await page.getByRole('button',{name:'Vollbild',exact:true}).click();await page.getByRole('button',{name:'Einpassen',exact:true}).click();}
async function selectBus(){const p=await bus.locator('.net-bus-trunk-hit').evaluate(p=>{const q=p.getPointAtLength(p.getTotalLength()*.65).matrixTransform(p.getScreenCTM());return {x:q.x,y:q.y};});await page.mouse.click(p.x,p.y);}
async function save(name){await dialog.getByLabel('Busname',{exact:true}).fill(name);const pending=page.waitForResponse(r=>r.url().endsWith('/workflow/bus-name')&&r.request().method()==='PUT');await dialog.getByLabel('Busname',{exact:true}).press('Enter');const r=await pending;assert.equal(r.status(),200,await r.text());await dialog.waitFor({state:'hidden'});}
try{
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);await ready();
  await selectBus();await page.getByRole('button',{name:'Bus umbenennen',exact:true}).click();await dialog.waitFor();
  assert.equal(await dialog.getByLabel('Busname',{exact:true}).inputValue(),initial.topology.scene.buses.find(b=>b.id==='local').name);
  await dialog.getByLabel('Busname',{exact:true}).fill(' ');assert.ok(await dialog.getByRole('button',{name:'Speichern',exact:true}).isDisabled());
  await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
  assert.deepEqual((await api('/workflow')).topology,initial.topology);
  await bus.locator('.net-bus-label').dblclick();await dialog.waitFor();await dialog.getByLabel('Busname',{exact:true}).fill('Fahrerassistenz Kamera ETH');
  const reject=route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:'Test: parallele Änderung'})});
  await page.route('**/api/engineering/workflow/bus-name',reject);
  await dialog.getByRole('button',{name:'Speichern',exact:true}).click();await dialog.getByRole('alert').waitFor();
  assert.deepEqual((await api('/workflow')).topology,initial.topology);
  assert.equal(await dialog.getByLabel('Busname',{exact:true}).inputValue(),'Fahrerassistenz Kamera ETH');
  await page.unroute('**/api/engineering/workflow/bus-name',reject);
  await save('Fahrerassistenz Kamera ETH');
  assert.equal(await bus.locator('.net-bus-label').textContent(),'Fahrerassistenz Kamera ETH');
  state=await api('/workflow');
  assert.deepEqual(state.versions,initial.versions);
  for(const node of state.topology.nodes) for(const port of node.ports){const old=initial.topology.nodes.flatMap(n=>n.ports).find(p=>p.id===port.id);for(const key of ['hardwareInterfaceId','physicalNetworkId','engineeringId','side','offset'])assert.equal(port[key],old[key]);assert.equal(port.name,inherited&&port.physicalNetworkId==='local'?'Fahrerassistenz Kamera ETH':old.name);if(inherited&&port.physicalNetworkId==='local'){assert.equal(port.nameSource,'network');assert.equal((await api('/hardware-interfaces/'+port.hardwareInterfaceId)).name,port.name);}}
  for(const b of state.topology.scene.buses){const old=initial.topology.scene.buses.find(item=>item.id===b.id);for(const key of ['path','branches','bounds','label'])assert.deepEqual(b[key],old[key]);}
  await page.reload();await ready();assert.equal(await bus.locator('.net-bus-label').textContent(),'Fahrerassistenz Kamera ETH');
  const pending=page.waitForResponse(r=>r.url().endsWith('/workflow/network-view')&&r.request().method()==='PUT');await page.getByRole('button',{name:'Linien automatisch',exact:true}).click();assert.equal((await pending).status(),200);
  assert.equal(await bus.locator('.net-bus-label').textContent(),'Fahrerassistenz Kamera ETH');
  await selectBus();await page.getByRole('button',{name:'Verbindung bearbeiten',exact:true}).click();
  const choice=page.getByRole('dialog',{name:'Verbindung auswählen',exact:true});await choice.locator('.net-connection-choices button').first().click();
  const relation=page.getByRole('dialog',{name:'Verbindung definieren',exact:true});await relation.getByRole('button',{name:'Bus umbenennen',exact:true}).click();
  await save('ETH Kamera');await relation.locator('.net-transfer-entry strong').filter({hasText:'ETH Kamera'}).waitFor();
  if(inherited){
    assert.equal(await relation.getByLabel('Quell-Interface',{exact:true}).inputValue(),'ETH Kamera');
    assert.equal(await relation.getByLabel('Ziel-Interface',{exact:true}).inputValue(),'ETH Kamera');
    // Saving the still-open relationship must not write back its pre-rename draft.
    const pending=page.waitForResponse(r=>r.url().endsWith('/workflow/topology')&&r.request().method()==='PUT');
    await relation.getByRole('button',{name:'Beziehung übernehmen',exact:true}).click();assert.equal((await pending).status(),200);
    await relation.waitFor({state:'hidden'});
    state=await api('/workflow');
    for(const node of state.topology.nodes)for(const port of node.ports)if(port.physicalNetworkId==='local'){assert.equal(port.name,'ETH Kamera');assert.equal(port.nameSource,'network');}
    for(const edge of state.topology.edges)if(edge.physicalNetworkId==='local'){assert.equal(edge.sourceInterfaceName,'ETH Kamera');assert.equal(edge.targetInterfaceName,'ETH Kamera');}
    await page.reload();await ready();assert.equal(await bus.locator('.net-bus-label').textContent(),'ETH Kamera');
  } else await relation.getByRole('button',{name:'Abbrechen',exact:true}).click();
  await bus.locator('.net-bus-label').dblclick();await dialog.waitFor();
  assert.equal(await dialog.getByLabel('Busname',{exact:true}).inputValue(),'ETH Kamera');
  await page.screenshot({path:'../backend/runtime/bus-name-dialog-verified.png'});
  await dialog.getByRole('button',{name:'Abbrechen',exact:true}).click();
  await page.screenshot({path:'../backend/runtime/bus-name-label-verified.png'});
  assert.equal(errors.length,0,errors.join('\n'));
  await fs.writeFile(`../backend/runtime/bus-name${inherited?'-inherited':''}-browser-result.json`,JSON.stringify({project,inheritedNames:inherited,openDialogRefresh:inherited,labelDoubleClick:true,toolbar:true,relationshipDialog:true,cancel:true,emptyNameRejected:true,failedSaveRetry:true,enterSaves:true,reload:true,automaticLinesPreserveFullName:true,idsAndPortsPreserved:true,geometryPreserved:true,versionsPreserved:true,pageErrors:errors},null,2));
  console.log('PASS',project);
}catch(e){failed=true;console.error(e);await page.screenshot({path:'../backend/runtime/bus-name-failure.png'});}
finally{const cdp=await browser.newBrowserCDPSession();await Promise.race([cdp.send('Browser.close').catch(()=>{}),new Promise(r=>setTimeout(r,2000))]);process.exit(failed?1:0);}
