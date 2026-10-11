"""KNX RF: edition, actual radio variant and service-specific evidence."""
from math import inf, nextafter
SPEC='https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/156/03_5F00_02_5F00_05-Communication-Medium-RF-v01.06.03-AS.pdf'
ASSOC='https://support.knx.org/hc/en-us/articles/360000155839-Frequency-Communication-Media-Couplers'
DOMAINS='https://support.knx.org/hc/en-us/articles/360000160000-Domains-Retransmission'
EVOLUTION='https://knx.org/news/knx-rf-multi-next-generation-knx-rf-standard'
SECURE='https://support.knx.org/hc/en-us/articles/360012689639-KNX-Data-Secure'
SETTINGS='https://raw.githubusercontent.com/calimero-project/calimero-core/61360088c59fd5f593608c971059437b37e0a836/src/tuwien/auto/calimero/link/medium/RFSettings.java'
SOURCES={SPEC:'KNX Association RF approved standard01.06.03,2013-10-29,KNX2.1; primary authored PDF mirrored on TI; declared PHY/framing/access/Multi/BiBat sections read via parsed PDF, not newerSLE or current regulatory approval',
    ASSOC:'KNX Association frequency/communication/media couplers,2022-04-20;868.3/915MHz and Ready versus Multi, accessed2026-10-02',
    DOMAINS:'KNX Association domains/retransmission,updated2026-08-27;6-byteDoA/255participants/up to3repeaters; allocation remains edition/project specific',
    EVOLUTION:'KNX Association RF evolution,2023-10-16; MultiSLE exists separately, not covered by old2013 normative table',
    SECURE:'KNX Association Data Secure,updated2026-09-23;actual end-device/group commissioning and independently protected keys',
    SETTINGS:'Calimero v2.6 exact61360088 RFSettings;6-byteDoA/serial/direction;constructor zero/broadcast placeholders are not allocated identities'}
LEGACY='KNX_2_1_RF_01_06_03'
VARIANTS=['RF1_READY','RF1_MULTI','RF1_BIBAT','RF1_BIBAT2','RF2_READY','RF3_READY','RF4_REGISTERED','MULTI_SLE_REGISTERED','OTHER_REGISTERED']
DECLARATIONS=[]


def d(key,kind,meaning,source=SPEC,unit=None,options=None,lo=None,hi=None,integer=False):
    DECLARATIONS.append(dict(key='krf_'+key,type=kind,description=meaning,source=source,source_revision=SOURCES[source],
        unit=unit,options=options,min=lo,max=hi,integer=integer))


for key,meaning,options,source in [
 ('edition','Actual reviewed KNX2.1 RF edition versus separately registered newer/other profile; no automatic SLE/region conformance.',[LEGACY,'REGISTERED_EDITION'],SPEC),
 ('variant','Actual RF1Ready/Multi/BiBat/BiBat2,433MHzRF2/3,915MHzRF4 or separately registeredSLE; not one generic wireless setting.',VARIANTS,ASSOC),
 ('channel','Actual single ready/BiBat channel versus MultiF1/F2/F3/S1/S2 or BiBat2F4; receiver compatibility is required.',['SINGLE','F1','F2','F3','S1','S2','F4','REGISTERED_CHANNEL'],SPEC),
 ('role','Actual original endpoint versus repeater versus independently qualified media coupler.', ['END_DEVICE','REPEATER','MEDIA_COUPLER'],SPEC),
 ('direction','Actual transmit versus receive; observed radio fields differ from transmitter limits.', ['TRANSMITTER','RECEIVER'],SPEC),
 ('device_direction','Actual unidirectional transmit-only versus bidirectional radio capability; no constructorfalse assumption.', ['UNIDIRECTIONAL','BIDIRECTIONAL'],SETTINGS),
 ('receiver_mode','Actual permanent/non-permanent/absent receiver, not assumed from mains/battery supply.', ['PRM','NPRM','TRANSMIT_ONLY'],SPEC),
 ('frame_kind','Actual RF Ready asynchronous, Multi data/ACK, BiBat sync/help/fastACK/long-header or registered service.',
  ['READY_DATA','MULTI_DATA','MULTI_FAST_ACK','MULTI_ACK_REP','BIBAT_DATA','BIBAT_SYNC','BIBAT_HELP','BIBAT_HELP_RESPONSE','BIBAT_FAST_ACK','LONG_HEADER','REGISTERED_SERVICE'],SPEC),
 ('access_kind','Actual original/repeated/ACK-repeater channel-access table row; priority is not encoded like CAN.', ['ORIGINAL','REPEATED','ACK_REP','REGISTERED_ACCESS'],SPEC),
 ('telegram_format','Actual standard versus LTE extended or separately registered secured/management layout.', ['STANDARD','LTE_EXTENDED','REGISTERED_FORMAT'],SPEC),
 ('communication','Actual individual connected/connectionless, multicast, domain/system broadcast; AET selectsSN/DoA.',
  ['INDIVIDUAL_CONNECTIONLESS','INDIVIDUAL_CONNECTED','MULTICAST','DOMAIN_BROADCAST','SYSTEM_BROADCAST','LTE_REGISTERED'],SPEC),
 ('modulation','Actual FSK or qualified registered modulation; not inferred from generic radio.', ['FSK','REGISTERED_MODULATION'],SPEC),
 ('encoding','Actual Manchester two chips per bit versus explicit registered encoding.', ['MANCHESTER','REGISTERED_ENCODING'],SPEC),
 ('bib_master_role','Actual BiBat master versus slave versus synchronous repeater; down/up roles differ.', ['MASTER','SLAVE','SYNCHRONOUS_REPEATER'],SPEC),
 ('bib_traffic_direction','Actual master downstream versus slave upstream or management frame.', ['DOWN','UP','MANAGEMENT'],SPEC),
 ('commissioning_mode','Actual S-Mode versus PB preassigned datagrams; factory group-number rule is not universal.', ['S_MODE','PB_MODE','REGISTERED_COMMISSIONING'],SPEC)]:d(key,'select',meaning,options=options,source=source)

