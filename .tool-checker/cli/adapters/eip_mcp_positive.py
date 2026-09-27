"""Reviewed positive MCP semantics. No live result is inferred from registration."""
import asyncio
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from urllib.parse import urlparse, parse_qs

TOOLS = ('search_requirements','get_requirement','get_requirement_coverage','get_architecture_context',
         'get_trace_path','get_open_issues','validate_traceability','create_requirement_draft',
         'create_function_draft','create_trace_link','create_diagram_view','get_diagram_view_state',
         'export_diagram_json','export_traceability_matrix','export_project_report','create_presentation')
WRITES = {'create_requirement_draft','create_function_draft','create_trace_link'}
VOLATILE = {'sourceSnapshotId','snapshotId','generatedAt','capturedAt','requestId','cache'}

class MissingEvidence(ValueError): pass

def stable(value):
    if isinstance(value, dict): return {k:stable(v) for k,v in value.items() if k not in VOLATILE}
    if isinstance(value, list): return [stable(v) for v in value]
    return value

def require(value, message):
    if not value: raise AssertionError(message)

def rows(payload, *keys):
    for key in keys:
        if isinstance(payload.get(key), list): return payload[key]
    return []

def gaps(payload):
    result=[]
    for key in ('dataGaps','gaps','warnings','criticalGaps'):
        for item in payload.get(key,[]) if isinstance(payload.get(key),list) else []:
            if item not in result: result.append(item)
    return result

def canonical_map(proof):
    result={}
    for obj in proof['canonical']['objects']:
        db=obj['fields']['database_fields']
        for key in (obj['id'],db.get('object_key'),db.get('external_id')):
            if key: result[str(key)]=obj
    if not result: raise MissingEvidence('Empty canonical scope')
    return result

def structural_group_diagram(value, scope):
    """Typed generated hardware-group view, never a foreign Core entity."""
    group=value.get('objectRef'); identity=value.get('id')
    if scope is None or group not in {'Central','Domain','Networks'}: return False
    mode=next((mode for mode in ('bdd','ibd') if identity==f'generated--system--{group}--{mode}-system'),None)
    if mode is None: return False
    if not (value.get('scopeRef')==group and value.get('scopeType')=='system' and
            value.get('owningBoard')=='hardware' and value.get('parentScopeRef') is None and
            value.get('kind')=='Hardware Topology' and value.get('ref')==f'DIAGRAM.{group}.{mode}-system'): return False
    link=urlparse(value.get('editLink',''))
    return not link.scheme and not link.netloc and link.path=='/dashboard/project' and parse_qs(link.query)=={
        'project':[scope],'panel':['diagram'],'diagram':[identity],'mode':[mode]}

def refs(value, canon, scope=None):
    """Validate explicit Core refs; generated diagram IDs are projection identities."""
    if isinstance(value, list):
        for item in value: refs(item,canon,scope)
    elif isinstance(value,dict):
        for key,item in value.items():
            if key=='projectId' and item and scope is not None: require(item==scope,'Foreign nested project reference')
            if key in {'objectRef','scopeRef','sourceRef','targetRef','sourceKey','targetKey','globalUuid','engineeringObjectId'} and item:
                require(str(item) in canon or (key in {'objectRef','scopeRef'} and structural_group_diagram(value,scope)), 'Foreign or nonexistent canonical reference: '+key)
            elif isinstance(item,(dict,list)): refs(item,canon,scope)

def object_rows(items,canon):
    for row in items:
        require(isinstance(row,dict),'Native object row is not an object')
        identities=[row[k] for k in ('id','ref','uuid','globalUuid') if row.get(k)]
        require(bool(identities) and all(str(i) in canon for i in identities),'Native row identity is not canonical')

