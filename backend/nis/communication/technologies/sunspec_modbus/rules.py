"""SunSpec model edition 1.1 and Secure TCP edition 1.0 (2025).

The information model is independent of an explicitly selected Modbus bearer.
Selected parameter checks are not SunSpec certification or a runtime decoder.
"""
from backend.nis.communication.services.native_review_support import declaration, fields as build_fields, WIRE_KEYS, ETHERNET_KEYS
MODEL='https://sunspec.org/wp-content/uploads/2025/01/SunSpec-Device-Information-Model-Specificiation-V1-1-final.pdf'
SECURE='https://sunspec.org/wp-content/uploads/2009/03/Secure-SunSpec-Modbus-Specification_final.pdf'
APP='https://www.modbus.org/file/secure/modbusprotocolspecification.pdf'
SOURCES={MODEL:'SunSpec Device Information Model1.1 approved05-09-2022, selected printed14-41: definition, Modbus layout/types/errors, JSON distinct.',SECURE:'Secure SunSpec Modbus1.0 approvedDecember10 2025, selected printed5-9/12-18. Normative section5 controls cipher support; RTU security explicitly deferred.',APP:'Modbus Application1.1b3 April26 2012 sections4,6.3,6.12,7: actual function/PDU/address envelope.'}
DECLARATIONS=[]
def d(k,t,meaning,source=MODEL,**kw):DECLARATIONS.append(declaration('ss_',k,t,meaning,source,SOURCES[source],**kw))
TYPES=['int16','int32','int64','raw16','uint16','uint32','uint64','acc16','acc32','acc64','bitfield16','bitfield32','bitfield64','enum16','enum32','float32','float64','string','sunssf','pad','ipaddr','ipv6addr','eui48']
for k,meaning,opts in [
 ('edition','Actual information-model edition independent of uploaded PDF date.',['MODEL_1_1_2022','REGISTERED_ACTUAL']),
 ('proposal_mode','Explicit literature proposal versus actual commissioned parameters.',['SOURCE_BASELINE','ACTUAL_CONFIG']),
 ('transport','Actual selected Modbus carriage; JSON representation is not a Modbus bearer.',['SERIAL_RTU','SERIAL_ASCII','TCP','SECURE_TCP']),
 ('secure_edition','Actual selected Secure TCP edition, no inherited v36 cipher defaults.',['SECURE_1_0_2025','REGISTERED_ACTUAL']),
 ('context','Actual model definition, wire instance or JSON instance.',['DEFINITION','MODBUS_INSTANCE','JSON_INSTANCE']),
 ('space','Actual Modbus table; SunSpec maps use holding registers.',['HOLDING','INPUT','COILS']),
 ('word_order','Actual whole multi-register order, not vendor little-endian word swapping.',['BIG_ENDIAN','LITTLE_ENDIAN']),
 ('group_type','Actual ordered point group; sync requires atomic whole-group access.',['group','sync']),
 ('point_type','Actual point type; sentinel and availability differ by type.',TYPES),
 ('access','Actual point permission; absent definition attribute defaults R.',['R','RW']),
 ('mandatory','Actual definition requirement; absent attribute defaults O.',['M','O']),
 ('availability','Actual decoded availability, not sentinel classified as valid data.',['VALID','NOT_IMPLEMENTED','NOT_ACCUMULATED','NOT_CONFIGURED','UNKNOWN']),
 ('operation','Actual data operation and result scope.',['READ','WRITE','DISCOVERY']),
 ('phase','Actual request, normal response or exception PDU, not generic payload.',['REQUEST','RESPONSE','EXCEPTION']),
 ('write_case','Actual attempted register write, authorization errors differ from invalid values.',['VALID','UNIMPLEMENTED','INVALID_VALUE','READ_ONLY','AUTHORIZATION_DENIED']),
 ('tls_version','Actual negotiated TLS version and independent required support.',['1.2','1.3']),
 ('cipher','Actual negotiated supported suite or qualified IANA/certificate-compatible alternate.',[
  'TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256','TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256','TLS_ECDHE_ECDSA_WITH_AES_128_CCM_8',
  'TLS_AES_128_GCM_SHA256','TLS_CHACHA20_POLY1305_SHA256','TLS_AES_128_CCM_SHA256','REGISTERED_ALLOWED']),
 ('role','Actual certificate role, not inferred authorization for all registers.',['ReadOnlySunSpec','GridServiceSunSpec','NetworkAdministratorSunSpec','SuperAdministratorSunSpec','REGISTERED_ADDITIONAL']),
 ('outcome','Actual correlated application acceptance independent of read-after-write.',['ACCEPTED','STALE','ERROR','UNKNOWN']),
]:d(k,'select',meaning,options=opts,source=SECURE if k in('secure_edition','tls_version','cipher','role')else MODEL)
for k,meaning,lo,hi,unit in [
 ('map_base','Actual0-based discovered address from0,40000,50000; not default40001.',0,65535,'register'),
 ('marker_hi','Actual first SunS marker register0x5375.',0,65535,None),('marker_lo','Actual second SunS marker register0x6E53.',0,65535,None),
 ('model_id','Actual administered ID1..65535; FFFF end sentinel distinct regular model.',1,65535,None),
 ('model_length','Actual remaining registers after L in instance, zero in definition.',0,65535,'register'),
 ('model_address','Actual address of current model ID register.',0,65535,'register'),
 ('next_model_address','Actual next model ID address=current+2+L; must remain within map.',0,65535,'register'),
 ('point_offset','Actual point offset in model payload.',0,65535,'register'),
 ('point_registers','Actual encoded whole point register width; string variable-size, no byte count confusion.',1,65535,'register'),
 ('definition_size','Actual optional size attribute in16-bit words, only string/pad may define it.',1,65535,'register'),
 ('point_bytes','Actual encoded point bytes=2*registers.',0,131070,'byte'),
 ('point_count','Actual repeat count; referenced static count defined earlier.',0,65535,None),
 ('sf','Actual signed power-of-ten scale factor−10..10; 0x8000 denotes unavailable.',-10,10,None),
 ('value','Actual decoded finite numeric value; type-specific sentinel never accepted as valid.',None,None,None),
 ('register_address','Actual0-based transaction start address.',0,65535,'register'),
 ('quantity','Actual whole registers per function; read125/write123 limits distinct.',1,125,'register'),
 ('byte_count','Actual register data count=2*quantity.',0,250,'byte'),
 ('function','Actual mandatory3/16 or optional6; no assumption optional6 implemented.',0,255,None),
 ('request_function','Actual original function for exception response.',0,127,None),
 ('exception_code','Actual wire exception; invalid/read-only/unimplemented2/3/4 vs role denial1.',0,255,None),
 ('pdu_bytes','Actual PDU includes function+address/count/data; maximum253 distinct model size.',1,253,'byte'),
 ('unit_id','Actual serial slave or MBAP route ID, source-qualified target binding.',0,255,None),
 ('tcp_port','Actual selected TCP port; ordinary502 vs secure802 literature proposals.',1,65535,None),
 ('atomic_registers','Actual entire sync group register count per operation, must equal group size.',1,65535,'register'),
 ('group_registers','Actual whole sync-group register size.',1,65535,'register'),
 ('root_certificates','Actual supported trust-anchor storage, secure2025 at least10.',0,None,None),
 ('role_extension_count','Actual one ASN1UTF8String certificate role, server role not mandatory.',0,None,None),
 ('fragment_capability_bytes','Actual supported TLS max fragment negotiation, not actual negotiated default512.',0,None,'byte'),
 ('source_ms','Actual acquisition/source/serializer bound.',0,None,'ms'),('transport_ms','Actual transaction/queue/serial or TCP/TLS/bearer bound.',0,None,'ms'),
 ('consumer_ms','Actual decoding/authorization/application bound.',0,None,'ms'),('e2e_ms','Actual complete source+transport+consumer bound.',0,None,'ms'),
 ('deadline_ms','Actual independent functional deadline.',0,None,'ms'),('age_ms','Actual correlated consuming data age.',0,None,'ms'),('freshness_ms','Actual allowed application age.',0,None,'ms'),
]:d(k,'number',meaning,min=lo,max=hi,unit=unit,integer=unit!='ms'and k!='value',source=APP if k in('quantity','byte_count','function','request_function','pdu_bytes','register_address','unit_id')else SECURE if k in('root_certificates','role_extension_count','fragment_capability_bytes')else MODEL)
for k,meaning in [
 ('support3','Actual endpoint supports mandatory Read Holding Registers.'),('support16','Actual endpoint supports mandatory Write Multiple Registers.'),
 ('support6','Actual optional Write Single Register support; cannot be assumed.'),('contiguous','Actual map has no holes including optional/unimplemented points.'),
 ('order_verified','Actual ordered points before groups, repeat instances consecutive.'),('atomic','Actual sync group accessed wholly and atomically.'),
 ('count_static','Actual referenced count point is static.'),('count_defined_before','Actual referenced count occurs in top-level group before repeat.'),
 ('sf_static','Actual scale-factor point never changes over operation.'),('sf_type_verified','Actual referenced scale-factor point is sunssf.'),
 ('symbols_verified','Actual enum value or bit position belongs to this point’s definition.'),('write_success','Actual successful information write; not functional acceptance.'),
 ('readback_match','Actual read-after-write reflects last successful request.'),('data_accepted','Actual consuming behavior and timing independently accepted.'),
 ('lower_binding_verified','Actual separate selected Modbus/TCP/serial/PHY configuration verified.'),('codec_verified','Actual complete model schema/sentinel/encoding decoding verified.'),
]:d(k,'boolean',meaning)
for k,meaning in [
 ('tls12_supported','Actual mandatory TLS1.2 support independent of selected1.3.'),('tls13_supported','Actual optional TLS1.3 support.'),
 ('mutual_tls','Actual both client/server authenticated during handshake.'),('x509v3','Actual validated X509v3 credentials.'),
 ('certificate_request','Actual server requested client certificate.'),('client_certificate','Actual client provided a validated certificate.'),
 ('fatal_terminated','Actual missing client certificate causes fatal termination.'),('resume_after_fatal','Actual forbidden resume after fatal alert.'),
 ('tls12_gcm','Actual required TLS1.2 AES128GCM suite support.'),('tls12_chacha','Actual required TLS1.2CHACHA20POLY1305 suite support.'),('tls12_ccm8','Actual required TLS1.2 AES128CCM8 suite support.'),
 ('tls13_gcm','Actual required TLS1.3 AES128GCM suite support when1.3supported.'),('tls13_chacha','Actual required TLS1.3CHACHA20POLY1305 support when1.3supported.'),('tls13_ccm','Actual required TLS1.3AES128CCM support when1.3supported.'),
 ('cipher_order_verified','Actual offered suites ordered as normative section5.2.'),('iana_allowed','Actual IANA suite status verified for negotiated cipher.'),('certificate_compatible','Actual suite compatible with X509v3 credential key/signature.'),
 ('disable_discouraged','Actual ability to disable IANA-discouraged suites.'),('mandatory_roles','Actual all four mandatory roles supported.'),('rights_configurable','Actual vendor supplied configurable point-level roles-to-rights database.'),
 ('role_map_verified','Actual required SunSpec role map revision verified, no broad role-only write approval.'),('authorized','Actual all requested points allowed by current client role.'),
 ('public_network','Actual communications routed over a public network.'),('ca_signed','Actual certificate CA-signed, mandatory on public network per section5.4.'),('trust_verified','Actual full validated trusted chain/current lifecycle.'),
 ('p256_supported','Actual required ECCP256 support, not a guessed negotiated key.'),('secure_renegotiation','Actual required secure renegotiation capability.'),
 ('compression_null','Actual NULL TLS compression; distinct forbidden NULL crypto.'),('sha256_supported','Actual SHA256 HMAC/PRF capability.'),('weak_crypto','Actual MD5/SHA1 HMAC or NULL crypto/forbiddenSHA1PRF selected.'),
]:d(k,'boolean',meaning,source=SECURE)
for k,meaning in [
 ('revision','Actual selected model/device firmware revision.'),('model_source','Actual exact approved/vendor model definition and revision.'),
 ('registered_source','Actual separately registered edition schema; current reviewed bounds do not certify it.'),
 ('binding_source','Actual selected serial/TCP/security canonical endpoints and separate lower-layer profile.'),('device_source','Actual device supported model/function/address capabilities.'),
 ('codec_source','Actual register/UTF8/IEEE754/sentinel/scale-factor codec evidence.'),('schedule_source','Actual polling/response/retry/queue/whole-carriage timing evidence.'),
 ('acceptance_source','Actual functional behavior/deadline/freshness requirement.'),('observation_source','Actual correlated acquisition/transaction/consumer observation.'),
 ('point_id','Actual unique alphanumeric or underscore ID in containing group.'),('raw_hex','Actual exact encoded whole point hex, preserves uint64/sentinels without floating-point loss.'),
 ('secure_source','Actual security edition/TLS/certificate/cipher implementation qualification.'),('rights_source','Actual vendor point-rights database and SunSpec role-map revision.'),
 ('role_oid','Actual client-role certificate extension OID.'),('role_encoding','Actual ASN1UTF8String encoding of one role.'),
]:d(k,'text',meaning,source=SECURE if k in('secure_source','rights_source','role_oid','role_encoding')else MODEL,**({'pattern':'[A-Za-z0-9_]+'}if k=='point_id'else {'pattern':'(?:[0-9A-Fa-f]{4})+'}if k=='raw_hex'else {}))
REQUIRED=('edition','transport','revision','model_source','binding_source','device_source','codec_source','schedule_source','acceptance_source')
REMOVED={k:'SunSpec owns information-model semantics. Clock/retry/gateway/MTU belongs to the actual separately selected serial or TCP/PHY profile.'for k in(*WIRE_KEYS,*ETHERNET_KEYS)}

