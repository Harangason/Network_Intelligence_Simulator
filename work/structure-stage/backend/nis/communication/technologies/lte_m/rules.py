"""Source-qualified LTE-M categories, E-UTRA bands and scheduled radio parameters.

Normative capability limits are not an installed device capability, measured
throughput or a capacity approval. Other releases require a registered schema.
"""
CAP='https://www.etsi.org/deliver/etsi_ts/136300_136399/136306/18.08.00_60/ts_136306v180800p.pdf'
RF='https://www.etsi.org/deliver/etsi_ts/136100_136199/136101/18.13.00_60/ts_136101v181300p.pdf'
PHY='https://www.etsi.org/deliver/etsi_ts/136200_136299/136211/18.00.02_60/ts_136211v180002p.pdf'
SOURCES={CAP:'ETSI TS136306V18.8.0 2026-08, Release18; tables4.1A-1/2/3/5/7 and sections4.3.4.63/64/126/224,4.3.29.1/2',
 RF:'ETSI TS136101V18.13.0 2026-08, Release18; tables5.5-1/5.6-1/5.6.1-1,section5.5E,6.2.2E,6.5.1/6.5.1E including band/power footnotes',
 PHY:'ETSI TS136211V18.0.2 2025-08, Release18; frame structures4.1/4.2,ULresource5.2.3/5.2.4,ULallocation5.3.4,HD-FDDtypeB6.2.5,DLnarrow/wideband6.2.7,DLallocation6.4.1'}
EDITION='R18_306_18_8_101_18_13_211_18_0_2'
# Band: duplex, UL MHz interval, DL MHz interval, allowed serving carrier MHz.
# These are serving-cell bandwidths, not Cat-M1/M2's allocation bandwidth.
BANDS={
 1:('FDD',(1920,1980),(2110,2170),(5,10,15,20)),
 2:('FDD',(1850,1910),(1930,1990),(1.4,3,5,10,15,20)),
 3:('FDD',(1710,1785),(1805,1880),(1.4,3,5,10,15,20)),
 4:('FDD',(1710,1755),(2110,2155),(1.4,3,5,10,15,20)),
 5:('FDD',(824,849),(869,894),(1.4,3,5,10)),
 7:('FDD',(2500,2570),(2620,2690),(5,10,15,20)),
 8:('FDD',(880,915),(925,960),(1.4,3,5,10)),
 11:('FDD',(1427.9,1447.9),(1475.9,1495.9),(5,10)),
 12:('FDD',(699,716),(729,746),(1.4,3,5,10)),
 13:('FDD',(777,787),(746,756),(5,10)),
 14:('FDD',(788,798),(758,768),(5,10)),
 18:('FDD',(815,830),(860,875),(5,10,15)),
 19:('FDD',(830,845),(875,890),(5,10,15)),
 20:('FDD',(832,862),(791,821),(5,10,15,20)),
 21:('FDD',(1447.9,1462.9),(1495.9,1510.9),(5,10,15)),
 24:('FDD',(1626.5,1660.5),(1525,1559),(5,10)),
 25:('FDD',(1850,1915),(1930,1995),(1.4,3,5,10,15,20)),
 26:('FDD',(814,849),(859,894),(1.4,3,5,10,15)),
 27:('FDD',(807,824),(852,869),(1.4,3,5,10)),
 28:('FDD',(703,748),(758,803),(3,5,10,15,20)),
 31:('FDD',(452.5,457.5),(462.5,467.5),(1.4,3,5)),
 39:('TDD',(1880,1920),(1880,1920),(5,10,15,20)),
 40:('TDD',(2300,2400),(2300,2400),(5,10,15,20)),
 41:('TDD',(2496,2690),(2496,2690),(5,10,15,20)),
 42:('TDD',(3400,3600),(3400,3600),(5,10,15,20)),
 43:('TDD',(3600,3800),(3600,3800),(5,10,15,20)),
 48:('TDD',(3550,3700),(3550,3700),(5,10,15,20)),
 54:('FDD',(1670,1675),(1670,1675),(1.4,3,5)),
 66:('FDD',(1710,1780),(2110,2200),(1.4,3,5,10,15,20)),
 71:('FDD',(663,698),(617,652),(5,10,15,20)),
 72:('FDD',(451,456),(461,466),(1.4,3,5)),
 73:('FDD',(450,455),(460,465),(1.4,3,5)),
 74:('FDD',(1427,1470),(1475,1518),(1.4,3,5,10,15,20)),
 85:('FDD',(698,716),(728,746),(5,10)),
 87:('FDD',(410,415),(420,425),(1.4,3,5)),
 88:('FDD',(412,417),(422,427),(1.4,3,5)),
 106:('FDD',(896,901),(935,940),(1.4,3))}