def trace_pair(args,before):
    canon=canonical_map(before); source=canon.get(args['source_id'])
    if not source or source['type']!='Requirement': raise MissingEvidence('Authorized trace source Requirement unavailable')
    linked=set()
    for relation in before['canonical']['relationships']:
        db=relation['fields']['database_fields']
        if relation['source_table']=='trace_links' and str(db.get('source_id'))==source['id'] and db.get('link_type')==args['relationship_type']:
            linked.add(str(db['target_id']))
    candidates=sorted((o for o in before['canonical']['objects'] if o['type']=='Function' and o['id'] not in linked and o['fields']['database_fields'].get('status')=='draft'),key=lambda o:o['fields']['database_fields'].get('object_key',''))
    if not candidates: raise MissingEvidence('No absent compatible trace pair in authorized synthetic scope')
    return candidates[0]['fields']['database_fields']['object_key']

def preserved(before, after):
    require(set(before)==set(after),'Native audit scope changed')
    for table,original in before.items():
        current={str(r['id']):r for r in after[table]}
        require(len(current)==len(after[table]),'Duplicate native audit identity')
        require(all(current.get(str(r['id']))==r for r in original),'Original audit row changed/deleted')

def outbox_check(before,after):
    require(after['prefix_length']==before['byte_length'] and after['prefix_sha256']==before['sha256'],
            'Original outbox bytes changed')
    old={r['id']:r for r in before['events']}; new={r['id']:r for r in after['events']}
    require(all(new.get(k)==v for k,v in old.items()),'Original scoped outbox event changed')
    return {k:v for k,v in new.items() if k not in old}

def event_match(events,envelope,tool,actor,scope,action,digest=None):
    event_id=envelope.get('audit',{}).get('auditEventId')
    require(bool(event_id) and event_id in events,'Missing fresh independent native audit event')
    event=events[event_id]; payload=event.get('payload',{})
    require(event.get('type')=='McpToolAudited' and event.get('projectId')==scope and
            event.get('actor')==actor and event.get('source')=='eip-mcp-gateway' and
            payload.get('tool')==tool and payload.get('action')==action and
            payload.get('coreWritesPerformed') is False,'Native audit actor/tool/action mismatch')
    if digest is not None: require(payload.get('artifactSha256')==digest,'Native artifact audit hash mismatch')

def supporting_event(events,tool,actor,scope,action,digest=None):
    matches=[event for event in events.values() if event.get('payload',{}).get('tool')==tool and event.get('payload',{}).get('action')==action and (digest is None or event.get('payload',{}).get('artifactSha256')==digest)]
    require(bool(matches),'Missing native supporting analysis/export audit')
    for event in matches: event_match(events,{'audit':{'auditEventId':event['id']}},tool,actor,scope,action,digest)

def diagram_data(source,args,limit):
    entries=rows(source,'items','entries','diagrams')[:limit]
    kind=args.get('diagram_type','').strip()
    if kind: entries=[r for r in entries if kind.casefold() in str(r.get('type') or r.get('diagramType') or r.get('kind') or '').casefold()]
    if not entries: raise MissingEvidence('No existing canonical diagram projection to qualify')
    return {'diagramType':kind or None,'entries':entries,'viewStateOnly':True,'coreWritesPerformed':False,'dataGaps':gaps(source)}

def report_text(scope,p):
    req=p['requirements']; arch=p['architecture']; issues=p['issues']; trace=p['traceability']
    count=lambda k:len(arch.get(k,[])) if isinstance(arch.get(k),list) else 0
    opened=[r for r in rows(issues,'issues','rows','items') if str(r.get('status') or r.get('state') or 'open').strip().lower() not in {'closed','done','resolved','rejected','archived'}]
    return '\n'.join((f'# EIP Project Report: {scope}','','## Source','Authenticated EIP backend projections; generated by eip-mcp-gateway/1.0.','','## Requirements',f"Visible requirements: {len(rows(req,'items','rows','requirements'))}",'','## Architecture',f"Components: {count('components')}; interfaces: {count('interfaces')}; dependencies: {count('dependencies')}",'','## Open Issues',f'Open issues: {len(opened)}','','## Traceability',f"Rows evaluated: {len(rows(trace,'rows','items','links'))}; data gaps: {len(gaps(trace))}",''))

