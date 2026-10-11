"""Source-qualified 1-Wire slots/devices; host bridges are separate buses."""
AN='https://www.analog.com/en/resources/technical-articles/1wire-communication-through-software.html'
STYLE='https://www.analog.com/en/resources/app-notes/reading-and-writing-1wirereg-devices-through-serial-interfaces.html'
TEMP='https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf'
MASTER='https://www.analog.com/media/en/technical-documentation/data-sheets/DS2482-100.pdf'
ID='https://www.analog.com/media/en/technical-documentation/data-sheets/DS1990A.pdf'
SOURCES={AN:'ADI AN126 May30,2002 timing Table2 and Example1 differ in overdrive A/E. Separate source-qualified recipes; neither nominal16.3kbps nor a software delay alone is a capacity proof.',
 STYLE:'ADI Reading and Writing1-Wire Devices Through Serial Interfaces: legacy time-slot excludes recovery, new style includes it; half-duplex single-master open-drain and load/threshold effects.',
 TEMP:'DS18B20 Rev6, printed7/19 (product publication2019-08-09). DC/AC tables, ROM/scratchpad/CRC/configuration, power and transaction sections read via publisher PDF extraction.',
 MASTER:'DS2482-100 Rev11 8/24. DC/timing tables and footnotes, registers, commands, hostI2C/1-Wire bit order. Narrative within65us conflicts table65.8..72.8; explicit electrical table controls proposed timing.',
 ID:'DS1990A/DS1990AA publisher data sheet Rev11/21, product listing Rev4. Distinct A/AA recovery, supply, reset, ROM commands and CRC; not universal old-device values.'}
DECLARATIONS=[]

def d(k,t,meaning,lo=None,hi=None,u=None,opts=None,src=AN,integer=False):
 DECLARATIONS.append(dict(key='ow_'+k,type=t,description=meaning,min=lo,max=hi,unit=u,options=opts,source=src,source_revision=SOURCES[src],integer=integer))

