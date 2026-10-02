"""Record the individually read Matter parameters after actual isolated PASS."""
import json,hashlib,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import matter as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
xml=folder/'individual/matter-tests.xml'
for relative in ('backend/communication/technologies/matter.py','backend/communication/technologies/catalog.py',
                 'backend/communication/technologies/core/components.py','backend/tests/test_technology_full_parameter_audit.py'):
 assert xml.stat().st_mtime_ns >= (root/relative).stat().st_mtime_ns,('stale receipt',relative)
suites=ET.parse(xml).findall('.//testsuite')
assert suites and all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
count=sum(int(v.get('tests','0'))for v in suites);assert count>=8821,count
manifest=json.loads((root/'work/matter-primary/core-manifest.json').read_text(encoding='utf-8'))
assert manifest['sha256']==hashlib.sha256(Path(manifest['path']).read_bytes()).hexdigest()
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='matter')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('matter')}
native={v['key']:v['description']for v in m.DECLARATIONS}
native['payload_bytes']='Actual complete encoded application TLV/protocol payload bytes, not8byte CANframe or universal65535 limit. UDP1280includesIPv6/UDP/Matter optional headers/extensions/MIC;TCPactualpeerreceiveboundexcludes4byte length prefix. Larger messages require qualified both-end capabilities and their own lower-layer segments.'
spec=dict(technology='matter',native=native,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),
 revisions=list(m.SOURCES.values()),scope=[
 'Every declared field individually reviewed for meaning/applicability/type/unit/bounds/dependencies/source/revision and conditional proposal; explicit NIS scenario requirements remain distinct from Core or device guarantees.',
 'OfficialCSA23-27349-012/CoreR1.6.1/2026-09-16 downloaded with ordinary documented browser file-link API after already accessible user-opened PDF.15,750,990bytes/1341pages;SHA256d7b078a4b80e8faf345205af0ba4773686e15097b2e6b6caecb5810585875b91. Read scopes/selected table screenshot in work/matter-primary/core-manifest.json; not the entire core or all cluster definitions.',
 'Matter application is industry-neutral and has no standalone PHY clock. Actual Ethernet/WiFi/Thread+IPv6+UDP/TCP choice is independent from BTP/PAFTP/NTL commissioning-only channels. Operational CASE versus commissioning-only PASE versus group credentials are explicit; selected paths never inferEthernetorBLE operational fallback.',
 'Standard peer fallback500idle/300active/4000threshold differs from unauthenticated DNS-SD(max1hourSII/SAI,65535SAT), session32/16bit fields and locally advertised SDK/platform/dynamic/ICD settings. SDK3bcdd56/v1.6.1.0 OpenThreadnonLinux2000/2000/1500boost proposals conditioned on platform and nonICD; receiver values remain separate from sender backoff.',
 'MRP default5totalattempts/1.6base/1.1margin/.25jitter/1threshold/200msACK are proposals, not actual confirmations. Source real equation versus pinned integer1127/1024,16/10,u8jitter/1024,three integer divisions and SDKexponentclamp4 independently tested. No random workload/evidence or derivedE2Edeadline is manufactured.',
 'UDP message+IPv6/UDP and optional extensions <=1280 versusTCPnegotiated64000fallbackmessagebound and4byte length prefix;BTP/PAFTP2prefix andNTL/UDPnone. CompleteMatter8+optional8/8or2header,6+vendor2/ACK4protocolheader,extensionlengthprefixes,0unsecuredor16secureMIC remain separate from appTLVpayload and lowerPHYsegments.',
 'Messageformat0/LITTLE_ENDIAN, reserved outgoing MX/SX flags, ACKpresence/counter, all tenIMopcodes in commonprotocol1 and standaloneACKempty payload versus sessionlessCheckInopcode50 tested. Actual64-bitfabric/node IDs remain16hextext with nonzero/operationalrange constraints, never JavaScriptfloat/defaultaddress. CRC or an unconfirmed source string does not implementAEAD/nonce/replay/authentication.',
 'Group dataUDP/sourceID/groupdestination/privacy lacksMRPR/Asemantics and has ownfabric/group/credential/address evidence. Application group range/universalFFFE/FFFF vsdeprecated/reserved IDs distinct. Groupsminimum3keys/4groupsperendpoint versusGroupcast4keys and reportedmembercapacity separated.',
 'Actual SupportedFabrics normativeuint8range5..254 overrides SDKcompiled16 suggestion; per-fabricACL4/CASE3/Read9/Subscribe3*3pathguarantees anddevice-typehigherminima do not become installedwhole-nodepooldefaults. Invoke paths matchpeerMaxPathsPerInvoke and >1excludesgroup/wildcards.',
 'ICD actualSIT<=15000msslowpoll/SII+SAI vsLITregistration/feature/usertrigger/CheckIn/threshold>=5000ms, fastpoll<active duration, idle seconds versusactive ms and CheckInbackoff verified. Normative9.16attributeIdleModeDuration<=64800(PDF726tablevisuallychecked) takes precedence over informative9.15.1.7 typo68400. ThreadSED differs from MatterICD; capability values are not automatically measured.',
 f'{count} selected ten-file regressions PASS in isolated SQL, including confirmedpeerinterval/losslessuint64storage preservation after rejectedforeigncommissioningtransport edit. Complete release gateNOT_RUN.'
 ],validation=dict(status='PASS',tests_passed=count,isolated_sql=True,complete_release_gate='NOT_RUN'),not_certified=[
 'EntireCore1341pages, allvendor/device-type/application cluster specifications, everyoptionalBTP/PAFTP/NTL negotiation, segmentation and fullcodec/AEAD/PASE/CASE/counter/DNS-SD parser implementation or devicecertification.',
 'Lexical sources and localdeclaredscalarVALID do not resolve actualcredential/sourceprovenance references, commissionedIPv6/physicalbindings, selectedSDKcompile/dynamicoverrides, whole-message/reassembly/resource/sleep/workloadschedule or executablecapacity/security evidence.',
 'Consumer-wide selectedlowerstackresolution/serializer/conditionalproposalUI/persistence/preflight/capacity/simulation/trace consistency, actorwizardregression, nine-stageE2E, full release gate and exacttestedproductiondelivery.'
 ])
(root/'work/matter-review-decisions.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'tests_passed':count,'native_fields':len(native),'removed':len(spec['removed'])}))
