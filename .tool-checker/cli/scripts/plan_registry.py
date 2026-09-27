"""Reviewed local plan overlays; original and frozen contracts stay untouched."""
from pathlib import Path
import copy
from tool_check import read, write, digest, ident
from progress_model import plan_for

def location(checker, task, test):
    from case_inventory import artifacts, safe
    return safe(artifacts(checker), 'plans/'+ident(task)+'/'+ident(test)+'.json')

def validate(case, plan, parameters):
    if not isinstance(parameters,dict): raise ValueError('Parameter definitions must be an object')
    candidate=dict(case,execution_plan=plan)
    steps,_=plan_for(candidate)
    for step in steps:
        if not step.get('kind'): continue
        if step['kind']=='http' and not any(k in step for k in ('equals','contains','json_equals')):
            raise ValueError('HTTP status alone is not a semantic expectation')
        for key in step.get('required_parameters',[]):
            if key not in parameters: raise ValueError('Required parameter has no definition: '+key)
        if not step.get('precondition'): raise ValueError('Every registered step needs a precondition')
        if step['kind']=='adapter' and not step.get('checks'):
            raise ValueError('Adapter needs exact original criterion mappings')
    mapped={(c['category'],c['name']) for s in plan for c in s.get('checks',[])}
    required={(category,name) for category in ('completion_criteria','failure_conditions') for name in case.get(category,[])}
    if not required.issubset(mapped): raise ValueError('Original criteria are not completely mapped')
    for name,schema in parameters.items():
        if not isinstance(schema,dict) or schema.get('type') not in ('string','boolean','integer','object','array'):
            raise ValueError('Explicit parameter type required: '+name)
    return candidate

def register(checker, task, test, plan, *, parameters=None, reviewer, reason, replace_hash=None):
    from case_inventory import revision_for
    case=read(checker.task(task)/'test_cases'/(ident(test)+'.json'))
    if case.get('execution_plan'): raise ValueError('Original native execution_plan already exists; preserve it')
    if not reviewer or not reason: raise ValueError('Reviewer and rationale required')
    validate(case,plan,parameters or {})
    path=location(checker,task,test)
    payload={'format':1,'task_id':task,'test_id':test,'revision':revision_for(case,checker.manifest(task)),
             'contract_hash':case['contract_hash'],'execution_plan':copy.deepcopy(plan),
             'parameters':parameters or {},'reviewer':reviewer,'reason':reason}
    payload['sha256']=digest(payload)
    if path.exists():
        old=read(path)
        verify(old)
        if old==payload:return old
        if replace_hash!=old['sha256']:raise ValueError('Existing reviewed overlay preserved; explicit old hash required')
        history=path.parent/'history'/test/(old['sha256']+'.json')
        if not history.exists():write(history,old)
    write(path,payload)
    return payload

def verify(payload):
    if payload.get('sha256')!=digest({k:v for k,v in payload.items() if k!='sha256'}):
        raise ValueError('Reviewed plan overlay hash conflict')

def resolve_case(checker, task, case):
    from case_inventory import revision_for
    if case.get('execution_plan'):return case
    path=location(checker,task,case['test_id'])
    if not path.exists():return case
    payload=read(path);verify(payload)
    if payload['revision']!=revision_for(case,checker.manifest(task)) or payload['contract_hash']!=case['contract_hash']:
        raise ValueError('Reviewed execution_plan overlay is outdated: '+case['test_id'])
    candidate=validate(case,payload['execution_plan'],payload['parameters'])
    candidate['plan_binding']={'sha256':payload['sha256'],'path':str(path),'revision':payload['revision']}
    candidate['plan_parameters']=payload['parameters']
    return candidate

def effective_llm_policy(case, cfg, requested=None):
    """A case override is authorized only by its current reviewed plan/contract."""
    from progress_model import POLICIES
    policy = requested or cfg.get('llm_usage_policy', 'ON_DEMAND')
    if policy not in POLICIES: raise ValueError('Unknown LLM policy')
    overrides = cfg.get('reviewed_case_llm_policies', {})
    if not isinstance(overrides, dict): raise ValueError('Reviewed case LLM policies must be an object')
    override = overrides.get(case['test_id'])
    if override is None: return policy
    if not isinstance(override, dict) or set(override) != {'policy', 'contract_hash', 'plan_sha256'}:
        raise ValueError('Exact reviewed case LLM policy binding required: ' + case['test_id'])
    if override['policy'] not in POLICIES: raise ValueError('Unknown reviewed case LLM policy')
    binding = case.get('plan_binding', {})
    if (not binding.get('sha256') or override['contract_hash'] != case.get('contract_hash')
            or override['plan_sha256'] != binding['sha256']):
        raise ValueError('Reviewed case LLM policy is stale/unbound: ' + case['test_id'])
    if requested is not None and requested != override['policy']:
        raise ValueError('Requested LLM policy conflicts with reviewed case binding')
    return override['policy']


def parameter_blockers(case, cfg):
    values=cfg.get('plan_parameters',{}).get(case['test_id'],{})
    types={'string':str,'boolean':bool,'integer':int,'object':dict,'array':list}
    blockers=[]
    for name,schema in case.get('plan_parameters',{}).items():
        if schema.get('required',True) and name not in values: blockers.append('Missing plan parameter: '+name)
        elif name in values and (type(values[name]) is not types[schema['type']] or values[name] in (None,'')):
            blockers.append('Invalid plan parameter: '+name)
    return blockers

def bind_parameters(case,cfg):
    blockers=parameter_blockers(case,cfg)
    if blockers:raise ValueError('; '.join(blockers))
    values=cfg.get('plan_parameters',{}).get(case['test_id'],{})
    def bind(item):
        if isinstance(item,dict):
            if set(item)=={'$parameter'}:
                if item['$parameter'] not in values:raise ValueError('Missing referenced plan parameter')
                return copy.deepcopy(values[item['$parameter']])
            return {k:bind(v) for k,v in item.items()}
        if isinstance(item,list):return [bind(v) for v in item]
        return item
    return dict(case,execution_plan=bind(case['execution_plan']))

def main(argv=None):
    import argparse
    import json
    from tool_check import Checker
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',required=True);parser.add_argument('--task',required=True)
    sub=parser.add_subparsers(dest='operation',required=True)
    p=sub.add_parser('register');p.add_argument('test_id');p.add_argument('--plan',required=True)
    p.add_argument('--replace-hash');p=sub.add_parser('status');p.add_argument('test_id')
    args=parser.parse_args(argv);checker=Checker(args.state)
    if args.operation=='register':
        definition=read(args.plan)
        result=register(checker,args.task,args.test_id,definition['execution_plan'],parameters=definition.get('parameters',{}),
                        reviewer=definition['reviewer'],reason=definition['reason'],replace_hash=args.replace_hash)
        print(json.dumps({'status':'REGISTERED','sha256':result['sha256'],'executed':False}))
    else:
        case=read(checker.task(args.task)/'test_cases'/(ident(args.test_id)+'.json'))
        resolved=resolve_case(checker,args.task,case)
        from case_inventory import readiness
        blockers=readiness(resolved,checker.cfg())
        print(json.dumps({'registered':bool(resolved.get('execution_plan')),'blockers':blockers,'executed':False}))
    return 0

if __name__=='__main__':raise SystemExit(main())