for k,meaning,opts,src in[
 ('mode','Actual selected1-Wire timing mode, not hostI2C/UART baud. Standard is unconfirmed baseline; overdrive requires every addressed device capability and valid transition.',['STANDARD','OVERDRIVE'],STYLE),
 ('role','Actual physical master versus selected target; master needs no invented slave ROM address.',['MASTER','TARGET'],STYLE),
 ('master','Actual identified timing implementation; AN126 table and software example differ for overdrive.',['SOFTWARE_AN126_TABLE','SOFTWARE_AN126_CODE','DS2482_100_REV11','REGISTERED'],AN),
 ('device','Actual selected target model/revision; REGISTERED requires its own capabilities and limits.',['DS18B20_REV6','DS1990A_2021','DS1990AA_2021','REGISTERED'],TEMP),
 ('slot_style','Actual period includes recovery or legacy active slot excludes recovery. Never add recovery twice.',['INCLUDES_RECOVERY','EXCLUDES_RECOVERY'],STYLE),
 ('rom_command','Actual ROM phase. Search enumerates one ROM per full64-triplet pass, not all devices in one pass.',['READ_ROM','MATCH_ROM','SKIP_ROM','SEARCH_ROM','ALARM_SEARCH','OVERDRIVE_SKIP','OVERDRIVE_MATCH','REGISTERED'],TEMP),
 ('function','Actual target operation after ROM selection; DS1990A has no thermometer scratchpad.',['NONE','CONVERT_T','READ_SCRATCHPAD','WRITE_SCRATCHPAD','COPY_SCRATCHPAD','RECALL_E2','READ_POWER','REGISTERED'],TEMP),
 ('power','Actual external supply versus parasitic bus power, not assumed from two-wire appearance.',['EXTERNAL','PARASITIC','REGISTERED'],TEMP),
 ('pullup_scope','Actual qualified weakpullup arrangement. Datasheet resistor limits apply to one target at minimumrecovery, not arbitrarymultidrop/load/longrecovery.',['SINGLE_MIN_RECOVERY','ACTUAL_QUALIFIED'],ID),
 ('outcome','Actual functional outcome distinct reset presence and checksum validity.',['ACCEPTED','REJECTED','PENDING','UNKNOWN'],TEMP),
]:d(k,'select',meaning,opts=opts,src=src)
for k,meaning,src in[
 ('device_source','Actual target identities, firmware/revision and device-specific capability/timing evidence.',TEMP),
 ('master_source','Actual master, bridge/driver, configured timing and bounded interruption evidence.',AN),
 ('physical_source','Actual topology/load, pullup, rise/fall, thresholds and operating rails/temperature evidence.',STYLE),
 ('schedule_source','Actual ROM/function/payload/polling/reset/recovery/conversion/retry traffic and service bounds.',STYLE),
 ('acceptance_source','Actual correlated result, data age and functional acceptance evidence.',TEMP),
 ('registered_source','Actual registered implementation/device/function specification, not genericCAN/I2C fallback.',STYLE),
 ('rom_hex','Actual64-bit ROM as eight wire-order octets: family first, six serial bytes, CRC last; not JavaScript floating number.',TEMP),
 ('scratch_hex','Actual nine-byteDS18B20 scratchpad in wire octet order including finalCRC.',TEMP),
 ('bus_id','Actual physical1-Wire segment identity, independent its host bridgeI2C segment.',STYLE),
]:d(k,'text',meaning,src=src)
for k,meaning,lo,hi,u,integer,src in[
 ('nominal_bps','Literature mode label16.3kbps for standard, not reciprocal of every implementation slot or actual serialization guarantee.',1,None,'bit/s',False,STYLE),
 ('master_count','Actual masters on this physical1-Wire segment; source protocol has one master.',1,1,None,True,STYLE),
 ('target_count','Actual discovered targets on this physical segment; not universal255 addressing limit.',1,None,None,True,STYLE),
 ('rom_bytes','Actual transmitted ROM octets;64bits is8octets.',8,8,'byte',True,TEMP),
 ('rom_family','Actual first ROM octet, DS18B20 family28hex versus DS1990A01hex.',0,255,None,True,TEMP),
 ('rom_crc','Actual transmitted finalROM CRC8 byte, not CRC16 or a claimedvalid boolean.',0,255,None,True,TEMP),
 ('scratch_bytes','Actual selectedDS18B20 scratchpad octets includingCRC.',9,9,'byte',True,TEMP),
 ('scratch_crc','Actual last scratchpadCRC8 byte over previous eight bytes.',0,255,None,True,TEMP),
 ('rom_opcode','Actual one-byte ROM command, LSB-first bits.',0,255,None,True,TEMP),
 ('function_opcode','ActualDS18B20 function command, not universal1-Wire opcode.',0,255,None,True,TEMP),
 ('search_passes','Actual completed ROM search paths; enumeration repeats per discovered identity.',0,None,None,True,ID),
 ('search_slots','Actual searchbit-triplet slots excluding reset/ROM command,64*3 per completed path.',0,None,None,True,ID),
 ('slot_us','Actual data slot tSLOT according to selected timing style, separate recovery when excluded.',0,None,'us',False,STYLE),
 ('period_us','Actual data start-to-start period, including recovery exactly once.',0,None,'us',False,STYLE),
 ('recovery_us','Actual high recovery, respecting every target and actual capacitive load.',0,None,'us',False,STYLE),
 ('write_one_us','Actual write-one low duration; edge/rise allowance must meet target thresholds.',0,None,'us',False,AN),
 ('write_zero_us','Actual write-zero low duration, not complete transaction.',0,None,'us',False,AN),
 ('read_low_us','Actual master read initiation low duration before release.',0,None,'us',False,AN),
 ('read_sample_us','Actual read sample from start of slot; load/rise must settle before sampling.',0,None,'us',False,AN),
 ('read_after_release_us','Actual software delay after releasing read line until sampling, not absolute sample instant.',0,None,'us',False,AN),
 ('reset_low_us','Actual reset low; long standard reset exits overdrive; device-specific upper constraints.',0,None,'us',False,STYLE),
 ('reset_high_us','Actual reset release-to-next-command high interval including presence and recovery.',0,None,'us',False,AN),
 ('presence_sample_us','Actual masterpresence sample after release, separate slavepresence delay.',0,None,'us',False,AN),
 ('presence_delay_us','Actual targetpresence low start after resetrelease.',0,None,'us',False,TEMP),
 ('presence_low_us','Actual targetpresence low duration after that delay.',0,None,'us',False,TEMP),
 ('rise_us','Actual released line threshold-crossing bound under all topology/loading conditions.',0,None,'us',False,STYLE),
 ('fall_us','Actual driven-low threshold-crossing bound; software delay is not proof of edge.',0,None,'us',False,STYLE),
 ('data_slots','Actual data bits transferred for selected byte stream, excludes reset/ROM/search unless explicitly accounted.',0,None,None,True,STYLE),
 ('data_bytes','Actual byte stream length for data_slots=8*data_bytes; no universal255 payload.',0,None,'byte',True,STYLE),
 ('transfer_bound_us','Actual bounded complete transaction including ROM/function/reset/host/interrupt/recovery/polls, not data-only slots.',0,None,'us',False,STYLE),
 ('interrupt_bound_us','Actual source-qualified scheduling interruption bound, no automaticzero.',0,None,'us',False,AN),
 ('resolution','ActualDS18B20 EEPROM-selected9..12-bit resolution; power-oninitial12 is proposal only.',9,12,'bit',True,TEMP),
 ('conversion_bound_ms','Declared worst-caseDS18B20 conversion wait for actualresolution, separate wire occupied time.',0,None,'ms',False,TEMP),
 ('strong_on_us','Actual latency enabling strongpullup after ConvertT/CopyScratchpad, max10us for parasiticDS18B20.',0,None,'us',False,TEMP),
 ('strong_hold_ms','Actual uninterrupted strongpullup hold, parasiticconversion orEEPROM write; blocks otherbusactivity.',0,None,'ms',False,TEMP),
 ('copy_bound_ms','DeclaredDS18B20 EEPROM write wait,10ms maximum source-bound not generic retry delay.',0,None,'ms',False,TEMP),
 ('target_v','Actual selectedtarget operating rail, not absolute maximum or universaldevicevoltage.',0,None,'V',False,TEMP),
 ('target_temperature_c','Actual selectedtarget operatingtemperature; thermometeraccuracy range narrower.',None,None,'degC',False,TEMP),
 ('pullup_ohm','Actual weakpullup resistance under selecteddevice/load, no universal4.7k for all masters.',0,None,'ohm',False,STYLE),
 ('load_pf','Actual whole1-Wire load including wiring/device capacitance, not individualstartupstoragecap.',0,None,'pF',False,MASTER),
 ('master_v','ActualDS2482 operatingrail2.9..5.5, not absolute6V or targetrail.',0,None,'V',False,MASTER),
 ('master_temperature_c','ActualDS2482 ambient -40..85, not storage125 orjunction150.',None,None,'degC',False,MASTER),
 ('host_i2c_bps','ActualDS2482 hostI2Cclock<=400k, independent1-Wire nominal16.3k andslots.',0,400000,'bit/s',False,MASTER),
 ('host_address','ActualDS2482 seven-bitI2Caddress selectedbyAD1/AD0, no invented1-Wire slaveaddress.',24,27,None,True,MASTER),
 ('host_ad0','Actual sampled addresspinAD0.',0,1,None,True,MASTER),
 ('host_ad1','Actual sampled addresspinAD1.',0,1,None,True,MASTER),
 ('bridge_config','ActualDS2482 lowfour configbits;bit1reserved0.',0,15,None,True,MASTER),
 ('bridge_config_write','ActualDS2482 configwritebyte highnibble complementlow, not sameas readregister upperzero.',0,255,None,True,MASTER),
 ('bridge_1ws','ActualDS2482 speedbit after targetoverdrive command, not support alone.',0,1,None,True,MASTER),
 ('age_ms','Actual correlatedsampleage, independent presence or transferCRC.',0,None,'ms',False,TEMP),
 ('freshness_limit_ms','Actual applicationacceptedage bound, no busstandard100ms.',0,None,'ms',False,TEMP),
]:d(k,'number',meaning,lo,hi,u,src=src,integer=integer)
for k,meaning,src in[
 ('all_overdrive_capable','Actual every addressedtarget andmaster supports selectedoverdrive.',STYLE),
 ('overdrive_transition','Actual standardreset plus overdriveROM command and speed-switch sequence completed.',AN),
 ('open_drain','Actual bus wired-AND open-drain interface, not push-pull driving high.',STYLE),
 ('lsb_first','Actual1-Wirebyte bitorderLSBfirst, independentI2CMSBfirst.',MASTER),
 ('presence','Actual resetpresence observation; not functional acceptance.',TEMP),
 ('short','ActualDS2482 shortdetected status, not assumedfalse from validsource.',MASTER),
 ('bridge_busy','ActualDS2482 1WB at moment of issuing nextcommand.',MASTER),
 ('active_pullup','ActualDS2482 APUconfiguration, not constantweakresistor.',MASTER),
 ('strong_pullup','Actual strongpowerdelivery enabledforparasiteoperation.',TEMP),
 ('activity_during_hold','Actual any other1-Wireactivityduring requiredstronghold; must befalse.',TEMP),
 ('data_accepted','Actual functionaldataacceptance, not CRC/presence.',TEMP),
]:d(k,'boolean',meaning,src=src)
REQUIRED=('mode','role','master','device','master_count','target_count','open_drain','lsb_first','device_source','master_source','physical_source','schedule_source','acceptance_source','bus_id')
REMOVED={k:'No universal1-Wire '+k+'; actual master/target slot, ROM, function and physical model replaces foreigntransport assumptions.'for k in('bitrate','mtu_bytes','duplex','vlan_id','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','rate_limit_bit_s','retry_limit','retransmission_enabled','retransmission_rate','retransmission_delay_ms','recovery_ms','link_fault_detect_ms','failover_ms','restore_delay_ms','mtbf_ms','sync_method')}
ROM_CODES=dict(READ_ROM=0x33,MATCH_ROM=0x55,SKIP_ROM=0xCC,SEARCH_ROM=0xF0,ALARM_SEARCH=0xEC,OVERDRIVE_SKIP=0x3C,OVERDRIVE_MATCH=0x69)
FUNC_CODES=dict(CONVERT_T=0x44,READ_SCRATCHPAD=0xBE,WRITE_SCRATCHPAD=0x4E,COPY_SCRATCHPAD=0x48,RECALL_E2=0xB8,READ_POWER=0xB4)
CONVERSIONS={9:93.75,10:187.5,11:375,12:750}
DS2482_TIMINGS={'STANDARD':dict(slot_us=(65.8,69.3,72.8),write_one_us=(7.6,8,8.4),read_low_us=(7.6,8,8.4),read_sample_us=(13.3,14,15),write_zero_us=(60,64,68),recovery_us=(5,5.3,5.6),reset_low_us=(570,600,630),reset_high_us=(554.8,584,613.2),presence_sample_us=(66.5,70,73.5)),
 'OVERDRIVE':dict(slot_us=(9.9,10.5,11),write_one_us=(.9,1,1.1),read_low_us=(.9,1,1.1),read_sample_us=(1.4,1.5,1.8),write_zero_us=(7.1,7.5,7.9),recovery_us=(2.8,3,3.2),reset_low_us=(68.4,72,75.6),reset_high_us=(70.3,74,77.7),presence_sample_us=(7.1,7.5,7.9))}
