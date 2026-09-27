"""Read-only NIS preflight for registered isolated HTTP reuse cases.
Never starts a container, creates a project, or fabricates semantic observations.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler, Request
from tool_check import read, write, now

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError('Redirect bei lokaler Vorprüfung abgewiesen')

INVENTORY_RESOURCES=('hardware-nodes','hardware-interfaces','functions','interfaces','messages','signals')

def get_json(base, project, path):
    with build_opener(ProxyHandler({}), NoRedirect()).open(Request(base+path, headers={'X-Project-ID':project}),timeout=10) as response:
        return json.load(response)

def check_baseline(case, step, workflow, inventory):
    """Validate the registered starting state; never treat an empty model as complete."""
    wizard=step['adapter']=='complete-master-real-wizard'
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
    else:
        if (workflow.get('artifact_checks',{}).get('engineering_model') or {}).get('complete') is not True:
            raise ValueError('Wiederverwendetes Testprojekt '+step['project_id']+' besitzt kein vollständiges kanonisches Ausgangsmodell; zuerst zugehörigen Wizard-Fall erfolgreich ausführen')
        known_preconditions={'Isolierter Teststack des veröffentlichten Images'}
        known_context={'Modellrevision und szenariospezifische Ausgangsdaten prüfen'}
    unknown=[name for name in case['preconditions'] if name not in known_preconditions]+[name for name in case['required_model_context'] if name not in known_context]
    if unknown: raise ValueError('Fallbezogene Vorprüfung noch nicht angebunden: '+'; '.join(unknown))

def collect(request, observe_capabilities=None):
    case=request['case']; project=Path(request['project']); directory=Path(request['evidence_directory'])
    cfg=read(Path(request['state'])/'config.json')
    steps=case.get('execution_plan',[])
    if len(steps)!=1 or steps[0].get('adapter') not in ('complete-master-real-wizard','complete-master-reuse','complete-master-reuse-readonly'):
        raise ValueError('Für '+case['test_id']+' fehlt eine geprüfte fallbezogene automatische Vorprüfung; registrierten Projektadapter ergänzen.')
    step=steps[0]; adapter=cfg.get('adapters',{}).get(step['adapter'],{})
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
    if step['adapter']=='complete-master-real-wizard':
        for resource in INVENTORY_RESOURCES:
            inventory[resource]=get_json(base,project_id,'/api/engineering/'+resource+'?limit=1000')
        write(directory/'inventory.json',inventory)
    check_baseline(case,step,workflow,inventory)
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
        if step['adapter']=='complete-master-real-wizard':
            inventory={resource:get_json(base,project_id,'/api/engineering/'+resource+'?limit=1000') for resource in INVENTORY_RESOURCES}
            write(directory/'inventory.json',inventory)
        check_baseline(case,step,workflow,inventory)
    for key,values in available.items():
        missing=set(case.get('required_'+key,[])+manifest.get('required_'+key,[]))-set(values)
        if missing: raise ValueError('Verfügbarkeit nicht nachgewiesen: '+', '.join(sorted(missing)))
    if case.get('browser_required') and not capability_proof: raise ValueError('Frische Browser-Vorprüfung benötigt einen registrierten Browseradapter')
    baseline=directory/'baseline.json'; write(baseline,{'model_revision':workflow['versions'],'workflow':workflow,'project_id':project_id,'base_url':base,'checked_at':now()})
    evidence={'runtime':str(directory/'runtime.json'),'model':str(directory/'workflow.json'),'request':str(directory/'request.json')}
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