def mutation(tool,args,data,before,after,canon):
    old={o['id']:o for o in before['canonical']['objects']}; new={o['id']:o for o in after['canonical']['objects']}
    orels={o['id']:o for o in before['canonical']['relationships']}; nrels={o['id']:o for o in after['canonical']['relationships']}
    require(all(new.get(k)==v for k,v in old.items()),'Mutation changed/deleted original Core object')
    require(all(nrels.get(k)==v for k,v in orels.items()),'Mutation changed/deleted original Core relation')
    added=[v for k,v in new.items() if k not in old]; edges=[v for k,v in nrels.items() if k not in orels]
    require(after['diagrams']==before['diagrams'],'Mutation changed diagram state')
    bp=before['project']; ap=after['project']
    require({k:v for k,v in bp.items() if k not in {'revision','updated_at'}}=={k:v for k,v in ap.items() if k not in {'revision','updated_at'}},'Unrelated project row mutation')
    require(int(ap['revision'])>int(bp['revision']),'Native project revision did not advance')
    if tool=='create_trace_link':
        require(args.get('confirmed') is True and data.get('status')=='applied','Trace preview is not persisted trace effect')
        require(not added,'Trace mutation created unrelated objects')
        src=canon.get(args['source_id']); dst=canon.get(args['target_id'])
        require(src and dst,'Trace endpoints absent from canonical scope')
        links=[e for e in edges if e['source_table']=='trace_links']
        require(len(links)==1 and len(edges)==1,'Unexpected trace relation delta')
        link=links[0]['fields']['database_fields']
        require(str(link['source_id'])==src['id'] and str(link['target_id'])==dst['id'] and link['link_type']==args['relationship_type'],'Wrong persisted trace link')
        command=data.get('command',{}); result=command.get('result',{})
        require(command.get('ok') is True and command.get('storage')=='postgresql','Trace native command returned no successful PostgreSQL result')
        require(result.get('id')==str(link['id']) and result.get('projectKey')==after['scope'] and result.get('sourceKey')==args['source_id'] and result.get('targetKey')==args['target_id'] and result.get('relationshipType')==args['relationship_type'] and result.get('traceLink') is True and result.get('created') is True and result.get('revision')==link.get('revision'),'Trace result identity/revision differs from persisted effect')
        target_id=src['id']; audit_action='trace_link.upsert'
    else:
        require(len(added)==1 and not edges,'Draft must create exactly one Core object and no unrelated relations')
        obj=added[0]; db=obj['fields']['database_fields']; meta=db.get('technical_metadata') or db.get('metadata') or {}
        spec=obj['fields']['specializations']; key=args['requirement_id'] if tool=='create_requirement_draft' else args['function_id']
        require(db.get('object_key')==key and str(db.get('object_type','')).casefold()==('requirement' if tool=='create_requirement_draft' else 'function'),'Wrong draft canonical ID/type')
        require(data.get('status')=='review_required' and db.get('status',db.get('lifecycle_status'))=='draft','Draft review boundary not persisted')
        draft=data.get('draft',{}); result=draft.get('result',{})
        require(draft.get('ok') is True,'Native draft command returned no success')
        if tool=='create_requirement_draft':
            require(db.get('name')==args['title'] and len(spec.get('requirements',[]))==1 and spec['requirements'][0].get('statement')==args['text'],'Wrong persisted requirement title/text')
            require(meta.get('requirement_type')==args.get('requirement_type','system') and meta.get('proposal',{}).get('proposalOnly') is True and meta.get('proposalStatus')=='review_required' and meta.get('source')=='eip-mcp-gateway','Wrong requirement proposal metadata')
            require(draft.get('storage')=='postgresql' and result.get('id')==obj['id'] and result.get('objectKey')==key and result.get('projectKey')==after['scope'] and result.get('objectType')=='Requirement' and result.get('revision')==obj['revision'] and result.get('created') is True,'Requirement result identity/revision differs from persisted draft')
        else:
            require(db.get('name')==args['name'] and meta.get('description')==args['description'] and len(spec.get('functions',[]))==1,'Wrong persisted function fields')
            require(meta.get('source')=='function_manager_command','Wrong native function provenance')
            require(not args.get('source_requirement_id') or args['source_requirement_id'] in canon,'Function proposed source requirement absent from native scope')
            require(result.get('ok') is True and result.get('atomic') is True and result.get('storage')=='postgresql' and result.get('engineeringObjectId')==obj['id'] and result.get('externalId')==key and result.get('projectId')==after['scope'] and result.get('objectType')=='Function' and result.get('revision')==obj['revision'] and result.get('projectRevision')==ap['revision'] and result.get('relationships')==0,'Function result identity/revision differs from persisted draft')
        target_id=obj['id']; audit_action=('requirement.upsert' if tool=='create_requirement_draft' else 'function.upsert')
    channels={}
    for table in ('audit_log','digital_thread_events'):
        after_rows=after['audit'].get(table,[])
        ids={str(r['id']) for r in before['audit'][table]}
        fresh=[r for r in after_rows if str(r['id']) not in ids and r.get('actor_id')==after['actor_id'] and str(r.get('project_id'))==str(ap['id']) and str(r.get('object_id'))==str(target_id) and r.get('action' if table=='audit_log' else 'event_type')==audit_action and r.get('correlation_id')]
        require(len(fresh)==1,'Expected exactly one fresh native audit in '+table)
        channels[table]=fresh[0]
    require(channels['audit_log']['correlation_id']==channels['digital_thread_events']['correlation_id'],'Native audit channels have mismatched correlations')

