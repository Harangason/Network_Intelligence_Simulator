"""Read-only NIS preflight for registered isolated HTTP reuse cases.
Never starts a container, creates a project, or fabricates semantic observations.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler, Request
from tool_check import read, write, now

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('Redirect bei lokaler Vorprüfung abgewiesen')

INVENTORY_RESOURCES=('hardware-nodes','hardware-interfaces','functions','interfaces','messages','signals')
EA_FIXTURE_KEYS={
    'EA-01':('source_signal_id','actuator_id','imported_assistant_state'),
    'EA-02':('known_signal_id','known_recipient_id','imported_history'),
    'EA-03':('source_signal_id','actuator_id','imported_assistant_state'),
    'EA-04':(),
    'EA-05':(),
    'EA-06':('snapshot_id','job_id','imported_history'),
    'EA-07':('gateway_id','route_id','imported_history'),
    'EA-08':('known_signal_id','unresolved_signal_id','imported_history'),
    'EA-09':('hardware_id','controller_id','max_channels','model'),
    'EA-09-NO-CAPABILITY':('hardware_id','controller_id','max_channels','model'),
    'EA-10':('snapshot_id','job_id','imported_history'),
    'EA-11':('objects','model','missing_fields'),
    'EA-11-MODEL-DETERMINED':('source_signal_id','actuator_id','imported_assistant_state'),
    'EA-12':('known_signal_id','workload_id','controlled_failure'),
    'EA-12-PRECONDITION':('known_signal_id','workload_id','controlled_failure'),
}

def get_json(base, project, path):
    with build_opener(ProxyHandler({}), NoRedirect()).open(Request(base+path, headers={'X-Project-ID':project}),timeout=10) as response:
        return json.load(response)

def observe_s41_registry(project_id, tools_payload, capability_payload):
    """Validate live registry reachability without claiming the S41 UI assertions passed."""
    if not isinstance(tools_payload, dict) or not isinstance(tools_payload.get('items'), list):
        raise ValueError('S41: Engineering-Toolregistry ist nicht lesbar')
    tools = [item for item in tools_payload['items'] if isinstance(item, dict)]
    available_tools = sorted({item.get('id') for item in tools if item.get('status') == 'available' and item.get('id')})
    if not available_tools:
        raise ValueError('S41: kein verfügbares registriertes Engineering-Tool beobachtet')
    if not isinstance(capability_payload, dict) or capability_payload.get('success') is not True:
        raise ValueError('S41: Engineering-Assistent-Capability-Endpunkt nicht erfolgreich')
    data = capability_payload.get('data')
    if isinstance(data, dict) and isinstance(data.get('data'), dict):
        data = data['data']
    if not isinstance(data, dict) or data.get('project_id') != project_id or not isinstance(data.get('capabilities'), list):
        raise ValueError('S41: Capability Registry ohne passenden Projektbezug oder Einträge')
    capabilities = [item for item in data['capabilities'] if isinstance(item, dict)]
    if not capabilities or any(not isinstance(item.get('id'), str) or not item['id'] for item in capabilities):
        raise ValueError('S41: registrierte Capability-Einträge sind unvollständig')
    return {'project_id': project_id, 'available_tool_ids': available_tools,
            'capability_ids': sorted({item['id'] for item in capabilities}),
            'available_capability_ids': sorted({item['id'] for item in capabilities if item.get('available') is True}),
            'source': 'live-engineering-tool-and-assistant-capability-registries'}

def observe_s45_simulation_pair(project_id, jobs, details_by_id):
    """Find current-project positive and fault Universal Traces from live API data."""
    positive = []
    negative = []
    for job in jobs:
        if not isinstance(job, dict) or job.get('project_id') != project_id or job.get('status') != 'completed':
            continue
        job_id = job.get('id')
        detail = details_by_id.get(job_id) if isinstance(job_id, str) else None
        if not isinstance(detail, dict) or detail.get('project_id') != project_id or detail.get('status') != 'completed':
            continue
        result = detail.get('result') or {}
        trace = result.get('trace') or {}
        artifacts = detail.get('artifact_downloads') or []
        has_universal_trace = trace.get('universal_trace') is True and any(
            isinstance(item, dict) and item.get('name') == 'universal_trace.jsonl' for item in artifacts)
        if not has_universal_trace:
            continue
        simulation = result.get('model_simulation') or {}
        scenario = simulation.get('scenario') or {}
        fault_summary = simulation.get('fault_summary') or {}
        fault_count = int(fault_summary.get('configured_faults') or fault_summary.get('total_faults') or 0)
        fault_count = max(fault_count, len(scenario.get('faults') or []))
        if fault_count > 0:
            negative.append(job_id)
        else:
            positive.append(job_id)
    if not positive or not negative:
        raise ValueError('S45: aktuelle positive und Fault-Simulation mit Universal Trace fehlen im selben Testprojekt')
    return {'positive_job_ids': sorted(set(positive)), 'fault_job_ids': sorted(set(negative)),
            'project_id': project_id, 'source': 'live-simulation-jobs-and-universal-trace-artifacts'}

def check_special_reuse(case, step, base):
    """Read the specific starting fact of a reuse scenario from its live project."""
    test_id=case['test_id'];project=step['project_id']
    if test_id in ('S43','S44'):
        exported=get_json(base,project,'/api/engineering/projects/export')
        source=exported.get('source_data') or {}
        if test_id=='S43':
            names={row.get('name') for rows in source.values() if isinstance(rows,list)
                   for row in rows if isinstance(row,dict)}
            required={'Controller_A','CAN_FD_1','Network_A','TemperatureSignal'}
            missing=sorted(required-names)
            if missing:raise ValueError('S43: Ausgangsmodell enthält nicht die benannten Objekte: '+', '.join(missing))
            return {'required_object_names':sorted(required),'source':'canonical-project-export'}
        signals=source.get('engineering_signals') or []
        matches=[row for row in signals if row.get('name')=='MotorRPM'
                 and row.get('lifecycle_state') not in ('deprecated','superseded')]
        if len(matches)!=1:
            raise ValueError('S44: genau ein aktives MotorRPM-Signal im kanonischen Modell erforderlich')
        signal=matches[0]
        width=(signal.get('configuration') or {}).get('bit_length') or signal.get('length_bits')
        if width!=4:raise ValueError('S44: vorhandenes MotorRPM-Binding hat nicht die geforderten 4 Bit')
        return {'signal_id':signal['id'],'binding_bits':4,'source':'canonical-project-export'}
    if test_id=='S45':
        jobs=get_json(base,project,'/api/simulations').get('jobs') or []
        if not isinstance(jobs, list): raise ValueError('S45: Simulationsregistry liefert keine Jobliste')
        details={}
        for job in jobs:
            if isinstance(job, dict) and job.get('project_id')==project and job.get('status')=='completed' and isinstance(job.get('id'), str):
                details[job['id']]=get_json(base,project,'/api/simulations/'+quote(job['id'], safe=''))
        return observe_s45_simulation_pair(project,jobs,details)
    if test_id=='S47':
        workflow=get_json(base,project,'/api/engineering/workflow?view=summary')
        context=workflow.get('context') or {}
        execution=context.get('agent_execution') or {}
        request=context.get('wizard_request') or {}
        if not execution.get('run_id') or execution.get('run_id')!=request.get('run_id'):
            raise ValueError('S47: persistenter Wizard-Lauf und zugehörige Auftragsrevision fehlen')
        return {'wizard_run_id':execution['run_id'],'request_revision':request.get('revision'),
                'source':'live-workflow-context'}
    if test_id=='S55':
        tools=get_json(base,project,'/api/engineering/tools').get('items') or []
        available=[item.get('id') for item in tools if item.get('status')=='available']
        if not available:raise ValueError('S55: keine verfügbaren registrierten Engineering-Tools beobachtet')
        missing_tool='tool-checker-s55-intentionally-unregistered'
        if missing_tool in {item.get('id') for item in tools}:
            raise ValueError('S55: kontrollierter Negativfall ist unerwartet registriert')
        try:
            get_json(base,project,'/api/engineering/tools/'+missing_tool)
        except HTTPError as error:
            if error.code!=404:raise
        else:
            raise ValueError('S55: Negativfall liefert unerwartet ein registriertes Tool')
        return {'available_tools':available,'missing_tool_id':missing_tool,
                'negative_lookup_status':404,'source':'live-tool-registry-and-negative-lookup'}
    if test_id=='S57':
        state=get_json(base,project,'/api/engineering/agent/conversation').get('data') or {}
        workload_id=state.get('active_engineering_workload_id')
        workload=(state.get('engineering_workloads') or {}).get(workload_id) or {}
        if not workload_id or not workload.get('goal'):
            raise ValueError('S57: offener Agent-Workload mit echter Engineering-Entscheidung fehlt')
        steps=workload.get('plan') or []
        questions=[item for item in (state.get('questions') or {}).values()
                   if isinstance(item,dict) and item.get('status')=='OPEN']
        if (workload.get('status')!='WAITING_FOR_ENGINEERING_DECISION'
                or not steps or not questions):
            raise ValueError('S57: persistierter Plan und Schrittzustand des Workloads fehlen')
        return {'workload_id':workload_id,'open_question_ids':[item.get('id') for item in questions],
                'completed_steps':[item.get('id') for item in steps if item.get('status')=='SUCCEEDED'],
                'pending_steps':[item.get('id') for item in steps if item.get('status')!='SUCCEEDED'],
                'source':'live-agent-conversation'}
    if test_id=='S58':
        capacity=get_json(base,project,'/api/engineering/capacity')
        findings=[item for item in capacity.get('findings') or [] if 'TIMING' in str(item.get('code') or '').upper()
                  and item.get('severity') in ('ERROR','BLOCKER','REVIEW')]
        if not findings:
            raise ValueError('S58: kontrollierter Timing-Fehlschlag ist in der aktuellen Berechnung nicht belegt')
        fixture_path=step.get('fixture_path')
        if not fixture_path or not Path(fixture_path).is_file():
            raise ValueError('S58: gebundene Repair-Strategie und freigegebener Umfang fehlen')
        fixture=read(Path(fixture_path))
        if not fixture.get('allowed_repair_scope'):
            raise ValueError('S58: zulässiger Repair-Umfang in der Fixture nicht belegt')
        return {'timing_finding_codes':[item['code'] for item in findings],
                'allowed_repair_scope':fixture['allowed_repair_scope'],'source':'live-capacity-result'}
    return None

def check_baseline(case, step, workflow, inventory, fixture=None, base=None):
    """Validate the registered starting state; never treat an empty model as complete."""
    wizard=step['adapter']=='complete-master-real-wizard'
    observation=None
    if wizard:
        if set(inventory)!=set(INVENTORY_RESOURCES):
            raise ValueError('Kanonisches Inventar unvollständig beobachtet')
        for resource, result in inventory.items():
            if not isinstance(result,dict) or not isinstance(result.get('items'),list) or type(result.get('count')) is not int:
                raise ValueError('Kanonisches Inventar nicht lesbar: '+resource)
            if result['count'] or result['items']:
                raise ValueError('Wizard benötigt ein leeres Testprojekt; vorhandenes Inventar: '+resource)
        checks=workflow.get('artifact_checks',{})
        for name in ('engineering_model','network_editor'):
            artifact=checks.get(name,{})
            if artifact.get('status')!='EMPTY' or any(artifact.get('counts',{}).values()):
                raise ValueError('Wizard benötigt leeren kanonischen Ausgangszustand: '+name)
        known_preconditions={'Isoliertes leeres Testprojekt auf geprüftem Build'}
        known_context={'Kanonisches Inventar und Modellrevision vor Ausführung'}
    elif case.get('test_id','').startswith('EA-'):
        if case['test_id'] in ('EA-04','EA-05'):
            if any(result.get('count',0) or result.get('items') for result in inventory.values()):
                raise ValueError(case['test_id']+': Adapter benötigt ein leeres Projekt für seinen eigenen Ausgangsmodell-Aufbau')
        elif fixture is None:
            raise ValueError('EA-Fall benötigt eine gebundene, beobachtbare Ausgangsfixture')
        elif not any(result.get('count',0) for result in inventory.values()):
            raise ValueError('EA-Ausgangsmodell ist leer; Fixture im isolierten Testprojekt herstellen')
        known_preconditions={'Isoliertes autorisiertes Testprojekt vorhanden',
                             'Browser, Assistant-Service, MCP-Registry und Core wirklich erreichbar',
                             'Projektkontext und Berechtigungen beobachtet'}
        known_context={'Canonical project model and revision'}
        test_id=case['test_id']
        if test_id=='EA-02':
            state=get_json(base,step['project_id'],'/api/engineering/agent/conversation').get('data',{})
            workload=state.get('engineering_workloads',{}).get(state.get('active_engineering_workload_id'),{})
            findings=workload.get('recipient_repair',{}).get('findings',[])
            if len(findings)!=1 or findings[0].get('signal_id')!=fixture['known_signal_id'] or not workload.get('recipient_repair',{}).get('proposal_id'):
                raise ValueError('EA-02: genau ein aktives Finding und autorisierter Korrekturvorschlag nicht live belegt')
            known_preconditions.add('Genau ein aktives Finding mit Evidence und autorisierter Modellkorrektur im selben Workload')
        elif test_id=='EA-03':
            state=get_json(base,step['project_id'],'/api/engineering/agent/conversation').get('data',{})
            if not state.get('engineering_workloads') and not state.get('conversation'):
                raise ValueError('EA-03: vorherige zyklische Abfrage im selben Projekt nicht live belegt')
            known_preconditions.add('Vorherige zyklische Abfrage im selben Kontext vorhanden')
        elif test_id=='EA-09-NO-CAPABILITY':
            if fixture['max_channels']!=1 or fixture.get('existing_channel_index') is None or not fixture.get('existing_interface_id'):
                raise ValueError('EA-09: erschöpfte CAN-FD-Kapazität in Fixture nicht belegt')
            hardware=next((item for item in inventory['hardware-nodes']['items'] if item.get('id')==fixture['hardware_id']),None)
            interface=next((item for item in inventory['hardware-interfaces']['items'] if item.get('id')==fixture['existing_interface_id']),None)
            controllers=((hardware or {}).get('hardware_information') or {}).get('communication_controllers',[])
            controller=next((item for item in controllers if item.get('id')==fixture['controller_id']),None)
            if (not controller or controller.get('technology')!='CAN_FD' or controller.get('max_channels')!=1
                    or controller.get('active_channels')!=[fixture['existing_channel_index']]
                    or not interface or interface.get('hardware_node_id')!=fixture['hardware_id']
                    or interface.get('controller_ref')!=fixture['controller_id']
                    or interface.get('channel_index')!=fixture['existing_channel_index']):
                raise ValueError('EA-09: erschöpfte CAN-FD-Kapazität im aktuellen kanonischen Modell nicht belegt')
            known_preconditions.add('Hardware besitzt nachweislich keinen zweiten freien CAN-FD-Kanal')
        elif test_id=='EA-11':
            if not fixture.get('missing_fields'):
                raise ValueError('EA-11: offene Zyklus-/Triggerentscheidung fehlt im Modellbeleg')
            known_preconditions.add('Modell und Policy lassen eine fachlich notwendige Zyklus-/Triggerentscheidung offen')
    else:
        if (workflow.get('artifact_checks',{}).get('engineering_model') or {}).get('complete') is not True:
            raise ValueError('Wiederverwendetes Testprojekt '+step['project_id']+' besitzt kein vollständiges kanonisches Ausgangsmodell; zuerst zugehörigen Wizard-Fall erfolgreich ausführen')
        known_preconditions={'Isolierter Teststack des veröffentlichten Images'}
        known_context={'Modellrevision und szenariospezifische Ausgangsdaten prüfen'}
        if case['test_id']=='S41':
            registry=observe_s41_registry(step['project_id'],
                get_json(base,step['project_id'],'/api/engineering/tools'),
                get_json(base,step['project_id'],'/api/engineering/agent/capabilities'))
            observation={'registry':registry,'model_revision':workflow['versions'],
                         'actor':'TOOL_CHECKER_AUTOMATED_E2E','source':'live-project-workflow-and-capability-registry'}
            known_preconditions.update(case['preconditions'])
            known_context.update(case['required_model_context'])
        elif case['test_id'] in {'S43','S44','S45','S47','S55','S57','S58'}:
            observation=check_special_reuse(case,step,base)
            known_preconditions.update(case['preconditions'])
            known_context.update(case['required_model_context'])
    unknown=[name for name in case['preconditions'] if name not in known_preconditions]+[name for name in case['required_model_context'] if name not in known_context]
    if unknown: raise ValueError('Fallbezogene Vorprüfung noch nicht angebunden: '+'; '.join(unknown))
    return observation

def collect(request, observe_capabilities=None):
    case=request['case']; project=Path(request['project']); directory=Path(request['evidence_directory'])
    cfg=read(Path(request['state'])/'config.json')
    steps=case.get('execution_plan',[])
    allowed=('complete-master-real-wizard','complete-master-reuse','complete-master-reuse-readonly')
    ea=case['test_id'] in EA_FIXTURE_KEYS and len(steps)==1 and steps[0].get('adapter','').startswith('complete-master-ea')
    if len(steps)!=1 or (steps[0].get('adapter') not in allowed and not ea):
        raise ValueError('Für '+case['test_id']+' fehlt eine geprüfte fallbezogene automatische Vorprüfung; registrierten Projektadapter ergänzen.')
    step=steps[0]; adapter=cfg.get('adapters',{}).get(step['adapter'],{})
    fixture=None
    if ea and EA_FIXTURE_KEYS[case['test_id']]:
        fixture_path=Path(step.get('fixture_path','')).resolve()
        if not fixture_path.is_relative_to(project/'.tool-checker/runs') or not fixture_path.is_file():
            raise ValueError('EA-Ausgangsfixture fehlt oder liegt außerhalb der registrierten Testläufe: '+str(fixture_path))
        fixture=read(fixture_path)
        if fixture.get('project_id')!=step.get('project_id') or fixture.get('base_url','').rstrip('/')!=step.get('base_url','').rstrip('/'):
            raise ValueError('EA-Fixture passt nicht zum registrierten Projekt/Stack')
        missing=[key for key in EA_FIXTURE_KEYS[case['test_id']]
                 if key not in fixture or fixture[key] is None or fixture[key]=='' or fixture[key]==[] or fixture[key]=={}]
        if missing: raise ValueError('EA-Fixture unvollständig: '+', '.join(missing))
        if Path(fixture.get('receipt',fixture.get('runtime_receipt',''))).resolve()!=Path(step.get('runtime_receipt','')).resolve():
            raise ValueError('EA-Fixture und Plan verwenden verschiedene Runtime-Belege')
    argv=adapter.get('argv',[])
    if not argv: raise ValueError('Ausführungsadapter nicht registriert: '+step['adapter'])
    for i,arg in enumerate(argv):
        if not isinstance(arg,str): raise ValueError('Ungültige Adapterargumente')
        if i==0 and not (Path(arg).is_file() or shutil.which(arg)):
            raise ValueError('Adapterprogramm fehlt: '+arg)
        if i>0 and Path(arg).suffix in ('.py','.mjs','.js','.ps1') and '{' not in arg and not (project/arg).is_file():
            raise ValueError('Registrierte Adapterdatei fehlt: '+str(project/arg)+'; Archivierung/Pfadbindung korrigieren.')
    receipt_path=Path(step.get('runtime_receipt',''))
    if not receipt_path.is_file(): raise ValueError('Beleg der isolierten Testumgebung fehlt: '+str(receipt_path))
    receipt=read(receipt_path); base=step.get('base_url','').rstrip('/'); parsed=urlsplit(base)
    if case['test_id']=='EA-05' and receipt.get('development_only') is not True:
        raise ValueError('EA-05-Fixture-Adapter verlangt einen isolierten Development-Teststack')
    if fixture is not None and fixture.get('runtime_build')!=receipt.get('release'):
        raise ValueError('EA-Fixture wurde auf anderem Build vorbereitet')
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.port in (None,13500) or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Keine registrierte isolierte lokale Testadresse: '+base)
    if receipt.get('status')!='PREPARED' or receipt.get('base_url','').rstrip('/')!=base:
        raise ValueError('Testadresse passt nicht zum PREPARED-Runtime-Beleg')
    app=receipt.get('containers',{}).get('app',''); db=receipt.get('containers',{}).get('db','')
    if not app.startswith('nis-e2e-app-') or not db.startswith('nis-e2e-db-'):
        raise ValueError('Isolierte NIS-Testcontainer nicht belegt')
    docker=shutil.which('docker')
    if not docker:
        candidate=Path.home()/'AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
        if candidate.is_file(): docker=str(candidate)
    if not docker: raise ValueError('Docker für Prüfung der Testcontainer nicht erreichbar')
    observations=[]
    for name in (app,db):
        command=[docker,'inspect','--format','{{json .State.Running}}|{{.Image}}|{{json .NetworkSettings.Ports}}',name]
        result=subprocess.run(command,capture_output=True,text=True,timeout=15)
        if result.returncode: raise ValueError('Isolierter Testcontainer fehlt/nicht erreichbar: '+name)
        running,image,ports=result.stdout.strip().split('|',2)
        if running!='true': raise ValueError('Isolierter Testcontainer ist gestoppt: '+name)
        if name==app:
            if image!=receipt.get('image_id'): raise ValueError('Laufendes Testimage stimmt nicht mit Runtime-Beleg überein')
            bindings=[v for values in (json.loads(ports) or {}).values() for v in (values or [])]
            if not any(v.get('HostPort')==str(parsed.port) and v.get('HostIp') in ('127.0.0.1','0.0.0.0') for v in bindings):
                raise ValueError('Testadresse ist nicht an den verifizierten Testcontainer gebunden')
        observations.append({'container':name,'running':True,'image':image})
    project_id=step.get('project_id')
    if not isinstance(project_id,str) or not project_id: raise ValueError('Testprojekt-ID fehlt im registrierten Plan')
    ready=get_json(base,project_id,'/api/ready')
    workflow=get_json(base,project_id,'/api/engineering/workflow?view=summary')
    write(directory/'runtime.json',{'containers':observations,'ready':ready,'base_url':base,'project_id':project_id})
    write(directory/'workflow.json',workflow)
    if not workflow.get('versions'): raise ValueError('Keine beobachtete Modellrevision für '+project_id)
    inventory={}
    if step['adapter']=='complete-master-real-wizard' or ea:
        for resource in INVENTORY_RESOURCES:
            inventory[resource]=get_json(base,project_id,'/api/engineering/'+resource+'?limit=1000')
        write(directory/'inventory.json',inventory)
    case_observation=check_baseline(case,step,workflow,inventory,fixture,base)
    if case_observation is not None:write(directory/'case-observation.json',case_observation)
    manifest=read(Path(request['state'])/'tasks'/request['task_id']/'manifest.json')
    available={'tools':['NIS HTTP API'],'skills':['tool-checker'],'views':[]}
    capability_proof=None
    if observe_capabilities is not None:
        if not callable(observe_capabilities): raise ValueError('Capability observer must be reviewed local code, not request data')
        observed=observe_capabilities(request,manifest)
        if not isinstance(observed,dict) or not observed.get('evidence'): raise ValueError('Observed capability evidence missing')
        capability_proof=observed
        for key in available:
            values=observed.get(key,[])
            if not isinstance(values,list) or any(not isinstance(v,str) for v in values): raise ValueError('Invalid observed capability list')
            available[key]=list(dict.fromkeys(available[key]+values))
        # Browser observation may update only view context. Capture the actual current baseline afterward.
        workflow=get_json(base,project_id,'/api/engineering/workflow?view=summary')
        write(directory/'workflow.json',workflow)
        if not workflow.get('versions'): raise ValueError('Modellrevision nach Browserprüfung fehlt')
        if step['adapter']=='complete-master-real-wizard' or ea:
            inventory={resource:get_json(base,project_id,'/api/engineering/'+resource+'?limit=1000') for resource in INVENTORY_RESOURCES}
            write(directory/'inventory.json',inventory)
        case_observation=check_baseline(case,step,workflow,inventory,fixture,base)
        if case_observation is not None:write(directory/'case-observation.json',case_observation)
    for key,values in available.items():
        missing=set(case.get('required_'+key,[])+manifest.get('required_'+key,[]))-set(values)
        if missing: raise ValueError('Verfügbarkeit nicht nachgewiesen: '+', '.join(sorted(missing)))
    if case.get('browser_required') and not capability_proof: raise ValueError('Frische Browser-Vorprüfung benötigt einen registrierten Browseradapter')
    baseline=directory/'baseline.json'; write(baseline,{'model_revision':workflow['versions'],'workflow':workflow,'project_id':project_id,'base_url':base,'checked_at':now()})
    evidence={'runtime':str(directory/'runtime.json'),'model':str(directory/'workflow.json'),'request':str(directory/'request.json')}
    if case_observation is not None:evidence['case_observation']=str(directory/'case-observation.json')
    proof={'source_hash':request['source_hash'],'contract_hash':request['contract_hash'],'project_path':str(project),'checked_at':now(),
           'isolated_scope':{'project_id':project_id,'base_url':base,'containers':observations}}
    for key in ('dependencies','application','project','permissions','test_data'):
        proof[key]={'status':'PASSED','evidence':evidence}
    for key in ('preconditions','required_model_context'):
        proof[key]=[{'name':name,'status':'PASSED','evidence':evidence} for name in case[key]]
    for key,values in available.items(): proof['available_'+key]=values
    if capability_proof:
        proof['capability_provider']=capability_proof
        proof['browser']={'observed_working':True,'provider':capability_proof.get('provider'),'evidence':capability_proof['evidence']}
    path=directory/'preflight.json';write(path,proof)
    return {case['test_id']:{'preflight':str(path),'baseline':str(baseline)}}



def main():
    parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    try: write(args.output,collect(read(args.request)));return 0
    except Exception as error:
        write(args.output,{'status':'BLOCKED','reason':str(error)})
        print(str(error));return 2

if __name__=='__main__': raise SystemExit(main())
