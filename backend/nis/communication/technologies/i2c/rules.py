"""I²C rules from NXP UM10204 Rev7; installation facts are never defaults."""
from math import isfinite

SOURCE = 'https://www.nxp.com/docs/en/user-guide/UM10204.pdf'
REVISION = 'NXP UM10204 Rev7.0 2021-10-01 sections3/5/6/7 Tables10-15'
MODES = {'STANDARD':100000, 'FAST':400000, 'FAST_PLUS':1000000,
         'HIGH_SPEED':3400000, 'ULTRA_FAST':5000000}
# All times ns. Values are normative limits, not claimed hardware measurements.
TIMING = {
 'STANDARD': {'low':4700,'high':4000,'start_hold':4000,'start_setup':4700,
              'stop_setup':4000,'bus_free':4700,'data_setup':250,'data_hold':0,
              'rise_max':1000,'fall_max':300,'data_valid_max':3450,'ack_valid_max':3450,'cap_max':400},
 'FAST': {'low':1300,'high':600,'start_hold':600,'start_setup':600,
          'stop_setup':600,'bus_free':1300,'data_setup':100,'data_hold':0,
          'rise_min':20,'rise_max':300,'fall_max':300,'data_valid_max':900,'ack_valid_max':900,'cap_max':400},
 'FAST_PLUS': {'low':500,'high':260,'start_hold':260,'start_setup':260,
               'stop_setup':260,'bus_free':500,'data_setup':50,'data_hold':0,
               'rise_max':120,'fall_max':120,'data_valid_max':450,'ack_valid_max':450,'cap_max':550},
 'ULTRA_FAST': {'low':50,'high':50,'start_hold':50,'start_setup':50,
                'stop_setup':50,'bus_free':80,'data_setup':30,'data_hold':10,
                'rise_max':50,'fall_max':50},
}

