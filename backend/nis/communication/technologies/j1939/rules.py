"""Independent J1939-21/-22, explicit PHY and implementation-qualified proposals."""
SHA='01aba95cca43847bc272ec7ddb12048f587e6554'
PY=f'https://raw.githubusercontent.com/juergenH87/python-can-j1939/{SHA}/j1939/'
LNX='https://raw.githubusercontent.com/torvalds/linux/v6.6/'
TP=LNX+'net/can/j1939/transport.c'
SOCKET=LNX+'net/can/j1939/socket.c'
UAPI=LNX+'include/uapi/linux/can/j1939.h'
CLAIM=LNX+'net/can/j1939/address-claim.c'
DOC=LNX+'Documentation/networking/j1939.rst'
CC=PY+'j1939_21.py'
FD=PY+'j1939_22.py'
ECU=PY+'electronic_control_unit.py'
NAME=PY+'name.py'
CA=PY+'controller_application.py'
PGN=PY+'parameter_group_number.py'
SAE21='https://saemobilus.sae.org/standards/j193921_202205-data-link-layer'
SAE22='https://saemobilus.sae.org/standards/j1939-22_202103-fd-data-link-layer'
PHY11='https://saemobilus.sae.org/standards/j1939-11_202607-physical-layer-250-kbit-s-twisted-shielded-pair'
PHY15='https://saemobilus.sae.org/standards/j193915_201812-physical-layer-250-kbps-un-shielded-twisted-pair-utp'
PHY14='https://saemobilus.sae.org/standards/j193914_202204-physical-layer-500-kbit-s'
PHY17='https://saemobilus.sae.org/standards/j193916_202409-automatic-baud-rate-detection-process'
DA='https://saemobilus.sae.org/standards/j193971_202208-vehicle-application-layer'
FUSA='https://saemobilus.sae.org/standards/j1939-77_202511-sae-j1939-fd-functional-safety-assurance-data'
SOURCES={u:'Linux v6.6 publisher source/hash manifest; relevant declared parameter/API/state code read; actual matching unmodified build required'for u in(TP,SOCKET,UAPI,CLAIM,DOC)}
SOURCES.update({u:'python-can-j1939 commit '+SHA+'2026-02-04T20:25:25Z publisher source/hash manifest; relevant implementation code read, not complete normative/conformance proof'for u in(CC,FD,ECU,NAME,CA,PGN)})
SOURCES.update({SAE21:'SAE J1939/21:2022-05-24 CEFF29 publisher scope; full licensed normative text not read',
 SAE22:'SAE J1939-22 publisher2021 scope and current revision2022-09-08 listing; full licensed normative text not read',
 PHY11:'SAE J1939-11:2026-07-15 current250k/HS transceiver publisher metadata; full normative PHY not read',
 PHY15:'SAE J1939/15:2018-12-14 current250k/UTP/classic-only publisher scope; full normative PHY not read',
 PHY14:'SAE J1939/14:2022-04-05 current500k/classic-only publisher scope; full normative PHY not read',
 PHY17:'SAE J1939/16:2024-09-17 publisher scope explicitly states J1939-17 fixed500k/2000k FD combination, no FD autodetection',
 DA:'SAE J1939/71 publisher scope and current2025-02-25 revision listing; actual SPN/PGN/NAME/addresses belong to selected J1939DA/application annex',
 FUSA:'SAE J1939-77:2025-11-19 publisher scope, assurance profiles separate from container TOS/TF/AD TYPE assignments; full normative safety proof not read'})
DECLARATIONS=[]

def d(key,kind,meaning,source=TP,unit=None,options=None,minimum=None,maximum=None,**extra):
    DECLARATIONS.append(dict(key='j39_'+key,type=kind,description=meaning,source=source,source_revision=SOURCES[source],
        unit=unit,options=options,min=minimum,max=maximum,**extra))

d('data_link','select','Explicit classical J1939-21 versus FD J1939-22; no automatic CAN/industry path selection.',source=SAE21,options=['J1939_21','J1939_22'])
d('phy_profile','select','Actual qualified250k shielded/unshielded,500k classical,500k/2M FD or explicitly registered OEM PHY.',source=PHY17,
 options=['J1939_11_250K_STP','J1939_15_250K_UTP','J1939_14_500K_CLASSIC','J1939_17_500K_2M_FD','OTHER_REGISTERED_PHY'])
d('profile','select','Actual qualified device versus unchanged exact Linux/Python build; settings never copied between implementations.',source=DOC,
 options=['QUALIFIED_DEVICE','LINUX_V6_6_FACTORY','PYTHON_CAN_01ABA95_FACTORY'])
d('direction','select','Actual sender/receiver; session limits and queue retry scope depend on role.',options=['TRANSMITTER','RECEIVER'])
d('service','select','Actual application/network-management/diagnostic service with its own PGN/SPN codec.',source=DA,
 options=['APPLICATION','ADDRESS_CLAIM','REQUEST_PGN','COMMANDED_ADDRESS','DIAGNOSTICS'])
d('transport','select','Actual classical single8/TP, optional ISO11783 ETP extension or separate FD MultiPG/FD TP.',source=DOC,
 options=['SINGLE_FRAME','TP_BAM','TP_CONNECTION','ETP_EXTENSION','FD_MULTI_PG','FD_TP_BAM','FD_TP_CONNECTION'])
