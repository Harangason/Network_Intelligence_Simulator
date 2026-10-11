import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from 'playwright';
import {withWireCrossings} from '../src/lib/network-crossings.ts';

const {project}=JSON.parse(await fs.readFile('../backend/runtime/crossing-test.json','utf8'));
assert.ok(project.startsWith('network-project-crossing-test-'));
const api=async(method='GET',body)=>{
  const r=await fetch('http://127.0.0.1:15050/api/engineering/workflow/network-view',{method,headers:{'X-Project-ID':project,'Content-Type':'application/json',Connection:'close'},body:body?JSON.stringify(body):undefined});
  assert.ok(r.ok,await r.clone().text());return r.json();
};
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1819,height:1272}});
page.setDefaultTimeout(25000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const save=()=>page.waitForResponse(r=>r.url().endsWith('/workflow/network-view')&&r.request().method()==='PUT');
try {
  const before=await api();
  const positions=Object.fromEntries(before.topology.nodes.map(n=>[n.id,{x:n.x,y:n.y,width:n.width,height:n.height}]));
  const automatic=await api('PUT',{positions,expected_token:before.edit_tokens.topology,reset_wires:true});
  const owner=automatic.topology.nodes.find(n=>n.name==='Bremsregelung');
  const buses=automatic.topology.scene.buses.filter(b=>b.frameId===owner.id).sort((a,b)=>a.branches[0].points.at(-1).x-b.branches[0].points.at(-1).x);
  const bus=buses[0], startX=bus.branches[0].points.at(-1).x;
  const endX=buses[3].branches[0].points.at(-1).x+12;
  const computed=withWireCrossings(automatic.topology.scene);
  assert.deepEqual(computed.wireBridges,automatic.topology.scene.wireBridges);
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);
  await page.getByRole('button',{name:'Linien automatisch',exact:true}).waitFor();
  const show=async()=>{await page.locator('.net-surface').evaluate((s,n)=>{s.scrollLeft=n.x-350;s.scrollTop=n.y-160;},owner);};
  await show();
  const selector=`.net-physical-bus[data-physical-network-id="${bus.id}"]`;
  const trunk=page.locator(`${selector} .net-bus-trunk-hit`);await trunk.waitFor({state:'attached'});
  const p=await trunk.evaluate(e=>{const p=e.getPointAtLength(e.getTotalLength()*.3).matrixTransform(e.getScreenCTM());return{x:p.x,y:p.y};});
  await page.mouse.move(p.x,p.y);await page.mouse.down();await page.mouse.move(p.x+endX-startX,p.y,{steps:12});
  const previewCount=await page.locator('.net-wire-bridge').count();
  assert.ok(previewCount>automatic.topology.scene.wireBridges.length);
  const response=save();await page.mouse.up();assert.equal((await response).status(),200);
  const crossed=await api();
  assert.deepEqual(withWireCrossings(crossed.topology.scene).wireBridges,crossed.topology.scene.wireBridges);
  assert.equal(await page.locator('.net-wire-bridge').count(),crossed.topology.scene.wireBridges.length);
  assert.deepEqual(crossed.topology.edges,before.topology.edges);
  assert.deepEqual(crossed.versions,before.versions);
  assert.ok(crossed.topology.scene.wireBridges.some(b=>b.busId===bus.id));
  await page.reload();await page.getByRole('button',{name:'Linien automatisch',exact:true}).waitFor();await show();
  assert.equal(await page.locator('.net-wire-bridge').count(),crossed.topology.scene.wireBridges.length);
  const path=page.locator(`[data-bridge-bus-id="${bus.id}"] .net-wire-bridge`).first();
  assert.ok((await path.getAttribute('d')).includes(' A '));
  assert.equal(await page.locator('.net-wires marker, .net-wires [marker-start], .net-wires [marker-end]').count(),0);
  await page.locator('.net-surface').screenshot({path:'../backend/runtime/network-crossings-browser.png'});
  assert.deepEqual(errors,[]);
  await fs.writeFile('../backend/runtime/network-crossings-browser-result.json',JSON.stringify({project,bus:bus.name,automaticBridges:automatic.topology.scene.wireBridges.length,afterManualCrossing:crossed.topology.scene.wireBridges.length,previewCount,sqlClientParity:true,reloadVerified:true,modelAndVersionsUnchanged:true,browserErrors:errors},null,2));
  console.log('Crossing bridges: preview, SVG arcs, SQL persistence, reload and client/server parity passed.');
}catch(e){console.error(e);process.exitCode=1;}
finally{await Promise.race([browser.close(),new Promise(r=>setTimeout(r,5000))]);}
process.exit(process.exitCode??0);
