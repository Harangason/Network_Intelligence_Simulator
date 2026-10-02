"""Record fresh source-qualified MMS scalar and shared-consumer verification."""
import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import mms as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
xml=folder/'individual/mms-tests.xml'
for relative in ('backend/communication/technologies/mms.py','backend/communication/technologies/catalog.py','backend/tests/test_mms_parameter_review.py'):
    assert xml.stat().st_mtime_ns >= (root/relative).stat().st_mtime_ns,('stale receipt',relative)
parsed=ET.parse(xml);suites=parsed.findall('.//testsuite')
assert suites and all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
cases=parsed.findall('.//testcase');native_count=sum('test_mms_'in c.get('name','')for c in cases)
assert native_count>=173 and len({c.get('classname')for c in cases})==10
primary=root/'work/mms-primary';manifest=json.loads((primary/'manifest.json').read_text())
tree=json.loads((primary/'tree-v1.6.json').read_text());assert not tree['truncated']
blobs={v['path']:v['sha']for v in tree['tree']if v['type']=='blob'}
scopes={
 'stack_config.h':'Compile directives32-78 and210-306 read, conditional WITH_MBEDTLS, separate resources/services/windows. Header1 does not unconditionally enable TLS.',
 'mms_client_connection.c':'Constructor/createInternal1596ff, timeout/window setters1783-1889, connect1941ff and invocation type. Sample AP titles not installed defaults; idleThreadSleep10 not universal E2E.',
 'mms_client_initiate.c':'Complete request/response/conclude encoding/parser read, CBB11/services85 padding, negotiated compile caps and nesting behavior.',
 'mms_association_service.c':'Initialization and parse/create initiate sections read; minimum128, compiled caps, optional configured minimum, runtime service flags, CBB intersection and emitted version1.',
 'cotp.c':'38-115,245-398,470-715 read; compiled cap vs negotiated exponent7..13, normalDT3, TPKT4, fragment/reassembly calculations.',
 'iso_connection_parameters.c':'Complete setter/config source read; AP-title actual10byte BER buffer, separate selectors/endpoints, credential API. Actual secrets not copied.',
 'iso_connection_parameters.h':'Enum/authenticator/types and selector size contracts, AP/AE optional identity/setters read. API certificate enum not executable ACSE certificate support.',
 'acse.c':'39-149 authentication/password/TLS callback and636-820 association size/identity/auth encoding read. Absent authenticator accepts; non-password API enum does not encode certificate.',
 'iso_session.c':'NormalDATA270-330, initialization functional-unit/selector/version2 and phase parsing read; DATA4bytes not association fixed framing.',
 'iso_presentation.c':'OID/context declarations and899-925 initialization plus actual context parsing read; MMS3/ACSE1 constructor only, BER overhead variable.',
 'mms_common_internal.h':'1-70 read, default nesting10 and file resources; nesting not assumed universal negotiated cap.',
 'InitiateRequestPdu.h':'Complete generated type read; localDetailInteger32, directionalInteger16, nestingInteger8 optional.',
 'InitiateRequestPdu.c':'Generated descriptor members read with delegated constraints to integer types.',
 'InitRequestDetail.c':'Generated version/CBB/services member descriptor read; delegated constraints not full licensed MMS norm.',
 'InitResponseDetail.c':'Corresponding generated response descriptor read.',
 'Integer8.c':'Constraint section1-42 read, signed8bit wire type distinct positive usable nesting.',
 'Integer16.c':'Constraint section1-42 read, signed16bit version/windows distinct positive usable configuration.',
 'Integer32.c':'Constraint section1-42 read, signed32bit localDetail distinct positive actual PDU cap.',
 'Unsigned32.c':'Constraint section1-42 read, exact0..4294967295 invocation domain.',
 'rfc1006.txt':'Sections4-6 read; class0/TCP102/TPKTversion3/header4/min7/max65535/TPDU65531. RFC statedTSDU65524 preserved distinct source library normalDT fragment formula; no invented alignment.',
 }
