"""Create a disposable CAN-FD fixture on an explicitly selected test backend."""
import os
import json, urllib.request, urllib.error, uuid
from pathlib import Path
project='network-project-flow-'+uuid.uuid4().hex[:8]
base=os.environ['SIMULATOR_TEST_BACKEND_URL'].rstrip('/')+'/api/engineering'
def api(method,path,data=None):
    req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json','X-Project-ID':project},method=method)
    try:
        with urllib.request.urlopen(req,timeout=60) as res:return json.load(res)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{method} {path}: {e.code} {e.read().decode()}')
nodes=[]
for name in ['Source','Target']:
    node=api('POST','/hardware-nodes',{'name':name,'device_type':'ECU'})
    func=api('POST','/functions',{'name':name+'Function','hardware_node_id':node['id']})
    physical=api('POST','/hardware-interfaces',{'name':name+'CAN','hardware_node_id':node['id'],'technology':'CAN_FD','bitrate':500000,'data_bitrate':2000000,'network_ref':'audit-can'})
    port=api('POST','/interfaces',{'name':name+'Interface','function_id':func['id'],'hardware_node_id':node['id'],'interface_type':'CAN_FD','configuration':{'network_id':'audit-can','bitrate':500000,'data_bitrate':2000000}})
    nodes.append({'id':name.lower(),'name':name,'kind':'ecu','engineeringId':node['id'],'ports':[{'id':name.lower()+'-p','name':'CAN FD','bus':'can_fd','engineeringId':port['id']}]})
    if name=='Source':
        msg=api('POST','/messages',{'name':'Status','interface_id':port['id'],'hardware_interface_id':physical['id'],'message_id_hex':'0x100','direction':'tx','cycle_ms':20,'dlc':8})
        sig=api('POST','/signals',{'name':'Temperature','message_id':msg['id'],'length_bits':16,'start_bit':0,'byte_order':'little_endian','data_type':'uint16','factor':1,'offset_value':0,'min_value':0,'max_value':100,'unit':'C'})
top={'nodes':nodes,'edges':[{'id':'link','source':'source','sourcePort':'source-p','target':'target','targetPort':'target-p','bus':'can_fd'}]}
api('PATCH','/workflow/parameters',{'parameters':{'industry':'automotive','technology':'can_fd','bitrate':500000,'data_bitrate':2000000,'cycle_ms':20,'duration_s':0.1,'payload_bytes':8,'queue_size':256,'warning_threshold':70,'critical_threshold':85,'overload_threshold':100,'formats':['universal-jsonl'],'max_events':100}})
state=api('PUT','/workflow/topology',{'topology':top})
print('PROJECT',project,'STATUSES',state['statuses'],flush=True)
routes=api('GET','/routing')['items'];print('ROUTES',len(routes),flush=True)
for route in routes:
    api('PATCH','/routing/'+route['id'],{'payload':{'message_id':msg['id'],'signal_ids':[sig['id']]}})
    result=api('POST','/routing/'+route['id']+'/validate',{'actor':'audit-reviewer'})
    print('VALIDATION',json.dumps(result)[:3500],flush=True)
api('POST','/routing/approve-all-valid',{'actor':'audit-reviewer'})
state=api('GET','/workflow')
api('PUT','/workflow/topology',{'topology':state['topology']})
cap=api('POST','/capacity/calculate',{});print('CAPACITY',cap.get('status'),flush=True)
pre=api('POST','/preflight',{});print('PREFLIGHT',json.dumps(pre),flush=True)
output = Path(__file__).resolve().parents[2] / 'test-output' / 'audit-flow-state.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({'project':project,'state':api('GET','/workflow'),'preflight':pre}),encoding='utf-8')