def evaluate(step,before,response,after):
    tool=step['tool']; args=step['arguments']; scope=step['scope']; actor=step['actor_id']
    for p in (before,after):
        if p.get('actor_id')!=actor or p.get('scope')!=scope or p.get('qualification',{}).get('scope_complete') is not True: raise MissingEvidence('Fresh actor/scope completeness mismatch')
    canon=canonical_map(before); preserved(before['audit'],after['audit']); events=outbox_check(before['outbox'],after['outbox'])
    require(response.get('isError',response.get('is_error')) is False,'MCP positive returned error or no explicit success flag')
    env=response.get('structuredContent',response.get('structured_content'))
    require(isinstance(env,dict) and env.get('ok') is True and env.get('tool')==tool and env.get('projectId')==scope and env.get('authorization')=='enforced-by-eip-backend','Wrong native result envelope')
    d=env['data']; p=before['projections']; refs(d,canonical_map(after),scope)
    if tool in WRITES:
        mutation(tool,args,d,before,after,canon); return
    require(all(before[k]==after[k] for k in ('canonical','project','diagrams')),'Read/export changed canonical/project/diagram state')
    require(stable(before['projections'])==stable(after['projections']),'Source projections changed during read/export')
    expected=None
    if tool=='search_requirements':
        allrows=rows(p['requirements'],'items','rows','requirements'); q=args.get('query','').strip().casefold(); typ=args.get('requirement_type','').strip().casefold(); status=args.get('status','').strip().casefold()
        matched=[r for r in allrows if (not q or q in ' '.join(str(r.get(k) or '') for k in ('id','ref','title','name','text','description')).casefold()) and (not typ or typ==str(r.get('type') or r.get('requirementType') or r.get('level') or '').casefold()) and (not status or status==str(r.get('status') or r.get('state') or '').casefold())]
        limit=max(1,min(200,int(args.get('limit',50)))); offset=max(0,min(1000000,int(args.get('offset',0)))); page=matched[offset:offset+limit]
        if not page: raise MissingEvidence('Positive requirement search has no matching existing data')
        object_rows(page,canon)
        expected={'items':page,'total':len(matched),'limit':limit,'offset':offset,'nextOffset':offset+len(page) if offset+len(page)<len(matched) else None,'filters':{'query':args.get('query',''),'requirementType':args.get('requirement_type',''),'status':args.get('status','')},'sourceTotal':p['requirements'].get('total'),'sourceScanTruncated':False,'dataGaps':gaps(p['requirements'])}
    elif tool=='get_requirement':
        require(args['requirement_id'] in canon,'Requested requirement absent from canonical scope'); expected={'requirement':p['requirement']}
        require(p['requirement'].get('id')==args['requirement_id'],'Backend requirement identity mismatch')
    elif tool=='get_requirement_coverage':
        detail=p['coverage'].get('detail'); require(args['requirement_id'] in canon,'Coverage requirement absent')
        g=gaps(p['coverage']); g.extend(x for x in gaps(detail or {}) if x not in g)
        if detail is None or detail.get('coverage') is None: g.append(args['requirement_id']+': Requirement coverage is unavailable.')
        expected={'requirementId':args['requirement_id'],'detail':detail,'coverage':(detail or {}).get('coverage'),'dataGaps':g}
    elif tool=='get_architecture_context':
        expected=p['architecture']
        object_rows(expected.get('components',[]),canon); object_rows(expected.get('interfaces',[]),canon)
    elif tool=='get_trace_path':
        require(args['source_id'] in canon,'Trace source not canonical'); expected=p['trace_path']
        require(expected.get('from')==args['source_id'],'Trace path wrong source')
        for hop in expected.get('path',[]):
            for key in ('source','target','sourceId','targetId','from','to'):
                if hop.get(key): require(str(hop[key]) in canon,'Trace path foreign endpoint')
    elif tool=='get_open_issues':
        opened=[r for r in rows(p['issues'],'issues','rows','items') if str(r.get('status') or r.get('state') or 'open').strip().lower() not in {'closed','done','resolved','rejected','archived'}]
        object_rows(opened,canon)
        limit=max(1,min(500,int(args.get('limit',100)))); expected={'items':opened[:limit],'total':len(opened),'limit':limit,'dataGaps':gaps(p['issues'])}
    elif tool=='validate_traceability':
        source=p['traceability']; rr=rows(source,'rows','items','links')
        if not rr: raise MissingEvidence('No traceability source rows')
        expected={'scope':args.get('scope','requirements').strip().lower(),'summary':source.get('stats') or source.get('summary') or {k:source[k] for k in ('overallCoverage','validation','meta') if k in source},'rowsEvaluated':len(rr),'dataGaps':gaps(source),'coreWritesPerformed':False}
        event_match(events,env,tool,actor,scope,'analysis_completed')
    elif tool=='create_diagram_view': expected=diagram_data(p['diagrams'],args,max(1,min(500,int(args.get('limit',100)))))
    elif tool=='get_diagram_view_state':
        entries=diagram_data(p['diagrams'],{},500)['entries']; wanted=args['diagram_id']; entry=next((r for r in entries if wanted in {str(r.get(k) or '') for k in ('id','ref','diagramId')}),None)
        if entry is None: raise MissingEvidence('Requested existing diagram absent')
        expected={'diagramId':wanted,'viewState':entry,'found':True,'viewStateOnly':True,'coreWritesPerformed':False}
    else:
        content=d.get('content'); require(isinstance(content,str) and hashlib.sha256(content.encode('utf-8')).hexdigest()==d.get('sha256'),'Artifact UTF-8 hash/content mismatch')
        require(d.get('coreWritesPerformed') is False and d.get('reproducible') is True,'Artifact projection boundary violated')
        event_match(events,env,tool,actor,scope,'export_generated',d['sha256'])
        if tool=='export_diagram_json':
            require(d.get('mediaType')=='application/json' and d.get('extension')=='json','Wrong diagram format')
            require(stable(json.loads(content))==stable(diagram_data(p['diagrams'],args,500)),'Diagram artifact differs from native source')
        elif tool=='export_traceability_matrix':
            source=p['traceability_rows']; rr=rows(source,'items','rows','links'); reader=csv.DictReader(io.StringIO(content)); parsed=list(reader)
            require(reader.fieldnames==['source','target','relationshipType','status','id','ref','objectType','coverage','gaps'],'Wrong CSV header')
            require(bool(rr) and len(parsed)==len(rr)==d.get('exportedRows') and d.get('sourceTotal')==source.get('total') and d.get('sourceScanTruncated') is False,'Wrong CSV source counts')
            for r,c in zip(rr,parsed):
                expectedrow={'source':r.get('source') or r.get('sourceRef') or r.get('from') or r.get('ref') or r.get('id') or '', 'target':r.get('target') or r.get('targetRef') or r.get('to') or '', 'relationshipType':r.get('relationshipType') or r.get('relation') or '', 'status':r.get('status') or r.get('state') or '', 'id':r.get('id') or '', 'ref':r.get('ref') or '', 'objectType':r.get('type') or '', 'coverage':r.get('coverage') if r.get('coverage') is not None else '', 'gaps':json.dumps(r.get('gaps') or [],ensure_ascii=False)}
                require(c=={k:str(v) for k,v in expectedrow.items()},'CSV row differs from native source')
                require(c['source'] in canon and (not c['target'] or c['target'] in canon),'CSV foreign source/target')
            require(d.get('mediaType')=='text/csv' and d.get('extension')=='csv','Wrong CSV format')
        elif tool=='export_project_report':
            require(content==report_text(scope,p) and d.get('mediaType')=='text/markdown' and d.get('extension')=='md','Report counts/source differ from backend projections')
            supporting_event(events,'validate_traceability',actor,scope,'analysis_completed')
        elif tool=='create_presentation':
            spec=json.loads(content); report=report_text(scope,p); title=args.get('title','').strip()
            expected_spec={'format':'eip-presentation-spec/1.0','title':title or f'EIP Project Status – {scope}','projectId':scope,'slides':[{'type':'title','title':title or 'Engineering Project Status','subtitle':scope},{'type':'management-summary','title':'Management Summary','bullets':[line for line in report.splitlines() if line and not line.startswith('#')]},{'type':'diagram','title':'Architecture','sourceTool':'export_diagram_json','rendering':'adapter-required'},{'type':'table','title':'Traceability','sourceTool':'export_traceability_matrix','rendering':'adapter-required'}],'officeAdapter':{'status':'provider-required','automaticRemoteControl':False,'writeback':False},'sourceArtifactSha256':hashlib.sha256(report.encode('utf-8')).hexdigest(),'coreWritesPerformed':False}
            require(spec==expected_spec and d.get('mediaType')=='application/vnd.eip.presentation+json' and d.get('extension')=='json','Presentation source/slides/Office boundary mismatch')
            supporting_event(events,'export_project_report',actor,scope,'export_generated',expected_spec['sourceArtifactSha256'])
            supporting_event(events,'validate_traceability',actor,scope,'analysis_completed')
        else: raise MissingEvidence('Unsupported tool')
    if expected is not None: require(stable(d)==stable(expected),'Tool data differs from independent backend source')

