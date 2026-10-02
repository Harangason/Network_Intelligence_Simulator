from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import profibus_pa as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/profibus_pa-tests.xml'
for path in('backend/communication/technologies/profibus_pa.py','backend/tests/test_profibus_pa_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_profibus_pa_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('profibus_pa'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/profibus-primary';m=json.loads((primary/'manifest.json').read_text());reviewed=[]
scopes={'system2016':'PIApril2016 printed4-5 MBP/MBP-IS physical table, DP/PA distinct coupling/device/process profile. PrintedPA2pF/m discrepancy superseded actualPF200nF/km primary guideline.',
 'pno1997':'Manufacturer-hosted original PNO924pages1997; scopedPart9 printed890-891/896-907 synchronous31.25k/Manchester/8bitoctets/PHYdelimiters/CRC16/native timers, not all currentIEC licensed normative documents.',
 'pf-pa2008':'tdoct1681October15 2008 pp4-5/22-26 read: TypeA properties/trunk+allspurs/current/voltage/drop, examples16or22devices/500mA/60mspurs/9.9V margin are NOT universaldefaults.',
 'eh-pa2024':'BA01691D/06/EN/03.24-0, printed64-70/198-201: actual PAProfile3.02 module slots/float4+status1/discrete1+status1/totalizer controls,16mA and9..32VselectedO200instrument. Not allPAdeviceprofiles.'}
for entry in m:
 if Path(entry['path']).stem not in scopes:continue
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 reviewed.append({**entry,'read_scope':scopes[Path(entry['path']).stem]})
for filename,scope in [('pno-timing-pa.txt','Extracted original selectedPart9 pp896-909 andPart4timer paragraphs, scoped source reader output, not a new specification.'),('pf-pa2008.txt','Full original28page extraction, manufacturer application guideline only.'),('eh-pa2024.txt','Selected actualoriginalpages64-70/198-201 andcommissioning excerpts.')]:
 path=primary/filename;reviewed.append(dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),read_scope=scope,kind='SCOPED_ORIGINAL_EXTRACTION'))
(primary/'pa-reviewed-manifest.json').write_text(json.dumps(reviewed,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='profibus_pa')['form_parameters']};after={v['key']for v in registry.parameter_fields('profibus_pa')}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings.update(bitrate='Fixed31.25kMBP nominal physical rate unconfirmed proposal; own synchronous8bit/Manchester/CRC16/device/power/coupler schedule distinctDP UART11/CAN/FF LAS.',payload_bytes='Whole application bytes distinct device module value/status/control,244bytes percyclic direction, FDL/PHY frames and acyclic transfer. No8byte/1500byteapplication defaults.')
spec=dict(technology='profibus_pa',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Each exported declared field meaning/type/unit/bound/dependency/default/provenance individually reviewed against scoped downloaded original PI/PNO/manufacturer sources. HistoricalPNO1997layout is explicitly qualified; full current PA4.02members specification inaccessible and not claimed.',
 'Independent MBP31.25k Manchester/halfduplex8bit FDLoctets/CRC16polynomial0x1DC7/twoPHYdelimiters versus DPUART11/FCS8 andFF LAS. ReviewedCRCprotected tokenFDL5/PHY8/64bits, shortackFDL3/PHY6. SDL2LE4..249/DU246/FDL255 andphysicalheader/gap separate.',
 'Common1900m segment includes trunk+ALLspurs; equipmentactualspur/device/power/ISlimits remainunknown. Twoendterminators/conditioned supply distincteveryspur. PATypeA80..120Ohm/200nF/km/0.8mm2/1mH/km, temperature-qualifiedloop resistance; noforeignDP135..165Ohm orprinted2pF/m discrepancy.',
 'Actual voltage budget includes worst-path loop/current/barrier drop; mA/metre/kilometre conversion explicit. Device min/max/ordercode remainevidencebound. Supply total includesall device/barrier/fault/sparecurrent, sourceexample16/22devices/500mA/20%margin not fabricateddefaults. FISCO/Entity requires actual assessment, no automaticcertificate.',
 'Part9nativeTSYN4..32/readystrict inequalities/TSM2+2setup/idlemax/propagation<=20/Tslpeerresponse/preamble+16/times32us distinctDP35setup/UART33bit. Device/couplerpoll/watchdog/applicationfreshness separate unknownactualtimers.',
 'Actual EH_O200Profile3.02 module slot1..13 withfloat4+status1 versusdiscrete1+status1/totalizercontrol/EMPTYholes. Cyclic244perdirection distinctaggregatedDP/PALINK244 mapping. Frame/CRC/GSD/status/framequality/freshness neededbeforefunctionalacceptance; actualbuspower andlinksuccess are notacceptance.',
 'Confirmedstation17/watchdog1234/poll250/trunk450 preserved. Device16mA/32VrestrictionsonlyselectedO200profile;registeredactualotherdevicehasownsource, noforcedmanufacturerscope.',
 f'{len(cases)} isolated tests PASS, {native} native and nine shared suites.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} PA and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['FullcurrentlicensedPA4.x/IEC/ISsystemcertification andallinstruments; full Manchester/CRC/state/token/poll/retry/coupler executor, actualwhole-treepower/noise/schedule/hardwareE2Ecapacity/safety. Runtime MODEL_MISSING; known literature proposals never fabricateactualdevices.',
 'Remaining profiles, cumulative consumers, README, release gate and exact tested-image production delivery remain pending.'])
(root/'work/profibus-pa-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