for entry in manifest:
    file=root/entry['path'];data=file.read_bytes();assert entry['sha256']==hashlib.sha256(data).hexdigest()
    if entry['source'].startswith('https://raw.githubusercontent.com/'):
        path=entry['source'].split('/libiec61850/',1)[1].split('/',1)[1]
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[path],path
        entry['verified_commit']=m.COMMIT
    entry['read_scope']=scopes.get(file.name,'Downloaded supplementary artifact; not relied on for any native field or normative certification.')
    entry['individual_local_tests_completed']=True
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='mms')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('mms')}
native={v['key']:v['description']for v in m.DECLARATIONS}
native['payload_bytes']='Actual service application octets fit complete encoded MMS PDU, actual BER overhead and negotiated/compiled cap; independent TPKT/COTP/TCP/IP/TLS/PHY lengths. No universal65535 cap.'
removed_meanings={**m.REMOVED,
 'duplex':'MMS needs an explicitly bound reliable full-duplex transport; actual Ethernet PHY duplex is a separate canonical lower profile, not MMS application default.',
 'mtu_bytes':'Actual lower-link MTU distinct negotiated MMS PDU, COTP TPDU and TPKT lengths; no inherited1500byte MMS cap.',
 'vlan_id':'Actual Ethernet VLAN belongs only to explicitly selected lower-network profile; generic MMS does not imply VLAN0.'}
spec=dict(technology='mms',native=native,removed={k:removed_meanings[k]for k in before-after},sources=list(m.SOURCES),
 revisions=list(m.SOURCES.values()),scope=[
 'Every declared native parameter reviewed for meaning/applicability/types/units/bounds/dependencies/source/proposal/provenance; retained NIS scenario fields are explicit application policies. Generic MMS industry-neutral, IEC61850 ACSI/SCL separate profile.',
 'Pinned libiec61850 v1.6 commit verified against Git tree blob hashes. Factory128 minimum/65000 compiled PDU,5 separate directional windows and8192 compiled COTP are conditional proposals; actual negotiation/build/source required. No inherited Ethernet10M/CAN queue/retry/priority parameters.',
 'Positive usable Integer32 PDU /Integer16 directional windows/version /Integer8 nesting and Unsigned32 invocation domain checked. Internal-1 constructor sentinel not actual usable capacity. Actual request/response source and local compile limits required for DATA; no nesting10 hard-cap where parser negotiates otherwise.',
 'MMS application bytes, actual BER overhead and complete PDU separated from peer/local negotiated caps. Calling/called independent. CBB11bits with5padding and services85bits/11octets with3padding, source client request defaults distinct server runtime service bitmap. No automatic dataset/read/write permission.',
 'RFC1006 TCP102 versus libraryTLS3782, TPKT3/header4/min7/max65535 and class0. Negotiated libraryTPDU128..8192 powers2 distinct compiled1024..8192. NormalDT3 and exact per-fragment payload/ceil(TSDU)/7byte total overhead tested; TCP segmentation and TLS overhead not folded into COTP count.',
 'Normal DATA session4/ACSE0 and actual variable presentation overhead separated from association phase. ContextMMS3/ACSE1 constructor proposals distinct actual negotiated IDs. No full executable OSI/MMS runtime codec or capacity manufactured.',
 'Local/remote T0..4/S0..16/P0..16 selector hex octet bounds independent. Actual AP-title OID grammar and qualified10byte BER output buffer checked; encoded size is an actual encoder record rather than guessed text length. No example AP-title/qualifier12 installed default.',
 'TLS requires actual compiled support, credential reference, trust result and security source. WITH_MBEDTLS is conditional; absent authenticator accepts in inspected source. Password/TLS credential paths distinguished API-only certificate enum. No credentials/default passwords copied.',
 'Request5000/connect10000/file-task2000ms implementation proposals separate functional deadlines. Threading/resources/dataset/file/keepalive factory limits source-qualified; rename compile0 and runtime service gates kept explicit.',
 f'{len(cases)} tests passed isolated SQL including{native_count} MMS tests and nine shared suites; nondefault TCP1102, calling2, timeout7200 and58000byte confirmed application survive rejected PDU edit. Cumulative tests/release gate/deployment remain required.'
 ],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native_count} MMS and nine shared consumer suites',complete_release_gate='NOT_RUN'),not_certified=[
 'Full licensed ISO9506/ISO8073/OSI normative text, all generic/vendor mappings and devices, complete runtime BER/OSI/TCP/TLS/PHY executors or standards conformance.',
 'Actual device identity, negotiated association trace, runtime services and window scheduling, physical capacity, calibrated E2E/functional/safety/security acceptance. ScalarVALID and factory proposals are not installed evidence; MODEL_MISSING remains explicit.'
 ])
(root/'work/mms-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps({'tests_passed':len(cases),'native_tests':native_count,'native_fields':len(native),'removed':len(before-after)}))
