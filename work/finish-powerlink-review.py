from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import powerlink as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/powerlink-tests.xml'
for path in('backend/communication/technologies/powerlink.py','backend/tests/test_powerlink_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_powerlink_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('powerlink'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/powerlink-primary';notes=primary/'source-review-notes.json';data=json.loads(notes.read_text());assert len(data['sources'])==2
(primary/'reviewed-manifest.json').write_text(json.dumps(dict(content_kind=data['content_kind'],path=str(notes.relative_to(root)),sha256=hashlib.sha256(notes.read_bytes()).hexdigest(),sources=data['sources'],download_status=data['download_status']),indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='powerlink')['form_parameters']};after={v['key']for v in registry.parameter_fields('powerlink')}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings.update(bitrate='Classic DS301 fixed nominal100Mbit/s100BASE-X HALF duplex, not switched Ethernet or application goodput. Proposal remains unconfirmed.',payload_bytes='Whole application bytes distinct PDO Size/mapping/fixed padded slot, ASnd/IP headers and SDO segmentation. No8byte or1500application ceiling.')
spec=dict(technology='powerlink',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Each declared type/unit/bound/meaning/dependency/default/provenance individually reviewed against scoped EPSG DS3011.5.1 PDF and DS302-B1.1.1 extension. Direct original downloads failed; available web PDF text and selected screenshot read; hashed review notes are not original binary hashes.',
 'Industry-neutral own POWERLINK transport, classical100M HALF duplex/Class2 repeater topology. Switched topology explicitly nonconforming; no inherited generic Ethernet/CAN rate/queue/VLAN defaults. Runtime capacity remains MODEL_MISSING.',
 'Actual role-scoped manager240/CN1..239/diagnostic253/router254, dummy252 only selected wait request and never actual device, unique actual MAC/source evidence. SoC/PRes/SoA multicast addresses distinct PReq unicast. Full optional redundancy302-A/isochain/routers not certified.',
 'Configured PDO slots36..1490 versus actual Size0..1490/mapping/version, PRes-list0ignore/65535actualRxMax. Serialization includes10PDO/18MACFCS wrapper+640ns preamble,96bit960ns IFG separate; no application8byte default. AsyncMTU300..1500 includes upper headers and bounded segment complete interfaceMTUminus18.',
 'Cycle1006h inus no universal default, actual device limits/granularity/peer agreement. Response-start/device/propagation/wholecycle bounds inns are distinct application deadline and actual scheduler. Fixed source proposals WaitSoC1000ns/PResTimeout25000ns/AsyncTimeout100000ns/prescaler2/multiplex0/fallback5000000us; actual device values preserved.',
 'Multiplex interval uses configured cycles, async-only node has no inferred cyclic guarantee. Selected Multiple-ASnd needs actual feature/target support, maximumslotcount and current sent count. AInv prohibited at exhausted limit or remainingtime<=source timeout. Source extension formula not full PHY/application capacity proof.',
 'Optional relative clock exactUInt64 decimaltext, SDO6bit sequence/history<=31 and actual transfer capability distinct PDO. Accepted cyclic data requires actualRD/mapping/frame validity/OPERATIONAL and freshness. Confirmed cycle2000us/MTU600/node17 survive foreign CAN/full-duplex rejection.',
 f'{len(cases)} isolated tests PASS, {native} native and nine shared suites.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} POWERLINK and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['Full optional extensions/device PDO profiles, complete MAC/DLL/SDO codec/state scheduler, actual whole-network timing/physical capacity/hardware acceptance and safety. Standard proposals do not synthesize equipment evidence.','Remaining profiles, cumulative consumers, README, release gate and exact tested-image production delivery remain pending.'])
(root/'work/powerlink-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
