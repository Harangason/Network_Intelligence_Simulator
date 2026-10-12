import test from 'node:test';
import assert from 'node:assert/strict';
import {emptyAnalysisContext,contextWithPatch,validatedContext,validatedDescriptor,contextFromSearch,analysisViewHref,validProfile} from './analysis-workspace.ts';
import {WorkspaceStore,analysisWorkspaceStore} from './analysis-workspace-browser.ts';
import {readAssistantContext} from '../../agent/lib/assistant-context.ts';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
test('context validation rejects foreign projects, bad times and trace payloads as state',()=>{
  const c=emptyAnalysisContext('p');
  assert.equal(validatedContext(c,'foreign'),null);
  for(const time_range of [[-1,2],[2,1],[0,Infinity],[0,NaN]])assert.equal(validatedContext({...c,time_range},'p'),null);
  assert.equal(validatedContext({...c,time_cursor:Infinity},'p'),null);
  assert.equal(validatedContext({...c,filter_set:{query:'x'.repeat(4097)}},'p'),null);
  assert.deepEqual(validatedContext({...c,events:[{id:'shadow'}],permissions:['write']},'p'),c);
});
test('source changes invalidate stale object references without inventing time alignment',()=>{
  const c={...emptyAnalysisContext('p'),simulation_run_id:'golden',trace_id:'golden',message_id:'m',signal_id:'s',event_id:'e',time_cursor:12.5,time_basis:'a'};
  const next=contextWithPatch(c,{simulation_run_id:'fault',trace_id:'fault'});
  assert.equal(next.message_id,null);assert.equal(next.signal_id,null);assert.equal(next.time_basis,null);assert.equal(next.time_cursor,null);
  assert.equal(contextWithPatch(c,{time_cursor:2,time_basis:'clock-b'}).time_basis,'clock-b');
});
test('deep links preserve project, source, selection, compare sides and exact time range',()=>{
  const context={...emptyAnalysisContext('p'),trace_id:'import:s',event_id:'s:5',signal_id:'sig',time_cursor:.000111344,time_range:[.0001,.0002],filter_set:{query:'Motor UND NICHT LIN'},compare_right:{run_id:'fault',trace_id:'fault',object_id:'ecu',time_range:[3,4],view:'signals'}};
  const descriptor={window_id:'child',workspace_id:'w',primary_id:'root',project_id:'p',view_id:'signals',context,link_mode:'COMPARE'};
  const href=analysisViewHref(descriptor),url=new URL(href,'http://localhost');
  assert.equal(url.pathname,'/trace-analysis');assert.equal(url.searchParams.get('link'),'COMPARE');
  const restored=contextFromSearch('p',url.search);assert.deepEqual(restored.time_range,context.time_range);assert.equal(restored.time_cursor,context.time_cursor);assert.equal(restored.trace_id,'import:s');assert.equal(restored.event_id,'s:5');assert.deepEqual(restored.compare_right,context.compare_right);
});
test('profiles contain only local project-scoped safe view restore metadata',()=>{
  const p={version:1,profile_id:'profile',name:'Trace',user_id:'local-session',project_scope:'p',primary_view:'sequence',secondary_views:['signals'],link_modes:['INDEPENDENT'],preferred_window_sizes:[[1200,900]],preferred_monitor_roles:['second'],restore_on_start:true};
  assert.equal(validProfile(p,'p'),true);assert.equal(validProfile(p,'q'),false);assert.equal(validProfile({...p,secondary_views:['editing']},'p'),false);assert.equal(validProfile({...p,preferred_window_sizes:[[Infinity,900]]},'p'),false);
});
const peers=[];
class Channel {
  constructor(name){this.name=name;this.owner=globalThis.window;peers.push(this);}
  postMessage(data){for(const p of peers.filter(p=>p!==this&&p.name===this.name))queueMicrotask(()=>{const old=globalThis.window;globalThis.window=p.owner;try{p.onmessage?.({data:structuredClone(data)});}finally{globalThis.window=old;}});}
  close(){peers.splice(peers.indexOf(this),1);}
}
function browser(search){const url=new URL(`http://localhost/trace-analysis?project=p&${search}`);return {location:{search:url.search,pathname:url.pathname,hash:''},outerWidth:1200,outerHeight:900,screenX:0,screenY:0,history:{state:null,replaceState(_s,_t,href){const next=new URL(href,url);globalThis.window.location.search=next.search;}},addEventListener(){},removeEventListener(){},dispatchEvent(){},setInterval(){return 1;},clearInterval(){},localStorage:{getItem(){return null;},setItem(){},removeItem(){}}};}
const tick=()=>new Promise(r=>setTimeout(r,0));
test('ordered primary sync, follower commands, independent comparison and logout use one context authority',async()=>{
  const oldWindow=globalThis.window,oldChannel=globalThis.BroadcastChannel;
  globalThis.BroadcastChannel=Channel;
  const a=browser('workspace=w&window=root&primary=root'),b=browser('workspace=w&window=child&primary=root&view=signals');
  globalThis.window=a;const primary=new WorkspaceStore('p');
  primary.update({simulation_run_id:'run',trace_id:'run',time_cursor:1,time_basis:'simulation_relative'});
  globalThis.window=b;const follower=new WorkspaceStore('p');await tick();
  assert.equal(follower.state.context.simulation_run_id,'run');assert.equal(follower.state.context.time_cursor,1);
  assert.equal(follower.state.descriptor.view_id,'signals');
  follower.update({signal_id:'s',time_cursor:2});await tick();assert.equal(primary.state.context.signal_id,'s');assert.equal(follower.state.context.time_cursor,2);
  follower.mode('INDEPENDENT');follower.update({trace_id:'other',simulation_run_id:'other'});
  globalThis.window=a;primary.update({time_cursor:3});await tick();assert.equal(follower.state.context.trace_id,'other');assert.equal(follower.state.context.time_cursor,null);
  globalThis.window=b;follower.mode('COMPARE');const side={run_id:'fault',trace_id:'fault',object_id:null,time_range:[1,2],view:'trace'};follower.update({compare_right:side});
  globalThis.window=a;primary.update({event_id:'primary-event',time_cursor:4});await tick();assert.deepEqual(follower.state.context.compare_right,side);assert.equal(follower.state.context.event_id,null);
  globalThis.window=b;follower.mode('FOLLOW_PRIMARY');await tick();assert.equal(follower.state.context.event_id,'primary-event');assert.equal(follower.state.context.time_cursor,4);
  const before=follower.state.context;
  primary.channel.postMessage({protocol:1,workspace:'w',project:'foreign',from:'root',primary:'root',type:'STATE',revision:Date.now()+100,context:emptyAnalysisContext('foreign')});await tick();assert.deepEqual(follower.state.context,before);
  primary.channel.postMessage({protocol:1,workspace:'w',project:'p',from:'root',primary:'root',type:'STATE',revision:0,context:emptyAnalysisContext('p')});await tick();assert.deepEqual(follower.state.context,before);
  primary.end();await tick();assert.equal(follower.state.ended,true);assert.equal(follower.state.context.trace_id,null);assert.deepEqual(follower.state.windows,[]);
  primary.dispose();follower.dispose();globalThis.window=oldWindow;globalThis.BroadcastChannel=oldChannel;
});
test('shared trace cache rechecks server access on hits and denies revoked or foreign access',async()=>{
  const code=await readFile(new URL('../../../../public/nis-analysis-worker.js',import.meta.url),'utf8');
  const replies=[],requests=[];let allowed=true;
  const port={start(){},postMessage(data){replies.push(data);}};
  const runtime={self:{},URLSearchParams,AbortSignal,Date,Error,Map,JSON,Number,fetch:async(path,options)=>{requests.push({path,project:options.headers['X-Project-ID']});return {ok:allowed,status:allowed?200:403,text:async()=>JSON.stringify({events:[{event_id:'original'}],next_cursor:null})};}};
  vm.runInNewContext(code,runtime);runtime.self.onconnect({ports:[port]});
  const parameters='cursor=0&limit=2000&start_s=0&end_s=1&q=';
  await port.onmessage({data:{type:'READ',id:'a',project:'p',source:'run',parameters}});await port.onmessage({data:{type:'READ',id:'b',project:'p',source:'run',parameters}});
  assert.equal(requests.filter(r=>r.path.includes('trace-window')).length,1);assert.equal(requests.filter(r=>r.path.includes('view=metadata')).length,2);assert.equal(replies[1].result.events[0].event_id,'original');
  allowed=false;await port.onmessage({data:{type:'READ',id:'c',project:'p',source:'run',parameters}});assert.match(replies[2].error,/403/);assert.equal(replies[2].result,undefined);
  await port.onmessage({data:{type:'READ',id:'d',project:'foreign',source:'run',parameters}});assert.match(replies[3].error,/403/);assert.equal(requests.at(-1).project,'foreign');
  await port.onmessage({data:{type:'READ',id:'e',project:'p',source:'run',parameters:parameters.replace('2000','2001')}});assert.match(replies[4].error,/Ungültiges Trace-Fenster/);
});

