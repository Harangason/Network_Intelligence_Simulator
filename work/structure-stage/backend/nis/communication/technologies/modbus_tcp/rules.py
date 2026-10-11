"""Native MBAP parameters, explicit transport binding and qualified Modbus Security."""
from copy import deepcopy
from backend.nis.communication.technologies.modbus_ascii import rules as common

APP=common.APP
TCP='https://www.modbus.org/file/secure/messagingimplementationguide.pdf'
SECURITY='https://www.modbus.org/file/secure/modbussecurityprotocol.pdf'
SOURCES={APP:common.SOURCES[APP],TCP:'Modbus Messaging on TCP/IP GuideV1.0b October24 2006 sections3/4; implementation examples not universal hardware limits',
 SECURITY:'MB-TCP-Security-v36 2021-07-30 sections6-10/AppendixA; TLS1.2-or-newer mutual X509v3, port802 and conditional role authorization'}
SHARED=set('phase function_kind word_order mapping_source function_source function request_function exception_code mei_type '
 'pdu_bytes data_bytes start_address quantity byte_count coil_value register_value register_bits '
 'read_quantity write_quantity write_start_address write_byte_count'.split())
PUBLIC=[1,2,3,4,5,6,15,16,20,21,22,23,24,43]  # Serial-only7/8/11/12/17 are not nativeTCP functions.
USER=common.USER

def rebind(value):
    if isinstance(value,str):return 'mt_'+value[3:] if value.startswith('ma_') else value
    if isinstance(value,list):return [rebind(v) for v in value]
    if isinstance(value,dict):return {rebind(k):rebind(v) for k,v in value.items()}
    return deepcopy(value)

DECLARATIONS=[rebind(v) for v in common.DECLARATIONS if v['key'][3:] in SHARED]
def d(key,kind,meaning,lo=None,hi=None,unit=None,options=None,source=TCP,**kw):
    DECLARATIONS.append(dict(key='mt_'+key,type=kind,description=meaning,min=lo,max=hi,unit=unit,options=options,
        source=source,source_revision=SOURCES[source],**kw))

for key,meaning,options,source in [
 ('profile','Actual MBAP guide binding or registered extension.',['GUIDE_1_0B','REGISTERED'],TCP),
 ('mode','Actual plain MBAP/TCP or Modbus Security TLS/TCP; TLS does not alter MBAP.',['PLAIN','SECURITY_V36','REGISTERED'],TCP),
 ('role','Actual client/server or explicit gateway; bidirectional client/server uses separate connections.',['CLIENT','SERVER','GATEWAY','REGISTERED'],TCP),
 ('destination','Actual direct TCP peer or serial gateway; unit identifier routing differs.',['DIRECT_TCP','SERIAL_GATEWAY','REGISTERED'],TCP),
 ('implementation','Actual guide example transaction resources versus registered manufacturer limits.',['GUIDE_EXAMPLE','REGISTERED'],TCP),
 ('connection_management','Actual automatic or explicit application socket management.',['AUTOMATIC','EXPLICIT'],TCP),
 ('tls_version','Actual negotiated TLS1.2 or newer; SSL/1.0/1.1 prohibited.',['TLS1_2','TLS1_3','REGISTERED'],SECURITY),
 ('credential_kind','Actual mutually authenticated X509v3 device credentials, not PSK-only.',['X509V3','REGISTERED'],SECURITY),
 ('key_kind','Actual RSA or ECC credentials and mandatory suite capabilities.',['RSA','ECC','REGISTERED'],SECURITY),
 ('cipher','Actual negotiated IANA suite; mandatory supported suites are not automatic negotiated defaults.',
  ['TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256','TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256','TLS_RSA_WITH_NULL_SHA256',
   'TLS_AES_128_GCM_SHA256','REGISTERED'],SECURITY),
 ('compression','Actual TLS1.2 compression must NULL; newerTLS has separate protocol semantics.',['NULL'],SECURITY),
 ('role_encoding','Actual one certificate role encoded ASN1 UTF8String, not default Operator rights.',['ASN1_UTF8STRING'],SECURITY),
]:d(key,'select',meaning,options=options,source=source)