CARRIER_PRBS={1.4:6,3:15,5:25,10:50,15:75,20:100}
TDD={0:('DSUUUDSUUU',5),1:('DSUUDDSUUD',5),2:('DSUDDDSUDD',5),
 3:('DSUUUDDDDD',10),4:('DSUUDDDDDD',10),5:('DSUDDDDDDD',10),6:('DSUUUDSUUD',5)}
DECLARATIONS=[]


def d(key,kind,meaning,source=CAP,lo=None,hi=None,unit=None,options=None,integer=False):
    DECLARATIONS.append(dict(key='ltm_'+key,type=kind,description=meaning,source=source,source_revision=SOURCES[source],
        min=lo,max=hi,unit=unit,options=options,integer=integer))


for key,meaning,options,source in [
 ('edition','Actual reviewed Release18 source set versus independently registered other release. No NR/NB-IoT fallback.',[EDITION,'REGISTERED_EDITION'],CAP),
 ('category','Actual matched DL/UL category pair; M2 also advertises M1 capabilities, not an arbitrary mixed pair.',['M1','M2','REGISTERED_CATEGORY'],CAP),
 ('role','Actual UE versus serving eNodeB; UE output-power/error requirements do not describe a base station.',['UE','ENODEB'],RF),
 ('direction','Actual scheduled radio direction, not a generic symmetric bus clock.',['UPLINK','DOWNLINK'],PHY),
 ('duplex','Actual FDD/TDD serving band. HD-FDD typeB is a UE mode within FDD.',['FDD','TDD'],RF),
 ('ue_duplex','Actual half/full FDD or TDD UE capability; actual scheduler must observe HD typeB guards.',['HD_FDD_TYPE_B','FD_FDD','TDD'],PHY),
 ('ce_mode','Actual coverage enhancement ModeA/B, independently supported and network selected.',['A','B'],CAP),
 ('rrc_state','Actual RRC context; non-repeated unicast connected mode qualifies optional DL64QAM.',['IDLE','CONNECTED'],CAP),
 ('service','Actual unicast versus independently qualified multicast/control channel.',['UNICAST','REGISTERED_SERVICE'],CAP),
 ('modulation','Actual PUSCH/PDSCH selected modulation; UL64/256QAM not supported by M1/M2.',['QPSK','16QAM','64QAM','256QAM','REGISTERED_MODULATION'],CAP),
 ('power_class','Actual commissioned UE power class; nominal maximum is not current output.',['2','3','5','6','REGISTERED_POWER_CLASS'],RF),
 ('carrier20_block','Actual UL20MHz bandwidth footnote interval for bands28/71.',['LOW','HIGH'],RF),
 ('cyclic_prefix','Actual selected normal versus extended PHY CP.',['NORMAL','EXTENDED'],PHY),
 ('grant_profile','Actual channel/RNTI and network wideband configuration:5MHz config is a grant ceiling, not literal serving carrier bandwidth. An independently registered grant has its own source.',
  ['NARROW_6','WIDE_PUSCH_5_C_RNTI','WIDE_PDSCH_5_C_RNTI','REGISTERED_GRANT'],PHY),
 ('security_profile','Actual access-stratum/NAS and separately registered application protection.',['REGISTERED_SECURITY'],CAP)]:d(key,'select',meaning,options=options,source=source)

