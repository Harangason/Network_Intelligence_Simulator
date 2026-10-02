from pathlib import Path
from pprint import pformat
import runpy
data=runpy.run_path(str(Path(__file__).with_name('write-goose-review-spec.py')))
declarations,SOURCE,REVISION=(data[k] for k in ('declarations','SOURCE','REVISION'))
path=Path('backend/communication/technologies/catalog.py')
text=path.read_text(encoding='utf-8')
required=['bitrate_bps','goose_profile','goose_edition','goose_role','goose_binding_source','goose_scl_source','goose_device_source','goose_schedule_source']
constraints=[]
def rule(key,when=None,**kwargs): constraints.append({'when':when or {},'parameter':key,**kwargs})
lib={'goose_profile':'LIBIEC61850_1_6_L2'}
rule('goose_encoding',lib,allowed=['ASN1_BER'])
rule('goose_ethertype',allowed=[35000])
rule('eth_type_length',allowed=[35000])
rule('eth_frame_format',allowed=['ETHERTYPE'])
rule('eth_payload_layer',allowed=['MAC_CLIENT'])
rule('eth_vlan_tags',{'goose_vlan_tag':True},allowed=[1])
rule('eth_vlan_tags',{'goose_vlan_tag':False},allowed=[0])
rule('eth_tag_mode',{'goose_vlan_tag':False},allowed=['UNTAGGED'])
rule('goose_timestamp_bytes',lib,allowed=[8])
rule('goose_header_bytes',allowed=[8])
rule('goose_reserved1',lib,allowed=[0])
rule('goose_reserved2',lib,allowed=[0])
rule('goose_length_bytes',equal_sum=[{'parameter':'goose_header_bytes'},{'parameter':'goose_apdu_bytes'}])
rule('goose_length_bytes',maximum_parameter='mtu_bytes')
rule('payload_bytes',equal_parameter='goose_length_bytes')
rule('eth_client_bytes',equal_parameter='goose_length_bytes')
rule('goose_all_data_bytes',maximum_parameter='goose_apdu_bytes')
rule('goose_num_entries',equal_parameter='goose_actual_entries')
rule('goose_max_ms',minimum_parameter='goose_min_ms')
rule('goose_next_ms',maximum_parameter='goose_tal_ms')
rule('goose_tal_ms',lib,equal_sum=[{'parameter':'goose_tal_basis_ms','factor':3}])
rule('goose_sq_num',{**lib,'goose_phase':'STATE_CHANGE'},allowed=[0])
rule('goose_next_ms',{**lib,'goose_phase':'STABLE'},equal_parameter='goose_max_ms')
rule('goose_tal_basis_ms',{**lib,'goose_phase':'STABLE'},equal_parameter='goose_max_ms')
operational={'goose_accept_operational':True}
rule('goose_operating_mode',operational,allowed=['OPERATIONAL'])
rule('goose_test',operational,required=True,allowed=[False])
rule('goose_nds_com',operational,required=True,allowed=[False])
rule('goose_conf_rev',operational,required=True,equal_parameter='goose_expected_conf_rev')
rule('goose_expected_conf_rev',operational,required=True)
rule('goose_acceptance_source',operational,required=True)
sem=f'''TECHNOLOGY_SEMANTICS['goose'] = {{
    'rate_source_profile_id': 'ethernet',
    'rate_model': deepcopy(TECHNOLOGY_SEMANTICS['ethernet']['rate_model']),
    'required_parameters': {required!r}, 'native_parameter_prefixes':['eth_','goose_'],
    'mechanisms': {{'access':['EXPLICIT_IEEE8023_L2_MULTICAST_GOCB'],
                   'integrity':['BER_DATASET_REVISION_STATE_SEQUENCE_AND_ACTUAL_SECURITY_SEPARATE'],
                   'scope':['LAN_GOOSE_NOT_UDP_IP_MMS_OR_ROUTED_GOOSE']}},
    'parameter_constraints': deepcopy(TECHNOLOGY_SEMANTICS['ethernet']['parameter_constraints']) + {pformat(constraints,width=110,sort_dicts=False)}
}}

'''
text=text.replace("TECHNOLOGY_SEMANTICS['generic_serial'] =",sem+"TECHNOLOGY_SEMANTICS['generic_serial'] =",1)
proposal={'kind':'PHYSICAL_RATE_FROM_DECLARED_STACK','status':'REVIEW_REQUIRED','source':SOURCE,'source_revision':REVISION,
          'note':'GOOSE raw L2 uses explicit canonical IEEE802.3 PHY modes; no independent universal100Mbit/s or event4ms. Library-qualified default PCP4 and configured retransmission fallbacks are conditional proposals, not actual SCL/device evidence.'}
