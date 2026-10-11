"""NFC RF and host declarations with explicit protocol, role and firmware scope."""
ECMA='https://ecma-international.org/wp-content/uploads/ECMA-340_4th_edition_june_2024.pdf'
DATA='https://www.nxp.com/docs/en/data-sheet/PN7160_PN7161.pdf'
HOST='https://www.nxp.com/docs/en/user-manual/UM11495.pdf'
FORUM='https://nfc-forum.org/build/specifications/analog-technical-specification/'
SOURCES={ECMA:'ECMA-340 fourth edition June2024: clauses7-12 andAnnexA; NFCIP1 only, not all NFC-A/B/F/V or NFCForum certification',
 DATA:'NXP PN7160/PN7161 Rev4.2 July22 2026: firmware6, interfaces11.6, electrical/operating conditions; model-specific, not universal NFC',
 HOST:'NXP UM11495 Rev1.8 June2 2025: NCI packet3.3, hostI2C/SPI4, logicalconnections5.3; older firmware features qualified by Rev4.2 data sheet',
 FORUM:'NFCForum Analog specification publisher metadata: release3.0 adds20mm operatingvolume; full licensed normative text not read'}
DECLARATIONS=[]
def d(k,t,meaning,lo=None,hi=None,unit=None,options=None,source=ECMA,integer=False):
    DECLARATIONS.append(dict(key='nf_'+k,type=t,description=meaning,min=lo,max=hi,unit=unit,options=options,
        source=source,source_revision=SOURCES[source],integer=integer))