for key,meaning,source in [
 ('revision','Actual full device/network release and compatible TS36.306/101/211/213/321/331 and NAS profiles.',CAP),
 ('registered_source','Actual independent schema/codec for another release/category/service/modulation/power profile.',CAP),
 ('device_source','Actual certified modem/firmware/category/CE/duplex/band and optional capabilities.',CAP),
 ('binding_source','Actual canonical UE/eNodeB/cell and separately registered application/backhaul transport paths.',PHY),
 ('network_source','Actual serving-cell radio configuration and network admission, not an automatic LTE-M band.',RF),
 ('regulatory_source','Actual jurisdiction, licensed deployment band and radio approval; norm is not permission.',RF),
 ('physical_source','Actual RF link budget/interference/sensitivity/antenna/temperature/frequency and device evidence.',RF),
 ('scheduler_source','Actual grants/allocated PRBs/MCS/TBS/repetitions/HD guards/TDD layout under complete shared-cell workload.',PHY),
 ('mac_rlc_source','Actual TS36.321/322 and network HARQ/RLC retransmission, queues and latency configuration.',CAP),
 ('rrc_nas_source','Actual TS36.331/24.301/24.008 state/timer/PSM/eDRX paging and negotiation profile.',CAP),
 ('application_source','Actual endpoint application codec and per-message byte count, independently selected IP/non-IP path.',CAP),
 ('security_source','Actual independently protected subscription/key references, access-stratum/NAS and application security.',CAP),
 ('capacity_source','Actual complete radio/core/backhaul/server capacity evidence; category peak is not net throughput.',PHY),
 ('acceptance_source','Actual functional E2E/freshness/safety acceptance, distinct from HARQ/RLC acknowledgement.',CAP),
 ('ue_id','Actual commissioned UE reference; never invent IMSI/IMEI/subscriber credentials.',CAP),
 ('cell_id','Actual network assigned serving cell, not a default eNodeB or CAN identifier.',RF),
 ('subscription_key_ref','Actual protected subscription credential reference; never default credentials.',CAP),
 ('carrier_aggregation_source','Actual band66 DL2180..2200MHz qualified carrier-aggregation/device/network proof.',RF),
 ('band74_capability_source','Actual compliance with band11 and band21 requirements when band74 is supported.',RF),
 ('power_profile_source','Actual non-CA/non-UL-MIMO class/MPR/A-MPR/P-MPR/tolerance; table6.2.2E lacks a band66 row.',RF),
 ('spectral_source','Actual occupied bandwidth/SEM/ACLR/spurious/blocking receiver and qualified test-condition evidence.',RF),
 ('frequency_error_source','Actual error compared to received eNodeB carrier over a0.5ms observation, not an oscillator catalog tolerance.',RF),
 ('retuning_source','Actual ce-RetuningSymbols/range/direction transitions and TS36.211 guards; not a universal2us delay.',PHY),
 ('airtime_source','Actual coded/repeated scheduled airtime including control/reference/guard resources, not appbytes/peakbits.',PHY),
 ('tdd_pattern','Actual ten subframe D/S/U pattern from configured UL/DL assignment.',PHY),
 ('tdd_special_source','Actual DwPTS/GP/UpPTS pattern and CP-qualified special subframe configuration.',PHY),
 ('psm_timer_encoding','Actual negotiated NAS T3412/T3324 units/value/deactivation encoding; no fabricated lifetime.',CAP),
 ('edrx_timer_encoding','Actual negotiated LTE-M eDRX/paging window encoding, distinct from NB-IoT tables.',CAP),
 ('harq_source','Actual applicable TS36.213 process counts/repetition/feedback/RTT per CE/duplex capability.',CAP)]:d(key,'text',meaning,source)

