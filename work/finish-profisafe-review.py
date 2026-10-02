from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import profisafe as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/profisafe-tests.xml'
for path in('backend/communication/technologies/profisafe.py','backend/tests/test_profisafe_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_profisafe_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('profisafe'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/profisafe-primary';reviewed=[]
scopes={'pi2016':'Actual edition2016 order4.342 printed5-11/16: 1:1codename blackchannel, V2implicitmonitoring/SPDUcontrolstatus/CRC, FV/OA/ipar, device/hostcertification andTWCDT+largestfailureDelta. Current2026MU2.1membersspec notaccessed/notclaimed.',
 'siemens2021':'A5E50557762-AA V6.4June2021 printed59-65/455: host limits V1CRC2/12,V2LPCRC3/12,V2XPCRC4/40 distinctprotocol123; modulepresetCRCseed1/passivation0onlyselectedXP; F_BlockID0/1/iParCRC, uniqueGSDaddress/watchdog1msstep actualbounds. Timingxls notread/claimed.',
 'driver2020':'A5E35388472-AC V2.2.3July2020 scopedprinted16-19/24-44/64-66/74-80: source/destination0/FFFF invalid, realcompiled0..12/123perdirection, V1CRC4source123distinctold122manual, state/returncodes/independent1ms16bit/inverse timers,8bitcontroller1instance,64bitmath/compilerconfiguration notgeneralPROFIsafeparameters.'}
for entry in json.loads((primary/'manifest.json').read_text()):
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 reviewed.append({**entry,'read_scope':scopes[Path(entry['path']).stem]})
for file in('pi2016.txt','siemens2021.txt','driver2020.txt','driver2020-param.txt','pi2016-response.txt'):
 path=primary/file;reviewed.append(dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),kind='SCOPED_PRIMARY_EXTRACTION',read_scope='Selected actual original pages read; separatehash originals, not allpages/fullcurrentstandards.'))
(primary/'reviewed-manifest.json').write_text(json.dumps(reviewed,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='profisafe')['form_parameters']};after={v['key']for v in registry.parameter_fields('profisafe')}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings['payload_bytes']='Wholeapplication bytes distinct0..12/40/123 directionalFuserdata, oneV2controlstatus/CRC2qualifiedbyprofile/mode, implicitmonitoring number andblackchannelwrapper. No ownphysicalrate/Ethernet1440limit.'
spec=dict(technology='profisafe',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Everydeclared nativeparameter meaning/type/unit/bounds/dependency/provenance/applicability/default individuallycheckedagainstthreeoriginalprimarydocumentswithhashes/scopedextractions. Currentlicensed2026MU2.1notavailable andnotclaimed; selectedS7V6.4/driver2.2.3explicit.',
 'F-host/device1:1codename island independentDP/PA/PN/mixedblackchannel, noownbitrate/CANqueue/Ethernetpayloadfallback. PN/mixedonlyV2withactualhost/devicecapability. Roles/directionaldata/locallycomparedsource/destination/GSD/safetyassurance evidence explicit.',
 'S7V1CRC2<=12,V2LPCRC3<=12,V2XPCRC4<=40 distinctdriverCRC4<=123 perinput/output. Actualcompiletimebuffers limitactualsize;0unuseddirection. V2SPDU=user+1+CRC, implicitmonitoring adds0wirebytes; V1trailerrequiresactualdrivercodecsource ratherthanV2guess.',
 'CRCseed/passivation selectedsubmodulecombination,0seedforbidschannelpassivation; S7BlockID0/1 matches iParpresence. Legacy16bitCRC3not32bitiParCRC/nottransportCRC2. Unknownactualsignatures/polynomials/GSDCRCcheckedflags neverautofilled.',
 'GSDactualwatchdog1msstep/min/max required, actualcompleteexchange strictbelowwatchdog; timer16bitonescomplement/independenttimebase/tolerance separatedatafreshness. Driverinstance1..32/8bitplatformonly1 anddemandpersiststwomonitoringnumbers.',
 'SFRT=sum5actualworstcasedelays+max(singlefailurewatchdog-minus-delay), notsumallwatchdogs/notbusfrequency. Eachreferencedcomponent/site/safetycaseinputunknown; settings do not certifySIL/deviceorwholefunction.',
 'Consumeracceptance requiresnewvalidCRC/parameter/mapping/nonpassivated/independenttimer/freshness state; oldtoggle,WDtimeout,CRCerror,FV/devicefault/iparmode/unacknowledgedOA forbidden. F-input not forcedtoF-outputonlydriverresult. Confirmeddest2000/watchdog321/iParCRC1234preserved.',
 f'{len(cases)} isolated tests PASS, {native} native andnine shared suites.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} PROFIsafe native andnine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['FullcurrentlicensedMU2.1/IEC/PROFIsafeCRC2/monitor/state-machine/reintegration/bearer executor andactualhardwareE2E/safetyfunctioncertification. Registerednewprofiles requiretheir ownfullschema; runtimeMODEL_MISSING.',
 'Remainingprofiles/cumulativeconsumerconsistency/README/releasegate/exacttestedimageproduction remainpending.'])
(root/'work/profisafe-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
