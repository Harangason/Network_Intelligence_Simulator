import json,time,uuid
from pathlib import Path
from industry50_fixtures import api
from industry50_adapter import request
p='nis-e2e-industry50-s28';folder=Path('.tool-checker/evidence/industry50/S28');cfg=json.loads((folder/'job-request.json').read_text(encoding='utf8'))['config'];mapping={};created={}
for old in cfg['engineering_model']['nodes']:
 x=api(p,'hardware-nodes',{'name':'CentralGateway' if old['id']=='gateway' else old['name'],'device_type':'Gateway' if old['id']=='gateway' else 'ECU'});mapping[old['id']]=x['id'];created[old['id']]=x
 f=api(p,'functions',{'name':old['name']+'Function','hardware_node_id':x['id']});created[old['id']+'-function']=f
for old in cfg['engineering_model']['interfaces']:
 x=api(p,'interfaces',{'name':old['id'],'function_id':created[old['hardware_node_id']+'-function']['id'],'interface_type':old['interface_type']});mapping[old['id']]=x['id']
 tech=old['interface_type'];h=api(p,'hardware-interfaces',{'name':old['id']+'Physical','hardware_node_id':mapping[old['hardware_node_id']],'technology':tech,'physical_port_ref':x['id'],'network_ref':'input-bus' if tech=='CAN_FD' else 'output-bus','bitrate':500000 if tech=='CAN_FD' else 19200});mapping[old['id']+'-hw']=h['id']
m=api(p,'messages',{'name':'TemperatureMessage','interface_id':mapping['source-if'],'hardware_interface_id':mapping['source-if-hw'],'message_id_hex':'0x120','cycle_ms':20,'dlc':2,'direction':'tx'});mapping['message']=m['id'];s=api(p,'signals',{'name':'Temperature','message_id':m['id'],'start_bit':0,'length_bits':16,'byte_order':'little_endian','factor':0.1,'offset_value':-40,'min_value':-40,'max_value':215,'unit':'degC'});mapping['temperature']=s['id']
def remap(x):
 if isinstance(x,str):return mapping.get(x,x)
 if isinstance(x,list):return [remap(i) for i in x]
 if isinstance(x,dict):return {k:remap(v) for k,v in x.items()}
 return x
cfg=remap(cfg);cfg['scenario']['faults'][0]['target']['id']=mapping['gateway'];(folder/'canonical-fixture-map.json').write_text(json.dumps(mapping,indent=2),encoding='utf8')
code,body=request('http://127.0.0.1:60023',p,'/api/simulations',{'project_id':p,'config':cfg});(folder/'canonical-job-submitted.json').write_text(body,encoding='utf8');assert code==202,(code,body);job=json.loads(body);print(job['id'],flush=True)
for _ in range(60):
 code,body=request('http://127.0.0.1:60023',p,'/api/simulations/'+job['id']);cur=json.loads(body)
 if cur['status'] in ['completed','failed','canceled']:
  (folder/'canonical-job-result.json').write_text(body,encoding='utf8');print(cur['status'],cur.get('error'));break
 time.sleep(1)
