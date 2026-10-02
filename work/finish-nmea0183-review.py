from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import nmea0183 as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/nmea0183-tests.xml'
for path in('backend/communication/technologies/nmea0183.py','backend/tests/test_nmea0183_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_nmea0183_parameter_review')for c in cases)
assert native==149 and len({c.get('classname')for c in cases})==10
primary=root/'work/nmea0183-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 entry.update(revision=n.SOURCES[entry['url']],read_scope=n.SOURCES[entry['url']],individual_local_tests_completed=True)
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='nmea0183')['form_parameters']};after={v['key']for v in registry.parameter_fields('nmea0183')}
meanings={v['key']:v['description']for v in n.DECLARATIONS}
meanings.update(bitrate='Actual serial baud: selected Standard4800 versus HighSpeed38400, separately configured device UART. Registered network/host carriage has no mandatory serial bitrate. Actual transmit/listener settings and all protocol traffic separate.',payload_bytes='Actual application bytes, not fixed8, sentence82, CAN PGN or lower-layer MTU. Actual address/commas/XOR/CRLF and optional registered wrappers counted separately.')
spec=dict(technology='nmea0183',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Each declared field meaning/type/unit/bounds/applicability/dependencies/source/default provenance reviewed. Publisher NMEA0183 4.30 overview, u-blox20 HPG2.00 interface50.02 R01May2025 protocol2/CFG/defaults and PRO-MUX-1 Issue1.00 reviewed. u-blox pages19 and192 rendered and visually checked. Full licensed4.30 specification not read; device capabilities remain source qualified.',
 'Industry neutral serial Standard4800 andHS38400 one talker/many listeners conditional baseline. Actual receiver matching,8N1 and10wirebits perchar versus configurable device UART. No inherited NMEA2000 250k, Ethernet MTU/VLAN, CAN queue/retry. Registered TCP/UDP/USB/I2C/SPI carriage does not require serial baud. Focused failures exposed unconditional required rate fields; matching allowed-condition lists now keep applicable serial requirements and exclude host/network rates.',
 'Printable ASCII complete sentence with uppercase/digit address, commas including null fields, XOR8 excluding delimiter/star/CRLF, two hex characters and exact CRLF. Primary ZDA checksum67, invalid GLL checksum42 and zero XOR fixture accepted. Standard TTSSS distinct proprietary Pmanufacturer/PUBX. Full formatter-specific field/unit/quality codecs and tag/authentication decoding not implemented.',
 'Body+6 sentence bytes, optional82 lengthlimit differs application data and registered wrapper. u-blox highprecision excludes82/compatibility and may exceed82; no global82 maximum. Per-port current enables and other UBX/RTCM/SPARTN traffic actual. Message divisor0 disables one message not whole port; measurement*navigation*divisor period and all stream framed load validated separately.',
 'u-blox current CFG-NMEA edition codes decimal21/23/40/41/42, not older hex0x4B. MULTI automaticGN, GSV GNSS-specific or explicit override. QZSS GP for2.3..4.10 andGQ4.11; strict edition4.11 QZSS/NavIC,4.10+ Galileo/BeiDou. Product support not inferred from newest edition. Invalid data output differs application VALID acceptance and current timestamp/freshness evidence.',
 'PRO-MUX-1 selected inputs1..4<=38400,5..8=4800,output1<=115200,2..6<=38400,separateSERIAL115200. Differential2.1V rating at100ohm,20mA output, input±35V only<1000ms versuscontinuous±15V; input2500V/output1000V/separateSERIAL1500V isolation, supply9..35V/operating-15..55/RH0..80. Device Ethernet10/100 carriage is not universal NMEA link rate or IP endpoint default.',
 f'{len(cases)} isolatedSQL tests PASS: {native} NMEA0183 plusnine shared suites. Confirmed9600 device UART,long highprecision application sentence and invalid-fix flag persisted and retained after rejected foreign MTU. MODEL_MISSING remains explicit; reviewed scalar fields do not execute a certified receiver/multiplexer/codec or prove E2E capacity.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} NMEA0183 and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['Full licensed current edition/PGN conversion, all formatter codecs/validity/security, actual device buffer/service/physical loading and capacity; source-qualified configuration is not NMEA device certification or functional E2E acceptance.','Cumulative consumer checks, README, release gate and exact-image production delivery pending.'])
(root/'work/nmea0183-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
