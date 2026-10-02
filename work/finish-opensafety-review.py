from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import opensafety as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/opensafety-tests.xml'
for path in ('backend/communication/technologies/opensafety.py','backend/tests/test_opensafety_parameter_review.py','backend/communication/technologies/catalog.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_opensafety_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('opensafety'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/opensafety-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 entry.update(read_scope='Pinned reference 1.4 source constants, serialization/deserialization, checksums, SOD mapping, consumer timing and call-frequency contracts. Not full current licensed EPSG/IEC specification or certified hardware.')
(primary/'reviewed-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='opensafety')['form_parameters']};after={v['key']for v in registry.parameter_fields('opensafety')}
meanings={v['key']:v['description']for v in n.DECLARATIONS}
meanings['payload_bytes']='Actual application bytes distinct source-defined safety frame LE, duplicated payload, SSDO segmentation and black-channel frame limits. No universal CAN8 or Ethernet1500 ceiling.'
spec=dict(technology='opensafety',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Each declared type/unit/bound/meaning/dependency/default/provenance reviewed against pinned B&R/IXXAT reference distribution 1.4 commit '+n.COMMIT+'. Archived implementation, not current full IEC/EPSG conformance. Primary source files hashed and read.',
 'Independent industry-neutral black channel; no Ethernet speed/frame or CAN parameters. Registration and public catalog domain now agree, 125 public profiles. Runtime capacity remains MODEL_MISSING.',
 'Ordinary two-subframe geometry duplicates LE0..254, slim SSDO omits second payload. LE0..8 CRC8_2F versus9..254 CRC16_BAAD or slimAC9A, zero initial register. Checksum outputs explicitly actual external verification; no implemented whole codec/CRC proof claimed.',
 'Actual ten-bit safety/domain/manager addresses, six-byte UDID, service-specific six-bit frame IDs, actual bearer encapsulation/limits and SOD mapping distinct application bytes. Demo SSDO12/SPDO128 and minimum-supported SSDO8 are configuration-qualified proposals; no fabricated addresses or safety confirmations.',
 'Actual clock units and UInt16 wire CT versus UInt32 local timer wraps, propagation intervals and SCT consumer gates. SCT pointer UInt16 in this pinned implementation despite an api comment naming SCT_U32. Actual smallest active refresh/SCT bounds periodic stack calls; no assumed100ms. First frame after synchronization remains safe, accepted data requires valid connection, checksums, application ranges and timing.',
 'CRC/SCT alone do not confirm system safety case/certificate scope or total fault reaction. Actual freshness and assurance evidence preserved. Confirmed tick100/SCT42/payload64/UDID survive rejection of foreign CAN rate.',
 f'{len(cases)} isolated tests PASS, {native} native and nine shared suites.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} openSAFETY and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['Full current standard, all optional device/SOD configurations, complete codec/state-machine runtime, physical black-channel capacity, hardware safety/E2E certification. Actual application evidence is not synthesized.','Cumulative consumers, README, release gate and exact tested-image production remain pending.'])
(root/'work/opensafety-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