def semantics():
 rules=[]
 def r(k,w=None,**kw):rules.append(dict(parameter='ss_'+k,when={'ss_edition':'MODEL_1_1_2022',**{'ss_'+a:b for a,b in(w or{}).items()}},source=MODEL,**kw))
 rules.append(dict(parameter='ss_registered_source',when={'ss_edition':'REGISTERED_ACTUAL'},required=True,source=MODEL))
 r('map_base',allowed=[0,40000,50000]);r('marker_hi',allowed=[0x5375]);r('marker_lo',allowed=[0x6E53]);r('space',allowed=['HOLDING']);r('word_order',allowed=['BIG_ENDIAN'])
 r('model_length',{'context':'DEFINITION'},allowed=[0]);r('model_length',{'model_id':65535},allowed=[0])
 r('next_model_address',equal_expression={'sum':['ss_model_address',2,'ss_model_length']})
 r('point_bytes',equal_expression={'product':['ss_point_registers',2]})
 ranges={'int16':(-32767,32767),'int32':(-2147483647,2147483647),'int64':(-9223372036854775807,9223372036854775807),
  'raw16':(0,65535),'uint16':(0,65534),'enum16':(0,65534),'uint32':(0,4294967294),'enum32':(0,4294967294),
  'uint64':(0,18446744073709551614),'acc16':(0,65535),'acc32':(0,4294967295),'acc64':(0,9223372036854775807),
  'bitfield16':(0,32767),'bitfield32':(0,2147483647),'sunssf':(-10,10),'pad':(32768,32768)}
 for t,(lo,hi) in ranges.items():r('value',{'point_type':t,'availability':'VALID'},minimum=lo,maximum=hi,integer=True)
 sentinels={'int16':'8000','int32':'80000000','int64':'8000000000000000','uint16':'FFFF','enum16':'FFFF','bitfield16':'FFFF',
  'uint32':'FFFFFFFF','enum32':'FFFFFFFF','bitfield32':'FFFFFFFF','uint64':'FFFFFFFFFFFFFFFF',
  'float32':'7FC00000','float64':'7FF8000000000000','sunssf':'8000'}
 for t,raw in sentinels.items():
  r('raw_hex',{'point_type':t,'availability':'NOT_IMPLEMENTED'},pattern='(?i)'+raw)
  r('raw_hex',{'point_type':t,'availability':'VALID'},pattern='(?i)(?!'+raw+'$)[0-9a-f]{'+str(len(raw))+'}')
 for t,raw in [('acc16','0000'),('acc32','00000000'),('acc64','0000000000000000')]:r('raw_hex',{'point_type':t,'availability':'NOT_ACCUMULATED'},pattern=raw)
 widths={'int16':1,'raw16':1,'uint16':1,'acc16':1,'bitfield16':1,'enum16':1,'sunssf':1,'int32':2,'uint32':2,'acc32':2,'bitfield32':2,'enum32':2,'float32':2,'ipaddr':2,'int64':4,'uint64':4,'acc64':4,'float64':4,'ipv6addr':8,'eui48':3}
 for t,size in widths.items():r('point_registers',{'point_type':t},allowed=[size])
 for t in TYPES:
  if t not in('string','pad'):r('definition_size',{'point_type':t},allowed=[])
 r('definition_size',{'point_type':'string'},required=True);r('point_registers',{'point_type':'string'},equal_parameter='ss_definition_size')
 for k in('count_static','count_defined_before'):r(k,when_present=['ss_point_count'],allowed=[True])
 for k in('sf_static','sf_type_verified'):r(k,when_present=['ss_sf'],allowed=[True])
 r('availability',{'mandatory':'M'},allowed=['VALID']);r('atomic',{'group_type':'sync'},required=True,allowed=[True])
 r('atomic_registers',{'group_type':'sync'},required=True,equal_parameter='ss_group_registers')
 r('quantity',{'group_type':'sync'},equal_parameter='ss_group_registers')
 r('group_registers',{'group_type':'sync'},required=True)
 for k in('contiguous','order_verified','support3','support16'):r(k,allowed=[True])
 r('function',allowed=[3,6,16,131,134,144]);r('support6',{'function':6},required=True,allowed=[True])
 r('quantity',{'function':3},maximum=125);r('quantity',{'function':16},maximum=123);r('quantity',{'function':6},allowed=[1])
 r('byte_count',equal_expression={'product':[2,'ss_quantity']})
 r('quantity',maximum_expression={'subtract':[65536,'ss_register_address']})
 for k in('phase','function'):r(k,when_present=['ss_pdu_bytes'],required=True)
 r('pdu_bytes',{'phase':'REQUEST','function':3},allowed=[5]);r('pdu_bytes',{'phase':'RESPONSE','function':3},equal_expression={'sum':[2,{'product':[2,'ss_quantity']}]})
 r('pdu_bytes',{'phase':'REQUEST','function':16},equal_expression={'sum':[6,{'product':[2,'ss_quantity']}]});r('pdu_bytes',{'phase':'RESPONSE','function':16},allowed=[5])
 for phase in('REQUEST','RESPONSE'):r('pdu_bytes',{'phase':phase,'function':6},allowed=[5])
 r('pdu_bytes',{'phase':'EXCEPTION'},allowed=[2])
 r('quantity',{'phase':'REQUEST','function':16},when_present=['ss_pdu_bytes'],required=True);r('quantity',{'phase':'RESPONSE','function':3},when_present=['ss_pdu_bytes'],required=True)
 for f in(131,134,144):r('function',{'function':f},equal_expression={'sum':['ss_request_function',128]})
 for case in('UNIMPLEMENTED','INVALID_VALUE','READ_ONLY'):r('exception_code',{'write_case':case},required=True,allowed=[2,3,4])
 r('exception_code',{'write_case':'AUTHORIZATION_DENIED'},required=True,allowed=[1]);r('readback_match',{'write_success':True},required=True,allowed=[True])
 for transport in('SERIAL_RTU','SERIAL_ASCII'):r('unit_id',{'transport':transport},minimum=1,maximum=247);r('tcp_port',{'transport':transport},allowed=[])
 secure={'transport':'SECURE_TCP','secure_edition':'SECURE_1_0_2025'}
 r('secure_edition',{'transport':'SECURE_TCP'},required=True)
 for k in('secure_source','rights_source','cipher','tls_version','role','role_oid','role_encoding'):r(k,secure,required=True)
 for k in('tls12_supported','mutual_tls','x509v3','certificate_request','client_certificate','tls12_gcm','tls12_chacha','tls12_ccm8','cipher_order_verified','iana_allowed','certificate_compatible','disable_discouraged','mandatory_roles','rights_configurable','role_map_verified','trust_verified','p256_supported','secure_renegotiation','compression_null','sha256_supported'):r(k,secure,required=True,allowed=[True])
 r('root_certificates',secure,required=True,minimum=10);r('role_extension_count',secure,required=True,allowed=[1]);r('role_oid',secure,allowed=['1.3.6.1.4.1.50316.802.1']);r('role_encoding',secure,allowed=['ASN1_UTF8STRING'])
 r('fragment_capability_bytes',secure,required=True,allowed=[512]);r('weak_crypto',secure,required=True,allowed=[False]);r('resume_after_fatal',secure,allowed=[False])
 for k in('tls13_supported','tls13_gcm','tls13_chacha','tls13_ccm'):r(k,{**secure,'tls_version':'1.3'},required=True,allowed=[True])
 for k in('tls13_gcm','tls13_chacha','tls13_ccm'):r(k,{**secure,'tls13_supported':True},required=True,allowed=[True])
 r('ca_signed',{**secure,'public_network':True},required=True,allowed=[True])
 r('exception_code',{**secure,'authorized':False},required=True,allowed=[1])
 r('authorized',{**secure,'role':'ReadOnlySunSpec','operation':'WRITE'},required=True,allowed=[False])
 for k in('client_certificate','certificate_request'):r('fatal_terminated',{**secure,k:False},required=True,allowed=[True])
 r('cipher',{**secure,'tls_version':'1.2'},allowed=['TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256','TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256','TLS_ECDHE_ECDSA_WITH_AES_128_CCM_8','REGISTERED_ALLOWED'])
 r('cipher',{**secure,'tls_version':'1.3'},allowed=['TLS_AES_128_GCM_SHA256','TLS_CHACHA20_POLY1305_SHA256','TLS_AES_128_CCM_SHA256','REGISTERED_ALLOWED'])
 r('e2e_ms',equal_expression={'sum':['ss_source_ms','ss_transport_ms','ss_consumer_ms']});r('e2e_ms',maximum_parameter='ss_deadline_ms');r('age_ms',maximum_parameter='ss_freshness_ms')
 for k in('source_ms','transport_ms','consumer_ms'):r(k,when_present=['ss_e2e_ms'],required=True)
 for k in('observation_source','model_id','availability','e2e_ms','deadline_ms','age_ms','freshness_ms'):r(k,{'data_accepted':True},required=True)
 for k,v in('lower_binding_verified',True),('codec_verified',True),('outcome','ACCEPTED'),('availability','VALID'):r(k,{'data_accepted':True},required=True,allowed=[v])
 return dict(rate_model={'type':'INFORMATION_MODEL_NO_UNIVERSAL_CLOCK','fields':[]},required_parameters=['ss_'+k for k in REQUIRED],native_parameter_prefixes=['ss_'],parameter_constraints=rules,medium_access_model='BOUND_MODBUS_REQUEST_RESPONSE',arbitration_model_id='SELECTED_SERIAL_CONTROLLER_OR_TCP_SERVICE',mechanisms={'binding':['SERIAL_OR_TCP_EXPLICIT','SECURE_TCP_2025_DISTINCT'],'model':['CONTIGUOUS_HOLDING_REGISTERS','TYPE_SENTINEL_PROVENANCE'],'qualification':['CAPACITY_INDEPENDENT','FUNCTIONAL_ACCEPTANCE_INDEPENDENT']})

def fields():
 base={'ss_edition':'MODEL_1_1_2022','ss_proposal_mode':'SOURCE_BASELINE'}
 proposals={}
 for key,value in [('space','HOLDING'),('word_order','BIG_ENDIAN'),('access','R'),('mandatory','O')]:proposals['ss_'+key]=[dict(when=base,value=value,source=MODEL,source_revision=SOURCES[MODEL])]
 proposals['ss_tcp_port']=[dict(when={**base,'ss_transport':'TCP'},value=502,source=APP,source_revision=SOURCES[APP]),dict(when={'ss_proposal_mode':'SOURCE_BASELINE','ss_transport':'SECURE_TCP','ss_secure_edition':'SECURE_1_0_2025'},value=802,source=SECURE,source_revision=SOURCES[SECURE])]
 result=build_fields(DECLARATIONS,['ss_'+k for k in REQUIRED],proposals)
 for item in result:
  if item['key'] not in {'ss_'+k for k in REQUIRED}|{'ss_registered_source','ss_proposal_mode','ss_secure_edition','ss_secure_source','ss_rights_source'}:
   item['schema_when']={'ss_edition':'MODEL_1_1_2022'}
 return result