for k,meaning,opts,src in [
 ('implementation','Actual installed controller/model or independently qualified implementation, independent of industry.',['PN7160','PN7161','REGISTERED'],DATA),
 ('protocol','Actual NFCIP1 or selected tag/card protocol; NFC-A/B/F/V are different RF paths.',['NFCIP1_ECMA340_2024','NFC_A','NFC_B','NFC_F','NFC_V','REGISTERED'],ECMA),
 ('operation','Actual reader/writer, card emulation or NFCIP1 peer mode, not host connection.',['READER_WRITER','CARD_EMULATION','PEER'],DATA),
 ('mode','Actual passive load-modulated target versus active alternating own fields.',['PASSIVE','ACTIVE'],ECMA),
 ('role','Actual initiator/target or reader/card. A host I2C master is not an NFC initiator by implication.',['INITIATOR','TARGET','READER','CARD'],ECMA),
 ('direction','Actual RF transfer direction, separate from DH/NFCC packet direction.',['INITIATOR_TO_TARGET','TARGET_TO_INITIATOR','READER_TO_CARD','CARD_TO_READER'],ECMA),
 ('rate_basis','Named rounded RF rate versus exact carrier/divisor. Neither is host I2C/SPI clock.',['NOMINAL_LABEL','CARRIER_DIVISOR'],ECMA),
 ('rate_profile','Fully specified NFCIP1 PHY versus higher active divisors needing independently qualified modulation/coding.',['SPECIFIED','EXTENDED_REGISTERED'],ECMA),
 ('host','Actual ordered I2C versus SPI hardware interface, not interchangeable software setting.',['I2C','SPI','REGISTERED'],HOST),
 ('host_direction','Actual NCI direction between devicehost and controller.',['DH_TO_NFCC','NFCC_TO_DH'],HOST),
 ('host_i2c_mode','PN7160 host supports Standard, Fast and High-speed; no automatic Fast-mode-plus.',['STANDARD','FAST','HIGH_SPEED'],HOST),
 ('nci_kind','Actual message type: data0/command1/response2/notification3.',['DATA','COMMAND','RESPONSE','NOTIFICATION'],HOST),
 ('rf_state','Actual selected controller RF-state, idle dynamicNDEF/loopback versus staticRF exchange.',['IDLE','NON_IDLE'],HOST),
 ('logical_kind','Actual staticRF, dynamicNDEF or loopback connection; not multiple simultaneous RF capacities.',['STATIC_RF','DYNAMIC_NDEF','DYNAMIC_LOOPBACK'],HOST),
 ('dep_pdu','Actual NFCIP1 DEP Information, ACK/NACK, protected or supervisory, with own header/size semantics.',['INFORMATION','ACK','NACK','PROTECTED','TIMEOUT_EXTENSION','ATTENTION'],ECMA),
 ('coding','Actual direction/protocol/rate coding; no universal Manchester or CAN bit stuffing.',['MODIFIED_MILLER','MANCHESTER','BPSK','NRZ','PPM_1_OF_4','REGISTERED'],DATA),
]:d(k,'select',meaning,options=opts,source=src)
for k,meaning,src in [
 ('device_source','Actual model/firmware/capability evidence; a catalog entry is not installed device proof.',DATA),
 ('mapping_source','Actual RF role, peer/tag, activation, selected protocol and encoding agreement.',ECMA),
 ('physical_source','Actual antenna tuning/operating volume/field/tolerance/regulatory measurements. No guaranteed distance from generic NFC label.',DATA),
 ('schedule_source','Actual activation, anticollision, whole RF/host exchanges, retries and application timing bound.',ECMA),
 ('acceptance_source','Actual application/security/deadline/freshness acceptance, not certified by an RF rate.',ECMA),
 ('registered_source','Actual selected alternative implementation/protocol/extendedPHY source and revision.',ECMA),
 ('host_source','Actual ordered interface, pins, clocks, IRQ/NSS/wake and driver behavior.',HOST),
 ('firmware_hex','Actual firmware triplet as six hex digits, e.g.12500a means displayed12.50.0A, not decimal18.80.10.',DATA),
 ('reset_ntf_hex','Actual PN7160/PN7161 CORE_RESET_NTF; byte9 model and10..12 firmware. Header/disposition still actual.',DATA),
 ('nci_hex','Actual host NCI packet including3-byte header and payload; not over-air NFC frame.',HOST),
 ('connection_source','Actual CORE_INIT/activation/connection result and current credits/max payload, not universal255 application bytes.',HOST),
 ('transaction_source','Actual uninterrupted request/response state, chaining/PSL/PNI and bounds.',ECMA),
 ('security_source','Actual NFC-SEC or tag/application authentication and protected encoding; CRC does not provide authenticity.',ECMA),
 ('field_qualification_source','Actual physical field limits/positions qualification; ECMA8.2 contains Hmin/Hmin wording ambiguity, no silent correction.',ECMA),
 ('ecp_authorization_source','Actual formal Apple ECP authorization when selected PN7161 feature used; no fabricated authorization.',DATA),
]:d(k,'text',meaning,source=src)
for k,meaning,lo,hi,u,src,integer in [
 ('carrier_hz','Actual nominal13.56MHz carrier, measured deviation qualified separately.',1,None,'Hz',ECMA,False),
 ('divisor','Actual carrier divisor128/64/32; selected PN7160 reader A/B adds16, V512.',1,None,None,ECMA,True),
 ('bit_duration_us','Exact carrier/divisor bit duration distinct rounded named rate.',0,None,'us',ECMA,False),
 ('model_id','Actual reset modelID0x61 PN7160 or0x71 PN7161.',0,255,None,DATA,True),
 ('fw_rom','Actual firmware ROM hex octet0x12=18 decimal on qualified12.50 firmware branch.',0,255,None,DATA,True),
 ('fw_major','Actual major hex octet0x50=80 decimal, not50 decimal.',0,255,None,DATA,True),
 ('fw_patch','Actual patch hex octet0x0A=10; P2P/typeF legacy availability stops after0A.',0,255,None,DATA,True),
 ('host_clock_bps','Actual DH-driven I2C/SPI clock rate, separate NFC RF bitrate.',1,None,'bit/s',HOST,False),
 ('host_address_bits','Actual I2C address width: PN7160 sevenbit, not tenbit.',1,None,'bit',HOST,True),
 ('host_address','Actual strapped sevenbit28..2Bhex; no automatic actual address28.',0,127,None,HOST,True),
 ('host_write_address','Actual eightbit address byte adds low R/W=0; not sevenbit slave identity.',0,255,None,HOST,True),
 ('host_read_address','Actual eightbit address byte adds low R/W=1.',0,255,None,HOST,True),
 ('host_spi_mode','Actual supported CPOL/CPHA SPI mode0..3; PN7160 halfduplex even with separateMOSI/MISO.',0,3,None,HOST,True),
 ('spi_direction_octet','Actual transfer detector0xxxxxxx write orFF read; additional host byte not RF overhead.',0,255,None,HOST,True),
 ('host_extra_octets','Actual I2C adds0/SPIadds1 transfer direction byte, excluding electrical address/ACK/clocks.',0,None,'byte',HOST,True),
 ('host_bytes','Actual NCI packet plus host mapping prefix; not whole I2C START/address/ACK bound.',3,None,'byte',HOST,True),
 ('nci_mt','Actual threebit message type0..3;4..7reserved.',0,7,None,HOST,True),
 ('nci_header0','Actual first NCI headeroctet: MTbits7..5, PBFbit4, GID/control orConnID/data low4.',0,255,None,HOST,True),
 ('nci_pbf','Actual packet boundaryflag1 means notfinal;0 complete orlastfragment.',0,1,None,HOST,True),
 ('nci_gid','Actual control groupID fourbits; definedopcode/source required, not all0..15groups implemented.',0,15,None,HOST,True),
 ('nci_oid','Actual control opcode sixbits; supportedopcode qualified independently.',0,63,None,HOST,True),
 ('nci_conn_id','Actual data connectionID fourbits, not IP endpoint.',0,15,None,HOST,True),
 ('nci_length','Actual8bit payload length, mayzero; not applicationlength or RF frame length.',0,255,'byte',HOST,True),
 ('nci_packet_bytes','Actual3-byte header plus NCI payload0..255, max258.',3,258,'byte',HOST,True),
 ('max_control_payload','Actual initialization-reported maxcontrol packet payload, not universal negotiated value.',1,255,'byte',HOST,True),
 ('max_data_payload','Actual activation/connection-reported maxdata packet payload.',1,255,'byte',HOST,True),
 ('mapping_mtu','Actual optional NCI transport MTU includes header; packet must fit, fragmentation perlogicalconnection.',3,None,'byte',HOST,True),
 ('credits','Actual available credits on selected connection; PN7160 limitedto1, zero means wait.',0,255,None,HOST,True),
 ('dynamic_connections','Actual PN7160 atmostone additional dynamic connection; no universalNFCCcount.',0,None,None,HOST,True),
 ('dep_len','Actual NFCIP1 transport LEN3..255 counts two CMDbytes, Byte1..n and LENitself; excludes RFCRC/preamble.',3,255,'byte',ECMA,True),
 ('dep_body_bytes','Actual NFCIP1 Byte1..n includingPFB/optionalDID/NAD, not solely userbytes.',0,252,'byte',ECMA,True),
 ('dep_lr','Actual negotiated LR0..3 gives Byte1..n limit64/128/192/252.',0,3,None,ECMA,True),
 ('dep_body_limit','Actual negotiated Byte1..n length limit fromLR, not advertisedNCI255.',1,252,'byte',ECMA,True),
 ('dep_pfb','Actual PFB fromtype/chaining/DID/NAD/PNI; reserved forms rejected.',0,255,None,ECMA,True),
 ('dep_pni','Actual peractivatedtarget packet number0..3; initial0 not globalcounter acrossdevices.',0,3,None,ECMA,True),
 ('dep_did','Actual NFCIP1 deviceidentifier where used; range determined by selectedactivation, actualsource.',0,14,None,ECMA,True),
 ('dep_nad','Actual optional nodeaddress octet, not inferredfromIP.',0,255,None,ECMA,True),
 ('dep_cmd1','Actual D4request versusD5response, not genericCANidentifier.',0,255,None,ECMA,True),
 ('dep_cmd2','Actual06DEP_REQ/07DEP_RES.',0,255,None,ECMA,True),
 ('dep_data_bytes','Actual information/protected/supervisory data bytes distinct DEP header and NFC application chain.',0,None,'byte',ECMA,True),
 ('dep_header_bytes','Actual PFB1 plus optionalDID/NAD; protectedsecurity format separatequalification.',1,3,'byte',ECMA,True),
 ('wt','Actual target waitingtime exponent0..14;15reserved, default14 proposal only NFCIP1.',0,14,None,ECMA,True),
 ('response_wait_us','Actual tRW4096/fc*2^WT measured between rate-specific modulation edges; rounded302us not exact.',0,None,'us',ECMA,False),
 ('rtox','Actual timeout-extension factor1..59;0/60..63reserved.',1,59,None,ECMA,True),
 ('extended_wait_us','Actual intermediate wait=min(tRW*RTOX,tRW_MAX), only target extension procedure.',0,None,'us',ECMA,False),
 ('initial_delay_us','Actual initialRFCA tIDT strictlygreater4096/fc, not rounded302us.',0,None,'us',ECMA,False),
 ('rf_wait_us','Actual tRFW512/fc.',0,None,'us',ECMA,False),
 ('rf_random_n','Actual initial/activation randomslot0..3; laterexchanges use0.',0,3,None,ECMA,True),
 ('initial_guard_us','Actual initialfieldon->command guard strictlygreater5000us.',0,None,'us',ECMA,False),
 ('active_delay_us','Actual activeRFCA sense delay768/fc..2559/fc.',0,None,'us',ECMA,False),
 ('active_guard_us','Actual activeRFCA fieldon guard strictlygreater1024/fc.',0,None,'us',ECMA,False),
 ('rf_preamble_bits','Actual passive212/424NFCIP1 minimum48Manchester zero bits; not allNFCframes.',0,None,'bit',ECMA,True),
 ('field_a_m','Actual physical field measurement at declared operatingposition, no implicit rangeguarantee.',0,None,'A/m rms',ECMA,False),
 ('field_threshold_a_m','Nominal externalfielddetect threshold0.1875A/m forNFCIP1; actualqualifieddetector distinct.',0,None,'A/m rms',ECMA,False),
 ('measured_carrier_hz','Actual carrier measurement, not nominal13.56MHz.',1,None,'Hz',DATA,False),
 ('carrier_tolerance_hz','Actual qualified oscillator/regulatorycarrier tolerance; datasheet contrasts7000HzISOand100ppmFCC.',0,None,'Hz',DATA,False),
 ('operating_distance_mm','Actual qualified operatingvolume/range; no universal20mm/100mm default.',0,None,'mm',DATA,False),
 ('vbatt_v','Actual selectedPN7160supply2.5..5.5passivetarget or2.8..5.5activeRF.',0,None,'V',DATA,False),
 ('vddpad_v','Actual selectedIOrail either1.65..1.95 or3.0..3.6V, not continuousrange.',0,None,'V',DATA,False),
 ('tx_supply_v','Actual transmitterstage2.7..5.25V, distinctVBAT/IO.',0,None,'V',DATA,False),
 ('temperature_c','Actual operatingambient−30..85C withselecteddatasheetPCB/thermalconditions, notSTcontrollerlimits.',None,None,'C',DATA,False),
]:d(k,'number',meaning,lo,hi,u,source=src,integer=integer)
for k,meaning,src in [
 ('ecp','Actual PN7161 AppleEnhancedContactlessPolling enabled, requiresformalhardware-specificauthorization.',DATA),
 ('host_follower_only','Actual PN7160host is followeronly; DH drivesclock.',HOST),
 ('host_half_duplex','Actual PN7160SPItransferdirection prevents simultaneousNCIread/write.',HOST),
 ('nci_last','Actual complete orlastpacket versus nonfinalsegment.',HOST),
 ('nci_send','Actual attempt to sendDHdata requiresnonzerocredit.',HOST),
 ('dep_did_present','Actual DEP header containsDID; actualmappedactivation separate.',ECMA),
 ('dep_nad_present','Actual DEP header containsNAD.',ECMA),
 ('dep_more','Actual chainingflag versus finalInformationPDU.',ECMA),
 ('transaction_uninterrupted','Actual initialization/anticollision/datatransfer transaction notinterleavedwithanother.',DATA),
 ('psl_during_data','Actual PN7160speed change duringdatatransfer prohibited; PSLselection earlier.',DATA),
 ('mode_changed','Actual NFCIP1active/passive mode change midtransaction prohibited.',ECMA),
 ('later_exchange','Actual beyondactivation: no randomresponseRFslot delay.',ECMA),
]:d(k,'boolean',meaning,source=src)
REQUIRED=['implementation','protocol','operation','mode','role','direction','rate_basis','carrier_hz','divisor',
 'device_source','mapping_source','physical_source','schedule_source','acceptance_source']
