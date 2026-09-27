"""Real NIS capability observation for explicitly supported native CLI cases."""
import argparse,importlib.util,json,sys,uuid
from pathlib import Path
from urllib.error import HTTPError
ROOT=Path('I:/PycharmProjects/My_first_Network_Simulator')
sys.path.insert(0,str(ROOT/'.tool-checker/cli/scripts'))
from tool_check import Checker,read,write,now
from plan_registry import resolve_case,bind_parameters
from nis_preflight import collect,get_json
VIEWS={'Projects':'/projects','Engineering':'/studio/engineering','Routing':'/studio/routing','Network':'/studio?mode=network','Capacity':'/studio/capacity','Validation':'/studio/validation','Simulation':'/studio/simulation','Trace':'/trace-analysis','Intelligence':'/studio/intelligence'}

def latest_preflight(base,project,tools):
 # GET reads a previously computed snapshot, not validator availability.
 # A new empty wizard project has no snapshot yet; preserve that state explicitly.
 if not any(t.get('id')=='validate.preflight' and t.get('status')=='available' and t.get('execution_endpoint')=='/preflight' for t in tools.get('items',[])):
  raise ValueError('Registered core preflight validator unavailable')
 try:return get_json(base,project,'/api/engineering/preflight')
 except HTTPError as error:
  if error.code!=404:raise
  body=json.loads(error.read())
  if body!={'error':'Noch kein Preflight vorhanden.'}:raise ValueError('Core preflight endpoint not observed')
  return {'status':'NOT_RUN','snapshot_available':False,'validator_availability':'Observed validate.preflight tool registry entry; no validation acceptance claimed'}
def validate(request,request_path,output):
 root=ROOT.resolve();directory=Path(request['evidence_directory']).resolve(strict=True)
 if Path(request['project']).resolve()!=root or Path(request['state']).resolve()!=root/'.tool-checker/state':raise ValueError('NIS project/state binding mismatch')
 if not directory.is_relative_to(root/'.tool-checker/runs/preflight') or Path(request_path).resolve().parent!=directory or Path(output).resolve().parent!=directory:raise ValueError('Preflight paths outside new native evidence scope')
 cfg=read(root/'.tool-checker/config/project-cli.json');provider=cfg['preflight_provider']
 if provider.get('reviewed') is not True or request['test_id'] not in provider.get('supported_case_ids',[]):raise ValueError('Case is outside reviewed automatic preflight scope')
 mapping=provider.get('capability_mapping',{})
 if mapping.get('reviewed') is not True or mapping.get('requested_skill')!='computer-use' or mapping.get('scope')!='browser-only' or mapping.get('native_windows') is not False:raise ValueError('Explicit reviewed browser-only compatibility mapping missing')
 checker=Checker(request['state']);task=request['task_id'];manifest=checker.manifest(task)
 case=checker.select(request['test_id'],task)
 if len(case)!=1 or request['source_hash']!=manifest['source_hash'] or request['contract_hash']!=case[0]['contract_hash']:raise ValueError('Native preflight contract/source binding mismatch')
 canonical=bind_parameters(resolve_case(checker,task,case[0]),checker.cfg())
 if request['case']!=canonical:raise ValueError('Native preflight resolved case differs from registered contract')
 return mapping

def observe(request,manifest):
 root=ROOT.resolve();directory=Path(request['evidence_directory']);step=request['case']['execution_plan'][0]
 base=step['base_url'].rstrip('/');project=step['project_id'];receipt=read(step['runtime_receipt'])
 build=get_json(base,project,'/api/build-info')
 if build!=receipt['release']:raise ValueError('Actual test build drift')
 tools=get_json(base,project,'/api/engineering/tools')
 if not tools.get('items'):raise ValueError('Actual runtime tool catalog unavailable')
 agent=get_json(base,project,'/api/engineering/agent/capabilities')
 if agent.get('success') is not True:raise ValueError('Actual agent capability observer denied/unavailable')
 validator=latest_preflight(base,project,tools)
 if not isinstance(validator,dict) or not validator:raise ValueError('Existing core preflight result unavailable')
 write(directory/'tool-availability.json',{'checked_at':now(),'runtime_build':build,'tools':tools,'agent_capabilities':agent,'core_preflight_observed':validator,'scope':'Availability observation; no completed LLM execution or new semantic validation claimed'})
 spec=importlib.util.spec_from_file_location('native_browser',root/'.tool-checker/cli/adapters/browser_runner.py');browser=importlib.util.module_from_spec(spec);spec.loader.exec_module(browser)
 mapping=read(root/'.tool-checker/config/project-cli.json')['preflight_provider']['capability_mapping'];command=Path(mapping['browser_command']).resolve(strict=True)
 job='preflight-'+uuid.uuid4().hex;observations=[]
 try:
  for name,path in VIEWS.items():
   url=base+path+('&' if '?' in path else '?')+'project='+project
   action={'step_id':'view-'+name.lower(),'step_label':name+' availability','precondition':'Receipt-bound disposable NIS project','browser_action':'navigate','url':url,'assertions':[{'kind':'visible','target':'body'},{'kind':'url_equals','expected':url}], 'timeout':45}
   proof=browser.execute({'step':action,'job_id':job,'run_id':'automatic-preflight','output_directory':str(directory)},command=str(command))
   if proof['status']!='PASSED':raise ValueError('Browser view unavailable: '+name)
   # An error page can be visible at the requested URL; reject it explicitly.
   receipt_data=read(proof['evidence'][0]['path'])
   if any(marker in receipt_data['snapshot'].lower() for marker in ('heading "404"','heading "not found"','heading "application error"','heading "internal server error"')):raise ValueError('Browser error page: '+name)
   observations.append({'name':name,'status':'PASSED','url':receipt_data['url'],'actions':['navigate','snapshot','DOM visible assertion','URL assertion','screenshot'],'evidence':proof['evidence']})
 finally:browser.close_session(job,command=str(command))
 if get_json(base,project,'/api/build-info')!=build:raise ValueError('Runtime changed during capability observation')
 proof={'provider':'installed native browser_runner.py / agent-browser Chromium','requested_skill':'computer-use','scope':'browser-only compatibility for explicitly requested standalone CLI','native_windows':False,'sky_or_cua_executed':False,'views':observations,'tools_scope':'Observed catalog/capability/preflight endpoints; actual case execution remains separate','checked_at':now()}
 write(directory/'capability-compatibility.json',proof)
 return {'tools':['Browser','Core validators','Engineering Agent','MCP','NIS isolated runtime'],'skills':['computer-use'],'views':list(VIEWS),'provider':proof['provider'],'native_windows':False,'sky_or_cua_executed':False,'evidence':[str(directory/'tool-availability.json'),str(directory/'capability-compatibility.json')]}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
 try:
  request=read(args.request);validate(request,args.request,args.output)
  write(args.output,collect(request,observe_capabilities=observe));return 0
 except Exception as error:
  # Final structured stdout is safe even if output path validation rejected it.
  print(json.dumps({'status':'BLOCKED','reason':str(error)},ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
