"""Read-only actual local Qwen evaluation with full source/section evidence."""
import asyncio,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from backend.nis.agent.orchestration.local_reasoner import LocalEngineeringReasoner
from backend.nis.engineering.goal_execution.progress import sink
OUT=Path(__file__).parent
SOURCE=Path('C:/Users/marti/PycharmProjects/Benchmark_Modelle/Fahrzeug komplett.txt')
async def main():
 source=SOURCE.read_bytes().decode('utf-8');reasoner=LocalEngineeringReasoner();calls=[];started=time.monotonic()
 state={'status':'RUNNING','source_path':str(SOURCE),'source_chars':len(source),'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'database_access':False,'scope':'native_parser_probe_only_not_wizard_or_simulation','module_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['backend/nis/agent/orchestration/project_intake.py','backend/nis/agent/orchestration/local_reasoner.py']}}
 def save(): (OUT/'native-vehicle-parser-probe.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
 def progress(event):
  state['progress']=event;save();print(json.dumps(event,ensure_ascii=True),flush=True)
 async def capture(response):
  if response.request.url.path!='/api/chat': return
  await response.aread();actual=response.json();payload=json.loads(response.request.content);user=json.loads(payload['messages'][1]['content']);text=''.join(user['source_lines'].values())
  calls.append({'model':actual.get('model'),'eval_count':actual.get('eval_count'),'prompt_eval_count':actual.get('prompt_eval_count'),'seconds':actual.get('total_duration',0)/1e9,'source_chars':len(text),'source_sha256':hashlib.sha256(text.encode()).hexdigest(),'repair':'validation_feedback' in user})
  state['calls']=calls;save();print(json.dumps({'event':'MODEL_RESPONSE',**calls[-1]}),flush=True)
 reasoner.client.event_hooks['response']=[capture];token=sink.set(progress);save()
 try:
  result=await reasoner.interpret_document(source,SOURCE.name)
  assert result['source_complete'] and not result['canonical_writes'] and result['approval_required']
  assert result['source_sha256']==state['source_sha256'] and result['source_chars']==len(source)
  assert len(result['segments']) >= 1
  assert result['segments'][0]['start']==0 and result['segments'][-1]['end']==len(source)
  assert all(a['end']==b['start'] for a,b in zip(result['segments'],result['segments'][1:]))
  assert [c['source_sha256'] for c in calls if not c['repair']]==[s['sha256'] for s in result['segments']]
  assert all(c['eval_count'] and c['model']==reasoner.model for c in calls)
  assert SOURCE.read_bytes().decode('utf-8') == source
  state.update(status='PASSED',result=result)
 except Exception as error:
  state.update(status='FAILED',error=str(error));raise
 finally:
  state['seconds']=time.monotonic()-started;save();sink.reset(token);await reasoner.client.aclose()
 print(json.dumps({'status':'PASSED','sections':len(result['segments']),'components':len(result['interpretation']['components']),'seconds':state['seconds']}),flush=True)
if __name__=='__main__': asyncio.run(main())
