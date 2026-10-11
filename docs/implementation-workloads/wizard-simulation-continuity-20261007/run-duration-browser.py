import hashlib,json,os,subprocess,sys
from pathlib import Path
from urllib.parse import urlparse
out=Path(__file__).parent.resolve();root=out.parents[2]
path=Path(sys.argv[1]).resolve()
assert path.is_relative_to(out/'duration-intent-stack')
receipt=json.loads(path.read_text())
assert receipt['status']=='PREPARED' and receipt.get('development_only') is not True
endpoint=urlparse(receipt['base_url'])
assert endpoint.hostname=='127.0.0.1' and endpoint.port not in {13500,15050,None}
docker='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
names=receipt['containers']
for key in ('app','db','network','runtime'):
 assert names[key].startswith('nis-e2e-'+key+'-')
assert subprocess.check_output([docker,'inspect',names['app'],'--format','{{.Image}}'],text=True).strip()==receipt['image_id']
environment={**os.environ,'NIS_E2E_ISOLATED':'1','NIS_E2E_URL':receipt['base_url'],
 'NIS_E2E_APP_CONTAINER':names['app'],'NIS_TEST_DOCKER':docker,
 'NIS_E2E_OUTPUT':str(out/'duration-intent-browser'),'NIS_E2E_REPORT':str(out/'duration-intent-browser.json')}
environment.pop('NIS_E2E_BROWSER_CHANNEL',None)
cleanup=[]
try:
 with (out/'duration-intent-browser.log').open('w',encoding='utf-8') as log:
  result=subprocess.run(['C:/Program Files/nodejs/node.exe','node_modules/playwright/cli.js','test',
   'e2e/technology-parameter-review.spec.ts','--grep','native simulation rates|CAN-FD scenario defaults'],
   cwd=root/'frontend',env=environment,stdout=log,stderr=subprocess.STDOUT)
 report_path=out/'duration-intent-browser.json';report=json.loads(report_path.read_text())
 report['_evidence']={'receipt':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},
  'image_id':receipt['image_id'],'source_sha256':receipt['release']['source_sha256'],
  'coverage':'TWO_REAL_PARAMETER_DURATION_INTENT_CASES_NOT_FULL_RELEASE'}
 report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
 if result.returncode==0:
  assert report['stats']['expected']==2 and report['stats']['unexpected']==0 and not report.get('errors')
 print(json.dumps({'exit_code':result.returncode,'stats':report['stats'],'image_id':receipt['image_id']}))
finally:
 for kind,key in [('container','app'),('container','db'),('network','network'),('volume','runtime')]:
  inspect=[docker,'inspect'] if kind=='container' else [docker,kind,'inspect']
  label='{{ index .Config.Labels "networkis.test" }}' if kind=='container' else '{{ index .Labels "networkis.test" }}'
  assert subprocess.check_output([*inspect,names[key],'--format',label],text=True).strip()=='disposable'
  command=[docker,'rm','-f',names[key]] if kind=='container' else [docker,kind,'rm',names[key]]
  removed=subprocess.run(command,capture_output=True,text=True)
  cleanup.append({'kind':kind,'name':names[key],'exit_code':removed.returncode})
  assert removed.returncode==0,removed.stderr
 (out/'duration-intent-browser-cleanup.json').write_text(json.dumps(cleanup,indent=2),encoding='utf-8')
sys.exit(result.returncode)
