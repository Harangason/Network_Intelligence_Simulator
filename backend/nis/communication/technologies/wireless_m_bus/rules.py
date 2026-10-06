"""Wireless M-Bus edition/mode/direction and full framed radio accounting."""
from backend.nis.communication.services.native_review_support import declaration, fields as build_fields, WIRE_KEYS
TI='https://www.ti.com/lit/an/swra423/swra423.pdf'
PHY='https://docs.silabs.com/rail/3.0.0/rail-wmbus-apps-with-efr32/03-using-the-configurator'
LIMIT='https://docs.silabs.com/rail/3.0.0/rail-wmbus-apps-with-efr32/02-limitations'
OMS='https://oms-group.org/wp-content/uploads/2024/10/OMS-Spec_Vol2_Primary_v501_01.pdf'
CODE='https://raw.githubusercontent.com/SiliconLabs/gecko_sdk/v4.4.6/app/flex/component/rail/sl_wmbus_support/sl_wmbus_support.c'
HEADER='https://raw.githubusercontent.com/SiliconLabs/gecko_sdk/v4.4.6/app/flex/component/rail/sl_wmbus_support/sl_wmbus_support.h'
SAMPLE='https://raw.githubusercontent.com/SiliconLabs/gecko_sdk/v4.4.6/app/flex/example/rail/rail_soc_wmbus_meter/wmbus_sample_frame.c'
SOURCES={TI:'TI AN121 SWRA4232013 selected4/4.1 and originalrastertables29/31/33/35/38/40 read; EN13757-4:2012draft timing/radio scope, no currentregulatoryEIRPauthorization.',PHY:'SilabsRAIL3.0.0 originalconfigurator table S/T/C/R/F andNEN2019indexes/direction/frequency/coding; nominalradiochips distinctinformationalbitrate.',LIMIT:'SilabsRAIL3.0.0 originallimitations: Series1T M2O needssoftwarepostamble, Series2hardware, frameA/Bsyncselection notsimultaneouswithoutdecoder;TCperformanceuncharacterized.',OMS:'OMSVol2Issue5.0.1/2023-12 original143p selected3.1.3/4.3/5.2.2/7.2.2/7.2.4: FrameA DLL10/LexcludingCRCs/ELL/CCreserved and application/securitysource; notallEN13757 clauses.',CODE:'OriginalSilabsGeckoSDKv4.4.6 supportC selectedencoder/blockCRC/limitedaccess/crypto5/manufacturer; softwareimplementation scope.',HEADER:'OriginalSilabsGeckoSDKv4.4.6 supportH selectedDLL/STL/LTL/configword/access/typedef widths; not allOMScompliance.',SAMPLE:'OriginalSilabsGeckoSDKv4.4.6 sample frameC setupDLLHeader L excludesLbyte;FrameAexcludeCRC,FrameB+2below125body/+4otherwise; illustrative sample notdevice defaults.'}
DECLARATIONS=[]
def d(k,t,m,s=PHY,**kw):DECLARATIONS.append(declaration('wm_',k,t,m,s,SOURCES[s],**kw))
for k,m,o,s in [('mode','Actual WirelessM-Bus mode, distinctwiredM-Bus.',['S1','S1M','S2','T1','T2','C1','C2','R2','N1','N2','F1','F2','REGISTERED_ACTUAL'],PHY),('direction','Actualmeter→other versusother→meter changesPHY.',['METER_TO_OTHER','OTHER_TO_METER'],PHY),('edition','Actualpublicqualifiededition; no blending2012draftandEN2019/OMS.',['RAIL3_EN2019','TI_AN121_2012_DRAFT','OMS5_0_1','REGISTERED_ACTUAL'],PHY),('frame','ActualframeA/B versusindependentOMS LPWANframeC.',['A','B','C_REGISTERED'],OMS),('coding','Actual Manchester/3of6/NRZ; 100kchips is notall100kapplicationdata.',['MANCHESTER','THREE_OF_SIX','NRZ','REGISTERED_ACTUAL'],TI),('hardware','Actual siliconcapability/implementation, includingpostambleworkaround.',['EFR32_SERIES1','EFR32_SERIES2','REGISTERED_ACTUAL'],LIMIT),('response_mode','ActualELLfast/slowresponse distinctfromapplicationdeadline.',['FAST','SLOW','REGISTERED_ACTUAL'],TI),('outcome','Actualindependent functionresult.',['ACCEPTED','RADIO_FRAME_ONLY','CRC_ONLY','ERROR','UNKNOWN'],OMS)]:d(k,'select',m,s,options=o)
for k,m,lo,hi,u,integ,s in [('chip_rate_cps','Actual selectedradio chip/symbol rate excludinglinecode.',1,None,'chip/s',False,TI),('data_bps','Actualinformationbitrate afterlinecode, notUART115200hostrate.',1,None,'bit/s',False,TI),('centre_mhz','Actualmode/direction/channel frequency withregulatoryapproval.',0,None,'MHz',False,PHY),('n_index','ActualEN2019 Nmodeconfiguration index, notoldlettername.',1,13,None,True,PHY),('channel','ActualNindexchannelnumber.',0,57,None,True,PHY),('spacing_khz','ActualNchannelspacing.',0,None,'kHz',False,PHY),('symbol_bits','Actualmodulationsymbolinformationbits,4GFSK2not1.',1,2,None,True,TI),('preamble_chips','Actualpreambleincluding sync forS/T/R versusseparateC/N.',0,None,'chip',True,TI),('sync_chips','Actualseparatesync lengthC/N; notdoublecountS/T/R.',0,None,'chip',True,TI),('postamble_chips','Actualselectedencodedtrailer, noTmissingpostamble.',0,8,'chip',True,TI),('response_ms','Actualreceive-ready/response interval fromselectededitionreference.',0,None,'ms',False,TI),('fac_n','ActualfrequentaccessrepeatN selectedallowedset.',1,13,None,True,TI),('fac_ms','ActualrepeatN*1000 interval, notdefault100msapplicationcycle.',0,None,'ms',False,TI),('fac_timeout_s','Actualfrequentaccess timeout.',0,None,'s',False,TI),('l_field','Actual8bitlengthencoding,FrameBcountsCRCwhileAnot.',0,255,None,True,SAMPLE),('datagram_bytes','ActualDLL+ELL+TPL+encrypteddata excludingCRC.',10,256,'byte',True,CODE),('crc_blocks','ActualframeAfirst10/rest16blocks orFrameB1/2.',1,17,None,True,CODE),('crc_bytes','Actual2byteCRCperblock.',2,34,'byte',True,CODE),('radio_bytes','ActualCRCprotectedframe bytes excludingpreamble/postamble.',12,290,'byte',True,CODE),('encoded_chips','Actuallinecodeddata+CRCs plusdefinedsync/preamble/trailer.',0,None,'chip',True,CODE),('nominal_air_us','Nominalencodedchips/radiochiprate; noMACcontention/host/hardwareproof.',0,None,'us',False,TI),('dll_bytes','ActualFrameA10byteDLLexcludingCRC.',0,None,'byte',True,OMS),('ell_bytes','ActualELL selectedshort/long, notautoomitforC.',0,None,'byte',True,OMS),('tpl_bytes','ActualCI+short/long transportheader.',0,None,'byte',True,HEADER),('application_bytes','Actualserializedapplicationbytes beforepadding/authentication.',0,None,'byte',True,OMS),('security_bytes','Actualcipherpadding/AFL/tagoverhead selectedsecuritymode.',0,None,'byte',True,OMS),('cc_raw','ActualELLCCBDSH0AR0 byte; reservedbitszero.',0,255,None,True,OMS),('access_number','Actual8bitdatagramaccesscounter/nonce source, notrandomdefault0.',0,255,None,True,OMS),('source_ms','Actualproducer/cipher/radiodriver delay.',0,None,'ms',False,OMS),('transport_ms','Actualradio/access/retry/window/forwardbound.',0,None,'ms',False,OMS),('use_ms','Actualconsumerdelay.',0,None,'ms',False,OMS),('e2e_ms','Actualsource-to-usebound independent CRC/responsewindow.',0,None,'ms',False,OMS),('deadline_ms','Independent functiondeadline.',0,None,'ms',False,OMS),('age_ms','Actualconsumeddataage.',0,None,'ms',False,OMS),('freshness_ms','Independent allowableage.',0,None,'ms',False,OMS)]:d(k,'number',m,s,min=lo,max=hi,unit=u,integer=integ)
for k,m,s in [('software_postamble','ActualSeries1Tencoderworkaroundcomplete.',LIMIT),('postamble_verified','ActualT M2Otrailerssourcecomplete.',LIMIT),('frame_decoder_verified','ActualselectedframeA/Bdecoder, secondsync detectaloneinsufficient.',LIMIT),('security_verified','Actualsecuritymode/key/counter/replay/peerconfiguration evidence.',OMS),('path_verified','Actualcomplete radio/access/hostpathevidence.',OMS),('data_accepted','Actualfreshindependent consumingfunctionsucceeds.',OMS)]:d(k,'boolean',m,s)
for k,m,s in [('revision','Actualstandards/device/stackedition.',PHY),('device_source','Actualpeer/transceiver/decoderbuffercapability.',LIMIT),('radio_source','ActualPHY/mode/direction/frameconfiguration.',PHY),('regulatory_source','Actualregion/channel/EIRP/dutycycleauthorization;2013table notcurrentlaw.',TI),('schedule_source','Actualresponse/reference/access/retry/hostpathbound.',TI),('acceptance_source','Actualindependent deadline/age/errorcontract.',OMS),('registered_source','ActualindependentqualifiedframeC/otherindex/standardedition.',OMS),('postamble_source','Actualtrailerimplementation/measurement.',LIMIT),('decoder_source','Actualselectedsync/frameCRC/softwaredecoder.',LIMIT),('security_source','Actualprotectedkey/IV/access/replayassessment; no keyinline.',OMS),('observation_source','Actualcorrelatedproducer/radio/window/consumertrace.',OMS)]:d(k,'text',m,s)
REQUIRED=('revision','device_source','radio_source','regulatory_source','schedule_source','acceptance_source')
REMOVED={k:'WirelessM-Bus mode/direction/chipcoding/frameCRC/OMSsecurity/access evidence explicit; noCAN/gateway or100k/255application default.'for k in WIRE_KEYS}
MODES={'S1':('MANCHESTER',32768,868.3),'S1M':('MANCHESTER',32768,868.3),'S2':('MANCHESTER',32768,868.3),'T1':('THREE_OF_SIX',100000,868.95),'T2':('THREE_OF_SIX',100000,868.95),'C1':('NRZ',100000,868.95),'C2':('NRZ',100000,868.95),'R2':('MANCHESTER',4800,868.33),'F1':('NRZ',2400,433.82),'F2':('NRZ',2400,433.82)}
NINDEX={1:(2400,169.40625,12.5,5),2:(4800,169.40625,12.5,5),3:(6400,169.41,12.5,5),4:(19200,169.4375,50,0),5:(2400,169.48125,12.5,0),6:(4800,169.48125,12.5,0),7:(2400,169.49375,12.5,7),8:(4800,169.49375,12.5,7),9:(6400,169.41,12.5,57),10:(2400,169.59375,12.5,17),11:(4800,169.59375,12.5,17),13:(19200,169.625,50,3)}
def semantics():
 rules=[]
 def r(k,w=None,s=PHY,**kw):rules.append(dict(parameter='wm_'+k,when={'wm_'+a:b for a,b in(w or{}).items()},source=s,**kw))
 rules.extend(dict(parameter=k,when={},allowed=[],source=PHY)for k in REMOVED)
 for selector in('mode','edition','hardware','response_mode'):r('registered_source',{selector:'REGISTERED_ACTUAL'},required=True)
 r('registered_source',{'frame':'C_REGISTERED'},required=True,s=OMS)
 for mode in('S1','S1M','T1','C1','N1','F1'):r('direction',{'mode':mode},allowed=['METER_TO_OTHER'])
 for mode,(coding,rate,freq)in MODES.items():
  for direction in('METER_TO_OTHER','OTHER_TO_METER'):
   selected=(coding,rate,freq)
   if mode=='T2'and direction=='OTHER_TO_METER':selected=('MANCHESTER',32768,868.3)
   if mode=='C2'and direction=='OTHER_TO_METER':selected=('NRZ',50000,869.525)
   if mode=='R2'and direction=='METER_TO_OTHER':
    r('coding',{'mode':mode,'direction':direction},allowed=['MANCHESTER']);continue
   w={'mode':mode,'direction':direction};r('coding',w,allowed=[selected[0]]);r('centre_mhz',w,allowed=[selected[2]])
 for coding,factor in [('MANCHESTER',.5),('THREE_OF_SIX',2/3)]:r('data_bps',{'coding':coding},equal_expression={'product':['wm_chip_rate_cps',factor]},s=TI)
 r('data_bps',{'coding':'NRZ'},equal_expression={'product':['wm_chip_rate_cps','wm_symbol_bits']},s=TI)
 for mode in('N1','N2'):
  r('n_index',{'mode':mode},allowed=list(NINDEX))
  for index,(bps,freq,spacing,last)in NINDEX.items():
   w={'mode':mode,'n_index':index};r('data_bps',w,allowed=[bps]);r('symbol_bits',w,allowed=[2 if bps==19200 else 1]);r('coding',w,allowed=['NRZ']);r('channel',w,maximum=last);r('spacing_khz',w,allowed=[spacing]);r('centre_mhz',w,equal_expression={'sum':[freq,{'product':['wm_channel',spacing*.001]}]})
   if bps==6400:r('hardware',w,allowed=['EFR32_SERIES2','REGISTERED_ACTUAL'])
 r('software_postamble',{'hardware':'EFR32_SERIES1','coding':'THREE_OF_SIX','direction':'METER_TO_OTHER'},required=True,allowed=[True],s=LIMIT)
 r('postamble_source',{'postamble_verified':True},required=True,s=LIMIT);r('decoder_source',{'frame_decoder_verified':True},required=True,s=LIMIT);r('security_source',{'security_verified':True},required=True,s=OMS)
 r('datagram_bytes',{'frame':'B'},maximum=252,s=SAMPLE)
 r('dll_bytes',{'frame':'A'},allowed=[10],s=OMS)
 r('datagram_bytes',equal_expression={'sum':['wm_dll_bytes','wm_ell_bytes','wm_tpl_bytes','wm_application_bytes','wm_security_bytes']},s=OMS)
 r('application_bytes',equal_parameter='payload_bytes',s=OMS)
 r('l_field',{'frame':'A'},equal_expression={'subtract':['wm_datagram_bytes',1]},s=SAMPLE)
 r('crc_blocks',{'frame':'A'},equal_expression={'sum':[1,{'ceiling':[{'product':[{'maximum':[0,{'subtract':['wm_datagram_bytes',10]}]},1/16]}]}]},s=CODE)
 r('crc_bytes',equal_expression={'product':['wm_crc_blocks',2]},s=CODE);r('radio_bytes',equal_expression={'sum':['wm_datagram_bytes','wm_crc_bytes']},s=CODE)
 for lo,hi,crc in[(10,125,1),(126,252,2)]:r('crc_blocks',{'frame':'B'},when_ranges={'wm_datagram_bytes':[lo,hi]},allowed=[crc],s=SAMPLE)
 r('l_field',{'frame':'B'},equal_expression={'subtract':['wm_radio_bytes',1]},s=SAMPLE);r('crc_blocks',{'frame':'B'},maximum=2,s=TI)
 for coding,factor in [('MANCHESTER',16),('THREE_OF_SIX',12)]:r('encoded_chips',{'coding':coding},equal_expression={'sum':[{'product':['wm_radio_bytes',factor]},'wm_preamble_chips','wm_sync_chips','wm_postamble_chips']},s=CODE)
 for bits in(1,2):r('encoded_chips',{'coding':'NRZ','symbol_bits':bits},equal_expression={'sum':[{'product':['wm_radio_bytes',8/bits]},'wm_preamble_chips','wm_sync_chips','wm_postamble_chips']},s=CODE)
 r('nominal_air_us',equal_ratio={'numerator_parameter':'wm_encoded_chips','denominator_parameter':'wm_chip_rate_cps','factor':1000000},s=TI)
 r('cc_raw',{'edition':'OMS5_0_1'},forbidden_bit_mask=9,s=OMS)
 for mode in('S2','T2','C2','R2','F2'):r('fac_n',{'edition':'TI_AN121_2012_DRAFT','mode':mode},allowed=[2,3,5]if mode in('S2','T2','C2')else[5,7,13],s=TI)
 r('data_bps',{'edition':'TI_AN121_2012_DRAFT','mode':'N2'},when_present=['wm_fac_n'],required=True,s=TI)
 for bps in(2400,4800,19200):r('fac_n',{'edition':'TI_AN121_2012_DRAFT','mode':'N2','data_bps':bps},allowed=[2,3,5]if bps==19200 else[5,7,13],s=TI)
 r('fac_ms',{'edition':'TI_AN121_2012_DRAFT'},equal_expression={'product':['wm_fac_n',1000]},s=TI);r('fac_timeout_s',{'edition':'TI_AN121_2012_DRAFT'},minimum=25,maximum=30,s=TI)
 r('response_ms',{'edition':'TI_AN121_2012_DRAFT','mode':'T2','direction':'OTHER_TO_METER'},minimum=2,maximum=3,s=TI)
 for mode in('C2','N2','F2'):r('response_ms',{'edition':'TI_AN121_2012_DRAFT','mode':mode,'direction':'OTHER_TO_METER','response_mode':'FAST'},minimum=99.5,maximum=100.5,s=TI)
 for mode in('C1','C2','F1','F2'):r('symbol_bits',{'mode':mode},allowed=[1],s=TI)
 for mode in('S1','S1M','S2','T1','T2','R2'):
  w={'edition':'TI_AN121_2012_DRAFT','mode':mode};r('preamble_chips',w,minimum=576 if mode=='S1' else 96 if mode=='R2' else 48,s=TI);r('sync_chips',w,allowed=[0],s=TI);r('postamble_chips',w,minimum=2,maximum=8,s=TI)
 for mode in('C1','C2','N1','N2'):
  w={'edition':'TI_AN121_2012_DRAFT','mode':mode};r('preamble_chips',w,allowed=[32 if mode.startswith('C') else 16],s=TI);r('sync_chips',w,allowed=[32 if mode.startswith('C') else 16],s=TI)
 for mode in('S2','R2'):r('response_ms',{'edition':'TI_AN121_2012_DRAFT','mode':mode,'direction':'OTHER_TO_METER'},minimum=3,maximum=50,s=TI)
 for mode in('C2','F2'):r('response_ms',{'edition':'TI_AN121_2012_DRAFT','mode':mode,'direction':'OTHER_TO_METER','response_mode':'SLOW'},minimum=999.5,maximum=1000.5,s=TI)
 for bps,lo in [(2400,2099.5),(4800,1099.5),(19200,1099.5)]:r('response_ms',{'edition':'TI_AN121_2012_DRAFT','mode':'N2','direction':'OTHER_TO_METER','response_mode':'SLOW','data_bps':bps},minimum=lo,maximum=lo+1,s=TI)
 r('e2e_ms',equal_expression={'sum':['wm_source_ms','wm_transport_ms','wm_use_ms']},maximum_parameter='wm_deadline_ms',s=OMS);r('age_ms',maximum_parameter='wm_freshness_ms',s=OMS)
 for k in('source_ms','transport_ms','use_ms'):r(k,when_present=['wm_e2e_ms'],required=True,s=OMS)
 for k in('e2e_ms','deadline_ms','age_ms','freshness_ms','observation_source'):r(k,{'data_accepted':True},required=True,s=OMS)
 r('path_verified',{'data_accepted':True},required=True,allowed=[True],s=OMS);r('outcome',{'data_accepted':True},required=True,allowed=['ACCEPTED'],s=OMS)
 return dict(rate_model={'type':'WIRELESS_MBUS_SELECTED_MODE_DIRECTION','fields':[]},parameter_evidence_scope='EXPLICIT_LAYER',required_parameters=['wm_'+k for k in REQUIRED],native_parameter_prefixes=['wm_'],parameter_constraints=rules,medium_access_model='WIRELESS_MBUS_ACTUAL_ACCESSIBILITY',arbitration_model_id='MODE_DIRECTION_ELL_ACCESS_WINDOWS',mechanisms={'network':['CHIPRATE_NOT_APPLICATION_RATE','FRAME_CRC_AND_LINECODE_COMPLETE'],'timing':['SELECTED_EDITION_RESPONSE_AND_HOST_PATH']})