for key,meaning,source in [
 ('revision','Actual selected device/firmware/standard revisions; industry independent.',TCP),
 ('network_id','Actual canonical application network identity.',TCP),
 ('transport_network_id','Actual separately registered TCP/IP and physical path identity; no own Ethernet clock.',TCP),
 ('binding_source','Actual client/server TCP sockets, IP path and separately confirmed lower-layer parameters.',TCP),
 ('device_source','Actual supported functions, connection counts and negotiated resources.',TCP),
 ('codec_source','Actual MBAP/PDU byte stream encoder/decoder and boundary reconstruction, no RTU CRC or ASCII LRC.',TCP),
 ('schedule_source','Actual application requests/replies/processing/concurrency/retry and transport schedule.',TCP),
 ('capacity_source','Actual complete TCP/IP/PHY/TLS bytes and per-path schedule, not MBAP alone.',TCP),
 ('acceptance_source','Actual functional timing/freshness/security/safety requirements and acceptance.',APP),
 ('registered_source','Actual registered function/transport/security/implementation deviation.',TCP),
 ('timer_source','Actual application/socket timeout and response-bound configuration; no standard response timeout.',TCP),
 ('connection_id','Actual TCP connection identity; TIDs unique only among pending requests on same connection.',TCP),
 ('request_connection_id','Actual correlated request connection, never cross-connection match by TID alone.',TCP),
 ('gateway_network_id','Actual separately validated serial segment/network behind gateway.',TCP),
 ('gateway_source','Actual TCP-to-serial unit/address/broadcast/queue/codec translation and physical path.',TCP),
 ('tls_source','Actual security implementation, handshake, negotiated suite/extensions and record framing.',SECURITY),
 ('certificate_ref','Actual provisioned client/server certificate reference, no generated identity or private key.',SECURITY),
 ('trust_ref','Actual PKI/trust-anchor/validation reference, no default trust-all.',SECURITY),
 ('role_oid','Actual Modbus certificate-role OID1.3.6.1.4.1.50316.802.1.',SECURITY),
 ('certificate_role','Actual one whole UTF8 role string; missing role maps NULL, not split roles/default Operator.',SECURITY),
 ('authorization_source','Actual vendor AuthZ function and user-configurable roles-to-rights database.',SECURITY),
 ('cipher_registry_source','Actual IANA registered and current security-qualified cipher source, including registered suites.',SECURITY),
]:d(key,'text',meaning,source=source)
d('adu_hex','text','Lossless hex representation of actual MBAP+PDU bytes; not ASCII wire encoding.',
  pattern=r'(?:[0-9A-F]{2}){8,260}',min_length=16,max_length=520)
