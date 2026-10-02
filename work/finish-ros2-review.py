from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import ros2 as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/ros2-tests.xml'
for file in('backend/communication/technologies/ros2.py','backend/tests/test_ros2_parameter_review.py','backend/tests/test_technology_standard_defaults.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/file).stat().st_mtime_ns,('stale',file)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_ros2_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('ros2'))+10 and len({c.get('classname')for c in cases})==10
reviewed=[]
for entry in json.loads((root/'work/ros2-primary/manifest.json').read_text()):
 if entry['url']not in n.SOURCES:continue
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 scope='Actual complete QoS policy/header definitions and compatibility tables read.'
 if entry['url']==n.API:scope='Actual selected rmw.h publisher actual_qos and serialized-message-size API paragraphs; whole file not claimed read.'
 elif entry['url']==n.TYPES:scope='Actual RMW QoS enums/struct/sentinels lines390-625 and depth0 definition.'
 elif entry['url']==n.ZCFG:scope='Actual session configuration lines1-204 and shared_memory760-810; whole JSON5 not claimed read.'
 elif entry['url']==n.DOMAIN:scope='Actual complete domain/range/OS/process limit discussion and PB7400,DG250,PG2 calculator.'
 elif entry['url']==n.DISC:scope='Actual options/default and Zenoh exclusion; discovery matrices not inferred tested.'
 elif entry['url']==n.EXEC:scope='Actual complete executor document including new EventsCBG/unboundedqueue and overload roundrobin conventional waitset.'
 elif entry['url']==n.IFACE:scope='Actual complete ROS message/service/action definition and primitive/bounded/unbounded types.'
 elif entry['url']==n.VENDOR:scope='Actual complete official vendor list, FastDDS conditional installation default, Zenoh and nonguaranteed cross-vendor interoperability.'
 elif entry['url']==n.ZEN:scope='Actual complete rmw_zenoh README including config/bufferpool/SHMfallback/security/bridge and Humble typehash incompatibility.'
 reviewed.append({**entry,'read_scope':scope})
assert len(reviewed)==len(n.SOURCES)
(root/'work/ros2-primary/reviewed-manifest.json').write_text(json.dumps(reviewed,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='ros2')['form_parameters']};after={v['key']for v in registry.parameter_fields('ros2')}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings['payload_bytes']='Actual serialized ROS application byte count from selected type support. No UDP65507/EthernetMTU limit and no invented CAN8byte value.'
spec=dict(technology='ros2',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['All declared parameter meanings/types/units/bounds/dependencies/default provenance individually checked against13 pinned original official source files with explicit actual read scopes.',
 'Industryneutral actual RMW/DDS/Zenoh/intraprocess binding; no forcedEthernet/UDP/DDS/default65507payload. No universal PHY rate or installed middleware default.',
 'Pinned official defaultKEEP_LAST10RELIABLEVOLATILE, sensor5BEST_EFFORT, parameter/event1000 androsoutTRANSIENT_LOCAL10slifespan are proposals; confirmed overrides retained. SYSTEM_DEFAULT and BEST_AVAILABLE are not actual endpoint QoS or capacity evidence.',
 'RMW normalized duration0UNSPECIFIED differsINT64_MAXinfinite andINT64_MAX-1bestavailable; finiteactualpositive.ns policydeadline represents publication spacing, not transport+executor+callbackE2E.',
 'DDS Request-vs-Offered reliability/durability/liveliness andfinite deadline/lease mismatch reject falseOK. Actual middleware result/source andcreatedendpointreadback required for acceptance; Zenoh matching separately represented andnotjudgedbyDDScompatibilitymatrix.',
 'DDS conventionalUDP PB7400/DG250/PG2 domain232/participantoverflow independently checked evenwithoutderivedports.0domainproposal notactualproject isolation; custommappingseparate. OSephemeralrange/adjacentdomains requireactual deployment, notgeneric rangeapproval.',
 'ROS fullyexpandedendpointnames/247limit andtype-supportserializedbounds separateunboundedarrays/images andunderlyingfragmentation. SERVICE/ACTIONconstituentendpoints/intraprocess notsimplifiedtoonepacket.',
 'Zenoh sourcequalifiedpeer/localconnect7447/localephemerallisten/scoutingfalse/gossiptrue/8MiBserializationpool/48MiBSHMpool/lazy/512power2 proposals. DDSdiscoveryenvunsupported; SHMenableflagrequirescapability andactualobservedpath/peersupport, mayfallbacknetwork.',
 'Functionalacceptance requiresactualcodec/type/domain/RMWinterop/matching/readback/clock/trace/value mapping/freshness andserialization+transport+executorwait+callback chain. Conventionalexecutors notassumedFIFO/real-timeunderload; registeredruntimecapacityMODEL_MISSING.',
 f'{len(cases)} isolated tests PASS, {native} native andnine shared suites. Earlier run1failure802PASS exposed foreignlocaltimingevidence acceptance, explicitly rejected andrerun.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} ROS2 native andnine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['Actual DDS/Zenohdiscovery/serialization/retransmission/SHM/security/executor hardware/OS execution, loadedRMWdefaults, crossversionbridgeinterop andobservedchaincapacity remainproject evidence; nofullROSruntimeexecutorcertification.',
 'Remainingprofiles/globalconsumerconsistency/README/completecumulativeregressions/releasegate/exacttestedproductiondeployment remainpending.'])
(root/'work/ros2-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
