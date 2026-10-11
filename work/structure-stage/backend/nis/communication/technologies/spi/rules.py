"""Device-qualified SPI modes, selected controllers and total transaction envelope."""
from math import isfinite
from backend.nis.communication.services.native_review_support import declaration, fields as build_fields, WIRE_KEYS
NXP='https://www.nxp.com/docs/en/application-note/AN3020.pdf'
PIC32='https://ww1.microchip.com/downloads/en/DeviceDoc/61132B.pdf'
SOURCES={NXP:'Freescale AN3020 Rev0 September2005, printed1-3,7-8,12-14 device packet/FIFO/clock/drive/ready examples, not universal SPI defaults.',PIC32:'Microchip original PIC32MX family reference compilation; selected DS61106E2008 section23 printed23-2,23-7/8,23-20/21,23-33/35/36 read. Device-data-sheet electrical limits still required.'}
DECLARATIONS=[]
def d(k,t,meaning,source=NXP,**kw):DECLARATIONS.append(declaration('spi_',k,t,meaning,source,SOURCES[source],**kw))
for k,meaning,opts in[
 ('controller_profile','Actual controller implementation, no universal byte count or50MHz capability.',['REGISTERED_DEVICE','PIC32MX_DS61106E','IMX1_AN3020']),
 ('bus_variant','Actual single-data SPI versus separately qualified dual/quad memory phases.',['SPI_SINGLE','REGISTERED_DUAL_QUAD']),
 ('role','Actual clock-owning controller versus selected target.',['CONTROLLER','TARGET']),
 ('duplex','Actual simultaneous TX/RX versus shared half-duplex data line.',['FULL_DUPLEX','HALF_DUPLEX']),
 ('bit_order','Actual matched data bit order, PIC32MX shifts most significant bit first.',['MSB_FIRST','LSB_FIRST']),
 ('sample_edge','Actual data sampling rising/falling edge matched across endpoints.',['RISING','FALLING']),
 ('change_edge','Actual data change edge distinct from sampling edge.',['RISING','FALLING']),
 ('cs_polarity','Actual chip-select active polarity, no universal reset/active-low evidence.',['ACTIVE_LOW','ACTIVE_HIGH']),
 ('select_kind','Actual selection per transaction, daisy-chain or externally bound framed sync.',['CHIP_SELECT','DAISY_CHAIN','FRAMED']),
 ('outcome','Actual independent decoding and consuming application result.',['ACCEPTED','OVERFLOW','UNDERRUN','MODE_MISMATCH','MISSING','STALE','UNKNOWN']),
]:d(k,'select',meaning,options=opts)
for k,meaning,lo,hi,unit,integer in[
 ('mode','Actual mode=2*CPOL+CPHA, not guessed defaultmode0.',0,3,None,True),
 ('cpol','Actual idle clock level0/1, separate phase.',0,1,None,True),('cpha','Actual first/second edge sample phase0/1.',0,1,None,True),
 ('word_bits','Actual controller and target word length, PIC32MX8/16/32 but other parts differ.',1,None,'bit',True),
 ('words','Actual transfer word count; dummy/address/command phases included separately.',0,None,None,True),
 ('transfer_clock_bits','Actual whole transaction clock pulses across all phases, not TXbytes+RXbytes for simultaneous full duplex.',0,None,'bit',True),
 ('command_bits','Actual command phase bits, independent device framing.',0,None,'bit',True),
 ('address_bits','Actual address phase bits, not an I2C slave address.',0,None,'bit',True),
 ('dummy_bits','Actual dummy/wait phase clock bits.',0,None,'bit',True),
 ('data_bits','Actual data-phase clock bits including selected word packing.',0,None,'bit',True),
 ('tx_bits','Actual simultaneously clocked transmit data bits, not sum withreceive for full duplex.',0,None,'bit',True),
 ('rx_bits','Actual receive data bits clocked by same SCK in full duplex.',0,None,'bit',True),
 ('controller_max_bps','Actual qualified SCK controller maximum under clock/pad/voltage/temp conditions.',1,None,'bit/s',False),
 ('target_max_bps','Actual selected target SCK maximum under actual mode/voltage/temp/load.',1,None,'bit/s',False),
 ('physical_max_bps','Actual PCB/pad/trace/loading/edge-qualified maximum.',1,None,'bit/s',False),
 ('period_ns','Actual selected SCK period1e9/bitrate_bps.',0,None,'ns',False),
 ('high_ns','Actual stable clock HIGH duration, device-qualified minimum.',0,None,'ns',False),
 ('low_ns','Actual stable clock LOW duration, device-qualified minimum.',0,None,'ns',False),
 ('rise_ns','Actual SCK transition rise time included in full period.',0,None,'ns',False),
 ('fall_ns','Actual SCK transition fall time included in full period.',0,None,'ns',False),
 ('minimum_high_ns','Actual target/controller qualified minimum HIGH.',0,None,'ns',False),
 ('minimum_low_ns','Actual target/controller qualified minimum LOW.',0,None,'ns',False),
 ('data_setup_ns','Actual received data stable before sampling edge.',0,None,'ns',False),
 ('minimum_setup_ns','Actual receiver setup requirement including skew/load/temp.',0,None,'ns',False),
 ('data_hold_ns','Actual data stable after sampling edge.',0,None,'ns',False),
 ('minimum_hold_ns','Actual receiver hold requirement.',0,None,'ns',False),
 ('cs_setup_ns','Actual chip-select setup before first relevant clock.',0,None,'ns',False),
 ('minimum_cs_setup_ns','Actual target chip-select setup requirement.',0,None,'ns',False),
 ('cs_hold_ns','Actual chip-select hold after last relevant clock.',0,None,'ns',False),
 ('minimum_cs_hold_ns','Actual target chip-select hold requirement.',0,None,'ns',False),
 ('cs_inactive_ns','Actual deselected interval between transactions.',0,None,'ns',False),
 ('minimum_cs_inactive_ns','Actual target minimum deselected/recovery interval.',0,None,'ns',False),
 ('output_valid_ns','Actual remote output valid worst-case after launch edge.',0,None,'ns',False),
 ('path_delay_ns','Actual combined clock/data propagation delay for selected sampling direction.',0,None,'ns',False),
 ('sample_window_ns','Actual launch-to-sample window for selected phase/controller, not alwayshalfperiod.',0,None,'ns',False),
 ('jitter_ns','Actual worst sampling/launch edge uncertainty.',0,None,'ns',False),
 ('serialized_us','Actual clock serialization totalbits/actualclock only.',0,None,'us',False),
 ('setup_bound_us','Actual whole transaction preclock setup upper bound.',0,None,'us',False),
 ('hold_bound_us','Actual postclock hold upper bound.',0,None,'us',False),
 ('gap_bound_us','Actual total intra-transaction/gap/ready wait bound, not just nominalonegap.',0,None,'us',False),
 ('transaction_bound_us','Actual clock plus setup/hold/allgaps upper envelope, separate application scheduling.',0,None,'us',False),
 ('ready_wait_us','Actual asynchronous device-ready wait bound; source600ns example is not bound.',0,None,'us',False),
 ('peripheral_clock_bps','Actual selected PIC32PBCLK, not CPU clock by default.',1,None,'bit/s',False),
 ('brg','Actual9bit PIC32 baud divider register0..511, not raw divider.',0,511,None,True),
 ('pic32_ckp','Actual PIC32CKP clock idle setting matches CPOL.',0,1,None,True),
 ('pic32_cke','Actual PIC32 output-edge select; normalmode CKE=1-CPHA, framedmust0.',0,1,None,True),
 ('pic32_smp','Actual PIC32 input sample middle/end setting, targetalways0.',0,1,None,True),
 ('imx_pclk_div','Actual i.MX1 programmable clock divider1..16.',1,16,None,True),
 ('imx_spi_div','Actual i.MX1 programmable SCK divide4,8,..512.',4,512,None,True),
 ('imx_pll_bps','Actual source i.MX1PLL, source96MHzexample notglobaldefault.',1,96000000,'bit/s',False),
 ('selected_targets','Actual enabled outputs in ordinary single-CS transaction, no CANarbitration.',0,None,None,True),
 ('source_bound_ms','Actual source/task/acquisition/serializer bound.',0,None,'ms',False),
 ('busy_bound_ms','Actual controller queue/transaction/retry/scheduling bound.',0,None,'ms',False),
 ('consumer_bound_ms','Actual decode/application consumption bound.',0,None,'ms',False),
 ('e2e_bound_ms','Actual complete source/busy/consumer sum.',0,None,'ms',False),
 ('e2e_limit_ms','Actual independent functional deadline.',0,None,'ms',False),
 ('age_ms','Actual correlated consuming sample age.',0,None,'ms',False),('freshness_ms','Actual independent allowed age.',0,None,'ms',False),
]:d(k,'number',meaning,min=lo,max=hi,unit=unit,integer=integer,source=PIC32 if k.startswith('pic32')or k in('brg','peripheral_clock_bps')else NXP)
for k,meaning in[
 ('ready_enabled','Actual device READY/handshake enabled and allocated.'),('framed','Actual controller framed sync mode versus ordinarychipselect.'),
 ('changing_width','Actual word width change requested.'),('idle','Actual module idle when changing word width.'),
 ('peer_mode_verified','Actual matching mode/word/order/duplex across controller and target.'),('physical_verified','Actual electrical/edge/pin/selected-target physical qualification.'),
 ('tri_state_verified','Actual unselected target output isolation prevents shared MISO contention.'),
 ('codec_verified','Actual command/address/dummy/register/CRC/application data encoding verified.'),('data_accepted','Actual independent application acceptance.')]:d(k,'boolean',meaning)
