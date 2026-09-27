"""Build reviewed EIP bindings from original contracts; never invokes EIP."""
import ast
import hashlib
import json
from pathlib import Path
import sys

def build(project, package):
    project=Path(project);package=Path(package)
    source=project/'.tool-checker/src'
    helper=source/'20260927_src_cli_adapter.py'
    tree=ast.parse((source/'20260925_src_mcp_negative_cases.py').read_text(encoding='utf-8-sig'))
    arguments=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ARGS' for t in n.targets))
    directory=project/'.tool-checker/var/state/tasks/eip-integrationsmaster-20260925/test_cases'
    cases={p.stem:json.loads(p.read_text(encoding='utf-8-sig')) for p in directory.glob('*.json')}
    definitions={'scope':{'type':'string'},'actor_id':{'type':'string'},'token_env':{'type':'string'},
        'audit_tables':{'type':'array'},'isolated_scope_authorized':{'type':'boolean'},
        'proof_argv':{'type':'array'}}
    plans={}
    for tool,args in arguments.items():
        test='MCP-'+tool+'-negative';case=cases[test]
        step={'step_id':'invalid-project','step_label':case['title'],'kind':'adapter','adapter':'eip-invalid-project',
            'phase':'engineering_execution','precondition':'Fresh authorized actor and complete isolated scope baseline',
            'tool':tool,'arguments':dict(args,project_id=''),'native_helper_path':str(helper),
            'native_helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),
            **{k:{'$parameter':k} for k in definitions},
            'checks':[{'category':k,'name':name} for k in ('completion_criteria','failure_conditions') for name in case[k]]}
        plans[test]={'contract_hash':case['contract_hash'],'execution_plan':[step],'parameters':definitions,
            'reviewer':'source-review-20260927','reason':'Exact project_id required rejection; validation-only response; complete unchanged original scope'}
    case=cases['REGRESSION']
    plans['REGRESSION']={'contract_hash':case['contract_hash'],'execution_plan':[{'step_id':'regression-profiles','step_label':case['title'],
        'kind':'adapter','adapter':'eip-regression','phase':'engineering_execution','operation':'regression',
        'precondition':'Fresh isolated database authorization and native runtime preflight',
        'isolated_database_authorized':{'$parameter':'isolated_database_authorized'},
        'checks':[{'category':k,'name':name} for k in ('completion_criteria','failure_conditions') for name in case[k]]}],
        'parameters':{'isolated_database_authorized':{'type':'boolean'}},'reviewer':'source-review-20260927',
        'reason':'Existing two-profile adapter verifies complete collection/JUnit, errors and skips'}
    missing={test:('Original browser/assistant/editor journey has no source-qualified local action/assertion plan' if case['browser_required']
             else 'Positive MCP domain result requires missing exact identity/reference/persistence/audit criterion mappings')
             for test,case in cases.items() if test not in plans}
    return {'kind':'REVIEWED_BINDINGS_NOT_RUN','registered_design_count':len(plans),'original_case_count':len(cases),
            'adapters':{'eip-invalid-project':{'argv':[sys.executable,str(package/'adapters/eip_mcp_negative.py')],'uses_llm':False,'mutating':False},
                        'eip-regression':{'argv':[sys.executable,str(helper)],'uses_llm':False,'mutating':False}},
            'plans':plans,'missing_implementation':missing,'runtime_blockers':'Explicit parameters, authorization, fresh native preflight and helper revision checks required; no executed EIP outcomes'}

if __name__=='__main__':
    project=Path(sys.argv[1]);package=Path(__file__).resolve().parent.parent
    target=Path(sys.argv[2]);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as file:json.dump(build(project,package),file,ensure_ascii=False,indent=2)
