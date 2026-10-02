from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import rfid as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/rfid-tests.xml'
for path in('backend/communication/technologies/rfid.py','backend/tests/test_rfid_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_rfid_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('rfid'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/rfid-primary';reviewed=[]
scopes={'gs1-gen2-301':'Actual Release3.0.1RatifiedFebruary2026/204pages pp29-35/45-61/66-73/96-105. Actualselectedpagesread; current860..930MHznotold960, Table6-9QueryXvsQuery/FrT/DBLF, QueryX/QueryYnowmandatory, PacketPCnotStoredPC.',
 'ti-hf-trf7970a':'SLOS743M March2020 pp1/11-12/17/40-42/57-58: ISO15693 fourroundedrate/subcarriercombinations withtwoPPMcodings, lowestknown6.62 distinctfactory26.48, carrier13.56M andhardware127FIFO notapplicationlimit.',
 'ti-lf-mrd2':'SCBU049 August2012 pp15-20/72-83/99: actualMRD2HDX134.2kcarrier, coilQ10..20/46.1..47.9uH andsame2.7..5.5Vsupply, host9600baud8N1/41bytelegacycodec, five sourcequalifiedtimingtemplates, Uint16zero-reset and50/17msfactoryburst.'}
for entry in json.loads((primary/'manifest.json').read_text()):
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 reviewed.append({**entry,'read_scope':scopes[Path(entry['path']).stem]})
for file in('gs1-gen2-301-selected.txt','ti-hf-trf7970a-selected.txt','ti-lf-mrd2-selected.txt'):
 path=primary/file;reviewed.append(dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),kind='SCOPED_PRIMARY_EXTRACTION',read_scope='Actualselectedoriginalpages; originalhashseparate.'))
(primary/'reviewed-manifest.json').write_text(json.dumps(reviewed,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='rfid')['form_parameters']};after={v['key']for v in registry.parameter_fields('rfid')}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings['payload_bytes']='Wholeapplication bytes distinctGen2PC/XPC/EPC/TID/CRC, HFframe/127FIFO, LFhost/aircodecs. No255byte universalapplicationmaximum andnoCAN8bytepayloaddefault.'
spec=dict(technology='rfid',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Everydeclarednativeparameter meaning/type/unit/bound/dependency/default/provenance individuallycheckedagainstthreehashedoriginalprimarydocuments. LF/HF/UHF selectedprofiles mutuallyrejectforeignparameters andneverassumeCAN/Ethernetrate or industry.',
 'CurrentGS1Gen2_3.0.1not2015v2.0.1:860..930Mcarrier, readerPIE6.25..25us, RTcal2.5..3Tari/TRcal1.1..3RTcal/DR8or64/3, tagrateBLF/M with1FM0/2/4/8Miller. Rounded33.3us/640k sourceendpoint usesdocumentedcalibrationtolerance ratherthanfalseexactequality.',
 'Lowestselectedmandatorybaseline160kBLF/M8=20k, consistentTari12.5/RTcal31.25/TRcal50; strict40kloweredge hasnoattainableuniversalminimum andnofake40kdefault. DigitalQueryXmandatory1/2/3/4/7andoptional0/5/6actualtagcapability; allnominalsettingsproposalsunconfirmed.',
 'QueryCRC5 versusQueryX/QueryYCRC16; RN16QueryreplynoCRC versusoptionalQueryXRN16+CRC5, command-dependent CRCcoverage andparameters. TemporaryRN16/handle notgloballyuniqueEPC/UID. TruncatedTID/XPC/ResponseBuffervariants requiretheiractualcodec, nofixed96bitEPC.',
 'Slot2**Q, newround0..2**Q-1 versuscountdownwrap32767andmatchingQueryXInit0waiting32767; noQ0capacityguarantee. Actualselection/state explicitlyseparate.',
 'All T1..T8sourcebounds individuallycheckedincludingFrTnominal/extended/Querymethodratebands; missingactualtolerance/source remainsUNVERIFIED. T2maxonlyreply/acknowledged, T1+T3>=T4, delayed/inprocessalways extended, T8onlyInit0. Noonegeneric100msdeadline.',
 'PacketPCLincludesXPCwhileStoredEPCwordcountstaysseparate; sourceXPCsupportmax29/EPCnonXPC31; nontruncatedEPCreply32+16*PacketPCL excludespreamble/dummy/extraResponseBuffer. Simpleformula notappliedtruncatedorTIDreply.',
 'TIHFISO15693fourmanufacturerroundedtagrates6.62/26.48onecarrier/6.67/26.69twocarriers and1of4/1of256readerPPM; lowestproposalnotmanufacturerhighfactorypreset.127byteFIFO notfullRFmessage/applicationmaximum. OtherHF/activeRFIDrequireindependentlyregisteredprofile.',
 'TILFMRD2HDXdevice-specificcoil/supply/carrier/hostcodeclimits andfivemodulationtimingtemplates; manufacturerAUTOvariants explicitlyselectedwithoutindustrydefault. Anytiming0resetentireselectedgroup/notzeroairtime; powerrequest0effective50/17ms; actualconfirmed100/25retained.',
 'Carrier/ratevalidity doesnotprovepopulation/collision/schedule/coexistence/regionalsettings/deviceidentity/CRC/frame/value/freshness acceptance. Actualsource/decodedtag/mapping/region/airtime evidence required; runtimeMODEL_MISSING.',
 f'{len(cases)} isolated tests PASS, {native} native andnine shared suites.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} RFID native andnine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['FullRFIDLF/HF/UHFmodulation/anticollision/QueryXQueryY/access/security/physicalenergy/coexistenceexecutor, regulatorapproval andactualreader/taghardwareconsumerE2E/runtimecapacity remainactualregisteredwork, notcataloguecertification.',
 'Remainingprofiles/cumulativeconsumerconsistency/README/releasegate/exacttestedimageproduction remainpending.'])
(root/'work/rfid-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
