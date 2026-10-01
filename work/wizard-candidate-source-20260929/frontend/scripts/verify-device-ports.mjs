import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from 'playwright';
const project='network-project-device-ports-ui-'+Date.now();
const headers={'X-Project-ID':project,'Content-Type':'application/json',Connection:'close'};
async function api(path,method='GET',body){const r=await fetch('http://127.0.0.1:15050/api/engineering'+path,{method,headers,body:body?JSON.stringify(body):undefined});const d=await r.json();assert.ok(r.ok,JSON.stringify(d));return d;}
const technologies=['can','can_fd','can_xl','lin','automotive_ethernet','flexray'];
const labels={can:'CAN',can_fd:'CAN FD',can_xl:'CAN-XL',lin:'LIN',automotive_ethernet:'Ethernet',flexray:'FlexRay'};
const nodes=[];
for(const id of ['owner','empty']){
  const hw=await api('/hardware-nodes','POST',{name:id==='owner'?'Fahrerassistenz':'Ohne Ports',domain:'robotics',device_type:'ECU'});
  nodes.push({id,name:hw.name,engineeringId:hw.id,kind:'ecu',x:id==='owner'?50:500,y:50,ports:id==='empty'?[]:technologies.map((bus,i)=>({id:'port-'+i,name:['Zentrale','Alpha','CAN Kanal 10','CAN Kanal 2','Ethernet_Kamera_mit_einem_sehr_langen_vollstaendigen_Anschlussnamen','FlexRay Steuerung'][i],bus,physicalNetworkId:'network-'+i,side:'bottom',offset:(i+1)/7}))});
}
let state=await api('/workflow/topology','PUT',{topology:{nodes,edges:[]}});
let alias=structuredClone(state.topology);alias.nodes.find(n=>n.id==='owner').ports.push({...alias.nodes.find(n=>n.id==='owner').ports[0],id:'alias',side:'top'});
state=await api('/workflow/topology','PUT',{topology:alias,expected_token:state.edit_tokens.topology});
const expected=[...new Map(state.topology.nodes.find(n=>n.id==='owner').ports.map(p=>[p.hardwareInterfaceId,p])).values()].sort((a,b)=>a.name.localeCompare(b.name,'de',{numeric:true}));
const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1371,height:1272}});let failed=false;const errors=[];page.on('pageerror',e=>errors.push(e.message));
const dialog=page.getByRole('dialog',{name:'Gerät und Ports',exact:true});
try{
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);
  await page.locator('.net-editor').waitFor();await page.getByRole('button',{name:'Vollbild',exact:true}).click();await page.getByRole('button',{name:'Einpassen',exact:true}).click();
  await page.locator('.net-node[data-node-id="owner"]').dblclick();await dialog.waitFor();
  const rows=dialog.locator('tbody tr');assert.equal(await rows.count(),6);
  for(let i=0;i<expected.length;i++){assert.equal(await rows.nth(i).locator('td').nth(0).innerText(),expected[i].name);assert.equal(await rows.nth(i).locator('td').nth(1).innerText(),labels[expected[i].bus]);}
  assert.equal(await dialog.getByRole('columnheader',{name:'Technik',exact:true}).count(),1);
  await page.screenshot({path:'../backend/runtime/device-ports-desktop.png'});
  await page.setViewportSize({width:720,height:640});
  const rect=await dialog.boundingBox();assert.ok(rect.x>=0&&rect.y>=0&&rect.x+rect.width<=720&&rect.y+rect.height<=640);
  const save=await dialog.getByRole('button',{name:'Speichern',exact:true}).boundingBox();assert.ok(save.y+save.height<640);
  const dimensions=await dialog.evaluate(e=>({width:e.clientWidth,scrollWidth:e.scrollWidth}));assert.ok(dimensions.scrollWidth<=dimensions.width);
  await dialog.getByLabel('Name',{exact:true}).fill('Unbestätigte Änderung');
  await page.screenshot({path:'../backend/runtime/device-ports-small.png'});
  await dialog.getByRole('button',{name:'Abbrechen',exact:true}).click();
  assert.deepEqual((await api('/workflow')).topology,state.topology);
  await page.setViewportSize({width:1371,height:1272});await page.getByRole('button',{name:'Einpassen',exact:true}).click();
  await page.locator('.net-node[data-node-id="empty"]').dblclick();await dialog.waitFor();
  await dialog.getByText('Für dieses Gerät sind noch keine Ports angelegt.',{exact:true}).waitFor();assert.equal(await dialog.locator('table').count(),0);
  await dialog.getByRole('button',{name:'Abbrechen',exact:true}).click();
  assert.equal(errors.length,0,errors.join('\n'));
  await fs.writeFile('../backend/runtime/device-ports-browser-result.json',JSON.stringify({project,ports:6,technologies:labels,alphabetical:true,physicalAliasesShownOnce:true,fullNames:true,desktop:true,smallViewport:true,emptyState:true,cancelPreserved:true,pageErrors:errors},null,2));
  console.log('PASS',project);
}catch(e){failed=true;console.error(e);await page.screenshot({path:'../backend/runtime/device-ports-failure.png'});}
finally{const cdp=await browser.newBrowserCDPSession();await Promise.race([cdp.send('Browser.close').catch(()=>{}),new Promise(r=>setTimeout(r,2000))]);process.exit(failed?1:0);}
