from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET,zipfile,io
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import ocpp as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/ocpp-tests.xml'
for path in('backend/communication/technologies/ocpp.py','backend/tests/test_ocpp_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_ocpp_parameter_review')for c in cases)
assert native==167 and len({c.get('classname')for c in cases})==10
primary=root/'work/ocpp-primary';manifest=json.loads((primary/'manifest.json').read_text())+json.loads((primary/'errata-manifest.json').read_text())
for entry in manifest:
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 entry.update(revision=n.SOURCES[entry['url']],read_scope=n.SOURCES[entry['url']],individual_local_tests_completed=True)
(primary/'reviewed-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for name,version in [('v16',n.VERSIONS[0]),('v201',n.VERSIONS[1]),('v21',n.VERSIONS[2])]:
 with zipfile.ZipFile(primary/(name+'.zip'))as package:
  if name=='v16':members=package.namelist();actual={Path(v).stem for v in members if '/json/'in v and v.endswith('.json')and not v.endswith('Response.json')}
  else:
   schema=zipfile.ZipFile(io.BytesIO(package.read(next(v for v in package.namelist()if v.endswith('part3_JSON_schemas.zip')))))
   actual={Path(v).stem.removesuffix('Request')for v in schema.namelist()if v.endswith('Request.json')}
   if name=='v21':assert {Path(v).stem for v in schema.namelist()if v.endswith('.json')and not v.endswith(('Request.json','Response.json'))}=={'NotifyPeriodicEventStream'}
  assert set(n.CALL_ACTIONS[version])==actual,(version,actual-set(n.CALL_ACTIONS[version]),set(n.CALL_ACTIONS[version])-actual)
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='ocpp')['form_parameters']};after={v['key']for v in registry.parameter_fields('ocpp')}
meanings={v['key']:v['description']for v in n.DECLARATIONS}
meanings.update(payload_bytes='Actual application bytes distinct complete encoded JSON/SOAP, escaping/whitespace, wrapper, WebSocket/TLS and selected bearer. No fixed8-byte proposal or65535 universal maximum. Actual directional device/action limits remain explicit.')
spec=dict(technology='ocpp',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Each declared field meaning/type/unit/bounds/applicability/dependencies/source/default provenance reviewed. Public OCA1.6 Edition2 JSON/SOAP/core with errata;2.0.1 Edition4 and2.1 Edition2 December2025 Parts2/4/appendices, and2026-06 errata (2.0.1 July13 publication) reviewed in affected sections. Schema action names checked against packages. Errata2.1 printedpage25/PDF29 rendered and visually inspected. Entire803-page use-case certification/state suite not claimed executed.',
 'Industry neutral application profile has no mandatory Ethernet/CAN scalar rate, MTU/VLAN/duplex, fixed8 or65535 payload. Actual edition, JSON-WebSocket versusSOAP1.2 HTTP, transport/peer/schema/schedule/acceptance/security source required. Version-specific subprotocol and SOAP1.2 proposed; heartbeat/CALLtimeout/retry/queues/password/IDs/device limits remain actual configured evidence rather than example300/30/3/60 defaults.',
 'UTF8 whole JSON wrapper bytes include escaping/whitespace. Strict array arity CALL/SEND4,RESULT3,ERROR/RESULTERROR5, integer message type/string IDs/actual action/objectpayload; null/non-finite constants/duplicate members/unpaired Unicode/field mismatch rejected. This is envelope validation, not complete action payload codec/state execution. Declared actual uncompressed/compressed/device sizes independent transport MTU and TLS fragment.',
 'Only2.1 has CALLRESULTERROR5/SEND6. SEND NotifyPeriodicEventStream has no response; source errata corrects stale NotifyEventStream example. Errata example itself contains equals instead ofcolon; invalidJSON is rejected rather than copied. Actual official schema names determine CALL action edition scope. Per-sender pendingCALL0 on this connection, matchingrequest/connection/outcome and ID uniqueness/retry evidence separate. SEND may coexist with pendingCALL. Response correlation is distinct functional ACCEPTED/freshness.',
 'Legacy1.6 FormationViolation/OccurenceConstraintViolation spelling deliberately preserved; newer Format/Occurrence spellings separate. Current errata deprecates MessageTypeNotSupported and removes contradictory fallback. Rendered strikeout confirms ignore entire unknown message, not just payload. Native configured message types outside selectededition rejected; no receiver-state-machine interoperability claim.',
 'New-edition station identifier allowed character set and48maximum versus legacyspace example and actual Basicusername withoutcolon; JSON36ID versusunbounded WS-A URI identifier. TLS1.2+ for selectednew profile2/3, actual certificate/hostname/time validation/source, credential length-only16minimum andreportedmax40..64. Secret notstored. Role-qualified CSMS/localcontroller compression support versus actualnegotiation, optional station support,legacyuncompressed. HTTP2 allowance qualifiedbycurrenterrata rather than mandatoryoldHTTP1.1.',
 'Actual transaction linearresubmit interval differs reconnect doubling/cappedstep/jitter. Heartbeat inactivity/CSMStime versusWebSocketping/pong;ping0disablesclientinitiation notserverresponse. Accepted bootinterval isheartbeat, pending/rejected retryinterval andzero selectsownanti-floodpolicy; pendingCALLtriggerexceptions distinct.1.6metersample/clockaligned0disablesreporting, connectorPreparing timeout notnetwork timeout. No nominalfrequency capacity claim.',
 'SOAP1.6 uses SOAP1.2, synchronous HTTP, slashaction, WS-A MessageID/From/anonymousReplyTo and RelatesTo onresponseonly; not JSON36/WebSocket/SEND. SOAPfaultretry exception fortransactionmessages noted in source, actual error/state executor notimplemented.',
 f'{len(cases)} isolatedSQLtests PASS; {native} OCPP plusnine sharedsuites. Confirmedheartbeat42/timeout17/stationidentity and70000applicationbytes retained after rejectedforeign10M rate. MODEL_MISSING explicit; device/protocol/physical certification andactualcapacity notinferred fromvalidfields.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} OCPP and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['All action payload/state/EV charging andsecurity certification, actualhandshakes/queues/offline delivery/schedule/functionalE2E proof. Source/envelope configuration validation isnot certifiedOCPP device compatibility or capacity.', 'Cumulative consumer checks, README, releasegate andexact-image production pending.'])
(root/'work/ocpp-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
