import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import modbus_tcp as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/modbus_tcp-tests.xml'
for path in ('backend/communication/technologies/modbus_tcp.py','backend/tests/test_modbus_tcp_parameter_review.py',
 'backend/communication/technologies/catalog.py','backend/communication/technologies/core/physical.py','backend/tests/test_technology_standard_defaults.py'):
    assert xml.stat().st_mtime_ns >= (root/path).stat().st_mtime_ns,('stale receipt',path)
parsed=ET.parse(xml);suites=parsed.findall('.//testsuite')
assert suites and all(int(s.get(k,'0'))==0 for s in suites for k in ('failures','errors','skipped'))
cases=parsed.findall('.//testcase');native=sum('test_tcp_'in c.get('name','')for c in cases)
assert native>=178 and len({c.get('classname')for c in cases})==10
primary=root/'work/modbus-primary';manifest={}
for key in ('tcp','security','application'):
    entry=json.loads((primary/(key+'-source.json')).read_text());assert entry['sha256']==hashlib.sha256((primary/(key+'.pdf')).read_bytes()).hexdigest()
    scopes={'tcp':'V1.0b October24 2006 pages4-6 MBAP;10-14 connections/ports/keepopen/access;18-19 socket resources and historical TCP defaults;22-26 TID/unit/response/no standard timeout;29-31 server/busy/resource behavior. Illustrative buffers300/900 and transaction16 not universal hardware maxima.',
      'security':'MB-TCP-Security-v36 2021-07-30 pages6-7 overview;10/14-19 normative TLS/X509v3/cipher/role/fragment/renegotiation statements;20 TLS record/application-layer structure. Full PKI/TLS runtime/cipher qualification not performed; policy source/reference remains actual.',
      'application':'V1.1b3 pages3-11/11-12/15-19/20/22-23/29-30/38/43/47-49: exact PDU/endian/function/address/quantity/exception semantics; native TCP excludes explicitly serial-only FC7/8/11/12/17.'}
    entry.update(read_scope=scopes[key],individual_local_tests_completed=True);manifest[key]=entry
(primary/'tcp-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='modbus_tcp')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('modbus_tcp')}
native_fields={v['key']:v['description']for v in m.DECLARATIONS}
native_fields['payload_bytes']='Actual complete function-specific PDU data0..252, including addresses/counts/metadata. Function1 producesPDU<=253; MBAP7 yieldsADU8..260; actual TCP/IP/TLS/PHY bytes and resource/schedule evidence separate.'
spec=dict(technology='modbus_tcp',native=native_fields,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),revisions=list(m.SOURCES.values()),
scope=[
 'Every declared parameter individually reviewed for meaning/applicability/types/units/bounds/dependencies/source/proposals/provenance. Explicit Modbus common application-PDU declarations separately exercised through TCP; serial7/8/11/12/17 excluded from native PUBLIC TCP and registered extensions require actual source.',
 'No own Ethernet10M clock, duplex/MTU/VLAN or forcedphysical alias. Actual registered TCP/IP/PHY path required, industry-neutral explicitbinding with empty defaultstack. MBAP7/PDU1..253/ADU8..260 and lengthunit+PDU2..254 exact; headerhex validates real network-order TID/protocol0/length/unit/function, no serialCRC/LRC.',
 'TIDuint16 unique only among pendingrequests on same connection, echoed with unit and actualconnection identity. Unknownpending/otherconnection blocked. DirectUnitFFproposal/0accepted versus gateway0..247 and actual serialtranslation/network source, no manufactured device addresses.',
 'Several TCP requests possible: resourcecap and uniqueTIDs actual. Guideexample client1..16 not universalcap; registeredmanufacturer128 tested. Connections/device caps and send/receive buffers below actualdriverresources; no universal900buffer orCANqueue. No fixedresponse timeout: actual timeout strictlygreaterthan pathresponsebound; legacy75s/2h/75sexamples not copied.',
 'Plain502 distinct ModbusSecurity802 without MBAPchange. V36 requires TLS1.2-or-newer/X509v3/mutualpeer/trustvalidation, actualsuite/IANA/currentpolicy references. TLS1.2 MFLextension512support/RFC5746 and conditionalRSA/ECCmandatorysuite/P256capabilities checked; actualfragment/record limit separate and newerTLSscoped. No full TLS/PKI implementation or capacity manufactured.',
 'OptionalroleAuthZ uses actual one ASN1UTF8String/OID1.3.6.1.4.1.50316.802.1 and vendor/userconfigurablerights; absentroleNULL, no defaultOperator. Deniedrequest returns exception1. UTF8bytecount distinctcodepoints. Securityfields rejected onPLAIN; auth-onlyNULLbulk distinct mandatoryauthentication and applicationconfidentiality requirement; deprecated/registered suites require currentactualpolicy.',
 f'{len(cases)} isolated SQL tests passed, including{native} TCP tests and nine shared suites. ConfirmedUnit0/TID65535/4200ms timeout remain saved after rejected Ethernetrate addition. No runtimecapacity certificate from scalarVALID.'
],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} TCP and nine shared suites',complete_release_gate='NOT_RUN'),
not_certified=['Complete Modbus runtime all-function decoder/traffic/client-server gateway or TLS/PKI/cipher acceptance; MODEL_MISSING remains explicit. Actual lowerpath resources/schedule and E2E safety/security acceptance still required.',
'Full cumulative tests, release gate and production delivery pending.'])
(root/'work/modbus-tcp-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps({'tests':len(cases),'native':native,'native_fields':len(native_fields),'removed':len(before-after)}))