# key, type, unit, alternatives, min, max, meaning. Exact device facts remain blank.
DECLARATIONS = [
 ('i2c_profile','select',None,['UM10204_STANDARD_LIMITS','SECTION7_2_EXTENDED_LOAD'],None,None,'Actual electrical qualification. Section7.2 higher load requires its own proven timing/drive/segmentation and frequency bound.'),
 ('i2c_mode','select',None,list(MODES),None,None,'Operating mode. STANDARD100kbit/s is a proposed baseline, not minimum clock frequency. UFm is a different unidirectional push-pull system.'),
 ('i2c_endpoint_role','select',None,['CONTROLLER','TARGET','CONTROLLER_TARGET'],None,None,'Actual endpoint role. A pure controller needs no own target address; controller-target does.'),
 ('i2c_controller_id','text',None,None,None,None,'Actual canonical clock-owning controller identity. No invented ECU identity or topology owner confirmation.'),
 ('i2c_device_source','text',None,None,None,None,'Actual controller/target datasheet revision, supported modes, pins and address constraints.'),
 ('i2c_binding_source','text',None,None,None,None,'Actual matching controller-target port and segment binding, with unique addresses/multiplexing evidence.'),
 ('i2c_physical_source','text',None,None,None,None,'Actual voltage/pull-up/driver/load/edge/threshold/segment evidence; nominal rate is not electrical validation.'),
 ('i2c_schedule_source','text',None,None,None,None,'Actual transactions, register/address phases, polling/retry/stretch/arbitration and functional acceptance evidence.'),
 ('i2c_drive','select',None,['OPEN_DRAIN','OPEN_COLLECTOR','HS_CURRENT_SOURCE','PUSH_PULL'],None,None,'Actual driver. Sm/Fm/Fm+ wired-AND open drain/collector; HS controller current source; UFm push-pull.'),
 ('i2c_address_bits','number','bit',[7,10],7,10,'Actual7/10-bit target address width, no inferred7-bit hardware configuration.'),
 ('i2c_target_address','number',None,None,0,1023,'Actual unshifted target address, excluding R/W. Reserved7-bit purposes require explicit matching service evidence.'),
 ('i2c_address_purpose','select',None,['ORDINARY','RESERVED_SERVICE'],None,None,'Actual ordinary versus reserved service addressing; general call/START/HS code/prefix are not interchangeable targets.'),
 ('i2c_address_source','text',None,None,None,None,'Actual device straps/register/assigned address and reserved service meaning; unknown, no automatic0x20.'),
 ('i2c_direction','select',None,['READ','WRITE','BIDIRECTIONAL'],None,None,'Actual transaction direction. UFm accepts writes only; bidirectional requires combined address phases.'),
 ('i2c_multi_controller','boolean',None,None,None,None,'Actual competing controller configuration. Arbitration is unnecessary for a proven single controller, not assumed false.'),
 ('i2c_clock_stretch_supported','boolean',None,None,None,None,'Actual matched controller/target stretching support. UFm cannot stretch; HS stretches only after ACK.'),
 ('i2c_hs_entry_rate_bps','number','bit/s',None,1,400000,'Actual F/S-mode HS controller-code entry clock. HS3.4M data rate cannot size this preceding phase.'),
 ('i2c_hs_controller_code','number',None,None,8,15,'Actual reserved8-bit HS controller code00001XXX; code8 reserved test/diagnostic, not a target address.'),
 ('i2c_hs_diagnostic','boolean',None,None,None,None,'Actual test/diagnostic use permitting controller code8; no implicit operational use.'),
 ('i2c_stretch_position','select',None,['ANY_LOW','AFTER_ACK','NONE'],None,None,'Actual stretch placement: HS only after ACK, UFm none. Stretch upper bound is device/schedule data, not a spec default.'),
 ('i2c_ack_policy','select',None,['ACK_NACK','NINTH_HIGH_NO_ACK'],None,None,'Bidirectional ACK/NACK is not CRC or functional acceptance. UFm preserves ninth pulse HIGH without target acknowledgement.'),
 ('i2c_vdd_v','number','V',None,0,None,'Actual pull-up/driver supply domain; no universal3.3/5V.'),
 ('i2c_vil_max_v','number','V',None,0,None,'Actual receiver LOW threshold, including legacy fixed-level parts and level translators.'),
 ('i2c_vih_min_v','number','V',None,0,None,'Actual receiver HIGH threshold, not universally inferred from current CMOS ratios.'),
 ('i2c_vol_max_v','number','V',None,0,None,'Actual worst-case driver LOW at actual current/voltage/temperature.'),
 ('i2c_voh_min_v','number','V',None,0,None,'Actual UFm push-pull HIGH guarantee; passive open drain HIGH is pull-up/leakage/load evidence.'),
 ('i2c_sink_bound_ma','number','mA',None,0,None,'Actual safe sink capability at specified VOL, not automatically3mA/20mA.'),
 ('i2c_source_bound_ma','number','mA',None,0,None,'Actual UFm source capability or HS current-source qualification; not passive pull-up current.'),
 ('i2c_pullup_ohms','number','Ohm',None,0,None,'Actual passive pull-up for Sm/Fm/Fm+; Rp minimum depends on sink and VOL, maximum on rise time and capacitance. No4.7k default.'),
 ('i2c_bus_cap_pf','number','pF',None,0,None,'Actual per-line wire+pins+connectors capacitance. Table11 limits400/400/550pF, HS100..400 interpolated timing; UFm no generic capacitance maximum.'),
 ('i2c_pin_cap_pf','number','pF',None,0,None,'Actual pin capacitance. Ordinary qualified device max10pF; switches/multiplexers can exceed with explicit device evidence.'),
 ('i2c_special_pin','boolean',None,None,None,None,'Actual special switch/multiplexer exception, unknown; prevents falsely applying ordinary10pF limit.'),
 ('i2c_extended_frequency_bound_bps','number','bit/s',None,1,None,'Actual verified section7.2 load/drive/RC/segmentation frequency bound, never an automatic higher mode or unspecified relaxation.'),
 ('i2c_extended_source','text',None,None,None,None,'Actual section7.2 calculations/datasheet/buffer and rise/fall/voltage evidence for non-baseline electrical load.'),
 ('i2c_bus_clear','select',None,['NINE_CLOCKS_SDA_STUCK','HARDWARE_RESET_OR_POWER_CYCLE','DEVICE_SPECIFIC'],None,None,'Actual recovery policy. Nine clocks are for SDA-stuck; SCL-stuck may require reset/power-cycle, not automatic nine-clock repair.'),
 ('i2c_recovery_source','text',None,None,None,None,'Actual stuck-line/retry/recovery/acceptance limits and controller capability; recovery is extra schedule time.'),
 ('i2c_retry_limit','number','attempts',None,0,None,'Actual transaction retry budget, no universal zero or guaranteed arbitration completion.'),
]
for suffix in ('low','high','start_hold','start_setup','stop_setup','bus_free','data_setup','data_hold',
               'rise','fall','data_valid','ack_valid','hs_first_rise','hs_data_rise','hs_data_fall'):
    DECLARATIONS.append((f'i2c_{suffix}_ns','number','ns',None,0,None,
        f'Actual {suffix} timing at actual load/threshold/mode. Normative mode limits are constraints, not measured default values.'))

