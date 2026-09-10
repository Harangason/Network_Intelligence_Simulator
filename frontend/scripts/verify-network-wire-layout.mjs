import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from 'playwright';

const {project} = JSON.parse(await fs.readFile('../backend/runtime/wire-layout-test.json', 'utf8'));
assert.ok(project.startsWith('network-project-wire-layout-test-'));
const view = async () => {
  const r=await fetch('http://127.0.0.1:15050/api/engineering/workflow/network-view',{headers:{'X-Project-ID':project,Connection:'close'}});
  assert.ok(r.ok);return r.json();
};
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1819,height:1272}});
page.setDefaultTimeout(25000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const saving=()=>page.waitForResponse(r=>r.url().endsWith('/workflow/network-view')&&r.request().method()==='PUT');
const geometry=t=>t.nodes.map(({id,x,y,width,height})=>({id,x,y,width,height}));
try {
  const before=await view();
  const owner=before.topology.nodes.find(n=>n.name==='Bremsregelung');
  const bus=before.topology.scene.buses.find(b=>b.frameId===owner.id&&b.name.includes('Ort offen'));
  assert.ok(bus);
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);
  const auto=page.getByRole('button',{name:'Linien automatisch',exact:true});
  await auto.waitFor();
  let response=saving();await auto.click();assert.equal((await response).status(),200);
  let current=await view();
  assert.deepEqual(geometry(current.topology),geometry(before.topology));
  assert.deepEqual(current.topology.edges,before.topology.edges);
  assert.deepEqual(current.versions,before.versions);
  const selectBus=`.net-physical-bus[data-physical-network-id="${bus.id}"]`;
  async function show(target=owner,zoom=1) {
    await page.locator('.net-surface').evaluate((surface,{n,zoom})=>{surface.scrollLeft=(n.x-380)*zoom;surface.scrollTop=(n.y-180)*zoom;},{n:target,zoom});
    await page.locator(selectBus).waitFor({state:'attached'});
  }
  async function drag(selector,dx,dy,cancel=false,ratio=.3) {
    const path=page.locator(selector);await path.waitFor({state:'attached'});
    const p=await path.evaluate((e,r)=>{const p=e.getPointAtLength(e.getTotalLength()*r).matrixTransform(e.getScreenCTM());return{x:p.x,y:p.y};},ratio);
    await page.mouse.move(p.x,p.y);await page.mouse.down();await page.mouse.move(p.x+dx,p.y+dy,{steps:12});
    if(cancel)await page.keyboard.press('Escape');await page.mouse.up();
  }
  const trunk=`${selectBus} .net-bus-trunk-hit`;
  await show();
  const initialX=current.topology.scene.buses.find(b=>b.id===bus.id).branches[0].points.at(-1).x;
  response=saving();await drag(trunk,40,0);assert.equal((await response).status(),200);
  current=await view();
  assert.ok(Math.abs(current.topology.scene.manualBusRoutes[bus.id].trunkX-initialX-40)<1);
  const saved=current;
  await page.reload();await auto.waitFor();await show();
  const renderedX=()=>page.locator(`${selectBus} .net-bus-trunk`).evaluate(p=>p.getPointAtLength(0).x);
  assert.ok(Math.abs(await renderedX()-current.topology.scene.manualBusRoutes[bus.id].trunkX)<.02);
  console.log('Trunk drag, SQL persistence and reload passed.');
  for(let i=0;i<5;i++)await page.getByRole('button',{name:'Vergrößern',exact:true}).click();
  await show(owner,1.5);
  response=saving();await drag(trunk,45,0);assert.equal((await response).status(),200);
  current=await view();
  assert.ok(Math.abs(current.topology.scene.manualBusRoutes[bus.id].trunkX-saved.topology.scene.manualBusRoutes[bus.id].trunkX-30)<1);
  await drag(trunk,-35,0,true);assert.deepEqual((await view()).topology,current.topology);
  console.log('150% zoom and Escape rollback passed.');
  await page.getByRole('button',{name:'Zoom auf 100 Prozent zurücksetzen',exact:true}).click();
  const branch=current.topology.scene.buses.find(b=>b.id===bus.id).branches.find(b=>b.nodeId!==owner.id);
  const child=current.topology.nodes.find(n=>n.id===branch.nodeId);await show(child);
  const branchSelector=`${selectBus} [data-branch-node-id="${child.id}"] .net-bus-branch-hit`;
  response=saving();await drag(branchSelector,0,34,false,.5);assert.equal((await response).status(),200);
  current=await view();
  const changed=current.topology.scene.buses.find(b=>b.id===bus.id).branches.find(b=>b.nodeId===child.id);
  assert.deepEqual(changed.points[0],branch.points[0]);
  assert.ok(Math.abs(changed.points.at(-1).y-branch.points.at(-1).y-34)<1);
  assert.equal(changed.points.length,4);
  await page.reload();await auto.waitFor();await show();
  assert.deepEqual((await view()).topology.scene.manualBusRoutes,current.topology.scene.manualBusRoutes);
  console.log('Branch dogleg and fixed endpoint passed.');
  const reject=route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:'Test: Projektstand veraltet'})});
  await page.route('**/workflow/network-view',reject);await drag(trunk,30,0);
  await page.getByRole('alert').filter({hasText:'Projektstand veraltet'}).waitFor();
  assert.deepEqual((await view()).topology,current.topology);
  assert.ok(Math.abs(await renderedX()-current.topology.scene.manualBusRoutes[bus.id].trunkX)<.02);
  await page.unroute('**/workflow/network-view',reject);
  response=saving();await auto.click();assert.equal((await response).status(),200);
  current=await view();
  assert.deepEqual(current.topology.scene.manualBusRoutes,{});
  assert.deepEqual(geometry(current.topology),geometry(before.topology));
  assert.deepEqual(current.topology.edges,before.topology.edges);
  assert.deepEqual(current.versions,before.versions);
  assert.equal(await page.locator('.net-wires marker, .net-wires [marker-start], .net-wires [marker-end]').count(),0);
  await show();await page.locator('.net-surface').screenshot({path:'../backend/runtime/wire-layout-browser.png'});
  assert.deepEqual(errors,[]);
  await fs.writeFile('../backend/runtime/wire-layout-browser-result.json',JSON.stringify({project,tests:['automatic routing preserves devices and model','trunk drag','SQL save and reload','150% zoom','Escape rollback','branch dogleg','409 rollback','automatic reset','no arrowheads','no browser exceptions'],bus:bus.name,versionsUnchanged:true},null,2));
  console.log('All wire layout browser checks passed.');
}catch(e){console.error(e);process.exitCode=1;}
finally{await Promise.race([browser.close(),new Promise(r=>setTimeout(r,5000))]);}
process.exit(process.exitCode??0);
