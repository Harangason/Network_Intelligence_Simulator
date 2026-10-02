from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import opc_ua as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/opc_ua-tests.xml'
for path in('backend/communication/technologies/opc_ua.py','backend/tests/test_opc_ua_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_opc_ua_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('opc_ua'))+15 and len({c.get('classname')for c in cases})==10
primary=root/'work/opc-ua-primary';manifest=[]
for entry in json.loads((primary/'manifest.json').read_text()):
 if entry['path'].endswith(('part4.html','part6.html','part7.html'))or'/profile/get/'in entry['url']:
  file=root/entry['path'];assert hashlib.sha256(file.read_bytes()).hexdigest()==entry['sha256']
  if '/profile/get/'in entry['url']:
   r=json.loads(file.read_text())['result'];assert r['profileUri'] and r['description']
   entry.update(profile_uri=r['profileUri'],profile_version=r['version'],last_update=r['lastUpdateTime'],read_scope='Current public profile description/URI/revision. Numeric releaseStatus not relabelled. No complete profile inventory or algorithm conformance-unit review claimed.')
  else:entry.update(revision='v1.05.07',read_scope='Scoped official HTML sections for declared service/type/mapping bounds. Not whole-specification certification.')
  manifest.append(entry)
file=primary/'part8-deadband.html';manifest.append(dict(path=str(file.relative_to(root)).replace('\\','/'),url=n.P8,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),revision='v1.05.07',read_scope='PercentDeadband7.2, actualAnalogItem EURange and0..100 bounds.'))
(primary/'reviewed-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='opc_ua')['form_parameters']};after={v['key']for v in registry.parameter_fields('opc_ua')}
meanings={v['key']:v['description']for v in n.DECLARATIONS}
meanings['payload_bytes']='Actual application bytes distinct assembled unencrypted UA message body, directional chunks/security/wire overhead and selected bearer. No universal8byte/65535 ceiling or automaticEthernet rate.'
spec=dict(technology='opc_ua',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Every declaredfield meaning/type/unit/bounds/dependencies/applicability/source/default provenance reviewed. Part4/6/7v1.05.07 scopedpublisherHTML, Part8section7.2 andcurrentprofileAPI snapshots hashed; no fullsecurityprofileinventory/certification or releaseStatusnumericlabel inference.',
 'Application protocol industry-neutral, distinctUA-TCP/UACP-WebSocket/JSON/OpenAPI/HTTPS actualendpoint/encoding/peer. No Ethernet10M/MTU/VLAN/CAN8byte/queue256 fallback; no blanket65535payload maximum. Physicallayer andcapacityMODEL_MISSING explicit.',
 'UACPcurrentversion0 proposal. SecurityfamilyqualifiedHELminimumECC1024vsRSA/None8192; ACKmin follows opposite-directionHEL size. Directionalclient/server chunk/message/chunkcount limits; zero means no limit for messagebody/chunkcount only. Wholechunks includeheader; exactlittle-endian UInt32header/channel andmessage/chunktype checks, not fullbinarycodec or cryptographic validation.',
 'Endpoint UTF8octets plusbinaryStringfour-byte length prefix checked againsttableencodedless4096; sourceerrornarrativeexceeds4096 discrepancy resolvedby normativefieldtable. URLidentity actual, no inventedlocalhostendpoint. SecurityURI actualsource; currentforbiddenECC_curve25519 rejected; currentChaCha20Poly1305 LegacySequenceNumbersFALSE distinctRSA/ECCprofilefamily.',
 'Actualsequenceincrement andpolicyqualifiedwrap UInt32 exact, tokenrenew doesnotreset andsame-token reuseinvalid; responsependingRequestId/connectioncorrelation separatefunctionalacceptance.75percentrenewtime SHOULD proposal basedonactualgranted lifetime, not guaranteedscheduler. Trust/certificate/nonce/full-security execution requires actualsource, noautomaticallyinsecureNone proposal.',
 'RequestedandrevisedSession/Subscription/Sampling/Queuevalues separate. CreateSubscriptionillegalrevisable requests canberevised; actualgrantedlifetime >=3*actualkeepalive; requestedpublish<=0fastest, negativesampling=-1inherited withoutlaterautomaticpublishcoupling. Samplingservermaximumexception actualsource; dataqueue0/1 revised1 versusactualeventminimum/maximum sentinels, falsequeueoverflow replaceslast.',
 'Percentdeadband0..100 requiresactualnumericAnalogItem EURange; thresholdpercent*rangewidth, no universal0..100engineeringunitrange. ReadmaxAgebest-effortandtimeoutHint0no-timeout do notprove sourcefreshness/E2E. OverallserviceGood separateitemGood/Uncertain/Bad/reserved, explicitpermissionforUncertain andactualfunctionalacceptance/freshness.',
 'WebSocketUACPbinarychunk limits distinctJSON/OpenAPI internalreceiverlimits, noHEL/ACKfieldsinJSON. Publishedmappingtable opcua+uajson controls ratherthanstale narrative opcua+json; OpenAPItextUTF8 versusgzipbinary. Noactualaccess-token secrets stored.',
 f'{len(cases)} isolatedSQLtests PASS; {native} native andnine sharedsuites. ConfirmedSession42000/publish75/queue42/70000applicationbytes preservedafterrejectedforeignCANrate.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native}OPC-UA andnine sharedsuites',complete_release_gate='NOT_RUN'),
 not_certified=['FullUAservice/codec/cryptographic/state-machine execution, allsecurity/transportprofileconformanceunits, actualphysicalservicecapacity andfunctionalE2E certification; selectedsourcebounds are not runtime evidence.','Cumulativeconsumers, README, releasegate andexactimageproduction remainpending.'])
(root/'work/opc-ua-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