for k,meaning in[
 ('controller_id','Actual canonical controller identity.'),('target_id','Actual canonical selected target identity.'),('chip_select','Actual canonical target selection or explicit framed binding.'),
 ('device_source','Actual controller/target datasheet revisions and firmware configuration.'),('binding_source','Actual pins/word/duplex/select/canonical endpoint binding.'),
 ('physical_source','Actual voltage/current/drive/load/layout/edge timing evidence.'),('codec_source','Actual per-device command/address/dummy/CRC/data serializer.'),
 ('schedule_source','Actual transfer/queue/retry/ready/CS/interrupt/DMA whole busy bound.'),('acceptance_source','Actual functional timing/data-age requirements.'),
 ('observation_source','Actual correlated clock/select/data/task/consumer observation.')]:d(k,'text',meaning)
REQUIRED=('controller_profile','bus_variant','role','device_source','binding_source','physical_source','codec_source','schedule_source','acceptance_source')
REMOVED={k:'SPI has device clock and target selection, no implicit CAN/Ethernet retry/gatewaycapacity.'for k in WIRE_KEYS if k!='bitrate'}

def semantics():
 rules=[]
 def r(k,w=None,**kw):rules.append(dict(parameter='spi_'+k,when={'spi_'+a:b for a,b in(w or{}).items()},source=NXP,source_revision=SOURCES[NXP],**kw))
 # The existing executor proves only a confirmed conservative transaction
 # envelope. An explicitly selected native controller profile starts the
 # separate complete controller/PHY/configuration review; never invent it
 # from the clock or erase an independently valid limited transaction bound.
 for declaration in DECLARATIONS:r('controller_profile',when_present=[declaration['key']],required=True)
 for k in REQUIRED:r(k,when_present=['spi_controller_profile'],required=True)
 r('mode',equal_expression={'sum':[{'product':[2,'spi_cpol']},'spi_cpha']})
 for mode,pol,pha,sample in [(0,0,0,'RISING'),(1,0,1,'FALLING'),(2,1,0,'FALLING'),(3,1,1,'RISING')]:
  r('cpol',{'mode':mode},allowed=[pol]);r('cpha',{'mode':mode},allowed=[pha]);r('sample_edge',{'mode':mode},allowed=[sample]);r('change_edge',{'mode':mode},allowed=['FALLING'if sample=='RISING'else'RISING'])
 for k in('controller_max_bps','target_max_bps','physical_max_bps'):rules.append(dict(parameter='bitrate_bps',maximum_parameter='spi_'+k,source=NXP))
 r('period_ns',equal_ratio={'numerator_offset':1,'denominator_parameter':'bitrate_bps','factor':1e9})
 r('period_ns',minimum_expression={'sum':['spi_high_ns','spi_low_ns','spi_rise_ns','spi_fall_ns']})
 for k,bound in [('high_ns','minimum_high_ns'),('low_ns','minimum_low_ns'),('data_setup_ns','minimum_setup_ns'),('data_hold_ns','minimum_hold_ns'),('cs_setup_ns','minimum_cs_setup_ns'),('cs_hold_ns','minimum_cs_hold_ns'),('cs_inactive_ns','minimum_cs_inactive_ns')]:r(k,minimum_expression='spi_'+bound)
 r('sample_window_ns',minimum_expression={'sum':['spi_output_valid_ns','spi_path_delay_ns','spi_minimum_setup_ns','spi_jitter_ns']})
 r('data_bits',equal_expression={'product':['spi_word_bits','spi_words']})
 r('transfer_clock_bits',equal_expression={'sum':['spi_command_bits','spi_address_bits','spi_dummy_bits','spi_data_bits']})
 for k in('tx_bits','rx_bits'):r(k,{'duplex':'FULL_DUPLEX'},maximum_parameter='spi_data_bits')
 r('data_bits',{'duplex':'HALF_DUPLEX'},minimum_expression={'sum':['spi_tx_bits','spi_rx_bits']})
 r('serialized_us',equal_ratio={'numerator_parameter':'spi_transfer_clock_bits','denominator_parameter':'bitrate_bps','factor':1e6})
 r('transaction_bound_us',minimum_expression={'sum':['spi_serialized_us','spi_setup_bound_us','spi_hold_bound_us','spi_gap_bound_us']})
 for k in('serialized_us','setup_bound_us','hold_bound_us','gap_bound_us'):r(k,when_present=['spi_transaction_bound_us'],required=True)
 r('ready_wait_us',{'ready_enabled':True},required=True);r('gap_bound_us',{'ready_enabled':True},minimum_expression='spi_ready_wait_us')
 w={'controller_profile':'PIC32MX_DS61106E'}
 r('word_bits',w,allowed=[8,16,32]);r('bit_order',w,allowed=['MSB_FIRST']);r('pic32_ckp',w,equal_parameter='spi_cpol')
 r('pic32_cke',{**w,'framed':False},equal_expression={'subtract':[1,'spi_cpha']});r('pic32_cke',{**w,'framed':True},allowed=[0])
 r('pic32_smp',{**w,'role':'TARGET'},allowed=[0]);r('idle',{**w,'changing_width':True},required=True,allowed=[True])
 rules.append(dict(parameter='bitrate_bps',when={'spi_controller_profile':'PIC32MX_DS61106E','spi_role':'CONTROLLER'},equal_ratio={'numerator_parameter':'spi_peripheral_clock_bps','denominator_sum':['spi_brg'],'denominator_offset':1,'factor':.5},source=PIC32))
 r('imx_spi_div',{'controller_profile':'IMX1_AN3020'},allowed=[4,8,16,32,64,128,256,512])
 rules.append(dict(parameter='bitrate_bps',when={'spi_controller_profile':'IMX1_AN3020','spi_role':'CONTROLLER'},equal_ratio={'numerator_parameter':'spi_imx_pll_bps','denominator_offset':1,'denominator_product':['spi_imx_pclk_div','spi_imx_spi_div']},source=NXP))
 r('selected_targets',{'select_kind':'CHIP_SELECT'},allowed=[1])
 chain=('source_bound_ms','busy_bound_ms','consumer_bound_ms');r('e2e_bound_ms',equal_expression={'sum':['spi_'+k for k in chain]})
 for k in chain:r(k,when_present=['spi_e2e_bound_ms'],required=True)
 r('e2e_bound_ms',maximum_parameter='spi_e2e_limit_ms');r('age_ms',maximum_parameter='spi_freshness_ms')
 w={'data_accepted':True}
 for k,v in [('peer_mode_verified',True),('physical_verified',True),('tri_state_verified',True),('codec_verified',True),('outcome','ACCEPTED')]:r(k,w,required=True,allowed=[v])
 for k in('controller_id','target_id','chip_select','mode','cpol','cpha','word_bits','bit_order','duplex','cs_polarity','select_kind','controller_max_bps','target_max_bps','physical_max_bps','observation_source','transaction_bound_us','e2e_bound_ms','e2e_limit_ms','age_ms','freshness_ms'):r(k,w,required=True)
 return dict(rate_model={'type':'DEVICE_DEPENDENT_CLOCK','fields':['bitrate_bps'],'minimum_bps':1},required_parameters=[],native_parameter_prefixes=['spi_'],parameter_constraints=rules,physical_layer_profile_id='actual_spi_voltage_pins_and_layout',medium_access_model='CONTROLLER_SELECTED_TRANSACTION',arbitration_model_id='ACTUAL_CONTROLLER_TASK_AND_CS',mechanisms={'selection':['CHIP_SELECT_OR_REGISTERED_FRAME'],'clocking':['MATCHED_CPOL_CPHA','DEVICE_QUALIFIED_CLOCK'],'realization':['FULL_DUPLEX_SHARED_CLOCK','NO_UNIVERSAL_SPI_CLOCK_OR_WORD_SIZE'],'qualification':['DEVICE_CONFIRMED_WHOLE_BUSY_BOUND','FUNCTIONAL_ACCEPTANCE_SEPARATE']})

