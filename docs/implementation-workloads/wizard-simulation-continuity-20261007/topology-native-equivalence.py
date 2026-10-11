import hashlib,importlib.util,json,sys,time
from pathlib import Path

out=Path(__file__).parent.resolve(); root=out.parents[2]
sys.path.insert(0,str(root))
from backend.nis.agent.tools import validation as current
from backend.nis.agent.tools.model import SECTIONS
from backend.nis.communication.technologies.lin import timing as current_lin
from backend.nis.engineering.capacity.service import simulation_parameters_for_protocol

def baseline(name,file):
    spec=importlib.util.spec_from_file_location(name,out/file)
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module)
    return module
previous=baseline('pre_topology_validation','pre-topology-validation.py')
previous_lin=baseline('backend.nis.communication.technologies.lin.pre_topology_timing','pre-topology-lin-timing.py')
data=json.loads((out/'topology-native-review-input.json').read_text(encoding='utf-8'))
rows={kind:data['model'][section] for section,kind in SECTIONS.items()}
current.objects=previous.objects=lambda kind:rows[kind]
state=data['workflow']; changes=data['proposal']['changes']
for name in ('review_simulation_capacity','review_parameter_findings','review_bus_rate_plans'):
    started=time.perf_counter(); expected=getattr(previous,name)(state,changes)
    before=time.perf_counter()-started
    started=time.perf_counter(); result=getattr(current,name)(state,changes)
    assert result==expected,name
    print(json.dumps({'function':name,'identical_results':True,'rows':len(result),
        'baseline_s':before,'current_s':time.perf_counter()-started,
        'sha256':hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()}),flush=True)

port=next(row for row in rows['HardwareNetworkInterface'] if str(row['technology']).lower()=='lin')
parameters=simulation_parameters_for_protocol('lin',state['parameters'],port,port.get('network_ref'),state['parameters'])
compared=0
for values in (parameters,{**parameters,'lin_bitrate_bps':9600,'bitrate':9600},
               {**parameters,'_simulation_assumption_fields':[]}):
    assert current_lin.prepare_simulation_parameters(values)==previous_lin.prepare_simulation_parameters(values)
    for payload in range(10):
        assert current_lin.planning_frame_parameters(payload,values)==previous_lin.planning_frame_parameters(payload,values)
        assert current_lin.estimate_planning_frame('lin',payload,values)==previous_lin.estimate_planning_frame('lin',payload,values)
        compared+=1
print(json.dumps({'native_lin_scenarios':compared,'identical_derivations':True}),flush=True)
