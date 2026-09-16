import json
from pathlib import Path
from industry50_fixtures import api,seed,ROOT
p='nis-e2e-industry50-s26';d=seed(p)
for h in [d['src'],d['dst']]:
 for kind,r in [('CommunicationCapability',{'id':'cap-'+h['id'],'hardware_node_ref':h['id'],'technology':'CAN_FD','supported':True,'controller_count':1,'max_channels':2,'max_ports':2,'supported_bitrates':[500000]}),('CommunicationController',{'id':'controller-'+h['id'],'hardware_node_ref':h['id'],'technology':'CAN_FD','max_channels':2})]:
  api(p,'communication-resources/'+kind,{'resource':r,'expected_revision':api(p,'communication-resources')['model_revision']},'PUT')
api(p,'hardware-interfaces',{'name':'CAN_FD_2','hardware_node_id':d['src']['id'],'technology':'CAN_FD','controller_ref':'controller-'+d['src']['id'],'channel_index':2,'physical_port_ref':'connector-2','network_ref':'alternative-can','bitrate':500000,'data_bitrate':2000000})
state=api(p,'workflow');params=state['parameters'];params['networks'].append({'id':'alternative-can','name':'Alternative_CAN','technology':'CAN_FD','bitrate':500000,'data_bitrate':2000000});api(p,'workflow/parameters',params,'PATCH')
msg=api(p,'messages',{'name':'ParkAssistDiagnostics','interface_id':d['si']['id'],'hardware_interface_id':d['sp']['id'],'message_id_hex':'0x121','cycle_ms':100,'dlc':1,'direction':'tx','configuration':d['message']['configuration']})
api(p,'signals',{'name':'ParkAssistFault','message_id':msg['id'],'start_bit':0,'length_bits':1,'byte_order':'little_endian','data_type':'boolean','factor':1,'offset_value':0,'min_value':0,'max_value':1,'semantic':{'semantic_type':'BOOLEAN'},'configuration':{'semantic_type':'BOOLEAN'}})
(ROOT/'.tool-checker/evidence/industry50/S26/fixture-extension.json').write_text(json.dumps({'two_CAN_networks':params['networks'],'two_payloads':[d['message']['id'],msg['id']],'prompt_binding':'Existing function=ParkAssist; target function on ADAS_Controller=DriverAssistance; no choice auto-answered'},indent=2),encoding='utf8')