for key,meaning,lo,hi,unit,source in [
 ('port','Actual TCP server port502 plain or802 Modbus Security; client ephemeral port separate.',1,65535,None,TCP),
 ('client_port','Actual distinct client local port>1024 in guide binding, not fixed502.',1,65535,None,TCP),
 ('transaction_id','Actual uint16 request/response correlation identifier, not TCP sequence number.',0,65535,None,TCP),
 ('request_transaction_id','Actual original pending transaction identifier on same TCP connection.',0,65535,None,TCP),
 ('protocol_id','MBAP protocol identifier0 for Modbus.',0,0,None,TCP),
 ('unit_id','Actual MBAP uint8 routing field; directFFrecommended/0accepted vsserial1..247/broadcast0.',0,255,None,TCP),
 ('request_unit_id','Actual request unit field copied in response, not fabricated device address.',0,255,None,TCP),
 ('mbap_bytes','Actual MBAP7bytes=TID2+protocol2+length2+unit1; no CRC.',7,7,'byte',TCP),
 ('length_field','Actual count following MBAP first6bytes:unit1+PDU1..253 gives2..254.',2,254,'byte',TCP),
 ('adu_bytes','Actual MBAP7+PDU1..253 gives8..260byte ADU; distinct serial256limit.',8,260,'byte',APP),
 ('outstanding','Actual simultaneous pending transactions on one connection; each needs unique16bitTID.',0,65536,None,TCP),
 ('client_transaction_cap','Actual client resource limit; guide example1..16 is not universal manufacturer cap.',1,65536,None,TCP),
 ('server_transaction_cap','Actual server transaction resources; saturation yields Busy6, no universal16default.',1,None,None,TCP),
 ('connections','Actual current TCP connections, not universal CAN queue size.',0,None,None,TCP),
 ('connection_cap','Actual configured maximum supported TCP connections, device dependent.',1,None,None,TCP),
 ('receive_buffer_bytes','Actual socket receive high-watermark below actual internal driver resources;900is illustrative.',1,None,'byte',TCP),
 ('send_buffer_bytes','Actual socket send high-watermark below actual internal driver resources.',1,None,'byte',TCP),
 ('driver_receive_bytes','Actual internal receive resource capacity; not MBAP ADU limit.',1,None,'byte',TCP),
 ('driver_send_bytes','Actual internal send resource capacity; not universal900bytes.',1,None,'byte',TCP),
 ('tls_fragment_bytes','Actual negotiated TLS maximum fragment; support512extension required, not installed negotiated512.',1,16384,'byte',SECURITY),
 ('tls_record_bytes','Actual TLS1.2 ciphertext fragment<=16384+2048, separate5byte record header and ADU.',1,None,'byte',SECURITY),
 ('role_count','Actual one role per certificate extension;0 means absent/NULL role.',0,1,None,SECURITY),
 ('role_utf8_bytes','Actual UTF8 role bytes, distinct Unicode codepoints, no arbitrary standard role-length cap.',0,None,'byte',SECURITY),
 ('ecc_curve_bits','Actual ECC capability includes at leastP256 when selected; installed curve not a default.',256,None,'bit',SECURITY),
]:d(key,'number',meaning,lo,hi,unit,source=source,integer=True)
for key,meaning in [
 ('response_bound_ms','Actual bounded worst-case complete response for selected path/function.'),
 ('response_timeout_ms','Actual application response timeout; deliberately no universal standard value.'),
 ('connect_timeout_ms','Actual configured connection establishment timeout;75s is legacy-stack example only.'),
 ('keepalive_idle_ms','Actual stack idle before probe;2h is historical example only.'),
 ('keepalive_interval_ms','Actual stack probe interval;75s is historical example only.'),
]:d(key,'number',meaning,0,None,'ms')
for key,meaning,source in [
 ('pending_id_unique','Actual pendingTIDs unique on selected connection; trace/queue proof still required.',TCP),
 ('pending_match','Actual received response refers to pending request; otherwise discard.',TCP),
 ('connection_persistent','Actual keep-open connection policy; recommended rather than open/close eachtransaction.',TCP),
 ('nodelay','Actual TCP_NODELAY enabled recommendation; not universal TCP QoS guarantee.',TCP),
 ('reuseaddr','Actual SO_REUSEADDR policy; socket state behavior depends actual OS.',TCP),
 ('keepalive','Actual SO_KEEPALIVE enabled recommendation; timings/resource effects configured.',TCP),
 ('mutual_auth','Actual client/server certificate authentication, required for Security.',SECURITY),
 ('certificate_validated','Actual peer chain/identity/trust validation completed, not automatic from certificate_ref.',SECURITY),
 ('authorization_enabled','Actual optional role authorization; if provided must meet role/database rules.',SECURITY),
 ('authorization_denied','Actual authorization rejection; exception1 returned for deniedrequest.',SECURITY),
 ('roles_configurable','Actual vendor roles-to-rights database user-configurable, no immutabledefaultrole.',SECURITY),
 ('mfl_extension','Actual Maximum Fragment Length extension supported byTLS1.2.',SECURITY),
 ('mfl_512_supported','Actual device can negotiate512byte TLS fragment; capability not negotiatedlength.',SECURITY),
 ('secure_renegotiation','Actual RFC5746 extension supported forTLS1.2; not applicableTLS1.3.',SECURITY),
 ('rsa_required_suite_supported','Actual RSA device supports ECDHE_RSA_AES128_GCM_SHA256.',SECURITY),
 ('ecc_required_suite_supported','Actual ECC device supports ECDHE_ECDSA_AES128_GCM_SHA256.',SECURITY),
 ('encryption_required','Actual application confidentiality requirement; auth-only NULLbulk differs null authentication.',SECURITY),
]:d(key,'boolean',meaning,source=source)

REQUIRED=['profile','mode','role','destination','revision','network_id','transport_network_id','binding_source','device_source',
          'codec_source','mapping_source','schedule_source','capacity_source','acceptance_source']
REMOVED={k:'Modbus TCP has no own universal '+k+'; separately registered actual TCP/IP/PHY/TLS path and device application policy replace inherited CAN/Ethernet defaults.'
 for k in (*common.REMOVED,'bitrate','duplex','mtu_bytes','vlan_id','vlan_pcp')}

