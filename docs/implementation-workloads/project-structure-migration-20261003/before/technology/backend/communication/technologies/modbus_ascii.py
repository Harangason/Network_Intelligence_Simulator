"""Modbus ASCII serial V1.02 parameters; not RTU CRC/gap or TCP MBAP."""
SERIAL='https://www.modbus.org/file/secure/modbusoverserial.pdf'
APP='https://www.modbus.org/file/secure/modbusprotocolspecification.pdf'
SOURCES={SERIAL:'Modbus Serial Line V1.02 December20 2006 sections2.1-2.6/3.2-3.6/5/AppendixB; ASCII optional regular class, not obsolete1996 guide',
 APP:'Modbus Application Protocol V1.1b3 April26 2012 sections4-7; industry-neutral PDU/function/addressing, actual manufacturer object mapping remains required'}
PUBLIC=[1,2,3,4,5,6,7,8,11,12,15,16,17,20,21,22,23,24,43]
USER=list(range(65,73))+list(range(100,111))
DIAG=[0,1,2,3,4,*range(10,19),20]
DECLARATIONS=[]
def d(key,kind,meaning,lo=None,hi=None,unit=None,options=None,source=SERIAL,**kw):
    DECLARATIONS.append(dict(key='ma_'+key,type=kind,description=meaning,min=lo,max=hi,unit=unit,options=options,
      source=source,source_revision=SOURCES[source],**kw))
for key,meaning,options,source in [
 ('profile','Actual standard serial V1.02 implementation or explicitly registered extension.',['V1_02','REGISTERED'],SERIAL),
 ('implementation_class','Actual ASCII requires Regular class; Basic implements RTU only.',['BASIC','REGULAR','REGISTERED'],SERIAL),
 ('mode','Actual ASCII transmission; RTU is generic device factory mode, not selected ASCII mode.',['ASCII','REGISTERED'],SERIAL),
 ('role','Actual serial bus master initiates one transaction; slave owns unique address.',['MASTER','SLAVE','REGISTERED'],SERIAL),
 ('phy','Actual separately qualified RS485 two/four wire or point-to-point RS232; four-wire multipoint is not RS422.',['RS485_2W','RS485_4W','RS232','REGISTERED'],SERIAL),
 ('parity','Actual matching device serial parity; EVEN default, NONE needs two stops.',['EVEN','ODD','NONE'],SERIAL),
 ('exchange','Actual serial unicast request/reply or broadcast write without reply.',['UNICAST','BROADCAST'],SERIAL),
 ('phase','Actual request/normal response/exception; function namespace and PDU length depend phase.',['REQUEST','RESPONSE','EXCEPTION'],APP),
 ('function_kind','Actual public assigned versus user-defined or registered extension function.',['PUBLIC','USER_DEFINED','REGISTERED'],APP),
 ('termination','Actual per-pair termination method; resistor150 or polarization-qualified RC120/1nF.',['RESISTOR','SERIES_RC','NONE','REGISTERED'],SERIAL),
 ('cable','Actual cable qualification, not a universal length at any baud rate.',['AWG26_OR_WIDER','CAT5','REGISTERED'],SERIAL),
 ('word_order','Actual multi-register vendor type/word order; standard big endian applies within a16bit register.',['DEVICE_SPECIFIC','REGISTERED'],APP),
 ]:d(key,'select',meaning,options=options,source=source)