def load_helper(step):
    path=Path(step['native_helper_path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=step['native_helper_sha256']: raise MissingEvidence('Reviewed native helper changed')
    spec=importlib.util.spec_from_file_location('positive_native_helper',path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def execute(request,helper=None,invoke=subprocess.run):
    step=dict(request['step']); args=dict(step['arguments']); step['arguments']=args; request=dict(request,step=step)
    helper=helper or load_helper(step)
    if not request.get('run_id') or not request.get('job_id') or not Path(request['output_directory']).is_dir(): return helper.blocked('Existing native job/run/output required')
    if step.get('tool') not in TOOLS or args.get('project_id')!=step.get('scope') or step.get('isolated_scope_authorized') is not True: return helper.blocked('Reviewed positive tool and authorized isolated scope required')
    for url in (step.get('mcp_url','http://127.0.0.1:8013/mcp'),step.get('api_url','http://127.0.0.1:5000')):
        parsed=urlparse(url)
        if parsed.scheme not in ('http','https') or parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.username or parsed.password: return helper.blocked('Reviewed loopback origin required')
    token=os.environ.get(step['token_env'])
    if not token: return helper.blocked('Explicit token environment unavailable')
    nonce=uuid.uuid4().hex
    if step['tool'] in WRITES:
        args['idempotency_key']='tc-positive-'+request['run_id']+'-'+nonce
        if step['tool']=='create_requirement_draft': args['requirement_id']='TC-POS-REQ-'+nonce[:16]
        elif step['tool']=='create_function_draft': args['function_id']='TC-POS-FUNC-'+nonce[:16]
        elif args.get('confirmed') is not True: return helper.blocked('Persisted trace requires explicit confirmed test input')
    before=helper.proof(step['proof_argv'],dict(request,nonce=nonce,phase='before'),invoke)
    if before.get('actor_id')!=step['actor_id'] or before.get('scope')!=step['scope'] or before.get('qualification',{}).get('scope_complete') is not True: return helper.blocked('Fresh baseline actor/scope unavailable')
    if step['tool']=='create_trace_link':
        try: args['target_id']=trace_pair(args,before)
        except MissingEvidence as e: return helper.blocked(str(e))
    response=asyncio.run(helper.native_call(step.get('mcp_url','http://127.0.0.1:8013/mcp'),token,step['tool'],args))
    after=helper.proof(step['proof_argv'],dict(request,nonce=nonce,phase='after',outbox_prefix_length=before['outbox']['byte_length']),invoke)
    observed={'before':before,'response':response,'after':after,'tool':step['tool'],'arguments':args,'scope':step['scope'],'actor_id':step['actor_id'],'binding':{'run_id':request['run_id'],'job_id':request['job_id'],'nonce':nonce}}
    path=helper.write_new(Path(request['output_directory']),nonce+'-positive-native-proof.json',observed)
    evidence=[{'ref':'native-proof','path':path,'kind':'backend'}]
    model={'model_revision':after['project']['revision'],'canonical':after['canonical']}
    mp=helper.write_new(Path(request['output_directory']),nonce+'-model-after.json',model); evidence.append({'ref':'model-after','path':mp,'kind':'model'})
    try: evaluate(step,before,response,after)
    except MissingEvidence as e: return helper.blocked(str(e),evidence)
    except (AssertionError,KeyError,TypeError,ValueError) as e: return helper.failed('Positive semantic effect failed: '+str(e),evidence)
    checks=[{'category':c['category'],'name':c['name'],'status':'PASSED','evidence':['native-proof','model-after'],**({'observed':False} if c['category']=='failure_conditions' else {})} for c in step['checks']]
    return {'status':'PASSED','llm_calls':0,'evidence':evidence,'observations':{'checks':checks,'model_after':model,'tools':[{'name':step['tool'],'status':'PASSED','evidence':['native-proof']}]}}

if __name__=='__main__':
    try: print(json.dumps(execute(json.load(sys.stdin)),ensure_ascii=False))
    except Exception as error: print(json.dumps({'status':'BLOCKED','llm_calls':0,'evidence':[],'observations':{'findings':[{'code':'POSITIVE_EVIDENCE_UNAVAILABLE','category':'ENVIRONMENT_ERROR','blocking':True,'detail':type(error).__name__}]}}))