def fields():
 p={}
 def v(k,val,w,s=PHY):p.setdefault('wm_'+k,[]).append(dict(when={'wm_'+a:b for a,b in w.items()},value=val,source=s,source_revision=SOURCES[s]))
 for mode,(coding,rate,freq)in MODES.items():
  v('coding',coding,{'mode':mode,'direction':'METER_TO_OTHER'});v('chip_rate_cps',rate,{'mode':mode,'direction':'METER_TO_OTHER'})
  if mode!='R2':v('centre_mhz',freq,{'mode':mode,'direction':'METER_TO_OTHER'})
  v('symbol_bits',1,{'mode':mode},TI)
 for mode in('N1','N2'):
  v('n_index',1,{'edition':'RAIL3_EN2019','mode':mode})
  for index,(bps,freq,spacing,last)in NINDEX.items():
   v('coding','NRZ',{'mode':mode,'n_index':index});v('symbol_bits',2 if bps==19200 else 1,{'mode':mode,'n_index':index},TI);v('chip_rate_cps',bps/2 if bps==19200 else bps,{'mode':mode,'n_index':index});v('data_bps',bps,{'mode':mode,'n_index':index})
 for mode,coding,rate,freq in [('T2','MANCHESTER',32768,868.3),('C2','NRZ',50000,869.525)]:
  for k,val in [('coding',coding),('chip_rate_cps',rate),('centre_mhz',freq)]:v(k,val,{'mode':mode,'direction':'OTHER_TO_METER'})
 for mode in('C2','N2','F2'):v('response_mode','FAST',{'edition':'TI_AN121_2012_DRAFT','mode':mode},TI);v('response_ms',100,{'edition':'TI_AN121_2012_DRAFT','mode':mode,'response_mode':'FAST','direction':'OTHER_TO_METER'},TI)
 return build_fields(DECLARATIONS,['wm_'+k for k in REQUIRED],p)
