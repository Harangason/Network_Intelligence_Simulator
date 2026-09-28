"""Receipt-bound environment for existing native NIS adapters; no project creation."""
import argparse,hashlib,json,os,re,shutil,subprocess,sys,uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import build_opener,ProxyHandler,Request,HTTPRedirectHandler
ROOT=Path('I:/PycharmProjects/My_first_Network_Simulator')
HASHES={'complete_master_reuse_adapter.mjs':'dd5fb5b1621d8afaeb136108f12d61d0e66c80d5d807a42b142fb19ae0c32a98','complete_master_wizard_adapter.mjs':'bec03bbe5c87d0e58d26067b9fae97396a282f3fd5581af3adcdabcc469da1e4','complete_master_specialized_adapter.mjs':'994c31a08c1066692616ee3d65d66d76ee7cba37d4922594a653a0e06dcb71a9'}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args):raise ValueError('Isolated runtime redirect rejected')
def verify_wizard_admission(root):
 helper=Path(root)/'.tool-checker/src/20260927_src_wizard_decision_admission.mjs'
 if helper.is_symlink() or hashlib.sha256(helper.read_bytes()).hexdigest()!='121139c9d629f2f412ec94bda7ece6049442935a2abec90a60b443cc6a82b80f':raise ValueError('Unreviewed wizard decision admission helper bytes/path')

def context(request,adapter):
 root=ROOT.resolve(strict=True);state=root/'.tool-checker/state'
 if Path(request['project']).resolve()!=root:raise ValueError('Native request project mismatch')
 job_id=request['job_id']
 if not re.fullmatch(r'job-[a-zA-Z0-9-]+',job_id):raise ValueError('Invalid native job ID')
 directory=state/'jobs'/job_id
 if Path(request['output_directory']).resolve()!=directory.resolve() or not directory.is_dir():raise ValueError('Native job evidence directory mismatch')
 job=read(directory/'job.json')
 if job.get('job_id')!=job_id or job.get('run_id')!=request['run_id'] or request['step'] not in job.get('plan',[]):raise ValueError('Native job step binding mismatch')
 target=Path(adapter).resolve(strict=True)
 if target.parent!=root/'.tool-checker' or target.name not in HASHES or hashlib.sha256(target.read_bytes()).hexdigest()!=HASHES[target.name]:raise ValueError('Unreviewed adapter bytes/path')
 if target.name=='complete_master_wizard_adapter.mjs':verify_wizard_admission(root)
 step=request['step'];receipt_path=Path(step['runtime_receipt']).resolve(strict=True)
 if not receipt_path.is_relative_to(root/'.tool-checker/runs'):raise ValueError('Runtime receipt outside project runs')
 receipt=read(receipt_path);base=step['base_url'].rstrip('/');url=urlsplit(base)
 if url.scheme!='http' or url.hostname!='127.0.0.1' or url.port in (None,13500,15050) or url.path or url.query or url.fragment or url.username or url.password:raise ValueError('Invalid isolated test URL')
 if receipt.get('status')!='PREPARED' or receipt.get('development_only') is not True or receipt.get('base_url','').rstrip('/')!=base:raise ValueError('Isolated runtime receipt mismatch')
 project=step.get('project_id','')
 if not (project.startswith('nis-e2e-final-examples-') or re.fullmatch(r'nis-ea-independent-20260924-r[1-3]-[a-z0-9-]+',project)):raise ValueError('Non-disposable test project')
 docker=shutil.which('docker') or str(Path.home()/'AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe')
 observed=[]
 for role in ('app','db'):
  name=receipt.get('containers',{}).get(role,'')
  if not re.fullmatch('nis-e2e-'+role+'-[a-z0-9]+',name):raise ValueError('Non-disposable container name')
  container=json.loads(subprocess.check_output([docker,'inspect',name],timeout=15))[0]
  if not container['State']['Running'] or container['Config']['Labels'].get('networkis.test')!='disposable':raise ValueError('Test container stopped or isolation unverified')
  if role=='app':
   if container['Image']!=receipt['image_id']:raise ValueError('Runtime image drift')
   bindings=[b for values in container['NetworkSettings']['Ports'].values() for b in (values or [])]
   if not any(b.get('HostPort')==str(url.port) and b.get('HostIp')=='127.0.0.1' for b in bindings):raise ValueError('Runtime port drift')
  observed.append({'container':name,'running':True,'image':container['Image']})
 with build_opener(ProxyHandler({}),NoRedirect()).open(Request(base+'/api/build-info',headers={'X-Project-ID':project}),timeout=10) as response:build=json.load(response)
 if build!=receipt['release']:raise ValueError('Running build drift')
 return {'base_url':base,'directory':directory,'target':target,'containers':observed,'build':build,'project_id':project}
def execute(request,adapter):
 binding=context(request,adapter)
 directory=binding['directory']/('adapter-evidence-'+uuid.uuid4().hex);directory.mkdir()
 env={**os.environ,'TOOL_CHECKER_ALLOWED_BASE_URL':binding['base_url'],'TOOL_CHECKER_EVIDENCE_ROOT':str(directory),'PYTHONUTF8':'1'}
 # Adapter invokes several different Python interpreters; inherited homes mix stdlibs.
 env.pop('PYTHONHOME',None);env.pop('PYTHONPATH',None)
 sys.path.insert(0,str(ROOT/'.tool-checker/cli/scripts'))
 from tool_check import Checker
 from source_discovery import resolve_reference
 job=read(binding['directory']/'job.json')
 manifest=read(ROOT/'.tool-checker/state/tasks'/job['task_id']/'manifest.json')
 rule=manifest['rule_files'][0]
 source=resolve_reference(Checker(ROOT/'.tool-checker/state'),rule['path'])
 if hashlib.sha256(source.read_bytes()).hexdigest()!=rule['sha256']:raise ValueError('Original rule source hash mismatch')
 env['TOOL_CHECKER_ORIGINAL_SOURCE_PATH']=str(source)
 env['TOOL_CHECKER_ORIGINAL_SOURCE_SHA256']=rule['sha256']
 (directory/'runtime-binding.json').write_text(json.dumps({k:str(v) if isinstance(v,Path) else v for k,v in binding.items()},indent=2),encoding='utf-8')
 node=shutil.which('node')
 if not node:
  installed=Path('C:/Program Files/nodejs/node.exe')
  if installed.is_file():node=str(installed)
 if not node:raise ValueError('Node executable unavailable')
 return subprocess.run([node,str(binding['target'])],input=json.dumps(request).encode('utf-8'),env=env,cwd=str(ROOT),stdout=sys.stdout.buffer,stderr=sys.stderr.buffer,shell=False).returncode
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--adapter',required=True);args=parser.parse_args()
 try:return execute(json.load(sys.stdin.buffer),args.adapter)
 except Exception as error:print('Receipt-bound NIS adapter blocked: '+str(error),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
