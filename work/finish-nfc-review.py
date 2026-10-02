from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import nfc as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/nfc-tests.xml'
for path in('backend/communication/technologies/nfc.py','backend/tests/test_nfc_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_nfc_parameter_review')for c in cases)
assert native>=180 and len({c.get('classname')for c in cases})==10
primary=root/'work/nfc-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
 assert hashlib.sha256((primary/(entry['name']+'.pdf')).read_bytes()).hexdigest()==entry['sha256']
 entry.update(revision=n.SOURCES[entry['url']],read_scope=n.SOURCES[entry['url']],individual_local_tests_completed=True)
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='nfc')['form_parameters']};after={v['key']for v in registry.parameter_fields('nfc')}
meanings={v['key']:v['description']for v in n.DECLARATIONS}
meanings.update(bitrate='Actual nominal RF mode label or exact13.56MHz/divisor; role/protocol/installedfirmware distinct fromhostI2C/SPI rate. No universal424k default.',payload_bytes='Actual encoded application bytes maychain overmultipleRF/NCI frames. NCI255, DEPbody252/LEN255 andapplicationlength differ. No fixed8byte oruniversal255bytepayload default.')
spec=dict(technology='nfc',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Each declaredfield meaning/type/unit/range/applicability/dependencies/source/defaultprovenance reviewed. ECMA340fourthJune2024 clauses7-12/AnnexA andNXPdataRev4.2July2026/UM1.8June2025 reviewed; NCIheaderPDF16 andLRPDF38 rendered/visuallychecked. No fulllicensedNFCForum/14443/15693 conformanceclaim.',
 'Industryneutral distinctNFCIP1/A/B/F/V RFrole, device, firmware andhost interface. Ownbaseline106kIP/A/B,212kF,selectedPNV26.48k proposals conditional; exact13560000/divisor versus roundednames separate. No unconditional424k/255applicationbyte/EthernetMTU/CANqueue/retry fallback.',
 'PN7160model61hex/PN716171hex; CORE_RESET_NTFbyte9model/10..12firmware, firmwarehex12500A isdisplay12.50.0A notdecimal18.80.10. Source4.2 P2P/FeliCaPCD onlythrough0A andFcardremoved0B; oldUMfeaturelist notuniversalcurrentcapability. PN7161ECPneedsactualformalexistingauthorization; no terms/authorization acceptanceperformed.',
 'PNreaderA/B106/212/424/848,card106/212/424;IP1PNonly106/212/424. NFCIP1fourthlistsadditionalactivecarrierdivisors butdoesnotspecifytheirPHYmodulation/coding: independentlyREGISTEREDqualificationrequired. NominalRF13.56MHz notguaranteed measuredtolerance/range/EMC. Protocol/directioncoding andactualsupply2.5passivetargetcard vs2.8RFactive, disjoint1.65..1.95/3.0..3.6IOrails,tx2.7..5.25/temp-30..85qualifiedPNonly.',
 'PNhostfollowerI2C7bits28..2Bstraps/Standard100kFast400kHs3.4M versusSPI7M/halfduplex/directionprefix0xxxxxxxwriteorFFread. Hostclocks/address/ACK/IRQ/retryboundnotRFthroughput. NCIheader3+payload0..255/packet3..258,MT/PBF/GID/ConnID/OIDheaderconsistency,actualmaxpacket/MTU/credit0wait/count1/dynamicconnection1 andRFidle/nonidleconstraints. No NCIopcode/stateexecutionorfullcreditpiggybackcodecclaim.',
 'IP1LEN3..255/body0..252 includesCMDpair plusPFB/DID/NAD/data, LR64/128/192/252notapplicationorNCIlimit. OwndirectionD4/06versusD5/07,PNI0..3,DID1..14whenpresent,NADactual,InformationACK/NACK/supervisoryheaders. Protectedrequiressecuritysource, no fullNFC-SECcodec/certificate. FullCRC/preamble/parity/chaining state/anticollision notexecuted.',
 'WT0..14/default14conditional;wait4096/fc*2^WT, extensionRTOX1..59 cappedWT14;rate-specificstart/stopedgeexplicit. InitialRFCAstrict4096/fc andguard>5ms,active768..2559/fc/guard>1024/fc/random0..3then0. Active/passivemodemustnotchange midtransaction;PNPSLonlybeforedata/uninterruptedtransaction. Everytimingactualsource not ratecapacity.',
 'ECMA8.2passivefieldupperboundsentence repeatsHminwhile8.1definesHmax: retainedqualificationrequirementinstead silentnormativecorrection. NFCForumAnalog3.0operatingvolume20mm metadata not universaldevicerange or certification. Actualoperatingvolume/measurement andfunctionalE2E remain unverified.',
 f'{len(cases)} isolatedSQLtests PASS, {native} NFC plusnine sharedsuites. Initialfocused sixfailures exposedNFCconstrainttargetbitratealias notcanonicalbitrate_bps; fixedandfreshlyverified. Confirmedapplication6000bytes/range12.5mm/SPIclock/firmware persisted andretainedafter rejectedforeign500k.'
 ],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} NFC and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['FullRF/NFCForum/NCI/ECMAstate/CRC/parity/activation/chaining/authentication execution, installedcontroller/antenna/EMC/currentcredits proof andcapacity. Source-qualified scalar/dependency validation notdeviceapproval orfunctionalE2E/safetyacceptance. MODEL_MISSING remains explicit.','Fullcumulativeconsumer verification/releasegate/README/production pending.'])
(root/'work/nfc-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