for key,meaning,lo,hi,unit,integer,source in [
 ('band','Actual eligible E-UTRA band, not any LTE/NR/NB-IoT band.',1,106,None,True,RF),
 ('carrier_bandwidth_mhz','Actual serving E-UTRA carrier bandwidth; M1 can use narrowband resources within a20MHz carrier.',1.4,20,'MHz',False,RF),
 ('carrier_prbs','Actual total serving-carrier PRBs, not allocated UE PRBs.',6,100,None,True,RF),
 ('ue_max_bandwidth_mhz','Normative selected category/band maximum capability bandwidth, not serving carrier or installed device evidence.',1.4,5,'MHz',False,CAP),
 ('allocated_prbs','Actual scheduled PUSCH/PDSCH PRBs, not total carrier PRBs; M2wideband max24,3MHz carrier ULmax13 including odd central PRB versus DLmax12.',1,100,None,True,PHY),
 ('allocated_bandwidth_mhz','Actual scheduled bandwidth qualified by CE/direction/category and serving carrier.',0,None,'MHz',False,CAP),
 ('carrier_mhz','Actual direction-qualified radio frequency; band66 CA footnote remains separate.',0,None,'MHz',False,RF),
 ('dl_tb_limit_bits','Normative category DLtransport block limit per TTI, including optional M1 feature; not actual message length or rate.',1,None,'bit',True,CAP),
 ('dl_soft_buffer_bits','Normative category soft channel bit capability; not free application queue size.',1,None,'bit',True,CAP),
 ('ul_tb_limit_bits','Normative category ULtransport block limit per TTI, including optional M1 feature; not actual granted TBS.',1,None,'bit',True,CAP),
 ('layer2_capability_bytes','Normative total L2buffer capability, not queue allocation or available hardware memory.',1,None,'byte',True,CAP),
 ('dl_spatial_layers','Normative max1 DLspatiallayer for M1/M2, not NR MIMO.',1,1,None,True,CAP),
 ('actual_tb_bits','Actual scheduler-selected transport block, distinct from application bytes/segmentation.',1,None,'bit',True,CAP),
 ('repetitions','Actual selected PUSCH/PDSCH/MPDCCH repetition count from independent channel/CE/grant profile.',1,None,None,True,CAP),
 ('scheduled_bound_ms','Actual complete local scheduling/airtime upper bound; no zero-delay assumption.',0,None,'ms',False,PHY),
 ('functional_bound_ms','Actual functional end-to-end deadline, independent of radio ACK/grant/nominal peak.',0,None,'ms',False,CAP),
 ('frame_ms','Normative frame duration10ms, not application cycle.',10,10,'ms',False,PHY),
 ('subframe_ms','Normative subframe duration1ms, not assumed repetition-free application TTI.',1,1,'ms',False,PHY),
 ('slot_ms','Normative15kHz-SCS slot duration0.5ms, not an NR scalable slot.',.5,.5,'ms',False,PHY),
 ('scs_khz','Normative LTE-M resource spacing15kHz, not NB-IoT3.75kHz.',15,15,'kHz',False,PHY),
 ('prb_subcarriers','Normative12subcarriers per regular PRB, distinct from optional sub-PRB UL allocation.',12,12,None,True,PHY),
 ('prb_bandwidth_khz','Normative180kHz resource block width; not occupied spectrum, channel BW or byte throughput.',180,180,'kHz',False,PHY),
 ('ul_symbols_per_slot','Normative7normalCP/6extendedCP ULsymbols per slot, includes channel-dependent overhead.',6,7,None,True,PHY),
 ('narrowband_prbs','Normative regular LTE-M narrowband six PRBs, not every serving carrier size.',6,6,None,True,PHY),
 ('wideband_prbs','Actual up-to-four DLnarrowbands per wideband; fewer when carrier has fewer than four narrowbands.',6,24,None,True,PHY),
 ('tdd_assignment','Actual UL/DL subframe assignment0..6, not a generic duty percentage.',0,6,None,True,PHY),
 ('tdd_switch_ms','Normative selected TDDswitchpoint periodicity5/10ms, not functional latency.',5,10,'ms',False,PHY),
 ('hd_guard_before_ms','Normative typeB no-DL subframe immediately before UL, not an available payload window.',1,1,'ms',False,PHY),
 ('hd_guard_after_ms','Normative typeB no-DL subframe immediately after UL.',1,1,'ms',False,PHY),
 ('nominal_max_power_dbm','Nominal selected UE class maximum excluding tolerance/MPR, not current output power.',None,None,'dBm',False,RF),
 ('output_power_dbm','Actual measured controlled transmit power; actual profile controls MPR/tolerance, not max-class default.',None,None,'dBm',False,RF),
 ('continuous_ul_ms','Actual continuous uplink duration;64ms selects HD-FDD frequency-error requirements.',0,None,'ms',False,RF),
 ('frequency_error_abs_ppm','Actual absolute frequency error observed over0.5ms; bound is not a measured default.',0,None,'ppm',False,RF)]:d(key,'number',meaning,source,lo,hi,unit,integer=integer)

for key,meaning in [
 ('ce_a_supported','Actual declared mandatory CE ModeA support, not inferred proof from category choice.'),
 ('ce_b_supported','Actual optional CE ModeB support; implies CE ModeA.'),
 ('ul_max_tbs_r14','Actual optional ce-PUSCH-NB-MaxTBS-r14 M1 ModeA1.4MHz2984-bit feature.'),
 ('dl_max_tbs_r17','Actual optional ce-PDSCH-MaxTBS-r17 M1 ModeA1.4MHz1736-bit feature.'),
 ('dl_64qam_r15','Actual optional connected non-repeated unicast CE ModeA DL64QAM support.'),
 ('wideband_r14','Actual ce-PDSCH-PUSCH-MaxBandwidth-r14 capability, not applicableM1 and mandatoryM2.'),
 ('subprb_r15','Actual optional ce-PUSCH-SubPRB-Allocation-r15 and scheduler support, not regular12-tone allocation.'),
 ('psm_enabled','Actual negotiated PSM; enabling it does not select timers or guarantee immediate reachability.'),
 ('edrx_enabled','Actual negotiated extended DRX; LTE-M paging differs from NB-IoT.'),
 ('capacity_confirmed','Actual complete approval, never True from one band/bandwidth or published peak rate.')]:d(key,'boolean',meaning)