def fields():
 out=build_fields(DECLARATIONS,[])
 for item in out:
  if item['key'] in {'spi_'+k for k in REQUIRED}:
   item['required_when']={'spi_controller_profile':['REGISTERED_DEVICE','PIC32MX_DS61106E','IMX1_AN3020']}
 return out

LOCAL=[('master_node_id','text',None,None,None,'Actual confirmed canonical clock owner, not assigned ECU.'),('chip_select','text',None,None,None,'Actual selected targetCS binding.'),('word_length_bits','number',1,None,'bit','Actual positive integer word length qualified bydevice.'),('duplex_mode','select',None,None,None,'Actual full/halfduplex singleSPI transfer, no dualquad inference.'),('cpol','number',0,1,None,'Actual integer idlelevel0/1.'),('cpha','number',0,1,None,'Actual integer samplingphase0/1.'),('cs_setup_bound_us','number',0,None,'us','Actual total transactionpreclock guard upperbound.'),('inter_transfer_gap_us','number',0,None,'us','Actual summed nonclockwait/hold/gap upperbound, notnominalminimum.'),('transfer_bits_bound','number',0,None,'bit','Actual whole transaction clock pulse upperbound includingcommand/address/dummy/packing.'),('bitrate_bps','number',1,None,'bit/s','Actual qualifiedclock for selected controller/target/PCB.'),('source','text',None,None,None,'Actual device/transaction trace or datasheet source.'),('confirmed','boolean',None,None,None,'Explicit confirmation of whole-device transaction proof, never a nominalclock default.')]
def local_fields():
 out=[]
 for k,t,lo,hi,unit,meaning in LOCAL:
  v=dict(key=k,label=k.replace('_',' '),type=t,numeric=t=='number',boolean=t=='boolean',optional=False,minimum=lo,maximum=hi,unit=unit,integer=k in('word_length_bits','cpol','cpha','transfer_bits_bound'),parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',scope='device',source=NXP,source_revision=SOURCES[NXP],description=meaning)
  if k=='duplex_mode':v['options']=['FULL_DUPLEX','HALF_DUPLEX']
  out.append(v)
 return out

def evidence_issues(e,payload_bytes=0):
 issues=[]
 for f in local_fields():
  v=e.get(f['key']);t=f['type']
  if v is None or isinstance(v,str)and not v.strip():issues.append(f['key']);continue
  if t=='number':
   if not isinstance(v,(int,float))or isinstance(v,bool)or not isfinite(v)or f['integer']and v!=int(v)or f['minimum']is not None and v<f['minimum']or f['maximum']is not None and v>f['maximum']:issues.append(f['key'])
  elif t=='text'and not isinstance(v,str)or t=='boolean'and type(v)is not bool or t=='select'and v not in f['options']:issues.append(f['key'])
 if e.get('confirmed')is not True:issues.append('confirmed')
 if not issues and e['transfer_bits_bound']<max(0,payload_bytes)*8:issues.append('transfer_bits_bound')
 return list(dict.fromkeys(issues))