d('frame_format','select','Actual CEFF29 classical or FEFF29/FBFF11 FD; Python reviewed receive path supports FEFF only.',source=FD,options=['CEFF_29','FEFF_29','FBFF_11'])
d('frame_phase','select','Actual current application/container/control/data frame, separate from whole transported PGN.',source=FD,
 options=['APPLICATION','TP_CM','TP_DT','ETP_CM','ETP_DT','MULTI_PG','FD_CM','FD_DT'])
d('pdu_kind','select','Actual destination-specific PDU1 versus PDU2 broadcast group extension; PS meaning is explicit.',source=UAPI,options=['PDU1','PDU2'])
d('address_mode','select','Actual dynamic NAME claim versus OEM static assignment; static mode needs separate ownership/uniqueness proof.',source=DOC,options=['DYNAMIC_NAME','STATIC_OEM'])
d('claim_state','select','Actual claimed/requesting/veto-wait/cannot-claim state; NULL254 cannot send ordinary application traffic.',source=CLAIM,options=['CLAIMED','REQUESTING','WAIT_VETO','CANNOT_CLAIM'])
d('address_owner','select','Actual in-kernel versus user-space owner of one ECU address; raw/kernel implementations cannot share that ECU.',source=DOC,options=['KERNEL','USERSPACE'])
d('assurance_mode','select','Actual selected assurance data; no inferred safety/cybersecurity from an FD frame.',source=FUSA,
 options=['NONE','MANUFACTURER_CS','MANUFACTURER_FUSA','MANUFACTURER_CS_FUSA','REGISTERED_SAE_FUSA'])
for key,meaning,source in [
 ('data_link_revision','Actual selected SAE data-link edition, not assumed compliance from an open-source implementation.',SAE21),
 ('phy_revision','Actual selected physical-layer edition and device compatibility.',PHY17),
 ('build_commit','Actual exact implementation commit/version, never floating main.',ECU),
 ('build_source','Actual binary/configuration and unmodified/modified build evidence.',ECU),
 ('device_source','Actual ECU/driver/transceiver/firmware and supported PGN/transport capabilities.',DOC),
 ('physical_source','Actual selected cable/stubs/termination/EMC/propagation/oscillator/timing and PHY evidence.',PHY11),
 ('binding_source','Actual canonical port, selected registered segment and independent gateway path.',DOC),
 ('dictionary_source','Actual J1939DA/application annex revision, SPN units/offsets/sentinels, PGN length/priority/period and manufacturer assignments.',DA),
 ('name_source','Actual unique NAME and assigned manufacturer/function/system/industry fields; constructor zeros are not allocated identity.',NAME),
 ('name_hex','Actual exact64-bit NAME in16 hex digits, never a floating point number.',NAME),
 ('application_source','Actual selected application/diagnostic service schema and end-to-end semantics.',DA),
 ('encoding_source','Actual PGN/SPN/transport/container/frame encoding and padding.',FD),
 ('schedule_source','Actual segment priorities, frame stuffing/errors, TP sessions/interference and driver queues.',TP),
 ('acceptance_source','Actual full functional E2E/freshness/safety acceptance; TP timeouts are separate.',FUSA),
 ('capacity_source','Actual complete shared segment traffic/arbitration/error/transport proof.',TP),
 ('claim_source','Actual allocation/claim observation, source NAME mapping and ownership uniqueness.',CLAIM),
 ('etp_source','Actual explicitly supported ISO11783 ETP extension and peer compatibility; not automatically all ISOBUS applications.',DOC),
 ('fd_source','Actual selected FD/DLC/BRS/nominal/data timing and receiving-controller compatibility.',FD),
 ('assurance_source','Actual TOS/TF/AD TYPE/profile/trailer codec and independent assurance verification.',FUSA),
 ('filter_source','Actual receive whitelist/bind/connect/masks, never one default subscribed PGN.',SOCKET)]:d(key,'text',meaning,source=source)
