from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import profibus_dp as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/profibus_dp-tests.xml'
for path in('backend/communication/technologies/profibus_dp.py','backend/tests/test_profibus_dp_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_profibus_dp_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('profibus_dp'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/profibus-primary';manifest=json.loads((primary/'manifest.json').read_text())
scopes={'system2016':'PI4/2016 printedpp2-5 physical/industry-neutral DP paths, pp6-10 protocol and GSD. Table2 has printed distance/unit errors; DP cable distances instead qualified ABB physical.',
 'step7v13':'SiemensA5E03775446-AC12/2014 printed45-54 actual source-qualified bus limits/HSA/constantcycle.',
 'abb-master':'ABB AutomationBuilder2.8.1 CM592-DP full bus parameter table. Unit conversion text has missing /1000; physical dimensional conversion applied explicitly.',
 'abb-physical':'ABB full TypeA cable/bps/segment load/line-end termination text. It lists9.6/19.2/93.75kbaud for1200m;45.45kbaud independently checked in SiemensARDOCELL08/06 Table5.2.',
 'pyrometer-dp-cable':'SiemensARDOCELL PZProfibus instruction manual08/06 IdentNr515634, printedp16 Table5.2 explicitly45.45kbaud1200m. Downloaded original72pages; only cable table used, no foreign PA overview assumptions.',
 'saia2019':'26-860ENG02 2019-01-31 printed1-5/1-6/1-9 and3-2..3-8,4-9/4-10 bounds and rate-dependent defaults; configurator presets not universal.',
 'spc3v16':'SPC3V1.6 April2009 printedp23 three WD states/actual factor restrictions. No device watchdog fabricated.',
 'acromag2002':'8500-698A02M000 2002 tutorial UART/framing/SAP/device/state, cross-checked 1997PNO original. Tutorial token diagram and divide255 checksum not used.',
 'pno1997':'Manufacturer-hosted original924pagePNO1997 document; scoped Part4 pp114-118/120-133 read and token diagram verified. Not whole current IEC specification.'}
reviewed=[]
for entry in manifest:
 name=Path(entry['path']).stem
 if name not in scopes:continue
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 reviewed.append({**entry,'read_scope':scopes[name]})
(primary/'dp-reviewed-manifest.json').write_text(json.dumps(reviewed,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='profibus_dp')['form_parameters']};after={v['key']for v in registry.parameter_fields('profibus_dp')}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings.update(bitrate='Lowest listed native DP9600baud unconfirmed proposal; agreed device rates and actual bearer/token/polling/qualified configurator determine timing.',payload_bytes='Whole application bytes distinct separately244cyclic input/output, FDL246dataunit/255whole UART frame and segmented acyclic data. No8byte/1500application defaults.')
spec=dict(technology='profibus_dp',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES)+['https://cache.industry.siemens.com/dl/files/969/25553969/att_7167/v1/pzdpsi_af4xx_e.pdf'],revisions=list(n.SOURCES.values())+['SiemensARDOCELL PZ08/06 Table5.2 printedp16'],
 scope=['Each exported declared field meaning/type/unit/bound/dependency/default/provenance individually reviewed against scoped downloaded original primary sources. Source contradictions identified; selected manufacturer qualified rather than silently generalized.',
 'Own FDL path: active masters may be multiple, one simultaneous token authority; class1 cyclic owner/class2 acyclic/passive slave, active-only HSA versus passive up126,126commissioning not operational. Actual unique station ring/GSD/mapping/schedule/acceptance remain source-bound.',
 'RS485 TypeA rate-qualified lengths/load32 including repeater/126overall/two powered terminations and135..165Ohm/<30pF/m/110Ohm/km. IS/optical require independent registered physical qualification and cannot inherit TypeA limits. No MBP PA or CAN/Ethernet timing fallback.',
 'Source-qualified SiemensSTEP7V13 dependent TSL/TSDR/TSET/TQUI/TID/TRDY/TTR limits differ ABB2.8.1 and SaiaENG02; rate-dependent Saia defaults explicit conditional. Lowest9600proposal distinct actual supported/agreed rate, TTR/scan/watchdog/addresses/IObuffers unknown.',
 'UART11NRZ, SYN>=33 only action/token, no inter-character idle; cyclic244bytes per direction distinctFDLDU246/SD2LE249/whole255. SimpleSAP count0..2, cyclicdefaultSAP absent; SD1six/SD3fourteen/token3/SCone octets. Actual full FCS/address/duplicate-sequence checks required before frame_valid, no complete codec executor claimed.',
 'Native bit-time->us conversion and response-first-character TSL distinct application deadline. DP-V1/V2 capabilities actual GSD. SPC3selected watchdog1/10ms/factors1..255 with both1 forbidden, separate baud control10ms and DP control expiry; no fabricated safe endpoint or generic timeout.',
 'Functional cyclic acceptance requires actualDATA_EXCHANGE/mapping/frame validity and correlated freshness, SRD SC does not establish accepted data. Existing187500baud/station17/slot200 preserved; foreignCAN/Ethernet fields rejected.',
 f'{len(cases)} isolated tests PASS, {native} native and nine shared suites.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} DP and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['Complete current licensedIEC/PI specifications and optional bridge/IS/optical/device profiles; fullFDL codec/token/GAP/polling/acyclic/retry executor, actual physical capacity/hardware E2E/safety. Runtime remains MODEL_MISSING, no source proposal becomes actual evidence.',
 'Remaining profiles, cumulative consumers, README, release gate and exact tested-image production delivery remain pending.'])
(root/'work/profibus-dp-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