REMOVED = {key:'Removed inherited packet-network '+key+': I²C has no intrinsic Ethernet MTU/VLAN/duplex/QoS/queue/transport retry/gateway capacity; actual controller software and transaction recovery require separate evidence.'
           for key in ('mtu_bytes','vlan_id','duplex','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent',
                       'rate_limit_bit_s','sync_method','retransmission_enabled','retransmission_rate','retry_limit',
                       'retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer','gateway_output_buffer',
                       'gateway_maximum_routes','gateway_maximum_messages_s')}

def semantics():
    rules=[]
    def rule(key,when=None,**kw):
        rules.append(dict(parameter=key,when=when or {},source=SOURCE,source_revision=REVISION,**kw))
    for mode,rate in MODES.items():
        scope={'i2c_mode':mode}
        rule('bitrate_bps',scope,maximum=rate)
        uf=mode=='ULTRA_FAST'
        rule('i2c_ack_policy',scope,allowed=['NINTH_HIGH_NO_ACK' if uf else 'ACK_NACK'])
        if mode!='HIGH_SPEED': rule('i2c_drive',scope,allowed=['PUSH_PULL'] if uf else ['OPEN_DRAIN','OPEN_COLLECTOR'])
        if mode not in ('HIGH_SPEED','ULTRA_FAST'):
            rule('i2c_stretch_position',scope,allowed=['ANY_LOW','NONE'])
        for name,bound in TIMING.get(mode,{}).items():
            if name=='cap_max': key='i2c_bus_cap_pf'; kind='maximum'
            elif name.endswith('_max'): key='i2c_'+name[:-4]+'_ns';kind='maximum'
            elif name.endswith('_min'): key='i2c_'+name[:-4]+'_ns';kind='minimum'
            else: key='i2c_'+name+'_ns';kind='minimum'
            applicable={**scope,'i2c_profile':'UM10204_STANDARD_LIMITS'}
            if name in ('data_valid_max','ack_valid_max'):
                applicable['i2c_clock_stretch_supported']=False
            rule(key,applicable,**{kind:bound})
    rule('i2c_direction',{'i2c_mode':'ULTRA_FAST'},allowed=['WRITE'])
    rule('i2c_multi_controller',{'i2c_mode':'ULTRA_FAST'},allowed=[False])
    rule('i2c_clock_stretch_supported',{'i2c_mode':'ULTRA_FAST'},allowed=[False])
    rule('i2c_stretch_position',{'i2c_mode':'ULTRA_FAST'},allowed=['NONE'])
    rule('i2c_stretch_position',{'i2c_mode':'HIGH_SPEED'},allowed=['AFTER_ACK','NONE'])
    rule('i2c_drive',{'i2c_mode':'HIGH_SPEED'},allowed=['OPEN_DRAIN','HS_CURRENT_SOURCE'])
    rule('i2c_target_address',{'i2c_endpoint_role':'CONTROLLER'},allowed=[])
    for role in ('TARGET','CONTROLLER_TARGET'):
        for key in ('i2c_address_bits','i2c_target_address','i2c_address_purpose','i2c_address_source'):
            rule(key,{'i2c_endpoint_role':role},required=True)
    rule('i2c_target_address',{'i2c_address_bits':7},maximum=127)
    rule('i2c_target_address',{'i2c_address_bits':7,'i2c_address_purpose':'ORDINARY'},minimum=8,maximum=119)
    rule('i2c_address_bits',allowed=[7,10])
    rule('i2c_hs_controller_code',{'i2c_mode':'HIGH_SPEED','i2c_hs_diagnostic':False},minimum=9)
    for key in ('i2c_hs_entry_rate_bps','i2c_hs_controller_code','i2c_hs_diagnostic'):
        rule(key,{'i2c_mode':'HIGH_SPEED'},required=True)
        for mode in ('STANDARD','FAST','FAST_PLUS','ULTRA_FAST'): rule(key,{'i2c_mode':mode},allowed=[])
    baseline={'i2c_profile':'UM10204_STANDARD_LIMITS','i2c_mode':'HIGH_SPEED'}
    rule('i2c_bus_cap_pf',baseline,maximum=400)
    # Table13 interpolation uses timing, never a linear interpolation of frequency.
    for key,at100,at400,kind in [('low',160,320,'minimum'),('high',60,120,'minimum'),
            ('rise',40,80,'maximum'),('fall',40,80,'maximum'),
            ('hs_first_rise',80,160,'maximum'),('hs_data_rise',80,160,'maximum'),
            ('hs_data_fall',80,160,'maximum'),('data_hold',70,150,'maximum')]:
        expr={'sum':[at100,{'product':[(at400-at100)/300,{'subtract':['i2c_bus_cap_pf',100]}]}]}
        rule('i2c_'+key+'_ns',baseline,when_ranges={'i2c_bus_cap_pf':[100,400]},**{kind+'_expression':expr})
        rule('i2c_'+key+'_ns',baseline,when_ranges={'i2c_bus_cap_pf':[0,100]},**{kind:at100})
    for key,bound in [('start_hold',160),('start_setup',160),('stop_setup',160),('data_setup',10)]:
        rule('i2c_'+key+'_ns',baseline,minimum=bound)
    for key in ('rise','fall','hs_first_rise','hs_data_rise','hs_data_fall'):
        rule('i2c_'+key+'_ns',baseline,when_ranges={'i2c_bus_cap_pf':[0,100]},minimum=10)
        rule('i2c_'+key+'_ns',baseline,when_ranges={'i2c_bus_cap_pf':[100,400]},
             minimum_expression={'sum':[10,{'product':[1/30,{'subtract':['i2c_bus_cap_pf',100]}]}]})
    rule('bitrate_bps',baseline,when_ranges={'i2c_bus_cap_pf':[400,400]},maximum=1700000)
    rule('bitrate_bps',maximum_ratio={'numerator_offset':1,'denominator_sum':['i2c_low_ns','i2c_high_ns','i2c_rise_ns','i2c_fall_ns'],'factor':1e9})
    rule('i2c_vdd_v',exclusive_minimum=0)
    rule('i2c_vol_max_v',maximum_parameter='i2c_vil_max_v')
    rule('i2c_vih_min_v',maximum_parameter='i2c_vdd_v',minimum_parameter='i2c_vil_max_v')
    rule('i2c_voh_min_v',{'i2c_mode':'ULTRA_FAST'},minimum_parameter='i2c_vih_min_v')
    rule('i2c_pin_cap_pf',{'i2c_profile':'UM10204_STANDARD_LIMITS','i2c_special_pin':False},maximum=10)
    for mode in ('FAST','FAST_PLUS'):
        rule('i2c_fall_ns',{'i2c_profile':'UM10204_STANDARD_LIMITS','i2c_mode':mode},minimum_expression={'product':['i2c_vdd_v',20/5.5]})
    for mode in ('STANDARD','FAST','FAST_PLUS'):
        rule('i2c_pullup_ohms',{'i2c_mode':mode},exclusive_minimum=0)
        rule('i2c_pullup_ohms',{'i2c_mode':mode},maximum_ratio={'numerator_parameter':'i2c_rise_ns','denominator_product':['i2c_bus_cap_pf'],'denominator_offset':1,'factor':1000/0.8473})
        rule('i2c_vdd_v',{'i2c_mode':mode},maximum_expression={'sum':['i2c_vol_max_v',{'product':['i2c_pullup_ohms','i2c_sink_bound_ma',0.001]}]})
    rule('i2c_extended_source',{'i2c_profile':'SECTION7_2_EXTENDED_LOAD'},required=True)
    rule('i2c_extended_frequency_bound_bps',{'i2c_profile':'SECTION7_2_EXTENDED_LOAD'},required=True)
    rule('bitrate_bps',{'i2c_profile':'SECTION7_2_EXTENDED_LOAD'},maximum_parameter='i2c_extended_frequency_bound_bps')
    return {'rate_model':{'type':'I2C_CONFIRMED_CLOCK','fields':['bitrate_bps'],'maximum_bps':5000000},
            'required_parameters':['bitrate_bps','i2c_mode','i2c_profile','i2c_endpoint_role','i2c_controller_id',
                'i2c_device_source','i2c_binding_source','i2c_physical_source','i2c_schedule_source'],
            'native_parameter_prefixes':['i2c_'],'parameter_constraints':rules,
            'mechanisms':{'addressing':['EXPLICIT_7_OR_10_BIT_TARGET_NOT_CONTROLLER_ADDRESS'],
                'integrity':['BIDIRECTIONAL_ACK_NACK_OR_UFM_NINTH_HIGH_NO_ACK'],
                'arbitration':['ONLY_ACTUAL_MULTICONTROLLER_F_S_PHASE_NOT_UFM'],
                'scope':['BUS_CONFIGURATION_PORT_ROLE_AND_TRANSACTION_EVIDENCE_SEPARATE']}}

