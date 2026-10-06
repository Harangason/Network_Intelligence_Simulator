"""Thread's own public baseline, actual dataset and radio/6LoWPAN bounds.

The reviewed public documentation is not a complete Thread edition or a device
certification. Secret keys are referenced, never copied into engineering data.
"""
from backend.nis.communication.services.native_review_support import declaration, fields as build_fields, WIRE_KEYS, ETHERNET_KEYS
OV='https://www.threadgroup.org/Portals/0/documents/resources/Thread_Technical_Overview.pdf'
ROLE='https://openthread.io/guides/thread-primer/node-roles-and-types'
IP='https://openthread.io/guides/thread-primer/ipv6-addressing'
DATA='https://openthread.io/reference/group/api-operational-dataset'
FRAG='https://www.rfc-editor.org/rfc/rfc4944.html'
COMP='https://www.rfc-editor.org/rfc/rfc6282.html'
LINK='https://openthread.io/reference/group/api-link-link'
RADIO='https://openthread.io/reference/group/radio-types'
SEC='https://openthread.io/reference/struct/ot-security-policy'
ROUTER='https://openthread.io/reference/group/api-thread-router'
STAMP='https://openthread.io/reference/struct/ot-timestamp'
SOURCES={OV:'Thread Technical Overview5October2015, printed2/6/10-15. 250kbps, IPv6/6LoWPAN, MACsecurity, sleepy parent; typical latency is not a guarantee.',ROLE:'OpenThread primer updated28September2026: roles/types/partitions/limits. MeshExtender/ECD terminology current; not full Thread1.4.1 specification.',IP:'OpenThread IPv6 primer updated28September2026: topology-dependentRLOC vs applicationML-EID and external scopes; no generated fixed addresses.',DATA:'OpenThread dataset API captured2October2026: otDatasetIsValid, required TLVs/lengths/UTF8/ULA, not full MeshCoP state-machine.',FRAG:'RFC4944 September2007 sections3-5.3, IEEE2006 reference MTU/overhead and fragmentation/reassembly.',COMP:'RFC6282 September2011 sections3/4.3: IPHC and UDP compression; sizes/offsets refer to uncompressed datagram, checksum elision conditional.',LINK:'OpenThread Link API updated27August2026: actual channel range/support, poll0clear vs≥10ms, max2^26−1, CSL160us units and actual retries.',RADIO:'OpenThread Radio Types captured2October2026: IEEE2.4GHz250k/62500symbols/s/16us/127octets, invalid RSSI/power127; actual platform capability and RF bounds separate.',SEC:'OpenThread SecurityPolicy API captured2October2026: configurable flags, rotationhours and actual routing-version threshold; no secret/defaultcredentials.',ROUTER:'OpenThread Router/Leader API captured2October2026: actual allowedchildren, router-ID range, promotion thresholds/timers and leaderweight; no guessed SDK build defaults.',STAMP:'OpenThread otTimestamp API updated14April2026: seconds/ticks/authoritative components; actual wire edition/configuration source required.'}
DECLARATIONS=[]
def d(k,t,meaning,source=OV,**kw):DECLARATIONS.append(declaration('th_',k,t,meaning,source,SOURCES[source],**kw))
for k,meaning,opts,src in [
 ('review_profile','Reviewed public documentation baseline versus independently registered actual edition.',['PUBLIC_BASELINE_2026','REGISTERED_ACTUAL'],OV),
 ('proposal_mode','Source proposals remain separate from commissioned actual values.',['SOURCE_BASELINE','ACTUAL_CONFIG'],OV),
 ('phy','Actual bearer: reviewed2.4GHz OQPSK or independently registered bearer.',['IEEE_802154_24GHZ_OQPSK','REGISTERED_ACTUAL'],RADIO),
 ('role','Actual forwarding role in one partition.',['MESH_EXTENDER','END_DEVICE','LEADER'],ROLE),
 ('device_type','Actual capabilities; ECD may promote, FED and MTD are children.',['ECD','FED','MED','SED','SSED','REGISTERED_ACTUAL'],ROLE),
 ('dataset_kind','Actual active/pending operational dataset.',['ACTIVE','PENDING'],DATA),
 ('address_kind','Actual application endpoint identity separate from topology locator.',['ML_EID','RLOC','ALOC','LINK_LOCAL','GLOBAL'],IP),
 ('fragment_kind','Actual adaptation fragmentation header.',['NONE','FIRST','SUBSEQUENT'],FRAG),
 ('compression','Actual LOWPAN_IPHC or uncompressed IP; not every header is two bytes.',['IPHC','UNCOMPRESSED','REGISTERED_ACTUAL'],COMP),
 ('udp_ports_mode','Actual UDP NHC portencoding0..3.',['FULL_FULL','FULL_LOW8','LOW8_FULL','LOW4_LOW4'],COMP),
 ('outcome','Correlated functional consumption status.',['ACCEPTED','STALE','ERROR','UNKNOWN'],OV),
]:d(k,'select',meaning,options=opts,source=src)
for k,meaning,lo,hi,unit,integer,src in [
 ('channel','Actual commissioned2.4GHz channel11..26 and hardware-supported channelmask.',11,26,None,True,LINK),
 ('channel_mask','Actual dataset channelmask32bit; selectedchannel bit must be set.',0,4294967295,None,True,DATA),
 ('symbol_rate','Actual2.4GHz reference62500 symbols/s, not data throughput.',1,None,'symbol/s',True,RADIO),
 ('symbol_us','Actual2.4GHz reference16us symbol duration.',0,None,'us',False,RADIO),
 ('symbols_per_octet','Actual2symbols per data octet for2.4GHz OQPSK.',1,None,None,True,RADIO),
 ('psdu_bytes','Actual MAC frame including FCS, distinct application/IP datagram.',3,127,'byte',True,RADIO),
 ('mac_header_bytes','Actual addressing/control/header bytes excluding separate security overhead and FCS; IEEE2006 reference25 total overhead includes2FCS.',0,23,'byte',True,FRAG),
 ('security_overhead_bytes','Actual auxiliaryheader/MIC overhead for selected security mode.',0,None,'byte',True,FRAG),
 ('fcs_bytes','Actual2byte PHY/MAC framecheck sequence included in PSDU.',0,2,'byte',True,RADIO),
 ('adaptation_bytes','Actual LOWPAN mesh/IPHC/fragment/UDP control bytes in this MAC payload.',0,None,'byte',True,FRAG),
 ('frame_data_bytes','Actual remaining encoded fragment or datagram content.',0,None,'byte',True,FRAG),
 ('phy_overhead_bytes','Actual preamble/SFD/PHYheader bytes from actual PHY qualification.',0,None,'byte',True,RADIO),
 ('wire_bytes','Actual PPDU bytes including PHY overhead plusPSDU.',3,None,'byte',True,RADIO),
 ('airtime_us','Actual serialization of wholePPDU; noMAC contention/poll/hops omitted from E2E.',0,None,'us',False,RADIO),
 ('pan_id','Actual dataset PAN ID; broadcastFFFF forbidden.',0,65535,None,True,DATA),
 ('network_name_bytes','Actual UTF8 byte count, not Unicode character count.',1,16,'byte',True,DATA),
 ('network_key_bytes','Provisioned key length; actual secret stored by key reference.',0,None,'byte',True,DATA),
 ('pskc_bytes','Provisioned PSKc length; actual secret stored by key reference.',0,None,'byte',True,DATA),
 ('active_seconds','Actual dataset timestamp seconds, distinct clock synchronization/Unix event time.',0,None,'s',True,STAMP),
 ('active_ticks','Actual dataset timestamp ticks; wire width/revision requires actual dataset codec.',0,65535,None,True,STAMP),
 ('pending_seconds','Actual pending timestamp seconds, distinct change delay.',0,None,'s',True,STAMP),
 ('pending_ticks','Actual pending timestamp ticks.',0,65535,None,True,STAMP),
 ('pending_delay_ms','Actual PendingDataset DelayTimer, no generic1000ms protocoldefault.',0,4294967295,'ms',True,DATA),
 ('rotation_hours','Actual key rotation in hours, no universal commissioned default.',0,65535,'h',True,SEC),
 ('routing_version_threshold','Actual API version-threshold value, edition wire width independently qualified.',0,255,None,True,SEC),
 ('partition_id','Actual logical partition identifier32bit, not fixeddefault.',0,4294967295,None,True,ROLE),
 ('leaders_per_partition','Actual one leader in each connected partition.',0,None,None,True,ROLE),
 ('mesh_extenders','Actual active extenders in reviewed public baseline≤32; device limit separate.',0,None,None,True,ROLE),
 ('children','Actual child count on one parent, reviewed public baseline≤511.',0,None,None,True,ROLE),
 ('allowed_children','Actual compiled/configured parent child-table capacity.',0,65535,None,True,ROUTER),
 ('leader_weight','Actual uint8 leader preference, no universal default64.',0,255,None,True,ROUTER),
 ('router_id_min','Actual assignable router-ID range minimum from implementation.',0,255,None,True,ROUTER),
 ('router_id_max','Actual assignable router-ID range maximum, not active router count.',0,255,None,True,ROUTER),
 ('router_id','Actual topology routerID within configured range.',0,255,None,True,ROUTER),
 ('child_id','Actual child identifier; extender/leader childID0.',0,65535,None,True,IP),
 ('upgrade_threshold','Actual promotion threshold, not every ECD always router.',0,255,None,True,ROUTER),
 ('downgrade_threshold','Actual demotion threshold.',0,255,None,True,ROUTER),
 ('router_jitter_s','Actual routerselection jitter bound from implementation.',0,255,'s',True,ROUTER),
 ('context_reuse_s','Actual contextID reuse delay.',0,4294967295,'s',True,ROUTER),
 ('child_timeout_s','Actual parent child lifetime; not same as poll period.',0,4294967295,'s',True,LINK),
 ('poll_ms','Actual OpenThread external poll0 clears override; nonzero≥10ms≤2^26−1.',0,67108863,'ms',True,LINK),
 ('effective_poll_ms','Actual resulting sleepy polling bound, zero override is not zero latency.',0,None,'ms',False,LINK),
 ('poll_wait_ms','Actual worst wait for parent delivery, requires own measured/scheduled evidence.',0,None,'ms',False,LINK),
 ('csl_period_units','Actual CSL period in units of10symbols (160us), edition≥1.2 supported separately.',0,65535,None,True,LINK),
 ('csl_period_us','Actual configured CSL period fromunits, not default for an ordinary SED.',0,None,'us',False,LINK),
 ('csl_guard_us','Actual clock drift/wakeup/receive guard bound.',0,None,'us',False,LINK),
 ('retries_direct','Actual configured direct frame retry limit, notCAN retry policy.',0,255,None,True,LINK),
 ('retries_indirect','Actual configured indirect retry limit, separate poll-bound count.',0,255,None,True,LINK),
 ('backoff_bound_us','Actual contention/CCA/backoff envelope, not guaranteed byPHYclock.',0,None,'us',False,LINK),
 ('ack_bound_us','Actual acknowledgment/turnaround/timeout envelope.',0,None,'us',False,LINK),
 ('retry_bound_us','Actual aggregate retry envelope, not scalar retransmission percentage.',0,None,'us',False,LINK),
 ('hop_count','Actual whole packet path forwarding count, not fixed mesh-depthdefault.',1,None,None,True,ROLE),
 ('hops_left','Actual RFC4944 mesh header4bit hopsleft;15requires deepfield.',0,15,None,True,FRAG),
 ('deep_hops_left','Actual optional8bit deep-hop field.',0,255,None,True,FRAG),
 ('hop_bound_ms','Actual aggregate perpath/hop scheduling/queue envelope.',0,None,'ms',False,ROLE),
 ('ipv6_mtu','Reviewed RFC4944 IPv6 linkMTU1280, not rawradio frame size.',0,None,'byte',True,FRAG),
 ('ipv6_payload_bytes','Actual uncompressed IPv6 PayloadLength16bit.',0,65535,'byte',True,FRAG),
 ('datagram_bytes','Actual uncompressed IPv6 header40+payload bytes.',40,None,'byte',True,FRAG),
 ('fragment_size','Actual11bit uncompressed datagram_size shared by fragments.',0,2047,'byte',True,FRAG),
 ('fragment_tag','Actual16bit tag shared across datagram and source/destination.',0,65535,None,True,FRAG),
 ('next_fragment_tag','Actual increment modulo65536; initialtag undefined.',0,65535,None,True,FRAG),
 ('fragment_offset_units','Actual subsequent datagram offset in8uncompressed octets.',0,255,None,True,FRAG),
 ('fragment_offset_bytes','Actual decoded offset, not compressed wire offset.',0,2040,'byte',True,FRAG),
 ('fragment_coverage_bytes','Actual represented uncompressed bytes in this fragment.',0,None,'byte',True,FRAG),
 ('fragment_header_bytes','Actual FRAG1four or FRAGNfive bytes, NONEzero.',0,5,'byte',True,FRAG),
 ('reassembly_timeout_s','Actual incomplete-datagram discardtimer≤60s.',0,60,'s',False,FRAG),
 ('reassembly_buffer_bytes','Actual available buffer for full uncompressed datagram.',0,None,'byte',True,FRAG),
 ('iphc_base_bytes','Actual base2 or3 withcontext extension, excludes inlinefields.',0,3,'byte',True,COMP),
 ('compressed_header_bytes','Actual complete compression+inlinefields; not always2or7.',0,None,'byte',True,COMP),
 ('context_src','Actual4bit source contextID.',0,15,None,True,COMP),('context_dst','Actual4bit destination contextID.',0,15,None,True,COMP),
 ('udp_source_port','Actual16bit UDP port before NHCcompression.',0,65535,None,True,COMP),('udp_destination_port','Actual16bit UDP port before NHCcompression.',0,65535,None,True,COMP),
 ('source_ms','Actual producer sampling/encode/queue bound.',0,None,'ms',False,OV),('transport_ms','Actual whole radio/CCA/retry/poll/path/reassembly envelope.',0,None,'ms',False,OV),('consumer_ms','Actual final decode/use bound.',0,None,'ms',False,OV),
 ('e2e_ms','Actual source+wholetransport+consumer bound.',0,None,'ms',False,OV),('deadline_ms','Actual independently specified functional deadline.',0,None,'ms',False,OV),('age_ms','Actual correlated data age atconsumer.',0,None,'ms',False,OV),('freshness_ms','Actual independent acceptableage.',0,None,'ms',False,OV),
]:d(k,'number',meaning,source=src,min=lo,max=hi,unit=unit,integer=integer)
for k,meaning,src in [
 ('rx_on_idle','Actual receiveralwayson versus sleepydevice.',ROLE),('forwards','Actual forwards othernodes; children do not.',ROLE),('border_router','Actual external-network role, not mandatory for local Thread.',ROLE),('external_delivery','Actual communication crosses Thread/nonThread boundary.',ROLE),
 ('active_authoritative','Actual ActiveTimestamp component, not time-syncproof.',STAMP),('pending_authoritative','Actual PendingTimestamp component.',STAMP),
 ('dataset_verified','Actual wholeTLV validity, duplicates/length/value checks and matching commissionedconfig.',DATA),('mac_security_verified','Actual linksecurity configured and validated, no end-to-end applicationsecurity inference.',OV),
 ('obtain_network_key','Actual out-of-band key provisioning permitted by policy.',SEC),('native_commissioning','Actual PSKc nativecommissioning permitted.',SEC),('external_commissioning','Actual externalcommissioner authentication permitted.',SEC),('legacy_routers','Actual Thread1.0/1.1routers permitted.',SEC),('commercial_commissioning','Actual commercialcommissioning enabled.',SEC),('autonomous_enrollment','Actual autonomousenrollment enabled.',SEC),('key_provisioning','Actual keyprovisioning permitted.',SEC),('toble','Actual ToBLE enabled, not same2.4GHz radio capacity.',SEC),('non_ccm_routers','Actual nonCCM routers enabled.',SEC),
 ('last_fragment','Actual final fragment; preceding fragments eightoctet alignment.',FRAG),('reassembly_overlap','Actual inconsistent overlap encountered.',FRAG),('partial_discarded','Actual timeout/disassociation/inconsistent-overlap fragments discarded.',FRAG),('reassembled','Actual complete matching tagged datagram reassembled.',FRAG),
 ('context_extension','Actual CIDextensionbyte present.',COMP),('checksum_elided','Actual UDPchecksum elision, only under explicitupperlayerauthorization.',COMP),('checksum_authorized','Actual upperlayer authorization and equivalentcoverage.',COMP),('checksum_verified','Actual sourceUDPchecksum validated beforeelision.',COMP),('integrity_verified','Actual additional link/end-to-end integrity presentandvalidated.',COMP),('checksum_restored','Actual decompressor restorescorrectIPv6UDPchecksum.',COMP),
 ('phy_verified','Actual RF/channel/regulatory/interference/device realization verified.',RADIO),('path_verified','Actual path/hops/poll/retry/service/reassembly bounded.',OV),('data_accepted','Actual consumingfunction accepted thiscorrelateddata.',OV),
]:d(k,'boolean',meaning,source=src)
for k,meaning,src in [
 ('revision','Actual Threadedition/implementation/build revision.',OV),('configuration_source','Actual commissioned configuration and role evidence.',OV),('phy_source','Actual radio/platform/channel/interference/regulatory evidence.',RADIO),('dataset_source','Actual dataset metadata/provisioning validation source.',DATA),
 ('security_source','Actual commissioned credential references andsecuritypolicy evidence.',SEC),('application_source','Actual upperlayer codec/port/security/function acceptance contract.',OV),('schedule_source','Actual whole path, queues, polls, retries, fragmentation and delivery bounds.',OV),('acceptance_source','Actual independentdeadline/freshness behavior contract.',OV),('observation_source','Actual correlated source/packet/reassembly/use trace.',OV),('registered_source','Actual separatelyqualified edition/PHY/codec extension.',OV),
 ('parent_id','Actual parentidentity for child, not generated frommesh-extender count.',ROLE),('partition_source','Actual partitionmembership/leader/topology observation.',ROLE),('external_binding_source','Actual explicit borderrouter/externalIP/PHYpath.',ROLE),('csl_source','Actual version≥1.2/platform clock/synchronizedsleep qualification.',LINK),
 ('network_name','Actual noncontrol UTF8 networkname1..16bytes.',DATA),('extended_pan_hex','Actual nonsecret8byte ExtendedPANID; notallzero/allFF.',DATA),('mesh_prefix','Actual locallyassigned fd00::/8 ULA /64prefix, notfixedchosenvalue.',DATA),('network_key_ref','Actual credentialstore reference; never secret keybytes.',DATA),('pskc_ref','Actual credentialstore PSKc reference; never secret PSKcbytes.',DATA),
 ('endpoint_address','Actual IPv6 address; applicationML-EID separate from topologyRLOC.',IP),('peer_address','Actual IPv6 peeraddress scoped tobound network.',IP),
]:d(k,'text',meaning,source=src,**({'format':'IP_ADDRESS'}if k.endswith('address')else {'format':'IP_NETWORK','ip_version':6,'prefix_length':64,'within_network':'fd00::/8'}if k=='mesh_prefix'else {}))
REQUIRED=('review_profile','revision','phy','configuration_source','phy_source','dataset_source','security_source','application_source','schedule_source','acceptance_source')
REMOVED={k:'Thread uses its actual IEEE802.15.4/IPv6/6LoWPAN path, notCAN retry/gateway/Ethernet MTU/rate fields.'for k in(*WIRE_KEYS,*ETHERNET_KEYS)if k!='bitrate'}
def semantics():
 rules=[]
 def r(k,w=None,src=OV,**kw):rules.append(dict(parameter='th_'+k,when={'th_review_profile':'PUBLIC_BASELINE_2026',**{'th_'+a:b for a,b in(w or{}).items()}},source=src,**kw))
 rules.append(dict(parameter='th_registered_source',when={'th_review_profile':'REGISTERED_ACTUAL'},required=True,source=OV))
 r('registered_source',{'phy':'REGISTERED_ACTUAL'},required=True,src=RADIO)
 rules.extend(dict(parameter=k,when={},allowed=[],source=OV)for k in REMOVED)
 rules.append(dict(parameter='bitrate_bps',when={'th_review_profile':'PUBLIC_BASELINE_2026','th_phy':'IEEE_802154_24GHZ_OQPSK'},allowed=[250000],source=RADIO))
 for k,value in [('symbol_rate',62500),('symbol_us',16),('symbols_per_octet',2),('fcs_bytes',2)]:r(k,{'phy':'IEEE_802154_24GHZ_OQPSK'},allowed=[value],src=RADIO)
 r('wire_bytes',equal_expression={'sum':['th_psdu_bytes','th_phy_overhead_bytes']},src=RADIO)
 r('psdu_bytes',equal_expression={'sum':['th_mac_header_bytes','th_security_overhead_bytes','th_fcs_bytes','th_adaptation_bytes','th_frame_data_bytes']},src=FRAG)
 r('airtime_us',equal_ratio={'numerator_parameter':'th_wire_bytes','factor':8000000,'denominator_parameter':'bitrate_bps'},src=RADIO)
 for c in range(11,27):r('channel_mask',{'channel':c},minimum_expression={'sum':[2**c,{'subtract':['th_channel_mask',{'integer_remainder':['th_channel_mask',2**(c+1)]}]}]},src=DATA)
 r('channel_mask',{'phy':'IEEE_802154_24GHZ_OQPSK'},forbidden_bit_mask=0xf80007ff,src=DATA)
 r('pan_id',forbidden=[65535],src=DATA)
 r('network_name',pattern=r'[^\x00-\x1f\x7f]+',text_encoding='utf-8',encoded_bytes_parameter='th_network_name_bytes',src=DATA)
 r('network_name_bytes',when_present=['th_network_name'],required=True,src=DATA)
 r('extended_pan_hex',pattern=r'[0-9a-fA-F]{16}',forbidden=['0000000000000000','ffffffffffffffff','FFFFFFFFFFFFFFFF'],src=DATA)
 for k in('network_key_bytes','pskc_bytes'):r(k,allowed=[16],src=DATA)
 for kind in('ACTIVE','PENDING'):
  for k in('active_seconds','active_ticks','active_authoritative','channel','channel_mask','extended_pan_hex','mesh_prefix','network_name','network_name_bytes','pan_id','network_key_ref','network_key_bytes','pskc_ref','pskc_bytes','security_source'):r(k,{'dataset_kind':kind},required=True,src=DATA)
 for k in('pending_seconds','pending_ticks','pending_authoritative','pending_delay_ms'):r(k,{'dataset_kind':'PENDING'},required=True,src=DATA)
 for k in('endpoint_address','peer_address'):r(k,ip_address_version=6,src=IP)
 r('leaders_per_partition',allowed=[1],src=ROLE);r('mesh_extenders',maximum=32,src=ROLE);r('children',maximum=511,maximum_parameter='th_allowed_children',src=ROLE)
 r('router_id',minimum_parameter='th_router_id_min',maximum_parameter='th_router_id_max',src=ROUTER);r('router_id_min',maximum_parameter='th_router_id_max',src=ROUTER)
 for role in('MESH_EXTENDER','LEADER'):
  for k in('rx_on_idle','forwards'):r(k,{'role':role},required=True,allowed=[True],src=ROLE)
  r('child_id',{'role':role},allowed=[0],src=IP)
 r('forwards',{'role':'END_DEVICE'},allowed=[False],src=ROLE)
 for kind in('FED','MED','SED','SSED'):r('role',{'device_type':kind},required=True,allowed=['END_DEVICE'],src=ROLE)
 for kind in('ECD','FED','MED'):r('rx_on_idle',{'device_type':kind},required=True,allowed=[True],src=ROLE)
 for kind in('SED','SSED'):r('rx_on_idle',{'device_type':kind},required=True,allowed=[False],src=ROLE);r('parent_id',{'device_type':kind},required=True,src=ROLE);r('poll_wait_ms',{'device_type':kind},required=True,src=LINK)
 r('poll_ms',when_ranges={'th_poll_ms':[1,9]},allowed=[],src=LINK)
 r('csl_period_us',equal_expression={'product':[160,'th_csl_period_units']},src=LINK)
 r('csl_source',{'device_type':'SSED'},required=True,src=LINK)
 for k in('external_binding_source',):r(k,{'external_delivery':True},required=True,src=ROLE)
 r('ipv6_mtu',allowed=[1280],src=FRAG);r('datagram_bytes',equal_expression={'sum':[40,'th_ipv6_payload_bytes']},maximum_parameter='th_ipv6_mtu',src=FRAG)
 for kind,n in [('NONE',0),('FIRST',4),('SUBSEQUENT',5)]:r('fragment_header_bytes',{'fragment_kind':kind},allowed=[n],src=FRAG)
 r('fragment_offset_units',{'fragment_kind':'FIRST'},allowed=[0],src=FRAG)
 r('fragment_offset_units',{'fragment_kind':'SUBSEQUENT'},minimum=1,src=FRAG)
 r('fragment_offset_bytes',equal_expression={'product':[8,'th_fragment_offset_units']},src=FRAG)
 r('fragment_size',equal_parameter='th_datagram_bytes',src=FRAG)
 r('fragment_coverage_bytes',{'last_fragment':False},multiple_of=8,src=FRAG)
 r('fragment_coverage_bytes',maximum_expression={'subtract':['th_fragment_size','th_fragment_offset_bytes']},src=FRAG)
 r('reassembly_buffer_bytes',minimum_parameter='th_fragment_size',src=FRAG)
 r('next_fragment_tag',equal_expression={'integer_remainder':[{'sum':['th_fragment_tag',1]},65536]},src=FRAG)
 r('partial_discarded',{'reassembly_overlap':True},required=True,allowed=[True],src=FRAG)
 r('deep_hops_left',{'hops_left':15},required=True,src=FRAG)
 r('iphc_base_bytes',{'compression':'IPHC','context_extension':False},allowed=[2],src=COMP);r('iphc_base_bytes',{'compression':'IPHC','context_extension':True},allowed=[3],src=COMP)
 r('compressed_header_bytes',minimum_parameter='th_iphc_base_bytes',src=COMP)
 for mode,source_range,dest_range in [('FULL_FULL',None,None),('FULL_LOW8',None,(0xf000,0xf0ff)),('LOW8_FULL',(0xf000,0xf0ff),None),('LOW4_LOW4',(0xf0b0,0xf0bf),(0xf0b0,0xf0bf))]:
  for k,bounds in [('udp_source_port',source_range),('udp_destination_port',dest_range)]:
   if bounds:r(k,{'udp_ports_mode':mode},minimum=bounds[0],maximum=bounds[1],src=COMP)
 for k in('checksum_authorized','checksum_verified','integrity_verified','checksum_restored'):r(k,{'checksum_elided':True},required=True,allowed=[True],src=COMP)
 r('e2e_ms',equal_expression={'sum':['th_source_ms','th_transport_ms','th_consumer_ms']});r('e2e_ms',maximum_parameter='th_deadline_ms');r('age_ms',maximum_parameter='th_freshness_ms')
 r('transport_ms',minimum_expression={'sum':['th_poll_wait_ms','th_hop_bound_ms']})
 for k in('source_ms','transport_ms','consumer_ms'):r(k,when_present=['th_e2e_ms'],required=True)
 for k in('role','device_type','endpoint_address','peer_address','observation_source','e2e_ms','deadline_ms','age_ms','freshness_ms'):r(k,{'data_accepted':True},required=True)
 for k,v in [('dataset_verified',True),('mac_security_verified',True),('phy_verified',True),('path_verified',True),('reassembled',True),('outcome','ACCEPTED')]:r(k,{'data_accepted':True},required=True,allowed=[v])
 return dict(rate_model={'type':'SINGLE_BITRATE','fields':['bitrate_bps'],'minimum_bps':1},parameter_evidence_scope='EXPLICIT_LAYER',required_parameters=['th_'+k for k in REQUIRED],native_parameter_prefixes=['th_'],parameter_constraints=rules,medium_access_model='ACTUAL_CSMA_CA_PARENT_POLL_AND_PATH',arbitration_model_id='ACTUAL_THREAD_PHY_CSMA_RETRY_POLL',mechanisms={'network':['IPV6_6LOWPAN_NOT_APPLICATION_CODEC','PARTITION_LEADER_PARENT_CHILD'],'timing':['WHOLE_PHY_CSMA_RETRY_POLL_PATH_REASSEMBLY','CONSUMER_ACCEPTANCE_SEPARATE']})
