"""Invalid-project MCP probes with exact rejection and complete unchanged scope."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
from urllib.parse import urlparse

def validation_only(response, tool):
    if set(response)-{'isError','is_error','content','structuredContent','structured_content','_meta','meta','result_type'}:return False
    if response.get('result_type') not in (None,'complete'):return False
    server_meta={'io.modelcontextprotocol/serverInfo':{
        'name':'eip-mcp-gateway','title':'Engineering Intelligence Platform MCP Gateway',
        'version':'1.0.0','description':'Controlled MCP tools over authenticated EIP Backend APIs.'}}
    if any(response.get(k) not in (None,{},server_meta) for k in ('_meta','meta')):return False
    if response.get('isError',response.get('is_error')) is not True:return False
    if response.get('structuredContent',response.get('structured_content')) not in (None,{}):return False
    content=response.get('content')
    if not isinstance(content,list) or len(content)!=1:return False
    item=content[0]
    if item.get('type')!='text' or set(item)-{'type','text','annotations','_meta','meta'}:return False
    if any(item.get(k) not in (None,{}) for k in ('annotations','_meta','meta')):return False
    text=item.get('text','')
    # Framework wrapper and the exact native ValueError are the only allowed text.
    return bool(re.fullmatch(r"(?:Error calling tool '"+re.escape(tool)+r"': |Error executing tool "+re.escape(tool)+r": )?project_id is required",text.strip()))

def load_helper(step):
    path=Path(step['native_helper_path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=step['native_helper_sha256']:
        raise ValueError('Native helper revision changed; review required')
    spec=importlib.util.spec_from_file_location('reviewed_eip_helper',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def execute(request, helper=None):
    step=request['step'];helper=helper or load_helper(step)
    for origin in (step.get('mcp_url','http://127.0.0.1:8013/mcp'),step.get('api_url','http://127.0.0.1:5000')):
        parsed=urlparse(origin)
        if parsed.scheme not in ('http','https') or parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.username or parsed.password:
            raise ValueError('Explicit reviewed loopback origin required')
    if step.get('isolated_scope_authorized') is not True: return helper.blocked('Explicit isolated scope authorization required')
    if not step.get('scope') or not step.get('actor_id') or not step.get('audit_tables') or not step.get('outbox_path'):
        return helper.blocked('Runtime scope, actor and complete audit table mapping required')
    if step['arguments'].get('project_id')!='':return helper.blocked('Reviewed invalid empty project input required')
    nonce=uuid.uuid4().hex
    before=helper.proof(step['proof_argv'],dict(request,nonce=nonce,phase='before'),subprocess.run)
    if before.get('actor_id')!=step['actor_id'] or before.get('scope')!=step['scope'] or before.get('qualification',{}).get('scope_complete') is not True:
        return helper.blocked('Fresh original actor/scope complete baseline mismatch')
    import os
    token=os.environ.get(step['token_env'])
    if not token:return helper.blocked('Explicit token environment unavailable')
    response=asyncio.run(helper.native_call(step.get('mcp_url','http://127.0.0.1:8013/mcp'),token,step['tool'],step['arguments']))
    after=helper.proof(step['proof_argv'],dict(request,nonce=nonce,phase='after'),subprocess.run)
    facets=('canonical','project','diagrams','audit','actor_id','scope','qualification')
    unchanged=all(k in before and before[k]==after.get(k) for k in facets)
    # Other projects may legitimately append events during this call. Compare the
    # complete scoped event sequence, never pauschally every shared outbox write.
    unchanged = unchanged and 'outbox' in before and 'outbox' in after and (
        before['outbox']['events'] == after['outbox']['events'] and
        before['outbox']['path'] == after['outbox']['path'])
    valid=validation_only(response,step['tool']) and unchanged
    path=helper.write_new(Path(request['output_directory']),nonce+'-invalid-project-proof.json',
        {'before':before,'response':response,'after':after,'validation_only':validation_only(response,step['tool']),'unchanged_scope':unchanged})
    evidence=[{'ref':'native-proof','path':path,'kind':'backend'}]
    if not isinstance(after.get('project'),dict) or 'revision' not in after['project'] or not isinstance(after.get('canonical'),dict):
        return helper.blocked('Fresh canonical poststate and project revision required')
    model={'model_revision':after['project']['revision'],'canonical':after['canonical']}
    model_path=helper.write_new(Path(request['output_directory']),nonce+'-model-after.json',model)
    evidence.append({'ref':'model-after','path':model_path,'kind':'model'})
    checks=[{'category':c['category'],'name':c['name'],'status':'PASSED' if valid else 'FAILED',
             'evidence':['native-proof'],**({'observed':not valid} if c['category']=='failure_conditions' else {})}
            for c in step['checks']]
    return {'status':'PASSED' if valid else 'FAILED','llm_calls':0,'evidence':evidence,'observations':{'checks':checks,'model_after':model}}

if __name__=='__main__':
    try:print(json.dumps(execute(json.load(sys.stdin)),ensure_ascii=False))
    except Exception as error:print('EIP negative adapter blocked: '+type(error).__name__,file=sys.stderr);raise SystemExit(2)