for key,meaning,lo,hi,unit,source in [
 ('nominal_bitrate_bps','Selected PHY nominal/arbitration bitrate;250k or500k proposals are PHY-qualified.',1,None,'bit/s',PHY17),
 ('data_bitrate_bps','Actual FD data-phase bitrate; J1939-17 fixed2M, absent on classical path.',1,None,'bit/s',PHY17),
 ('priority','Actual wire3-bit priority; Linux default6 differs from SO_PRIORITY mapping7-priority.',0,7,None,SOCKET),
 ('socket_priority','Actual Linux SO_PRIORITY0..7, inverse wire priority; not generic QoS priority.',0,7,None,SOCKET),
 ('pgn','Actual18-bit current-frame PGN; PDU1 low8 bits zero, PDU2 includes group extension.',0,262143,None,UAPI),
 ('message_pgn','Actual whole reassembled application PGN, distinct from TP/ETP/FD CM/DT or container PGN.',0,262143,None,UAPI),
 ('can_id','Actual current CAN identifier,29-bitCEFF/FEFF versus11-bitFBFF.',0,536870911,None,UAPI),
 ('reserved_data_page','Actual PGN reserved/EDP bit; assignment requires selected dictionary/edition.',0,1,None,UAPI),
 ('data_page','Actual PGN data-page bit.',0,1,None,UAPI),
 ('pdu_format','Actual PF8-bit, below240=PDU1.',0,255,None,UAPI),
 ('pdu_specific','Actual destination address forPDU1 or PGN group extension forPDU2.',0,255,None,UAPI),
 ('source_address','Actual current source address,255 broadcast is not a sender.',0,254,None,UAPI),
 ('destination_address','Actual destination or global255; NULL254 invalid ordinary destination.',0,255,None,UAPI),
 ('preferred_address','Actual OEM/NAME-based preferred address; not manufacturer/example address.',0,253,None,DA),
 ('identity_number','Actual21-bit unique manufacturer device identity.',0,2097151,None,UAPI),
 ('manufacturer_code','Actual11-bit registered manufacturer code.',0,2047,None,UAPI),
 ('ecu_instance','Actual3-bit ECU instance.',0,7,None,UAPI),
 ('function_instance','Actual5-bit function instance.',0,31,None,UAPI),
 ('function_code','Actual8-bit function meaning depends on selected industry/system dictionary.',0,255,None,UAPI),
 ('name_reserved_bit','Actual NAME reserved bit; reviewed Python encoder writes0, no invented identity.',0,1,None,UAPI),
 ('system_code','Actual7-bit system code; standard term vehicle-system does not select a Simulator industry.',0,127,None,UAPI),
 ('system_instance','Actual4-bit system instance.',0,15,None,UAPI),
 ('industry_group','Actual3-bit NAME industry group; publisher library recognizes0..5; no assumed agricultural/on-highway group.',0,5,None,NAME),
 ('message_octets','Actual whole application data, not one classic8/FD64-byte frame.',0,None,'Byte',DOC),
 ('frame_octets','Actual encoded current CAN data length; FD DLC representability and headers separate.',0,64,'Byte',FD),
 ('data_frames','Actual count:ceil(message/7) classicalTP/ETP versusceil(message/60) FD TP.',1,16777215,'Frames',TP),
 ('segment_number','Actual TP sequence or FD24-bit absolute segment number, never whole payload length.',1,16777215,None,FD),
 ('etp_offset_packets','Actual ETP24-bit data-packet offset, not classicTP sequence.',0,16777215,None,TP),
 ('etp_sequence','Actual ETP block sequence1..255.',1,255,None,TP),
 ('transport_data_octets','Actual data carried in current DT frame after sequence/header, at most7classic/60FD.',0,60,'Byte',FD),
 ('cts_packets','Actual flow-control window in segments;0 hold is not a default throughput guarantee.',0,255,None,FD),
 ('fd_session_id','Actual FD4-bit session field; admitted BAM0..3 versusconnection0..7 in reviewed stack.',0,15,None,FD),
 ('active_sessions','Actual sessions in one transmitter or originator/responder pair, not all segment receivers.',0,None,None,FD),
 ('fd_control_type','Actual FD control nibble RTS0/CTS1/EOMS2/EOMA3/BAM4/ABORT15.',0,15,None,FD),
 ('fd_data_type','Actual FD DT frame indicator nibble; reviewed implementation supports normal0 only.',0,15,None,FD),
 ('cpg_octets','Actual one contained PG data length, at most60 after4-byte service header.',0,60,'Byte',FD),
 ('cpg_count','Actual contained PG count, each4-byte service header counts against one64-byte frame.',1,16,None,FD),
 ('cpg_total_octets','Actual sum of all contained PG application data; no per-PG header duplication shortcut.',0,60,'Byte',FD),
 ('container_octets','Actual unpadded sum4*cpg_count+cpg_total_octets, distinct from rounded FD DLC.',4,64,'Byte',FD),
 ('padding_octets','Actual added FD DLC padding bytes, not application data.',0,63,'Byte',FD),
 ('tos','Actual3-bit contained-PG service type; reviewed Python supports SAE/no assurance2 only.',0,7,None,FD),
 ('trailer_format','Actual3-bit contained-PG trailer format; reviewed Python supports0 only.',0,7,None,FD),
 ('ad_type','Actual TP assurance data type field; meanings require selected standard/manufacturer source.',0,255,None,FD),
 ('assurance_octets','Actual assurance trailer octets; not default safety evidence.',0,None,'Byte',FUSA),
 ('aggregation_ms','Actual MultiPG flush wait, deadline of earliest contained PG;0 explicitly sends immediately.',0,None,'ms',FD),
 ('bam_interval_ms','Actual BAM pacing; classic reviewed50..200ms versusFD10..200ms.',0,None,'ms',CC),
 ('connection_interval_ms','Actual implementation/OEM flow-controlled DT pacing; not BAM timer.',0,None,'ms',TP),
 ('t1_ms','Actual inter-segment timeout; pinnedPython750ms, not functional deadline.',0,None,'ms',FD),
 ('t2_ms','Actual responderCTS-toDT timeout; pinnedPython1250ms.',0,None,'ms',FD),
 ('t3_ms','Actual originator waitCTS timeout; pinnedPython1250ms.',0,None,'ms',FD),
 ('t4_ms','Actual holdCTS wait timeout; pinnedPython1050ms.',0,None,'ms',FD),
 ('t5_ms','Actual FD waitEOMA afterEOMS; pinnedPython3000ms, not applicable classicalTP.',0,None,'ms',FD),
 ('tr_ms','Actual response timer; pinnedPython200ms.',0,None,'ms',FD),
 ('th_ms','Actual hold interval; pinnedPython500ms.',0,None,'ms',FD),
 ('claim_wait_ms','Actual address contention wait; implementation/addresses qualify250ms, not universal startup delay.',0,None,'ms',CA),
 ('claim_start_ms','Actual Python CA.start default500ms before claim, separate from250msveto.',0,None,'ms',CA),
 ('claim_request_ms','Actual Python request-for-claim timer1250ms, not application request deadline.',0,None,'ms',CA),
 ('linux_tp_block','Actual Linux configured flow-control block cap255;0 internal sentinel means255, not zero permitted wire packets.',0,255,None,TP),
 ('linux_tx_queue_retries','Actual Linux ENOBUFS queue admission retry cap100, not CAN wire retransmissions.',0,None,None,TP),
 ('linux_retry_delay_ms','Actual randomized local queue retry10..25ms, no fixed suggested random sample.',10,25,'ms',TP),
 ('linux_abort_ms','Actual Linux abort-session timeout500ms.',0,None,'ms',LNX+'net/can/j1939/j1939-priv.h'),
 ('linux_echo_ms','Actual Linux simple-frame local echo timer10000ms, not wire TP or application acceptance.',0,None,'ms',LNX+'net/can/j1939/j1939-priv.h'),
 ('filter_count','Actual Linux per-socket whitelist count,512 ceiling, not subscribed PGN count.',0,512,None,UAPI),
 ('backbone_m','Actual selected PHY cable limit and topology; no importedISOBUS40m globaldefault.',0,None,'m',PHY11),
 ('stub_m','Actual selected PHY/device stub length.',0,None,'m',PHY11),
 ('termination_ohm','Actual selected physical termination and measured topology.',0,None,'Ohm',PHY11),
 ('stuffed_frame_bits','Actual bounded wire frame including stuffing/CRC/ACK/IFS at appropriate bitrate phases.',1,None,'bit',PHY17),
 ('arbitration_bits','Actual nominal-rate portion of FD/classic frame including applicable stuffing/ACK/IFS.',0,None,'bit',PHY17),
 ('data_phase_bits','Actual FD data-rate portion including applicable stuffing/CRC; absent or0 on classic/noBRS.',0,None,'bit',PHY17),
 ('arbitration_bound_ms','Actual selected shared-segment identifier priority/interference bound.',0,None,'ms',TP),
 ('functional_bound_ms','Actual full application E2E deadline, not any TP timeout.',0,None,'ms',FUSA)]:
    if source not in SOURCES:SOURCES[source]='Linuxv6.6 publisher header constants/hash manifest read; actual matching build required'
    d(key,'number',meaning,source=source,unit=unit,minimum=lo,maximum=hi)