for key,meaning,source in [
 ('revision','Actual standard/device/firmware revisions, independent of application industry.',SERIAL),
 ('network_id','Actual canonical serial bus identity and master/slave ownership.',SERIAL),
 ('binding_source','Actual selected serial interfaces, mode, parity, baud and physical path.',SERIAL),
 ('device_source','Actual slave firmware/capabilities/address and master configuration.',SERIAL),
 ('rate_source','Actual supported and calibrated baud rate; optional rates not globally capped115200.',SERIAL),
 ('physical_source','Actual cable, common, shielding, termination, bias, unit load, topology and repeaters.',SERIAL),
 ('codec_source','Actual binary PDU/ASCII hex/LRC/colon/CR/delimiter and complete encoded frame.',APP),
 ('mapping_source','Actual coil/register/object namespace, zero-based PDU address and vendor multiword types.',APP),
 ('schedule_source','Actual one-master transactions, replies/no-replies, gaps, timers, retries and processing bounds.',SERIAL),
 ('capacity_source','Actual request/reply serialized lengths, per-character gaps and complete schedule.',SERIAL),
 ('acceptance_source','Actual application functional timing/freshness/security/safety acceptance; LRC not safety certificate.',APP),
 ('registered_source','Actual registered nonstandard mode/PHY/function/codec/qualification.',SERIAL),
 ('timer_source','Actual configured long inter-character or response/turnaround/retry timers.',SERIAL),
 ('delimiter_source','Actual FC8/subfunction3 changed LF agreement at all selected endpoints.',APP),
 ('device_limit_source','Actual manufacturer unit-load/polarization qualified maximum without repeater.',SERIAL),
 ('function_source','Actual supported public/user-defined function, diagnostics/MEI or variable file/event codec.',APP),
 ]:d(key,'text',meaning,source=source)
d('hex_body','text','Actual uppercase hexadecimal address/PDU/LRC octets before colon/CR/LF; even6..510characters, not raw binary bytes.',
  pattern=r'(?:[0-9A-F]{2}){3,255}',min_length=6,max_length=510)
for key,meaning,lo,hi,unit,source in [
 ('data_bits','Actual ASCII character contains7data bits, unlike RTU8.',7,7,'bit',SERIAL),
 ('start_bits','Actual asynchronous start bit per ASCII character.',1,1,'bit',SERIAL),
 ('stop_bits','Actual1with parity or2without, keeping10wire bits.',1,2,'bit',SERIAL),
 ('character_bits','Actual10total bits per ASCII character, including start/parity/stop.',10,10,'bit',SERIAL),
 ('destination_address','Actual addressed slave1..247 or broadcast0; master has no own serial address.',0,247,None,SERIAL),
 ('slave_address','Actual slave node unique own1..247address, not fabricated master address.',1,247,None,SERIAL),
 ('active_masters','Actual one serial master at a time, no CAN contention or parallel requests.',1,1,None,SERIAL),
 ('outstanding','Actual master one pending transaction, distinct Modbus TCP concurrency.',1,1,None,SERIAL),
 ('function','Actual transmitted function1..127 or exceptionoriginal+128;0invalid.',1,255,None,APP),
 ('request_function','Actual correlated original request code, not high-bit exception opcode.',1,127,None,APP),
 ('exception_code','Actual defined application exception1..6/8/10/11; not malformed-frame reply.',1,255,None,APP),
 ('diagnostic','Actual FC8 subfunction;5..9/19/21+reserved.',0,65535,None,APP),
 ('mei_type','Actual FC43 public MEI13/14; CANopen embedded payload is not CAN bus selection.',0,255,None,APP),
 ('pdu_bytes','Actual binary function-plus-data PDU1..253, before serial address/LRC/ASCII expansion.',1,253,'byte',APP),
 ('data_bytes','Actual complete function-specific binary PDU data0..252, including fields/metadata.',0,252,'byte',APP),
 ('frame_chars','Actual ASCII frame=2*(PDU+address1+LRC1)+colon1+CR/LF2; maximum513.',9,513,'character',SERIAL),
 ('hex_chars','Actual encoded address/PDU/LRC body length, excluding3delimiter characters.',6,510,'character',SERIAL),
 ('serial_bits','Actual total asynchronous wire bits=10*ASCII frame characters; gaps separate.',90,5130,'bit',SERIAL),
 ('colon','Actual ASCII start delimiter0x3A, not ASCII hex text encoded address.',58,58,None,SERIAL),
 ('cr','Actual carriage-return delimiter0x0D.',13,13,None,SERIAL),
 ('lf','Actual0x0Adefault or documented changed7bit delimiter.',0,127,None,SERIAL),
 ('lrc','Actual8bit LRC two-complement sum of binary address/PDU before ASCII encoding; excludes delimiters.',0,255,None,SERIAL),
 ('binary_sum','Actual unsigned sum of address/function/data octets, excluding LRC/colon/CR/LF.',0,None,None,SERIAL),
 ('start_address','Actual zero-based16bit coil/register address, not human40001 reference.',0,65535,None,APP),
 ('quantity','Actual function-dependent coil/register quantity, not generic payload byte count.',1,2000,None,APP),
 ('byte_count','Actual function-specific data byte count; coil packing ceil(quantity/8) vs register2*quantity.',0,255,'byte',APP),
 ('coil_value','Actual FC5 off0000/onFF00, not scalar boolean1.',0,65535,None,APP),
 ('register_value','Actual16bit FC6 register value, most-significant octet first.',0,65535,None,APP),
 ('register_bits','Actual one MODBUS register16bits; float/multiword mapping device-specific.',16,16,'bit',APP),
 ('read_quantity','Actual FC23 register read1..125, separate write1..121.',1,125,None,APP),
 ('write_quantity','Actual FC23 write register count1..121, separate FC16 max123.',1,121,None,APP),
 ('write_start_address','Actual FC23 separate zero-based write address.',0,65535,None,APP),
 ('write_byte_count','Actual FC23 two octets per written register.',0,242,'byte',APP),
 ('devices','Actual master-plus-slave physical device count without repeaters; unit loads differ addresses.',2,248,None,SERIAL),
 ('device_limit','Actual documented devices without repeater;32standard baseline, bias reduces4.',2,248,None,SERIAL),
 ('terminations_per_pair','Actual RS485 termination at both trunk ends, none on drops; RS232none.',0,2,None,SERIAL),
 ('polarization_locations','Actual bias at one location if required, not all nodes.',0,1,None,SERIAL),
 ('tap_derivations','Actual number of derivations at a multiport tap, bound40m/n.',1,None,None,SERIAL),
 ]:d(key,'number',meaning,lo,hi,unit,source=source,integer=True)
