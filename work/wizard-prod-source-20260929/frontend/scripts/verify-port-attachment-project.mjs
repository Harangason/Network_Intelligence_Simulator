// Read-only verification of the exact reported card and bus in the user's large project.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';
const project='network-project-20260910042736034-d11591d0';
const get=async()=>{const r=await fetch('http://127.0.0.1:15050/api/engineering/workflow',{headers:{'X-Project-ID':project}});assert.ok(r.ok);return r.json();};
const before=await get(),topology=before.topology;
const sensor=topology.nodes.find(n=>n.name==='Test'),owner=topology.nodes.find(n=>n.name==='Fahrerassistenz');
assert.ok(sensor&&owner);
const targetBus=topology.scene.buses.find(b=>b.local&&b.frameId===owner.id&&b.technology==='can_fd');assert.ok(targetBus);
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1819,height:1272}});
let failed=false;const errors=[];page.on('pageerror',e=>errors.push(e.message));
// No write is permitted to reach the project, even if a UI regression attempted one.
await page.route('**/api/engineering/**',r=>['GET','HEAD','OPTIONS'].includes(r.request().method())?r.continue():r.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:'Read-only verification'})}));
try {
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);
  await page.locator('.net-editor.large-topology').waitFor();
  await page.getByRole('button',{name:'Vollbild',exact:true}).click();
  await page.locator('.net-surface').evaluate((el,p)=>{const canvas=el.querySelector('.net-canvas');const zoom=new DOMMatrix(getComputedStyle(canvas).transform).a;el.scrollLeft=p.x*zoom-300;el.scrollTop=p.y*zoom-180;},owner);
  const port=page.locator(`[data-port-id="${sensor.ports[0].id}"]`);await port.waitFor({state:'visible'});
  const rect=await port.boundingBox();
  const target=await page.locator(`[data-physical-network-id="${targetBus.id}"] .net-bus-trunk-hit`).evaluate(p=>{
    const q=p.getPointAtLength(p.getTotalLength()*.65),v=new DOMPoint(q.x,q.y).matrixTransform(p.getScreenCTM());return{x:v.x,y:v.y};});
  await page.mouse.move(rect.x+rect.width/2,rect.y+rect.height/2);await page.mouse.down();await page.mouse.move(target.x,target.y,{steps:15});
  await page.mouse.up();
  const connected=topology.edges.some(e=>e.sourcePort===sensor.ports[0].id||e.targetPort===sensor.ports[0].id);
  if (connected) {
    await page.getByRole('alert').filter({hasText:'bereits'}).waitFor();
  } else {
    const dialog=page.getByRole('dialog',{name:'Verbindung definieren'});await dialog.waitFor();
    assert.ok((await dialog.innerText()).includes('Fahrerassistenz'));
    await dialog.getByRole('button',{name:'Abbrechen',exact:true}).click();
  }
  await page.screenshot({path:'../backend/runtime/port-attachment-project-preview.png'});
  const after=await get();assert.deepEqual(after.topology,before.topology);
  assert.deepEqual(errors,[]);
  await fs.writeFile('../backend/runtime/port-attachment-project-result.json',JSON.stringify({project,nodes:topology.nodes.length,bus:targetBus.name,sensor:sensor.name,alreadyConnected:connected,targetRecognized:true,modelUnchanged:true,pageErrors:errors},null,2));
  console.log('PASS exact project: Test → Fahrerassistenz CAN FD; model unchanged');
} catch(e){failed=true;console.error(e);await page.screenshot({path:'../backend/runtime/port-attachment-project-failure.png'});}
finally{const cdp=await browser.newBrowserCDPSession();await Promise.race([cdp.send('Browser.close').catch(()=>{}),new Promise(r=>setTimeout(r,2000))]);process.exit(failed?1:0);}
