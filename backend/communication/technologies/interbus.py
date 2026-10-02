"""Qualified INTERBUS rings; process image, PCP and local PLC are distinct."""
BC='https://download.beckhoff.com/download/document/io/bus-terminals/bc4000en.pdf'
AXC='https://www.phoenixcontact.com/en-us/products/extension-module-axc-f-il-adapt-1020304?type=pdf'
PCI='https://datasheet.octopart.com/2725260-Phoenix-Contact-datasheet-13325117.pdf'
SOURCES={BC:'Beckhoff BC4000 v2.2.0 2022-03-16 chapters2,5,6,7; other BC register rows excluded',
 AXC:'Phoenix Contact 1020304 AXC F IL ADAPT official product PDF generated2026-09-02, pp1-4',
 PCI:'Phoenix Contact IBS PCI SC QS UM E 6190_en_03 manufacturer manual, distributor-hosted original, chapters3.2/3.3'}
DECLARATIONS=[]


def d(key,kind,meaning,source=BC,unit=None,options=None,minimum=None,maximum=None,**extra):
    DECLARATIONS.append(dict(key='ib_'+key,type=kind,description=meaning,source=source,source_revision=SOURCES[source],
        unit=unit,options=options,min=minimum,max=maximum,**extra))


d('device_profile','select','Actual equipment and manual revision; generic equipment cannot inherit BC4000 PLC defaults.',options=['ACTUAL_DEVICE','BC4000_2_2','AXC_F_IL_ADAPT_202609','PCI_SC_RI_I_T_6190_03'])
d('configuration_phase','select','Actual values versus source-qualified factory proposals; no automatically confirmed hardware.',options=['CONFIGURED_DEVICE','FACTORY_PROFILE'])
d('role','select','Actual ring master, slave or system coupler; internal PLC does not imply fieldbus master.',options=['MASTER','SLAVE','MASTER_SLAVE'])
d('segment_kind','select','Actual local or remote ring; installation remote needs independently registered PHY evidence.',options=['LOCAL','REMOTE','INSTALLATION_REMOTE'])
d('cycle_kind','select','Actual initialization/identification or process-data cycle; PCP traffic needs its own channel budget.',options=['ID','PROCESS_DATA','PCP'])
d('bitrate_bps','number','Actual selected segment clock;500k is reviewed baseline,2M requires every applicable participant to support it.',minimum=1,options=[500000,2000000],unit='bit/s')
d('medium','select','Actual paired copper or optical PHY; local Inline and remote cable are independent.',options=['COPPER','POLYMER','HCS','GLASS'],source=AXC)
for key,meaning in [('device_source','Actual firmware/identity/limits and configured register evidence.'),
 ('master_source','Actual selected master/firmware and separate ring capacity proof.'),
 ('physical_source','Actual connectors, cable/segment/length/power and homogeneous selected clock.'),
 ('encoding_source','Actual ordered ID/data-register/process-image/PCP layout.'),
 ('schedule_source','Actual master cycle and application release/read/write schedule.'),
 ('acceptance_source','Actual full controller-to-device timing/quality/freshness acceptance.'),
 ('ring_binding','Actual canonical ring/interface binding, not an automatically assigned CAN ID.'),
 ('node_identity','Actual unique physical station identity/order and approved configuration.'),
 ('pcp_source','Actual device/firmware PCP service/channel/state/budget evidence.'),
 ('power_source','Actual consumption/derating/terminal allocation evidence.'),
 ('coupled_ring_binding','Actual other independent ring of the system coupler.')]:d(key,'text',meaning)