for key,meaning,source in [
 ('revision','Actual selected full physical/link/security edition and compatible device capabilities.',SPEC),
 ('registered_profile_source','Actual registered alternate/current/SLE/RF4/channel/service parameter schema and codec; old incomplete RF4 table is not evidence.',EVOLUTION),
 ('device_source','Actual radio chip/antenna/firmware, supported Ready/Multi/BiBat/channel/receiver capabilities.',ASSOC),
 ('regulatory_source','Actual current deployment jurisdiction, band/power/duty/LBT and applicable radio approval;2013 limits are not current permission.',SPEC),
 ('physical_source','Actual ERP/sensitivity/link budget/interference/coexistence/temperature/oscillator and radio evidence.',SPEC),
 ('binding_source','Actual canonical RF port, selected independent channel/domain and registered TP/IP/media-coupler paths.',ASSOC),
 ('commissioning_source','Actual unique commissioned domain/member serials/group mappings/receiver capabilities and secure keys.',DOMAINS),
 ('application_source','Actual DPT/APCI/LTE application codec and payload, not all255bytes application data.',SPEC),
 ('encoding_source','Actual RF length/C/Esc/info/SN-DoA/LPCl/TPCl/APCl/LTE/CRC/pre/postamble encoding.',SPEC),
 ('schedule_source','Actual airtime, receiver scanning/wake-up/channel access/repeats/ACKs and BiBat synchronization.',SPEC),
 ('capacity_source','Actual complete shared radio domain/coexistence/channel duty/transport/coupler capacity evidence.',SPEC),
 ('acceptance_source','Actual functional E2E/freshness/safety acceptance, distinct from localLData.con or radio ACK.',SPEC),
 ('serial_hex','Actual6-byte sender serial; constructorzero is not allocation.',SETTINGS),
 ('domain_hex','Actual6-byte commissioned RF domain;2013 allocation from memberSN differs from newer ETS domain policy.',DOMAINS),
 ('domain_member_serial_hex','Actual domain-owner/member serial for the2013 allocation rule, not invented reference identity.',SPEC),
 ('wire_address_hex','Actual transmitted6-byte SN orDoA selected by AET.',SPEC),
 ('receiver_source','Actual configured recipients, fast/slow capability, scan state/slots and address acceptance.',SPEC),
 ('ack_source','Actual FastAck-capable recipients/unique configured slots/expected list and real missing-ACK handling.',SPEC),
 ('bib_master_serial_hex','Actual BiBat master serial used as synchronous domain, not zero/defaultmaster.',SPEC),
 ('bib_schedule_source','Actual commissioned BiBat64slot/128block/pseudorandom table and receive-window alignment.',SPEC),
 ('security_source','Actual independently commissioned KNX Data Secure per group/endpoint, not KNX IP Secure radio transport.',SECURE),
 ('group_key_ref','Actual protected group key reference; no secret key/defaultcredentials.',SECURE),
 ('coupler_source','Actual RF-TP/RF-IP mapping, frame capability, translation latency, filtering and independently sized other medium.',SPEC),
 ('crc_source','Actual byte-order/no-reflection/initial-zero/complemented FT3 CRC16 source and test vector.',SPEC)]:d(key,'text',meaning,source=source)