def semantics():
    # Application-PDU rules only, with fields explicitly declared above.
    allowed={'ma_'+v for v in SHARED};rules=[]
    def refs(v):
        if isinstance(v,dict):return refs(list(v.keys()))|refs(list(v.values()))
        if isinstance(v,list):return set().union(*map(refs,v)) if v else set()
        return {v} if isinstance(v,str) and v.startswith('ma_') else set()
    for item in common.semantics()['parameter_constraints']:
        if item['source']==APP and refs(item)<=allowed:
            rule=rebind(item)
            if rule.get('parameter')=='mt_request_function' and rule.get('when')=={'mt_function_kind':'PUBLIC'}:rule['allowed']=PUBLIC
            rules.append(rule)
    def r(key,when=None,source=TCP,**kw):
        rules.append(dict(parameter=key if key in ('bitrate_bps','payload_bytes','local_timing_evidence') else'mt_'+key,
          when={'mt_'+k:v for k,v in(when or{}).items()},source=source,source_revision=SOURCES[source],**kw))
    r('local_timing_evidence',allowed=[])
    for key in ('profile','mode','role','destination','implementation','tls_version','key_kind','cipher','credential_kind','word_order','function_kind'):
        r('registered_source',{key:'REGISTERED'},required=True)
    r('port',{'mode':'PLAIN','profile':'GUIDE_1_0B'},allowed=[502])
    r('port',{'mode':'SECURITY_V36'},allowed=[802],source=SECURITY)
    r('client_port',{'profile':'GUIDE_1_0B'},minimum=1025)
    r('unit_id',{'destination':'DIRECT_TCP','profile':'GUIDE_1_0B'},allowed=[0,255])
    r('unit_id',{'destination':'SERIAL_GATEWAY'},maximum=247)
    for key in ('gateway_source','gateway_network_id'):r(key,{'destination':'SERIAL_GATEWAY'},required=True)
    for phase in ('RESPONSE','EXCEPTION'):
        r('transaction_id',{'phase':phase},equal_parameter='mt_request_transaction_id')
        r('unit_id',{'phase':phase},equal_parameter='mt_request_unit_id')
        r('connection_id',{'phase':phase},equal_parameter='mt_request_connection_id')
        for key in ('request_transaction_id','request_unit_id','request_connection_id'):r(key,{'phase':phase},required=True)
        r('pending_match',{'phase':phase},allowed=[True],required=True)
    r('pending_id_unique',when_positive=['mt_outstanding'],allowed=[True],required=True)
    r('outstanding',maximum_parameter='mt_client_transaction_cap')
    r('client_transaction_cap',when_present=['mt_outstanding'],required=True)
    r('client_transaction_cap',{'implementation':'GUIDE_EXAMPLE'},maximum=16)
    r('registered_source',when_greater_than={'mt_client_transaction_cap':16},required=True)
    r('connections',maximum_parameter='mt_connection_cap')
    r('connection_cap',when_present=['mt_connections'],required=True)
    r('length_field',equal_expression={'sum':['mt_pdu_bytes',1]},exact_decimal_equality=True)
    r('adu_bytes',equal_expression={'sum':['mt_pdu_bytes',7]},exact_decimal_equality=True)
    for key in ('length_field','adu_bytes'):r('pdu_bytes',when_present=['mt_'+key],required=True,source=APP)
    r('adu_hex',hex_bytes_parameter='mt_adu_bytes',hex_octets=[dict(offset=o,width=w,parameter='mt_'+k)
       for o,w,k in [(0,2,'transaction_id'),(2,2,'protocol_id'),(4,2,'length_field'),(6,1,'unit_id'),(7,1,'function')]])
    for key in ('adu_bytes','transaction_id','protocol_id','length_field','unit_id','function'):r(key,when_present=['mt_adu_hex'],required=True)
    r('response_timeout_ms',exclusive_minimum_expression='mt_response_bound_ms')
    r('response_bound_ms',when_present=['mt_response_timeout_ms'],required=True)
    for key in ('response_timeout_ms','connect_timeout_ms','keepalive_idle_ms','keepalive_interval_ms'):r('timer_source',when_present=['mt_'+key],required=True)
    for key,driver in [('receive_buffer_bytes','driver_receive_bytes'),('send_buffer_bytes','driver_send_bytes')]:
        r(key,exclusive_maximum_expression='mt_'+driver)
        r(driver,when_present=['mt_'+key],required=True)
    secure={'mode':'SECURITY_V36'}
    for key in ('tls_version','credential_kind','key_kind','encryption_required','authorization_enabled','tls_source','certificate_ref','trust_ref','cipher','cipher_registry_source','mutual_auth','certificate_validated'):
        r(key,secure,required=True,source=SECURITY)
    for key in ('mutual_auth','certificate_validated'):r(key,secure,allowed=[True],source=SECURITY)
    r('credential_kind',secure,allowed=['X509V3'],source=SECURITY)
    r('tls_record_bytes',{**secure,'tls_version':'TLS1_2'},maximum=18432,source=SECURITY)
    for key in ('mfl_extension','mfl_512_supported','secure_renegotiation'):
        r(key,{**secure,'tls_version':'TLS1_2'},allowed=[True],required=True,source=SECURITY)
    for key,cap in [('RSA','rsa_required_suite_supported'),('ECC','ecc_required_suite_supported')]:
        r(cap,{**secure,'key_kind':key},allowed=[True],required=True,source=SECURITY)
    r('ecc_curve_bits',{**secure,'key_kind':'ECC'},minimum=256,required=True,source=SECURITY)
    r('tls_fragment_bytes',{**secure,'tls_version':'TLS1_2'},allowed=[512,1024,2048,4096,16384],source=SECURITY)
    r('cipher',{**secure,'tls_version':'TLS1_3'},allowed=['TLS_AES_128_GCM_SHA256','REGISTERED'],source=SECURITY)
    r('cipher',{**secure,'tls_version':'TLS1_2'},forbidden=['TLS_AES_128_GCM_SHA256'],source=SECURITY)
    r('cipher',{**secure,'encryption_required':True},forbidden=['TLS_RSA_WITH_NULL_SHA256'],source=SECURITY)
    r('cipher',{**secure,'encryption_required':False},allowed=['TLS_RSA_WITH_NULL_SHA256','REGISTERED'],source=SECURITY)
    r('role_count',secure,when_present=['mt_certificate_role'],allowed=[1],required=True,source=SECURITY)
    r('certificate_role',secure,text_encoding='utf-8',encoded_bytes_parameter='mt_role_utf8_bytes',source=SECURITY)
    r('role_oid',secure,when_present=['mt_certificate_role'],allowed=['1.3.6.1.4.1.50316.802.1'],required=True,source=SECURITY)
    r('role_encoding',secure,when_present=['mt_certificate_role'],allowed=['ASN1_UTF8STRING'],required=True,source=SECURITY)
    r('certificate_role',{'role_count':0},allowed=[],source=SECURITY)
    for key in ('authorization_source','roles_configurable'):r(key,{**secure,'authorization_enabled':True},required=True,source=SECURITY)
    r('roles_configurable',{**secure,'authorization_enabled':True},allowed=[True],source=SECURITY)
    r('exception_code',{**secure,'authorization_denied':True},allowed=[1],required=True,source=SECURITY)
    r('phase',{**secure,'authorization_denied':True},allowed=['EXCEPTION'],required=True,source=SECURITY)
    for spec in DECLARATIONS:
        if spec['source']==SECURITY:r(spec['key'][3:],{'mode':'PLAIN'},allowed=[],source=SECURITY)
    return dict(rate_model={'type':'APPLICATION_DEPENDENT','fields':[]},required_parameters=['mt_'+k for k in REQUIRED],
      native_parameter_prefixes=['mt_'],parameter_evidence_scope='EXPLICIT_LAYER',parameter_constraints=rules,
      mechanisms={'framing':['MBAP_7_PDU_MAX253_ADU_MAX260','TCP_BYTE_STREAM_BOUNDARIES'],
       'transport':['EXPLICIT_TCP_IP_PHY_BINDING','OPTIONAL_MODBUS_SECURITY_802'],
       'correlation':['PENDING_TID_AND_UNIT_SAME_CONNECTION'],'timing':['ACTUAL_CONCURRENCY_RESOURCES_NO_SERIAL_GAPS']})