def local_fields():
    def f(key,kind,description,**kw):
        optional=kw.pop('optional_override',False)
        return {**dict(key=key,label=key.replace('_',' '),type=kind,numeric=kind=='number',boolean=kind=='boolean',
            optional=optional,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',source=SOURCE,
            source_revision=REVISION,description=description,scope='device'), **kw}
    return [
      f('evidence_scope','select','Actual controller port, target port or complete transaction; legacy omitted scope remains transaction only.',optional_override=True,options=['CONTROLLER_PORT','TARGET_PORT','TRANSACTION']),
      f('master_node_id','text','Actual owning controller canonical identity. Not a target address.'),
      f('slave_address','address','Actual unshifted target integer or decimal/0x hexadecimal text, not the controller own port address.',required_scopes=['TARGET_PORT','TRANSACTION']),
      f('address_bits','number','Actual7/10-bit target address width.',integer=True,allowed_values=[7,10],required_scopes=['TARGET_PORT','TRANSACTION']),
      f('i2c_mode','select','Standard-mode is a review proposal from UM10204, not confirmed device configuration.',
        options=list(MODES),default='STANDARD',default_status='PROPOSED',parameter_origin='STANDARD_PROFILE_PROPOSAL'),
      f('transfer_direction','select','Actual complete transaction READ/WRITE/combined direction.',options=['READ','WRITE','BIDIRECTIONAL'],required_scopes=['TRANSACTION']),
      *[f(key,'number',meaning,unit=unit,minimum=0,required_scopes=['TRANSACTION'],**extra)
        for key,unit,meaning,extra in [
         ('start_stop_bound_us','us','Actual sum of START/repeatedSTART/STOP/bus-free timing for the transfer layout; no universal2us.',{}),
         ('clock_stretch_limit_us','us','Actual total target/controller stretch bound. I2C has no universal timeout; UFm requires zero.',{}),
         ('transfer_bits_bound','bit','Actual total data-phase clock bound including all address/data9th pulses/register overhead; HS entry separately bounded.',{'integer':True})]],
      f('multi_master','boolean','Actual competing controllers; not assumed false.',required_scopes=['TRANSACTION']),
      f('arbitration_bound_us','number','Actual complete retry/competition upper bound only for multicontroller transactions; no automatic zero.',unit='us',minimum=0,optional_override=True),
      f('bitrate_bps','number','Actual data-phase bus clock, positive during active transfers; stopped0Hz is not a positive capacity rate.',unit='bit/s',minimum=0),
      f('hs_entry_rate_bps','number','Actual HS entry F/S clock1..400k; optional outsideHS.',unit='bit/s',minimum=0,maximum=400000,optional_override=True),
      f('hs_entry_bound_us','number','Actual HS entry duration incl9-bit controller-code/NACK phase; not serialized at HS rate.',unit='us',minimum=0,optional_override=True),
      f('bus_cap_pf','number','Actual HS line load needed for HS timing qualification, unknown.',unit='pF',minimum=0,maximum=400,optional_override=True),
      f('hs_clock_timing_source','text','Actual load-interpolated HS LOW/HIGH/edge timing and current-source proof.',optional_override=True),
      f('address_purpose','select','Actual reserved7-bit service purpose; absent legacy nonreserved target remains ordinary only.',options=['ORDINARY','RESERVED_SERVICE'],optional_override=True),
    ]