for key,meaning,lo,hi,unit,integer in [
 ('bitrate_bps','Actual information bits/s;fast16384 versus slow8192, not chiprate32768.',1,None,'bit/s',True),
 ('chiprate_cps','Actual encoded chips/s;Manchester2*bitrate.',1,None,'chip/s',True),
 ('carrier_hz','Actual selected carrier frequency, not generic868MHz for all RF variants.',1,None,'Hz',True),
 ('bandwidth_hz','Actual modulation bandwidth; edition/channel upper limit is not an operating default.',1,None,'Hz',True),
 ('deviation_hz','Actual FSK deviation magnitude;fast typical60000,slow range has no supplied universal typical.',1,None,'Hz',True),
 ('tx_erp_dbm','Actual radiated transmitterERP,2013 typical0dBm proposal only; power affects duty policy.',None,None,'dBm',False),
 ('tx_erp_mw','Actual radiatedERPmW for channel/power-dependent duty branch, distinct from chip conducted power.',0,None,'mW',False),
 ('duty_percent','Actual air-time proportion within qualified regulatory observation window, not maxlimit default.',0,100,'%',False),
 ('duty_window_ms','Actual applicable duty-cycle observation window from current radio approval.',0,None,'ms',False),
 ('tx_frequency_error_ppm','Actual magnitude of transmit frequency error including aging/temperature.',0,None,'ppm',False),
 ('rx_frequency_tolerance_ppm','Actual qualified receive frequency tolerance;specifiedminimum is not measuredclockerror.',0,None,'ppm',False),
 ('tx_chip_error_percent','Actual magnitude of transmit encoded-chip timing error.',0,None,'%',False),
 ('rx_chip_tolerance_percent','Actual supported receive chiprate tolerance at statedBER/direction.',0,None,'%',False),
 ('tx_jitter_us','Actual magnitude of chip transition jitter.',0,None,'us',False),
 ('rx_sensitivity_dbm','Actual radiated sensitivity at specifiedBER/antenna orientation.',None,None,'dBm',False),
 ('test_ber','Actual sensitivity/test BER criterion, not an assumed zero runtime error probability.',0,1,None,False),
 ('link_budget_db','Actual link budget from qualified transmitter and receiver, recommended100dB is not measurement.',0,None,'dB',False),
 ('operating_min_c','Actual device operating-temperature lower limit, exampleoutdoor temperature is not standard default.',None,None,'degC',False),
 ('operating_max_c','Actual device operating-temperature upper limit.',None,None,'degC',False),
 ('blocking_category','Actual receiver blocking category per applicable edition/radio standard.',1,None,None,True),
 ('preamble_pairs','Actual number of01chip pairs;Ready79,MultiFast247,MultiSlow4111;BiBatmin15pairs,not fixed15.',0,None,None,True),
 ('preamble_chips','Actual physical preamble chips, distinct from data octets and pairs.',0,None,'chip',True),
 ('violation_chips','Actual Manchester violation6chips for revieweddata frames.',0,None,'chip',True),
 ('sync_chips','Actual revieweddata sync12chips; special ACK structure separately encoded.',0,None,'chip',True),
 ('postamble_chips','Actual2..8chip basic trailer versus special extendedACK/postamble.',0,None,'chip',True),
 ('interframe_ms','Actual fixed quiet-medium interval by role/frame/channel, notCAN arbitration.',0,None,'ms',False),
 ('random_ms','Actual random backoff, discrete1msstep with exclusiveupperbound in reviewedtable; no fixed zeroexample default.',0,None,'ms',True),
 ('medium_access_ms','Actual interframe+randomtime after current channel free, not a whole application latency guarantee.',0,None,'ms',False),
 ('channel_timeout_ms','Actual Multi channel blockage timeout fast500/slow1500ms.',0,None,'ms',False),
 ('length_field','Actual L octet counts useroctets afterL excludingCRCs;255reserved in reviewed edition.',0,254,'Byte',True),
 ('user_octets','Actual total RF user octets includingL and firstblock,excludingCRCs/pre/postamble.',10,255,'Byte',True),
 ('block_count','Actual first10-byteblock plusceil(remaining/16), each block has2CRCbytes.',1,None,None,True),
 ('frame_octets','Actual useroctets plus2*blockcount, excluding physicalpre/postamble.',12,None,'Byte',True),
 ('crc_octets','Actual per-block CRC2bytes, distinct from one end-of-frame CANCRC.',2,2,'Byte',True),
 ('crc_polynomial','Actual non-reflected FT3 polynomial0x3D65, not reflected genericDNP implementation parameter.',15717,15717,None,True),
 ('crc_initial','Actual non-reflected FT3 initialzero, not optional frame evidence bypass.',0,0,None,True),
 ('crc_xorout','Actual complemented FT3 result0xFFFF, MSB-first onwire.',65535,65535,None,True),
 ('c_field','ActualSEND_NO_REPLY C0x44, not availability of Multi fastACK.',68,68,None,True),
 ('esc_field','ActualRF escape0xFF.',255,255,None,True),
 ('source_address','Actual16-bit individual sender;05FFpreassignedonlytransmit-only2013 profile.',0,65535,None,True),
 ('destination_address','Actual16-bit group/individual destination; systembroadcast0.',0,65535,None,True),
 ('address_type','Actual ATbit,individual0/group1.',0,1,None,True),
 ('address_extension_type','Actual AETbit0senderSN versus1domainDoA; unrelated toATbit.',0,1,None,True),
 ('lfn','Actual3-bit RF linkframe number for duplicate elimination, not TCPsequence.',0,7,None,True),
 ('repetition_counter','Actual3-bitRF repetition counter;2013Ready/BiBat endpoint6 versusMulti2, not sendretrycount.',0,7,None,True),
 ('received_repetition_counter','Actual received counter before repeater decrement, notdefault6 for repeatingframes.',0,7,None,True),
 ('rssi_code','Actual2-bit info RSSIcode0unknown/1weak/2medium/3strong; no measurementdefault.',0,3,None,True),
 ('frame_control','ActualRF controlbyte;Ready0x0*,BiBat0x4*/sync0x50/help0x60/response0x70,Multi0x8*/0x9*/AckRep0xA0.',0,255,None,True),
 ('eff','Actual4-bit extendedframe format;standard0, LTE uses registeredtagformats.',0,15,None,True),
 ('tpci','Actual2-bittransport class;LTE00.',0,3,None,True),
 ('transport_sequence','Actual4-bittransport sequence; LTEtaggroup1.',0,15,None,True),
 ('apci','Actual selected10-bitapplicationservice encoding, not allassignments valid for everyDPT.',0,1023,None,True),
 ('lte_iot','Actual16-bit LTE interface object type, assigned by selected application spec.',0,65535,None,True),
 ('lte_instance','Actual LTE object instance from selected application codec.',0,None,None,True),
 ('lte_pid','Actual LTE property ID from selected application schema.',0,255,None,True),
 ('domain_participants','Actual commissioned devices per RF domain, association limit255.',1,255,None,True),
 ('repeaters','Actual commissioned retransmitters per RF domain, at most3; no assumedzero.',0,3,None,True),
 ('ack_expected','Actual FastAck destinationcount;2013recommended1..64, alternateinstallation needsregisteredprofile.',1,255,None,True),
 ('ack_slot','Actual unique configured receiver slot, not automaticallyslot1.',1,255,None,True),
 ('ack_slot_ms','Actual MultiFastACKslot5ms, slowtimingsdouble; not applicationdeadline.',0,None,'ms',False),
 ('ack_start_us','Actual ACK starts100..300us after fastslot start, slowtimingsdouble.',0,None,'us',False),
 ('ack_clock_error_percent','Actual ACKmicrocontrollerclock accuracy magnitude,max0.05% in2013Fast.',0,None,'%',False),
 ('ack_postamble_ms','Actual special MultiFastpostamble9ms, slowtimingsdouble; extraEOA structure accounted separately.',0,None,'ms',False),
 ('echo_timeout_ms','Actual repeater echo wait75ms for reviewedfastchannel; qualifiedslow-frame processing/echo timing needs actual source.',0,None,'ms',False),
 ('ack_retry_attempts','Actual Multi initialsendplus3immediateretries4attempts, separate fromRC2.',1,None,None,True),
 ('bib_slot_ms','ActualBiBat synchronous time-slot62.5ms.',0,None,'ms',False),
 ('bib_block_ms','ActualBiBat64slots4000msplus actual pseudorandompause≤1000ms.',0,None,'ms',False),
 ('bib_pause_ms','ActualBiBat pseudorandompause from commissioned48-bitmaster-derivedtable, not fixed500ms.',0,1000,'ms',False),
 ('bib_section_blocks','ActualBiBat128blocks persection, not generic1000ms syncperiod.',1,None,None,True),
 ('bib_repeater_number','Actualcommissioned1..3 synchronousrepeaternumber, not allocateddefault1.',1,3,None,True),
 ('bib_repeater_delay_ms','Actual(n+1)*62.5ms synchronousrepeaterdelay.',0,None,'ms',False),
 ('bib_concatenated_frames','Actual≤3 same-receivertelegramsin synchronousslot.',1,3,None,True),
 ('bib_airtime_ms','Actualcontinuousairtime≤61ms includingallphysicalheader/sync/trailerchips.',0,None,'ms',False),
 ('bib_clock_error_ppm','Actualsynchronousclockerrormagnitude,strictlyless100ppm per2013wording.',0,None,'ppm',False),
 ('bib_jitter_us','Actualsynchronoussystemjittermagnitude,strictlyless100us.',0,None,'us',False),
 ('bib_fastack_wait_ms','ActualBiBatfeedbackreceiverwait300ms, separatefromMulti5msACKslots.',0,None,'ms',False),
 ('bib_fastack_attempts','ActualBiBatfeedbackinitialsendplus2repetitions3attempts, notMulti4.',1,None,None,True),
 ('bib_fastack_master_delay_ms','ActualBiBatmasterfastACKresponse,strictlyless200ms.',0,None,'ms',False),
 ('bib_fastack_retry_ms','ActualBiBatretryaftermissingACKwithin10ms.',0,None,'ms',False),
 ('long_header_ms','ActualbidirectionalBiBatalarm3500mslongheader, not500msMultiSlowpreamble.',0,None,'ms',False),
 ('long_header_wakeup_ms','Actuallongheaderalarmreceiverwakeup≤3400ms.',0,None,'ms',False),
 ('data_secure_key_octets','ActualDataSecureAES128key16bytes, notactualsecretvalue.',16,16,'Byte',True),
 ('functional_bound_ms','ActualfunctionalapplicationE2Ebudgetdistinctfrommedium/sync/ACKlimits.',0,None,'ms',False)]:d(key,'number',meaning,lo=lo,hi=hi,unit=unit,integer=integer)
