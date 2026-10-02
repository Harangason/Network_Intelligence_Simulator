"""Persist CSI-2 decisions after fresh isolated CSI and shared-consumer tests."""
import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import mipi_csi2 as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
xml=folder/'individual/mipi_csi2-tests.xml'
for relative in ('backend/communication/technologies/mipi_csi2.py','backend/communication/technologies/catalog.py',
                 'backend/tests/test_technology_full_parameter_audit.py','backend/communication/technologies/core/components.py'):
    assert xml.stat().st_mtime_ns >= (root/relative).stat().st_mtime_ns,('stale receipt',relative)
suites=ET.parse(xml).findall('.//testsuite')
assert suites and all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
cases=ET.parse(xml).findall('.//testcase');count=len(cases)
assert sum('test_csi_' in c.get('name','') for c in cases)>=230
assert len({c.get('classname')for c in cases})==10
manifest_path=root/'work/csi2-primary/manifest.json'
manifest=json.loads(manifest_path.read_text())
scopes={
 'version-matrix':'One-page March2026 feature matrix read and visually inspected; footnotes3-10 not defined in publicly available document and not reconstructed.',
 'ti960':'SNLS589D September2023, pages1,8-18,39-41,43-46,49,94,102-103 read; timing min/max tables on15,17,18 rendered and visually inspected. Selected CSI implementation only, not whole FPD-Link data sheet conformance.',
 'lattice':'FPGA-IPUG-02321-1.2 August2026 IP4.2.0; pages10-44,47,50-55,83-84 read; selected configuration, packet, buffer, clock/calibration and known-error limitations. No claim of all signal descriptions, CTS or generated-IP hardware testing.'}
for key,entry in manifest.items():
    assert entry['sha256']==hashlib.sha256((manifest_path.parent/(key+'.pdf')).read_bytes()).hexdigest()
    entry.update(read_scope=scopes[key],individual_local_tests_completed=True)
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='mipi_csi2')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('mipi_csi2')}
native={v['key']:v['description']for v in m.DECLARATIONS}
native['payload_bytes']='Actual application encoded bytes inside selected long-packet word count0..65535; classic complete packet is WC+6 and may exceed65535. Short packets carry two header data octets, no application long payload. Codec/source-qualified scope, no guessed universal8-byte CAN payload.'
spec=dict(technology='mipi_csi2',native=native,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),
 revisions=list(m.SOURCES.values()),scope=[
 'Each native declaration reviewed for meaning, applicability, type/unit/bounds/dependencies, version/source, conditional proposal and actual evidence. Retained NIS scenario fields remain application policies, not CSI standards. No common bitrate proposal across different PHY/device paths.',
 'Primary public CSI-2 v4.2, D-PHY v3.6 and C-PHY v3.1 pages plus March2026 matrix checked. Matrix footnotes1/2 read; missing footnote3-10 definitions and member-only norms/CTS remain limitations. Version reference is not exact-only compatibility. CSI1.1 has four-lane limit; later paths use actual endpoint limit.',
 'DPHY FCM forwarded DDR clock, ECM128/132 versus CPHY16/7 and32/9 exact coding groups. Per-lane/trio rates and aggregate coding-only throughput remain distinct from full packet/transition/calibration capacity. Extended VC and actual codec source required; optional feature versions and PHY scopes separated.',
 'CCI resolves a separate canonical I2C/I3C profile and transaction evidence. Standard100k proposal through2.0 versus Fast400k from2.1; deprecated Standard remains possible on qualified legacy implementation. Fm+/I3C optional revision support, no use of CSI imaging clock for control bus.',
 'Basic short four-byte header/no CRC vs long WC+6 including four-byte header and two-byte CRC; DI=VC*64+DT only with compatible header. RAW10 four samples/five octets and RAW12 two/three require actual complete groups, source-qualified packing and padding; host allocated bits differ from wire bits.',
 'TI960 PLL/reference exact arithmetic including23MHz1472Mbit/s and26MHz1664Mbit/s; PLL0 calibration required at any selected reference,400M requires explicit per-port override. Lane1/2/3/4 and VC0..3 are this manufacturer limits. Timing/UI and electrical measurements use actual point/envelope, including EOT maximum and summed prepare+zero, not universal default register contents.',
 'TI UI-dependent rise/fall/LP/return-loss limits distinguish installed actual rate from maximum PHY capability; total skew<=1.5G differs static/dynamic skew above1.5G. Typical transitions, buffers and aggregation/replication do not prove worst-case schedule or E2E safety.',
 'Lattice current IP4.2.0 Soft/Hard TX/RX rate bounds are independent. Generated PPI Soft8 vs Hard8/16 determines byte clock; no unconditional Hard16 proposal. RX controller64 only generated PPI16/four lanes, remaining combinations32. Actual configuration source required. UVSI host allocation, PPC, MBSI buffer allowance, minimum WC, AXI clock, reconfiguration wait and skew/init counters remain separately scoped.',
 'Lattice CSI TX only, escape/ULPS/BTA unsupported; byte/pixel interfaces and known pathological two-bit error reporting remain documented limits rather than complete safety evidence. No physical/runtime executor is fabricated by semantic metadata.',
 f'{count} tests passed in isolated SQL:230 CSI-native tests and nine shared consumer suites. Earlier interrupted full cumulative run was not a PASS. Complete cumulative regression and release gate remain required before delivery.'
 ],validation=dict(status='PASS',tests_passed=count,isolated_sql=True,
   selected_scope='230 CSI tests plus nine shared technology/rate/physical/capacity/default/parameter suites; other native per-technology tests deselected',complete_release_gate='NOT_RUN'),not_certified=[
 'Member-only complete CSI/PHY normative specifications and CTS; actual device electrical qualification, generated hardware, complete codecs, stream schedulers, calibrated trace, capacity and functional/safety/security acceptance.',
 'Local scalar validation is not source resolution or runtime capacity. MODEL_MISSING remains until an executable selected-path evidence model passes its gate. No production delivery yet.'
 ])
(root/'work/csi2-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps({'tests_passed':count,'native_fields':len(native),'removed':len(before-after)}))