def evidence_issues(e, payload_bytes=0, require_transaction=False):
    """Additional role/mode/layout constraints; caller validates typed declarations."""
    errors=[]
    number=lambda v: isinstance(v,(int,float)) and not isinstance(v,bool) and isfinite(v)
    integer=lambda v: number(v) and v==int(v)
    scope=e.get('evidence_scope') or 'TRANSACTION'
    if scope not in ('CONTROLLER_PORT','TARGET_PORT','TRANSACTION'): errors.append('evidence_scope')
    if require_transaction and scope!='TRANSACTION': errors.append('transaction_evidence')
    mode=e.get('i2c_mode')
    rate=e.get('bitrate_bps')
    if mode not in MODES or not number(rate) or not 0<rate<=MODES.get(mode,0): errors.append('bitrate_bps')
    if scope!='CONTROLLER_PORT':
        bits=e.get('address_bits');raw=e.get('slave_address')
        try:
            if isinstance(raw,str):
                value=int(raw,16) if raw.startswith(('0x','0X')) else int(raw,10)
            elif integer(raw): value=int(raw)
            else: raise ValueError
            if not integer(bits) or bits not in (7,10) or not 0<=value<2**int(bits): errors.append('slave_address')
            elif bits==7 and not 8<=value<=119 and e.get('address_purpose')!='RESERVED_SERVICE': errors.append('address_purpose')
        except (TypeError,ValueError,OverflowError): errors.append('slave_address')
    if scope=='TRANSACTION':
        multi=e.get('multi_master');direction=e.get('transfer_direction')
        if type(multi)is not bool: errors.append('multi_master')
        if direction not in ('READ','WRITE','BIDIRECTIONAL'): errors.append('transfer_direction')
        address_octets=1 if e.get('address_bits')==7 else 2
        if direction=='READ' and e.get('address_bits')==10 or direction=='BIDIRECTIONAL': address_octets+=1
        clocks=e.get('transfer_bits_bound')
        if not integer(clocks) or clocks<9*(max(0,payload_bytes)+address_octets): errors.append('transfer_bits_bound')
        for key in ('start_stop_bound_us','clock_stretch_limit_us'):
            if not number(e.get(key)) or e[key]<0: errors.append(key)
        if number(e.get('start_stop_bound_us')):
            # At least one start and final stop; combined reads need repeated START.
            limits=TIMING.get(mode)
            minimum=(limits['start_hold']+limits['stop_setup'])/1000 if limits else 0.32
            if direction=='BIDIRECTIONAL' or direction=='READ' and e.get('address_bits')==10:
                minimum+=(limits['start_setup']+limits['start_hold'])/1000 if limits else 0.32
            if e['start_stop_bound_us']<minimum: errors.append('start_stop_bound_us')
        arb=e.get('arbitration_bound_us')
        if multi is True and arb is None or arb is not None and (not number(arb) or arb<0): errors.append('arbitration_bound_us')
        if mode=='ULTRA_FAST':
            if direction!='WRITE': errors.append('transfer_direction')
            if multi is not False: errors.append('multi_master')
            if e.get('clock_stretch_limit_us')!=0: errors.append('clock_stretch_limit_us')
            if arb not in (None,0): errors.append('arbitration_bound_us')
        if mode=='HIGH_SPEED':
            er=e.get('hs_entry_rate_bps');bound=e.get('hs_entry_bound_us');cap=e.get('bus_cap_pf')
            if not number(er) or not 0<er<=400000: errors.append('hs_entry_rate_bps')
            if not number(bound) or number(er) and er>0 and bound<9/er*1e6: errors.append('hs_entry_bound_us')
            if not number(cap) or not 0<=cap<=400: errors.append('bus_cap_pf')
            if cap==400 and number(rate) and rate>1700000: errors.append('bitrate_bps')
            if not isinstance(e.get('hs_clock_timing_source'),str) or not e['hs_clock_timing_source'].strip(): errors.append('hs_clock_timing_source')
    return list(dict.fromkeys(errors))