REMOVED={k:'No universal NFC '+k+'; selected RF protocol/device/firmware, host packet and transaction evidence replace foreign transport policies.'
 for k in('mtu_bytes','duplex','vlan_id','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
 'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','recovery_ms','link_fault_detect_ms','failover_ms','restore_delay_ms','mtbf_ms')}

def semantics():
    rules=[]
    def r(k,w=None,source=ECMA,**kw):
        rules.append(dict(parameter='bitrate_bps' if k=='bitrate' else k if k in('payload_bytes','local_timing_evidence')else'nf_'+k,
            when={'nf_'+key:value for key,value in(w or{}).items()},source=source,source_revision=SOURCES[source],**kw))
    for k in REQUIRED:r(k,required=True)
    r('local_timing_evidence',allowed=[])
    r('carrier_hz',allowed=[13560000]);r('nci_mt',allowed=[0,1,2,3],source=HOST)
    r('bit_duration_us',equal_expression={'product':['nf_divisor',1000000/13560000]})
    r('registered_source',{'implementation':'REGISTERED'},required=True)
    r('registered_source',{'protocol':'REGISTERED'},required=True)
    r('registered_source',{'rate_profile':'EXTENDED_REGISTERED'},required=True)
    dep={'protocol':'NFCIP1_ECMA340_2024'}
    r('operation',dep,allowed=['PEER']);r('role',dep,allowed=['INITIATOR','TARGET']);r('direction',dep,allowed=['INITIATOR_TO_TARGET','TARGET_TO_INITIATOR'])
    r('rate_profile',dep,required=True)
    r('divisor',{**dep,'rate_profile':'SPECIFIED'},allowed=[128,64,32])
    r('mode',{**dep,'rate_profile':'EXTENDED_REGISTERED'},allowed=['ACTIVE'])
    r('divisor',{**dep,'rate_profile':'EXTENDED_REGISTERED'},allowed=[16,8,4,2])
    r('mode_changed',dep,allowed=[False]);r('rf_random_n',{'later_exchange':True},allowed=[0])
    r('wt',dep,maximum=14)
    r('response_wait_us',dep,equal_expression={'product':[4096/13.56,{'power':[2,'nf_wt']}]})
    r('wt',dep,when_present=['nf_response_wait_us'],required=True)
    r('extended_wait_us',dep,equal_expression={'minimum':[{'product':['nf_response_wait_us','nf_rtox']},4096/13.56*16384]})
    for k in('response_wait_us','rtox'):r(k,dep,when_present=['nf_extended_wait_us'],required=True)
    r('initial_delay_us',dep,exclusive_minimum=4096/13.56)
    r('rf_wait_us',dep,allowed=[512/13.56]);r('initial_guard_us',dep,exclusive_minimum=5000)
    r('active_delay_us',{**dep,'mode':'ACTIVE'},minimum=768/13.56,maximum=2559/13.56)
    r('active_guard_us',{**dep,'mode':'ACTIVE'},exclusive_minimum=1024/13.56)
    r('field_threshold_a_m',dep,allowed=[.1875])
    # The published passive field upper-bound sentence says Hmin twice. Retain
    # explicit physical qualification instead of silently rewriting the source.
    r('field_qualification_source',dep,when_present=['nf_field_a_m'],required=True)
    r('field_a_m',{**dep,'mode':'ACTIVE'},minimum=1.5,maximum=7.5)
    for divisor,nominal in [(128,106000),(64,212000),(32,424000),(16,848000),(8,1695000),(4,3390000),(2,6780000),(512,26480)]:
        r('bitrate',{'divisor':divisor,'rate_basis':'NOMINAL_LABEL'},allowed=[nominal])
        r('bitrate',{'divisor':divisor,'rate_basis':'CARRIER_DIVISOR'},allowed=[13560000/divisor])
    for impl,model in [('PN7160',0x61),('PN7161',0x71)]:
        w={'implementation':impl}
        for k in('fw_rom','fw_major','fw_patch'):r(k,w,required=True,source=DATA)
        r('model_id',w,allowed=[model],source=DATA);r('fw_rom',w,allowed=[0x12],source=DATA);r('fw_major',w,allowed=[0x50],source=DATA)
        for protocol in('NFCIP1_ECMA340_2024','NFC_F'):r('fw_patch',{**w,'protocol':protocol},maximum=0x0a,source=DATA)
        r('divisor',{**w,'protocol':'NFCIP1_ECMA340_2024'},allowed=[128,64,32],source=DATA)
        r('fw_patch',{**w,'operation':'CARD_EMULATION','protocol':'NFC_F'},maximum=0x0a,source=DATA)
        for protocol in('NFC_A','NFC_B'):
            r('divisor',{**w,'protocol':protocol,'operation':'READER_WRITER'},allowed=[128,64,32,16],source=DATA)
            r('divisor',{**w,'protocol':protocol,'operation':'CARD_EMULATION'},allowed=[128,64,32],source=DATA)
        r('divisor',{**w,'protocol':'NFC_F'},allowed=[64,32],source=DATA)
        r('divisor',{**w,'protocol':'NFC_V'},allowed=[512],source=DATA)
        r('operation',{**w,'protocol':'NFC_V'},allowed=['READER_WRITER'],source=DATA)
        for protocol in('NFC_A','NFC_B','NFC_F','NFC_V'):r('mode',{**w,'protocol':protocol},allowed=['PASSIVE'],source=DATA)
        r('mode_changed',w,allowed=[False],source=DATA);r('transaction_uninterrupted',w,allowed=[True],source=DATA);r('psl_during_data',w,allowed=[False],source=DATA)
        r('temperature_c',w,minimum=-30,maximum=85,source=DATA)
        r('tx_supply_v',w,minimum=2.7,maximum=5.25,source=DATA)
        r('vddpad_v',w,minimum=1.65,maximum=3.6,source=DATA)
        r('vddpad_v',w,when_greater_than={'nf_vddpad_v':1.95},minimum=3,source=DATA)
        if impl=='PN7160':r('ecp',w,allowed=[False],source=DATA)
        r('ecp_authorization_source',{**w,'ecp':True},required=True,source=DATA)
        r('host',w,allowed=['I2C','SPI'],source=HOST)
        r('host_follower_only',w,allowed=[True],source=HOST)
        r('host_half_duplex',{**w,'host':'SPI'},allowed=[True],source=HOST)
        r('host_clock_bps',{**w,'host':'SPI'},maximum=7000000,source=HOST)
        r('spi_direction_octet',{**w,'host':'SPI','host_direction':'DH_TO_NFCC'},maximum=127,source=HOST)
        r('spi_direction_octet',{**w,'host':'SPI','host_direction':'NFCC_TO_DH'},allowed=[255],source=HOST)
        r('host_address_bits',{**w,'host':'I2C'},allowed=[7],source=HOST)
        r('host_address',{**w,'host':'I2C'},minimum=0x28,maximum=0x2b,source=HOST)
        for mode,limit in [('STANDARD',100000),('FAST',400000),('HIGH_SPEED',3400000)]:r('host_clock_bps',{**w,'host':'I2C','host_i2c_mode':mode},maximum=limit,source=HOST)
        r('host_i2c_mode',{**w,'host':'I2C'},when_present=['nf_host_clock_bps'],required=True,source=HOST)
        r('credits',w,maximum=1,source=HOST);r('dynamic_connections',w,maximum=1,source=HOST)
        r('rf_state',{**w,'logical_kind':'STATIC_RF'},allowed=['NON_IDLE'],source=HOST)
        for logical in('DYNAMIC_NDEF','DYNAMIC_LOOPBACK'):r('rf_state',{**w,'logical_kind':logical},allowed=['IDLE'],source=HOST)
    for impl in('PN7160','PN7161'):
        r('vbatt_v',{'implementation':impl},minimum=2.5,maximum=5.5,source=DATA)
        r('vbatt_v',{'implementation':impl,'role':'READER'},minimum=2.8,source=DATA)
        r('vbatt_v',{'implementation':impl,'role':'INITIATOR'},minimum=2.8,source=DATA)
        r('vbatt_v',{'implementation':impl,'role':'TARGET','mode':'ACTIVE'},minimum=2.8,source=DATA)
    r('firmware_hex',pattern=r'[0-9A-Fa-f]{6}',integer_bitfields=[dict(offset=16,width=8,parameter='nf_fw_rom'),dict(offset=8,width=8,parameter='nf_fw_major'),dict(offset=0,width=8,parameter='nf_fw_patch')],source=DATA)
    r('reset_ntf_hex',pattern=r'600009[0-9A-Fa-f]{10}[67]1[0-9A-Fa-f]{6}',hex_octets=[dict(offset=8,width=1,parameter='nf_model_id'),dict(offset=9,width=1,parameter='nf_fw_rom'),dict(offset=10,width=1,parameter='nf_fw_major'),dict(offset=11,width=1,parameter='nf_fw_patch')],source=DATA)
    r('host_source',when_present=['nf_host'],required=True,source=HOST)
    r('host_extra_octets',{'host':'I2C'},allowed=[0],source=HOST);r('host_extra_octets',{'host':'SPI'},allowed=[1],source=HOST)
    r('host_bytes',equal_expression={'sum':['nf_nci_packet_bytes','nf_host_extra_octets']},source=HOST)
    r('host_write_address',equal_expression={'product':['nf_host_address',2]},source=HOST)
    r('host_read_address',equal_expression={'sum':[{'product':['nf_host_address',2]},1]},source=HOST)
    r('nci_packet_bytes',equal_expression={'sum':[3,'nf_nci_length']},source=HOST)
    r('nci_length',when_present=['nf_nci_packet_bytes'],required=True,source=HOST)
    r('nci_packet_bytes',maximum_parameter='nf_mapping_mtu',source=HOST)
    r('nci_last',{'nci_pbf':0},allowed=[True],source=HOST);r('nci_last',{'nci_pbf':1},allowed=[False],source=HOST)
    for kind,mt in [('DATA',0),('COMMAND',1),('RESPONSE',2),('NOTIFICATION',3)]:
        w={'nci_kind':kind};r('nci_mt',w,allowed=[mt],source=HOST)
        if kind=='DATA':
            r('nci_length',w,maximum_parameter='nf_max_data_payload',source=HOST)
            r('nci_conn_id',w,required=True,source=HOST)
            r('nci_header0',w,equal_expression={'sum':[{'product':[32,'nf_nci_mt']},{'product':[16,'nf_nci_pbf']},'nf_nci_conn_id']},source=HOST)
        else:
            for k in('nci_gid','nci_oid'):r(k,w,required=True,source=HOST)
            r('nci_length',{**w,'host_direction':'DH_TO_NFCC'},maximum_parameter='nf_max_control_payload',source=HOST)
            r('nci_header0',w,equal_expression={'sum':[{'product':[32,'nf_nci_mt']},{'product':[16,'nf_nci_pbf']},'nf_nci_gid']},source=HOST)
            r('host_direction',w,allowed=['DH_TO_NFCC']if kind=='COMMAND'else['NFCC_TO_DH'],source=HOST)
    r('credits',{'nci_kind':'DATA','host_direction':'DH_TO_NFCC','nci_send':True},required=True,minimum=1,source=HOST)
    for k in('connection_source','max_data_payload'):r(k,{'nci_kind':'DATA'},required=True,source=HOST)
    r('nci_hex',hex_bytes_parameter='nf_nci_packet_bytes',hex_octets=[dict(offset=0,width=1,parameter='nf_nci_header0'),dict(offset=2,width=1,parameter='nf_nci_length')],source=HOST)
    for k in('nci_header0','nci_mt','nci_pbf','nci_packet_bytes'):r(k,when_present=['nf_nci_hex'],required=True,source=HOST)
    for kind in('COMMAND','RESPONSE','NOTIFICATION'):r('nci_hex',{'nci_kind':kind},hex_octets=[dict(offset=1,width=1,parameter='nf_nci_oid')],source=HOST)
    for protocol in('NFC_A','NFC_B','NFC_F','NFC_V'):
        r('role',{'protocol':protocol,'operation':'READER_WRITER'},allowed=['READER'],source=DATA)
        r('role',{'protocol':protocol,'operation':'CARD_EMULATION'},allowed=['CARD'],source=DATA)
        r('direction',{'protocol':protocol},allowed=['READER_TO_CARD','CARD_TO_READER'],source=DATA)
    for divisor in(128,64,32,16):
        r('coding',{'protocol':'NFC_A','direction':'READER_TO_CARD','divisor':divisor},allowed=['MODIFIED_MILLER'],source=DATA)
        r('coding',{'protocol':'NFC_A','direction':'CARD_TO_READER','divisor':divisor},allowed=['MANCHESTER']if divisor==128 else['BPSK'],source=DATA)
        r('coding',{'protocol':'NFC_B','direction':'READER_TO_CARD','divisor':divisor},allowed=['NRZ'],source=DATA)
        r('coding',{'protocol':'NFC_B','direction':'CARD_TO_READER','divisor':divisor},allowed=['BPSK'],source=DATA)
    r('coding',{'protocol':'NFC_F'},allowed=['MANCHESTER'],source=DATA)
    r('coding',{'protocol':'NFC_V','direction':'READER_TO_CARD'},allowed=['PPM_1_OF_4'],source=DATA)
    r('coding',{'protocol':'NFC_V','direction':'CARD_TO_READER'},allowed=['MANCHESTER'],source=DATA)
    for k in('dep_len','dep_body_bytes','dep_lr','dep_body_limit','dep_header_bytes','dep_data_bytes','dep_did_present','dep_nad_present','transaction_source'):
        r(k,dep,when_present=['nf_dep_pdu'],required=True)
    r('dep_len',dep,equal_expression={'sum':[3,'nf_dep_body_bytes']})
    r('dep_body_bytes',dep,equal_expression={'sum':['nf_dep_header_bytes','nf_dep_data_bytes']},maximum_parameter='nf_dep_body_limit')
    for lr,limit in enumerate((64,128,192,252)):r('dep_body_limit',{**dep,'dep_lr':lr},allowed=[limit])
    for did in(False,True):
        for nad in(False,True):r('dep_header_bytes',{**dep,'dep_did_present':did,'dep_nad_present':nad},allowed=[1+did+nad])
    r('dep_did',{**dep,'dep_did_present':True},minimum=1,required=True);r('dep_nad',{**dep,'dep_nad_present':True},required=True)
    r('dep_did',{**dep,'dep_did_present':False},allowed=[]);r('dep_nad',{**dep,'dep_nad_present':False},allowed=[])
    for pdu,base in [('INFORMATION',0),('ACK',64),('NACK',80),('PROTECTED',32)]:
        for did in(False,True):
            for nad in(False,True):
                for more in(False,True):
                    w={**dep,'dep_pdu':pdu,'dep_did_present':did,'dep_nad_present':nad,'dep_more':more}
                    r('dep_pfb',w,equal_expression={'sum':[base+4*did+8*nad+(16*more if pdu in('INFORMATION','PROTECTED') else 0),'nf_dep_pni']})
    for pdu in('ACK','NACK','ATTENTION'):r('dep_data_bytes',{**dep,'dep_pdu':pdu},allowed=[0])
    for pdu,base in [('TIMEOUT_EXTENSION',144),('ATTENTION',128)]:
        for did in(False,True):
            for nad in(False,True):r('dep_pfb',{**dep,'dep_pdu':pdu,'dep_did_present':did,'dep_nad_present':nad},allowed=[base+4*did+8*nad])
    r('dep_data_bytes',{**dep,'dep_pdu':'TIMEOUT_EXTENSION'},allowed=[1])
    r('rtox',{**dep,'dep_pdu':'TIMEOUT_EXTENSION'},required=True)
    r('security_source',{**dep,'dep_pdu':'PROTECTED'},required=True)
    for direction,a,b in [('INITIATOR_TO_TARGET',0xd4,6),('TARGET_TO_INITIATOR',0xd5,7)]:
        r('dep_cmd1',{**dep,'direction':direction},allowed=[a]);r('dep_cmd2',{**dep,'direction':direction},allowed=[b])
    for divisor in(64,32):r('rf_preamble_bits',{**dep,'mode':'PASSIVE','divisor':divisor},minimum=48)
    r('measured_carrier_hz',minimum_expression={'subtract':['nf_carrier_hz','nf_carrier_tolerance_hz']},maximum_expression={'sum':['nf_carrier_hz','nf_carrier_tolerance_hz']})
    r('carrier_tolerance_hz',when_present=['nf_measured_carrier_hz'],required=True)
    return dict(rate_model={'type':'SINGLE_BITRATE','fields':['bitrate_bps'],'minimum_bps':1},
      required_parameters=['bitrate_bps',*['nf_'+k for k in REQUIRED]],native_parameter_prefixes=['nf_'],parameter_evidence_scope='EXPLICIT_LAYER',
      parameter_constraints=rules,physical_layer_profile_id='nfc_actual_rf_protocol_and_controller',
      medium_access_model='EXPLICIT_ACTIVATION_ANTICOLLISION_HALF_DUPLEX',arbitration_model_id='RFCA_AND_PROTOCOL_SPECIFIC_SELECTION',
      mechanisms={'physical':['NFCIP1_A_B_F_V_SEPARATE_ROLES','CARRIER_DIVISOR_DISTINCT_NCI_HOST_CLOCK'],
       'framing':['NFCIP1_DEP_CHAINING','NCI_HEADER_PAYLOAD_CREDITS_DISTINCT_RF_FRAME'],
       'qualification':['INSTALLED_DEVICE_FIRMWARE_AND_ANTENNA','NO_AUTOMATIC_TAG_OR_APPLICATION_CAPACITY']})

