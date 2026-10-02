from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import one_wire as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/one_wire-tests.xml'
for path in('backend/communication/technologies/one_wire.py','backend/tests/test_one_wire_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_one_wire_parameter_review')for c in cases)
assert native>=142 and len({c.get('classname')for c in cases})==10
primary=root/'work/one-wire-primary';manifest=[];seen=set()
for filename in('article-web-read.txt','timing-web-find.txt','electrical-web-read.txt','timing-commands-web-read.txt','config-web-read.txt','bridge-rom-web-read.txt'):
 path=primary/filename;body=path.read_text(encoding='utf-8');sources=[url for url in n.SOURCES if url in body];seen.update(sources)
 assert sources and 'Source:'in body
 manifest.append(dict(path=str(path.relative_to(root)).replace('\\','/'),kind='WEB_TOOL_TEXT_EXCERPT',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),urls=sources,source_revisions=[n.SOURCES[url]for url in sources],
  read_scope='Publisher extraction of relevant article/table/register/command/power/CRC sections. Snapshot hash is the returned excerpt, not an original PDF binary hash. Direct publisher binary downloads failed; no full PDF download or visual inspection claimed.'))
assert seen==set(n.SOURCES),(seen,set(n.SOURCES))
(primary/'reviewed-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='one_wire')['form_parameters']};after={v['key']for v in registry.parameter_fields('one_wire')}
meanings={v['key']:v['description']for v in n.DECLARATIONS}
meanings.update(payload_bytes='Actual selecteddevice/function application bytes distinct ROM/search/reset/CRC/conversion/power andhost wrappers. No universal8byte or255byte proposal, and no false scalarbaud capacity guarantee.')
spec=dict(technology='one_wire',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Every declaredfield meaning/type/unit/bounds/dependency/applicability/source/default provenance reviewed. Source sections read through publisher web extraction, saved hashedtext excerpts; no binaryPDFhash or visually inspected table claim. Standard/overdrive actualcapabilities, singlemaster open-drainLSBfirst and64bitROM wireorder distinct hostI2C.',
 'Standard mode and nominal16.3kbps label proposed separately. Source-qualified AN126 table versuscode A/E discrepancy retained; DS2482Rev11 table65.8..72.8us (typ69.3) controls rather than contradictory narrativewithin65. Recovery-included period distinct legacy active slot+recovery; rise/fall/interrupt/topology actual evidence not guessed.',
 'DS18B20Rev6 standard-only selectedtarget, DS1990A/AA distinct recovery1/5us, minimumperiod61/65us, supply andreset maximum. Actualtarget andmaster operatingrails/ambient distinctabsolute/storagelimits. Typical hardwaretimes are unconfirmed proposals, not guaranteedactualmeasurements.',
 '64bitROM preserved as eightwireoctets, family+sixidentitybytes+CRC; TARGETrole requiredROM, MASTERno inventedslaveaddress. ExactMaximCRC8 initial0/reflected8C overdeclaredprefix matches actuallastbyte, separateModbusCRC16. InitialsyntheticROMtest hadwrongD1, rejected; corrected8C independently derivedwithnormal0x31bitregister. Scratchpad50054B467FFF0C10 CRC1C andASCII123456789 CRC A1 crosschecked independently.',
 'ReadROMsingledevice,64triplets192slots persearchpath; IDdevicesMatch/Skip nofunctionalapplication. DS18B20ROM/functionopcodes independent.9..12-bit conversionworst93.75/187.5/375/750ms distinct wirebudget; EEPROM10ms;parasitestrongenable<=10us anduninterruptedhold nobusactivity/polling. Actualclock/current/load/identity/acceptance never auto-confirmed.',
 'DS2482hostI2C100kproposal max400k, ADpins7bit24..27 distinct1WireROM, configlowbits/reservedbit1/highcomplementwrite versusreadupperzero, busy/shortcommandvalidity andselected1WS; standard1nF versusoverdrive300pF actualloadlimit. Datasheet A/AA weakresistor limits explicitly scoped to one target/minimumrecovery; actual qualifiedmultidrop resistance needs ownsource. No invented upper bound on longhighidle for IDdevices. Device-specific transport andfullhardwarephysicalproof remain separate.',
 f'{len(cases)} isolatedSQLtests PASS; {native} native plusnine sharedsuites. Confirmedresolution9/conversion94/host250k/ROM/300applicationbytes preserved afterrejectedforeign10Mrate. MODEL_MISSING remains explicit: configuration rules donot establishcomplete capacity orfunctionalE2E.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native}1-Wire andnine sharedsuites',complete_release_gate='NOT_RUN'),
 not_certified=['Complete device/bridgefunction-state-machine execution, all available1-Wiredevices, physicalrise/current/topology/CRC16/authentication andactualcapacity/E2E certification. Registereddevice requires ownsource.','Cumulative consumers, README, releasegate andexactimageproduction remainpending.'])
(root/'work/one-wire-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
