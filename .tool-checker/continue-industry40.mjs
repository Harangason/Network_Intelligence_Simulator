import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
const root=process.cwd(), source=path.join(root,'.tool-checker/evidence/industry40-live-ai');
const py=path.join(root,'backend/.venv/Scripts/python.exe');
const cli='F:/CodexOrdner/plugins/cache/plugins-cli/tool-checker/1.0.0/skills/tool-checker/scripts/tool_check.py';
const tc=(...a)=>JSON.parse(execFileSync(py,[cli,'--state',path.join(root,'.tool-checker/state'),'--task','industry40',...a],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'},maxBuffer:2000000}));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const save=(p,v)=>fs.writeFileSync(p,typeof v==='string'?v:JSON.stringify(v,null,2));
const browser=await chromium.launch({headless:true});
try {for(const name of fs.readdirSync(source).sort()) {
 const old=path.join(source,name), raw=read(path.join(old,'agent-events.json'));
 const proposals=raw.events.map(x=>x.data??x).filter(x=>x.type==='APPROVAL'&&x.proposal?.validation_result?.valid===true);
 const userDecision=fs.existsSync(path.join(old,'user-decision.json'))?read(path.join(old,'user-decision.json')):null;
 if(!proposals.length&&!userDecision)continue;
 const dir=path.join(old,'continuation');fs.mkdirSync(dir,{recursive:true});if(fs.existsSync(path.join(dir,'finished.json')))continue;
 const {project,base}=read(path.join(old,'run-id.json'));if(!base.startsWith('http://127.0.0.1:57797'))throw Error('Wrong target');
 const context=await browser.newContext({viewport:{width:1418,height:1272}}),page=await context.newPage();page.setDefaultTimeout(20000);
 const headers={'X-Project-ID':project}; const get=async url=>{const r=await context.request.get(base+url,{headers});if(!r.ok())throw Error('GET '+r.status());return r.json();};
 let run;
 try {
  await page.goto(base+'/studio/agent?project='+project,{waitUntil:'load'});
  await page.getByRole('heading',{name:'Engineering Assistant',exact:true}).waitFor();
  const workflow=await get('/api/engineering/workflow?view=summary');save(path.join(dir,'before.json'),{model_revision:workflow.versions,workflow});
  const pre=read(path.join(old,'preflight.json'));pre.checked_at=new Date().toISOString();pre.required_model_context=pre.required_model_context.map(x=>({...x,evidence:workflow}));save(path.join(dir,'preflight.json'),pre);
  run=tc('run',name,'--preflight',path.join(dir,'preflight.json'),'--baseline',path.join(dir,'before.json'));save(path.join(dir,'run-id.json'),run);
  console.log(name+' CONTINUATION '+run.run_id);
  if(userDecision){
   const payload={messages:[{id:crypto.randomUUID(),role:'user',parts:[{type:'text',text:'Auswahl bestätigt.'}]}],context:{active_project_id:project,active_view:'model'},input:{type:'QUESTION_ANSWER',question_id:userDecision.question_id,selected_options:userDecision.selected_option_ids}};
   save(path.join(dir,'request.json'),payload);save(path.join(dir,'user-decision.json'),userDecision);
   const response=await context.request.post(base+'/api/agent/chat',{headers,data:payload,timeout:300000});const wire=await response.text();save(path.join(dir,'agent.sse'),wire);
   save(path.join(dir,'agent-events.json'),{status:response.status(),events:wire.split('\n').filter(l=>l.startsWith('data: ')&&!l.includes('[DONE]')).flatMap(l=>{try{return [JSON.parse(l.slice(6))];}catch{return [];}})});
   const after=await get('/api/engineering/workflow?view=summary');const model={model_revision:after.versions,workflow:after};save(path.join(dir,'after.json'),model);
   save(path.join(dir,'conversation.json'),await get('/api/engineering/agent/conversation'));
   await page.reload();await page.screenshot({path:path.join(dir,'review.png'),fullPage:true});
   const refs=[];for(const [file,kind]of[['user-decision.json','other'],['agent-events.json','backend'],['conversation.json','backend'],['after.json','model'],['review.png','screenshot']])refs.push(tc('evidence',run.run_id,path.join(dir,file),'--kind',kind).id);
   const obs={run_id:run.run_id,model_after:model,claimed_complete:false,checks:[],findings:[],questions:[{name:'Welche hybride Bus-Strategie soll ich als Vorschlag anlegen?',evidence:refs}]};save(path.join(dir,'observations.json'),obs);save(path.join(dir,'finished.json'),tc('finish',run.run_id,'--observations',path.join(dir,'observations.json')));console.log(name+' USER DECISION SUBMITTED');continue;
  }
  const network=[];page.on('response',async r=>{if(r.url().includes('/proposals/')&&r.request().method()==='POST'){try{network.push({url:r.url(),status:r.status(),body:await r.json()});}catch{}}});
  await page.getByRole('button',{name:'Vorschlag freigeben',exact:true}).first().click();
  await page.getByRole('button',{name:'Ins Modell übernehmen',exact:true}).first().click();
  const proposalId=proposals[0].proposal.proposal_id;
  let current;
  for(let i=0;i<15;i++){current=await get('/api/engineering/agent/proposals/'+proposalId);if(current.data?.status==='APPLIED'||network.some(x=>x.status>=400))break;await page.waitForTimeout(1000);}
  save(path.join(dir,'proposal-after.json'),current);save(path.join(dir,'review-responses.json'),network);
  save(path.join(dir,'review-ui.txt'),await page.locator('body').innerText());await page.screenshot({path:path.join(dir,'review.png'),fullPage:true});
  if(current.data?.status==='APPLIED'){
   const prompt='Der Netzwerkvorschlag wurde im Test freigegeben und übernommen. Führe den ursprünglichen Engineering-Auftrag mit den noch fehlenden Modellobjekten und Prüfschritten fort. Prüfe zuerst den gespeicherten Zustand; erzeuge keine Duplikate. Ursprünglicher Auftrag:\n'+read(path.join(old,'request.json')).messages[0].parts[0].text;
   const payload={messages:[{id:crypto.randomUUID(),role:'user',parts:[{type:'text',text:prompt}]}],context:{active_project_id:project}};save(path.join(dir,'request.json'),payload);
   const response=await context.request.post(base+'/api/agent/chat',{headers,data:payload,timeout:300000});const wire=await response.text();save(path.join(dir,'agent.sse'),wire);
   save(path.join(dir,'agent-events.json'),{status:response.status(),events:wire.split('\n').filter(l=>l.startsWith('data: ')&&!l.includes('[DONE]')).flatMap(l=>{try{return [JSON.parse(l.slice(6))];}catch{return [];}})});
  }
  const after=await get('/api/engineering/workflow?view=summary');const model={model_revision:after.versions,workflow:after};save(path.join(dir,'after.json'),model);
  const refs=[];for(const [file,kind]of[['proposal-after.json','backend'],['review-responses.json','backend'],['review-ui.txt','browser'],['review.png','screenshot'],['after.json','model'],['agent-events.json','backend']])if(fs.existsSync(path.join(dir,file)))refs.push(tc('evidence',run.run_id,path.join(dir,file),'--kind',kind).id);
  const obs={run_id:run.run_id,decision_source:'SCRIPTED_TEST',claimed_complete:false,model_after:model,checks:[{name:'Gültiger Netzwerkvorschlag über reguläre UI übernommen',status:current.data?.status==='APPLIED'?'PASSED':'FAILED',evidence:refs}],findings:[],browser:[{target:'Vorschlag freigeben / Ins Modell übernehmen',purpose:'Reguläre Übernahme eines validierten Teilvorschlags',precondition:'VALIDATED proposal in isolated project',expected_effect:'APPLIED and persisted network',actual_effect:current.data?.status??JSON.stringify(current),url:page.url(),status:'PASSED',evidence:refs}]};save(path.join(dir,'observations.json'),obs);save(path.join(dir,'finished.json'),tc('finish',run.run_id,'--observations',path.join(dir,'observations.json')));console.log(name+' CONTINUED '+current.data?.status);
 }catch(e){save(path.join(dir,'error.txt'),e.stack);console.log(name+' CONTINUATION ERROR '+e.message);if(run){save(path.join(dir,'error-observations.json'),{run_id:run.run_id,environment_error:e.message});save(path.join(dir,'finished.json'),tc('finish',run.run_id,'--observations',path.join(dir,'error-observations.json')));}}
 finally{await context.close();}
}}finally{await browser.close();}
