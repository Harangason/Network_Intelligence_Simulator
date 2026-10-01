"""Apply individually declared H1 fields and explicit cross-field rules."""
from pathlib import Path
from pprint import pformat
import runpy
data=runpy.run_path(str(Path(__file__).with_name('write-foundation-h1-review-spec.py')))
declarations,removed,SOURCE,REVISION=(data[key] for key in ('declarations','removed','SOURCE','REVISION'))

path=Path('backend/communication/technologies/catalog.py')
text=path.read_text(encoding='utf-8')
required=['bitrate_bps','ff_profile','ff_configuration_source','ff_cff_source','ff_physical_source','ff_schedule_source']
constraints=[]
def rule(parameter, when=None, **kwargs):
    constraints.append({'when':when or {},'parameter':parameter,**kwargs})
dt={'ff_layout':'YOKOGAWA_FMS_DIAGRAM','ff_pdu':'DT'}
for key,value in [('ff_fms_pci_bytes',4),('ff_fas_pci_bytes',1),('ff_fcs_bytes',2)]:
    rule(key,dt,allowed=[value])
rule('ff_dl_pci_bytes',dt,minimum=5,maximum=15)
rule('ff_ph_sdu_bytes',dt,minimum=8,maximum=273)
rule('ff_dl_sdu_bytes',dt,minimum=5,equal_expression={'sum':['payload_bytes','ff_fms_pci_bytes','ff_fas_pci_bytes']})
rule('ff_ph_sdu_bytes',dt,equal_expression={'sum':['ff_dl_sdu_bytes','ff_dl_pci_bytes','ff_fcs_bytes']})
rule('ff_wire_octets',{'ff_profile':'H1_VOLTAGE_MODE'},equal_expression={'sum':['ff_ph_sdu_bytes','ff_preamble_bytes','ff_start_bytes','ff_end_bytes']})
for priority,limit in [('URGENT',64),('NORMAL',128),('TIME_AVAILABLE',256)]:
    rule('ff_dl_sdu_bytes',{'ff_priority':priority},maximum=limit)
for vcr,access,storage in [('PUBLISHER_SUBSCRIBER','SCHEDULED_CD','BUFFERED'),('CLIENT_SERVER','UNSCHEDULED_PT','QUEUED'),('SOURCE_SINK','UNSCHEDULED_PT','QUEUED')]:
    rule('ff_access',{'ff_vcr':vcr},allowed=[access])
    rule('ff_buffering',{'ff_vcr':vcr},allowed=[storage])
rule('ff_las_active',{'ff_device_class':'BASIC'},allowed=[False])
for state,lo,hi in [('OPERATIONAL',16,247),('CLEARED',248,251),('TEMPORARY',252,255)]:
    rule('ff_node_address',{'ff_address_state':state},minimum=lo,maximum=hi)
rule('ff_node_address',{'ff_address_state':'OPERATIONAL','ff_device_class':'LINK_MASTER'},maximum_parameter='ff_fun')
rule('ff_node_address',{'ff_address_state':'OPERATIONAL','ff_device_class':'BRIDGE'},maximum_parameter='ff_fun')
rule('ff_node_address',{'ff_address_state':'OPERATIONAL','ff_device_class':'BASIC'},minimum_expression={'sum':['ff_fun','ff_nun']})
rule('ff_nun',{},maximum_expression={'subtract':[247,'ff_fun']})
rule('ff_macrocycle_us',{},equal_expression={'sum':['ff_scheduled_us','ff_unscheduled_us','ff_maintenance_us']})
rule('ff_publish_offset_us',{},maximum_parameter='ff_macrocycle_us',maximum_offset=-0.001)
rule('ff_exchange_bound_us',{'ff_access':'SCHEDULED_CD'},maximum_parameter='ff_scheduled_us')
rule('ff_token_hold_us',{'ff_access':'SCHEDULED_CD'},allowed=[])
rule('ff_publish_offset_us',{'ff_access':'UNSCHEDULED_PT'},allowed=[])
rule('ff_token_hold_us',{'ff_access':'UNSCHEDULED_PT'},maximum_parameter='ff_unscheduled_us')
rule('ff_segment_total_m',{},equal_expression={'sum':['ff_trunk_m','ff_spurs_total_m']})
for cable,limit in [('TYPE_A',1900),('TYPE_B',1200),('TYPE_C',400),('TYPE_D',200)]:
    rule('ff_segment_total_m',{'ff_profile':'H1_VOLTAGE_MODE','ff_cable_type':cable},maximum=limit)
rule('ff_terminal_v',{'ff_profile':'H1_VOLTAGE_MODE'},minimum=9,maximum=32)
rule('ff_terminators',{'ff_profile':'H1_VOLTAGE_MODE'},allowed=[2])
rule('ff_devices_ma',{},maximum_parameter='ff_supply_ma')
rule('ff_is_source',{'ff_is_required':True},required=True)
# FMS user-data declarations do not silently define control telegram layouts.
for pdu in ['CD','PT','RT','EC','DC','RI','PN','PR','TD','CT','RQ','RR','CL','TL','IDLE']:
    for key in ['payload_bytes','ff_fms_pci_bytes','ff_fas_pci_bytes']:
        rule(key,{'ff_layout':'YOKOGAWA_FMS_DIAGRAM','ff_pdu':pdu},allowed=[])
