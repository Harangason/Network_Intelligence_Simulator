from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import nmea2000 as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/nmea2000-tests.xml'
for path in('backend/communication/technologies/nmea2000.py','backend/tests/test_nmea2000_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_nmea2000_parameter_review')for c in cases)
assert native==153 and len({c.get('classname')for c in cases})==10
primary=root/'work/nmea2000-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 if entry['url']in n.SOURCES:entry.update(revision=n.SOURCES[entry['url']],read_scope=n.SOURCES[entry['url']],individual_local_tests_completed=True)
 else:entry.update(read_scope='Downloaded for investigation but not used as a normative parameter source.',individual_local_tests_completed=False)
(primary/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='nmea2000')['form_parameters']};after={v['key']for v in registry.parameter_fields('nmea2000')}
meanings={v['key']:v['description']for v in n.DECLARATIONS}
meanings.update(bitrate='NMEA2000 fixed250000bit/s classic CAN extended29. Separate profile/no ordinaryCAN/J1939 required-parameter inheritance. Actual bit-timing/physical/error-retry/PGN schedule remain device evidence.',payload_bytes='Actual complete encoded PGN bytes. Selected SINGLE<=8, FAST_PACKET<=223, qualified ISO-TP<=1785 and pinnedlibrary storage223. No automatic8 or223globalmaximum; dataframeDLC andTPmanagement frames separate.')
spec=dict(technology='nmea2000',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Every declared field meaning/type/unit/bounds/applicability/dependencies/source/default provenance reviewed individually. Publisher3.000 overview, Actisense guideRev4 2021, Warwick author CANNewsletter2/2024 threepages, Simma1.3 April2013 public manual and Timo implementation pinned5b7b9fc3ccc18e30ebfba92da6486cffc6251595 reviewed. Full licensed Main/Appendices A/B/C not read, no device/certification claims inferred.',
 'Industry neutral separate NMEA2000 profile250k CAN-CC29bit/FDfalse/BRSfalse. No CAN500k,NMEA0183 serial, EthernetMTU/duplex/VLAN orgenericqueue fallback. Active automaticCAN retransmission separateboundedservice evidence; selectedsamplepoint85..90 versusSimma<=87.5 sourcequalified. Active NAME/addressclaim andsilentmonitor distinct; currentpinnedstack maxsource251/null254, not genericJ1939 address default.',
 'Lossless16hex64bit NAME/currentassigned manufacturer/product/identity/class/function/instances andPGNcodec evidence, noexampleproduct666/manufacturer402/source orindustry4 auto-confirmed. PDU1PF<240 excludesdestinationfromPGN, PDU2includesPSextension/implicit255; exact29bitID priority/DP/PF/PS/source relations. Library/codec presence doesnot imply currentNMEA certification orinteroperability.',
 'Actual PGN transport registration not inferred from length. SINGLE<=8; FASTfirst6+following7/5bitindex0..31 and3bitsequence0..7/lastpadding gives223 in32frames. Warwick article says31frames; pinned implementation/MaxDataLen calculation resolves reviewedbehavior to32, not silently copying conflictingsummary. Simma8bitsequence APIargument doesnotmake8bitwirecounter. ISO-TPdata<=1785/255dataframes plusactual management, BAMglobal versusRTS/CTSaddressed; pinnedlibrary currentstorage223 isseparatelimit.',
 'Actual<=50physicaldevices,backbone MICRO100m/MIDorHEAVY250m,longestdrop6m/sum78m,externalend2*120 nominalparallel60 distinctmeasurement. Actisense2021catalog selectedbranchcurrent3/4/8A qualified tothatcatalog; laterconnector/cable ratings needregisteredsource. Selectedactualcable/source required insteadunboundedbackbone lengthwithoutgrade.',
 'Standarddevice9..16V vsseparatelyqualified24V all-devicerating/warning, positive+return loadedloop Vdevice=Vfeed-Rloop*branchI. Actual1LEN50mA upperallocation versusmeasureddraw, bus-only20LEN constraint versusseparateaux circuitry. Fuses,actualbranchcurrents/isolation/ground not fabricated fromnominal12V orrating. Device voltage/current actualsourceandpowerprofile required.',
 'PinnedTimoheartbeat60000ms/reassembly100ms conditionalimplementation proposals; Simma10ms tick/250msBIPwindow/25percent (100disables)/10RX3TXbuffers128bytes proposals onlythatstack. No100ms universalcycle,128==1785 guarantee orNMEAdevice certification. ConfirmedISO1785payload,42.5ms customretrybound andlosslessNAME persisted andretainedafterrejected100M.',
 f'{len(cases)} isolatedSQLtests PASS; {native} NMEA2000 plusnine sharedsuites. CompletePGNfield codecs/addressclaim/reassembly/state/physicalmeasurements/actual CANerror schedule not executed orcertified; capacityMODEL_MISSING explicit.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} NMEA2000 and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['LicensedMain/PGNappendices/fullprotocolstate andphysicalcertification, actualaddressclaim/traffic/errorrecovery/isolation/connectorproof andfunctionalE2E acceptance. Publicsource configuration/dependency validation isnot certifieddevice capacity.','Cumulative consumer verification, README, releasegate andexact-image production pending.'])
(root/'work/nmea2000-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