text=text.replace("    'generic_serial':",f"    'goose': {proposal!r},\n    'generic_serial':",1)
text=text.replace("'fsoe','generic_can','generic_serial'} else", "'fsoe','generic_can','generic_serial'} else",1)
text=text.replace('("goose", "GOOSE", "energy", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "goose"), 100_000_000, 1500, ("objects", "multicast", "pubsub", "redundancy", "time_sync", "safety", "qos"), True)',
 '("goose", "GOOSE", "generic_networking", "APPLICATION", "MESSAGE", ("DATA_OBJECT", "STATUS", "QUALITY"), "ethernet_port", ("ethernet", "goose"), None, None, ("objects", "multicast", "pubsub", "redundancy", "qos"), False)',1)
block=f'''    if technology_id == 'goose':
        source=REVIEW_RATE_PROPOSALS['goose']
        # Explicit composition of the reviewed raw IEEE802.3 transport and
        # GOOSE application schema; never an implicit foreign transport fallback.
        fields=_parameter_form_schema('ethernet',
            {{**technology,'id':'ethernet','default_stack':['ethernet']}},
            {{**rate_source,'id':'ethernet'}},review)
        for item in fields:
            if item['key'] in {{'qos_priority','vlan_id'}}:
                item.update(conditional_defaults=[{{'when':{{'goose_profile':'LIBIEC61850_1_6_L2','goose_vlan_tag':True}},
                    'value':4 if item['key']=='qos_priority' else 0}}],default_status='PROPOSED_CONDITIONAL')
            if item['key']=='payload_bytes':
                item['description']='Actual L2 GOOSE8-byte header plus full encoded APDU as MAC-client octets; allData/counts are separate. No8-byte default.'
        for key,kind,unit,options,minimum,maximum,meaning in {pformat(declarations,width=110)}:
            native=field(key,key.replace('goose_','').replace('_',' '),'communication','route',field_type=kind,
                unit=unit,options=options,minimum=minimum,maximum=maximum,description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['goose']['required_parameters'],integer=kind=='number',
                parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=source['source'],source_revision=source['source_revision'])
            if key in {{'goose_timestamp_bytes','goose_appid','goose_conf_rev','goose_expected_conf_rev','goose_st_num','goose_sq_num','goose_num_entries','goose_actual_entries','goose_reserved1','goose_reserved2'}}:
                native['schema_when']={{'goose_profile':'LIBIEC61850_1_6_L2'}}
            proposals={{'goose_encoding':'ASN1_BER','goose_ethertype':35000,'goose_timestamp_bytes':8,'goose_header_bytes':8,'goose_reserved1':0,'goose_reserved2':0}}
            fallback={{'goose_min_ms':500,'goose_max_ms':5000,'goose_event_repeats':2}}
            if key in proposals or key in fallback:
                when={{'goose_profile':'LIBIEC61850_1_6_L2'}}
                if key in fallback: when['goose_schedule_origin']='STACK_FALLBACK'
                native.update(conditional_defaults=[{{'when':when,'value':proposals.get(key,fallback.get(key))}}],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
'''
text=text.replace("    if technology_id == 'generic_serial':\n",block+"    if technology_id == 'generic_serial':\n",1)
# Preserve per-layer provenance rather than labelling Ethernet constraints as BER.
text=text.replace("{'source': REVIEW_RATE_PROPOSALS['dali']['source'],", "{'source': REVIEW_RATE_PROPOSALS['dali']['source'],",1)
needle="                       {'source': REVIEW_RATE_PROPOSALS[technology_id]['source'],"
provenance="""                       {'source':REVIEW_RATE_PROPOSALS['goose' if item['parameter'].startswith('goose_') else 'ethernet']['source'],
                        'source_revision':REVIEW_RATE_PROPOSALS['goose' if item['parameter'].startswith('goose_') else 'ethernet']['source_revision']}
                       if technology_id == 'goose' else
"""
text=text.replace(needle,provenance+needle,1)
path.write_text(text,encoding='utf-8')
print({'native_fields':len(declarations),'application_constraints':len(constraints)})