test('the existing assistant request context receives exact analysis references and clears them on session end',()=>{
  const oldWindow=globalThis.window,oldChannel=globalThis.BroadcastChannel;
  globalThis.window=browser('workspace=assistant-test&window=root&primary=root&view=signals');
  globalThis.BroadcastChannel=Channel;
  const primary=analysisWorkspaceStore('p');
  try {
    primary.update({trace_id:'import:original',signal_id:'pressure',event_id:'original:4',time_cursor:.4,time_range:[.1,.8],time_basis:'clock-a',analysis_stage:'INSPECT_SIGNALS'});
    const request=readAssistantContext();
    assert(request.selected_object_refs.some(r=>r.object_type==='Signal'&&r.id==='pressure'));
    const metadata=request.selected_object_refs.find(r=>r.object_type==='AnalysisContext');
    assert.equal(metadata.project_id,'p');assert.equal(metadata.event_id,'original:4');assert.equal(metadata.time_cursor,'0.4');assert.equal(metadata.time_basis,'clock-a');assert.equal(metadata.analysis_stage,'INSPECT_SIGNALS');
    globalThis.window.location.search='?project=foreign';
    assert.deepEqual(readAssistantContext().selected_object_refs,[]);
    globalThis.window.location.search='?project=p';primary.end();
    assert.deepEqual(readAssistantContext().selected_object_refs,[]);
  } finally {primary.dispose();globalThis.window=oldWindow;globalThis.BroadcastChannel=oldChannel;}
});