semantics={'rate_model':{'type':'FIXED_LINK_RATE','fields':['bitrate_bps'],'fixed_bps':31250},
 'required_parameters':required,
 'mechanisms':{'access':['LAS_SCHEDULED_COMPEL_DATA','PASS_TOKEN_UNSCHEDULED'],
               'integrity':['DLPDU_FRAME_CHECK_SEQUENCE'],
               'synchronization':['LINK_SCHEDULING_TIME_DISTRIBUTION','APPLICATION_TIME_SEPARATE'],
               'relationships':['BUFFERED_PUBLISHER_SUBSCRIBER','QUEUED_CLIENT_SERVER','QUEUED_SOURCE_SINK']},
 'parameter_constraints':constraints}
text=text.replace("TECHNOLOGY_SEMANTICS['flexray'] = {",f"TECHNOLOGY_SEMANTICS['foundation_fieldbus_h1'] = {pformat(semantics,width=110,sort_dicts=False)}\n\nTECHNOLOGY_SEMANTICS['flexray'] = {{",1)
proposal={'kind':'FIXED_NOMINAL_RATE','default_bps':31250,'status':'REVIEW_REQUIRED','source':SOURCE,'source_revision':REVISION,
 'note':'Fixed31.25kbit/s H1 baseline. Actual FMS data, DLSDU, complete physical telegram and LAS transaction are distinct; native device/CFF/physical/schedule evidence remains unknown. No100M HSE or CAN defaults.'}
text=text.replace("    'flexray': {'kind':'DISCRETE_STANDARD_RATES'",f"    'foundation_fieldbus_h1': {proposal!r},\n    'flexray': {{'kind':'DISCRETE_STANDARD_RATES'",1)
text=text.replace("'ethernet_ip','flexray'} else", "'ethernet_ip','flexray','foundation_fieldbus_h1'} else",1)
text=text.replace('("foundation_fieldbus_h1", "FOUNDATION Fieldbus H1", "process_industry", "INDUSTRY_PROFILE", "PROCESS_DATA", ("FIELD", "STATUS", "QUALITY"), "fieldbus_interface", (), 31_250, 251, ("objects", "pubsub", "time_sync", "safety"), True)',
 '("foundation_fieldbus_h1", "FOUNDATION Fieldbus H1", "generic_networking", "APPLICATION", "PDU", ("FIELD", "STATUS", "QUALITY"), "h1_fieldbus_interface", (), 31_250, 251, ("objects", "pubsub", "time_sync", "request_response"), True)',1)
block=f'''    if technology_id == 'foundation_fieldbus_h1':
        source=REVIEW_RATE_PROPOSALS['foundation_fieldbus_h1']
        fields=[item for item in fields if item['key'] not in {set(removed)!r}]
        for item in fields:
            if item['key']=='payload_bytes':
                item.pop('default',None)
                item.update(integer=True,default_status='UNKNOWN',parameter_origin='DEVICE_CONFIGURATION',
                    source=source['source'],source_revision=source['source_revision'],simulation_relevant=False,
                    description='Actual FMS encoded data, not full telegram or logical segmented domain; applies to qualified DT layout only.')
        for key,kind,unit,options,minimum,maximum,default,meaning in {pformat(declarations,width=110)}:
            native=field(key,key.replace('ff_','').replace('_',' '),'timing' if unit=='us' else 'physical','route',
                field_type=kind,unit=unit,options=options,minimum=minimum,maximum=maximum,
                default=default if key in {{'ff_profile','ff_layout','ff_las_service_address'}} else None,
                description=meaning,simulation_relevant=False)
            native.update(required=key in TECHNOLOGY_SEMANTICS['foundation_fieldbus_h1']['required_parameters'],
                integer=kind=='number' and unit not in {{'us','m','V','mA','ohm'}},
                parameter_origin='TRANSPORT_PROFILE' if default is not None else 'DEVICE_CONFIGURATION',
                default_status='PROPOSED' if default is not None else 'UNKNOWN',
                source=source['source'],source_revision=source['source_revision'])
            if default is not None and key not in {{'ff_profile','ff_layout','ff_las_service_address'}}:
                when={{'ff_layout':'YOKOGAWA_FMS_DIAGRAM','ff_pdu':'DT'}} if key in {{'ff_fms_pci_bytes','ff_fas_pci_bytes','ff_fcs_bytes'}} else {{'ff_profile':'H1_VOLTAGE_MODE'}}
                native.update(conditional_defaults=[{{'when':when,'value':default}}],default_status='PROPOSED_CONDITIONAL')
            fields.append(native)
'''
text=text.replace("    if technology_id == 'flexray':\n",block+"    if technology_id == 'flexray':\n",1)
path.write_text(text,encoding='utf-8')
print({'fields':len(declarations),'constraints':len(constraints)})