for key,meaning,maximum in [('station_order','Actual discovered ring order; not manufacturer ID or project-assigned CAN address.',None),
 ('input_bytes','Actual station fieldbus input process image, not local PLC storage.',None),
 ('output_bytes','Actual station fieldbus output process image.',None),
 ('effective_words','Actual non-rounded periphery register words; not sum of independent IN+OUT images.',None),
 ('id_words','Actual encoded register width, with device-specific rounding.',None),
 ('id_code','Actual ID-cycle module class; not manufacturer identity.',255),
 ('total_nodes','Actual nodes on the selected master ring.',None),
 ('local_nodes','Actual local station count; actual power budget may reduce maximum.',None),
 ('remote_branches','Actual remote branches; local-only master forbids these.',None),
 ('pcp_nodes','Actual participants using the parameter channel, not whole ring device count.',None),
 ('master_input_bits','Actual selected master input allocation.',None),
 ('master_output_bits','Actual selected master output allocation.',None),
 ('master_io_bits','Actual combined input+output allocation, distinct from register length.',None),
 ('master_register_bytes','Actual master register allocation, not a PCP message-size ceiling.',None),
 ('local_plc_input_bytes','Actual local PLC input storage, not fieldbus bytes.',None),
 ('local_plc_output_bytes','Actual local PLC output storage, not fieldbus bytes.',None),
 ('local_terminals','Actual BC K-bus allocation, not global ring nodes.',64),
 ('pcp_service_bytes','Actual complete device-accepted PCP service size, unknown until actual service/peer evidence.',None),
 ('peer_pcp_service_limit','Actual PCP peer service size, not universal246-byte process image.',None),
 ('cycle_effective_bytes','Actual full ring effective bytes for qualified timing formula, not words.',None),
 ('cycle_couplers','Actual couplers for qualified timing formula.',None)]:d(key,'number',meaning,minimum=0,maximum=maximum,unit='Byte'if key.endswith('bytes')or key.endswith('limit')else None)
for key in ('hop_length_m','ring_length_m'):d(key,'number','Actual measured '+key+' with applicable segment/medium/device limits.',minimum=0,unit='m')
d('timing_model','select','Actual measured/verified model versus BC manual500k ring estimate; estimate alone is not complete capacity or E2E proof.',options=['ACTUAL_VERIFIED','BC4000_500K_MANUAL'])
for key in ('model_cycle_ms','ring_reaction_ms','error_recovery_ms','controller_master_ms','coupler_output_ms','application_bound_ms'):
    d(key,'number','Actual or qualified-model '+key+'; ring and full functional latency remain separate.',minimum=0,unit='ms')
for key,minimum,maximum,unit in [('bc_input_offset',0,None,'Byte'),('bc_output_offset',0,None,'Byte'),
 ('bc_digital_input_offset',0,None,'Byte'),('bc_digital_output_offset',0,None,'Byte'),
 ('bc_plc_cycle_ms',0,None,'ms'),('bc_background_ms',0,None,'ms'),('bc_remanent_bytes',0,512,'Byte'),
 ('bc_persistent_bytes',0,512,'Byte'),('bc_autorefresh_cycles',0,255,None),('bc_autorefresh_retries',0,255,None)]:
    d(key,'number','Actual BC4000 register '+key+'; other BC8x00/BC9000 table columns do not apply.',minimum=minimum,maximum=maximum,unit=unit)
for key in ('bc_remanent_enabled','bc_terminal_check'):d(key,'boolean','Actual BC4000 register '+key+'.')
d('bc_kbus_update','select','Actual BC4000 K-bus update relative to local PLC, not INTERBUS arbitration.',options=['BEFORE_AND_AFTER','BEFORE','AFTER'])
d('bc_first_terminal_mapping','select','Actual first BC terminal mapping; no invented configured project terminal.',options=['COMPLEX_FIELD_BUS','COMPACT_FIELD_BUS','LOCAL_PROCESS_IMAGE'])
d('bc_other_terminal_mapping','select','Actual mapping policy for subsequent BC terminals; actual individual overrides require evidence.',options=['COMPLEX_FIELD_BUS','COMPACT_FIELD_BUS','LOCAL_PROCESS_IMAGE'])
d('pci_slave_configuration','select','Actual PCI SC slave DIP10 configuration source; OFF ignores baud/ID DIP positions.',options=['STORED_OR_UPSTREAM','DIP_SWITCHES'],source=PCI)
d('pci_slave_bitrate_bps','number','Actual independent upper-ring slave clock, not forced equal to lower-ring master.',options=[500000,2000000],minimum=1,unit='bit/s',source=PCI)
d('pci_slave_id_code','number','Actual PCI SC slave ID code, not BC4000 ID51.',minimum=0,maximum=255,source=PCI)
d('pci_slave_words','number','Actual PCI SC slave process words; discrete DIP lengths0..14 or16, combined process and PCP width at most16.',minimum=0,maximum=16,source=PCI)
d('pci_pcp_words','number','Actual PCI SC slave parameter-channel words;0,1,2 or4 with matching ID code.',minimum=0,maximum=4,source=PCI)
d('pci_power_loss_error','boolean','Actual PCI SC slave power-loss behavior.',source=PCI)

