"""Time-Triggered Ethernet own roles, traffic classes and actual schedule bounds.

Public protocol descriptions and specifically identified hardware are reviewed;
public abstracts do not certify the full SAE AS6802A standard or a safety case.
"""
from backend.nis.communication.services.native_review_support import declaration, fields as build_fields, WIRE_KEYS, ETHERNET_KEYS
ESA='https://www.esa.int/Enabling_Support/Space_Engineering_Technology/Onboard_Computers_and_Data_Handling/Time-Triggered_Ethernet'
PMC='https://tttech.com/aerospace/products/end-systems/tte-end-system-lab-space-pmc'
CONTROLLER='https://indico.esa.int/event/148/attachments/985/1175/brochure_final.pdf'
RUAG='https://indico.esa.int/event/22/contributions/2011/attachments/1698/1990/6.ADCSS_2013_-_Implementation_aspects_of_TTEthernet_Interfaces_P-FLPP-HO_-_1108586_-_RSE_-_1_-_1.pdf'
STARTUP='https://ntrs.nasa.gov/api/citations/20120014302/downloads/20120014302.pdf'
SYNC='https://ntrs.nasa.gov/api/citations/20120003666/downloads/20120003666.pdf'
SAE='https://saemobilus.sae.org/standards/as6802a-time-triggered-ethernet'
SOURCES={ESA:'ESA publicTTEoverview: distinctscheduled/asynchronousclasses, switchedEthernet andactualPHYdevices; no universal1Gbit/s.',PMC:'TTTech TTEEndSystemLabSpacePMC publicproductpage captured2October2026:3channels100/1000M fullDuplex, TT/RC/BE. Product not all TTEdevices.',CONTROLLER:'TTTech ADCSS2016 exhibitor sheet actualPDFpage32: EndSystemControllerSpace3channels10/100/1000M,RGMII vsRMII,128send/256receiveVL/8partitions/1024send2048receiveCOMports. Edition/product-specific maxima.',RUAG:'RUAG ADCSS23October2013 presentation actualslides4-5: TT/RC/BE, commonglobaltime/perhopVLschedule, switchgatekeepers,PCF/latencycorrection.',STARTUP:'NASA/CR2012-217764 publicstartupmodel report selectedsection2:roles/priorityfilter/CSCAIN/cliquerecovery. Example6SM6CM10integrationcycles not defaults or generalfaultproof.',SYNC:'NASA/CR2012-217554 March2012 selectedsections2/3.2: cluster/equalintegrationcycles, scheduledperlinknonoverlap, SM/CM/SC rolesnotnecessarilyfixeddeviceclass, precision/permanence andexplicitfaultassumptions. Researchanalysis not fullcurrentstandard.',SAE:'SAE AS6802A publisherpublicabstract14February2023: networkfault-tolerantsynchronization anddispatch; node-memory/CPUpartitioning andcompleteapplicationarchitecture notcovered. Fulllicensedstandardnotreviewed.'}
DECLARATIONS=[]
def d(k,t,meaning,source=SYNC,**kw):DECLARATIONS.append(declaration('tt_',k,t,meaning,source,SOURCES[source],**kw))
for k,meaning,opts,src in [
 ('review_profile','Selected publicdescriptions/devicebaseline versus separatelyqualifiedactualedition.',['PUBLIC_REFERENCE','REGISTERED_ACTUAL'],SAE),('proposal_mode','Source proposals distinct commissionedvalues.',['SOURCE_BASELINE','ACTUAL_CONFIG'],SAE),
 ('device_profile','Actual identifieddevice, no productlimitsapplied toallTTE.',['TTTECH_CONTROLLER_SPACE_2016','TTTECH_PMC_2026','REGISTERED_ACTUAL'],CONTROLLER),('phy_interface','ActualRGMII/RMII orindependentlyqualifiedlinkinterface.',['RGMII','RMII','REGISTERED_ACTUAL'],CONTROLLER),
 ('traffic_class','Actual TTscheduled, RCboundedrate, BEasynchronous semantics.',['TT','RC','BE'],RUAG),('sync_role','Actualrole is distinct physicalend-system/switchclass.',['SM','CM','SC','NONE'],SYNC),('pcf_type','Actual startup/synchronizationmessage type, notapplicationTTdataset.',['CS','CA','IN'],STARTUP),
 ('fault_profile','Actual assumptions ofselectedanalysis/safetycase, notgeneraldualByzantineclaim.',['SINGLE_BYZANTINE_OR_OMISSION','DUAL_OMISSION','REGISTERED_ACTUAL'],SYNC),('sync_state','Actual assessed synchronizationstatus, not a claimedcompletewire-stateencoding.',['SYNCHRONIZED','INTEGRATING','UNSYNCHRONIZED','UNKNOWN'],SYNC),
 ('rc_profile','Actual registeredrate-constrainedprotocol/codec path, independent TTtime schedule.',['ARINC664P7_BOUND_ACTUAL','REGISTERED_ACTUAL'],RUAG),('outcome','Actual correlatedconsumercurrentdata outcome.',['ACCEPTED','STALE','ERROR','UNKNOWN'],SAE),
]:d(k,'select',meaning,source=src,options=opts)
for k,meaning,lo,hi,unit,integer,src in [
 ('link_bps','Actual perhopphysicalrate; knownproductratesare conditional, notAS6802globalminimum.',1,None,'bit/s',True,CONTROLLER),('channels','Actualdevicecommunicationchannels, notallindependentautomatically.',1,None,None,True,PMC),
 ('send_vls','Actual configuredsendvirtual-link count.',0,None,None,True,CONTROLLER),('receive_vls','Actual configuredreceivevirtual-link count.',0,None,None,True,CONTROLLER),('partitions','Actual memorypartitionsdevice-capability, notapplicationCPU safetyproof.',0,None,None,True,CONTROLLER),('send_com_ports','Actual configuredsendcommunicationports.',0,None,None,True,CONTROLLER),('receive_com_ports','Actual configuredreceivecommunicationports.',0,None,None,True,CONTROLLER),
 ('frame_bytes','Actual completeEthernetframebytes, notapplicationpayloadonly.',0,None,'byte',True,SAE),('wire_bytes','Actual completeoccupiedframe/PHY/IFGbytes underqualifiedactualPHYmodel.',0,None,'byte',True,SAE),('serialization_us','Actual wholewirebytes8/rate, notfullE2Elatency.',0,None,'us',False,SAE),('peer_frame_max','Actual qualifiedpeer/MACmaximumframe, notglobalTTE1500.',0,None,'byte',True,SAE),
 ('integration_us','Actual configuredequalnominalintegrationperiod, no universal5ms/10ms.',0,None,'us',False,SYNC),('integration_cycles','Actual countwithinclusterperiod, examplesnotdefault10.',1,None,None,True,SYNC),('cluster_us','Actual completeclusterperiod=integration*cycles.',0,None,'us',False,SYNC),('period_us','Actual particularTTdatasetperiod, distinctintegrationperiod.',0,None,'us',False,RUAG),('phase_us','Actual periodicdispatchphasefromscheduleorigin.',0,None,'us',False,RUAG),('offset_us','Actual perhopTT transmissionoffsetwithincluster.',0,None,'us',False,SYNC),('slot_end_us','Actual correspondingperhopintervalendwithincluster.',0,None,'us',False,SYNC),('guard_us','Actual precision/drift/interferenceguardenvelope fromqualifiedschedule.',0,None,'us',False,SYNC),
 ('clock_error_us','Actual worstrelativelocalclockdifference, nottimestampgranularity.',0,None,'us',False,SYNC),('precision_us','Actual requiredmaximumrelativeclockerrorDelta.',0,None,'us',False,SYNC),('receive_window_us','Actual scheduledPCFreceptionacceptancewindow.',0,None,'us',False,SYNC),('sync_masters','ActualregisteredSMmembershipcount.',0,None,None,True,SYNC),('compression_masters','ActualregisteredCMmembershipcount.',0,None,None,True,SYNC),('sync_priority','Actual clockpriorityfromconfiguredfilter, no fixed1 or2.',0,None,None,True,STARTUP),
 ('rx_time_us','ActualPCFreceptiontimestamp inqualifiedcommonclockscope.',None,None,'us',False,SYNC),('actual_delay_us','Actual accumulatedtransitdelay forpermanence, notnominalserializationonly.',0,None,'us',False,SYNC),('maximum_delay_us','Actual qualifiedmaxPCFtransportdelay.',0,None,'us',False,SYNC),('added_delay_us','Actual artificialpermanencewait=max−actualdelay.',0,None,'us',False,SYNC),('permanence_us','Actualdeliverypoint=reception+addedwait.',None,None,'us',False,SYNC),('compression_us','Actual boundedCMcompressionprocessing/wait.',0,None,'us',False,SYNC),('startup_us','Actual boundedcoldstart/reintegrationresolution underfaultassumptions.',0,None,'us',False,STARTUP),('clique_recovery_us','Actual boundedpost-transientcliquerecovery, no example60cycledefault.',0,None,'us',False,STARTUP),
 ('rc_bag_us','Actual selectedRCminimuminterframegap/BAG; ownARINCboundsource, notTTcycle.',0,None,'us',False,RUAG),('rc_jitter_us','Actual selectedRCrelease/arrivaljitter.',0,None,'us',False,RUAG),('rc_queue_us','Actual fullRCqueue/servicecontentionenvelope.',0,None,'us',False,SYNC),('be_blocking_us','Actual boundedBEinterference ifclaimed;BEalonehasnoguarantee.',0,None,'us',False,SYNC),('switch_residence_us','Actual totalswitchprocessing/queue/waitbound alongpath.',0,None,'us',False,SYNC),('hop_count','Actual whole pathlink/switchcount.',1,None,None,True,SYNC),
 ('source_ms','Actual sampling/encode/hostqueue envelope.',0,None,'ms',False,SAE),('transport_ms','Actual allhopTT/RC/BE path envelope.',0,None,'ms',False,SAE),('consumer_ms','Actual decode/applicationCPU/use envelope separate AS6802networkscope.',0,None,'ms',False,SAE),('e2e_ms','Actual source+transport+consumerbound.',0,None,'ms',False,SAE),('deadline_ms','Actual independent functionaldeadline.',0,None,'ms',False,SAE),('age_ms','Actual correlatedproducer-to-consumerdataage.',0,None,'ms',False,SAE),('freshness_ms','Actual independentlyacceptablecurrentdataage.',0,None,'ms',False,SAE),
]:d(k,'number',meaning,source=src,min=lo,max=hi,unit=unit,integer=integer)
for k,meaning,src in [
 ('full_duplex','Actual knownTTTechdevicephysicalmodefull-duplex, notwholeprofilecert.',PMC),('fault_tolerance_claimed','Actualrequestednetworkfault-guarantees requireexplicitcase.',SYNC),('tt_nonoverlap_verified','Actual everyTTintervalnonoverlap ontheentireselectedroute.',SYNC),('clock_verified','Actualsynchronization/drift/precision/faultobservation qualified.',SYNC),('schedule_verified','Actualschedulecompiled/installed/allhop timing andcompetingtrafficverified.',RUAG),('path_verified','Actual allhopdevice/PHY/channel/streamboundqualified.',SYNC),('host_verified','ActualnodeCPU/memoryapplicationintegrationproofseparate networkstandard.',SAE),('data_accepted','Actualfreshcorrelateddatasetconsumedbyfunction.',SAE),
]:d(k,'boolean',meaning,source=src)
for k,meaning,src in [
 ('revision','ActualAS6802/implementation/devicebuildedition.',SAE),('configuration_source','Actual hardware/ports/VLs/TT/RC/BEbindings.',RUAG),('phy_source','Actual PHYfull-duplex/cable/encoding/frame/IFG/capabilities.',ESA),('schedule_source','Actual entireglobalperhopTTscheduleandRC/BEpolicingbounds.',SYNC),('acceptance_source','Actual independentfunctiondeadline/freshnessfailure contract.',SAE),('registered_source','Actual independentlyqualifiedvariant/edition extension.',SAE),('device_source','Actualselectedvendor/device/revision capabilities.',PMC),('clock_source','Actual SM/CM/SCmembership/state/precision/startup/clique/fault evidence.',SYNC),('pcf_source','ActualcompletePCFcodec/version/type/membership/transitdelayqualification.',STARTUP),('fault_source','Actual faultassumptions/topology/independentchannels/proofandtests.',SYNC),('rc_source','Actual registeredRCcodec/BAG/jitter/queue/policing qualification.',RUAG),('observation_source','Actualcorrelatedemission/allhoparrival/consumer trace.',SAE),('be_bound_source','Actualextrareservation/queue/policingproof forclaimedBEbound.',SYNC),
 ('vl_id','Actualperstreamvirtual-linkidentifier, notfixedglobalCANid.',RUAG),('path_id','Actualboundchannel/routeidentity.',SYNC),('schedule_revision','Actual installedschedule/configurationartifactversion.',RUAG),('membership_source','Actual SM/CMpriorityfilter/domain/clique membership.',STARTUP),('host_source','Actualnodememory/CPU/sampling/consumptionpartitioning proof.',SAE),
]:d(k,'text',meaning,source=src)
REQUIRED=('review_profile','revision','traffic_class','configuration_source','phy_source','schedule_source','acceptance_source')
REMOVED={k:'TTE uses its actual TT/RC/BE, sync/PCF/schedule/device path. GenericCANretry/gateway andunqualifiedEthernetclock/MTU/VLANfields do not substitute nativeconfiguration.'for k in(*WIRE_KEYS,*ETHERNET_KEYS)}
def semantics():
 rules=[]
 def r(k,w=None,src=SYNC,**kw):rules.append(dict(parameter='tt_'+k,when={'tt_review_profile':'PUBLIC_REFERENCE',**{'tt_'+a:b for a,b in(w or{}).items()}},source=src,**kw))
 rules.append(dict(parameter='tt_registered_source',when={'tt_review_profile':'REGISTERED_ACTUAL'},required=True,source=SAE))
 rules.extend(dict(parameter=k,when={},allowed=[],source=SAE)for k in REMOVED)
 for profile,rates in [('TTTECH_CONTROLLER_SPACE_2016',[10000000,100000000,1000000000]),('TTTECH_PMC_2026',[100000000,1000000000])]:
  r('link_bps',{'device_profile':profile},allowed=rates,src=CONTROLLER if profile.endswith('2016')else PMC);r('channels',{'device_profile':profile},maximum=3,src=PMC);r('full_duplex',{'device_profile':profile},allowed=[True],src=PMC)
 for k,v in [('send_vls',128),('receive_vls',256),('partitions',8),('send_com_ports',1024),('receive_com_ports',2048)]:r(k,{'device_profile':'TTTECH_CONTROLLER_SPACE_2016'},maximum=v,src=CONTROLLER)
 r('link_bps',{'device_profile':'TTTECH_CONTROLLER_SPACE_2016','phy_interface':'RMII'},allowed=[10000000,100000000],src=CONTROLLER)
 r('device_source',when_present=['tt_device_profile'],required=True,src=PMC)
 r('serialization_us',equal_ratio={'numerator_parameter':'tt_wire_bytes','denominator_parameter':'tt_link_bps','factor':8000000},src=SAE)
 r('wire_bytes',minimum_parameter='tt_frame_bytes',src=SAE);r('frame_bytes',maximum_parameter='tt_peer_frame_max',src=SAE)
 r('cluster_us',equal_expression={'product':['tt_integration_us','tt_integration_cycles']})
 r('clock_error_us',maximum_parameter='tt_precision_us')
 r('phase_us',exclusive_maximum_expression='tt_period_us')
 r('slot_end_us',maximum_parameter='tt_cluster_us',minimum_expression={'sum':['tt_offset_us','tt_serialization_us','tt_guard_us']})
 r('guard_us',minimum_parameter='tt_clock_error_us')
 r('actual_delay_us',maximum_parameter='tt_maximum_delay_us')
 r('added_delay_us',equal_expression={'subtract':['tt_maximum_delay_us','tt_actual_delay_us']})
 r('permanence_us',equal_expression={'sum':['tt_rx_time_us','tt_added_delay_us']})
 for k in('actual_delay_us','maximum_delay_us'):r(k,when_present=['tt_added_delay_us'],required=True)
 for k in('rx_time_us','added_delay_us'):r(k,when_present=['tt_permanence_us'],required=True)
 for k in('clock_source','membership_source'):r(k,when_present=['tt_sync_role'],when_not={'tt_sync_role':'NONE'},required=True)
 for k in('pcf_source',):r(k,when_present=['tt_pcf_type'],required=True,src=STARTUP)
 r('fault_source',{'fault_tolerance_claimed':True},required=True);r('fault_profile',{'fault_tolerance_claimed':True},required=True)
 for k in('rc_profile','rc_source','rc_bag_us','rc_jitter_us','rc_queue_us'):r(k,{'traffic_class':'RC'},required=True,src=RUAG)
 r('rc_bag_us',{'traffic_class':'RC'},exclusive_minimum=0,src=RUAG)
 r('be_bound_source',{'traffic_class':'BE'},when_present=['tt_transport_ms'],required=True)
 for k in('integration_us','integration_cycles','cluster_us','period_us','phase_us','offset_us','slot_end_us','serialization_us','guard_us','clock_error_us','precision_us','clock_source','vl_id','path_id','schedule_revision'):r(k,{'traffic_class':'TT'},required=True)
 for k in('integration_us','cluster_us','period_us'):r(k,{'traffic_class':'TT'},exclusive_minimum=0)
 r('sync_role',{'traffic_class':'TT'},required=True,allowed=['SM','CM','SC'])
 r('e2e_ms',equal_expression={'sum':['tt_source_ms','tt_transport_ms','tt_consumer_ms']},maximum_parameter='tt_deadline_ms',src=SAE);r('age_ms',maximum_parameter='tt_freshness_ms',src=SAE)
 for k in('source_ms','transport_ms','consumer_ms'):r(k,when_present=['tt_e2e_ms'],required=True,src=SAE)
 for k in('observation_source','host_source','e2e_ms','deadline_ms','age_ms','freshness_ms'):r(k,{'data_accepted':True},required=True,src=SAE)
 for k,v in [('path_verified',True),('host_verified',True),('outcome','ACCEPTED')]:r(k,{'data_accepted':True},required=True,allowed=[v],src=SAE)
 for k,v in [('clock_verified',True),('schedule_verified',True),('tt_nonoverlap_verified',True),('sync_state','SYNCHRONIZED')]:r(k,{'data_accepted':True,'traffic_class':'TT'},required=True,allowed=[v])
 return dict(rate_model={'type':'EXPLICIT_TTE_TRAFFIC_SCHEDULE_AND_PHY','fields':[]},parameter_evidence_scope='EXPLICIT_LAYER',required_parameters=['tt_'+k for k in REQUIRED],native_parameter_prefixes=['tt_'],parameter_constraints=rules,medium_access_model='ACTUAL_TT_RC_BE_PERLINK_SCHEDULE',arbitration_model_id='ACTUAL_TTE_GLOBAL_SYNC_AND_TRAFFIC_PARTITION',mechanisms={'network':['TT_RC_BE_SEPARATE','SM_CM_SC_ROLES_PCF_STARTUP_SYNC'],'timing':['GLOBAL_SCHEDULE_AND_PRECISION_QUALIFIED','NODE_APPLICATION_NOT_AS6802_NETWORK_PROOF']})
def fields():
 proposals={}
 for profile,rate,src in [('TTTECH_CONTROLLER_SPACE_2016',10000000,CONTROLLER),('TTTECH_PMC_2026',100000000,PMC)]:
  for k,v in [('link_bps',rate),('full_duplex',True)]:proposals.setdefault('tt_'+k,[]).append(dict(when={'tt_review_profile':'PUBLIC_REFERENCE','tt_proposal_mode':'SOURCE_BASELINE','tt_device_profile':profile},value=v,source=src,source_revision=SOURCES[src]))
 out=build_fields(DECLARATIONS,['tt_'+k for k in REQUIRED],proposals)
 for f in out:
  if f['key']not in {'tt_'+k for k in REQUIRED}|{'tt_proposal_mode','tt_registered_source'}:f['schema_when']={'tt_review_profile':'PUBLIC_REFERENCE'}
 return out
