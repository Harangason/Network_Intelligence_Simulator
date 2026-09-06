import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const base=process.env.SIMULATOR_TEST_URL;
const project=process.env.SIMULATOR_TEST_PROJECT;
const output=process.env.SIMULATOR_TEST_OUTPUT || fileURLToPath(new URL('../../backend/test-output',import.meta.url));
if(!base || !project) throw new Error('Set SIMULATOR_TEST_URL and SIMULATOR_TEST_PROJECT for a prepared, isolated test project.');
await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(`${base}/studio/simulation?project=${project}`);
 await page.getByRole('button',{name:'Start',exact:true}).waitFor();
 await page.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Start')?.disabled,{},{timeout:30000});
 const response=page.waitForResponse(r=>r.url().endsWith('/api/simulations')&&r.request().method()==='POST',{timeout:30000});
 await page.getByRole('button',{name:'Start',exact:true}).click();
 const started=await response;const job=await started.json();console.log('START',started.status(),JSON.stringify(job));
 if(started.status()!==202)throw Error('Start failed');
 let result;
 for(let i=0;i<60;i++){
  result=await page.evaluate(async ({id,project})=>await(await fetch('/api/simulations/'+id,{headers:{'X-Project-ID':project}})).json(),{id:job.id,project});
  if(['completed','failed','canceled'].includes(result.status))break;
  await new Promise(r=>setTimeout(r,500));
 }
 if(!(result?.result?.trace?.events > 0)) throw new Error('Simulation produced no frames');
 if(result.status!=='completed')throw Error('Run incomplete: '+result.status);
 await page.locator('.signal-lane').first().waitFor({timeout:15000});
 await page.screenshot({path:`${output}/audit-simulation.png`,fullPage:true});
 await page.goto(`${base}/studio/results?project=${project}`);
 await page.getByRole('button',{name:'Projektlink',exact:true}).waitFor();
 await page.locator('.result-run-list button').filter({hasText:job.id.slice(0,10)}).waitFor();
 await page.locator('.runtime-analysis').waitFor();
 console.log('Verified simulation, signal display and results:',project,job.id);
 await page.screenshot({path:`${output}/audit-results.png`,fullPage:true});
 await page.goto(`${base}/studio/intelligence?project=${project}`);
 await page.getByRole('button',{name:'Neu bewerten',exact:true}).waitFor({timeout:30000});
 const assessed=page.waitForResponse(r=>r.url().includes('/intelligence/assess')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Neu bewerten',exact:true}).click();
 if((await assessed).status()!==200)throw new Error('Intelligence assessment failed');
 const workflow=await page.evaluate(async project=>await(await fetch('/api/engineering/workflow',{headers:{'X-Project-ID':project}})).json(),project);
 if(!['COMPLETE','APPROVED','WARNING'].includes(workflow.statuses.data_science_intelligence))throw new Error('Assessment did not complete the workflow');
 await page.screenshot({path:`${output}/audit-intelligence.png`,fullPage:true});
 await fs.writeFile(`${output}/audit-simulation-report.json`,JSON.stringify({project,job:result,workflowStatuses:workflow.statuses,pageErrors:errors},null,2));
 if(errors.length)throw Error(errors.join('\n'));
}finally{await browser.close()}