REMOVED={key:'Removed inherited '+key+': INTERBUS ordered shift-register ring and PCP/PLC/device settings require their own evidence, no CAN or Ethernet queues/serial setup.'for key in
 ('bitrate','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
 'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
 'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}
REQUIRED=['device_profile','configuration_phase','role','segment_kind','cycle_kind','bitrate_bps','medium',
 'device_source','master_source','physical_source','encoding_source','schedule_source','acceptance_source','ring_binding']


def semantics():
    rules=[]
    def r(key,when=None,source=BC,**kw):rules.append(dict(parameter='ib_'+key,when={'ib_'+k:v for k,v in (when or {}).items()},source=source,source_revision=SOURCES[source],**kw))
    r('bitrate_bps',allowed=[500000,2000000])
    r('pcp_source',{'cycle_kind':'PCP'},required=True)
    r('pcp_service_bytes',{'cycle_kind':'PCP'},maximum_parameter='ib_peer_pcp_service_limit')
    r('master_io_bits',equal_expression={'sum':['ib_master_input_bits','ib_master_output_bits']},source=AXC)
    r('pcp_nodes',maximum_parameter='ib_total_nodes',source=AXC)
    bc={'device_profile':'BC4000_2_2'};axc={'device_profile':'AXC_F_IL_ADAPT_202609'};pci={'device_profile':'PCI_SC_RI_I_T_6190_03'}
    for key,allowed in [('role',['SLAVE']),('segment_kind',['REMOTE']),('medium',['COPPER']),('bitrate_bps',[500000]),('id_code',[1,2,3,49,50,51])]:r(key,bc,allowed=allowed)
    for key in ('input_bytes','output_bytes'):r(key,bc,maximum=64)
    for key in ('local_plc_input_bytes','local_plc_output_bytes'):r(key,bc,maximum=512)
    r('effective_words',bc,minimum=1,maximum=32)
    for words in range(1,33):
        rounded=words if words<=10 else 12 if words<=12 else 14 if words<=14 else 16 if words<=16 else 24 if words<=24 else 32
        r('id_words',{**bc,'effective_words':words},allowed=[rounded])
    r('bc_persistent_bytes',bc,maximum_expression={'subtract':['ib_bc_remanent_bytes',1]})
    r('bc_input_offset',bc,maximum_expression={'subtract':[512,'ib_input_bytes']})
    r('bc_output_offset',bc,maximum_expression={'subtract':[512,'ib_output_bytes']})
    r('hop_length_m',{**bc,'segment_kind':'REMOTE'},maximum=400)
    r('ring_length_m',bc,maximum=12800)
    for spec in DECLARATIONS:
        key=spec['key'].removeprefix('ib_')
        if key.startswith('bc_')or key in ('local_plc_input_bytes','local_plc_output_bytes','local_terminals'):
            r(key,when_not={'ib_device_profile':'BC4000_2_2'},allowed=[])
        if key.startswith('pci_')or key=='coupled_ring_binding':r(key,when_not={'ib_device_profile':'PCI_SC_RI_I_T_6190_03'},allowed=[])
    for key,allowed in [('role',['MASTER']),('segment_kind',['LOCAL']),('medium',['COPPER']),('remote_branches',[0])]:r(key,axc,allowed=allowed,source=AXC)
    for key,maximum in [('local_nodes',63),('total_nodes',63),('pcp_nodes',24),('master_input_bits',2048),('master_output_bits',2048),('master_io_bits',4096),('master_register_bytes',512)]:r(key,axc,maximum=maximum,source=AXC)
    r('power_source',axc,when_present=['ib_local_nodes'],required=True,source=AXC)
    r('role',pci,allowed=['MASTER_SLAVE'],source=PCI)
    r('coupled_ring_binding',pci,required=True,source=PCI)
    r('pci_slave_bitrate_bps',pci,allowed=[500000,2000000],source=PCI)
    r('pci_slave_words',pci,allowed=list(range(15))+[16],maximum_expression={'subtract':[16,'ib_pci_pcp_words']},source=PCI)
    r('pci_pcp_words',pci,allowed=[0,1,2,4],source=PCI)
    for words,code in [(0,3),(1,235),(2,232),(4,233)]:r('pci_slave_id_code',{**pci,'pci_pcp_words':words},allowed=[code],source=PCI)
    r('bitrate_bps',{'timing_model':'BC4000_500K_MANUAL'},allowed=[500000])
    r('model_cycle_ms',{'timing_model':'BC4000_500K_MANUAL'},equal_expression={'sum':[0.2,{'product':[0.002,{'sum':[{'product':[13,{'sum':[6,'ib_cycle_effective_bytes']}]},{'product':[1.5,'ib_cycle_couplers']}]}]}]})
    r('ring_reaction_ms',{'timing_model':'BC4000_500K_MANUAL'},equal_expression={'product':[2,'ib_model_cycle_ms']})
    r('error_recovery_ms',{'timing_model':'BC4000_500K_MANUAL'},equal_expression={'product':[5,'ib_model_cycle_ms']})
    for key in ('model_cycle_ms','cycle_effective_bytes','cycle_couplers'):r(key,{'timing_model':'BC4000_500K_MANUAL'},required=True)
    return {'rate_model':{'type':'INTERBUS_INDEPENDENT_RING_CLOCKS','fields':[]},'required_parameters':['ib_'+key for key in REQUIRED],
        'native_parameter_prefixes':['ib_'],'parameter_constraints':rules,'mechanisms':{'framing':['ID_CYCLE_OR_PROCESS_DATA_SHIFT_REGISTER_OR_PCP'],
        'arbitration':['MASTER_DRIVEN_ORDERED_RING'],'addressing':['DISCOVERED_STATION_ORDER_NOT_MANUFACTURER_ID'],
        'physical':['ACTIVE_RING_RETURN_PATH_MEDIUM_AND_ROLE_SPECIFIC'],'acceptance':['RING_CYCLE_SEPARATE_FROM_LOCAL_PLC_AND_FUNCTIONAL_E2E']}}


def fields():
    result=[];required=set(semantics()['required_parameters'])
    bc_defaults={'input_bytes':16,'output_bytes':16,'id_code':51,'id_words':8,'bc_input_offset':128,'bc_output_offset':128,
        'bc_digital_input_offset':0,'bc_digital_output_offset':0,'bc_plc_cycle_ms':5,'bc_background_ms':2,
        'bc_remanent_enabled':True,'bc_remanent_bytes':64,'bc_persistent_bytes':0,'bc_autorefresh_cycles':0,
        'bc_terminal_check':True,'bc_kbus_update':'BEFORE_AND_AFTER','bc_first_terminal_mapping':'LOCAL_PROCESS_IMAGE','bc_other_terminal_mapping':'COMPLEX_FIELD_BUS'}
    pci_defaults={'pci_slave_configuration':'STORED_OR_UPSTREAM','pci_slave_id_code':3,'pci_slave_words':16,'pci_pcp_words':0,'pci_slave_bitrate_bps':500000,'pci_power_loss_error':True}
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items()if v is not None};key=item['key'].removeprefix('ib_')
        item.update(label=key.replace('_',' '),category='communication',scope='network',required=item['key']in required,
            editable=True,integer=spec['type']=='number'and spec['unit']not in ('ms','m'),parameter_origin='DEVICE_CONFIGURATION',
            default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
        proposals=[]
        if key=='bitrate_bps':proposals.append({'when':{},'value':500000,'source':BC,'source_revision':SOURCES[BC]})
        if key in bc_defaults:proposals.append({'when':{'ib_device_profile':'BC4000_2_2','ib_configuration_phase':'FACTORY_PROFILE'},'value':bc_defaults[key],'source':BC,'source_revision':SOURCES[BC]})
        if key in pci_defaults:proposals.append({'when':{'ib_device_profile':'PCI_SC_RI_I_T_6190_03','ib_configuration_phase':'FACTORY_PROFILE'},'value':pci_defaults[key],'source':PCI,'source_revision':SOURCES[PCI]})
        if proposals:item.update(conditional_defaults=proposals,default_status='PROPOSED_CONDITIONAL')
        result.append(item)
    return result
