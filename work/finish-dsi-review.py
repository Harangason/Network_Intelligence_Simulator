"""Fresh isolated DSI and consumer evidence; not a complete release receipt."""
import hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import mipi_dsi as m
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001'
xml=folder/'individual/mipi_dsi-tests.xml'
for relative in ('backend/communication/technologies/mipi_dsi.py','backend/communication/technologies/catalog.py','backend/tests/test_mipi_dsi_parameter_review.py'):
    assert xml.stat().st_mtime_ns >= (root/relative).stat().st_mtime_ns,('stale receipt',relative)
suites=ET.parse(xml).findall('.//testsuite')
assert suites and all(int(v.get(k,'0'))==0 for v in suites for k in ('failures','errors','skipped'))
cases=ET.parse(xml).findall('.//testcase');count=len(cases)
assert sum('test_dsi_'in c.get('name','')for c in cases)>=199
assert len({c.get('classname')for c in cases})==10
manifest_path=root/'work/dsi-primary/manifest.json';manifest=json.loads(manifest_path.read_text())
scopes={'ti83':'SLLSEC1I October2020 pages1,6-8,9 hold requirement,10-29 read. Page8 electrical min/max table rendered and visually inspected including duplicated100ohm clockcode01 row; no guessed correction. Not Q1 device qualification or full hardware conformance.',
 'linux-display':'Linux v6.12 lines14-79 direction-specific packet data types read; DCS command enumeration not treated as complete normative set or implemented panel.',
 'linux-host':'Linux v6.12 lines459-580 packet classifiers/header representation,655-810 compression/generic write and827-965 generic/DCS reads/write buffer helpers read. ECC TODO and absent wireCRC distinguish software size from complete packet.'}
for key,entry in manifest.items():
    ext='pdf'if key=='ti83'else'txt'
    assert entry['sha256']==hashlib.sha256((manifest_path.parent/(key+'.'+ext)).read_bytes()).hexdigest()
    entry.update(read_scope=scopes[key],individual_local_tests_completed=True)
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
original=next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='mipi_dsi')
before={v['key']for v in original['form_parameters']};after={v['key']for v in registry.parameter_fields('mipi_dsi')}
native={v['key']:v['description']for v in m.DECLARATIONS}
native['payload_bytes']='Actual long-packet application octets fit actual word count0..65535, plus separate classic header4/CRC2. Short command data belongs inside header, not long application payload. Pixel complete groups, device buffer/minimumWC and PHY timing remain separate.'
spec=dict(technology='mipi_dsi',native=native,removed={k:m.REMOVED[k]for k in before-after},sources=list(m.SOURCES),
 revisions=list(m.SOURCES.values()),scope=[
 'Every declared native parameter reviewed for meaning, applicability, type/unit/bounds/dependencies, revision/source, proposal and actual evidence; every retained NIS scenario field is application policy. No2.5G global default or inherited CAN queue/retry/priority default.',
 'DSI1.3.2 vs DSI-2 v2.2 and DCS2.1 public primary summaries checked2026-10-02. DSI legacy D-PHY differs registered DSI-2 C-PHY/A-PHY/advancedD-PHY paths. Hybrid/VRR/RGB48 require revision2.2/endpoints; actual DCS revision and compression feature source remain separate. Member norms/CTS not obtained or certified.',
 'Direction-qualified classic DSI short/long opcode lists from pinned Linuxv6.12 differ CSI numeric ranges:0x09long and0x37short. Basic DI0..3VC/6bitDT,4byte short vsWC+6long. Kernel helper size does not include full physical CRC and has ECCgenerationTODO; no claim of executable NIS full codec.',
 'Generic write0/1/2 parameters and DCS opcode-plus-parameters1/2 choose short; longer command uses own long datatype/WC. Generic read max2parameters and DCSread1 require actual reverse capability. SET_MAX_RETURN sets returned long bound rather than measured response.',
 'RGB56516, packedRGB666 four pixels/nine octets, looseRGB666 useful18/wire24, RGB88824 have separate exact pixel/WC/group/DI checks. No truncating partial groups or applying camera RAWpacking to display packets.',
 'TI83 DSI1.02/D-PHY1.00 input80..1000Mbit/s and1/2/3/4lanes distinct LatticeRX minima. No virtual-channel/reverse/BTA/command mode support. I2C7bit44/45 fromADDRpin distinct8bit58/5Aaddress-cycle bytes; separate canonical control path and<=400kclock. No guessed installed address.',
 'TI DSI40..500MHz clock uses own5MHz bucket8..100 and exact500MHzendpoint. LVDS25..154MHz output depends on actual continuousDSIclock/divisor1..25 or25..154MREFCLK/multiplier1..4 and six range buckets. Wrong source register, reserved codes and noncontinuous DSI-source clock rejected. Required control and bridge output bindings stay separate.',
 'TI power/temperature/receiver electrical/setup/hold/REFCLK jitter/duty/edge limits use nonQ1 source. LVDS external90..132ohm load differs internal100/200near-end termination; data versus clock swing tables separated. Duplicated100ohm clockcode01 row requires actual manufacturer clarification, not assumed correction.',
 'TI syncdelay>=32 plus additional pipeline differs panel-selected geometry/porches and test-only vertical/front-porch registers. Test pattern disables DSI reception and proves output path only. Power/reset/PLL/ULPS sequence and recommended minimum waits source-qualified; no example200nF or resolution/FPS as universal installed default.',
 'Lattice IP4.2.0 DSI-2 RX only, no CSI TX inheritance. GeneratedSoft8/Hard8or16 PPI determines byteclock and32/64controller. DSI minimum long WC14/34 differs CSI6/10. RXFIFO depth/stalls, free/CSRclock, dynamic AXI2ms wait, extra Softprepare/zero and PHYidle clocks checked. EoTP-disabled MPPT and known two-bit ECCreporting exception need actual acceptance evidence; no full safety certificate.',
 f'{count} isolated SQL tests passed, including199 DSI cases and nine shared consumer suites. Confirmed330k controlclock/7bit45/RGB666packed2430byteWC/640Mlane survive rejected invalid packing edit. Complete cumulative native regression and release gate remain required before delivery.'
 ],validation=dict(status='PASS',tests_passed=count,isolated_sql=True,selected_scope='199 DSI tests plus nine shared parameter/default/rate/physical/capacity suites',complete_release_gate='NOT_RUN'),not_certified=[
 'Complete member-only DSI/DSI-2/DCS/PHY normative text and CTS, all vendor implementations, actual physical qualification and complete display/command/PHY runtime executors.',
 'ST AN4860 public PDF downloads failed; no field depends on its unread tables and no ST-specific parameter verification is claimed. Primary manufacturer/implementation bounds are explicitly qualified to their actual source.',
 'Local scalarVALID is not resolved hardware provenance, full codec/line/transition/buffer schedule, calibrated E2E trace, capacity or functional/safety/security acceptance. MODEL_MISSING stays explicit; no production delivery.'
 ])
(root/'work/dsi-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n')
print(json.dumps({'tests_passed':count,'native_fields':len(native),'removed':len(before-after)}))
