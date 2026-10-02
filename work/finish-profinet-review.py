from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import profinet as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/profinet-tests.xml'
for path in('backend/communication/technologies/profinet.py','backend/tests/test_profinet_parameter_review.py','backend/tests/test_technology_standard_defaults.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_profinet_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('profinet'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/profinet-primary';m=json.loads((primary/'manifest.json').read_text());reviewed=[]
scopes={'pi2018-update':'DocumenteditionNovember2018 order4.132, not downloadtimestamp2024; printed8-16/23-24 IO/AR/GSD/IOPS/IOCS/RT/IRT/100Mduplex/PCP6/LLDP/optionalfastcycle. No licensedlatestnormativecertification claim.',
 'siemens2023':'A5E33436509B04/2023 printed46-50/137-139: updatefactorclock, even/oddclockhardwarepathrestrictions, source-qualified1msdefault onlyselectedSIMOTION; IRTphase/topology/sync, not RTdeterminism.',
 'src__device__pf_cmdev':'PinnedPNIO2.4 IOCRchecker2990-3380: L2/UDP CSDU/rates/frameIDs/clockratios/phase/sentinel/nativenstime/datahold/priority/GSDmininterval. Enumacceptance not executorsupport; avoiduint32productoverflow.',
 'src__common__pf_ppm':'PinnedPPMbufferlayout/taggedL2offset20+CSDU+APDU4 excludesFCS, datastatus, clockcounterhelpersnormalizeincrementmod65536; not all UDPheaders/wholephysical timing.',
 'include__pnet_api':'PinnedIOXS0/128, DataStatusbitsemantics and RTC3ready explicitlynotimplemented.',
 'src__device__pf_cmina':'PinneddeclaredPNIO2.4 station grammar text read1502-1650; stricterASCIIbaseline registered separately frompunycode, no copiedemptylabel/consecutivehyphen/portprefixparserbugs.',
 'src__pf_types':'PinnedIOCRtype/class/status enums and CSDU comments/data+IOPS/IOCS structure, compiletimebuffers not universal limits.',
 'src__common__pf_dcp':'PinnedDCPHelloFEFC/GetSetFEFD/IdentifyReqFEFE/IdentifyResFEFF service constants; separatecyclicframeIDs.'}
for entry in m:
 stem=Path(entry['path']).stem
 if stem not in scopes:continue
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 reviewed.append({**entry,'read_scope':scopes[stem]})
assert len(reviewed)==len(scopes)
for file in('pi2018-update.txt','siemens2023.txt'):
 path=primary/file;reviewed.append(dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),kind='ORIGINAL_TEXT_EXTRACTION',read_scope='Scoped primary excerpts; original PDF separately hashed, no full-read assertion.'))
(primary/'reviewed-manifest.json').write_text(json.dumps(reviewed,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='profinet')['form_parameters']};after={v['key']for v in registry.parameter_fields('profinet')}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings.update(bitrate='ConventionalPI100Mbps baseline proposal, actual explicit PHY and optionalregisteredotherlink. Not CAN rate or universal RT/IRTtimingproof.',payload_bytes='Whole application bytes distinct native CSDU1440 IOdata+IOPS+IOCS+padding and taggedL2NIC24/fullMAC28byteoverhead. No arbitrary8byte/application1440limit.')
spec=dict(technology='profinet',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Every declared field meaning/type/unit/limits/dependencies/provenance/applicability/source-qualified default reviewed individually. Eight original PI/Siemens/pinnedstack sources with scoped read/hash manifest; does notclaimall currentlicensedPNIO standards.',
 'Separate IOcontroller/device/supervisor roles and AR/GSDML/submoduleownership; DCP serviceFrameIDs distinct cyclicRTC1/2/3/unicast/multicastIDs. PublicstackPNIOwire enums notfullIRTsupport. Explicit PHY/duplex/rate noforeignCAN/EthernetMTU/queuefallback.',
 'CSDU12UDP/40L2 through1440 includesIOdata/status/padding; taggedL2bufferCSDU+24withoutFCS/fullMAC+28withFCS,8wirebits/byte andactualrate serialization. Wholeapplication payloadunboundedbyCSDU; UDPoverhead needsseparateactualcodec.',
 '31.25usfactor,update=clock*ratio,phase<=ratio,GSDminimuminterval,dataholdfactor<=7680 with1.92sL2/61.44sUDPprotocolbounds. Ratio>=256/8192conditionssourcequalified, SIMOTIONevenclock1msdefaultconditionalnotgenericfastest. No integeroverflow inherited fromCchecker.',
 'UInt32FFFFFFFFbesteffortsentinel differs scheduledoffset<clock/4ms, counter normalization/wrap65536 separatepacketcount. Actual IRTsync/hardware/topology/per-portphase/optionalDFP/MRP/fastcapabilityrequired, notautomaticdefaults.',
 'DeclaredPNIOASCIIstationgrammar1..63label/240totaluniqueactualnames, noportprefix/IPnumeric/emptylabels, punycodealternategrammarneedsregisteredsource. Ordinaryfunctionalacceptance requiresDATAEXCHANGE/frame/map/IOPSGOOD/DataValid/ProviderRun/freshness;stationproblemdistinctdata-invalid.',
 'Confirmed stationuser17/clock16/ratio8/hold7/recordtimeout1234 retained. Literature bitrate/clock/VID/PCP/transfersentinelproposals neverautoconfirmactualGSD/address/sync/safety.',
 f'{len(cases)} isolatedPASS tests, {native} native andnine shared suites.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} PROFINET native and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['FullcurrentlicensedPROFINET/TSN/IRT/MRP/DFPcodec/state/clock/port-schedule executors, actualhardwareE2Ecapacity/safetycertification; runtime MODEL_MISSING honest. AlternateUDPframing/oddSIMOTIONclocks/punycodeexplicitregisteredsource only.',
 'Remainingprofiles/cumulativeconsumerconsistency/README/exacttestedimagereleaseproduction pending.'])
(root/'work/profinet-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