for key,meaning,lo,hi,unit in [
 ('character_time_us','Actual10bits divided by selected baud; processing/gaps separate.',0,None,'us'),
 ('serialization_us','Actual complete ASCII wirebits divided by selected baud; excludes gap/turnaround.',0,None,'us'),
 ('interchar_timeout_ms','Actual1000ms ASCII baseline; documented user configuration can increase, not RTU1.5chars.',1,None,'ms'),
 ('interchar_gap_bound_ms','Actual worst-case inter-character idle must fit configured timeout.',0,None,'ms'),
 ('response_timeout_ms','Actual application/device response timeout, no universal1000ms orCANretry.',0,None,'ms'),
 ('turnaround_ms','Actual broadcast processing wait before next request, not automatic100mscapacity.',0,None,'ms'),
 ('tx_baud_bps','Actual observed transmitter baud respects better than1percent error.',0,None,'bit/s'),
 ('rx_tolerance_percent','Actual receiver must accept2percent rate error, not clock drift20ppm.',2,None,'%'),
 ('trunk_m','Actual trunk length depends rate, cable and loads;1000m only qualified<=9600/AWG26.',0,None,'m'),
 ('drop_m','Actual derivation length<=20m and<=40m/n for multiporttap.',0,20,'m'),
 ('termination_ohm','Actual per-end resistor150 or RC120 suggested, not universal installed hardware.',0,None,'ohm'),
 ('termination_w','Actual termination resistor power;150ohm.5W orRC120ohm.25W proposals.',0,None,'W'),
 ('termination_cap_nf','Actual series RC capacitor1nF suggestion, not parallel bus load.',0,None,'nF'),
 ('termination_cap_v','Actual seriesRC capacitor rating at least10V.',0,None,'V'),
 ('bias_ohm','Actual pullup/pulldown450..650ohm when polarization required.',0,None,'ohm'),
 ('bias_v','Actual polarization5V, not optional node auxiliary5..24Vsupply.',0,None,'V'),
 ('rs232_cap_pf','Actual RS232 wire capacitance to ground maximum2500pF.',0,None,'pF'),
 ]:d(key,'number',meaning,lo,hi,unit)
