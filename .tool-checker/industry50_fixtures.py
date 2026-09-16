"""Explicit source fixtures through public API; never generated test results."""
import json, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:60023'
def api(project,path,data=None,method=None):
    assert project.startswith('nis-e2e-industry50-')
    req=urllib.request.Request(BASE+'/api/engineering/'+path,
        data=None if data is None else json.dumps(data).encode(),method=method,
        headers={'X-Project-ID':project,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e: raise RuntimeError(f'{path} {e.code} {e.read().decode()}')
def seed(project):
    assert not api(project,'hardware-nodes')['items'], 'Do not replay fixture over existing objects'
    src=api(project,'hardware-nodes',{'name':'ChassisController','device_type':'ECU'})
    dst=api(project,'hardware-nodes',{'name':'ADAS_Controller','device_type':'ECU'})
    sf=api(project,'functions',{'name':'ParkAssist','hardware_node_id':src['id']})
    df=api(project,'functions',{'name':'DriverAssistance','hardware_node_id':dst['id']})
    si=api(project,'interfaces',{'name':'ParkAssistOutput','function_id':sf['id'],'interface_type':'CAN_FD'})
    di=api(project,'interfaces',{'name':'DriverAssistanceEthernet','function_id':df['id'],'interface_type':'Ethernet'})
    for h in [src,dst]:
        for kind,resource in [
          ('CommunicationCapability',{'id':'cap-'+h['id'],'hardware_node_ref':h['id'],'technology':'CAN_FD','supported':True,'controller_count':1,'max_channels':1,'max_ports':1,'supported_bitrates':[500000]}),
          ('CommunicationController',{'id':'controller-'+h['id'],'hardware_node_ref':h['id'],'technology':'CAN_FD','max_channels':1})]:
            rev=api(project,'communication-resources')['model_revision']
            api(project,'communication-resources/'+kind,{'resource':resource,'expected_revision':rev},'PUT')
    sp=api(project,'hardware-interfaces',{'name':'CAN_FD_1','hardware_node_id':src['id'],'technology':'CAN_FD','controller_ref':'controller-'+src['id'],
        'channel_index':1,'physical_port_ref':'connector-'+src['id'],'network_ref':'chassis-can','bitrate':500000,'data_bitrate':2000000})
    ep=api(project,'hardware-interfaces',{'name':'ETH_1','hardware_node_id':dst['id'],'technology':'Ethernet','network_ref':'adas-ethernet','bitrate':1000000000})
    message=api(project,'messages',{'name':'ParkAssistStatus','interface_id':si['id'],'hardware_interface_id':sp['id'],'message_id_hex':'0x120','cycle_ms':100,'dlc':1,'direction':'tx',
        'configuration':{'maximum_latency_ms':20,'maximum_jitter_ms':5,'communication_contract':{'scope':'FUNCTION_OUTPUT','consumer_refs':[df['id']],
        'transmission':{'mode':'CYCLIC','period_ms':100,'functional_requirements':{'confirmed':True,'maximum_event_to_response_ms':250,'sampling_delay_ms':0,'actuation_delay_ms':0}}}}})
    signal=api(project,'signals',{'name':'ParkAssistActive','message_id':message['id'],'start_bit':0,'length_bits':1,'byte_order':'little_endian','data_type':'boolean',
        'factor':1,'offset_value':0,'min_value':0,'max_value':1,'semantic':{'semantic_type':'BOOLEAN'},'configuration':{'semantic_type':'BOOLEAN'}})
    api(project,'workflow/parameters',{'industry':'automotive','technology':'can_fd','formats':['universal-jsonl'],'bitrate':500000,'data_bitrate':2000000,
        'cycle_ms':100,'payload_bytes':1,'queue_size':256,'warning_threshold':60,'critical_threshold':75,'overload_threshold':90,'target_bus_load_percent':60,
        'networks':[{'id':'chassis-can','name':'Chassis_CAN','technology':'CAN_FD','bitrate':500000,'data_bitrate':2000000},
                    {'id':'adas-ethernet','name':'ADAS_ETHERNET','technology':'Ethernet','bitrate':1000000000}]},'PATCH')
    data={'project':project,'src':src,'dst':dst,'sf':sf,'df':df,'si':si,'di':di,'sp':sp,'ep':ep,'message':message,'signal':signal,
          'fixture_origin':'S23/S24 source baseline + explicit 100ms/boolean/250ms test contract from existing canonical SQL fixture; not agent output'}
    folder=ROOT/'.tool-checker/evidence/industry50'/project.rsplit('-',1)[-1].upper();folder.mkdir(parents=True,exist_ok=True)
    (folder/'fixture.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    return data
if __name__=='__main__':
    import sys
    print(json.dumps(seed('nis-e2e-industry50-'+sys.argv[1].lower()),indent=2))
