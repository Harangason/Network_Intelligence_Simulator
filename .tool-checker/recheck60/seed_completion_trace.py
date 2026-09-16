import json
from pathlib import Path
import industry60_fixtures
industry60_fixtures.BASE = 'http://127.0.0.1:56335'
from industry60_fixtures import api
OUT=Path('.tool-checker/evidence/industry60-completion/canonical-trace');OUT.mkdir(parents=True,exist_ok=True)
SOURCE=Path('.tool-checker/evidence/industry60-recheck/trace');P='nis-e2e-industry60-canonical-trace-ce66';mapping={};created={}
cfg=json.loads((SOURCE/'golden-config.json').read_text())
assert not api(P,'hardware-nodes')['items']
for old in cfg['engineering_model']['nodes']:
    h=api(P,'hardware-nodes',{'name':'CentralGateway' if old['id']=='gateway' else old['name'],'device_type':old['device_type']});mapping[old['id']]=h['id'];created[old['id']]=h
    f=api(P,'functions',{'name':old['name']+'Function','hardware_node_id':h['id']});created[old['id']+'-function']=f
for old in cfg['engineering_model']['interfaces']:
    i=api(P,'interfaces',{'name':old['id'],'function_id':created[old['hardware_node_id']+'-function']['id'],'interface_type':old['interface_type']});mapping[old['id']]=i['id']
    tech=old['interface_type'];h=api(P,'hardware-interfaces',{'name':old['id']+'Physical','hardware_node_id':mapping[old['hardware_node_id']],'technology':tech,'physical_port_ref':i['id'],'network_ref':'input-bus' if tech=='CAN_FD' else 'output-bus','bitrate':500000 if tech=='CAN_FD' else 100000000,'data_bitrate':2000000 if tech=='CAN_FD' else None});mapping[old['id']+'-hw']=h['id']
m=api(P,'messages',{'name':'TemperatureMessage','interface_id':mapping['source-if'],'hardware_interface_id':mapping['source-if-hw'],'message_id_hex':'0x120','cycle_ms':20,'dlc':2,'direction':'tx'});mapping['message']=m['id']
s=api(P,'signals',{'name':'Temperature','message_id':m['id'],'start_bit':0,'length_bits':16,'byte_order':'little_endian','data_type':'unsigned','factor':.1,'offset_value':-40,'min_value':-40,'max_value':215,'unit':'degC'});mapping['temperature']=s['id']
def remap(v):
    if isinstance(v,str):return mapping.get(v,v)
    if isinstance(v,list):return [remap(x) for x in v]
    if isinstance(v,dict):return {k:remap(x) for k,x in v.items()}
    return v
route=remap(cfg['engineering_model']['routes'][0]);route.pop('id');route.pop('approval_state');r=api(P,'routing',route);mapping['canonical-route']=r['id']
(OUT/'canonical-map.json').write_text(json.dumps({'mapping':mapping,'created':created,'route':r},indent=2),encoding='utf8')
for label in ['golden','fault']:
    original=json.loads((SOURCE/(label+'-config.json')).read_text());result=remap(original)
    (OUT/(label+'-canonical-config.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
print('Canonical baseline created; route approval and snapshot are not implied.')