for key,meaning in [
 ('reply_expected','Actual broadcast has no reply; diagnostic listen-only and frame errors differ normalunicast.'),
 ('changed_delimiter','Actual nondefault LF configured by documented diagnostic command.'),
 ('listen_only','Actual addressed slave listen-only state; only restart command processed, no reply.'),
 ('polarization','Actual device requires and bus implements single-location polarization.'),
 ('common','Actual common third/fifth conductor implemented, independent cable shield.'),
 ('shielded','Actual serial cable shielded and protective-ground arrangement.'),
 ('four_wire_as_two','Actual 4W used2W modified wiring halves qualified maximum length.'),
 ('repeater','Actual repeaters create separately qualified segments and latency.'),
 ]:d(key,'boolean',meaning)

REQUIRED=['profile','implementation_class','mode','role','phy','parity','data_bits','start_bits','stop_bits','character_bits',
 'revision','network_id','binding_source','device_source',
 'rate_source','physical_source','codec_source','mapping_source','schedule_source','capacity_source','acceptance_source']
REMOVED={k:'Modbus ASCII has no universal '+k+'; actual serial master schedule, device timers/retries and physical path replace inherited CAN/IP policy.'for k in
 ('queue_size','queue_policy','qos_priority','traffic_class','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
 'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
 'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}

def semantics():
    rules=[dict(parameter='local_timing_evidence',allowed=[],source=SERIAL,source_revision=SOURCES[SERIAL])]
    def r(key,when=None,source=SERIAL,**kw):
        rules.append(dict(parameter=key if key in('payload_bytes','bitrate_bps')else'ma_'+key,
          when={'ma_'+k:v for k,v in(when or{}).items()},source=source,source_revision=SOURCES[source],**kw))
    for key in ('profile','implementation_class','mode','role','phy','function_kind','termination','cable','word_order'):
        r('registered_source',{key:'REGISTERED'},required=True)
    standard={'profile':'V1_02'};r('implementation_class',standard,allowed=['REGULAR'])
    r('mode',standard,allowed=['ASCII'])
    for parity in ('EVEN','ODD','NONE'):r('stop_bits',{'parity':parity},allowed=[2 if parity=='NONE'else 1])
    r('slave_address',{'role':'SLAVE'},required=True);r('slave_address',{'role':'MASTER'},allowed=[])
    for ex in ('UNICAST','BROADCAST'):
        w={'exchange':ex};r('destination_address',w,minimum=1 if ex=='UNICAST'else 0,maximum=247 if ex=='UNICAST'else 0,required=True)
    r('phase',{'exchange':'BROADCAST'},allowed=['REQUEST'])
    r('reply_expected',{'exchange':'BROADCAST'},allowed=[False])
    r('request_function',{'exchange':'BROADCAST'},allowed=[5,6,8,15,16,21,22],source=APP)
    r('diagnostic',{'exchange':'BROADCAST','request_function':8},allowed=[1,3,4,10,20],source=APP)
    r('reply_expected',{'listen_only':True},allowed=[False],source=APP)
    r('reply_expected',{'request_function':8,'diagnostic':4},allowed=[False],source=APP)
    r('reply_expected',{'exchange':'UNICAST','listen_only':False},when_not={'ma_diagnostic':4},allowed=[True],source=APP)
    r('request_function',{'function_kind':'PUBLIC'},allowed=PUBLIC,source=APP)
    r('request_function',{'function_kind':'USER_DEFINED'},allowed=USER,source=APP)
    r('function_source',{'function_kind':'USER_DEFINED'},required=True,source=APP)
    r('function_kind',when_present=['ma_request_function'],required=True,source=APP)
    for key in ('request_function','phase'):r(key,when_present=['ma_function'],required=True,source=APP)
    r('function',{'phase':'REQUEST'},equal_parameter='ma_request_function',source=APP)
    r('function',{'phase':'RESPONSE'},equal_parameter='ma_request_function',source=APP)
    r('function',{'phase':'EXCEPTION'},equal_parameter='ma_request_function',equal_parameter_offset=128,source=APP)
    r('exception_code',{'phase':'EXCEPTION'},allowed=[1,2,3,4,5,6,8,10,11],required=True,source=APP)
    r('pdu_bytes',{'phase':'EXCEPTION'},allowed=[2],source=APP)
    r('diagnostic',{'request_function':8},allowed=DIAG,required=True,source=APP)
    r('mei_type',{'request_function':43},allowed=[13,14],required=True,source=APP)
    r('function_source',{'request_function':43},required=True,source=APP)
    r('pdu_bytes',equal_expression={'sum':['ma_data_bytes',1]},source=APP,exact_decimal_equality=True)
    r('payload_bytes',equal_parameter='ma_data_bytes',source=APP)
    r('frame_chars',equal_expression={'sum':[{'product':[2,{'sum':['ma_pdu_bytes',2]}]},3]},exact_decimal_equality=True)
    r('pdu_bytes',when_present=['ma_frame_chars'],required=True,source=APP)
    r('hex_chars',equal_expression={'product':[2,{'sum':['ma_pdu_bytes',2]}]},exact_decimal_equality=True)
    r('hex_body',text_encoding='ascii',encoded_bytes_parameter='ma_hex_chars')
    r('hex_chars',when_present=['ma_hex_body'],required=True)
    r('serial_bits',equal_expression={'product':['ma_frame_chars',10]},exact_decimal_equality=True)
    r('frame_chars',when_present=['ma_serial_bits'],required=True)
    for key,expr in [('character_time_us',{'product':[10000000,{'power':['bitrate_bps',-1]}]}),
      ('serialization_us',{'product':['ma_serial_bits',1000000,{'power':['bitrate_bps',-1]}]})]:r(key,equal_expression=expr)
    r('lrc',equal_expression={'integer_remainder':[{'subtract':[256,{'integer_remainder':['ma_binary_sum',256]}]},256]},exact_decimal_equality=True)
    r('binary_sum',when_present=['ma_lrc'],required=True)
    r('lf',{'changed_delimiter':False},allowed=[10])
    r('delimiter_source',{'changed_delimiter':True},required=True,source=APP)
    r('changed_delimiter',when_present=['ma_lf'],required=True)
    r('interchar_gap_bound_ms',maximum_parameter='ma_interchar_timeout_ms')
    r('interchar_timeout_ms',when_present=['ma_interchar_gap_bound_ms'],required=True)
    r('timer_source',when_greater_than={'ma_interchar_timeout_ms':1000},required=True)
    for key in ('response_timeout_ms','turnaround_ms'):r('timer_source',when_present=['ma_'+key],required=True)
    r('tx_baud_bps',exclusive_minimum_expression={'product':['bitrate_bps',.99]},exclusive_maximum_expression={'product':['bitrate_bps',1.01]},exact_decimal_bounds=True)
    for fc,maximum in [(1,2000),(2,2000),(3,125),(4,125),(15,1968),(16,123)]:
        w={'request_function':fc};r('quantity',w,maximum=maximum,source=APP)
        r('quantity',w,when_present=['ma_byte_count'],required=True,source=APP)
        r('quantity',w,when_present=['ma_pdu_bytes'],when_not={'ma_phase':'EXCEPTION'},required=True,source=APP)
        r('start_address',w,maximum_expression={'subtract':[65536,'ma_quantity']},source=APP)
        r('quantity',w,when_present=['ma_start_address'],required=True,source=APP)
        request={**w,'phase':'REQUEST'};response={**w,'phase':'RESPONSE'}
        if fc<=4:
            r('pdu_bytes',request,allowed=[5],source=APP)
            expr={'ceiling':[{'product':['ma_quantity',.125]}]}if fc<=2 else{'product':['ma_quantity',2]}
            r('byte_count',response,equal_expression=expr,source=APP,exact_decimal_equality=True)
            r('byte_count',response,when_present=['ma_pdu_bytes'],required=True,source=APP)
            r('pdu_bytes',response,equal_expression={'sum':['ma_byte_count',2]},source=APP,exact_decimal_equality=True)
        else:
            expr={'ceiling':[{'product':['ma_quantity',.125]}]}if fc==15 else{'product':['ma_quantity',2]}
            r('byte_count',request,equal_expression=expr,source=APP,exact_decimal_equality=True)
            r('byte_count',request,when_present=['ma_pdu_bytes'],required=True,source=APP)
            r('pdu_bytes',request,equal_expression={'sum':['ma_byte_count',6]},source=APP,exact_decimal_equality=True)
            r('pdu_bytes',response,allowed=[5],source=APP)
    for fc in (5,6):
        for phase in ('REQUEST','RESPONSE'):r('pdu_bytes',{'request_function':fc,'phase':phase},allowed=[5],source=APP)
    r('coil_value',{'request_function':5},allowed=[0,65280],source=APP)
    for phase,count in [('REQUEST',1),('RESPONSE',2)]:r('pdu_bytes',{'request_function':7,'phase':phase},allowed=[count],source=APP)
    w={'request_function':23};r('write_byte_count',w,equal_expression={'product':['ma_write_quantity',2]},source=APP,exact_decimal_equality=True)
    r('pdu_bytes',{**w,'phase':'REQUEST'},equal_expression={'sum':['ma_write_byte_count',10]},source=APP,exact_decimal_equality=True)
    r('pdu_bytes',{**w,'phase':'RESPONSE'},equal_expression={'sum':[2,{'product':['ma_read_quantity',2]}]},source=APP,exact_decimal_equality=True)
    r('start_address',w,maximum_expression={'subtract':[65536,'ma_read_quantity']},source=APP)
    r('write_start_address',w,maximum_expression={'subtract':[65536,'ma_write_quantity']},source=APP)
    for key,functions in {'coil_value':[5],'register_value':[6],'read_quantity':[23],'write_quantity':[23],
      'write_start_address':[23],'write_byte_count':[23],'diagnostic':[8],'mei_type':[43],
      'quantity':[1,2,3,4,15,16]}.items():
        r('request_function',when_present=['ma_'+key],required=True,source=APP)
        for fc in set(PUBLIC+USER)-set(functions):r(key,{'request_function':fc},allowed=[],source=APP)
    for phy in ('RS485_2W','RS485_4W'):
        w={'phy':phy};r('common',w,allowed=[True]);r('shielded',w,allowed=[True]);r('terminations_per_pair',w,allowed=[2])
        r('devices',w,maximum_parameter='ma_device_limit')
        r('device_limit',w,when_present=['ma_devices'],required=True)
        r('device_limit_source',w,when_greater_than={'ma_device_limit':32},required=True)
        r('device_limit_source',{**w,'polarization':True},when_greater_than={'ma_device_limit':28},required=True)
        r('polarization_locations',{**w,'polarization':True},allowed=[1]);r('bias_ohm',{**w,'polarization':True},minimum=450,maximum=650)
        r('bias_v',{**w,'polarization':True},allowed=[5])
        r('polarization_locations',{**w,'polarization':False},allowed=[0])
        r('termination',w,forbidden=['NONE'])
    r('terminations_per_pair',{'phy':'RS232'},allowed=[0]);r('termination',{'phy':'RS232'},allowed=['NONE'])
    r('devices',{'phy':'RS232'},allowed=[2]);r('rs232_cap_pf',{'phy':'RS232'},maximum=2500)
    r('shielded',{'phy':'RS232'},allowed=[True]);r('common',{'phy':'RS232'},allowed=[True])
    for key in ('bias_ohm','bias_v','polarization_locations','termination_ohm','termination_w','termination_cap_nf','termination_cap_v'):
        r(key,{'phy':'RS232'},allowed=[])
    for phy in ('RS485_2W','RS485_4W'):r('rs232_cap_pf',{'phy':phy},allowed=[])
    r('termination_cap_v',{'termination':'SERIES_RC'},minimum=10)
    r('trunk_m',{'cable':'CAT5'},maximum=600)
    for wiring,length in [(False,1000),(True,500)]:r('trunk_m',{'cable':'AWG26_OR_WIDER','four_wire_as_two':wiring},
      when_ranges={'bitrate_bps':[1,9600]},maximum=length)
    r('drop_m',maximum_expression={'product':[40,{'power':['ma_tap_derivations',-1]}]})
    return dict(rate_model={'type':'SINGLE_BITRATE','fields':['bitrate_bps'],'minimum_bps':1},
      required_parameters=['bitrate_bps',*['ma_'+k for k in REQUIRED]],native_parameter_prefixes=['ma_'],
      parameter_evidence_scope='EXPLICIT_LAYER',parameter_constraints=rules,
      mechanisms={'encoding':['ASCII_UPPERCASE_HEX_7_DATA_BITS_10_SERIAL_BITS'],
      'integrity':['LRC_BINARY_TWOS_COMPLEMENT_NOT_RTU_CRC'],
      'timing':['ONE_MASTER_ONE_TRANSACTION','ASCII_INTERCHAR_TIMER_NOT_RTU_SILENCE'],
      'physical':['EXPLICIT_RS485_2W_4W_OR_RS232_NOT_CAN_OR_ETHERNET']})

def fields():
    result=[]
    proposals={'data_bits':7,'start_bits':1,'character_bits':10,'active_masters':1,'outstanding':1,
      'colon':58,'cr':13,'register_bits':16,'interchar_timeout_ms':1000,'parity':'EVEN'}
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items()if v is not None};key=spec['key'].removeprefix('ma_')
        item.update(label=key.replace('_',' '),category='physical'if spec['source']==SERIAL else'encoding',scope='network',
          editable=True,required=key in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',
          validation_relevant=True,simulation_relevant=False)
        conditional=[]
        if key in proposals:conditional=[dict(when={'ma_profile':'V1_02'},value=proposals[key])]
        if key=='stop_bits':conditional=[dict(when={'ma_parity':p},value=2 if p=='NONE'else 1)for p in ('EVEN','ODD','NONE')]
        if key=='lf':conditional=[dict(when={'ma_changed_delimiter':False},value=10)]
        if key in ('device_limit','terminations_per_pair'):
            for phy in ('RS485_2W','RS485_4W'):
                for bias in (False,True):conditional.append(dict(when={'ma_phy':phy,'ma_polarization':bias},value=(28 if bias else 32)if key=='device_limit'else 2))
        if key in ('termination_ohm','termination_w','termination_cap_nf','termination_cap_v'):
            vals={'termination_ohm':{'RESISTOR':150,'SERIES_RC':120},'termination_w':{'RESISTOR':.5,'SERIES_RC':.25},
              'termination_cap_nf':{'SERIES_RC':1},'termination_cap_v':{'SERIES_RC':10}}
            conditional=[dict(when={'ma_phy':phy,'ma_termination':method},value=value)for phy in ('RS485_2W','RS485_4W')for method,value in vals[key].items()]
        if conditional:
            for c in conditional:c.update(source=spec['source'],source_revision=spec['source_revision'])
            item.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=conditional)
        result.append(item)
    return result
