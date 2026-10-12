import {chromium} from '../../../frontend/node_modules/playwright/index.mjs';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const project='20261009072206008-4bb505f1',job='33f124d0ad234c989dcbbd773e6393f9';
const base='http://127.0.0.1:13500',headers={'X-Project-ID':project};
const browser=await chromium.launch({headless:true});
try {
 const page=await browser.newPage();page.setDefaultTimeout(60000);
 const observations=[];
 await page.goto(`${base}/studio/simulation?project=${project}&job=${job}`);
 const before=(await(await page.request.get(`${base}/api/simulations`,{headers})).json()).jobs.map(j=>j.id).sort();
 const bar=page.locator('.simulation-command-bar');
 await bar.getByLabel('Seed',{exact:true}).waitFor();
 await bar.locator('.trace-format-trigger:enabled').waitFor();
 const controls=['Dauer (s)','Geschwindigkeit (x)','Seed'];
 const initial=await Promise.all(controls.map(name=>bar.getByLabel(name,{exact:true}).inputValue()));
 assert.deepEqual(initial,['2','1','42']);
 for(const width of [1506,1319,954,390]) {
  await page.setViewportSize({width,height:1244});
  const fields=await bar.locator(':scope > label').evaluateAll(labels=>labels.map(label=>{
   const caption=label.querySelector('span').getBoundingClientRect(),input=label.querySelector('input,select').getBoundingClientRect();
   return {name:label.querySelector('span').textContent,caption:{left:caption.left,right:caption.right,top:caption.top,bottom:caption.bottom},input:{left:input.left,right:input.right,top:input.top,width:input.width,height:input.height}};
  }));
  const numeric=fields.slice(1);
  assert.equal(numeric.length,3);
  assert(numeric.every(f=>f.caption.bottom<=f.input.top&&f.input.width>=140&&f.input.height>=36));
  if(width>1180){
   assert(Math.max(...numeric.map(f=>f.input.width))-Math.min(...numeric.map(f=>f.input.width))<1);
   assert(Math.max(...numeric.map(f=>f.input.top))-Math.min(...numeric.map(f=>f.input.top))<1);
  }
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  assert.equal(overflow,false);
  for(const name of ['Speichern unter','Start','Weiter','Stop','Reset'])assert(await bar.getByRole('button',{name,exact:true}).isVisible());
  assert.equal(await page.locator('details.fault-editor').getAttribute('open'),null);
  observations.push({viewport:width,fields,document_overflow:overflow});
  if(width===1319||width===390)await bar.screenshot({path:new URL(`production-fields-${width}.jpg`,import.meta.url).pathname.replace(/^\/(\w:)/,'$1'),type:'jpeg',quality:85});
 }
 const after=(await(await page.request.get(`${base}/api/simulations`,{headers})).json()).jobs.map(j=>j.id).sort();assert.deepEqual(after,before);
 await writeFile(new URL('production-functional.json',import.meta.url),JSON.stringify({status:'PASSED',captured_at:new Date().toISOString(),project,job,scope:'Read-only actual deployed field presentation, no simulation start or model changes',unchanged_values:initial,unchanged_job_ids:after,observations},null,2));
 console.log('PRODUCTION_FIELDS_VERIFIED');
}finally{await browser.close();}
