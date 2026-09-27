"""Local agent-browser actions with explicit DOM assertions and fresh receipts."""
import json
import os
import shutil
import subprocess
import sys
import uuid
import tempfile
from pathlib import Path
from datetime import datetime, timezone

ACTIONS={'navigate':'open','click':'click','fill':'fill','select':'select','inspect':'snapshot'}
ASSERTIONS={'text_equals','text_contains','url_equals','title_equals','visible'}

def validate_step(step):
    if step.get('browser_action') not in ACTIONS:raise ValueError('Explicit supported browser action required')
    if not step.get('precondition'):raise ValueError('Browser precondition required')
    assertions=step.get('assertions')
    if not isinstance(assertions,list) or not assertions:raise ValueError('Browser assertions required')
    for a in assertions:
        if a.get('kind') not in ASSERTIONS:raise ValueError('Unsupported browser assertion')
        if a['kind'] not in ('url_equals','title_equals') and not a.get('target'):raise ValueError('DOM assertion target required')
        if a['kind']!='visible' and not isinstance(a.get('expected'),str):raise ValueError('Explicit assertion expectation required')
    if step['browser_action']=='navigate':
        if not step.get('url','').startswith(('http://','https://','file:///')):raise ValueError('Reviewed browser URL required')
    elif step['browser_action']!='inspect' and not step.get('target'):raise ValueError('Action target required')
    if step['browser_action'] in ('fill','select') and not isinstance(step.get('value'),str):raise ValueError('Action value required')

def command_argv(command=None):
    command=command or os.environ.get('TOOL_CHECKER_AGENT_BROWSER') or shutil.which('agent-browser')
    if not command:raise RuntimeError('Local agent-browser executable unavailable')
    path=Path(command)
    if path.suffix.lower() in ('.cmd','.ps1'):
        native=path.parent/'node_modules/agent-browser/bin/agent-browser-win32-x64.exe'
        if native.is_file():return [str(native)]
        # Execute installed JS directly, avoiding Windows shell argument reparsing.
        entry=path.parent/'node_modules/agent-browser/bin/agent-browser.js'
        node=shutil.which('node')
        if not entry.is_file() or not node:raise RuntimeError('agent-browser JS entry or Node unavailable')
        return [node,str(entry)]
    return [str(command)]

def local_invoke(argv, **kwargs):
    # Browser daemons can inherit pipe handles on Windows. Files cannot keep
    # communicate() waiting after the bounded CLI process has exited.
    kwargs.pop('capture_output',None)
    kwargs.pop('text',None);kwargs.pop('encoding',None);kwargs.pop('errors',None)
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        result=subprocess.run(argv,stdout=stdout,stderr=stderr,**kwargs)
        stdout.seek(0);stderr.seek(0)
        return subprocess.CompletedProcess(argv,result.returncode,stdout.read().decode('utf-8','replace'),stderr.read().decode('utf-8','replace'))

def close_session(job_id, invoke=local_invoke, command=None):
    if not isinstance(job_id,str) or not job_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in job_id):
        raise ValueError('Owned job identifier required')
    result=invoke(command_argv(command)+['--session','tc-'+job_id,'close'],shell=False,timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode:raise RuntimeError('Owned browser session could not be closed')

def execute(request, invoke=local_invoke, command=None):
    step=request['step'];validate_step(step)
    if not request.get('job_id') or not request.get('run_id'):raise ValueError('Existing job/run binding required')
    output=Path(request['output_directory']).resolve()
    if not output.is_dir():raise ValueError('Existing evidence directory required')
    prefix=command_argv(command)
    session='tc-'+request['job_id']
    def call(args):
        result=invoke(prefix+['--session',session]+args,capture_output=True,text=True,encoding='utf-8',errors='replace',
                      shell=False,timeout=step.get('timeout',30),creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode:raise RuntimeError('Browser command failed; no successful receipt')
        return result.stdout.strip()
    action=[ACTIONS[step['browser_action']]]
    if step['browser_action']=='navigate':action.append(step['url'])
    elif step['browser_action']!='inspect':action.append(step['target'])
    if step['browser_action'] in ('fill','select'):action.append(step['value'])
    nonce=uuid.uuid4().hex
    started=datetime.now(timezone.utc).isoformat()
    call(action);snapshot=call(['snapshot']);url=call(['get','url'])
    checks=[]
    for a in step['assertions']:
        kind=a['kind']
        if kind=='url_equals':actual=url
        elif kind=='title_equals':actual=call(['get','title'])
        elif kind=='visible':actual=call(['is','visible',a['target']]).lower()=='true'
        else:actual=call(['get','text',a['target']])
        passed=actual is True if kind=='visible' else a['expected'] in actual if kind=='text_contains' else actual==a['expected']
        checks.append({'assertion':a,'actual':actual,'passed':passed})
    screenshot=output/(nonce+'-browser.png');call(['screenshot',str(screenshot)])
    if not screenshot.is_file() or not screenshot.stat().st_size:raise RuntimeError('Fresh screenshot missing')
    passed=all(c['passed'] for c in checks)
    receipt={'run_id':request['run_id'],'job_id':request['job_id'],'nonce':nonce,'started_at':started,
             'observed_at':datetime.now(timezone.utc).isoformat(),'url':url,'snapshot':snapshot,'checks':checks}
    path=output/(nonce+'-browser.json')
    with path.open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
    status='PASSED' if passed else 'FAILED'
    observations={'browser':[{'target':step.get('target',url),'purpose':step['step_label'],
        'precondition':step['precondition'],'expected_effect':json.dumps(step['assertions']),
        'actual_effect':json.dumps(checks),'url':url,'status':status,'evidence':['browser','screenshot']}]}
    return {'status':status,'llm_calls':0,'evidence':[{'ref':'browser','path':str(path),'kind':'browser'},
            {'ref':'screenshot','path':str(screenshot),'kind':'screenshot'}],'observations':observations}

if __name__=='__main__':
    try:print(json.dumps(execute(json.load(sys.stdin)),ensure_ascii=False))
    except Exception as error:
        print('Local browser runner blocked: '+type(error).__name__,file=sys.stderr);raise SystemExit(2)