for key,meaning,source in [
 ('unmodified_build','Actual pinned source/configuration has no modifications.',ECU),
 ('brs','Actual FD bitrate switching; forbidden classic, pinned Python built-in sender usesTrue.',ECU),
 ('arbitrary_address_capable','Actual NAME bit63 and address allocation capability.',UAPI),
 ('etp_enabled','Actual peer-supported ISO11783 ETP extension; not automaticJ1939feature.',DOC),
 ('so_broadcast','Actual Linux socket broadcast permission, defaultFalse, needed for both receive/transmit.',SOCKET),
 ('promiscuous','Actual Linux promiscuous receive flag; does not manufacture destination ownership.',SOCKET),
 ('error_queue','Actual Linux SO_J1939_ERRQUEUE, independent from wire retry policy.',SOCKET),
 ('cap_net_admin','Actual Linux privilege for wire priorities0/1; no privilege default.',SOCKET),
 ('linux_tp_padding','Actual Linux padding data frames to8, factoryTrue.',TP),
 ('claim_confirmed','Actual observed claim/uniqueness confirmation.',CLAIM),
 ('schedule_confirmed','Actual complete schedule confirmation.',TP),
 ('capacity_confirmed','Actual complete segment capacity confirmation.',TP)]:d(key,'boolean',meaning,source=source)
REMOVED={k:'Removed inherited '+k+': J1939 has explicitly selected classic/FD PHY, native priority/TP/container/API configuration; generic queues/retransmission percentages/gateway/CAN defaults cannot prove that path.'for k in
 ('bitrate','arbitration_bitrate','data_bitrate','queue_size','queue_policy','qos_priority','reserved_bandwidth_percent','sync_method','rate_limit_bit_s',
 'retransmission_enabled','retransmission_rate','retry_limit','retransmission_delay_ms','gateway_maximum_throughput','gateway_input_buffer',
 'gateway_output_buffer','gateway_maximum_routes','gateway_maximum_messages_s')}
REQUIRED=['data_link','phy_profile','profile','direction','service','transport','data_link_revision','phy_revision','device_source','physical_source',
 'binding_source','dictionary_source','name_source','application_source','encoding_source','schedule_source','acceptance_source','capacity_source','nominal_bitrate_bps']

