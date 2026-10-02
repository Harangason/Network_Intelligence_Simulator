import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import nb_iot as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/nb_iot-tests.xml'
for path in('backend/communication/technologies/nb_iot.py','backend/tests/test_nb_iot_parameter_review.py',
            'backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
    assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
parsed=ET.parse(xml);suites=parsed.findall('.//testsuite')
assert suites and all(int(s.get(k,'0'))==0 for s in suites for k in('failures','errors','skipped'))
cases=parsed.findall('.//testcase');native=sum(c.get('classname','').endswith('test_nb_iot_parameter_review')for c in cases)
assert native>=224 and len({c.get('classname')for c in cases})==10
primary=root/'work/nb-iot-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
    assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
    entry.update(revision=n.SOURCES[entry['url']],read_scope=n.SOURCES[entry['url']],individual_local_tests_completed=True)
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='nb_iot')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('nb_iot')}
native_fields={v['key']:v['description']for v in n.DECLARATIONS}
native_fields['payload_bytes']='Actual encoded application bytes may spanmultiple MAC/RLC/PDCP blocks. No universal8/1500byte packet, applicationrate250k or directpayload/TBS ratio. Actualheader andsegmentation sourceindependent.'
spec=dict(technology='nb_iot',native=native_fields,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=[
 'Every declaredparameter reviewed individually: meaning/applicability/type/unit/bounds/dependencies/source/conditionalproposal/provenance. Sixversion-qualified ETSI primaryPDFs retainedwithSHA256. CategoryPDF55, RFbandPDF65, PHYRU206/207, proceduresTBS531/540 andNAS eDRX651/timer715 visuallyinspected toverifycolumns/footnotes. SelectedRelease18 rules notcompleteRelease19/otheredition/deviceconformance.',
 'Industryneutral transportpath, explicitterrestrialE-UTRA versusindependentlyregisteredNR/NTN. No forcediot template, LTE-Mbandlist/CANrate/EthernetMTU/queue/gateway/retryfallback orfixed250k/1500applicationpacket.200kHzchannel versus180kHzgrid; actual grants/coding/repetition/halfduplex/control/resources/NAS/core determinecapacity. MODEL_MISSING remains explicit.',
 'NB1 DL680/soft2112/UL1000/L2buffer4000; NB2 DL2536/soft6400/UL2536/L2buffer8000 versus optionalDL16QAM4968/soft12800/L2buffer12000. NB2alsoNB1advertised, actualinstalleddevicecaps neverdefaulted. OptionalbandqualifiedUL16QAM doesnotincreaseUL2536cap. Multi-tone/multi-carrier mandatoryselectedR18 capabilities notassumedolderdevice.',
 'Own38E-UTRAbands includes17/65/103; band54TDD, neitherLTE-M27/39/40norNRn-bandautomatic. Actualdirection/NS04/06USedges/qualified24specialintervals and65/66/70/74footnotes. Power3/5/6nom23/20/14dBm conditionalproposals; actualpower hasownMPR/tolerance/source, missingband88table requiresownqualifiedsource. UErelativecarriererror<=0.2ppm<=1GHz,else0.1ppm with72/tone-slotaverage; notoscillatorcatalogppm.',
 'UL3.75kHz grid48/2msslot/single-tone versus15kHzgrid12/0.5msslot. NPUSCHformat1RUslots16/8/4/2 for1/3/6/12tones; format2controlsingle-tone4slots/BPSK. ContiguousDCItoneindices/reservedranges andownexactUL/DLTBS tables. Single-toneMCS0/1/2mapstoTBS0/2/1, notidentity. ULresource1/2/3/4/5/6/8/10;ULrep1..128versusDL1..2048. Actual16QAMNB2unicastcap/config/search-space/MCS15/nonrepetition andinbandDLdifferentTBSoffset. SparseULtableemptycellsnotaccepted. PUR/EDT/SIB/multiTB requiresregisteredownrules.',
 'HD-FDDtypeBbefore/afterguard1msproposal; TDDactualconfiguration3.75kHzonly1/4 and15kHz1..5, actualspecialsubframes/guardsourcesseparate. ru_msoccupiedbasicresource notcompletecoded/repeatedairtime: NPRACH, NPDCCH, reference/reservedresources, gaps/postponements, HARQ/RLC andwholecellworkload stillactualevidence. No per-packetcapacity/E2Ecertificatefromonevalidtablepair.',
 'NB-S1 CPmandatorycapability/UPoptionalS1-Udependency andcurrentTAIacceptedfeature. CPcanIP/non-IP/Ethernet, noautomaticUDPstack. ActualSCEFnonIPCP-only versusSGi endpoint/PDNpath. NASapplicableEMM+240s/ESM+180s tableadditions separateactualapplicationdeadline, namedprocedure/source stillrequired. FullNASprocedures/codecs/security notexecuted.',
 'T3412timer3high3unit/low5value,0..31multiplier; units600/3600/36000/2/30/60s. Unit6NETWORKreceivedS1request320hours regardlessprotection versusUEgrant320hoursprotectedor1hourunprotected. Unit7extendedT3412consideredIEabsent, notinfinite/deactivatedfinite0. T3324timer2units2/60/360s and3..6interpreted60,unit7deactivated;zeroactivevaluevalid/immediatePSMnotmissing.',
 'ActualreceivedNB-S1 eDRX0/1consideredIEabsent versus4/6/7/8interpretedcode2/20.48s; othermappedcycles20.48..10485.76s. PTW(code+1)*2.56s versusLTE-M1.28sstep. Rawoctet nibble/decoded consistency. Requests donotsetgranted/currentuse; actuallatestgrantrequiresrawPTW/cycle/timers/source; activePSMnormalregisteredidle/nonemergency, currenteDRXnonemergency. Paging/awake/TAU/corebuffering actualboundsnotguaranteedfromtimer.',
 f'{len(cases)} isolatedSQL tests passed, including{native} NB-IoT andnine sharedsuites. Confirmed35712000secondprotectedT3412,zeroactiveT3324 and5000applicationbytes preserved after rejectedforeign250kbit/s.'
 ],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} NB-IoT and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['FullTS36.101RF/spectralreceiver/environmentalapproval, 36.212coding,36.213completegrant/HARQ,36.321/322/331 MAC/RLC/RRC,24.301actualNAS stateexecutor,installeddevice/networkcurrentproof. Selectedscalar/tablechecks notcompleteNB1/NB2conformance. OtherNR/NTN/release,fullradio/control/randomaccess/corecapacity andfunctionalE2E/safetyacceptance remainunverified. MODEL_MISSINGexplicit.',
 'Full cumulative consumer tests, release gate, README and production delivery pending.'])
(root/'work/nb-iot-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps(dict(tests=len(cases),native=native,fields=len(native_fields),removed=len(before-after))))
