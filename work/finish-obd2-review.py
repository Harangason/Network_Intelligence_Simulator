from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import obd2 as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/obd2-tests.xml'
for path in('backend/communication/technologies/obd2.py','backend/tests/test_obd2_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_obd2_parameter_review')for c in cases)
assert native==149 and len({c.get('classname')for c in cases})==10
primary=root/'work/obd2-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 entry.update(revision=n.SOURCES[entry['url']],read_scope=n.SOURCES[entry['url']],individual_local_tests_completed=True)
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='obd2')['form_parameters']};after={v['key']for v in registry.parameter_fields('obd2')}
meanings={v['key']:v['description']for v in n.DECLARATIONS}
meanings.update(bitrate='Actual vehicle transport bitrate: J1850 PWM41600/VPW10400, K-line10400, selected CAN250000/500000. Five-baud initialization and adapter UART are separate. DoIP/registered carriage has no mandatory vehicle scalar rate.',payload_bytes='Actual complete application service payload, not CAN DLC8, ELM host ASCII characters or Ethernet MTU. Selected legacy/adapter/segmentation bounds and actual encoded request/response evidence apply independently.')
spec=dict(technology='obd2',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Every declared field meaning, type, unit, bounds, applicability, dependencies, source and default provenance reviewed individually. ELM327DSK v2.2 and STN2120DSA public device sheets reviewed; current SAE J1979-2_202604 publisher metadata inspected. Publisher April/May2026 revision-date disagreement retained. Full licensed SAE/ISO/DigitalAnnex text was not read. ELM pages37 and70 rendered and visually checked.',
 'Industry neutral actual application, vehicle transport and adapter host separation. LegacyJ1979 does not acquire forcedUDS/CAN/Ethernet. Concrete ELM protocol1..9 and 11/29bit250/500k bindings, K-line slow/fast initialization and J1850 modes reviewed. Automatic searching does not identify the actual vehicle transport. DoIP/registered transport requires its own source and does not inherit a CAN rate or4095-byte limit.',
 'CAN identifier width versus extra ISO-TP address byte separated; functional7DF/18DB33F1 binding qualified to legacy CAN. Physical response ID is not inferred by adding8. Classic8-byte DLC, PCI SF/CF1,FF2,FC3, address/padding/data accounting, selected12-bit4095 response limit, source-qualified flow-control modes and hex/service octets reviewed. Full codec, transport state and vehicle operation were not executed.',
 'ELM AllowLong permits8-byte sends only within the selected application; legacy service remains<=7. Multiple legacy CAN PIDs<=6 versus one on other legacy paths. Positive legacy SID=request+64, negative/pending0x78 and NO_DATA are separate from accepted service data. Known response count and filters are required for early return; functional requests do not automatically have one ECU.',
 'ATST0 restores current PP03, not zero milliseconds. Parameter table4.096ms*effective count*CTM gives204.8ms for factoryhex32; narrative approximate200ms retained as approximate. CANCTM1/5 versus nonCAN1. Adaptive timing is not guaranteed vehicle response. Pending nominal5000ms per correlated message does not imply a bounded number or functionalE2E acceptance. SW0 disables wake; PP17 hex92*20.48ms=2990.08ms nominal3s, K-line only. Current configured PP values are not replaced by factory proposals.',
 'Host UART ELM8N1 and qualified pin9600/38400 factory proposal are separate vehicle bitrate. STN62..8M theoretical UART requires actual hardware/driver evidence. ELM4.2..5.5 and STN3..3.6 operating rails and STN-40..85 ambient are separate absolute/storage limits and OBD connector supply. No arbitrary PID/filter/manufacturer service, ECU address or measured timing auto-confirmed.',
 f'{len(cases)} isolatedSQL tests PASS: {native} OBD2 plusnine shared suites. Confirmed KWP10400, configured host115200, custom PP60/245.76ms and encoded request persisted and retained after rejected250k vehicle rate. CurrentOBDonUDS source qualification remains explicit; MODEL_MISSING is not changed by scalar field validation.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} OBD2 and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['Full licensed service/DigitalAnnex definitions, actual vehicle codec/transport/adapter state, electrical and ECU response proofs, complete capacity and functionalE2E acceptance. Source-qualified configuration validation is not certified vehicle compliance.', 'Cumulative consumer verification, README, releasegate and exact-image production pending.'])
(root/'work/obd2-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