def fields():
 baseline={'th_review_profile':'PUBLIC_BASELINE_2026','th_proposal_mode':'SOURCE_BASELINE'}
 proposals={}
 for k,v,src,w in [('symbol_rate',62500,RADIO,{'th_phy':'IEEE_802154_24GHZ_OQPSK'}),('symbol_us',16,RADIO,{'th_phy':'IEEE_802154_24GHZ_OQPSK'}),('symbols_per_octet',2,RADIO,{'th_phy':'IEEE_802154_24GHZ_OQPSK'}),('fcs_bytes',2,RADIO,{'th_phy':'IEEE_802154_24GHZ_OQPSK'}),('ipv6_mtu',1280,FRAG,{}),('leaders_per_partition',1,ROLE,{}),('fragment_header_bytes',4,FRAG,{'th_fragment_kind':'FIRST'}),('fragment_header_bytes',5,FRAG,{'th_fragment_kind':'SUBSEQUENT'})]:
  proposals.setdefault('th_'+k,[]).append(dict(when={**baseline,**w},value=v,source=src,source_revision=SOURCES[src]))
 out=build_fields(DECLARATIONS,['th_'+k for k in REQUIRED],proposals)
 for f in out:
  if f['key']not in {'th_'+k for k in REQUIRED}|{'th_proposal_mode','th_registered_source'}:f['schema_when']={'th_review_profile':'PUBLIC_BASELINE_2026'}
 return out