def semantics():
    rules=[]
    def r(key,when=None,source=TP,**kw):rules.append(dict(parameter='j39_'+key,when={'j39_'+k:v for k,v in(when or {}).items()},source=source,source_revision=SOURCES[source],**kw))
    for phy in ('J1939_11_250K_STP','J1939_15_250K_UTP'):
        r('nominal_bitrate_bps',{'phy_profile':phy},allowed=[250000],source=PHY11 if phy.startswith('J1939_11')else PHY15)
        r('data_link',{'phy_profile':phy},allowed=['J1939_21'],source=PHY15)
    r('nominal_bitrate_bps',{'phy_profile':'J1939_14_500K_CLASSIC'},allowed=[500000],source=PHY14)
    r('data_link',{'phy_profile':'J1939_14_500K_CLASSIC'},allowed=['J1939_21'],source=PHY14)
    r('nominal_bitrate_bps',{'phy_profile':'J1939_17_500K_2M_FD'},allowed=[500000],source=PHY17)
    r('data_bitrate_bps',{'phy_profile':'J1939_17_500K_2M_FD'},allowed=[2000000],required=True,source=PHY17)
    r('data_link',{'phy_profile':'J1939_17_500K_2M_FD'},allowed=['J1939_22'],source=PHY17)
    r('frame_format',{'data_link':'J1939_21'},allowed=['CEFF_29'],source=SAE21)
    r('transport',{'data_link':'J1939_21'},allowed=['SINGLE_FRAME','TP_BAM','TP_CONNECTION','ETP_EXTENSION'],source=DOC)
    r('frame_octets',{'data_link':'J1939_21'},maximum=8,source=SAE21)
    r('brs',{'data_link':'J1939_21'},allowed=[False],source=SAE21)
    r('data_bitrate_bps',{'data_link':'J1939_21'},allowed=[],source=SAE21)
    r('data_phase_bits',{'data_link':'J1939_21'},allowed=[0],source=SAE21)
    r('data_phase_bits',{'brs':False},allowed=[0],source=SAE21)
    r('stuffed_frame_bits',equal_expression={'sum':['j39_arbitration_bits','j39_data_phase_bits']},source=PHY17)
    r('frame_format',{'data_link':'J1939_22'},allowed=['FEFF_29','FBFF_11'],required=True,source=FD)
    r('transport',{'data_link':'J1939_22'},allowed=['FD_MULTI_PG','FD_TP_BAM','FD_TP_CONNECTION'],source=FD)
    r('data_bitrate_bps',{'data_link':'J1939_22'},required=True,source=PHY17)
    r('fd_source',{'data_link':'J1939_22'},required=True,source=FD)
    for key in ('fd_source','fd_session_id','fd_control_type','fd_data_type','cpg_octets','cpg_count','cpg_total_octets',
                'container_octets','padding_octets','tos','trailer_format','ad_type','assurance_octets','aggregation_ms'):
        r(key,{'data_link':'J1939_21'},allowed=[],source=FD)
    r('assurance_mode',{'data_link':'J1939_21'},allowed=['NONE'],source=FUSA)
    for key in ('etp_source','etp_offset_packets','etp_sequence'):
        r(key,when_not={'j39_transport':'ETP_EXTENSION'},when_present=['j39_transport'],allowed=[],source=DOC)
    for key in ('bam_interval_ms','segment_number','transport_data_octets','cts_packets','active_sessions','data_frames'):
        r(key,{'transport':'SINGLE_FRAME'},allowed=[])
    r('frame_octets',{'data_link':'J1939_22'},allowed=list(range(9))+[12,16,20,24,32,48,64],source=FD)
    r('data_bitrate_bps',minimum_parameter='j39_nominal_bitrate_bps',source=PHY17)
    r('socket_priority',{'profile':'LINUX_V6_6_FACTORY'},equal_expression={'subtract':[7,'j39_priority']},source=SOCKET)
    r('cap_net_admin',{'profile':'LINUX_V6_6_FACTORY'},when_ranges={'j39_priority':[0,1]},allowed=[True],required=True,source=SOCKET)
    r('so_broadcast',{'profile':'LINUX_V6_6_FACTORY','destination_address':255},allowed=[True],required=True,source=SOCKET)
    r('address_owner',{'profile':'LINUX_V6_6_FACTORY'},allowed=['KERNEL'],source=DOC)
    r('address_owner',{'profile':'PYTHON_CAN_01ABA95_FACTORY'},allowed=['USERSPACE'],source=DOC)
    r('name_hex',pattern=r'[0-9a-fA-F]{16}',forbidden=['0000000000000000','FFFFFFFFFFFFFFFF','ffffffffffffffff'],source=UAPI,
        integer_text_base=16,integer_bitfields=[{'parameter':'j39_'+key,'offset':offset,'width':width,'boolean':boolean}
        for key,offset,width,boolean in [('identity_number',0,21,False),('manufacturer_code',21,11,False),('ecu_instance',32,3,False),
        ('function_instance',35,5,False),('function_code',40,8,False),('name_reserved_bit',48,1,False),('system_code',49,7,False),
        ('system_instance',56,4,False),('industry_group',60,3,False),('arbitrary_address_capable',63,1,True)]])
    for key in ('claim_source','name_hex'):r(key,{'address_mode':'DYNAMIC_NAME'},required=True,source=CLAIM)
    r('source_address',{'claim_state':'CLAIMED'},maximum=253,source=CLAIM)
    r('source_address',{'claim_state':'CANNOT_CLAIM'},allowed=[254],source=CLAIM)
    r('source_address',when_not={'j39_service':'REQUEST_PGN','j39_claim_state':'CANNOT_CLAIM'},when_present=['j39_service'],maximum=253,source=CLAIM)
    r('service',{'claim_state':'CANNOT_CLAIM'},allowed=['ADDRESS_CLAIM'],source=CLAIM)
    r('service',{'claim_state':'WAIT_VETO'},allowed=['ADDRESS_CLAIM','REQUEST_PGN'],source=CA)
    r('destination_address',forbidden=[254],source=UAPI)
    r('destination_address',{'service':'ADDRESS_CLAIM'},allowed=[255],source=CLAIM)
    r('pgn',{'service':'ADDRESS_CLAIM'},allowed=[60928],source=CLAIM)
    r('pgn',{'service':'REQUEST_PGN'},allowed=[59904],source=UAPI)
    r('pdu_format',{'pdu_kind':'PDU1'},maximum=239,source=UAPI)
    r('pdu_format',{'pdu_kind':'PDU2'},minimum=240,source=UAPI)
    r('pdu_specific',{'pdu_kind':'PDU1'},equal_parameter='j39_destination_address',source=UAPI)
    r('destination_address',{'pdu_kind':'PDU2'},allowed=[255],source=UAPI)
    pgn={'sum':[{'product':['j39_reserved_data_page',131072]},{'product':['j39_data_page',65536]},{'product':['j39_pdu_format',256]}]}
    r('pgn',{'pdu_kind':'PDU1'},multiple_of=256,equal_expression=pgn,source=UAPI)
    r('pgn',{'pdu_kind':'PDU2'},equal_expression={'sum':[pgn,'j39_pdu_specific']},source=UAPI)
    for fmt in ('CEFF_29','FEFF_29'):r('can_id',{'frame_format':fmt},equal_expression={'sum':[{'product':['j39_priority',67108864]},
        {'product':['j39_reserved_data_page',33554432]},{'product':['j39_data_page',16777216]},
        {'product':['j39_pdu_format',65536]},{'product':['j39_pdu_specific',256]},'j39_source_address']},source=UAPI)
    r('can_id',{'frame_format':'FBFF_11'},maximum=2047,equal_parameter='j39_source_address',source=FD)
    r('destination_address',{'frame_format':'FBFF_11'},allowed=[255],source=FD)
    r('priority',{'frame_format':'FBFF_11'},allowed=[0],source=FD)
    r('transport',{'frame_format':'FBFF_11'},allowed=['FD_MULTI_PG'],source=FD)
    r('message_octets',equal_parameter='payload_bytes',source=DOC)
    r('message_octets',{'transport':'SINGLE_FRAME'},maximum=8,source=CC)
    r('frame_octets',{'transport':'SINGLE_FRAME'},equal_parameter='j39_message_octets',source=CC)
    r('frame_phase',{'transport':'SINGLE_FRAME'},allowed=['APPLICATION'],source=CC)
    r('message_pgn',{'transport':'SINGLE_FRAME'},equal_parameter='j39_pgn',source=CC)
    for transport in ('TP_BAM','TP_CONNECTION'):
        w={'transport':transport};r('message_octets',w,minimum=9,maximum=1785)
        r('data_frames',w,equal_expression={'ceiling':[{'product':['j39_message_octets',1/7]}]},maximum=255)
        r('frame_phase',w,allowed=['TP_CM','TP_DT']);r('segment_number',w,maximum=255)
    r('destination_address',{'transport':'TP_BAM'},allowed=[255]);r('destination_address',{'transport':'TP_CONNECTION'},maximum=253)
    r('active_sessions',{'transport':'TP_BAM','direction':'TRANSMITTER'},maximum=1,source=CC)
    r('bam_interval_ms',{'transport':'TP_BAM'},minimum=50,maximum=200,source=CC)
    r('message_octets',{'transport':'ETP_EXTENSION'},minimum=1786,maximum=117440505,source=DOC)
    r('data_frames',{'transport':'ETP_EXTENSION'},equal_expression={'ceiling':[{'product':['j39_message_octets',1/7]}]},source=TP)
    r('destination_address',{'transport':'ETP_EXTENSION'},maximum=253);r('frame_phase',{'transport':'ETP_EXTENSION'},allowed=['ETP_CM','ETP_DT'])
    r('segment_number',{'transport':'ETP_EXTENSION'},equal_expression={'sum':['j39_etp_offset_packets','j39_etp_sequence']},maximum_parameter='j39_data_frames')
    r('etp_enabled',{'transport':'ETP_EXTENSION'},allowed=[True],required=True,source=DOC)
    r('etp_source',{'transport':'ETP_EXTENSION'},required=True,source=DOC)
    for phase,number in [('TP_CM',60416),('TP_DT',60160),('ETP_CM',51200),('ETP_DT',50944),('FD_CM',19712),('FD_DT',19968)]:
        r('pgn',{'frame_phase':phase},allowed=[number],source=FD if phase.startswith('FD')else TP)
    for phase in ('TP_DT','ETP_DT'):r('transport_data_octets',{'frame_phase':phase},maximum=7)
    r('frame_octets',{'profile':'LINUX_V6_6_FACTORY','linux_tp_padding':True,'frame_phase':'TP_DT'},allowed=[8])
    r('frame_octets',{'frame_phase':'FD_CM','assurance_mode':'NONE'},allowed=[12],source=FD)
    r('fd_control_type',allowed=[0,1,2,3,4,15],source=FD)
    r('transport_data_octets',{'frame_phase':'FD_DT'},maximum=60,maximum_expression={'subtract':['j39_frame_octets',4]},source=FD)
    for transport,limit in [('FD_TP_BAM',15300),('FD_TP_CONNECTION',16777215)]:
        w={'transport':transport};r('message_octets',w,minimum=61,maximum=limit,source=FD)
        r('data_frames',w,equal_expression={'ceiling':[{'product':['j39_message_octets',1/60]}]},source=FD)
        r('frame_phase',w,allowed=['FD_CM','FD_DT'],source=FD)
        r('segment_number',w,maximum_parameter='j39_data_frames',source=FD)
    r('destination_address',{'transport':'FD_TP_BAM'},allowed=[255],source=FD)
    r('destination_address',{'transport':'FD_TP_CONNECTION'},maximum=253,source=FD)
    r('active_sessions',{'transport':'FD_TP_BAM','direction':'TRANSMITTER'},maximum=4,source=FD)
    r('fd_session_id',{'transport':'FD_TP_BAM'},maximum=3,source=FD)
    r('active_sessions',{'transport':'FD_TP_CONNECTION','direction':'TRANSMITTER'},maximum=8,source=FD)
    r('fd_session_id',{'transport':'FD_TP_CONNECTION'},maximum=7,source=FD)
    r('bam_interval_ms',{'transport':'FD_TP_BAM'},minimum=10,maximum=200,source=FD)
    r('message_octets',{'transport':'FD_MULTI_PG'},maximum=60,source=FD)
    r('frame_phase',{'transport':'FD_MULTI_PG'},allowed=['MULTI_PG'],source=FD)
    r('pgn',{'frame_phase':'MULTI_PG','frame_format':'FEFF_29'},allowed=[9472],source=PGN)
    r('cpg_octets',{'transport':'FD_MULTI_PG'},equal_parameter='j39_message_octets',source=FD)
    r('container_octets',{'transport':'FD_MULTI_PG'},equal_expression={'sum':[{'product':[4,'j39_cpg_count']},'j39_cpg_total_octets']},source=FD)
    r('cpg_total_octets',{'transport':'FD_MULTI_PG'},minimum_parameter='j39_cpg_octets',source=FD)
    r('frame_octets',{'transport':'FD_MULTI_PG'},equal_expression={'sum':['j39_container_octets','j39_padding_octets']},source=FD)
    for frame,min_unpadded in [(4,4),(5,5),(6,6),(7,7),(8,8),(12,9),(16,13),(20,17),(24,21),(32,25),(48,33),(64,49)]:
        r('container_octets',{'transport':'FD_MULTI_PG','frame_octets':frame},minimum=min_unpadded,source=FD)
    r('cpg_total_octets',{'transport':'FD_MULTI_PG','cpg_count':1},equal_parameter='j39_cpg_octets',source=FD)
    for service,length in [('ADDRESS_CLAIM',8),('REQUEST_PGN',3),('COMMANDED_ADDRESS',9)]:r('message_octets',{'service':service},allowed=[length],source=CA)
    r('assurance_source',when_not={'j39_assurance_mode':'NONE'},when_present=['j39_assurance_mode'],required=True,source=FUSA)
    r('assurance_octets',{'assurance_mode':'NONE'},allowed=[0],source=FUSA)
    for profile,version in [('LINUX_V6_6_FACTORY','v6.6'),('PYTHON_CAN_01ABA95_FACTORY',SHA)]:
        for key in ('build_commit','build_source','unmodified_build'):r(key,{'profile':profile},required=True,source=ECU)
        r('build_commit',{'profile':profile},allowed=[version],source=ECU);r('unmodified_build',{'profile':profile},allowed=[True],source=ECU)
    r('data_link',{'profile':'LINUX_V6_6_FACTORY'},allowed=['J1939_21'],source=DOC)
    for key,value in [('linux_tp_block',255),('linux_tp_padding',True),('linux_tx_queue_retries',100),('linux_abort_ms',500),('linux_echo_ms',10000)]:
        r(key,{'profile':'LINUX_V6_6_FACTORY'},allowed=[value])
    r('frame_format',{'profile':'PYTHON_CAN_01ABA95_FACTORY','data_link':'J1939_22'},allowed=['FEFF_29'],source=FD)
    r('brs',{'profile':'PYTHON_CAN_01ABA95_FACTORY','data_link':'J1939_22'},allowed=[True],source=ECU)
    r('etp_enabled',{'profile':'PYTHON_CAN_01ABA95_FACTORY'},allowed=[False],source=ECU)
    r('transport',{'profile':'PYTHON_CAN_01ABA95_FACTORY'},forbidden=['ETP_EXTENSION'],source=ECU)
    for key in ('socket_priority','so_broadcast','promiscuous','error_queue','cap_net_admin','filter_count','filter_source',
                'linux_tp_block','linux_tx_queue_retries','linux_retry_delay_ms','linux_abort_ms','linux_echo_ms','linux_tp_padding'):
        r(key,{'profile':'PYTHON_CAN_01ABA95_FACTORY'},allowed=[],source=SOCKET)
    r('assurance_mode',{'profile':'PYTHON_CAN_01ABA95_FACTORY','data_link':'J1939_22'},allowed=['NONE'],source=FD)
    for key,value in [('tos',2),('trailer_format',0),('ad_type',0),('fd_data_type',0)]:
        r(key,{'profile':'PYTHON_CAN_01ABA95_FACTORY','data_link':'J1939_22'},allowed=[value],source=FD)
    for key,value in [('t1_ms',750),('t2_ms',1250),('t3_ms',1250),('t4_ms',1050),('tr_ms',200),('th_ms',500),('claim_request_ms',1250)]:
        r(key,{'profile':'PYTHON_CAN_01ABA95_FACTORY'},allowed=[value],source=FD if not key.startswith('claim')else CA)
    r('t5_ms',{'data_link':'J1939_21'},allowed=[],source=CC)
    r('t5_ms',{'profile':'PYTHON_CAN_01ABA95_FACTORY','data_link':'J1939_22'},allowed=[3000],source=FD)
    r('name_reserved_bit',{'profile':'PYTHON_CAN_01ABA95_FACTORY'},allowed=[0],source=NAME)
    r('claim_wait_ms',{'profile':'PYTHON_CAN_01ABA95_FACTORY','claim_state':'WAIT_VETO'},allowed=[250],source=CA)
    r('preferred_address',{'profile':'PYTHON_CAN_01ABA95_FACTORY','claim_state':'WAIT_VETO'},minimum=128,maximum=247,source=CA)
    return {'rate_model':{'type':'J1939_EXPLICIT_CLASSIC_OR_FD_PHY','fields':[]},'required_parameters':['j39_'+k for k in REQUIRED],
        'native_parameter_prefixes':['j39_'],'parameter_constraints':rules,'mechanisms':{'framing':['CLASSIC21_CEFF_OR_FD22_EXPLICIT'],
        'arbitration':['ACTUAL_CAN_PRIORITY_AND_WIRE_PHASE_BOUNDS'],'addressing':['SOURCE_ADDRESS','NAME','PGN','STATIC_OEM_OR_EXACT_NAME_CLAIM'],
        'address_resolution':['J1939_ADDRESS_CLAIM'],'diagnostics':['J1939_DM'],
        'segmentation':['CLASSIC_TP_ETP_EXTENSION_FD_MULTI_PG_FD_TP_SEPARATE'],
        'acceptance':['SELECTED_PGN_SPN_ASSURANCE_AND_FULL_SEGMENT_E2E_NOT_INFERRED']}}