def fields():
    result=[]
    proposals={'protocol_id':0,'mbap_bytes':7,'connection_management':'AUTOMATIC','connection_persistent':True,
                'nodelay':True,'reuseaddr':True,'keepalive':True,'register_bits':16}
    for spec in DECLARATIONS:
        key=spec['key'][3:];item={k:v for k,v in spec.items()if v is not None}
        item.update(label=key.replace('_',' '),category='encoding',scope='network',editable=True,required=key in REQUIRED,
         parameter_origin='DEVICE_CONFIGURATION',default_status='UNKNOWN',validation_relevant=True,simulation_relevant=False)
        conditional=[]
        if key in proposals:conditional=[dict(when={'mt_profile':'GUIDE_1_0B'},value=proposals[key])]
        if key=='port':conditional=[dict(when={'mt_mode':mode},value=port)for mode,port in [('PLAIN',502),('SECURITY_V36',802)]]
        if key=='unit_id':conditional=[dict(when={'mt_destination':'DIRECT_TCP'},value=255)]
        if key=='word_order':conditional=[]
        if key=='compression':conditional=[dict(when={'mt_mode':'SECURITY_V36','mt_tls_version':'TLS1_2'},value='NULL')]
        if conditional:
            for c in conditional:c.update(source=spec['source'],source_revision=spec['source_revision'])
            item.update(default_status='PROPOSED_CONDITIONAL',conditional_defaults=conditional)
        if spec['source']==SECURITY:item['schema_when']={'mt_mode':'SECURITY_V36'}
        result.append(item)
    return result