def fields():
    result=[]
    for spec in DECLARATIONS:
        k=spec['key'][3:];item={key:value for key,value in spec.items()if value is not None}
        item.update(label=k.replace('_',' '),category='communication',scope='network',editable=True,required=k in REQUIRED,
          parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
        defaults=[]
        if k=='carrier_hz':defaults=[dict(when={},value=13560000,source=ECMA,source_revision=SOURCES[ECMA])]
        if k=='divisor':
            defaults=[dict(when={'nf_protocol':'NFCIP1_ECMA340_2024'},value=128,source=ECMA,source_revision=SOURCES[ECMA])]
            defaults.extend(dict(when={'nf_protocol':p,'nf_implementation':impl},value=v,source=DATA,source_revision=SOURCES[DATA])
               for impl in('PN7160','PN7161')for p,v in [('NFC_A',128),('NFC_B',128),('NFC_F',64),('NFC_V',512)])
        if k=='wt':defaults=[dict(when={'nf_protocol':'NFCIP1_ECMA340_2024'},value=14,source=ECMA,source_revision=SOURCES[ECMA])]
        if k=='field_threshold_a_m':defaults=[dict(when={'nf_protocol':'NFCIP1_ECMA340_2024'},value=.1875,source=ECMA,source_revision=SOURCES[ECMA])]
        if defaults:item.update(conditional_defaults=defaults,default_status='PROPOSED_CONDITIONAL',parameter_origin='TRANSPORT_PROFILE')
        result.append(item)
    return result