for key,meaning,source in [('fast_ack','ActualcommissionedMultiFastACKrequested,optionalreceivercapability.',SPEC),
 ('battery_ok','Actualobservedsenderbatterystate,notdefaulthealthyflag.',SPEC),
 ('lbt_supported','Actualbidirectionalradiochannel-sensingcapability/currentapproval.',SPEC),
 ('data_secure','Actualend-deviceDataSecurepergroup,notIPSecuretransport.',SECURE),
 ('security_confirmed','Actualkey/sequence/authenticationcommissioningverified.',SECURE),
 ('schedule_confirmed','Actualsharedradioscheduleverified.',SPEC),('capacity_confirmed','Actualcompletecapacityverified.',SPEC)]:d(key,'boolean',meaning,source=source)

REMOVED={k:'Removed inherited '+k+': RF edition/variant/channel access, radio duty, commissioned identity, receiver/repeater/ACK and independently qualified coupler replace generic CAN/Ethernet bitrate/queue/priority/retry/sync/gateway assumptions.' for k in
 ('bitrate','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
 'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer',
 'gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}
REQUIRED=['edition','variant','channel','role','direction','device_direction','frame_kind','revision','device_source','regulatory_source',
 'physical_source','binding_source','commissioning_source','application_source','encoding_source','schedule_source','capacity_source','acceptance_source','bitrate_bps']


def semantics():
    rules=[dict(parameter='local_timing_evidence',allowed=[],source='docs/GENERATION_RULE_MANAGER.md',source_revision='KNX RF has its own radio/role/service evidence, not I2C transaction evidence')]
    def r(key,when=None,**kw):rules.append(dict(parameter='krf_'+key,when={'krf_'+k:v for k,v in(when or {}).items()},source=SPEC,source_revision=SOURCES[SPEC],**kw))
    old={'edition':LEGACY}
    r('variant',old,allowed=VARIANTS[:6])
    r('registered_profile_source',{'edition':'REGISTERED_EDITION'},required=True)
    for v in ('RF1_READY','RF1_BIBAT','RF2_READY','RF3_READY'):r('channel',{**old,'variant':v},allowed=['SINGLE'])
    r('channel',{**old,'variant':'RF1_BIBAT2'},allowed=['SINGLE','F4'])
    r('channel',{**old,'variant':'RF1_MULTI'},allowed=['F1','F2','F3','S1','S2'])
    for variant in VARIANTS[:6]:
        base={**old,'variant':variant}
        r('modulation',base,allowed=['FSK']);r('encoding',base,allowed=['MANCHESTER'])
        if variant!='RF1_MULTI':r('bitrate_bps',base,allowed=[16384])
        for key in ('tx_frequency_error_ppm',):r(key,base,maximum=25)
        r('rx_frequency_tolerance_ppm',base,minimum=25)
        r('tx_chip_error_percent',base,maximum=1.5);r('rx_chip_tolerance_percent',base,minimum=2)
        r('tx_jitter_us',base,maximum=5);r('tx_erp_dbm',base,minimum=-3,maximum=10 if variant=='RF2_READY'else 7 if variant=='RF3_READY'else 14)
        r('blocking_category',base,minimum=2)
        r('operating_min_c',base,maximum=0);r('operating_max_c',base,minimum=45)
        r('rx_sensitivity_dbm',base,maximum=-80)
    for variant,hz,bw in [('RF1_READY',868300000,600000),('RF1_BIBAT',868300000,600000),
                          ('RF2_READY',433500000,500000),('RF3_READY',433500000,400000)]:
        base={**old,'variant':variant};r('carrier_hz',base,allowed=[hz]);r('bandwidth_hz',base,maximum=bw);r('deviation_hz',base,minimum=48000,maximum=80000)
        r('duty_percent',base,maximum=1)
    for ch,hz,rate,bw,duty in [('F1',868300000,16384,500000,1),('F2',868950000,16384,500000,.1),
                              ('F3',869850000,16384,300000,None),('S1',869850000,8192,300000,None),('S2',869525000,8192,250000,10)]:
        base={**old,'variant':'RF1_MULTI','channel':ch}
        r('carrier_hz',base,allowed=[hz]);r('bitrate_bps',base,allowed=[rate]);r('bandwidth_hz',base,maximum=bw)
        r('deviation_hz',base,minimum=48000 if ch.startswith('F')else 20000,maximum=80000 if ch.startswith('F')else 65000)
        if duty is not None:r('duty_percent',base,maximum=duty)
        else:
            r('tx_erp_mw',base,required=True)
            r('duty_percent',base,when_ranges={'krf_tx_erp_mw':[0,5]},maximum=100)
            # Start at the next representable power above5mW: exactly5 is the low-power branch.
            r('duty_percent',base,when_half_open_ranges={'krf_tx_erp_mw':[nextafter(5,inf),None]},maximum=1)
        r('preamble_pairs',base,allowed=[247 if ch.startswith('F')else 4111])
        r('channel_timeout_ms',base,allowed=[500 if ch.startswith('F')else 1500])
    r('carrier_hz',{**old,'variant':'RF1_BIBAT2','channel':'SINGLE'},allowed=[868300000])
    r('carrier_hz',{**old,'variant':'RF1_BIBAT2','channel':'F4'},allowed=[869525000])
    r('bandwidth_hz',{**old,'variant':'RF1_BIBAT2','channel':'F4'},maximum=250000)
    r('deviation_hz',{**old,'variant':'RF1_BIBAT2','channel':'F4'},minimum=50000,maximum=60000)
    r('duty_percent',{**old,'variant':'RF1_BIBAT2','channel':'F4'},maximum=10)
    r('chiprate_cps',{'encoding':'MANCHESTER'},equal_expression={'product':['krf_bitrate_bps',2]})
    r('tx_erp_mw',equal_expression={'power':[10,{'product':['krf_tx_erp_dbm',.1]}]})
    r('preamble_chips',equal_expression={'product':['krf_preamble_pairs',2]})
    for kind in ('READY_DATA','MULTI_DATA','BIBAT_DATA'):
        base={**old,'frame_kind':kind,'direction':'TRANSMITTER'}
        r('violation_chips',base,allowed=[6]);r('sync_chips',base,allowed=[12])
        if kind!='MULTI_DATA':r('postamble_chips',base,minimum=2,maximum=8)
        else:r('postamble_chips',{**base,'fast_ack':False},minimum=2,maximum=8)
    r('length_field',equal_expression={'subtract':['krf_user_octets',1]})
    r('block_count',equal_expression={'sum':[1,{'ceiling':[{'product':[{'subtract':['krf_user_octets',10]},.0625]}]}]})
    r('frame_octets',equal_expression={'sum':['krf_user_octets',{'product':['krf_block_count',2]}]})
    r('operating_min_c',maximum_parameter='krf_operating_max_c')
    for key in ('serial_hex','domain_hex','domain_member_serial_hex','wire_address_hex','bib_master_serial_hex'):r(key,pattern=r'[0-9a-fA-F]{12}')
    r('domain_hex',old,when_present=['krf_domain_member_serial_hex'],equal_parameter='krf_domain_member_serial_hex')
    for com in ('MULTICAST','SYSTEM_BROADCAST'):
        base={**old,'communication':com};r('address_extension_type',base,allowed=[0]);r('address_type',base,allowed=[1]);r('wire_address_hex',base,equal_parameter='krf_serial_hex')
    for com in ('INDIVIDUAL_CONNECTIONLESS','INDIVIDUAL_CONNECTED','DOMAIN_BROADCAST'):
        base={**old,'communication':com};r('address_extension_type',base,allowed=[1]);r('wire_address_hex',base,equal_parameter='krf_domain_hex')
    for com in ('INDIVIDUAL_CONNECTIONLESS','INDIVIDUAL_CONNECTED'):
        r('address_type',{**old,'communication':com,'telegram_format':'STANDARD'},allowed=[0])
    for com in ('SYSTEM_BROADCAST','DOMAIN_BROADCAST'):r('destination_address',{**old,'communication':com},allowed=[0]);r('address_type',{**old,'communication':com},allowed=[1])
    r('rssi_code',{**old,'role':'END_DEVICE','direction':'TRANSMITTER'},allowed=[0])
    r('receiver_mode',{'device_direction':'UNIDIRECTIONAL'},allowed=['TRANSMIT_ONLY'])
    r('direction',{'device_direction':'UNIDIRECTIONAL'},allowed=['TRANSMITTER'])
    r('source_address',{**old,'device_direction':'UNIDIRECTIONAL'},allowed=[1535])
    for variant in ('RF1_READY','RF2_READY','RF3_READY'):
        base={**old,'variant':variant};r('frame_kind',base,allowed=['READY_DATA']);r('fast_ack',base,allowed=[False])
        r('preamble_pairs',base,allowed=[79]);r('repetition_counter',{**base,'role':'END_DEVICE'},allowed=[6])
        r('frame_control',base,minimum=0,maximum=15)
    for variant in ('RF1_BIBAT','RF1_BIBAT2'):
        base={**old,'variant':variant};r('bib_schedule_source',base,when_present=['krf_bib_master_role'],required=True)
        r('repetition_counter',{**base,'role':'END_DEVICE'},allowed=[6])
        for kind,control in [('BIBAT_SYNC',80),('BIBAT_HELP',96),('BIBAT_HELP_RESPONSE',112)]:
            r('frame_control',{**base,'frame_kind':kind},allowed=[control])
        r('bib_slot_ms',base,allowed=[62.5]);r('bib_section_blocks',base,allowed=[128])
        r('bib_block_ms',base,equal_expression={'sum':[4000,'krf_bib_pause_ms']})
        r('bib_clock_error_ppm',base,exclusive_maximum=100);r('bib_jitter_us',base,exclusive_maximum=100)
        r('bib_airtime_ms',base,maximum=61)
        r('bib_repeater_delay_ms',base,equal_expression={'product':[{'sum':['krf_bib_repeater_number',1]},62.5]})
        r('domain_hex',base,when_present=['krf_bib_master_serial_hex'],equal_parameter='krf_bib_master_serial_hex')
        r('frame_kind',base,forbidden=['MULTI_DATA','MULTI_FAST_ACK','MULTI_ACK_REP'])
        r('preamble_pairs',{**base,'frame_kind':'BIBAT_DATA'},minimum=15)
        r('preamble_chips',{**base,'bib_traffic_direction':'DOWN','frame_kind':'BIBAT_DATA'},allowed=[32])
        r('bib_master_role',{**base,'bib_traffic_direction':'DOWN','direction':'TRANSMITTER'},allowed=['MASTER','SYNCHRONOUS_REPEATER'])
        r('bib_fastack_wait_ms',{**base,'frame_kind':'BIBAT_FAST_ACK'},allowed=[300])
        r('bib_fastack_attempts',{**base,'frame_kind':'BIBAT_FAST_ACK'},allowed=[3])
        r('bib_fastack_master_delay_ms',{**base,'frame_kind':'BIBAT_FAST_ACK'},exclusive_maximum=200)
        r('bib_fastack_retry_ms',{**base,'frame_kind':'BIBAT_FAST_ACK'},maximum=10)
        r('long_header_ms',{**base,'frame_kind':'LONG_HEADER'},allowed=[3500])
        r('long_header_wakeup_ms',{**base,'frame_kind':'LONG_HEADER'},maximum=3400)
    r('repetition_counter',{**old,'variant':'RF1_MULTI','role':'END_DEVICE'},allowed=[2])
    r('frame_kind',{**old,'variant':'RF1_MULTI'},allowed=['MULTI_DATA','MULTI_FAST_ACK','MULTI_ACK_REP'])
    r('frame_control',{**old,'variant':'RF1_MULTI','frame_kind':'MULTI_DATA','fast_ack':False},minimum=128,maximum=143)
    r('frame_control',{**old,'variant':'RF1_MULTI','frame_kind':'MULTI_DATA','fast_ack':True},minimum=144,maximum=159)
    r('frame_control',{**old,'variant':'RF1_MULTI','frame_kind':'MULTI_ACK_REP'},allowed=[160])
    for variant in ('RF1_READY','RF2_READY','RF3_READY','RF1_MULTI'):
        for key in ('bib_master_role','bib_traffic_direction','bib_master_serial_hex','bib_schedule_source',
                    'bib_slot_ms','bib_block_ms','bib_pause_ms','bib_section_blocks','bib_repeater_number','bib_repeater_delay_ms',
                    'bib_concatenated_frames','bib_airtime_ms','bib_clock_error_ppm','bib_jitter_us',
                    'bib_fastack_wait_ms','bib_fastack_attempts','bib_fastack_master_delay_ms','bib_fastack_retry_ms','long_header_ms','long_header_wakeup_ms'):
            r(key,{**old,'variant':variant},allowed=[])
    r('repetition_counter',{**old,'role':'REPEATER'},equal_expression={'subtract':['krf_received_repetition_counter',1]})
    r('medium_access_ms',equal_expression={'sum':['krf_interframe_ms','krf_random_ms']})
    access=[]
    for variant in ('RF1_READY','RF2_READY','RF3_READY'):
        access.extend([(variant,'ORIGINAL','BIDIRECTIONAL',None,15,15),(variant,'ORIGINAL','UNIDIRECTIONAL',None,150,10),
                       (variant,'REPEATED',None,None,5,10)])
    for ch in ('F1','F2','F3','S1','S2'):
        fast=ch.startswith('F');access.extend([('RF1_MULTI','ORIGINAL',None,ch,30 if fast else 60,20 if fast else 40),
            ('RF1_MULTI','REPEATED',None,ch,5 if fast else 10,5 if fast else 10),
            ('RF1_MULTI','ACK_REP',None,ch,10 if fast else 20,5 if fast else 10)])
    for variant,kind,capability,ch,interval,upper in access:
        base={**old,'variant':variant,'access_kind':kind}
        if capability:base['device_direction']=capability
        if ch:base['channel']=ch
        r('interframe_ms',base,allowed=[interval]);r('random_ms',base,exclusive_maximum=upper)
    for ch in ('F1','F2','F3','S1','S2'):
        factor=1 if ch.startswith('F')else 2;base={**old,'variant':'RF1_MULTI','channel':ch,'fast_ack':True}
        r('ack_source',base,required=True);r('receiver_source',base,required=True);r('ack_expected',base,required=True,maximum=64)
        r('ack_slot',base,maximum_parameter='krf_ack_expected')
        r('ack_slot_ms',base,allowed=[5*factor]);r('ack_start_us',base,minimum=100*factor,maximum=300*factor)
        r('ack_clock_error_percent',base,maximum=.05);r('ack_postamble_ms',base,allowed=[9*factor])
        r('ack_retry_attempts',base,allowed=[4])
        if factor==1:r('echo_timeout_ms',base,allowed=[75])
    for variant in ('RF1_READY','RF2_READY','RF3_READY','RF1_BIBAT','RF1_BIBAT2'):
        for key in ('ack_expected','ack_slot','ack_source','ack_slot_ms','ack_start_us','ack_clock_error_percent','ack_postamble_ms','echo_timeout_ms','ack_retry_attempts','channel_timeout_ms'):
            r(key,{**old,'variant':variant},allowed=[])
    for key in ('ack_expected','ack_slot','ack_slot_ms','ack_start_us','ack_clock_error_percent','ack_postamble_ms','echo_timeout_ms','ack_retry_attempts'):
        r(key,{'fast_ack':False},allowed=[])
    for key in ('security_source','group_key_ref','data_secure_key_octets'):r(key,{'data_secure':True},required=True)
    for key in ('security_source','group_key_ref','data_secure_key_octets','security_confirmed'):r(key,{'data_secure':False},allowed=[])
    r('coupler_source',{'role':'MEDIA_COUPLER'},required=True)
    r('eff',{'telegram_format':'STANDARD'},allowed=[0])
    r('eff',{**old,'telegram_format':'LTE_EXTENDED'},minimum=4,maximum=7)
    r('lte_instance',{**old,'telegram_format':'LTE_EXTENDED'},maximum=255)
    for capability,aet in [('UNIDIRECTIONAL',0),('BIDIRECTIONAL',1)]:
        r('address_extension_type',{**old,'telegram_format':'LTE_EXTENDED','device_direction':capability},allowed=[aet])
    r('tpci',{**old,'telegram_format':'LTE_EXTENDED'},allowed=[0]);r('transport_sequence',{**old,'telegram_format':'LTE_EXTENDED'},allowed=[1])
    for key in ('lte_iot','lte_instance','lte_pid'):r(key,{'telegram_format':'STANDARD'},allowed=[])
    for key in ('length_field','user_octets','block_count','frame_octets','c_field','esc_field'):
        r(key,{**old,'frame_kind':'MULTI_FAST_ACK'},allowed=[])
    return {'rate_model':{'type':'EXPLICIT_KNX_RF_EDITION_VARIANT_CHANNEL','fields':[]},
        'parameter_proposals':{'kind':'VARIANT_DEPENDENT','source':SPEC,'source_revision':SOURCES[SPEC]},
        'required_parameters':['krf_'+k for k in REQUIRED],'native_parameter_prefixes':['krf_'],'parameter_constraints':rules,
        'mechanisms':{'framing':['FT3_PER_BLOCK_CRC_AND_PHYSICAL_PREAMBLE'],'addressing':['COMMISSIONED_SENDER_SN_OR_DOMAIN_AET'],
        'arbitration':['EDITION_VARIANT_DIRECTION_CHANNEL_ACCESS_NO_CAN_PRIORITY'],
        'flow_control':['READY_NO_REPLY_MULTI_OPTIONAL_ACK_BIBAT_SYNC_SEPARATE'],
        'acceptance':['LOCAL_SEND_CONFIRMATION_RADIO_ACK_AND_FUNCTIONAL_E2E_SEPARATE']}}


def fields():
    result=[];required=set(semantics()['required_parameters'])
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items()if v is not None};key=item['key'].removeprefix('krf_')
        item.update(label=key.replace('_',' '),category='communication',scope='network',required=item['key']in required,
            editable=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
        proposals=[];old={'krf_edition':LEGACY}
        def p(value,**conditions):proposals.append({'when':{**old,**{'krf_'+k:v for k,v in conditions.items()}},'value':value,
            'source':item['source'],'source_revision':item['source_revision']})
        if key in ('bitrate_bps','chiprate_cps'):
            factor=2 if key=='chiprate_cps'else 1
            for variant in ('RF1_READY','RF1_BIBAT','RF1_BIBAT2','RF2_READY','RF3_READY'):p(16384*factor,variant=variant)
            for ch in ('F1','F2','F3','S1','S2'):p((16384 if ch.startswith('F')else 8192)*factor,variant='RF1_MULTI',channel=ch)
        if key=='carrier_hz':
            for variant,hz in [('RF1_READY',868300000),('RF1_BIBAT',868300000),('RF2_READY',433500000),('RF3_READY',433500000)]:p(hz,variant=variant)
            for ch,hz in [('F1',868300000),('F2',868950000),('F3',869850000),('S1',869850000),('S2',869525000)]:p(hz,variant='RF1_MULTI',channel=ch)
            p(868300000,variant='RF1_BIBAT2',channel='SINGLE');p(869525000,variant='RF1_BIBAT2',channel='F4')
        if key in ('modulation','encoding','tx_erp_dbm'):
            for variant in VARIANTS[:6]:p('FSK'if key=='modulation'else 'MANCHESTER'if key=='encoding'else 0,variant=variant)
        if key=='deviation_hz':
            for variant in ('RF1_READY','RF1_BIBAT','RF2_READY','RF3_READY'):p(60000,variant=variant)
            for ch in ('F1','F2','F3'):p(60000,variant='RF1_MULTI',channel=ch)
        if key=='preamble_pairs':
            for variant in ('RF1_READY','RF2_READY','RF3_READY'):p(79,variant=variant)
            for ch in ('F1','F2','F3','S1','S2'):p(247 if ch.startswith('F')else 4111,variant='RF1_MULTI',channel=ch)
        if key=='interframe_ms':
            for variant in ('RF1_READY','RF2_READY','RF3_READY'):
                p(15,variant=variant,device_direction='BIDIRECTIONAL',access_kind='ORIGINAL')
                p(150,variant=variant,device_direction='UNIDIRECTIONAL',access_kind='ORIGINAL')
                p(5,variant=variant,access_kind='REPEATED')
            for ch in ('F1','F2','F3','S1','S2'):
                fast=ch.startswith('F')
                for kind,value in [('ORIGINAL',30 if fast else 60),('REPEATED',5 if fast else 10),('ACK_REP',10 if fast else 20)]:p(value,variant='RF1_MULTI',channel=ch,access_kind=kind)
        if key=='channel_timeout_ms':
            for ch in ('F1','F2','F3','S1','S2'):p(500 if ch.startswith('F')else 1500,variant='RF1_MULTI',channel=ch)
        if key in ('ack_slot_ms','ack_postamble_ms','ack_retry_attempts'):
            for ch in ('F1','F2','F3','S1','S2'):
                factor=1 if ch.startswith('F')else 2
                p(4 if key=='ack_retry_attempts'else (5 if key=='ack_slot_ms'else 9)*factor,variant='RF1_MULTI',channel=ch,fast_ack=True)
        if key=='repetition_counter':
            for variant in ('RF1_READY','RF2_READY','RF3_READY','RF1_BIBAT','RF1_BIBAT2'):p(6,variant=variant,role='END_DEVICE')
            p(2,variant='RF1_MULTI',role='END_DEVICE')
        if key in ('violation_chips','sync_chips'):
            for kind in ('READY_DATA','MULTI_DATA','BIBAT_DATA'):
                p(6 if key=='violation_chips'else 12,frame_kind=kind,direction='TRANSMITTER')
        if key in ('c_field','esc_field','crc_octets','crc_polynomial','crc_initial','crc_xorout'):
            for kind in ('READY_DATA','MULTI_DATA','BIBAT_DATA'):
                p({'c_field':68,'esc_field':255,'crc_octets':2,'crc_polynomial':15717,'crc_initial':0,'crc_xorout':65535}[key],frame_kind=kind)
        if key in ('bib_slot_ms','bib_section_blocks'):
            for variant in ('RF1_BIBAT','RF1_BIBAT2'):p(62.5 if key=='bib_slot_ms'else 128,variant=variant)
        if key=='data_secure_key_octets':proposals=[{'when':{'krf_data_secure':True},'value':16,'source':SECURE,'source_revision':SOURCES[SECURE]}]
        if proposals:item.update(conditional_defaults=proposals,default_status='PROPOSED_CONDITIONAL')
        result.append(item)
    return result