REQUIRED=['edition','category','role','direction','duplex','ue_duplex','ce_mode','revision','device_source','binding_source',
 'network_source','regulatory_source','physical_source','scheduler_source','mac_rlc_source','rrc_nas_source',
 'application_source','security_source','capacity_source','acceptance_source']
REMOVED={key:'Removed foreign '+key+': actual LTE-M category, grants/CE/repetition/HARQ/RLC and shared-cell evidence replace generic CAN/Ethernet/radio defaults.'for key in
 ('bitrate','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
 'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput',
 'gateway_input_buffer','gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}


def semantics():
    rules=[dict(parameter='local_timing_evidence',allowed=[],source=PHY,source_revision='LTE-M is not an addressed I2C wire transaction')]
    def r(key,when=None,source=CAP,**kw):
        rules.append(dict(parameter='ltm_'+key,when={'ltm_edition':EDITION,**{'ltm_'+k:v for k,v in (when or {}).items()}},
            source=source,source_revision=SOURCES[source],**kw))
    for key,value in [('edition','REGISTERED_EDITION'),('category','REGISTERED_CATEGORY'),('service','REGISTERED_SERVICE'),
                      ('modulation','REGISTERED_MODULATION'),('power_class','REGISTERED_POWER_CLASS'),('grant_profile','REGISTERED_GRANT')]:
        rules.append(dict(parameter='ltm_registered_source',when={'ltm_'+key:value},required=True,source=CAP,source_revision=SOURCES[CAP]))
    r('band',allowed=list(BANDS),source=RF)
    for duplex,modes in [('FDD',['HD_FDD_TYPE_B','FD_FDD']),('TDD',['TDD'])]:
        r('ue_duplex',{'duplex':duplex},allowed=modes,source=PHY)
    for key in ('tdd_assignment','tdd_pattern','tdd_switch_ms','tdd_special_source'):
        r('duplex',when_present=['ltm_'+key],allowed=['TDD'],required=True,source=PHY)
    for key in ('hd_guard_before_ms','hd_guard_after_ms'):
        r('ue_duplex',when_present=['ltm_'+key],allowed=['HD_FDD_TYPE_B'],required=True,source=PHY)
    for key in ('power_class','nominal_max_power_dbm','output_power_dbm','frequency_error_abs_ppm'):
        r('role',when_present=['ltm_'+key],allowed=['UE'],required=True,source=RF)
    for band,(duplex,ul,dl,widths)in BANDS.items():
        w={'band':band};r('duplex',w,allowed=[duplex],source=RF)
        r('ue_duplex',w,allowed=['HD_FDD_TYPE_B','FD_FDD']if duplex=='FDD'else['TDD'],source=RF)
        r('carrier_bandwidth_mhz',w,allowed=list(widths),source=RF)
        for direction,bounds in [('UPLINK',ul),('DOWNLINK',dl)]:
            r('carrier_mhz',{**w,'direction':direction},minimum=bounds[0],maximum=bounds[1],source=RF)
        for category,maximum in [('M1',1.4),('M2',min(5,max(widths)))]:
            r('ue_max_bandwidth_mhz',{**w,'category':category},allowed=[maximum])
            r('allocated_bandwidth_mhz',{**w,'category':category},maximum=maximum)
        if band!=66:
            r('power_class',{**w,'role':'UE'},allowed=['2','3','5','6']if band in(31,72)else['3','5','6'],source=RF)
    r('power_class',{'role':'UE'},when_not={'ltm_ue_duplex':'HD_FDD_TYPE_B'},forbidden=['2'],source=RF)
    r('power_profile_source',{'role':'UE','band':66},required=True,source=RF)
    r('carrier_aggregation_source',{'band':66,'direction':'DOWNLINK'},when_ranges={'ltm_carrier_mhz':[2180,2200]},required=True,source=RF)
    r('band74_capability_source',{'band':74},required=True,source=RF)
    for band,ranges in [(28,[(713,723),(728,738)]),(71,[(673,678),(683,688)])]:
        w={'band':band,'direction':'UPLINK','carrier_bandwidth_mhz':20}
        r('carrier20_block',w,required=True,source=RF)
        for block,(lo,hi)in zip(['LOW','HIGH'],ranges):r('carrier_mhz',{**w,'carrier20_block':block},minimum=lo,maximum=hi,source=RF)
    for bw,prbs in CARRIER_PRBS.items():r('carrier_prbs',{'carrier_bandwidth_mhz':bw},allowed=[prbs],source=RF)
    r('allocated_prbs',maximum_parameter='ltm_carrier_prbs',source=PHY)
    r('allocated_bandwidth_mhz',maximum_parameter='ltm_carrier_bandwidth_mhz',source=RF)
    r('ce_a_supported',allowed=[True])
    r('ce_b_supported',{'ce_mode':'B'},allowed=[True],required=True)
    r('allocated_bandwidth_mhz',{'ce_mode':'B','direction':'UPLINK'},maximum=1.4)
    r('allocated_prbs',{'category':'M1'},maximum=6,source=PHY)
    r('allocated_prbs',{'category':'M2'},maximum=24,source=PHY)
    r('allocated_prbs',{'category':'M2','direction':'UPLINK','ce_mode':'B'},maximum=6,source=PHY)
    for direction,maximum in [('UPLINK',13),('DOWNLINK',12)]:
        r('allocated_prbs',{'category':'M2','direction':direction,'carrier_prbs':15},maximum=maximum,source=PHY)
    r('allocated_prbs',{'grant_profile':'NARROW_6'},maximum=6,source=PHY)
    r('grant_profile',when_greater_than={'ltm_allocated_prbs':6},required=True,
      allowed=['WIDE_PUSCH_5_C_RNTI','WIDE_PDSCH_5_C_RNTI','REGISTERED_GRANT'],source=PHY)
    for profile,direction in [('WIDE_PUSCH_5_C_RNTI','UPLINK'),('WIDE_PDSCH_5_C_RNTI','DOWNLINK')]:
        w={'grant_profile':profile}
        for key,value in [('category','M2'),('direction',direction),('rrc_state','CONNECTED'),('service','UNICAST'),('wideband_r14',True)]:
            r(key,w,allowed=[value],required=True,source=PHY)
        if direction=='UPLINK':r('ce_mode',w,allowed=['A'],source=PHY)
    r('wideband_r14',{'category':'M1'},forbidden=[True])
    r('wideband_r14',{'category':'M2'},allowed=[True])
    for category,flag,dl_limit,soft,ul_limit,l2 in [
        ('M1',False,1000,25344,1000,20000),('M1',True,1736,43008,2984,40000),('M2',None,4008,73152,6968,100000)]:
        dw={'category':category,**({'dl_max_tbs_r17':flag}if flag is not None else{})}
        uw={'category':category,**({'ul_max_tbs_r14':flag}if flag is not None else{})}
        r('dl_tb_limit_bits',dw,allowed=[dl_limit]);r('dl_soft_buffer_bits',dw,allowed=[soft])
        r('ul_tb_limit_bits',uw,allowed=[ul_limit]);r('layer2_capability_bytes',uw,allowed=[l2])
    # Supporting an optional ModeA capability does not prohibit ModeB operation.
    # Using a block larger than the basic M1limit requires that capability and A.
    for flag,direction in [('ul_max_tbs_r14','UPLINK'),('dl_max_tbs_r17','DOWNLINK')]:
        w={'category':'M1','direction':direction}
        r('ce_mode',w,when_greater_than={'ltm_actual_tb_bits':1000},allowed=['A'])
        r(flag,w,when_greater_than={'ltm_actual_tb_bits':1000},allowed=[True],required=True)
    r('wideband_prbs',allowed=[6,12,18,24],source=PHY)
    for prbs,wide in [(6,6),(15,12),(25,24),(50,24),(75,24),(100,24)]:
        r('wideband_prbs',{'carrier_prbs':prbs},allowed=[wide],source=PHY)
    r('modulation',{'direction':'UPLINK'},forbidden=['64QAM','256QAM'])
    r('modulation',{'direction':'DOWNLINK'},forbidden=['256QAM'])
    w={'direction':'DOWNLINK','modulation':'64QAM'}
    for key,value in [('dl_64qam_r15',True),('ce_mode','A'),('rrc_state','CONNECTED'),('service','UNICAST'),('repetitions',1)]:
        r(key,w,allowed=[value],required=True)
    for direction,limit in [('UPLINK','ul_tb_limit_bits'),('DOWNLINK','dl_tb_limit_bits')]:
        r('actual_tb_bits',{'direction':direction},maximum_parameter='ltm_'+limit)
        r(limit,{'direction':direction},when_present=['ltm_actual_tb_bits'],required=True)
    for key,flag in [('dl_tb_limit_bits','dl_max_tbs_r17'),('dl_soft_buffer_bits','dl_max_tbs_r17'),
                     ('ul_tb_limit_bits','ul_max_tbs_r14'),('layer2_capability_bytes','ul_max_tbs_r14')]:
        r(flag,{'category':'M1'},when_present=['ltm_'+key],required=True)
    for cp,count in [('NORMAL',7),('EXTENDED',6)]:r('ul_symbols_per_slot',{'cyclic_prefix':cp},allowed=[count],source=PHY)
    for assignment,(pattern,period)in TDD.items():
        w={'duplex':'TDD','tdd_assignment':assignment};r('tdd_pattern',w,allowed=[pattern],source=PHY);r('tdd_switch_ms',w,allowed=[period],source=PHY)
    r('tdd_assignment',{'duplex':'TDD'},required=True,source=PHY);r('tdd_special_source',{'duplex':'TDD'},required=True,source=PHY)
    for cls,power in [('2',26),('3',23),('5',20),('6',14)]:
        r('nominal_max_power_dbm',{'role':'UE','power_class':cls},when_not={'ltm_band':66},allowed=[power],source=RF)
    # Frequency error is an actual measured absolute value, never a proposal.
    for ue in ('TDD','FD_FDD'):r('frequency_error_abs_ppm',{'role':'UE','ue_duplex':ue},maximum=.1,source=RF)
    w={'role':'UE','ue_duplex':'HD_FDD_TYPE_B'}
    r('frequency_error_abs_ppm',w,when_ranges={'ltm_continuous_ul_ms':[0,64]},maximum=.1,source=RF)
    r('frequency_error_abs_ppm',w,when_greater_than={'ltm_continuous_ul_ms':64},when_ranges={'ltm_carrier_mhz':[0,1000]},maximum=.2,source=RF)
    r('frequency_error_abs_ppm',w,when_greater_than={'ltm_continuous_ul_ms':64,'ltm_carrier_mhz':1000},maximum=.1,source=RF)
    for flag,target in [('psm_enabled','psm_timer_encoding'),('edrx_enabled','edrx_timer_encoding')]:r(target,{flag:True},required=True)
    for key in ('actual_tb_bits','allocated_prbs','allocated_bandwidth_mhz','repetitions','carrier_mhz','frequency_error_abs_ppm'):
        for target in ('band','carrier_bandwidth_mhz','ce_mode','category'):
            r(target,when_present=['ltm_'+key],required=True)
    r('frequency_error_source',when_present=['ltm_frequency_error_abs_ppm'],required=True,source=RF)
    r('carrier_mhz',when_present=['ltm_frequency_error_abs_ppm'],required=True,source=RF)
    r('power_profile_source',when_present=['ltm_output_power_dbm'],required=True,source=RF)
    r('carrier_prbs',when_present=['ltm_allocated_prbs'],required=True,source=RF)
    for key,targets in [('ue_max_bandwidth_mhz',['band']),('carrier_prbs',['carrier_bandwidth_mhz']),
                        ('wideband_prbs',['carrier_prbs','carrier_bandwidth_mhz']),('ul_symbols_per_slot',['cyclic_prefix']),
                        ('nominal_max_power_dbm',['band','power_class']),('output_power_dbm',['band','power_class']),
                        ('tdd_pattern',['duplex','tdd_assignment']),('tdd_switch_ms',['duplex','tdd_assignment'])]:
        for target in targets:r(target,when_present=['ltm_'+key],required=True)
    r('continuous_ul_ms',{'role':'UE','ue_duplex':'HD_FDD_TYPE_B'},when_present=['ltm_frequency_error_abs_ppm'],required=True,source=RF)
    return dict(rate_model={'type':'LTE_M_CATEGORY_CE_GRANT_AND_SHARED_CELL_DEPENDENT','fields':[]},
        required_parameters=['ltm_'+v for v in REQUIRED],native_parameter_prefixes=['ltm_'],parameter_constraints=rules,
        physical_layer_profile_id='lte_m_actual_eutra_radio',medium_access_model='ENODEB_GRANTS_WITH_CE_REPETITION_AND_DUPLEX_GUARDS',
        arbitration_model_id='ENODEB_GRANTS_WITH_CE_REPETITION_AND_DUPLEX_GUARDS',
        mechanisms={'addressing':['COMMISSIONED_UE_AND_NETWORK_ASSIGNED_CELL'],
          'medium_access':['ENODEB_SHARED_CELL_SCHEDULER','CE_QUALIFIED_RANDOM_ACCESS'],
          'integrity':['CHANNEL_CODING_DISTINCT_FROM_AS_NAS_AND_APPLICATION_INTEGRITY'],
          'services':['LTE_M_M1','LTE_M_M2','SEPARATELY_SELECTED_APPLICATION_TRANSPORT'],
          'reliability':['CHANNEL_CE_HARQ','RLC_MODE_DEPENDENT_ARQ'],
          'supervision':['RADIO_ACK_NOT_FUNCTIONAL_COMPLETION']})


def fields():
    result=[];required=set(semantics()['required_parameters'])
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items()if v is not None};key=spec['key'].removeprefix('ltm_')
        item.update(label=key.replace('_',' '),category='communication',scope='network',required=spec['key']in required,
          editable=True,parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
        if item['type']in('number','boolean'):item['schema_when']={'ltm_edition':EDITION}
        proposals=[]
        def p(value,source=spec['source'],**when):
            proposals.append(dict(when={'ltm_edition':EDITION,**{'ltm_'+k:v for k,v in when.items()}},value=value,source=source,source_revision=SOURCES[source]))
        fixed={'frame_ms':10,'subframe_ms':1,'slot_ms':.5,'scs_khz':15,'prb_subcarriers':12,'prb_bandwidth_khz':180,'narrowband_prbs':6,'dl_spatial_layers':1}
        if key in fixed:p(fixed[key])
        if key in ('hd_guard_before_ms','hd_guard_after_ms'):p(1,ue_duplex='HD_FDD_TYPE_B')
        for band,(duplex,ul,dl,widths)in BANDS.items():
            if key=='carrier_bandwidth_mhz':p(min(widths),band=band)
            if key=='ue_max_bandwidth_mhz':
                for category,bw in [('M1',1.4),('M2',min(5,max(widths)))]:p(bw,category=category,band=band)
            if key=='nominal_max_power_dbm'and band!=66:
                for cls,power in [('3',23),('5',20),('6',14)]:p(power,role='UE',band=band,power_class=cls)
                if band in(31,72):p(26,role='UE',band=band,power_class='2',ue_duplex='HD_FDD_TYPE_B')
        if key=='carrier_prbs':
            for bw,count in CARRIER_PRBS.items():p(count,carrier_bandwidth_mhz=bw)
        if key=='wideband_prbs':
            for prbs,wide in [(6,6),(15,12),(25,24),(50,24),(75,24),(100,24)]:p(wide,carrier_prbs=prbs)
        for category,flag,dl_limit,soft,ul_limit,l2 in [('M1',False,1000,25344,1000,20000),('M1',True,1736,43008,2984,40000),('M2',None,4008,73152,6968,100000)]:
            values={'dl_tb_limit_bits':dl_limit,'dl_soft_buffer_bits':soft,'ul_tb_limit_bits':ul_limit,'layer2_capability_bytes':l2}
            if key in values:p(values[key],category=category,**({'dl_max_tbs_r17'if key.startswith('dl_')else'ul_max_tbs_r14':flag}if flag is not None else{}))
        if key=='ul_symbols_per_slot':
            for cp,count in [('NORMAL',7),('EXTENDED',6)]:p(count,cyclic_prefix=cp)
        for assignment,(pattern,period)in TDD.items():
            if key=='tdd_pattern':p(pattern,duplex='TDD',tdd_assignment=assignment)
            if key=='tdd_switch_ms':p(period,duplex='TDD',tdd_assignment=assignment)
        # Actual band/category/grants/addresses/output/error/optional abilities,
        # timers, approval and source references never receive invented defaults.
        if proposals:item.update(conditional_defaults=proposals,default_status='PROPOSED_CONDITIONAL')
        result.append(item)
    return result