SOFTWARE={'STANDARD':dict(write_one_us=6,write_zero_us=60,read_low_us=6,read_after_release_us=9,read_sample_us=15,slot_us=70,reset_low_us=480,reset_high_us=480,presence_sample_us=70),
 'OVERDRIVE':dict(write_one_us=1,write_zero_us=7.5,read_low_us=1,read_after_release_us=1,read_sample_us=2,reset_low_us=70,reset_high_us=48.5,presence_sample_us=8.5)}

def semantics():
 rules=[]
 def r(k,w=None,src=AN,**kw):rules.append(dict(parameter=k if k in('bitrate_bps','local_timing_evidence','payload_bytes')else'ow_'+k,when={'ow_'+a:b for a,b in(w or{}).items()},source=src,source_revision=SOURCES[src],**kw))
 for k in REQUIRED:r(k,required=True)
 for k in('bitrate_bps','local_timing_evidence'):r(k,allowed=[])
 for k in('open_drain','lsb_first'):r(k,allowed=[True])
 for k in('master','device','rom_command','function','power'):r('registered_source',{k:'REGISTERED'},required=True,src=STYLE)
 for k in('all_overdrive_capable','overdrive_transition'):r(k,{'mode':'OVERDRIVE'},required=True,allowed=[True],src=STYLE)
 r('nominal_bps',{'mode':'STANDARD'},allowed=[16300],src=STYLE)
 for dev in('DS18B20_REV6','DS1990A_2021','DS1990AA_2021'):
  w={'device':dev};r('mode',w,allowed=['STANDARD'],src=TEMP if dev=='DS18B20_REV6'else ID)
  r('rom_family',w,allowed=[0x28 if dev=='DS18B20_REV6'else 1],src=TEMP if dev=='DS18B20_REV6'else ID)
 for k in('rom_hex','rom_crc','rom_family','rom_bytes'):r(k,{'role':'TARGET'},required=True,src=TEMP)
 r('rom_hex',pattern=r'[0-9A-Fa-f]{16}',hex_bytes_parameter='ow_rom_bytes',hex_crc8_maxim_parameter='ow_rom_crc',hex_crc8_prefix_bytes=7,hex_octets=[dict(offset=0,width=1,parameter='ow_rom_family'),dict(offset=7,width=1,parameter='ow_rom_crc')],src=TEMP)
 for k in('scratch_hex','scratch_crc','scratch_bytes'):r(k,when_present=['ow_scratch_hex'],required=True,src=TEMP)
 r('scratch_hex',pattern=r'[0-9A-Fa-f]{18}',hex_bytes_parameter='ow_scratch_bytes',hex_crc8_maxim_parameter='ow_scratch_crc',hex_crc8_prefix_bytes=8,hex_octets=[dict(offset=8,width=1,parameter='ow_scratch_crc')],src=TEMP)
 for k in('scratch_hex','resolution','conversion_bound_ms','copy_bound_ms','function_opcode'):
  r('device',when_present=['ow_'+k],allowed=['DS18B20_REV6'],src=TEMP)
 for cmd,code in ROM_CODES.items():r('rom_opcode',{'rom_command':cmd},allowed=[code],src=TEMP)
 r('target_count',{'rom_command':'READ_ROM'},allowed=[1],src=TEMP)
 r('rom_hex',{'rom_command':'MATCH_ROM'},required=True,src=TEMP)
 for dev in('DS1990A_2021','DS1990AA_2021'):
  r('rom_command',{'device':dev},allowed=['READ_ROM','SEARCH_ROM'],src=ID);r('function',{'device':dev},allowed=['NONE'],src=ID)
 r('search_slots',equal_expression={'product':['ow_search_passes',192]},src=ID)
 r('search_passes',when_present=['ow_search_slots'],required=True,src=ID)
 for func,code in FUNC_CODES.items():r('function_opcode',{'function':func},allowed=[code],src=TEMP);r('device',{'function':func},allowed=['DS18B20_REV6'],src=TEMP)
 for cmd in('OVERDRIVE_SKIP','OVERDRIVE_MATCH'):r('mode',{'rom_command':cmd},allowed=['OVERDRIVE']);r('all_overdrive_capable',{'rom_command':cmd},required=True,allowed=[True])
 for k in('slot_us','period_us','write_one_us','write_zero_us','read_low_us','read_sample_us','reset_low_us','reset_high_us','transfer_bound_us'):r(k,exclusive_minimum=0)
 r('slot_style',when_present=['ow_period_us'],required=True,src=STYLE)
 r('slot_us',when_present=['ow_period_us'],required=True,src=STYLE)
 r('period_us',{'slot_style':'INCLUDES_RECOVERY'},equal_parameter='ow_slot_us',src=STYLE)
 r('period_us',{'slot_style':'EXCLUDES_RECOVERY'},equal_expression={'sum':['ow_slot_us','ow_recovery_us']},src=STYLE)
 r('recovery_us',{'slot_style':'EXCLUDES_RECOVERY'},when_present=['ow_period_us'],required=True,src=STYLE)
 r('write_zero_us',maximum_parameter='ow_slot_us');r('read_sample_us',maximum_parameter='ow_slot_us')
 r('read_sample_us',minimum_expression={'sum':['ow_read_low_us','ow_rise_us']},src=STYLE)
 r('read_low_us',when_present=['ow_read_sample_us'],required=True)
 r('read_sample_us',equal_expression={'sum':['ow_read_low_us','ow_read_after_release_us']})
 for k in('read_sample_us','read_low_us'):r(k,when_present=['ow_read_after_release_us'],required=True)
 r('data_slots',equal_expression={'product':['ow_data_bytes',8]},src=STYLE);r('data_bytes',when_present=['ow_data_slots'],required=True,src=STYLE)
 r('transfer_bound_us',minimum_expression={'product':['ow_data_slots','ow_period_us']},src=STYLE)
 for k in('data_slots','period_us','interrupt_bound_us'):r(k,when_present=['ow_transfer_bound_us'],required=True,src=STYLE)
 for dev,recovery,slot,lo,hi in [('DS18B20_REV6',1,60,3,5.5),('DS1990A_2021',1,61,2.8,6),('DS1990AA_2021',5,65,3,5.25)]:
  w={'device':dev};src=TEMP if dev=='DS18B20_REV6'else ID
  r('target_v',w,minimum=lo,maximum=hi,src=src);r('target_temperature_c',w,minimum=-55 if dev=='DS18B20_REV6'else -40,maximum=125 if dev=='DS18B20_REV6'else 85,src=src)
  r('recovery_us',w,minimum=recovery,src=src)
  r('slot_us',{**w,'slot_style':'EXCLUDES_RECOVERY'},minimum=60,src=src)
  if dev=='DS18B20_REV6':r('slot_us',{**w,'slot_style':'EXCLUDES_RECOVERY'},maximum=120,src=TEMP)
  r('period_us',w,minimum=slot if dev!='DS18B20_REV6'else 61,src=src)
  for k in('write_one_us','read_low_us'):r(k,w,minimum=1,maximum=15,src=src)
  r('write_zero_us',w,minimum=60,maximum=120,src=src);r('read_sample_us',w,maximum=15,src=src)
  r('reset_low_us',w,minimum=480,src=src);r('reset_high_us',w,minimum=480,src=src)
  r('presence_delay_us',w,minimum=15,maximum=60,src=src);r('presence_low_us',w,minimum=60,maximum=240,src=src)
 r('reset_low_us',{'device':'DS1990AA_2021'},maximum=640,src=ID)
 r('reset_low_us',{'device':'DS18B20_REV6','power':'PARASITIC'},maximum=960,src=TEMP)
 for dev,lo,hi in [('DS1990A_2021',600,5000),('DS1990AA_2021',300,2200)]:
  r('pullup_ohm',{'device':dev,'pullup_scope':'SINGLE_MIN_RECOVERY'},minimum=lo,maximum=hi,src=ID)
 for k in('pullup_scope','physical_source'):r(k,when_present=['ow_pullup_ohm'],required=True,src=ID)
 r('target_count',{'pullup_scope':'SINGLE_MIN_RECOVERY'},allowed=[1],src=ID)
 r('registered_source',{'pullup_scope':'ACTUAL_QUALIFIED'},required=True,src=ID)
 for dev in('DS1990A_2021','DS1990AA_2021'):r('power',{'device':dev},allowed=['PARASITIC'],src=ID)
 for resolution,bound in CONVERSIONS.items():r('conversion_bound_ms',{'device':'DS18B20_REV6','resolution':resolution},minimum=bound,src=TEMP)
 r('resolution',when_present=['ow_conversion_bound_ms'],required=True,src=TEMP)
 r('copy_bound_ms',minimum=10,src=TEMP)
 for func in('CONVERT_T','COPY_SCRATCHPAD'):
  w={'device':'DS18B20_REV6','power':'PARASITIC','function':func}
  r('strong_pullup',w,required=True,allowed=[True],src=TEMP);r('strong_on_us',w,required=True,maximum=10,src=TEMP)
  r('strong_hold_ms',w,required=True,minimum_parameter='ow_conversion_bound_ms'if func=='CONVERT_T'else'ow_copy_bound_ms',src=TEMP)
  r('conversion_bound_ms'if func=='CONVERT_T'else'copy_bound_ms',w,required=True,src=TEMP)
  r('activity_during_hold',w,required=True,allowed=[False],src=TEMP)
 for master in('SOFTWARE_AN126_TABLE','SOFTWARE_AN126_CODE','DS2482_100_REV11'):r('slot_style',{'master':master},allowed=['INCLUDES_RECOVERY'])
 for mode,values in DS2482_TIMINGS.items():
  w={'master':'DS2482_100_REV11','mode':mode}
  for k,(lo,typ,hi)in values.items():r(k,w,minimum=lo,maximum=hi,src=MASTER)
  r('load_pf',w,maximum=1000 if mode=='STANDARD'else 300,src=MASTER);r('bridge_1ws',w,allowed=[0 if mode=='STANDARD'else 1],src=MASTER)
 for k in('host_i2c_bps','host_address','host_ad0','host_ad1','bridge_config','bridge_config_write','bridge_1ws','bridge_busy','short','active_pullup','master_v','master_temperature_c'):
  r('master',when_present=['ow_'+k],allowed=['DS2482_100_REV11'],src=MASTER)
 r('host_i2c_bps',exclusive_minimum=0,src=MASTER)
 r('host_address',equal_expression={'sum':[24,{'product':['ow_host_ad1',2]},'ow_host_ad0']},src=MASTER)
 for k in('host_ad0','host_ad1'):r(k,when_present=['ow_host_address'],required=True,src=MASTER)
 r('bridge_config',allowed=[0,1,4,5,8,9,12,13],src=MASTER)
 for config in(0,1,4,5,8,9,12,13):
  r('bridge_1ws',{'bridge_config':config},allowed=[config//8],src=MASTER)
  r('active_pullup',{'bridge_config':config},allowed=[bool(config&1)],src=MASTER)
 r('bridge_config_write',equal_expression={'sum':['ow_bridge_config',{'product':[{'subtract':[15,'ow_bridge_config']},16]}]},src=MASTER)
 r('bridge_config',when_present=['ow_bridge_config_write'],required=True,src=MASTER)
 r('bridge_busy',allowed=[False],src=MASTER);r('short',allowed=[False],src=MASTER)
 r('master_v',minimum=2.9,maximum=5.5,src=MASTER);r('master_temperature_c',minimum=-40,maximum=85,src=MASTER)
 r('age_ms',maximum_parameter='ow_freshness_limit_ms',src=TEMP);r('freshness_limit_ms',when_present=['ow_age_ms'],required=True,src=TEMP)
 r('outcome',{'data_accepted':True},required=True,allowed=['ACCEPTED'],src=TEMP)
 return dict(rate_model={'type':'APPLICATION_DEPENDENT','fields':[]},required_parameters=['ow_'+k for k in REQUIRED],native_parameter_prefixes=['ow_'],parameter_constraints=rules,parameter_evidence_scope='EXPLICIT_LAYER',
  physical_layer_profile_id='source_qualified_1wire_slot_and_load',medium_access_model='SINGLE_MASTER_OPEN_DRAIN_HALF_DUPLEX_SLOTS',arbitration_model_id='MASTER_SCHEDULE_ROM_SEARCH_AND_POWER_HOLDS',
  mechanisms={'framing':['LSB_FIRST_OCTETS','ROM_AND_DEVICE_FUNCTION_SEPARATE','MAXIM_CRC8_PREFIX'],
   'physical':['ACTUAL_SLOT_RECOVERY_THRESHOLD_LOAD_POWER','HOST_BRIDGE_INDEPENDENT_BUS'],
   'qualification':['NO_255BYTE_FRAME_OR_I2C_ADDRESS_FALLBACK','CONVERSION_DISTINCT_BUS_SERIALIZATION']})

def fields():
 result=[]
 for spec in DECLARATIONS:
  k=spec['key'][3:];item={a:b for a,b in spec.items()if b is not None}
  item.update(label=k.replace('_',' '),category='timing'if spec.get('unit')in('us','ms')else'communication',scope='network',editable=True,required=k in REQUIRED,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
  defaults=[]
  if k in('mode','master_count','open_drain','lsb_first'):item.update(default={'mode':'STANDARD','master_count':1,'open_drain':True,'lsb_first':True}[k],default_status='PROPOSED',parameter_origin='TRANSPORT_PROFILE')
  if k=='nominal_bps':defaults=[dict(when={'ow_mode':'STANDARD'},value=16300,source=STYLE,source_revision=SOURCES[STYLE])]
  if k=='slot_style':defaults=[dict(when={'ow_master':m},value='INCLUDES_RECOVERY',source=MASTER if m=='DS2482_100_REV11'else AN,source_revision=SOURCES[MASTER if m=='DS2482_100_REV11'else AN])for m in('SOFTWARE_AN126_TABLE','SOFTWARE_AN126_CODE','DS2482_100_REV11')]
  for mode,timings in DS2482_TIMINGS.items():
   if k in timings:defaults.append(dict(when={'ow_mode':mode,'ow_master':'DS2482_100_REV11'},value=timings[k][1],source=MASTER,source_revision=SOURCES[MASTER]))
  for mode,timings in SOFTWARE.items():
   if k in timings:
    for m in('SOFTWARE_AN126_TABLE','SOFTWARE_AN126_CODE'):
     value=timings[k]
     if mode=='OVERDRIVE'and m=='SOFTWARE_AN126_CODE':value={'write_one_us':1.5,'read_low_us':1.5,'read_after_release_us':.75,'read_sample_us':2.25}.get(k,value)
     defaults.append(dict(when={'ow_mode':mode,'ow_master':m},value=value,source=AN,source_revision=SOURCES[AN]))
  if k=='resolution':defaults=[dict(when={'ow_device':'DS18B20_REV6'},value=12,source=TEMP,source_revision=SOURCES[TEMP])]
  if k=='conversion_bound_ms':defaults=[dict(when={'ow_device':'DS18B20_REV6','ow_resolution':bits},value=v,source=TEMP,source_revision=SOURCES[TEMP])for bits,v in CONVERSIONS.items()]
  if k=='copy_bound_ms':defaults=[dict(when={'ow_device':'DS18B20_REV6','ow_function':'COPY_SCRATCHPAD'},value=10,source=TEMP,source_revision=SOURCES[TEMP])]
  if k=='host_i2c_bps':defaults=[dict(when={'ow_master':'DS2482_100_REV11'},value=100000,source=MASTER,source_revision=SOURCES[MASTER])]
  if defaults:item.update(conditional_defaults=defaults,default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE')
  result.append(item)
 return result
