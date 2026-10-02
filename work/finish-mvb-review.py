import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import mvb as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/mvb-tests.xml'
for path in ('backend/communication/technologies/mvb.py','backend/tests/test_mvb_parameter_review.py',
             'backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
    assert xml.stat().st_mtime_ns >= (root/path).stat().st_mtime_ns,('stale receipt',path)
parsed=ET.parse(xml);suites=parsed.findall('.//testsuite')
assert suites and all(int(s.get(k,'0'))==0 for s in suites for k in ('failures','errors','skipped'))
cases=parsed.findall('.//testcase');native=sum(c.get('classname','').endswith('test_mvb_parameter_review')for c in cases)
assert native>=177 and len({c.get('classname')for c in cases})==10
primary=root/'work/mvb-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
    assert entry['sha256']==hashlib.sha256((primary/(entry['name']+'.pdf')).read_bytes()).hexdigest()
    source={'abb_pcnode_1995':m.ABB,'imc_fieldbus':m.IMC,'lapp_mvb_cable':m.CABLE}[entry['name']]
    entry.update(revision=m.SOURCES[source],read_scope=m.SOURCES[source],individual_local_tests_completed=True)
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='mvb')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('mvb')}
native_fields={v['key']:v['description']for v in m.DECLARATIONS}
native_fields.update(bitrate='Fixed nominal gross MVB1.5Mbit/s sourceproposal fromcurrentimc4.15 andABBhistoricalcontroller; measuredrate separateactualtolerance. Manchester is notdoubleusefulrate orCAN1M/Ethernet clock. No runtime capacity fromnominalrate.',
 payload_bytes='Actual application bytes within configured16/32/64/128/256bitdataset; wholeportfixed, oneproducer/multiplesinks. Messageport256bits includesactualmessageheader. No fabricated32byte applicationdefault.')
spec=dict(technology='mvb',native=native_fields,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),revisions=list(m.SOURCES.values()),
scope=[
 'Every declaredparameter individually reviewed formeaning/applicability/type/unit/bounds/dependencies/source/proposal/provenance. Currentimc4.15 February2026 pp17-18 differscached4.14 March2023. LAPP2173001V06 November2025 pp1-2. HistoricABBPCNode TN-AC-95/185 December1995 chapter2 publictechnicalmanualextract lacks2-8/2-9, noassertion fullmanual/currentIECconformance. IEC2012Edition1/stability2030 metadataonly, fulllicensed268pagesnotread.',
 'Industryneutral transportpath, no forcedrail generationtemplate. MVBgross1.5Mbit/s sourcebackedproposal/nominalfixed, Manchester/PHY/frame/queue/schedule notCANorEthernet. Actualmeasuredclock separateselectedhardwaretolerance. RemovedforeignMTU/VLAN/duplex/queue/retry/linkrecovery/sync assumptions; actualapplicationNISscenario stilllabelledscenario.',
 'NativePDsizes16/32/64/128/256/Fcodes0..4, ninebitdelimiter/master16information+8check=33bit-times22us. Slave9+data+8ceil(data/64)=33/49/81/153/297bit-times,32bitdata serialization49/1.5usnotrounded33us. Separatemedia-specificenddelimiter/guard/turnaround/gap; telegramlowerbound allparts, not onlypayloadtime. Scalarframing checks notcomplete TC57codec/PHY executor.',
 'Actual12bit masterfield scopeport0..4095/device/eventparameters;8bitmessage station separate. Exactfourhexcharacter masterinformationwordFcodehigh4+addresslow12. PDexactlyoneproducer/multiplebroadcastsinks, no perconsumerduplicatepayload. Fixeddataset/variablewidth/offset/nonoverlap andhostbit-word/endianqualificationrequired; applicationfreshnessactualsource+limit.',
 'MessagepollF12/256data includesactualheader beforeapplicationpayload, actualdeviceaddressscope. Supervisory/eventF8/9/13/14/15, reserved5..7/10/11 notaccepted; eventF9parameters notaddress andmultiplebidders notmisclassified multiplePDproducers. Fullmessagesegmentation/eventstate/tokenhandover andhostAPI notcertified.',
 'Oneactiveadministrator; backuprotation notmultipleconcurrentmasters. HistoricalABBslave1.4..4us/master<=42.7us onlyselectedoldprofile; registeredactualcontroller6us canhaveownsource. Slowestprovidedredundantline boundsgovern notaverage;duplicatedmedia sendboth/receiveone doesnotdoubleusablepayload.',
 'HistoricalESD20m/EMD200m/OGF2000m selectedqualifiers. CurrentimcEMD/ESD+ hardwiredloggeronlyMONITOR/PD/BUS, actualwiredselectionmustmatch; max200m/32segmenttaps, not4095tapsglobaladdressspace. Onrequestcustomopticalrequiresregisteredqualification, no automaticPHYswitch or activeBAclaim.',
 'HistoricalABBstandardbase1msproposal versusown0.833mssetting; basicmultiples1/2/4/8, individualpow2poll, <=1024msmacro/maxpoll onlyoldprofile. Actualphasebudgetperiodic+supervisory+event+guard=period, historicalscan350usminimumsporadicspace. Startpermitted requiresactuallongesttelegram<=remainingperiod; sourceactualscanlist stillmandatory. No globalschedule/E2Ecertificate.',
 'SelectedLAPP120ohm±10% at0.75..3MHz,40.1ohm/kmmax and5Gohm*kmmin at20C. Cap46nF/km/coupling1500pF/km at1.5MHz, xtalk>=45dB/kmat0.75..3MHz, transfer<=20milliohm/m at20MHz, attenuation<=15/20dB/km at1.5/3MHz separatelypairedtestpoints. No foreignCANterminator120ohm assertion; othercablerequiresownsource.',
 'LAPPcableoperatingvoltage<=125V nottransmitamplitude, fixedinstall−40..90C andradius>=3diam versusoccasionalflex>=10diam. Actualflexthermalqualification remainsrequired. Nominal7.6mmouter/0.74cconditionalpartproposals notactualmeasurement; operatingtemperature distinct20Clabpoint. Fullfire/EMC/environmental/safetycertificate notinferred.',
 f'{len(cases)} isolatedSQL tests passed including{native} MVB andnine sharedsuites. Confirmedport4095/32byteport/custom5usendguard retainedafterrejectedforeign1Mrate.'
],validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} MVB and nine shared suites',complete_release_gate='NOT_RUN'),
not_certified=['FullIEC61375-3-1/3-2 conformance, TC57/Manchester/enddelimiters hardwarecodec, eventarbitration/mastership state, hostAPI/resources, completeactualPHY/cable/scanbusywindow andE2E/safetyacceptance. MODEL_MISSING remains explicit.',
 'Full cumulative consumer tests, release gate and production delivery pending.'])
(root/'work/mvb-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps(dict(tests=len(cases),native=native,fields=len(native_fields),removed=len(before-after))))