def fields():
    result=[];required=set(semantics()['required_parameters'])
    for spec in DECLARATIONS:
        item={k:v for k,v in spec.items()if v is not None};key=item['key'].removeprefix('j39_')
        item.update(label=key.replace('_',' '),category='communication',scope='network',required=item['key']in required,editable=True,
            integer=spec['type']=='number'and spec['unit']not in ('ms','m','Ohm'),parameter_origin='DEVICE_CONFIGURATION',
            default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
        proposals=[];py={'j39_profile':'PYTHON_CAN_01ABA95_FACTORY','j39_build_commit':SHA,'j39_unmodified_build':True}
        linux={'j39_profile':'LINUX_V6_6_FACTORY','j39_build_commit':'v6.6','j39_unmodified_build':True}
        if key=='nominal_bitrate_bps':proposals=[{'when':{'j39_phy_profile':p},'value':v,'source':source}for p,v,source in
            [('J1939_11_250K_STP',250000,PHY11),('J1939_15_250K_UTP',250000,PHY15),('J1939_14_500K_CLASSIC',500000,PHY14),('J1939_17_500K_2M_FD',500000,PHY17)]]
        if key=='data_bitrate_bps':proposals=[{'when':{'j39_phy_profile':'J1939_17_500K_2M_FD'},'value':2000000}]
        if key=='frame_format':proposals=[{'when':{'j39_data_link':'J1939_21'},'value':'CEFF_29'},
            {'when':{**py,'j39_data_link':'J1939_22'},'value':'FEFF_29'}]
        if key=='priority':proposals=[{'when':{**linux,'j39_frame_phase':'APPLICATION'},'value':6}]
        if key=='bam_interval_ms':proposals=[{'when':{**py,'j39_transport':'TP_BAM'},'value':50},
            {'when':{**linux,'j39_transport':'TP_BAM'},'value':50},{'when':{**py,'j39_transport':'FD_TP_BAM'},'value':10}]
        if key=='cts_packets':proposals=[{'when':{**py,'j39_transport':t},'value':1}for t in('TP_CONNECTION','FD_TP_CONNECTION')]
        python_values={'t1_ms':750,'t2_ms':1250,'t3_ms':1250,'t4_ms':1050,'tr_ms':200,'th_ms':500,'claim_start_ms':500,'claim_request_ms':1250}
        if key in python_values:
            scopes=[{}]if key.startswith('claim_')else[{'j39_transport':t}for t in('TP_CONNECTION','FD_TP_CONNECTION')]
            proposals=[{'when':{**py,**scope},'value':python_values[key]}for scope in scopes]
        if key=='claim_wait_ms':proposals=[{'when':{**py,'j39_claim_state':'WAIT_VETO'},'value':250}]
        if key=='t5_ms':proposals=[{'when':{**py,'j39_transport':'FD_TP_CONNECTION'},'value':3000}]
        if key in ('tos','trailer_format','ad_type','fd_data_type','brs'):
            proposals=[{'when':{**py,'j39_data_link':'J1939_22'},'value':{'tos':2,'trailer_format':0,'ad_type':0,'fd_data_type':0,'brs':True}[key]}]
        linux_values={'linux_tp_block':255,'linux_tp_padding':True,'linux_tx_queue_retries':100,'linux_abort_ms':500,'linux_echo_ms':10000,
            'so_broadcast':False,'promiscuous':False,'error_queue':False,'filter_count':0,'connection_interval_ms':0}
        if key in linux_values:proposals=[{'when':linux,'value':linux_values[key]}]
        if proposals:item.update(conditional_defaults=[{**v,'source':v.get('source',item['source']),'source_revision':SOURCES[v.get('source',item['source'])]}for v in proposals],default_status='PROPOSED_CONDITIONAL')
        result.append(item)
    return result
